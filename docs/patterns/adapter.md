# Adapter — Sensor and actuator ports

## Problem: incompatible device interfaces

Sensors arrive in different shapes. A simulated sensor produces a number in
code; a vendor SDK speaks its own language (`kind: "SOIL"`, `rawPermille: 412`,
`timestampMs` in epoch milliseconds); an MQTT device pushes a payload dict such
as `{"value": 0.41, "unit": "vwc"}`. If services and routers handled those
formats directly, every caller would need `if source == ...` branches, vendor
field names and unit conversions would leak across the codebase, and adding a
device type would mean editing business code.

## Solution: one port, one adapter per format

- **Target / port** (domain): `SensorPort.read(device) -> Reading` and
  `ActuatorPort.apply(device_id, command, payload) -> AppliedCommand`.
  No FastAPI, SQLAlchemy, Pydantic or network code.
- **Normalized value object:** `Reading(device_id, value, unit, source, recorded_at)`,
  frozen, with a timezone-aware `recorded_at` and `source` in
  `simulation | vendor | mqtt`.
- **Adapters** (infrastructure), each translating one format into `Reading`:

| Adapter | Adaptee / input | Translation | `source` |
|---------|-----------------|-------------|----------|
| `SimulationSensorAdapter` | in-process generator | range by `device_type` (moisture 0.2–0.6 vwc, light 200–2000 lux) | `simulation` |
| `VendorStubSensorAdapter` | `AcmeSensorSdkStub` (object adapter, composition) | `rawPermille / 1000` → vwc, `rawDeciLux / 10` → lux, `timestampMs` → UTC datetime; vendor errors → `SensorReadError` | `vendor` |
| `MqttSensorAdapter` | payload dict | `translate(device_id, {"value", "unit", "recorded_at"?})`; `read()` refuses (push-only); never opens a broker | `mqtt` |
| `SimulationActuatorAdapter` | none (no GPIO) | records commands in memory and logs them | — |

- **Client:** `ReadingIngest` receives an adapter **selector** function and only
  calls `SensorPort.read()`. It never imports an adapter class.

## Adapter selection rule

Defined once in `infrastructure/adapters/sensors/selector.py`:

1. `default_config.adapter == "vendor_stub"` → vendor stub (a separate key, so it
   never collides with protocol values)
2. `default_config.protocol == "simulation"` → simulation adapter
3. `default_config.protocol == "mqtt"` → MQTT adapter
4. anything else → `SensorReadError` (HTTP 400)

Family `simulation` devices use `protocol: simulation`; family `edge` devices use
`protocol: mqtt`. The Phase 5 migration normalized existing rows to these values.

## One ingest path

`ReadingIngest.record(device_id, reading=None, at=None)` is the only writer of
`sensor_readings`:

- `POST /api/sensors/{id}/read` → one-shot read through the selected adapter
- `SimulationSampler.run_once(now)` (started from the app lifespan, ticking every
  5 s) → records enabled `protocol: simulation` sensors whose
  `sampling_interval_seconds` has elapsed, stamping the tick time
- Phase 12 → `MqttSensorAdapter.translate(...)` output passed in as `reading`

`sampling_interval_seconds` and `tracking_enabled` are columns on `devices` and
the source of truth (backfilled from `default_config` by migration). MQTT
devices and devices with tracking off are never sampled. Readings are appended,
indexed by `(device_id, recorded_at DESC)` for "latest per device" queries.

## Where in code

- `backend/src/domain/sensors/reading.py`, `ports.py` — `Reading`, `SensorPort`, `SensorReadError`
- `backend/src/domain/actuators/ports.py` — `ActuatorPort`, `AppliedCommand`
- `backend/src/infrastructure/adapters/sensors/` — `simulation.py`, `vendor_stub.py`, `mqtt.py`, `selector.py`
- `backend/src/infrastructure/adapters/actuators/simulation.py`
- `backend/src/application/readings/` — `service.py` (`ReadingIngest`), `sampler.py`, `dto.py`, `mappers.py`
- `backend/src/infrastructure/persistence/reading_repository.py`
- `backend/src/interfaces/sampler_runner.py` — background loop; `main.py` lifespan
- `backend/src/interfaces/api/sensors.py` (read, history), `devices.py` (sampling PATCH)
- `frontend/src/features/sensors/SensorReadingPanel.tsx` — Read now, sampling controls, temporary poll
- `backend/tests/test_sensor_adapters.py`,