from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Device:
    device_type: str          # e.g. "moisture_sensor", "water_pump"
    role: str                 # "sensor" or "actuator"
    device_family: str        # "simulation" or "edge"
    display_name: str
    default_config: dict = field(default_factory=dict)
    id: UUID | None = None    # None until the database saves it
    
    default_config: dict = field(default_factory=dict)
    id: UUID | None = None
    zone_id: UUID | None = None
    location_id: UUID | None = None