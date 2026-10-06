import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Integration tests need TEST_DATABASE_URL pointing at a *_test database",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.infrastructure.db import engine  # noqa: E402
from src.main import app  # noqa: E402

MISSING_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def client():
    assert engine.url.database.endswith("_test"), "Refusing to wipe a non-test database"
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE sensor_readings, devices, zones, locations CASCADE"))
    with TestClient(app) as c:
        yield c


def kit(client, family="simulation"):
    res = client.post("/api/devices/provision", params={"family": family})
    assert res.status_code == 201, res.text
    return res.json()


def first(devices, role):
    return next(d for d in devices if d["role"] == role)


def row_count(device_id) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM sensor_readings WHERE device_id = :id"), {"id": device_id}
        ).scalar_one()


def test_read_inserts_a_row_and_returns_normalized_dto(client):
    sensor = first(kit(client), "sensor")
    assert row_count(sensor["id"]) == 0

    res = client.post(f"/api/sensors/{sensor['id']}/read")
    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == {"device_id", "value", "unit", "source", "recorded_at"}
    assert body["device_id"] == sensor["id"]
    assert body["source"] == "simulation"
    assert row_count(sensor["id"]) == 1

    client.post(f"/api/sensors/{sensor['id']}/read")
    assert row_count(sensor["id"]) == 2                           # repeated reads add history

    history = client.get(f"/api/sensors/{sensor['id']}/readings", params={"limit": 10}).json()
    assert len(history) == 2
    assert history[0]["recorded_at"] >= history[1]["recorded_at"]  # newest first


def test_read_errors(client):
    devices = kit(client, "edge")
    mqtt_sensor = first(devices, "sensor")
    actuator = first(devices, "actuator")

    assert client.post(f"/api/sensors/{MISSING_ID}/read").status_code == 404
    assert client.post(f"/api/sensors/{mqtt_sensor['id']}/read").status_code == 400   # push-only
    assert client.post(f"/api/sensors/{actuator['id']}/read").status_code == 400      # not a sensor
    assert row_count(mqtt_sensor["id"]) == 0


def test_patch_sampling_persists_and_validates(client):
    devices = kit(client)
    sensor, actuator = first(devices, "sensor"), first(devices, "actuator")

    res = client.patch(
        f"/api/devices/{sensor['id']}/sampling",
        json={"sampling_interval_seconds": 15, "tracking_enabled": False},
    )
    assert res.status_code == 200, res.text
    assert (res.json()["sampling_interval_seconds"], res.json()["tracking_enabled"]) == (15, False)

    stored = next(d for d in client.get("/api/devices").json() if d["id"] == sensor["id"])
    assert (stored["sampling_interval_seconds"], stored["tracking_enabled"]) == (15, False)

    too_small = client.patch(
        f"/api/devices/{sensor['id']}/sampling",
        json={"sampling_interval_seconds": 3, "tracking_enabled": True},
    )
    assert too_small.status_code == 400

    assert client.patch(
        f"/api/devices/{actuator['id']}/sampling",
        json={"sampling_interval_seconds": 30, "tracking_enabled": True},
    ).status_code == 400

    assert client.patch(
        f"/api/devices/{MISSING_ID}/sampling",
        json={"sampling_interval_seconds": 30, "tracking_enabled": True},
    ).status_code == 404