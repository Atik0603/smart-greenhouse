from uuid import UUID

from src.application.locations.dto import (
    LocationConfigCreateRequest,
    LocationConfigResponse,
    LocationSummaryDto,
    ZoneReadDto,
)
from src.domain.locations.config_builder import LocationConfigBuilder
from src.domain.locations.entity import Location, LocationConfig, LocationSummary, Zone


# --- Request DTO -> builder steps -> domain ---

def build_config_from_request(request: LocationConfigCreateRequest) -> LocationConfig:
    builder = LocationConfigBuilder().with_name(request.location_name)
    for zone in request.zones:
        builder.add_zone(
            zone.name,
            zone.moisture_threshold_low,
            zone.moisture_threshold_high,
            zone.schedule,
        )
    return builder.build()


# --- Domain -> response DTOs ---

def zone_to_dto(zone: Zone, location_id: UUID) -> ZoneReadDto:
    if zone.id is None:
        raise ValueError("Cannot map an unsaved zone (id is None) to a DTO")
    return ZoneReadDto(
        id=zone.id,
        location_id=location_id,
        name=zone.name,
        moisture_threshold_low=zone.moisture_threshold_low,
        moisture_threshold_high=zone.moisture_threshold_high,
        schedule=zone.schedule,
    )


def location_to_summary(location: Location) -> LocationSummaryDto:
    if location.id is None:
        raise ValueError("Cannot map an unsaved location (id is None) to a DTO")
    return LocationSummaryDto(id=location.id, name=location.name)


def location_config_to_dto(location: Location) -> LocationConfigResponse:
    summary = location_to_summary(location)
    return LocationConfigResponse(
        location=summary,
        zones=[zone_to_dto(z, summary.id) for z in location.zones],
    )

def location_summary_to_dto(summary: LocationSummary) -> LocationSummaryDto:
    return LocationSummaryDto(id=summary.id, name=summary.name)