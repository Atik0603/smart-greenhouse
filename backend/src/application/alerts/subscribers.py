from typing import Callable

from sqlalchemy.orm import Session

from src.domain.events.bus import EventBus
from src.domain.events.events import (
    ActuatorStateChanged,
    AlertCreated,
    CommandFailed,
    ReadingCreated,
    ThresholdCrossed,
)
from src.infrastructure.persistence.alert_repository import AlertRepository
from src.infrastructure.persistence.location_repository import LocationRepository

SessionFactory = Callable[[], Session]

MOISTURE_UNIT = "vwc"


class MoistureThresholdSubscriber:
    """Turns a low moisture reading into a ThresholdCrossed event. Stores nothing itself."""

    def __init__(self, bus: EventBus, session_factory: SessionFactory) -> None:
        self._bus = bus
        self._session_factory = session_factory

    def on_reading(self, event: ReadingCreated) -> None:
        if event.unit != MOISTURE_UNIT or event.zone_id is None:
            return                                  # not moisture, or no zone to compare with
        with self._session_factory() as db:
            found = LocationRepository(db).get_zone(event.zone_id)
        if found is None:
            return
        zone, _location_id = found
        if event.value < zone.moisture_threshold_low:       # strictly below
            self._bus.publish(
                ThresholdCrossed(
                    device_id=event.device_id,
                    location_id=event.location_id,
                    zone_id=event.zone_id,
                    moisture=event.value,
                    threshold_low=zone.moisture_threshold_low,
                    recorded_at=event.recorded_at,
                )
            )


class AlertPersistenceSubscriber:
    """The ONLY writer of alerts. Publishers never touch AlertRepository."""

    def __init__(self, bus: EventBus, session_factory: SessionFactory) -> None:
        self._bus = bus
        self._session_factory = session_factory

    def on_threshold(self, event: ThresholdCrossed) -> None:
        self._insert(event, "warning", "Moisture below zone low")

    def on_command(self, event: CommandFailed) -> None:
        self._insert(event, "warning", event.message)

    def on_state(self, event: ActuatorStateChanged) -> None:
        if event.state != "error":
            return
        self._insert(event, "critical", "Actuator entered error")

    def _insert(self, event, severity: str, message: str) -> None:
        with self._session_factory() as db:
            alert = AlertRepository(db).add(
                severity=severity,
                message=message,
                event_type=event.event_type,
                device_id=event.device_id,
                location_id=event.location_id,
                zone_id=event.zone_id,
            )
        self._bus.publish(
            AlertCreated(
                alert_id=alert.id,
                device_id=alert.device_id,
                location_id=alert.location_id,
                zone_id=alert.zone_id,
                severity=alert.severity,
                alert_type=alert.event_type,
                message=alert.message,
            )
        )