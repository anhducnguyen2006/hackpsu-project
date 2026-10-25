from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedPrincipal, require_principal
from app.limits import analysis_gate

from app.api.schemas import (
    AnalysisRequest,
    DatasetAnalysisCommand,
    DatasetAnalysisResponse,
    DatasetResourceRequest,
    DatasetResourcesResponse,
    ExploreRequest,
    ExploratoryAnalysisResponse,
)
from app.analysis.service import DatasetAnalysisService
from app.assessment.gemini import GeminiService
from app.config import settings
from app.demo import demo_analysis, demo_exploration
from app.discovery.dataverse import DataverseRepositoryError
from app.discovery.uci import UCIRepositoryError, UCIRepositoryService
from app.discovery.zenodo import ZenodoRepositoryError
from app.ingestion.guard import DownloadRejected
from app.ingestion.retrieve import SelectionError, list_resources

router = APIRouter(
    prefix="/dev",
    tags=["development"],
    dependencies=[Depends(require_principal)],
)
adapter = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)
analysis_service = DatasetAnalysisService(adapter, GeminiService())


@router.get("/dataset-test")
def dataset_test(
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> dict:
    """Development-only proof of concept for UCI dataset ID 320.

    Disabled unless DEV_ROUTES_ENABLED is set. Authentication runs first, so a
    missing token cannot download the dataset.
    """
    del principal
    if not settings.dev_routes_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return adapter.fetch_and_profile(320)
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


analysis_router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
    dependencies=[Depends(require_principal)],
)


@analysis_router.post("/resources", response_model=DatasetResourcesResponse)
def dataset_resources(
    request: DatasetResourceRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> DatasetResourcesResponse:
    """List files for one dataset after re-reading provider metadata."""
    del principal
    try:
        return list_resources(request.dataset_id)
    except SelectionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (DownloadRejected, UCIRepositoryError, DataverseRepositoryError, ZenodoRepositoryError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@analysis_router.post("/analyze", response_model=DatasetAnalysisResponse)
def analyze_selected_dataset(
    request: DatasetAnalysisCommand,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> DatasetAnalysisResponse:
    """Analyze one UCI dataset or one server-resolved external file."""
    with analysis_gate.limit(principal.sub):
        if settings.demo_mode and request.dataset_id == "uci:320":
            return demo_analysis()
        try:
            return analysis_service.analyze_selected(
                request.dataset_id,
                request.research_question,
                request.resource_id,
                user_sub=principal.sub,
            )
        except SelectionError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except (DownloadRejected, UCIRepositoryError, DataverseRepositoryError, ZenodoRepositoryError) as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@analysis_router.post("/{dataset_id}/analyze", response_model=DatasetAnalysisResponse)
def analyze_dataset(
    dataset_id: str,
    request: AnalysisRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> DatasetAnalysisResponse:
    with analysis_gate.limit(principal.sub):
        if settings.demo_mode and dataset_id == "uci:320":
            return demo_analysis()
        try:
            return analysis_service.analyze(dataset_id, request, user_sub=principal.sub)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except UCIRepositoryError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@analysis_router.post(
    "/{dataset_id}/explore", response_model=ExploratoryAnalysisResponse
)
def explore_dataset(
    dataset_id: str,
    request: ExploreRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> ExploratoryAnalysisResponse:
    with analysis_gate.limit(principal.sub):
        if settings.demo_mode and dataset_id == "uci:320":
            if request.independent_variable != "studytime" or request.outcome_variable != "G3":
                raise HTTPException(
                    status_code=400,
                    detail="DEMO_MODE supports the cached studytime versus G3 analysis only.",
                )
            return demo_exploration()
        try:
            return analysis_service.explore(dataset_id, request)
        except SelectionError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except UCIRepositoryError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
