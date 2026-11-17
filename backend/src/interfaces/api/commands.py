from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.application.commands.composition import build_command_service
from src.application.commands.dto import CommandLogDto, CommandRequest
from src.application.commands.service import CommandService
from src.domain.commands.errors import InvalidCommandPayloadError, UnknownCommandError
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.db import get_db

router = APIRouter(prefix="/api/commands", tags=["commands"])


def get_command_service(db: Session = Depends(get_db)) -> CommandService:
    return build_command_service(db)


@router.post(
    "",
    response_model=CommandLogDto,
    responses={
        400: {"description": "Unknown command type or invalid payload (no log row)"},
        404: {"description": "Device not found, or not an actuator (no log row)"},
        409: {
            "model": CommandLogDto,
            "description": "Rejected: not allowed in the actuator's current state (logged)",
        },
    },
    summary="Submit a command; returns its command_log row (success/failed 200, rejected 409)",
)
def submit_command(
    request: CommandRequest,
    service: CommandService = Depends(get_command_service),
):
    try:
        entry = service.submit(request.command_type, request.device_id, request.payload)
    except DeviceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (UnknownCommandError, InvalidCommandPayloadError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if entry.status == "rejected":
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=jsonable_encoder(entry))
    return entry


@router.get(
    "",
    response_model=list[CommandLogDto],
    summary="Command history from command_log, newest first",
)
def list_commands(
    limit: int = Query(default=50, ge=1, le=200, description="How many rows (1–200)"),
    service: CommandService = Depends(get_command_service),
) -> list[CommandLogDto]:
    return service.list_recent(limit)