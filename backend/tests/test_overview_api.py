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
        conn.execute(
            text("TRUNCATE automation_rules, sensor_readings, devices, zones, locations CASCADE")
        )
    with TestClient(app) as c:
        yield c


# --- seeding helpers ---

def kit(client, family="simulation"):
    res = client.post("/api/devices/provision", params={"family": family})
    assert res.status_code == 201, res.text
    return res.json()


def seed_location(client):
    res = client.post(
        "/api/locations/config",
        json={
            "location_name": "Overview Bay",
            "zones": [
                {"name": "North", "moisture_threshold_low": 0.2, "moisture_threshold_high": 0.4},
                {"name": "South", "moisture_threshold_low": 0.3, "moisture_threshold_high": 0.5},
            ],
        },
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    zones = {z["name"]: z for z in body["zones"]}
    return body["location"], zones["North"], zones["South"]


def assign_without_tracking(device_id, zone_id, location_id):
    """Seed an assignment directly, and stop the background sampler touching this sensor."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE devices SET zone_id = :zone, location_id = :loc, tracking_enabled = false "
                "WHERE id = :id"
            ),
            {"zone": zone_id, "loc": location_id, "id": device_id},
        )


def newest_reading_row(device_id):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT value, unit FROM sensor_readings WHERE device_id = :id "
                "ORDER BY recorded_at DESC LIMIT 1"
            ),
            {"id": device_id},
        ).one()


def zone_named(overview, name):
    return next(z for z in overview["zones"] if z["name"] == name)


# --- the test ---

def test_overview_returns_strategy_and_readings(client):
    # Unknown location → 404
    assert client.get(f"/api/locations/{MISSING_ID}/overview").status_code == 404

    # Seed: two zones, one assigned moisture sensor with a reading, the rest unassigned
    location, north, south = seed_location(client)
    devices = kit(client)
    sensor = next(d for d in devices if d["device_type"] == "moisture_sensor")
    unassigned_ids = {d["id"] for d in devices if d["id"] != sensor["id"]}
    assert unassigned_ids, "the kit should leave at least one device unassigned"

    assign_without_tracking(sensor["id"], north["id"], location["id"])
    read = client.post(f"/api/sensors/{sensor['id']}/read")
    assert read.status_code == 201, read.text

    url = f"/api/locations/{location['id']}/overview"
    res = client.get(url)
    assert res.status_code == 200, res.text
    overview = res.json()

    # Location
    assert overview["location"] == {"id": location["id"], "name": "Overview Bay"}

    # No strategy saved yet → 200 with both fields null
    assert overview["strategy_key"] is None
    assert overview["last_recommendation"] is None

    # Counts: assigned devices only
    assert overview["device_counts"] == {"sensor": 1, "actuator": 0}

    # Unassigned devices appear in no zone
    listed = {d["id"] for zone in overview["zones"] for d in zone["devices"]}
    assert listed == {sensor["id"]}
    assert listed.isdisjoint(unassigned_ids)

    # The assigned sensor's newest reading, with sampling fields copied from the device
    north_zone = zone_named(overview, "North")
    [reading] = north_zone["latest_readings"]
    expected = newest_reading_row(sensor["id"])
    assert reading["device_id"] == sensor["id"]
    assert reading["value"] == pytest.approx(float(expected.value))
    assert reading["unit"] == expected.unit
    assert reading["tracking_enabled"] is False
    assert reading["sampling_interval_seconds"] == sensor["sampling_interval_seconds"]

    # The zone with no assigned devices is still listed, empty
    south_zone = zone_named(overview, "South")
    assert south_zone["devices"] == []
    assert south_zone["latest_readings"] == []

    # After saving a key, last_recommendation matches evaluate for the same location
    saved = client.put(
        f"/api/locations/{location['id']}/automation", json={"strategy_key": "aggressive"}
    )
    assert saved.status_code == 200, saved.text

    overview = client.get(url).json()
    evaluation = client.post(f"/api/locations/{location['id']}/automation/evaluate").json()

    assert overview["strategy_key"] == "aggressive"
    assert overview["last_recommendation"] == {
        "action": evaluation["action"],
        "reason": evaluation["reason"],
    }