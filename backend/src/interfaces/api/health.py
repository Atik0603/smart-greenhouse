from fastapi import APIRouter

from src.infrastructure.db import check_db_connection

router = APIRouter()


@router.get("/health")
def health():
    db_status = check_db_connection()
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
    }