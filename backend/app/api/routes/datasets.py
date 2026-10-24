from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AnalysisRequest,
    DatasetAnalysisResponse,
    ExploreRequest,
    ExploratoryAnalysisResponse,
)
from app.analysis.service import DatasetAnalysisService
from app.assessment.gemini import GeminiService
from app.config import settings
from app.demo import demo_analysis, demo_exploration
from app.discovery.uci import UCIRepositoryError, UCIRepositoryService

router = APIRouter(prefix="/dev", tags=["development"])
adapter = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)
analysis_service = DatasetAnalysisService(adapter, GeminiService())


@router.get("/dataset-test")
def dataset_test() -> dict:
    """Development-only proof of concept for UCI dataset ID 320."""
    try:
        return adapter.fetch_and_profile(320)
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


analysis_router = APIRouter(prefix="/datasets", tags=["datasets"])


@analysis_router.post("/{dataset_id}/analyze", response_model=DatasetAnalysisResponse)
def analyze_dataset(
    dataset_id: str, request: AnalysisRequest
) -> DatasetAnalysisResponse:
    if settings.demo_mode and dataset_id == "uci:320":
        return demo_analysis()
    try:
        return analysis_service.analyze(dataset_id, request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@analysis_router.post(
    "/{dataset_id}/explore", response_model=ExploratoryAnalysisResponse
)
def explore_dataset(
    dataset_id: str, request: ExploreRequest
) -> ExploratoryAnalysisResponse:
    if settings.demo_mode and dataset_id == "uci:320":
        if request.independent_variable != "studytime" or request.outcome_variable != "G3":
            raise HTTPException(
                status_code=400,
                detail="DEMO_MODE supports the cached studytime versus G3 analysis only.",
            )
        return demo_exploration()
    try:
        return analysis_service.explore(dataset_id, request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
