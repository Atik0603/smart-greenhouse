import os
import uuid
from datetime import datetime, timezone


import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Integration tests need TEST_DATABASE_URL pointing at a *_test database",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.application.events.composition import get_event_bus  # noqa: E402
from src.application.readings.service import ReadingIngest  # noqa: E402
from src.domain.events.events import CommandFailed  # noqa: E402
from src.domain.sensors.reading import Reading  # noqa: E402
from src.infrastructure.adapters.sensors.selector import select_sensor_adapter  # noqa: E402
from src.infrastructure.db import SessionLocal, engine  # noqa: E402
from src.infrastructure.persistence.device_repository import DeviceRepository  # noqa: E402
from src.infrastructure.persistence.reading_repository import ReadingRepository  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    assert engine.url.database.endswith("_test"), "Refusing to wipe a non-test database"
    monkeypatch.setenv("SAMPLER_ENABLED", "false")      # no background readings during these tests
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE alerts, command_log, actuator_execution_log, actuator_states, "
                "automation_rules, sensor_readings, devices, zones, locations CASCADE"
            )
        )
    with TestClient(app) as c:
        yield c


# --- seeding helpers ---

def seed_lab(client):
    """Lab Site A: Bench 1 (low 0.20) and Bench 2 (low 0.30), plus a simulation kit."""
    res = client.post(
        "/api/locations/config",
        json={
            "location_name": "Lab Site A",
            "zones": [
                {"name": "Bench 1", "moisture_threshold_low": 0.2, "moisture_threshold_high": 0.45},
                {"name": "Bench 2", "moisture_threshold_low": 0.3, "moisture_threshold_high": 0.6},
            ],
        },
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    zones = {z["name"]: z for z in body["zones"]}
    kit = client.post("/api/devices/provision", params={"family": "simulation"}).json()
    return body["location"], zones["Bench 1"], zones["Bench 2"], kit


def of_type(devices, device_type):
    return next(d for d in devices if d["device_type"] == device_type)


def assign(client, device_id, zone_id):
    res = client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": zone_id})
    assert res.status_code == 200, res.text


def set_tracking(client, device_id, enabled):
    res = client.patch(
        f"/api/devices/{device_id}/sampling",
        json={"sampling_interval_seconds": 60, "tracking_enabled": enabled},
    )
    assert res.status_code == 200, res.text


def ingest_moisture(device_id, value):
    """Ingest a translated reading through the real ReadingIngest (the MQTT path)."""
    device_uuid = uuid.UUID(str(device_id))       # JSON gives strings; the domain uses UUIDs
    with SessionLocal() as db:
        ingest = ReadingIngest(
            DeviceRepository(db), ReadingRepository(db), select_sensor_adapter, get_event_bus()
        )
        ingest.record(
            device_uuid,
            reading=Reading(
                device_id=device_uuid, value=value, unit="vwc", source="mqtt",
                recorded_at=datetime.now(timezone.utc),
            ),
        )


def scalar(sql, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def alerts(client, **params):
    res = client.get("/api/alerts", params=params)
    assert res.status_code == 200, res.text
    return res.json()


# --- The subscriber writes on a published event ---

def test_subscriber_inserts_alert_on_published_event(client):
    *_, kit = seed_lab(client)
    pump = of_type(kit, "water_pump")

    get_event_bus().publish(
        CommandFailed(
            device_id=pump["id"], location_id=None, zone_id=None,
            command_type="stop_pump", message="Published directly",
        )
    )

    [row] = alerts(client)
    assert (row["event_type"], row["severity"], row["message"]) == (
        "command.failed", "warning", "Published directly",
    )


# --- threshold.crossed, with tracking and zone filters ---

def test_low_moisture_on_bench_1_creates_threshold_alert_for_that_zone(client):
    location, bench1, bench2, kit = seed_lab(client)
    sensor = of_type(kit, "moisture_sensor")
    assign(client, sensor["id"], bench1["id"])
    set_tracking(client, sensor["id"], True)

    ingest_moisture(sensor["id"], 0.10)                      # strictly below 0.20

    [row] = alerts(client, zone_id=bench1["id"])
    assert row["event_type"] == "threshold.crossed"
    assert row["severity"] == "warning"
    assert row["message"] == "Moisture below zone low"
    assert row["location_id"] == location["id"]
    assert row["zone_id"] == bench1["id"]
    assert row["device_id"] == sensor["id"]
    assert set(row) == {
        "id", "location_id", "zone_id", "device_id", "severity",
        "message", "event_type", "status", "created_at",
    }                                                         # no acknowledged_at
    assert alerts(client, zone_id=bench2["id"]) == []
    assert len(alerts(client, location_id=location["id"])) == 1


def test_tracking_off_stores_the_reading_and_creates_no_alert(client):
    _, bench1, _, kit = seed_lab(client)
    sensor = of_type(kit, "moisture_sensor")
    assign(client, sensor["id"], bench1["id"])
    set_tracking(client, sensor["id"], False)

    ingest_moisture(sensor["id"], 0.10)

    assert scalar("SELECT count(*) FROM sensor_readings WHERE device_id = :id", id=sensor["id"]) == 1
    assert alerts(client) == []


@pytest.mark.parametrize("value", [0.20, 0.35])
def test_moisture_at_or_above_low_creates_no_alert(client, value):
    _, bench1, _, kit = seed_lab(client)
    sensor = of_type(kit, "moisture_sensor")
    assign(client, sensor["id"], bench1["id"])
    set_tracking(client, sensor["id"], True)

    ingest_moisture(sensor["id"], value)                     # 0.20 is not strictly below 0.20
    assert alerts(client) == []


def test_unassigned_sensor_never_creates_a_threshold_alert(client):
    *_, kit = seed_lab(client)
    sensor = of_type(kit, "moisture_sensor")                 # no zone to compare with
    set_tracking(client, sensor["id"], True)

    ingest_moisture(sensor["id"], 0.01)
    assert alerts(client) == []


# --- command.failed on the unassigned pump ---

def test_failed_command_on_unassigned_pump_stores_null_location_and_zone(client):
    *_, kit = seed_lab(client)
    pump = of_type(kit, "water_pump")
    send = lambda t: client.post("/api/commands", json={"command_type": t, "device_id": pump["id"]})

    assert send("start_pump").json()["status"] == "success"
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE actuator_states SET updated_at = now() - interval '31 minutes' WHERE device_id = :id"),
            {"id": pump["id"]},
        )
    assert send("stop_pump").json()["status"] == "failed"

    [row] = alerts(client)
    assert row["event_type"] == "command.failed"
    assert row["severity"] == "warning"
    assert row["message"] == "Max run time exceeded"
    assert row["device_id"] == pump["id"]
    assert row["location_id"] is None and row["zone_id"] is None


def test_rejected_command_creates_no_alert(client):
    *_, kit = seed_lab(client)
    pump = of_type(kit, "water_pump")
    res = client.post("/api/commands", json={"command_type": "stop_pump", "device_id": pump["id"]})
    assert res.status_code == 409
    assert alerts(client) == []


# --- state.changed only for error ---

def test_transition_to_error_creates_a_critical_alert_and_others_do_not(client):
    *_, kit = seed_lab(client)
    pump = of_type(kit, "water_pump")
    move = lambda target: client.post(f"/api/devices/{pump['id']}/transition", json={"target": target})

    assert move("running").status_code == 200                # state saved, but no alert
    assert alerts(client) == []

    assert move("error").status_code == 200
    [row] = alerts(client)
    assert (row["event_type"], row["severity"], row["message"]) == (
        "state.changed", "critical", "Actuator entered error",
    )

    assert move("idle").status_code == 200                   # leaving error: no new alert
    assert len(alerts(client)) == 1


# --- API filters ---

def test_alert_filters_and_validation(client):
    *_, kit = seed_lab(client)
    pump = of_type(kit, "water_pump")
    client.post(f"/api/devices/{pump['id']}/transition", json={"target": "error"})

    assert len(alerts(client)) == 1                          # default status=active
    assert len(alerts(client, status="all")) == 1
    assert alerts(client, status="resolved") == []
    assert alerts(client, since="2999-01-01T00:00:00Z") == []
    assert len(alerts(client, since="2000-01-01T00:00:00Z")) == 1
    assert client.get("/api/alerts", params={"status": "bogus"}).status_code == 400
    assert client.get("/api/alerts", params={"limit": 0}).status_code == 422
    assert client.get("/api/alerts", params={"limit": 201}).status_code == 422