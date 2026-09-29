# Builder — Location configuration

## Intent in this project

A location is configured in steps: a name, then one or more zones, each with
moisture thresholds (VWC 0.0–1.0) and an optional schedule. Several rules span
the whole configuration (at least one zone, unique zone names within the
location). `LocationConfigBuilder` collects those steps and `build()` checks
every rule in one place. It returns an **unsaved, immutable** `LocationConfig`
or raises `ConfigurationError`. Only a config that passed `build()` is ever
persisted.

```python
config = (
    LocationConfigBuilder()
    .with_name("Bay A")
    .add_zone("North", 0.20, 0.40)
    .add_zone("South", 0.25, 0.45, {"water_at": "06:00"})
    .build()
)
```

## Why this is Builder (not Factory Method / Abstract Factory)

| Pattern | Question | Used for |
|---------|----------|----------|
| Factory Method (Phase 2) | Which **type** of one product? | One sensor with type-specific defaults |
| Abstract Factory (Phase 3) | Which **family** of products? | A matching kit of sensors + actuators |
| Builder (Phase 4) | How do we **assemble one complex object validly**? | A location with a variable number of zones |

The factories decide *which* variant to create and produce it in one call.
Here the client supplies the parts (name, any number of zones) and the
difficulty is assembling them into a valid whole. A constructor with many
parameters could create a half-valid location (no zones, inverted thresholds);
the builder makes that impossible because the product only exists after
`build()` succeeds.

## Where validation lives

- **Domain:** `backend/src/domain/locations/config_builder.py`
  - `build()` — location name required, at least one zone, unique zone names
    (case-insensitive), and each zone checked by `validate_zone_fields()`.
  - `validate_zone_fields()` — non-empty name, thresholds within 0.0–1.0,
    low strictly less than high. Also reused by the zone add/edit use cases,
    so there is one set of zone rules, not two.
- **Application:** `config_service.py` calls `build()` (through the mapper)
  *before* the repository, so an invalid config never reaches the database.
- **API:** only translates `ConfigurationError` → 400. DTOs check types, not
  business rules, so the domain stays the single authority.
- **Frontend:** mirrors the rules for instant inline feedback, but the server's
  400 message is still shown when it rejects something.
- **Persistence:** `LocationRepository.save_config()` writes the location and
  all its zones in one transaction (flush for the id, one commit, rollback on
  failure), so a location is never saved without its zones.

## Why `location_id` naming

The resource is a **location** (a bay, room or site in the greenhouse), not
the whole greenhouse. Using `location_id` in `zones`, `devices`, DTOs and routes
keeps the relational naming consistent and leaves room for several locations
within one greenhouse product. No schema or endpoint uses `greenhouse_id`.

## Why device assignment is not a builder method

- A zone has no `id` until the config is saved, so there is nothing to point a
  device at during building.
- Devices already exist (Phases 2–3); moving a device between zones is an
  everyday update, not a reason to rebuild a location.
- Assignment is handled by `ZoneAssignmentService`
  (`PATCH /api/devices/{id}/zone`). It copies `location_id` from the zone in
  the same write, and clears both columns on unassign, so a device's location
  can never disagree with its zone.

The same reasoning applies to listing and deleting locations and to adding,
editing or deleting zones on a saved location: these are separate operations
that do not call `build()`.

## Where in code

- `backend/src/domain/locations/` — `entity.py`, `config_builder.py`, `errors.py`
- `backend/src/application/locations/` — `dto.py`, `mappers.py`, `config_service.py`, `zone_service.py`, `zone_assignment_service.py`
- `backend/src/infrastructure/persistence/location_repository.py`
- `backend/src/interfaces/api/locations.py`, and `devices.py` (assignment route)
- `frontend/src/components/config/` — `LocationConfigWizard.tsx` and its parts
- `backend/tests/test_location_config_builder.py`, `test_locations_api.py`