from fastapi import APIRouter, HTTPException

from app.discovery.uci import UCIRepositoryError, UCIStudentPerformanceAdapter

router = APIRouter(prefix="/dev", tags=["development"])
adapter = UCIStudentPerformanceAdapter()


@router.get("/dataset-test")
def dataset_test() -> dict:
    """Development-only proof of concept for UCI dataset ID 320."""
    try:
        return adapter.fetch_and_profile()
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

