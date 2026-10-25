import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    ResearchHistoryItem,
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
)


router = APIRouter(prefix="/research", tags=["research"])
logger = logging.getLogger(__name__)
embedding_service = EmbeddingService()


@router.get("/history", response_model=list[ResearchHistoryItem])
def research_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ResearchHistoryItem]:
    return [
        ResearchHistoryItem.model_validate(item)
        for item in list_recent_research_questions(limit)
    ]


@router.post("/similar", response_model=list[SimilarResearchItem])
def similar_research(
    request: SimilarResearchRequest,
) -> list[SimilarResearchItem]:
    try:
        embedding = embedding_service.embed_text(request.research_question)
        matches = find_similar_research_questions(
            embedding,
            embedding_service.model_identifier,
            limit=5,
        )
        return [SimilarResearchItem.model_validate(item) for item in matches]
    except Exception:
        logger.warning("research similarity unavailable; returning no matches")
        return []


@router.get("/{query_id}/session", response_model=ResearchSessionResponse)
def research_session(query_id: int) -> ResearchSessionResponse:
    item = get_research_session(query_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research query not found")
    return ResearchSessionResponse.model_validate(item)


@router.get("/{query_id}", response_model=ResearchHistoryItem)
def research_query(query_id: int) -> ResearchHistoryItem:
    item = get_research_question(query_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research query not found")
    return ResearchHistoryItem.model_validate(item)
