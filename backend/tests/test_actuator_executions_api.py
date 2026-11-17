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
            text(
                "TRUNCATE command_log, actuator_execution_log, actuator_states, automation_rules, "
                "sensor_readings, devices, zones, locations CASCADE"
            )
        )
    with TestClient(app) as c:
        yield c


def a_pump(client):
    devices = client.post("/api/devices/provision", params={"family": "simulation"}).json()
    return next(d for d in devices if d["device_type"] == "water_pump")


def send(client, command_type, device_id):
    return client.post("/api/commands", json={"command_type": command_type, "device_id": device_id})


def log_rows(device_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT success, policy_applied, message FROM actuator_execution_log "
                "WHERE device_id = :id ORDER BY created_at"
            ),
            {"id": device_id},
        ).all()
    return [tuple(r) for r in rows]


def total_rows() -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM actuator_execution_log")).scalar_one()


def age_running(device_id):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE actuator_states SET updated_at = now() - interval '31 minutes' WHERE device_id = :id"),
            {"id": device_id},
        )


def test_successful_command_inserts_a_success_row(client):
    pump = a_pump(client)
    assert send(client, "start_pump", pump["id"]).json()["status"] == "success"
    assert log_rows(pump["id"]) == [(True, ["logging"], None)]


def test_failed_policy_writes_execution_row(client):
    pump = a_pump(client)
    send(client, "start_pump", pump["id"])
    age_running(pump["id"])

    res = send(client, "stop_pump", pump["id"])

    assert res.status_code == 200 and res.json()["status"] == "failed"
    assert log_rows(pump["id"]) == [
        (True, ["logging"], None),
        (False, ["maxRunTime", "logging"], "Max run time exceeded"),
    ]


def test_running_for_less_than_the_limit_still_succeeds(client):
    pump = a_pump(client)
    send(client, "start_pump", pump["id"])
    assert send(client, "stop_pump", pump["id"]).json()["status"] == "success"
    assert log_rows(pump["id"]) == [(True, ["logging"], None), (True, ["logging"], None)]


def test_executions_endpoint_lists_newest_first(client):
    pump = a_pump(client)
    send(client, "start_pump", pump["id"])
    age_running(pump["id"])
    send(client, "stop_pump", pump["id"])

    rows = client.get("/api/actuators/executions", params={"limit": 10}).json()

    assert [r["success"] for r in rows] == [False, True]
    assert set(rows[0]) == {"id", "device_id", "success", "policy_applied", "message", "created_at"}
    assert rows[0]["policy_applied"] == ["maxRunTime", "logging"]
    assert rows[1]["message"] is None
    assert len(client.get("/api/actuators/executions", params={"limit": 1}).json()) == 1


def test_rejected_missing_or_sensor_commands_write_no_execution_row(client):
    pump = a_pump(client)
    devices = client.get("/api/devices").json()
    sensor = next(d for d in devices if d["role"] == "sensor")

    assert send(client, "stop_pump", pump["id"]).status_code == 409    # rejected: never reaches the port
    assert send(client, "start_pump", sensor["id"]).status_code == 404
    assert send(client, "start_pump", MISSING_ID).status_code == 404
    assert total_rows() == 0
