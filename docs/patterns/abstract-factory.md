# Abstract Factory — Device families

## Problem

A greenhouse environment needs sensors **and** actuators that belong together.
A simulation setup uses simulated devices; an edge (hardware) setup uses
hardware-style devices with protocols such as I2C and GPIO. If each device
were chosen with its own `if family == ...`, nothing would stop a simulated
moisture sensor from being paired with a real edge water pump — each device
is valid on its own, but the combination is wrong and potentially harmful.

## Solution

One **family factory** creates the whole matching kit. The client picks the
factory once; every device it returns belongs to that family by construction.

| Role | Code |
|------|------|
| Abstract factory | `DeviceFamilyFactory` — `create_sensors()`, `create_actuators()`, `create_device_set()` |
| Concrete factories | `SimulationDeviceFactory`, `EdgeDeviceFactory` |
| Abstract product | `Device` (role = sensor or actuator) |
| Concrete products | the 4 devices in each kit (moisture, light, water pump, grow light) |
| Registry | `DEVICE_FAMILY_FACTORIES` + `get_family_factory()` |
| Client | `DeviceFamilyService.provision_family()` |

`create_device_set()` is implemented once in the abstract factory and always
calls both `create_sensors()` and `create_actuators()`, so no family can
produce a kit that is missing a role.

## Contrast with Factory Method (Phase 2)

| | Factory Method | Abstract Factory |
|--|----------------|------------------|
| Question | Which **one** product? | Which **product line**? |
| Output | One `Sensor` | A list of matching `Device`s |
| Prevents | Wrong defaults for a single sensor | Mixing devices from different families |

The two patterns are composed, not competing: family factories build their
sensors by calling the Phase 2 creators (`SENSOR_CREATORS`), then tag the
result with the family key and add family-specific config (e.g. `protocol`).

## Where in code

- `backend/src/domain/devices/entity.py` — `Device`
- `backend/src/domain/devices/family_factory.py` — abstract + concrete factories, registry, `UnknownDeviceFamilyError`
- `backend/src/domain/sensors/creators.py` — Phase 2 creators, reused
- `backend/src/application/devices/family_service.py` — client: resolve factory → create set → persist
- `backend/src/infrastructure/persistence/device_repository.py` — saves a kit in one transaction; lists with family/role filters
- `backend/src/interfaces/api/devices.py` — `GET /api/devices`, `POST /api/devices/provision?family=...`
- `frontend/src/components/devices/` — family switcher, device list, provision button
- `backend/tests/test_device_family_factories.py` — factory tests (no DB/HTTP)

## Why `Device` ≠ `DeviceDto`

`Device` is the domain model: plain Python, no framework imports, free to
change internally. `DeviceDto` is the API contract: a Pydantic model that
defines the JSON shape and the Scalar schema. Keeping them separate means
internal changes don't leak into the API, and the domain stays independent
of Pydantic/FastAPI. A dedicated mapper in the application layer converts
between them at the boundary; the factory and repository never import the DTO.

## Extension exercise: a third family

To add e.g. a `cloud` family:

1. Write `CloudDeviceFactory(DeviceFamilyFactory)` with `family_key = "cloud"`
   and its own `create_sensors()` / `create_actuators()`.
2. Register it: `"cloud": CloudDeviceFactory()` in `DEVICE_FAMILY_FACTORIES`.
3. Add `"cloud"` to the frontend `DeviceFamily` type and switcher options.

No changes are needed in the service, repository, router, or DTO — and the
parametrized "never mixes families" test covers the new family automatically.
Adding a new **product kind** (e.g. a camera in every kit) is the costly
direction: every concrete factory must be updated.