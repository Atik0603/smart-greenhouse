from src.domain.locations.entity import Location, LocationConfig, Zone
from src.domain.locations.errors import ConfigurationError

MIN_VWC = 0.0
MAX_VWC = 1.0


def validate_zone_fields(name: str, low: float, high: float) -> None:
    """Rules for a single zone. Used by build() AND by zone add/edit later."""
    if not name or not name.strip():
        raise ConfigurationError("Zone name is required")
    for label, value in (("low", low), ("high", high)):
        if not MIN_VWC <= value <= MAX_VWC:
            raise ConfigurationError(
                f"Zone '{name}': {label} threshold must be between "
                f"{MIN_VWC} and {MAX_VWC} (got {value})"
            )
    if low >= high:
        raise ConfigurationError(
            f"Zone '{name}': low threshold ({low}) must be strictly less than high ({high})"
        )


class LocationConfigBuilder:
    def __init__(self) -> None:
        self._name: str | None = None
        self._zones: list[Zone] = []

    def with_name(self, name: str) -> "LocationConfigBuilder":
        self._name = name.strip()
        return self

    def add_zone(
        self,
        name: str,
        moisture_threshold_low: float,
        moisture_threshold_high: float,
        schedule: dict | None = None,
    ) -> "LocationConfigBuilder":
        self._zones.append(
            Zone(
                name=name.strip(),
                moisture_threshold_low=float(moisture_threshold_low),
                moisture_threshold_high=float(moisture_threshold_high),
                schedule=dict(schedule or {}),
            )
        )
        return self

    def build(self) -> LocationConfig:
        if not self._name:
            raise ConfigurationError("Location name is required")
        if not self._zones:
            raise ConfigurationError("At least one zone is required")

        seen_names: set[str] = set()
        for zone in self._zones:
            validate_zone_fields(
                zone.name, zone.moisture_threshold_low, zone.moisture_threshold_high
            )
            key = zone.name.casefold()
            if key in seen_names:
                raise ConfigurationError(
                    f"Zone name '{zone.name}' is used more than once in this location"
                )
            seen_names.add(key)

        return LocationConfig(
            location=Location(name=self._name, zones=tuple(self._zones))
        )