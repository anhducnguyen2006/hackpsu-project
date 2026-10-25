from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import ResearchHistoryItem
from app.research.repository import (
    get_research_question,
    list_recent_research_questions,
)


router = APIRouter(prefix="/research", tags=["research"])


@router.get("/history", response_model=list[ResearchHistoryItem])
def research_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ResearchHistoryItem]:
    return [
        ResearchHistoryItem.model_validate(item)
        for item in list_recent_research_questions(limit)
    ]


@router.get("/{query_id}", response_model=ResearchHistoryItem)
def research_query(query_id: int) -> ResearchHistoryItem:
    item = get_research_question(query_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research query not found")
    return ResearchHistoryItem.model_validate(item)
