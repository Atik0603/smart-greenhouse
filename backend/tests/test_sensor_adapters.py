import random
import socket
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.devices.entity import Device
from src.domain.sensors.ports import SensorReadError
from src.domain.sensors.reading import Reading
from src.infrastructure.adapters.actuators.simulation import SimulationActuatorAdapter
from src.infrastructure.adapters.sensors.mqtt import MqttSensorAdapter
from src.infrastructure.adapters.sensors.selector import select_sensor_adapter
from src.infrastructure.adapters.sensors.simulation import SIMULATION_RANGES, SimulationSensorAdapter
from src.infrastructure.adapters.sensors.vendor_stub import AcmeSensorSdkStub, VendorStubSensorAdapter

FIXED_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_device(device_type="moisture_sensor", **config) -> Device:
    return Device(
        id=uuid.uuid4(),
        device_type=device_type,
        role="sensor",
        device_family="simulation",
        display_name="Test sensor",
        default_config=config,
    )


# --- Reading value object ---

def test_reading_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        Reading(uuid.uuid4(), 0.3, "vwc", "simulation", datetime(2026, 1, 1, 12, 0))


def test_reading_rejects_unknown_source():
    with pytest.raises(ValueError, match="source"):
        Reading(uuid.uuid4(), 0.3, "vwc", "banana", FIXED_TIME)


# --- Simulation adapter ---

@pytest.mark.parametrize("device_type", ["moisture_sensor", "light_sensor"])
def test_simulation_values_stay_in_documented_range(device_type):
    low, high, unit = SIMULATION_RANGES[device_type]
    adapter = SimulationSensorAdapter(rng=random.Random(42), clock=lambda: FIXED_TIME)
    device = make_device(device_type)

    for _ in range(200):
        reading = adapter.read(device)
        assert low <= reading.value <= high
        assert reading.unit == unit
        assert reading.source == "simulation"
        assert reading.device_id == device.id
        assert reading.recorded_at == FIXED_TIME


def test_simulation_rejects_device_type_it_cannot_generate():
    with pytest.raises(SensorReadError):
        SimulationSensorAdapter().read(make_device("water_pump"))


# --- Vendor stub adapter (translation is the point) ---

def test_vendor_soil_payload_translates_to_vwc():
    device_id = uuid.uuid4()
    raw = {"serial": "X1", "kind": "SOIL", "rawPermille": 412, "timestampMs": 1_767_268_800_000}

    reading = VendorStubSensorAdapter.translate(device_id, raw)

    assert reading == Reading(
        device_id=device_id,
        value=0.412,
        unit="vwc",
        source="vendor",
        recorded_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )


def test_vendor_light_payload_translates_to_lux():
    reading = VendorStubSensorAdapter.translate(
        uuid.uuid4(), {"kind": "LIGHT", "rawDeciLux": 15230, "timestampMs": 1_767_268_800_000}
    )
    assert reading.value == 1523.0
    assert reading.unit == "lux"
    assert reading.source == "vendor"


@pytest.mark.parametrize(
    "raw",
    [
        {"kind": "SOIL", "timestampMs": 1_767_268_800_000},          # missing rawPermille
        {"kind": "SOIL", "rawPermille": 412},                         # missing timestampMs
        {"kind": "WIND", "rawKnots": 3, "timestampMs": 1_767_268_800_000},  # unknown kind
    ],
)
def test_vendor_malformed_payload_becomes_sensor_read_error(raw):
    with pytest.raises(SensorReadError):
        VendorStubSensorAdapter.translate(uuid.uuid4(), raw)


def test_vendor_read_goes_through_sdk_and_yields_vendor_source():
    adapter = VendorStubSensorAdapter(sdk=AcmeSensorSdkStub(rng=random.Random(1)))
    reading = adapter.read(make_device("moisture_sensor"))
    assert reading.source == "vendor"
    assert reading.unit == "vwc"
    assert 0.2 <= reading.value <= 0.6


def test_same_logical_read_has_different_source_per_adapter():
    device = make_device("moisture_sensor")
    sim = SimulationSensorAdapter(rng=random.Random(1)).read(device)
    vendor = VendorStubSensorAdapter(sdk=AcmeSensorSdkStub(rng=random.Random(1))).read(device)
    assert (sim.source, vendor.source) == ("simulation", "vendor")
    assert sim.unit == vendor.unit == "vwc"


# --- MQTT adapter (translation without a broker) ---

def test_mqtt_payload_translates_without_opening_a_socket(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("MQTT translation must not open a socket")

    monkeypatch.setattr(socket, "socket", no_network)

    device_id = uuid.uuid4()
    reading = MqttSensorAdapter(clock=lambda: FIXED_TIME).translate(device_id, {"value": 0.41, "unit": "vwc"})

    assert reading == Reading(device_id, 0.41, "vwc", "mqtt", FIXED_TIME)


def test_mqtt_uses_payload_timestamp_when_given():
    reading = MqttSensorAdapter().translate(
        uuid.uuid4(), {"value": 1200, "unit": "lux", "recorded_at": "2026-01-01T12:00:00+00:00"}
    )
    assert reading.recorded_at == FIXED_TIME
    assert reading.value == 1200.0


@pytest.mark.parametrize(
    "payload",
    [
        {"unit": "vwc"},                                   # no value
        {"value": "0.4", "unit": "vwc"},                   # value is a string
        {"value": True, "unit": "vwc"},                    # bool is not a number here
        {"value": 0.4, "unit": ""},                        # empty unit
        {"value": 0.4, "unit": "vwc", "recorded_at": "2026-01-01T12:00:00"},  # no timezone
    ],
)
def test_mqtt_rejects_invalid_payloads(payload):
    with pytest.raises(SensorReadError):
        MqttSensorAdapter().translate(uuid.uuid4(), payload)


def test_mqtt_devices_cannot_be_read_on_demand():
    with pytest.raises(SensorReadError, match="push"):
        MqttSensorAdapter().read(make_device(protocol="mqtt"))


# --- Selector rule ---

def test_selector_follows_documented_rule():
    assert isinstance(select_sensor_adapter(make_device(protocol="simulation")), SimulationSensorAdapter)
    assert isinstance(select_sensor_adapter(make_device(protocol="mqtt")), MqttSensorAdapter)
    # vendor flag wins over protocol
    assert isinstance(
        select_sensor_adapter(make_device(protocol="simulation", adapter="vendor_stub")),
        VendorStubSensorAdapter,
    )
    with pytest.raises(SensorReadError):
        select_sensor_adapter(make_device(protocol="zigbee"))


# --- Actuator port ---

def test_simulation_actuator_records_commands_in_memory():
    adapter = SimulationActuatorAdapter(clock=lambda: FIXED_TIME)
    device_id = uuid.uuid4()

    result = adapter.apply(device_id, "on", {"duration_s": 10})

    assert result.device_id == device_id
    assert result.command == "on"
    assert result.payload == {"duration_s": 10}
    assert result.applied_at == FIXED_TIME
    assert adapter.applied == [result]