from uuid import UUID

from src.application.locations.dto import LocationConfigCreateRequest
from src.application.locations.mappers import build_config_from_request
from src.domain.locations.entity import Location, LocationSummary
from src.domain.locations.errors import LocationNotFoundError
from src.infrastructure.persistence.location_repository import LocationRepository


class LocationConfigService:
    def __init__(self, repository: LocationRepository) -> None:
        self.repository = repository

    def create_config(self, request: LocationConfigCreateRequest) -> Location:
        config = build_config_from_request(request)  # 1. builder validates (may raise ConfigurationError)
        return self.repository.save_config(config)   # 2. only a valid config reaches the database

    def get_config(self, location_id: UUID) -> Location:
        location = self.repository.get_location(location_id)
        if location is None:
            raise LocationNotFoundError(location_id)
        return location

    def list_locations(self) -> list[LocationSummary]:
        return self.repository.list_locations()

    def delete_location(self, location_id: UUID) -> None:
        if not self.repository.delete_location(location_id):
            raise LocationNotFoundError(location_id)