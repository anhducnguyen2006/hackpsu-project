import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthenticatedPrincipal, require_principal
from app.limits import similarity_gate
from database.connection import DatabaseUnavailableError

from app.api.schemas import (
    ResearchHistoryItem,
    ResearchGraphResponse,
    ResearchSessionResponse,
    SimilarResearchItem,
    SimilarResearchRequest,
)
from app.discovery.embeddings import EmbeddingService
from app.research.repository import (
    find_similar_research_questions,
    get_research_question,
    get_research_session,
    list_recent_research_questions,
    get_research_graph,
)


router = APIRouter(
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(require_principal)],
)
logger = logging.getLogger(__name__)
embedding_service = EmbeddingService()
_STORAGE_ERRORS = (DatabaseUnavailableError, psycopg.Error)


def _storage_unavailable(error: Exception) -> HTTPException:
    if isinstance(error, psycopg.errors.UndefinedColumn):
        return HTTPException(
            status_code=503,
            detail=(
                "Research storage is missing owner enforcement. "
                "Apply migration 004_research_query_owner.sql before using research history."
            ),
        )
    return HTTPException(status_code=503, detail="Research storage is unavailable.")


@router.get("/history", response_model=list[ResearchHistoryItem])
def research_history(
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> list[ResearchHistoryItem]:
    try:
        items = list_recent_research_questions(principal.sub, limit)
    except _STORAGE_ERRORS as error:
        raise _storage_unavailable(error) from error
    return [
        ResearchHistoryItem.model_validate(item)
        for item in items
    ]


@router.post("/similar", response_model=list[SimilarResearchItem])
def similar_research(
    request: SimilarResearchRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> list[SimilarResearchItem]:
    with similarity_gate.limit(principal.sub):
        try:
            embedding = embedding_service.embed_text(request.research_question)
            matches = find_similar_research_questions(
                embedding,
                embedding_service.model_identifier,
                principal.sub,
                limit=5,
            )
            return [SimilarResearchItem.model_validate(item) for item in matches]
        except _STORAGE_ERRORS as error:
            raise _storage_unavailable(error) from error
        except Exception:
            # Embedding failure is an explicit empty result, not a saved-history claim.
            logger.warning("research similarity unavailable; returning no matches")
            return []


@router.get("/graph", response_model=ResearchGraphResponse)
def research_graph(
    limit: int = Query(default=100, ge=1, le=500),
    research_id: int | None = Query(default=None, ge=1),
) -> ResearchGraphResponse:
    """Return persisted research connections only; no graph generation occurs here."""
    graph = get_research_graph(limit=limit, research_id=research_id)
    return ResearchGraphResponse.model_validate(graph)


@router.get("/{query_id}/session", response_model=ResearchSessionResponse)
def research_session(
    query_id: int,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> ResearchSessionResponse:
    try:
        item = get_research_session(query_id, principal.sub)
    except _STORAGE_ERRORS as error:
        raise _storage_unavailable(error) from error
    if item is None:
        raise HTTPException(status_code=404, detail="Research query not found")
    return ResearchSessionResponse.model_validate(item)


@router.get("/{query_id}", response_model=ResearchHistoryItem)
def research_query(
    query_id: int,
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> ResearchHistoryItem:
    try:
        item = get_research_question(query_id, principal.sub)
    except _STORAGE_ERRORS as error:
        raise _storage_unavailable(error) from error
    if item is None:
        raise HTTPException(status_code=404, detail="Research query not found")
    return ResearchHistoryItem.model_validate(item)
