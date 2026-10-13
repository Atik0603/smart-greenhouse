from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class LocationAutomationContext:
    """Everything a strategy may look at for ONE zone. Plain values only, no ORM rows."""

    location_id: UUID
    zone_id: UUID
    moisture: float          # latest reading among moisture sensors in this zone
    low: float               # zone.moisture_threshold_low
    high: float              # zone.moisture_threshold_high
    light: float | None = None

    def __post_init__(self) -> None:
        if not self.low < self.high:
            raise ValueError(f"low ({self.low}) must be less than high ({self.high})")