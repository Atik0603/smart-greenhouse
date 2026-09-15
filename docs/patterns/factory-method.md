# Pattern Note: Factory Method — Sensor Creation

## Problem

Sensors come in different types (moisture, light, and more later) with
type-specific default configuration: units, sampling intervals,
thresholds. If the API handler constructed sensors directly —
`if type == "moisture": Sensor(unit="percent", ...)` — every new sensor
type would mean editing that same handler again, and the defaults for
each type would live far away from the type they belong to.

## Solution

Each sensor type has its own **creator** class responsible for that
type's defaults. All creators implement a shared `create_sensor()`
method (the *factory method*). The application layer looks up a
creator by a short type key (`"moisture"`, `"light"`) from a registry
dict, calls `create_sensor()`, and persists the result — it never
imports or instantiates a concrete sensor type directly.

Adding a new sensor type means adding one new creator class and one
registry entry — not touching the HTTP router, the service, or any
other creator.

## Where to look in code

| Role | Location |
|---|---|
| Product (`Sensor` entity) | `backend/src/domain/sensors/entity.py` |
| Creator interface | `backend/src/domain/sensors/creators.py` — `SensorCreator` |
| Concrete creators | same file — `MoistureSensorCreator`, `LightSensorCreator` |
| Registry | same file — `SENSOR_CREATORS` dict |
| Client (uses the registry) | `backend/src/application/sensors/service.py` — `SensorService.create_sensor` |
| Persistence mapping | `backend/src/infrastructure/persistence/device_repository.py` |
| HTTP boundary | `backend/src/interfaces/api/sensors.py` |
| Unit tests | `backend/tests/test_sensor_creators.py` |

## Extension exercise

Add a `temperature` sensor type end-to-end:

1. Add `TemperatureSensorCreator` in `creators.py`, with a distinct
   `default_config` (e.g. `{"unit": "celsius", "sampling_interval_seconds": 120}`).
2. Register it: `"temperature": TemperatureSensorCreator()` in
   `SENSOR_CREATORS`.
3. Add a unit test asserting its `device_type` and a config key unique
   to it.
4. No changes needed in `service.py`, `sensors.py` (the router), or
   the frontend's type union beyond adding `"temperature"` to the
   allowed values — that's the point of the pattern.