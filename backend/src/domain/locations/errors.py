class ConfigurationError(ValueError):
    """Raised when a location configuration breaks a domain rule."""


class LocationNotFoundError(Exception):
    def __init__(self, location_id) -> None:
        super().__init__(f"Location {location_id} not found")
        self.location_id = location_id

class ZoneNotFoundError(Exception):
    def __init__(self, zone_id) -> None:
        super().__init__(f"Zone {zone_id} not found")
        self.zone_id = zone_id