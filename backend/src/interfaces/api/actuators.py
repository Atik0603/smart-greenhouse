from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.actuators.composition import build_actuator_port
from src.application.actuators.dto import AppliedCommandDto, ApplyRequest, ExecutionDto
from src.application.actuators.service import ActuatorExecutionService
from src.domain.actuators.errors import NotAnActuatorError, PolicyViolationError
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

router = APIRouter(prefix="/api/actuators", tags=["actuators"])


def get_execution_service(db: Session = Depends(get_db)) -> ActuatorExecutionService:
    return ActuatorExecutionService(
        build_actuator_port(db), DeviceRepository(db), ExecutionLogRepository(db)
    )


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


@router.post(
    "/{device_id}/apply",
    response_model=AppliedCommandDto,
    responses={
        400: {"description": "Device is not an actuator"},
        404: {"description": "Device not found"},
        409: {"description": "Blocked by a policy (e.g. max run time); the attempt is still logged"},
    },
    summary="Demo: send a command through the decorated actuator port (Phase 10 replaces this with Command)",
)
def apply_command(
    device_id: UUID,
    request: ApplyRequest,
    service: ActuatorExecutionService = Depends(get_execution_service),
) -> AppliedCommandDto:
    try:
        return service.apply(device_id, request.command, request.payload)
    except DeviceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NotAnActuatorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PolicyViolationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc