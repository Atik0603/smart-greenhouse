# State pattern — actuator lifecycle (Phase 8)

## Problem

An actuator (pump relay, LED panel) cannot accept every command at every moment:
you cannot stop a pump that is not running, and you should not cut the power or
send it into maintenance in the middle of watering. Which actions are legal depends
on what the device is currently doing. Writing that as `if state == "idle" and
command == ...` chains in routers and services scatters the rules, and one path
eventually forgets one.

## Solution

Each lifecycle state is an object that knows which states it may move to and which
command causes each move. The actuator's **context** holds the current state object
and delegates to it. An illegal move raises a domain error before anything is saved.

```text
ActuatorState (ABC)
    transitions() -> {target state: command | None}
        ├── OffState          ├── IdleState       ├── RunningState
        ├── MaintenanceState  └── ErrorState
ActuatorContext(device_type, state)
    transition(target)    → IllegalTransitionError if not allowed
    allowed_commands()    → derived from the current state
```

## Legal transitions

Everything not listed is illegal (for example `running → off`, `running →
maintenance`, `off → running`, `error → running`, or any move to the same state).

| From | To | Command |
|---|---|---|
| `off` | `idle` | `power_on` |
| `idle` | `running` | `start` (`start_pump` / `lights_on`) |
| `idle` | `maintenance` | `begin_maintenance` |
| `idle` | `off` | `power_off` |
| `idle` | `error` | system event |
| `running` | `idle` | `stop` (`stop_pump` / `lights_off`) |
| `running` | `error` | system event |
| `maintenance` | `idle` | `end_maintenance` |
| `maintenance` | `error` | system event |
| `error` | `idle` | `reset` |
| `error` | `maintenance` | `begin_maintenance` |

A running device must stop first before it can be powered off or serviced. Every
powered state can fail (`→ error`); a device that is off cannot. After an error it is
either reset or sent to maintenance.

## Decisions

- **`error` is an event, not a command.** Nobody presses a "break" button, so
  `→ error` is a legal transition (the demo endpoint can trigger it) but never appears
  in `allowed_commands`, which lists only actions a user can take.
- **Command names follow the device type** for start/stop (`start_pump`/`stop_pump` for
  a `water_pump`, `lights_on`/`lights_off` for a `grow_light`); the other commands are
  generic. Phase 10's Command objects reuse these names.
- **Storage:** table `actuator_states` (`device_id` PK and FK to `devices` with
  `ON DELETE CASCADE`, `state`, `updated_at`). State is always loaded from the database
  and never kept in the FastAPI process, so it survives a restart.
- **Seeding:** the migration inserts `idle` for every existing `role = 'actuator'`
  device, because it is a one-time data change tied to the schema change. Actuators
  provisioned later have no row; the repository treats a missing row as the initial
  state `idle` and creates the row on the first legal transition. Every actuator
  therefore always resolves a state, and Phase 3's factories did not change.
- **Closed set, so a CHECK constraint.** `state` has a database CHECK limited to the five
  names, unlike Phase 6's `strategy_key`, which has none. Strategies are an open set
  (a new one is just a new class), whereas lifecycle states are a closed set: adding one
  means redesigning the table, so a migration is expected, and the constraint stops
  even a manual SQL update from storing a typo.
- **Guard before save.** `ActuatorContext.transition` raises before the state changes,
  and `ActuatorStateService` calls `save_state` only after `transition` returns, so an
  illegal move never reaches the table.
- **Errors:** an unknown state name or a sensor target is **400**; a well-formed but
  disallowed move is **409** (it conflicts with the resource's current state); a missing
  device is **404**.
- **The UI only displays.** React shows `state` and `allowed_commands` (badge and
  tooltip). Its demo selector deliberately offers illegal targets too, so the backend's
  409 explanation is what the user sees.

## State vs Strategy

| | Strategy (Phase 6) | State (Phase 8) |
|---|---|---|
| What varies | a policy: how to decide | a lifecycle: what is legal now |
| Who changes the active object | the client (the grower picks a key) | the context itself, through transitions |
| Do the objects know each other | no | yes, each state names its next states |

## Where in code

- `backend/src/domain/actuators/` — `state.py` (state objects, registry), `context.py`
  (`ActuatorContext`, command names), `errors.py`
- `backend/src/infrastructure/persistence/actuator_state_repository.py`
- `backend/src/application/devices/actuator_state_service.py`, `dto.py`, `mappers.py`
- `backend/src/interfaces/api/devices.py` — `state` and `allowed_commands` on device
  responses, `POST /api/devices/{device_id}/transition`;
  `backend/src/interfaces/api/locations.py` — zone device list
- `frontend/src/components/devices/ActuatorStateBadge.tsx`,
  `ActuatorTransitionDemo.tsx`
- `backend/tests/test_actuator_state.py`, `test_actuator_state_service.py`,
  `test_actuator_state_api.py`

## Exercise: add a state

Add `calibrating` (reachable from `maintenance`, back to `idle` when finished).

1. Add `CalibratingState` in `state.py` with its `transitions()` and register it.
2. Add `calibrating` to `MaintenanceState.transitions()` and update the table above.
3. Update the CHECK constraint with a new Alembic migration (a closed set needs one).
4. Add the edges to `LEGAL` in `test_actuator_state.py`.

The service, router and frontend badge need no change, apart from a badge colour.