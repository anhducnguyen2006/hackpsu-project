from fastapi import APIRouter

from app.api.schemas import DiscoveryRequest, DiscoveryResponse
from app.assessment.gemini import GeminiService
from app.config import settings
from app.discovery.search import DiscoveryService
from app.discovery.uci import UCIRepositoryService

router = APIRouter(prefix="/discovery", tags=["discovery"])
repository = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)
service = DiscoveryService(repository, GeminiService())


@router.post("/search", response_model=DiscoveryResponse)
def search(request: DiscoveryRequest) -> DiscoveryResponse:
    interpretation, datasets, warnings, processing_mode = service.search(
        request.research_question, request.limit
    )
    explanation = (
        "Results are ranked using verified UCI metadata. Preliminary relevance is "
        "not the same as research suitability; full suitability requires data profiling."
        if datasets
        else "No UCI datasets matched the verified metadata search terms."
    )
    return DiscoveryResponse(
        interpretation=interpretation,
        datasets=datasets,
        explanation=explanation,
        warnings=warnings,
        processing_mode=processing_mode,
    )
