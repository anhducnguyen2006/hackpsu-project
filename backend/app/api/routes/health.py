from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedPrincipal, require_principal
from database.connection import get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/database")
def database_health(
    principal: AuthenticatedPrincipal = Depends(require_principal),
) -> dict[str, str]:
    del principal
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return {
            "status": "connected",
            "database": "TigerData PostgreSQL",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

