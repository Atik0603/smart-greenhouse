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


@pytest.fixture
def client():
    assert engine.url.database.endswith("_test"), "Refusing to wipe a non-test database"
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE devices, zones, locations CASCADE"))
    with TestClient(app) as c:
        yield c


# --- helpers ---

def zone(name, low=0.2, high=0.4, **extra):
    return {"name": name, "moisture_threshold_low": low, "moisture_threshold_high": high, **extra}


def create_location(client, name, *zones):
    res = client.post("/api/locations/config", json={"location_name": name, "zones": list(zones)})
    assert res.status_code == 201, res.text
    return res.json()


def provision_kit(client, family="simulation"):
    res = client.post("/api/devices/provision", params={"family": family})
    assert res.status_code == 201, res.text
    return res.json()


def assign(client, device_id, zone_id):
    return client.patch(f"/api/devices/{device_id}/zone", json={"zone_id": zone_id})


def get_device(client, device_id):
    return next(d for d in client.get("/api/devices").json() if d["id"] == device_id)


def zone_device_ids(client, location_id, zone_id):
    res = client.get(f"/api/locations/{location_id}/zones/{zone_id}/devices")
    assert res.status_code == 200, res.text
    return {d["id"] for d in res.json()}


# --- create / read ---

def test_create_config_persists_location_and_zones(client):
    created = create_location(client, "Bay A", zone("North"), zone("South", 0.3, 0.5, schedule={"water_at": "06:00"}))
    location_id = created["location"]["id"]

    res = client.get(f"/api/locations/{location_id}/config")
    assert res.status_code == 200
    body = res.json()
    assert body["location"] == {"id": location_id, "name": "Bay A"}
    assert {z["name"] for z in body["zones"]} == {"North", "South"}
    assert all(z["location_id"] == location_id for z in body["zones"])
    assert all(set(z) == {"id", "location_id", "name", "moisture_threshold_low", "moisture_threshold_high", "schedule"} for z in body["zones"])


def test_invalid_config_returns_400_and_saves_nothing(client):
    res = client.post("/api/locations/config", json={"location_name": "Bad", "zones": [zone("X", 0.6, 0.4)]})
    assert res.status_code == 400
    assert "strictly less" in res.json()["detail"]
    assert client.get("/api/locations").json() == []


def test_missing_location_returns_404(client):
    res = client.get("/api/locations/00000000-0000-0000-0000-000000000000/config")
    assert res.status_code == 404


# --- assignment ---

def test_zone_lists_only_its_assigned_devices(client):
    loc = create_location(client, "Bay A", zone("North"), zone("South"))
    north, south = loc["zones"][0]["id"], loc["zones"][1]["id"]
    kit = provision_kit(client)

    for device in (kit[0], kit[1]):
        res = assign(client, device["id"], south)
        assert res.status_code == 200
        assert res.json()["location_id"] == loc["location"]["id"]  # copied from the zone
    assign(client, kit[2]["id"], north)

    assert zone_device_ids(client, loc["location"]["id"], south) == {kit[0]["id"], kit[1]["id"]}
    assert kit[2]["id"] not in zone_device_ids(client, loc["location"]["id"], south)
    assert kit[3]["id"] not in zone_device_ids(client, loc["location"]["id"], south)  # unassigned device


def test_unassign_clears_zone_and_location(client):
    loc = create_location(client, "Bay A", zone("North"))
    device = provision_kit(client)[0]
    assign(client, device["id"], loc["zones"][0]["id"])

    res = assign(client, device["id"], None)
    assert res.status_code == 200
    assert res.json()["zone_id"] is None
    assert res.json()["location_id"] is None


def test_zone_devices_404_when_zone_belongs_to_another_location(client):
    a = create_location(client, "Bay A", zone("North"))
    b = create_location(client, "Bay B", zone("North"))
    res = client.get(f"/api/locations/{a['location']['id']}/zones/{b['zones'][0]['id']}/devices")
    assert res.status_code == 404


# --- list / delete locations ---

def test_list_and_delete_location_unassigns_its_devices(client):
    a = create_location(client, "Bay A", zone("North"))
    b = create_location(client, "Bay B", zone("North"))
    listed_ids = {l["id"] for l in client.get("/api/locations").json()}
    assert listed_ids == {a["location"]["id"], b["location"]["id"]}

    device = provision_kit(client)[0]
    assign(client, device["id"], a["zones"][0]["id"])

    assert client.delete(f"/api/locations/{a['location']['id']}").status_code == 204
    assert client.get(f"/api/locations/{a['location']['id']}/config").status_code == 404
    assert [l["id"] for l in client.get("/api/locations").json()] == [b["location"]["id"]]

    after = get_device(client, device["id"])  # the device row still exists…
    assert after["zone_id"] is None and after["location_id"] is None  # …but is unassigned


# --- zone management ---

def test_add_zone_to_existing_location(client):
    loc = create_location(client, "Bay A", zone("North"))
    location_id = loc["location"]["id"]

    res = client.post(f"/api/locations/{location_id}/zones", json=zone("East", 0.3, 0.6))
    assert res.status_code == 201
    assert res.json()["location_id"] == location_id

    names = {z["name"] for z in client.get(f"/api/locations/{location_id}/config").json()["zones"]}
    assert names == {"North", "East"}


def test_invalid_zone_update_returns_400_and_keeps_zone(client):
    loc = create_location(client, "Bay A", zone("North", 0.2, 0.4))
    location_id, zone_id = loc["location"]["id"], loc["zones"][0]["id"]

    res = client.patch(f"/api/locations/{location_id}/zones/{zone_id}", json={"moisture_threshold_low": 0.9})
    assert res.status_code == 400

    stored = client.get(f"/api/locations/{location_id}/config").json()["zones"][0]
    assert stored["moisture_threshold_low"] == 0.2
    assert stored["moisture_threshold_high"] == 0.4


def test_delete_zone_unassigns_devices_and_last_zone_is_protected(client):
    loc = create_location(client, "Bay A", zone("North"), zone("South"))
    location_id = loc["location"]["id"]
    north, south = loc["zones"][0]["id"], loc["zones"][1]["id"]
    device = provision_kit(client)[0]
    assign(client, device["id"], south)

    assert client.delete(f"/api/locations/{location_id}/zones/{south}").status_code == 204
    after = get_device(client, device["id"])
    assert after["zone_id"] is None and after["location_id"] is None

    res = client.delete(f"/api/locations/{location_id}/zones/{north}")
    assert res.status_code == 400
    remaining = client.get(f"/api/locations/{location_id}/config").json()["zones"]
    assert [z["id"] for z in remaining] == [north]