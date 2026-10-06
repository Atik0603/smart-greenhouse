from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.readings.dto import ReadingDto
from src.application.readings.service import ReadingIngest
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.sensors.ports import SensorReadError
from src.infrastructure.adapters.sensors.selector import select_sensor_adapter
from src.application.sensors.service import SensorService, UnknownSensorTypeError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


class SensorCreateRequest(BaseModel):
    type: str
    display_name: str | None = None


class SensorResponse(BaseModel):
    id: UUID
    device_type: str
    display_name: str
    default_config: dict


@router.get("", response_model=list[SensorResponse])
def list_sensors(db: Session = Depends(get_db)):
    service = SensorService(db)
    return service.list_sensors()


@router.post("", response_model=SensorResponse, status_code=201)
def create_sensor(payload: SensorCreateRequest, db: Session = Depends(get_db)):
    service = SensorService(db)
    display_name = payload.display_name or payload.type.capitalize()
    try:
        return service.create_sensor(payload.type, display_name)
    except UnknownSensorTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def get_reading_ingest(db: Session = Depends(get_db)) -> ReadingIngest:
    return ReadingIngest(DeviceRepository(db), ReadingRepository(db), select_sensor_adapter)


@router.post(
    "/{sensor_id}/read",
    response_model=ReadingDto,
    status_code=status.HTTP_201_CREATED,
    summary="Read a sensor now through its adapter and store the reading",
)
def read_sensor(
    sensor_id: UUID,
    ingest: ReadingIngest = Depends(get_reading_ingest),
) -> ReadingDto:
    try:
        return ingest.record(sensor_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SensorReadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{sensor_id}/readings",
    response_model=list[ReadingDto],
    summary="List a sensor's most recent stored readings, newest first",
)
def list_sensor_readings(
    sensor_id: UUID,
    limit: int = 20,
    ingest: ReadingIngest = Depends(get_reading_ingest),
) -> list[ReadingDto]:
    try:
        return ingest.list_recent(sensor_id, limit)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SensorReadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc