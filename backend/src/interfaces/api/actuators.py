from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.application.actuators.dto import ExecutionDto
from src.application.actuators.service import ActuatorExecutionService
from src.infrastructure.db import get_db
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

router = APIRouter(prefix="/api/actuators", tags=["actuators"])


def get_execution_service(db: Session = Depends(get_db)) -> ActuatorExecutionService:
    return ActuatorExecutionService(ExecutionLogRepository(db))


@router.get(
    "/executions",
    response_model=list[ExecutionDto],
    summary="Recent actuator execution attempts (success and blocked), newest first",
)
def list_executions(
    limit: int = Query(default=20, description="How many rows to return (1–200)"),
    service: ActuatorExecutionService = Depends(get_execution_service),
) -> list[ExecutionDto]:
    return service.list_recent(limit)