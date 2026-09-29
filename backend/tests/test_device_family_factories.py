import pytest

from src.domain.devices.family_factory import (
    DEVICE_FAMILY_FACTORIES,
    EdgeDeviceFactory,
    SimulationDeviceFactory,
    UnknownDeviceFamilyError,
    get_family_factory,
)


def test_simulation_kit_has_four_devices_one_family_and_both_roles():
    devices = SimulationDeviceFactory().create_device_set()

    assert len(devices) == 4
    assert {d.device_family for d in devices} == {"simulation"}
    assert [d.role for d in devices].count("sensor") == 2
    assert [d.role for d in devices].count("actuator") == 2


def test_edge_kit_differs_from_simulation_in_family_and_config():
    sim = SimulationDeviceFactory().create_device_set()
    edge = EdgeDeviceFactory().create_device_set()

    assert {d.device_family for d in edge} == {"edge"}
    sim_protocols = {d.default_config["protocol"] for d in sim}
    edge_protocols = {d.default_config["protocol"] for d in edge}
    assert sim_protocols.isdisjoint(edge_protocols)


def test_family_sensors_still_come_from_phase2_creators():
    devices = EdgeDeviceFactory().create_device_set()
    moisture = next(d for d in devices if d.device_type == "moisture_sensor")

    assert moisture.role == "sensor"
    assert moisture.default_config["moisture_threshold"] == 30   # Phase 2 default kept
    assert moisture.default_config["protocol"] == "i2c"          # family config added


@pytest.mark.parametrize("family_key", list(DEVICE_FAMILY_FACTORIES))
def test_every_registered_family_never_mixes_families(family_key):
    devices = get_family_factory(family_key).create_device_set()

    assert {d.device_family for d in devices} == {family_key}
    assert all(d.id is None for d in devices)


def test_unknown_family_raises_domain_error():
    with pytest.raises(UnknownDeviceFamilyError):
        get_family_factory("banana")