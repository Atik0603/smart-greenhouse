from uuid import UUID

from pydantic import BaseModel, Field


# --- Requests (JSON coming IN) ---

class ZoneCreateRequest(BaseModel):
    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float
    schedule: dict = Field(default_factory=dict)


class LocationConfigCreateRequest(BaseModel):
    location_name: str
    zones: list[ZoneCreateRequest]


class ZoneUpdateRequest(BaseModel):
    name: str | None = None
    moisture_threshold_low: float | None = None
    moisture_threshold_high: float | None = None
    schedule: dict | None = None


class DeviceZoneAssignmentRequest(BaseModel):
    zone_id: UUID | None


# --- Responses (JSON going OUT) ---

class LocationSummaryDto(BaseModel):
    id: UUID
    name: str


class ZoneReadDto(BaseModel):
    id: UUID
    location_id: UUID
    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float
    schedule: dict


class LocationConfigResponse(BaseModel):
    location: LocationSummaryDto
    zones: list[ZoneReadDto]