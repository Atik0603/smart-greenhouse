# Command pattern — actuator commands and audit history (Phase 10)

## Problem

Controlling an actuator used to be a direct call to the port. That call leaves no
record of what the operator asked for, every caller would have to repeat the same
steps (check the state, call the port, update the state, record the outcome), and
a request can't be listed, queued or replayed because it's gone the moment it runs.

## Solution

Each request is an object. A command knows its type, target device, payload, the
lifecycle state it leads to, and how to execute itself against an `ActuatorPort`.
An invoker runs any command without knowing which kind it is. The application
service wraps every run in the same guarded steps and records each attempt in
`command_log`.

| Role | Class |
|---|---|
| Command | `Command` (`domain/commands/base.py`): `command_type`, `target_state`, `execute(port)` |
| Concrete commands | `StartPumpCommand`, `StopPumpCommand`, `SetLightLevelCommand` |
| Receiver | `ActuatorPort`: the Phase 9 stack Logging → MaxRunTime → `SimulationActuatorAdapter` |
| Invoker | `CommandInvoker.run(command, port)` |
| Client | `CommandService`, which builds the command from the HTTP request |

| Command | Sent to the port | `target_state` |
|---|---|---|
| `start_pump` | `start_pump`, `{}` | `running` |
| `stop_pump` | `stop_pump`, `{}` | `idle` |
| `set_light_level` | `set_light_level`, `{"level": n}` (0–100, default 1) | `running` |

A registry (`_REGISTRY` in `invoker.py`) maps the type string to the class. Neither
the invoker nor the service contains `if command_type == ...`.

## Execute path

`POST /api/commands` → `CommandService.submit`:

1. Device missing or not an actuator → **404**, no row.
2. `command_for(type)`: unknown type or invalid payload → **400**, no row.
3. **Guard:** if the type is not in `ActuatorContext.allowed_commands()` for the saved
   state → `command_log` **rejected** → **409** with the row. No `apply`, no state change.
4. `CommandInvoker.run(command, port)` through the decorated port. A policy or adapter
   error → **failed** → **200** with the row; `actuator_states` unchanged, and the
   decorator has already written its own `actuator_execution_log` row.
5. After a completed apply: `ActuatorContext.transition(target_state)` and save, only
   when the target differs from the current state (`set_light_level` on a running
   light does not transition).
6. `command_log` **success** → **200** with the row.

`GET /api/commands?limit=50` (1–200) lists the history newest first.

## Rejected vs failed vs success

- **rejected** — not legal in the current state, so never attempted (stop on an idle
  pump; `set_light_level` on a pump).
- **failed** — legal and attempted, but a policy or the adapter stopped it (stop on a
  pump that has been running for 30 minutes: `Max run time exceeded`).
- **success** — attempted and completed; the lifecycle moved if needed.

## Decisions

- **`set_light_level` added to `allowed_commands`** for grow lights in `idle` and
  `running` (`EXTRA_COMMANDS` in `domain/actuators/context.py`), so the State guard
  can approve it. Device-specific extras live next to the device-specific command
  names; the shared state classes stay generic.
- **The guard and the transition use the same `ActuatorContext`**, so a command that
  passes the guard always has a legal transition to its target.
- **Two logs.** `command_log` records operator intent and its outcome, including
  requests that never reached the actuator. `actuator_execution_log` (Phase 9) records
  what reached the port and which policies acted. A blocked max-run-time command
  appears in both; a rejected one only in `command_log`.
- **The Phase 9 demo route was removed.** `POST /api/actuators/{device_id}/apply`
  called the port without a command; all actuator actions now go through
  `POST /api/commands`.
- **Rows are committed immediately** (`CommandLogRepository.add`), so `rejected` and
  `failed` rows are kept even though nothing else changes.
- **409 carries the row.** A rejected command is an outcome, not a malformed request,
  so the 409 body has the same shape as the 200.

## Command object vs calling the port from the router

| Router calls the port | Command + invoker |
|---|---|
| Each route repeats guard, apply, state update and logging | one service path for every command |
| No record of rejected requests | every attempt is a `command_log` row |
| Easy to skip the State guard or the decorators | commands always run through `build_actuator_port` after the guard |
| A request exists only while the call runs | a request is an object: it can be stored, listed, queued, undone |

## Frontend

`CommandPanel` in `#controls` shows Start/Stop for pumps and Set level (default 1)
for lights. A button is enabled only when its name is in the device's
`allowed_commands`. After every click it reloads the actuators and the history. The
backend still guards, so a stale page produces a `rejected` row, not a state change.

## Where in code

- `backend/src/domain/commands/` — `base.py`, `pump.py`, `light.py`, `invoker.py`, `errors.py`
- `backend/src/domain/actuators/context.py` — `EXTRA_COMMANDS`
- `backend/src/application/commands/` — `service.py`, `composition.py`, `dto.py`
- `backend/src/infrastructure/persistence/command_log_repository.py`, `models.py` (`CommandLogRow`)
- `backend/src/interfaces/api/commands.py` — `POST /api/commands`, `GET /api/commands`
- `frontend/src/components/commands/CommandPanel.tsx`
- `backend/tests/test_commands.py`, `test_command_service.py`, `test_commands_api.py`

## Exercise: add a command

Add `lights_off` (target `idle`), which `allowed_commands` already offers for a
running light:

1. Write `LightsOffCommand(Command)` with `command_type = "lights_off"`,
   `target_state = "idle"`, and `execute` calling `port.apply(...)`.
2. Add it to the tuple that builds `_REGISTRY`.
3. Add a button for `lights_off` in `CONTROLS` in `CommandPanel.tsx`.
4. Add tests.

No change to the invoker, the service, the router or the tables.