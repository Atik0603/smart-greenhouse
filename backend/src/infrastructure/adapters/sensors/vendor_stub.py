import random
from datetime import datetime, timezone
from uuid import UUID

from src.domain.devices.entity import Device
from src.domain.sensors.ports import SensorPort, SensorReadError
from src.domain.sensors.reading import Reading


class AcmeSensorSdkStub:
    """Pretend third-party SDK. Its API and data shape are deliberately unlike ours."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    def fetch(self, serial: str, kind: str) -> dict:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        if kind == "SOIL":
            return {"serial": serial, "kind": "SOIL", "rawPermille": self._rng.randint(200, 600), "timestampMs": now_ms}
        if kind == "LIGHT":
            return {"serial": serial, "kind": "LIGHT", "rawDeciLux": self._rng.randint(2000, 20000), "timestampMs": now_ms}
        raise ValueError(f"Acme SDK does not support kind {kind}")


# Our device_type -> the vendor's name for that kind of sensor
VENDOR_KIND_BY_DEVICE_TYPE = {"moisture_sensor": "SOIL", "light_sensor": "LIGHT"}


class VendorStubSensorAdapter(SensorPort):
    def __init__(self, sdk: AcmeSensorSdkStub | None = None) -> None:
        self._sdk = sdk or AcmeSensorSdkStub()

    def read(self, device: Device) -> Reading:
        kind = VENDOR_KIND_BY_DEVICE_TYPE.get(device.device_type)
        if kind is None:
            raise SensorReadError(f"Vendor SDK has no sensor kind for '{device.device_type}'")
        raw = self._sdk.fetch(serial=str(device.id), kind=kind)  # speak the vendor's language
        return self.translate(device.id, raw)                     # answer in ours

    @staticmethod
    def translate(device_id: UUID, raw: dict) -> Reading:
        try:
            recorded_at = datetime.fromtimestamp(raw["timestampMs"] / 1000, tz=timezone.utc)
            if raw["kind"] == "SOIL":
                value, unit = raw["rawPermille"] / 1000, "vwc"
            elif raw["kind"] == "LIGHT":
                value, unit = raw["rawDeciLux"] / 10, "lux"
            else:
                raise SensorReadError(f"Unknown vendor sensor kind: {raw['kind']!r}")
        except (KeyError, TypeError) as exc:
            raise SensorReadError(f"Malformed vendor payload: {exc}") from exc

        return Reading(device_id=device_id, value=value, unit=unit, source="vendor", recorded_at=recorded_at)