from dataclasses import replace
from uuid import UUID

from src.application.locations.dto import ZoneCreateRequest, ZoneUpdateRequest
from src.domain.locations.config_builder import validate_zone_fields
from src.domain.locations.entity import Zone
from src.domain.locations.errors import (
    ConfigurationError,
    LocationNotFoundError,
    ZoneNotFoundError,
)
from src.infrastructure.persistence.location_repository import LocationRepository


class ZoneService:
    def __init__(self, repository: LocationRepository) -> None:
        self.repository = repository

    # --- helpers ---

    def _require_location(self, location_id: UUID) -> None:
        if not self.repository.location_exists(location_id):
            raise LocationNotFoundError(location_id)

    def _require_zone_in_location(self, location_id: UUID, zone_id: UUID) -> Zone:
        found = self.repository.get_zone(zone_id)
        if found is None or found[1] != location_id:
            raise ZoneNotFoundError(zone_id)
        return found[0]

    def _ensure_unique_name(
        self, location_id: UUID, name: str, exclude_zone_id: UUID | None = None
    ) -> None:
        if self.repository.zone_name_exists(location_id, name, exclude_zone_id):
            raise ConfigurationError(f"Zone name '{name}' already exists in this location")

    # --- use cases ---

    def add_zone(self, location_id: UUID, request: ZoneCreateRequest) -> Zone:
        self._require_location(location_id)
        name = request.name.strip()
        validate_zone_fields(name, request.moisture_threshold_low, request.moisture_threshold_high)
        self._ensure_unique_name(location_id, name)
        return self.repository.add_zone(
            location_id,
            Zone(
                name=name,
                moisture_threshold_low=float(request.moisture_threshold_low),
                moisture_threshold_high=float(request.moisture_threshold_high),
                schedule=dict(request.schedule),
            ),
        )

    def update_zone(self, location_id: UUID, zone_id: UUID, request: ZoneUpdateRequest) -> Zone:
        self._require_location(location_id)
        current = self._require_zone_in_location(location_id, zone_id)

        updated = replace(
            current,
            name=(request.name if request.name is not None else current.name).strip(),
            moisture_threshold_low=(
                request.moisture_threshold_low
                if request.moisture_threshold_low is not None
                else current.moisture_threshold_low
            ),
            moisture_threshold_high=(
                request.moisture_threshold_high
                if request.moisture_threshold_high is not None
                else current.moisture_threshold_high
            ),
            schedule=request.schedule if request.schedule is not None else current.schedule,
        )

        validate_zone_fields(
            updated.name, updated.moisture_threshold_low, updated.moisture_threshold_high
        )
        self._ensure_unique_name(location_id, updated.name, exclude_zone_id=zone_id)
        return self.repository.update_zone(updated)

    def delete_zone(self, location_id: UUID, zone_id: UUID) -> None:
        self._require_location(location_id)
        self._require_zone_in_location(location_id, zone_id)
        if self.repository.count_zones(location_id) <= 1:
            raise ConfigurationError("Cannot delete the last zone of a location")
        self.repository.delete_zone_and_unassign(zone_id)