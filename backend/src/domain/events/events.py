from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID


@dataclass(frozen=True)
class ReadingCreated:
    event_type: ClassVar[str] = "reading.created"
    device_id: UUID
    value: float
    unit: str
    source: str
    recorded_at: datetime
    location_id: UUID | None
    zone_id: UUID | None


@dataclass(frozen=True)
class ThresholdCrossed:
    event_type: ClassVar[str] = "threshold.crossed"
    device_id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    moisture: float
    threshold_low: float
    recorded_at: datetime


@dataclass(frozen=True)
class CommandFailed:
    event_type: ClassVar[str] = "command.failed"
    device_id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    command_type: str
    message: str


@dataclass(frozen=True)
class ActuatorStateChanged:
    event_type: ClassVar[str] = "state.changed"
    device_id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    previous_state: str
    state: str


@dataclass(frozen=True)
class AlertCreated:
    """Published after an alert row is stored. Phase 12's WebSocket subscribes to this."""
    event_type: ClassVar[str] = "alert.created"
    alert_id: UUID
    device_id: UUID | None
    location_id: UUID | None
    zone_id: UUID | None
    severity: str
    alert_type: str
    message: str