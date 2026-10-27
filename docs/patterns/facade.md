# Facade pattern — location overview (Phase 7)

## Problem

The dashboard needs one snapshot per location: the location and its zones,
which devices are assigned where, each device's newest reading, the saved
automation strategy and what that strategy recommends right now. That data
lives in four subsystems built in earlier phases (locations/zones, devices,
readings, automation). Without a facade, either the router would import five
repositories and assemble the result, or the React panel would call several
endpoints and merge them in the browser. Every client would need to know how
the subsystems fit together.

## Solution

One entry point, `LocationOverviewFacade.get_overview(location_id)`, returns
one read model, `LocationOverviewDto`. The facade coordinates existing
subsystems and adds no business rules of its own: it fetches, groups and maps.

```text
GET /api/locations/{location_id}/overview
  router ──► LocationOverviewFacade.get_overview(location_id)
               ├── LocationRepository.get_location          location + every zone
               ├── DeviceRepository.list_assigned_in_location
               ├── ReadingRepository.latest_by_device
               └── AutomationService.get_rule / evaluate    saved key + recommendation
```

Subsystems hidden behind the facade: locations and zones (Phase 4), assigned
devices (Phases 2–4), sensor readings (Phase 5), saved strategy and its
evaluation (Phase 6).

## Rules the read model follows

- **Scoped by `location_id`.** No `greenhouse_id` anywhere.
- **Assigned** means the device has this `location_id` *and* a non-null
  `zone_id`. Unassigned devices are absent from `device_counts`, from
  `zones[].devices` and from `zones[].latest_readings`.
- **Every zone is listed**, including one with no devices (empty `devices` and
  `latest_readings`). Zones come from the location, not from the devices.
- **`latest_readings` is nested per zone**: one newest row (by `recorded_at`)
  per assigned device that has one, from any source (manual read, sampler,
  MQTT ingest). A device with no reading stays in `devices`.
  `tracking_enabled` and `sampling_interval_seconds` are copied from the device;
  they are not columns on `sensor_readings`.
- **No saved strategy** → HTTP 200 with `strategy_key` and
  `last_recommendation` both `null`. A missing location → 404.

## The recommendation is computed, not cached

`last_recommendation` is produced on **every GET** by calling the existing
`AutomationService.evaluate(location_id)` and copying its top-level `action`
and `reason`. The facade does not call the evaluate HTTP route, does not
reimplement `decide`, and does not store the result in a new table. The facade
first asks `AutomationService.get_rule`; it calls `evaluate` only when a key is
saved, so "no key" is a normal branch, not a caught exception. Because nothing
is cached, the next GET after a new reading or a strategy change reflects the
database.

## Query shape

1. `get_location` — the location and its zones (one load).
2. `list_assigned_in_location` — one query for all assigned devices.
3. `latest_by_device` — one query for the newest reading of all those device
   ids, using Postgres `DISTINCT ON (device_id) ... ORDER BY device_id,
   recorded_at DESC` (served by the Phase 5 index on
   `(device_id, recorded_at DESC)`). Skipped entirely when there are no devices.
4. `AutomationService.get_rule` — the saved key.
5. Only if a key exists: `AutomationService.evaluate`.

There is no reading query per device in a Python loop. `evaluate` still looks
up moisture (and light) **once per zone** inside the automation service, and
re-checks the location and rule. That duplication is accepted deliberately:
the facade reuses the automation subsystem through its public service instead
of reaching into its internals or reimplementing `decide` to save a few
queries.

## Wiring

The router (`interfaces/api/overview.py`) imports only the facade, its DTO and
`LocationNotFoundError`; it imports no repositories and no `AutomationService`.
The facade is assembled from a session by `build_location_overview_facade(db)`
in `application/overview/facade.py`, so knowledge of the facade's parts lives
in one place. The facade itself still receives its collaborators through the
constructor, so tests can pass their own.

## Frontend

`OverviewPanel` (`#overview` on `DashboardPage`) uses the existing locations
list for its dropdown, then one `getLocationOverview(locationId)` call feeds
every card: assigned counts, strategy, recommendation, and one card per zone
with thresholds, devices and their reading or a "No reading" state. Refresh
repeats the same call. The panel does not call device, reading or automation
endpoints.

## Database

No new table and no migration. The optional `location_overview_v1` view was
skipped: existing tables (`locations`, `zones`, `devices`, `sensor_readings`,
`automation_rules`) are enough.

## Where in code

- `backend/src/application/overview/dto.py` — `LocationOverviewDto` and nested DTOs
- `backend/src/application/overview/facade.py` — `LocationOverviewFacade`,
  `build_location_overview_facade`
- `backend/src/infrastructure/persistence/device_repository.py` —
  `list_assigned_in_location`
- `backend/src/infrastructure/persistence/reading_repository.py` —
  `latest_by_device`
- `backend/src/interfaces/api/overview.py` —
  `GET /api/locations/{location_id}/overview`
- `frontend/src/features/overview/OverviewPanel.tsx`,
  `frontend/src/services/api.ts` (`getLocationOverview`)
- `backend/tests/test_overview_api.py` —
  `test_overview_returns_strategy_and_readings`