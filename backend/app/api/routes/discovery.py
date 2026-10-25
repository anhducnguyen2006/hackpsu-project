import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api import schemas
from app.api.schemas import DiscoveryGraphRequest, DiscoveryRequest, DiscoveryResponse, KnowledgeGraphResponse
from app.auth import AuthenticatedPrincipal, require_principal
from app.limits import discovery_gate
from app.assessment.gemini import GeminiService
from app.config import settings
from app.demo import demo_search
from app.discovery.embeddings import EmbeddingService
from app.discovery.search import DiscoveryService, build_external_providers
from app.discovery.uci import UCIRepositoryService
from app.research.repository import persist_discovery_result

router = APIRouter(
    prefix="/discovery",
    tags=["discovery"],
    dependencies=[Depends(require_principal)],
)
logger = logging.getLogger(__name__)
repository = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)
service = DiscoveryService(
    repository,
    GeminiService(),
    build_external_providers(),
    EmbeddingService(),
)


def _persist_discovery_result_background(
    question: str,
    normalized_question: str | None,
    dataset_payloads: list[dict],
    embedding_service: object | None,
    user_sub: str,
) -> None:
    """Best-effort persistence with a fresh repository transaction.

    ``user_sub`` is the verified subject captured on the request. The task does
    not read the request or a request-scoped connection. Anonymous history is
    never written.
    """
    started = time.perf_counter()
    if not isinstance(user_sub, str) or not user_sub.strip():
        logger.error(
            "discovery background persistence refused because no authenticated owner was supplied"
        )
        return
    try:
        datasets = [
            schemas.DatasetResult.model_validate(payload)
            for payload in dataset_payloads
        ]
        query_id = persist_discovery_result(
            question=question,
            normalized_question=normalized_question,
            datasets=datasets,
            embedding_service=embedding_service,
            user_sub=user_sub.strip(),
        )
        logger.info(
            "discovery stage=background_persistence elapsed_ms=%.1f query_id=%s datasets=%d",
            (time.perf_counter() - started) * 1000,
            query_id,
            len(datasets),
        )
    except Exception as error:
        # History is useful but not required to answer a live discovery request.
        # Exception text is deliberately omitted because drivers can echo conninfo.
        logger.error(
            "discovery background persistence failed datasets=%d elapsed_ms=%.1f error_type=%s",
            len(dataset_payloads),
            (time.perf_counter() - started) * 1000,
            type(error).__name__,
        )


@router.post("/search", response_model=DiscoveryResponse)
def search(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> DiscoveryResponse:
    started = time.perf_counter()
    with discovery_gate.limit(principal.sub):
        return _search(request, background_tasks, principal, started)


def _search(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    principal: AuthenticatedPrincipal,
    started: float,
) -> DiscoveryResponse:
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
    background_tasks.add_task(
        _persist_discovery_result_background,
        request.research_question,
        interpretation.refined_question if interpretation else None,
        [dataset.model_dump(mode="json") for dataset in datasets],
        getattr(service, "embedding_service", None),
        principal.sub,
    )
    explanation = (
        "Results are ranked using verified repository metadata and local semantic "
        "similarity. Semantic similarity is not research suitability; full suitability "
        "requires data profiling."
        if datasets
        else "No eligible public tabular datasets were both verified and relevant enough to return."
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


@router.post("/graph", response_model=KnowledgeGraphResponse)
def graph(
    request: DiscoveryGraphRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> KnowledgeGraphResponse:
    """Build a graph from this process's cached normalized search records."""
    with discovery_gate.limit(principal.sub):
        if settings.demo_mode:
            return KnowledgeGraphResponse(nodes=[], edges=[])
        return service.graph_for_search(request.research_question, request.limit)
