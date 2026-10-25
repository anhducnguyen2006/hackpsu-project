import logging
import time

from fastapi import APIRouter

from app.api.schemas import DiscoveryRequest, DiscoveryResponse
from app.assessment.gemini import GeminiService
from app.config import settings
from app.demo import demo_search
from app.discovery.embeddings import EmbeddingService
from app.discovery.search import DiscoveryService, build_external_providers
from app.discovery.uci import UCIRepositoryService

router = APIRouter(prefix="/discovery", tags=["discovery"])
logger = logging.getLogger(__name__)
repository = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)
service = DiscoveryService(
    repository,
    GeminiService(),
    build_external_providers(),
    EmbeddingService(),
)


@router.post("/search", response_model=DiscoveryResponse)
def search(request: DiscoveryRequest) -> DiscoveryResponse:
    started = time.perf_counter()
    if settings.demo_mode:
        interpretation, datasets, warnings, processing_mode = demo_search(
            request.research_question
        )
        return DiscoveryResponse(
            interpretation=interpretation,
            datasets=datasets[: request.limit],
            explanation="DEMO_MODE is enabled. These are cached verified UCI results, not a live repository search.",
            warnings=warnings,
            processing_mode=processing_mode,
            ranking_status="demo_cached",
        )
    (
        interpretation,
        datasets,
        warnings,
        processing_mode,
        ranking_status,
    ) = service.search_with_status(
        request.research_question, request.limit
    )
    explanation = (
        "Results are ranked using verified repository metadata and local semantic "
        "similarity. Semantic similarity is not research suitability; full suitability "
        "requires data profiling."
        if datasets
        else "No UCI datasets matched the verified metadata search terms."
    )
    response = DiscoveryResponse(
        interpretation=interpretation,
        datasets=datasets,
        explanation=explanation,
        warnings=warnings,
        processing_mode=processing_mode,
        ranking_status=ranking_status,
    )
    logger.info(
        "discovery stage=serialization elapsed_ms=%.1f datasets=%d mode=%s",
        (time.perf_counter() - started) * 1000,
        len(response.datasets),
        response.processing_mode,
    )
    return response
