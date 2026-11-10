# Decorator pattern — actuator policies and execution log (Phase 9)

## Problem

Sending a command to an actuator needs extra behaviour around it: every attempt
must be recorded, and an actuator that has been running too long must refuse
further commands. Adding that inside `SimulationActuatorAdapter` mixes policies
into the adapter; doing it with inheritance (`LoggingActuator`,
`MaxRunTimeActuator`, `LoggingMaxRunTimeActuator`, …) needs a new subclass for
every combination, and the number grows with each new policy.

## Solution

Each policy is a small class that implements the same `ActuatorPort` as the
adapter and holds the component it wraps (`inner`). It does its own work and
then forwards the call, or refuses it. Because every layer is an
`ActuatorPort`, layers can be stacked, and the caller cannot tell how many there
are.

```text
caller ──► LoggingActuatorDecorator ──► MaxRunTimeActuatorDecorator ──► SimulationActuatorAdapter
           ActuatorPort.apply(device_id, command, payload) -> AppliedCommand   (every layer)
```

| Role | Class |
|---|---|
| Component | `ActuatorPort` (`domain/actuators/ports.py`) |
| Concrete component | `SimulationActuatorAdapter` (Phase 5), innermost |
| Decorators | `LoggingActuatorDecorator`, `MaxRunTimeActuatorDecorator` |

## The policies

- **Max run time** — if the actuator's persisted state is `running` and
  `actuator_states.updated_at` is at least 30 minutes before the clock, it raises
  `PolicyViolationError("maxRunTime", "Max run time exceeded")` and **does not call
  the inner component**. It reads state through an injected lookup
  (`ActuatorStateRepository.get_state_since`), so it reuses Phase 8's lifecycle
  instead of inventing its own. An actuator with no state row is never blocked.
- **Logging** — calls the inner component and writes exactly one row to
  `actuator_execution_log` per call, then returns the result or re-raises:

| Outcome | `success` | `policy_applied` | `message` |
|---|---|---|---|
| completed | `true` | `["logging"]` | `null` |
| blocked by max run time | `false` | `["maxRunTime", "logging"]` | `Max run time exceeded` |
| unexpected adapter error | `false` | `["logging"]` | the error text |

The command string is not validated in this phase: an unknown command succeeds
unless max run time blocks it. Phase 10 consults `allowed_commands`.

## Order

Composition order is **logging → max-run-time → simulation adapter**, wired in one
place, `build_actuator_port(db)` in `application/actuators/composition.py`.

Logging must be outermost so it observes every attempt, including blocked ones.
With the order reversed, max run time would raise before the call reached
logging, and a blocked attempt would leave no row
(`test_wrong_order_loses_the_blocked_attempt` demonstrates this).

## Decisions

- **Return type.** The requirements write `apply(...) -> None`; Phase 5's port
  already returned `AppliedCommand`, and its tests use the result. I kept
  `AppliedCommand`. Every decorator keeps the exact signature and forwards the
  inner result unchanged, which is what the pattern requires.
- **Failure is an exception.** A policy signals "no" with `PolicyViolationError`
  carrying the policy name; logging records it and re-raises, and the router maps
  it to HTTP 409. The router contains no policy checks.
- **The failed row survives the failed request.** `ExecutionLogRepository.add`
  commits immediately, so the row written for a blocked attempt is kept even
  though the request ends with an error.
- **Only real attempts are logged.** The service checks that the device exists and
  is an actuator before entering the chain (404 / 400), so those cases write no row.
- **Known limitation.** Max run time blocks *every* command once the limit is hit,
  including `stop_pump`. That is the literal requirement; a real system would let
  stop commands through, which Phase 10 can refine with the state guards.

## Decorator vs inheritance

| | Inheritance | Decorator (composition) |
|---|---|---|
| Combining policies | a subclass per combination | stack wrappers at runtime |
| Adding a policy | new subclasses for each mix | one new class, one line in the composition root |
| Removing a policy | edit a class hierarchy | delete one wrapper line |
| Order | fixed in the class | chosen when composing |

## Decorator vs Adapter

Adapter (Phase 5) **changes** an interface: it translates a vendor or MQTT format
into `Reading`. Decorator **keeps** the interface and **adds** behaviour around
it. Both hold a wrapped object; the difference is whether the interface changes.

## Where in code

- `backend/src/domain/actuators/ports.py` — `ActuatorPort`, `AppliedCommand`
- `backend/src/domain/actuators/errors.py` — `PolicyViolationError`
- `backend/src/infrastructure/adapters/actuators/` — `simulation.py`,
  `logging_decorator.py`, `max_runtime_decorator.py`
- `backend/src/infrastructure/persistence/execution_log_repository.py`,
  `models.py` (`ActuatorExecutionLogRow`)
- `backend/src/application/actuators/` — `composition.py`, `service.py`, `dto.py`
- `backend/src/interfaces/api/actuators.py` —
  `GET /api/actuators/executions?limit=20`, demo `POST /api/actuators/{device_id}/apply`
- `frontend/src/features/actuators/ExecutionLog.tsx` (`#executions`)
- `backend/tests/test_actuator_decorators.py`, `test_actuator_executions_api.py`

## Exercise: add a policy

A `QuietHoursActuatorDecorator` that blocks commands between 22:00 and 06:00:

1. Implement `ActuatorPort.apply`; raise `PolicyViolationError("quietHours", ...)`
   inside the window, otherwise forward to `inner`.
2. Wrap it in `build_actuator_port`, inside logging (so blocked attempts are logged).
3. Add unit tests with a fixed clock.

The service, router, table and UI need no change: the new policy name simply
appears in `policy_applied`.