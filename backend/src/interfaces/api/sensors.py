from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.sensors.service import SensorService, UnknownSensorTypeError
from src.infrastructure.db import get_db

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