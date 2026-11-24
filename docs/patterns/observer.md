# Observer pattern — event bus and alerts (Phase 11)

## Problem

Several things must happen *because* something else happened: a low moisture
reading, a failed command or an actuator entering `error` should each create an
alert, and in Phase 12 the same moments must reach the browser live. If the code
where the action happens called the alert code directly, ingest, commands and the
state service would all depend on alerts, and every new reaction would mean editing
every action.

## Solution

The code where something happens publishes a **domain event** to an in-process
`EventBus`. Interested parts subscribe to the event classes they care about. A
publisher never knows who listens; a new reaction is one new subscriber.

| Role | Class |
|---|---|
| Subject | `EventBus` (`domain/events/bus.py`): `subscribe(event_class, handler)`, `publish(event)` |
| Events | `ReadingCreated`, `ThresholdCrossed`, `CommandFailed`, `ActuatorStateChanged`, `AlertCreated` (`domain/events/events.py`) |
| Publishers | `ReadingIngest`, `CommandService`, `ActuatorStateService` (the transition service) |
| Concrete observers | `MoistureThresholdSubscriber`, `AlertPersistenceSubscriber` (`application/alerts/subscribers.py`) |

```text
ReadingIngest ───────┐                              ┌─► MoistureThresholdSubscriber ─► publishes ThresholdCrossed
CommandService ──────┼─ publish ─► EventBus ────────┤
ActuatorStateService ┘                              └─► AlertPersistenceSubscriber ─► alerts row ─► publishes AlertCreated
```

## Who publishes what

- **`ReadingIngest.record`** — after every stored reading, `ReadingCreated`
  (`device_id`, `value`, `unit`, `source`, `recorded_at`, `location_id`, `zone_id`),
  **only when the device's `tracking_enabled` is true**. The reading is stored either
  way. Manual read, the simulation sampler and translated MQTT payloads all pass
  through `record`, so they share one publish rule.
- **`CommandService`** — `CommandFailed` after a `failed` command (the message is the
  exception text, e.g. `Max run time exceeded`), and `ActuatorStateChanged` after it
  saves a new state. A rejected command publishes nothing.
- **`ActuatorStateService.transition`** — `ActuatorStateChanged` after every
  successful state save.
- **`MoistureThresholdSubscriber`** — `ThresholdCrossed` when the unit is `vwc`, a zone
  is set, and the value is strictly below that zone's `moisture_threshold_low`.
- **`AlertPersistenceSubscriber`** — `AlertCreated` after each insert, for Phase 12.

`location_id` and `zone_id` are copied from the device at publish time. Both are
`null` for an unassigned device; no zone is ever invented.

## Stored alerts

| `event_type` | `severity` | `message` | When |
|---|---|---|---|
| `threshold.crossed` | warning | `Moisture below zone low` | every `ThresholdCrossed` |
| `command.failed` | warning | the failure message | every `CommandFailed` |
| `state.changed` | critical | `Actuator entered error` | `ActuatorStateChanged` with `state == "error"` only |

Alerts are rows in `alerts` (foreign keys nullable, `ON DELETE SET NULL`), so the
event feed survives a refresh. `GET /api/alerts` lists them newest first: default
`status=active` and `limit=50` (1–200), `status` in `active`/`resolved`/`all` (other
values 400), optional `location_id`, `zone_id` and `since`.

## Decisions

- **One bus per process.** `get_event_bus()` (`application/events/composition.py`,
  cached with `lru_cache`) builds it once and subscribes the handlers in a fixed order.
  Requests and the background sampler get the same bus; Phase 12's socket will too.
- **Subscribers open their own session.** The bus outlives any request, so the two
  subscribers receive a session factory (`SessionLocal`) and use a fresh session per
  event. Alerts are committed independently of the request or sampler tick.
- **Publish after commit.** An event says "this happened", so publishers publish only
  once their own data is stored.
- **A failing subscriber is isolated.** `EventBus.publish` calls each handler in
  `try/except` and logs errors, so one broken handler can't stop later handlers (e.g.
  Phase 12's socket) or the publisher. The trade-off: a broken handler only shows up in
  the logs.
- **Events are routed by class**, not by `if event_type == ...`; each event class also
  carries its dotted `event_type` string, which is what `alerts.event_type` stores.
- **Publishers don't import `AlertRepository`** (checked by a test). Only
  `AlertPersistenceSubscriber` writes alerts.

## Observer vs Phase 12 WebSocket

This phase is in-process and synchronous: the feed **polls** `GET /api/alerts` every
5 seconds, and `services/realtime.ts` is a stub whose `subscribeRealtime` returns a
no-op unsubscribe. Phase 12 does not build a second pub/sub. It subscribes a dashboard
WebSocket to this same bus (to `AlertCreated`, already published) and fills in
`realtime.ts`. The event feed already calls `subscribeRealtime`, so it won't change.

## Observer vs Facade vs Command

- **Facade** (Phase 7): one caller *pulls* a combined view from many subsystems.
  Observer *pushes* one event to many listeners.
- **Command** (Phase 10): captures an *intent to act*. Observer spreads the *outcome*:
  `CommandService` publishes `CommandFailed` after a failed command without knowing
  that alerts exist.

## Where in code

- `backend/src/domain/events/` — `events.py`, `bus.py`
- `backend/src/application/alerts/` — `subscribers.py`, `service.py`, `dto.py`
- `backend/src/application/events/composition.py` — `build_event_bus`, `get_event_bus`
- Publishers: `application/readings/service.py`, `application/commands/service.py`,
  `application/devices/actuator_state_service.py`
- `backend/src/infrastructure/persistence/alert_repository.py`, `models.py` (`AlertRow`)
- `backend/src/interfaces/api/alerts.py` — `GET /api/alerts`
- `frontend/src/components/alerts/EventFeed.tsx` (`#events`),
  `frontend/src/services/realtime.ts`
- `backend/tests/test_event_bus.py`, `test_alerts_api.py`

## Exercise: add a subscriber

A `MetricsSubscriber` that counts events per type in memory:

1. Write a class with `on_event(self, event)` that increments
   `self.counts[event.event_type]`.
2. Subscribe it in `build_event_bus` to the event classes it should count.
3. Test it by publishing events on a fresh bus.

No publisher changes, and no table.