from dataclasses import FrozenInstanceError

import pytest

from src.domain.locations.config_builder import LocationConfigBuilder
from src.domain.locations.entity import LocationConfig
from src.domain.locations.errors import ConfigurationError


def valid_builder() -> LocationConfigBuilder:
    return (
        LocationConfigBuilder()
        .with_name("Bay A")
        .add_zone("North", 0.2, 0.4)
        .add_zone("South", 0.25, 0.45, {"water_at": "06:00"})
    )


def test_valid_config_builds_unsaved_location_with_zones_in_order():
    config = valid_builder().build()

    assert isinstance(config, LocationConfig)
    assert config.location.name == "Bay A"
    assert [z.name for z in config.location.zones] == ["North", "South"]
    assert config.location.zones[1].schedule == {"water_at": "06:00"}
    assert config.location.id is None
    assert all(z.id is None for z in config.location.zones)


@pytest.mark.parametrize("name", ["", "   "])
def test_missing_location_name_is_rejected(name):
    builder = LocationConfigBuilder().with_name(name).add_zone("North", 0.2, 0.4)
    with pytest.raises(ConfigurationError, match="Location name"):
        builder.build()


def test_no_name_step_at_all_is_rejected():
    with pytest.raises(ConfigurationError, match="Location name"):
        LocationConfigBuilder().add_zone("North", 0.2, 0.4).build()


def test_no_zones_is_rejected():
    with pytest.raises(ConfigurationError, match="At least one zone"):
        LocationConfigBuilder().with_name("Bay A").build()


@pytest.mark.parametrize("low, high", [(0.5, 0.3), (0.4, 0.4)])
def test_low_threshold_must_be_strictly_less_than_high(low, high):
    builder = LocationConfigBuilder().with_name("Bay A").add_zone("North", low, high)
    with pytest.raises(ConfigurationError, match="strictly less"):
        builder.build()


@pytest.mark.parametrize("low, high", [(-0.1, 0.4), (0.2, 1.5)])
def test_thresholds_must_be_within_vwc_range(low, high):
    builder = LocationConfigBuilder().with_name("Bay A").add_zone("North", low, high)
    with pytest.raises(ConfigurationError, match="between"):
        builder.build()


def test_duplicate_zone_names_in_one_location_are_rejected():
    builder = (
        LocationConfigBuilder()
        .with_name("Bay A")
        .add_zone("North", 0.2, 0.4)
        .add_zone("north", 0.1, 0.3)
    )
    with pytest.raises(ConfigurationError, match="more than once"):
        builder.build()


def test_same_zone_name_is_fine_in_different_locations():
    LocationConfigBuilder().with_name("Bay A").add_zone("North", 0.2, 0.4).build()
    LocationConfigBuilder().with_name("Bay B").add_zone("North", 0.2, 0.4).build()


def test_built_product_is_immutable():
    config = valid_builder().build()
    assert isinstance(config.location.zones, tuple)
    with pytest.raises(FrozenInstanceError):
        config.location.name = "Changed"


def test_builder_has_no_device_step():
    assert not hasattr(LocationConfigBuilder(), "add_device")