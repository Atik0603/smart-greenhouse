"""
Sensor adapter selection rule (Phase 5):

1. default_config["adapter"] == "vendor_stub"  -> VendorStubSensorAdapter
   (a separate key, so it never collides with the protocol values)
2. default_config["protocol"] == "simulation"  -> SimulationSensorAdapter
3. default_config["protocol"] == "mqtt"        -> MqttSensorAdapter
4. anything else                               -> SensorReadError
"""

from src.domain.devices.entity import Device
from src.domain.sensors.ports import SensorPort, SensorReadError
from src.infrastructure.adapters.sensors.mqtt import MqttSensorAdapter
from src.infrastructure.adapters.sensors.simulation import SimulationSensorAdapter
from src.infrastructure.adapters.sensors.vendor_stub import VendorStubSensorAdapter

VENDOR_STUB_FLAG = "vendor_stub"

# Adapters hold no per-device state, so one shared instance of each is enough.
_SIMULATION = SimulationSensorAdapter()
_VENDOR_STUB = VendorStubSensorAdapter()
_MQTT = MqttSensorAdapter()

_BY_PROTOCOL: dict[str, SensorPort] = {
    "simulation": _SIMULATION,
    "mqtt": _MQTT,
}


def select_sensor_adapter(device: Device) -> SensorPort:
    config = device.default_config or {}
    if config.get("adapter") == VENDOR_STUB_FLAG:
        return _VENDOR_STUB
    adapter = _BY_PROTOCOL.get(config.get("protocol"))
    if adapter is None:
        raise SensorReadError(
            f"No sensor adapter for protocol {config.get('protocol')!r} on device {device.id}"
        )
    return adapter