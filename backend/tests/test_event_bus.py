import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.readings.service import ReadingIngest
from src.domain.events.bus import EventBus
from src.domain.events.events import CommandFailed, ReadingCreated
from src.domain.sensors.reading import Reading

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
SRC = Path(__file__).resolve().parents[1] / "src"


def failed(message="boom"):
    return CommandFailed(
        device_id=uuid.uuid4(), location_id=None, zone_id=None, command_type="stop_pump", message=message
    )


# --- The bus ---

def test_handlers_run_in_subscription_order():
    bus, calls = EventBus(), []
    bus.subscribe(CommandFailed, lambda e: calls.append("first"))
    bus.subscribe(CommandFailed, lambda e: calls.append("second"))
    bus.publish(failed())
    assert calls == ["first", "second"]


def test_events_are_routed_by_class():
    bus, calls = EventBus(), []
    bus.subscribe(ReadingCreated, lambda e: calls.append("reading"))
    bus.publish(failed())
    assert calls == []


def test_a_failing_subscriber_does_not_stop_the_others():
    bus, calls = EventBus(), []
    bus.subscribe(CommandFailed, lambda e: 1 / 0)
    bus.subscribe(CommandFailed, lambda e: calls.append(e.message))
    bus.publish(failed("still delivered"))          # must not raise
    assert calls == ["still delivered"]


def test_publishing_with_no_subscribers_is_fine():
    EventBus().publish(failed())


# --- ReadingIngest: the tracking rule ---

class FakeDevices:
    def __init__(self, device):
        self.device = device

    def get_device(self, device_id):
        return self.device if device_id == self.device.id else None


class FakeReadings:
    def __init__(self):
        self.saved = []

    def add(self, reading):
        self.saved.append(reading)
        return reading


def sensor(tracking_enabled, zone_id=None, location_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), role="sensor", tracking_enabled=tracking_enabled,
        zone_id=zone_id, location_id=location_id,
    )


def ingest_one(device):
    bus, published, readings = EventBus(), [], FakeReadings()
    bus.subscribe(ReadingCreated, published.append)
    ingest = ReadingIngest(FakeDevices(device), readings, select_adapter=lambda d: None, bus=bus)
    ingest.record(
        device.id,
        reading=Reading(device_id=device.id, value=0.10, unit="vwc", source="mqtt", recorded_at=NOW),
    )
    return readings.saved, published


def test_tracking_on_publishes_reading_created_with_device_location():
    zone, location = uuid.uuid4(), uuid.uuid4()
    device = sensor(tracking_enabled=True, zone_id=zone, location_id=location)

    saved, published = ingest_one(device)

    assert len(saved) == 1
    [event] = published
    assert (event.device_id, event.value, event.unit, event.source) == (device.id, 0.10, "vwc", "mqtt")
    assert event.recorded_at == NOW
    assert (event.location_id, event.zone_id) == (location, zone)


def test_tracking_off_stores_the_reading_but_does_not_publish():
    saved, published = ingest_one(sensor(tracking_enabled=False))
    assert len(saved) == 1
    assert published == []


def test_unassigned_sensor_publishes_null_location_and_zone():
    _, [event] = ingest_one(sensor(tracking_enabled=True))
    assert event.location_id is None and event.zone_id is None


# --- Publishers do not know about alerts ---

@pytest.mark.parametrize(
    "path",
    [
        "application/readings/service.py",            # ReadingIngest
        "application/commands/service.py",            # CommandService
        "application/devices/actuator_state_service.py",  # the transition service
    ],
)
def test_publishers_do_not_import_the_alert_repository(path):
    source = (SRC / path).read_text(encoding="utf-8")
    assert "AlertRepository" not in source
    assert "alert_repository" not in source