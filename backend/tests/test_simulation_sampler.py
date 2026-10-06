import os
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Sampler tests need TEST_DATABASE_URL pointing at a *_test database",
)

from sqlalchemy import text  # noqa: E402

from src.application.readings.sampler import SimulationSampler  # noqa: E402
from src.application.readings.service import ReadingIngest  # noqa: E402
from src.infrastructure.adapters.sensors.selector import select_sensor_adapter  # noqa: E402
from src.infrastructure.db import SessionLocal, engine  # noqa: E402
from src.infrastructure.persistence.device_repository import DeviceRepository  # noqa: E402
from src.infrastructure.persistence.models import DeviceRow, ReadingRow  # noqa: E402
from src.infrastructure.persistence.reading_repository import ReadingRepository  # noqa: E402

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    assert engine.url.database.endswith("_test"), "Refusing to wipe a non-test database"
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE sensor_readings, devices, zones, locations CASCADE"))
    session = SessionLocal()
    yield session
    session.close()


def add_sensor(db, *, protocol="simulation", tracking=True, interval=60, device_type="moisture_sensor"):
    row = DeviceRow(
        device_type=device_type,
        role="sensor",
        device_family="simulation" if protocol == "simulation" else "edge",
        display_name=f"{protocol} sensor",
        default_config={"protocol": protocol},
        sampling_interval_seconds=interval,
        tracking_enabled=tracking,
    )
    db.add(row)
    db.commit()
    return row.id


def make_sampler(db) -> SimulationSampler:
    devices, readings = DeviceRepository(db), ReadingRepository(db)
    return SimulationSampler(devices, readings, ReadingIngest(devices, readings, select_sensor_adapter))


def readings_for(db, device_id) -> list[ReadingRow]:
    return db.query(ReadingRow).filter(ReadingRow.device_id == device_id).all()


def test_records_when_due_skips_inside_interval_and_records_again_after(db):
    sensor = add_sensor(db, interval=60)
    sampler = make_sampler(db)

    assert sampler.run_once(T0) == 1                              # no previous row → due
    assert sampler.run_once(T0 + timedelta(seconds=30)) == 0      # inside the interval
    assert sampler.run_once(T0 + timedelta(seconds=60)) == 1      # interval elapsed

    times = sorted(r.recorded_at for r in readings_for(db, sensor))
    assert times == [T0, T0 + timedelta(seconds=60)]              # stored with the tick time


def test_skips_disabled_and_mqtt_devices(db):
    enabled = add_sensor(db, protocol="simulation", tracking=True)
    disabled = add_sensor(db, protocol="simulation", tracking=False)
    mqtt = add_sensor(db, protocol="mqtt", tracking=True)

    assert make_sampler(db).run_once(T0) == 1

    assert len(readings_for(db, enabled)) == 1
    assert readings_for(db, disabled) == []
    assert readings_for(db, mqtt) == []


def test_each_device_follows_its_own_interval(db):
    fast = add_sensor(db, interval=10)
    slow = add_sensor(db, interval=300, device_type="light_sensor")
    sampler = make_sampler(db)

    for seconds in range(0, 61, 10):                              # ticks at 0, 10, ... 60 s
        sampler.run_once(T0 + timedelta(seconds=seconds))

    assert len(readings_for(db, fast)) == 7                       # every tick
    assert len(readings_for(db, slow)) == 1                       # only the first