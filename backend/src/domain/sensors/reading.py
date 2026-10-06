from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

READING_SOURCES = ("simulation", "mqtt", "vendor")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Reading:
    device_id: UUID
    value: float
    unit: str          # e.g. "vwc", "lux"
    source: str        # "simulation", "mqtt" or "vendor"
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("Reading.recorded_at must be timezone-aware")
        if self.source not in READING_SOURCES:
            raise ValueError(f"Unknown reading source: {self.source!r}")