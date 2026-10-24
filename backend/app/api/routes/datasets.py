from fastapi import APIRouter, HTTPException

from app.config import settings
from app.discovery.uci import UCIRepositoryError, UCIRepositoryService

router = APIRouter(prefix="/dev", tags=["development"])
adapter = UCIRepositoryService(catalog_ttl=settings.uci_catalog_ttl_seconds)


@router.get("/dataset-test")
def dataset_test() -> dict:
    """Development-only proof of concept for UCI dataset ID 320."""
    try:
        return adapter.fetch_and_profile(320)
    except UCIRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
