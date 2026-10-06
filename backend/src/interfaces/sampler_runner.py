import asyncio
import logging
import os

from src.application.readings.sampler import SimulationSampler
from src.application.readings.service import ReadingIngest
from src.domain.sensors.reading import utc_now
from src.infrastructure.adapters.sensors.selector import select_sensor_adapter
from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

logger = logging.getLogger(__name__)

SAMPLER_TICK_SECONDS = 5


def sampler_enabled() -> bool:
    return os.environ.get("SAMPLER_ENABLED", "true").lower() != "false"


def run_sampler_tick() -> int:
    """One sampler pass with its own database session."""
    db = SessionLocal()
    try:
        devices = DeviceRepository(db)
        readings = ReadingRepository(db)
        ingest = ReadingIngest(devices, readings, select_sensor_adapter)
        return SimulationSampler(devices, readings, ingest).run_once(utc_now())
    finally:
        db.close()


async def sampler_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_sampler_tick)
        except Exception:
            logger.exception("Sampler tick failed")
        await asyncio.sleep(SAMPLER_TICK_SECONDS)