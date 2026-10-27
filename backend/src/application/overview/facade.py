from collections import defaultdict
from uuid import UUID

from src.application.automation.service import AutomationService
from src.application.locations.dto import LocationSummaryDto
from src.application.overview.dto import (
    DeviceCountsDto,
    LocationOverviewDto,
    OverviewDeviceDto,
    OverviewReadingDto,
    OverviewZoneDto,
    RecommendationSummaryDto,
)
from src.domain.devices.entity import Device
from src.domain.locations.errors import LocationNotFoundError
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.location_repository import LocationRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository


class LocationOverviewFacade:
    """One entry point for the dashboard overview. Composes existing subsystems; adds no rules."""

    def __init__(
        self,
        locations: LocationRepository,
        devices: DeviceRepository,
        readings: ReadingRepository,
        automation: AutomationService,
    ) -> None:
        self._locations = locations
        self._devices = devices
        self._readings = readings
        self._automation = automation

    def get_overview(self, location_id: UUID) -> LocationOverviewDto:
        # 1. Location + every zone (one load)
        location = self._locations.get_location(location_id)
        if location is None:
            raise LocationNotFoundError(location_id)

        # 2. Assigned devices only (one query)
        devices = self._devices.list_assigned_in_location(location_id)

        # 3. Newest reading for those devices (one query, any source)
        latest = self._readings.latest_by_device([d.id for d in devices])

        # 4 + 5. Saved strategy; evaluate only if one exists
        rule = self._automation.get_rule(location_id)
        recommendation = None
        if rule is not None:
            evaluation = self._automation.evaluate(location_id)
            recommendation = RecommendationSummaryDto(
                action=evaluation.action, reason=evaluation.reason
            )

        # 6. Group devices under their zones
        by_zone: dict[UUID, list[Device]] = defaultdict(list)
        for device in devices:
            by_zone[device.zone_id].append(device)

        zones = [
            OverviewZoneDto(
                id=zone.id,
                name=zone.name,
                moisture_threshold_low=zone.moisture_threshold_low,
                moisture_threshold_high=zone.moisture_threshold_high,
                devices=[self._device_dto(d) for d in by_zone[zone.id]],
                latest_readings=[
                    self._reading_dto(d, latest[d.id]) for d in by_zone[zone.id] if d.id in latest
                ],
            )
            for zone in location.zones
        ]

        return LocationOverviewDto(
            location=LocationSummaryDto(id=location.id, name=location.name),
            device_counts=DeviceCountsDto(
                sensor=sum(1 for d in devices if d.role == "sensor"),
                actuator=sum(1 for d in devices if d.role == "actuator"),
            ),
            zones=zones,
            strategy_key=None if rule is None else rule.strategy_key,
            last_recommendation=recommendation,
        )

    # --- mappers ---

    @staticmethod
    def _device_dto(device: Device) -> OverviewDeviceDto:
        return OverviewDeviceDto(
            id=device.id,
            device_type=device.device_type,
            role=device.role,
            display_name=device.display_name,
        )

    @staticmethod
    def _reading_dto(device: Device, reading) -> OverviewReadingDto:
        return OverviewReadingDto(
            device_id=reading.device_id,
            value=reading.value,
            unit=reading.unit,
            recorded_at=reading.recorded_at,
            tracking_enabled=device.tracking_enabled,                    # from the device
            sampling_interval_seconds=device.sampling_interval_seconds,  # from the device
        )