from datetime import datetime
from typing import Callable
from uuid import UUID

from src.domain.devices.entity import Device
from src.domain.sensors.ports import SensorPort, SensorReadError
from src.domain.sensors.reading import Reading, utc_now


class MqttSensorAdapter(SensorPort):
    """Translates MQTT-style payload dicts into Readings. Never opens a broker connection."""

    def __init__(self, clock: Callable[[], datetime] = utc_now) -> None:
        self._clock = clock

    def read(self, device: Device) -> Reading:
        raise SensorReadError(
            "MQTT devices push their readings; they cannot be read on demand"
        )

    def translate(self, device_id: UUID, payload: dict) -> Reading:
        value = payload.get("value")
        unit = payload.get("unit")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SensorReadError("MQTT payload 'value' must be a number")
        if not isinstance(unit, str) or not unit.strip():
            raise SensorReadError("MQTT payload 'unit' must be a non-empty string")

        recorded_at = self._clock()
        raw_time = payload.get("recorded_at")
        if raw_time is not None:
            try:
                recorded_at = datetime.fromisoformat(raw_time)
            except (TypeError, ValueError) as exc:
                raise SensorReadError("MQTT payload 'recorded_at' must be an ISO-8601 string") from exc
            if recorded_at.tzinfo is None:
                raise SensorReadError("MQTT payload 'recorded_at' must include a timezone")

        return Reading(
            device_id=device_id,
            value=float(value),
            unit=unit.strip(),
            source="mqtt",
            recorded_at=recorded_at,
        )