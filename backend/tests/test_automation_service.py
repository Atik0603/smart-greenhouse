import uuid
from datetime import datetime, timezone

import pytest

from src.application.automation.service import AutomationService
from src.domain.automation.errors import (
    LocationNotFoundError,
    NoStrategySelectedError,
    UnknownStrategyError,
)
from src.infrastructure.persistence.automation_repository import AutomationRule, ZoneSnapshot

LOCATION = uuid.uuid4()


class FakeRules:
    def __init__(self, key: str | None = None) -> None:
        self.saved: dict = {}
        if key:
            self.upsert(LOCATION, key)

    def get(self, location_id):
        return self.saved.get(location_id)

    def upsert(self, location_id, strategy_key):
        rule = AutomationRule(location_id, strategy_key, datetime.now(timezone.utc))
        self.saved[location_id] = rule
        return rule


class FakeContexts:
    def __init__(self, zones: list[ZoneSnapshot]) -> None:
        self.zones = zones

    def location_exists(self, location_id):
        return location_id == LOCATION

    def list_zone_snapshots(self, location_id):
        return self.zones


def zone(name: str, moisture: float | None, has_sensor: bool = True) -> ZoneSnapshot:
    return ZoneSnapshot(
        zone_id=uuid.uuid4(), zone_name=name, low=0.20, high=0.40,
        has_moisture_sensor=has_sensor, moisture=moisture, light=None,
    )


def service(key=None, zones=None) -> AutomationService:
    return AutomationService(FakeRules(key), FakeContexts(zones or [zone("North", 0.25)]))


# --- Evaluate uses the persisted key ---

def test_evaluate_uses_saved_strategy_and_results_differ():
    svc = service(key="conservative")
    assert svc.evaluate(LOCATION).zones[0].action == "wait"

    svc.save_strategy(LOCATION, "aggressive")
    result = svc.evaluate(LOCATION)
    assert result.strategy_key == "aggressive"
    assert result.zones[0].action == "irrigate"


def test_evaluate_without_saved_strategy_raises_409_error():
    with pytest.raises(NoStrategySelectedError):
        service(key=None).evaluate(LOCATION)


# --- Errors ---

def test_unknown_key_is_rejected_and_nothing_saved():
    svc = service()
    with pytest.raises(UnknownStrategyError):
        svc.save_strategy(LOCATION, "nope")
    assert svc.get_rule(LOCATION) is None


def test_missing_location_is_not_found():
    with pytest.raises(LocationNotFoundError):
        service(key="conservative").evaluate(uuid.uuid4())
    with pytest.raises(LocationNotFoundError):
        service().save_strategy(uuid.uuid4(), "conservative")


# --- Per-zone rules ---

def test_zone_without_sensor_waits_and_does_not_borrow():
    zones = [zone("North", 0.10), zone("South", None, has_sensor=False)]
    result = service(key="aggressive", zones=zones).evaluate(LOCATION)

    north, south = result.zones
    assert north.action == "irrigate"
    assert south.action == "wait"
    assert south.reason == "No moisture sensor in this zone"
    assert south.moisture is None          # North's 0.10 was not borrowed


def test_sensor_without_readings_waits_with_its_own_reason():
    result = service(key="aggressive", zones=[zone("North", None)]).evaluate(LOCATION)
    assert result.zones[0].reason == "Moisture sensor has no readings yet"


def test_summary_irrigates_if_any_zone_needs_water():
    zones = [zone("North", 0.10), zone("South", 0.38)]
    result = service(key="conservative", zones=zones).evaluate(LOCATION)

    assert result.action == "irrigate"
    assert "1 of 2" in result.reason and "North" in result.reason


def test_summary_waits_when_no_zone_needs_water():
    result = service(key="conservative", zones=[zone("North", 0.38)]).evaluate(LOCATION)
    assert result.action == "wait"