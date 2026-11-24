from functools import lru_cache

from src.application.alerts.subscribers import (
    AlertPersistenceSubscriber,
    MoistureThresholdSubscriber,
    SessionFactory,
)
from src.domain.events.bus import EventBus
from src.domain.events.events import (
    ActuatorStateChanged,
    CommandFailed,
    ReadingCreated,
    ThresholdCrossed,
)
from src.infrastructure.db import SessionLocal


def build_event_bus(session_factory: SessionFactory = SessionLocal) -> EventBus:
    """Create a bus and subscribe every handler, in a fixed order."""
    bus = EventBus()
    threshold = MoistureThresholdSubscriber(bus, session_factory)
    alerts = AlertPersistenceSubscriber(bus, session_factory)

    bus.subscribe(ReadingCreated, threshold.on_reading)
    bus.subscribe(ThresholdCrossed, alerts.on_threshold)
    bus.subscribe(CommandFailed, alerts.on_command)
    bus.subscribe(ActuatorStateChanged, alerts.on_state)
    return bus


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    """The single application-wide bus (requests, the sampler, and Phase 12's socket)."""
    return build_event_bus()