from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DeviceDto(BaseModel):
    id: UUID
    device_type: str
    role: Literal["sensor", "actuator"]
    device_family: str
    display_name: str
    default_config: dict
    zone_id: UUID | None = None
    location_id: UUID | None = None
    sampling_interval_seconds: int = 300
    tracking_enabled: bool = True
    state: str | None = None                      
    allowed_commands: list[str] = []

class SamplingUpdateRequest(BaseModel):
    sampling_interval_seconds: int
    tracking_enabled: bool


class TransitionRequest(BaseModel):
    target: str


class ActuatorStateDto(BaseModel):
    device_id: UUID
    state: str
    allowed_commands: list[str]