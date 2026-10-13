# Strategy pattern — irrigation automation (Phase 6)

## Problem

Deciding whether a zone needs water has no single right answer. A cautious
grower waters only when soil is dry; another keeps it consistently moist.
Writing those policies as `if key == "conservative": ... elif ...` inside the
API handler would mix HTTP, database access and irrigation logic, and every new
policy would mean editing that handler.

## Solution

Each policy is its own class behind one interface. The service picks the object
by the location's **saved** key and calls `decide`; it never knows which
algorithm runs.

```text
AutomationStrategy (ABC)
    decide(context: LocationAutomationContext) -> Recommendation
        ├── ConservativeStrategy   key "conservative"
        └── AggressiveStrategy     key "aggressive"
```

- `LocationAutomationContext` — plain values for one zone: `location_id`,
  `zone_id`, latest `moisture`, zone `low`/`high`, optional `light`.
- `Recommendation` — `action` (`irrigate` | `wait`), `reason`, optional
  `score` (urgency 0–1).

## The two strategies

| Strategy | Irrigates when | Example (low 0.20, high 0.40, moisture 0.25) |
|---|---|---|
| conservative | moisture < low | wait — "0.25 is at or above the low threshold 0.20" |
| aggressive | moisture < (low + high) / 2 | irrigate — "0.25 is below the midpoint 0.30" |

They disagree whenever moisture is between `low` and the midpoint.

## Decisions

- **Storage:** dedicated `automation_rules` table (`location_id` UNIQUE,
  `strategy_key`, `parameters` JSONB, `updated_at`) rather than columns on
  `locations`, keeping automation separate from the Phase 4 location aggregate.
  Saving is an upsert (`INSERT ... ON CONFLICT (location_id) DO UPDATE`).
- **Valid keys live in code, not the database.** `strategy_key` has no CHECK
  constraint; the registry in `strategy.py` is the single list. Unknown keys are
  rejected by `get_strategy()` (HTTP 400) before anything is saved or `decide`
  runs.
- **Who chooses:** the user, per location, in the dashboard. A new location has
  no rule; evaluate then returns 409 instead of silently using a default, so
  every recommendation traces back to a saved choice.
- **Per zone:** one context per zone, built from that zone's thresholds and the
  latest reading among `moisture_sensor` devices with that `zone_id`. Readings
  may come from manual read, the sampler or MQTT ingest. Unassigned devices and
  other zones' sensors are never used.
- **Missing data is not a strategy:** a zone with no moisture sensor ("No
  moisture sensor in this zone") or no readings yet ("Moisture sensor has no
  readings yet") gets `wait` from the service, before any strategy runs.
- **Response:** the required `{ location_id, strategy_key, action, reason }`
  plus a `zones` list. Top-level `action` is `irrigate` if any zone irrigates.
- **No ORM in the domain:** repositories copy rows into `ZoneSnapshot`; the
  service builds `LocationAutomationContext`; strategies import no SQLAlchemy.

## Where in code

- `backend/src/domain/automation/` — `strategy.py` (interface, strategies,
  registry), `context.py`, `errors.py`
- `backend/src/infrastructure/persistence/automation_repository.py` —
  `AutomationRuleRepository` (get, upsert), `AutomationContextRepository`
  (zone snapshots, latest readings)
- `backend/src/application/automation/` — `dto.py`, `service.py`
  (`AutomationService`)
- `backend/src/interfaces/api/automation.py` —
  `GET /api/automation/strategies`, `GET|PUT /api/locations/{location_id}/automation`,
  `POST /api/locations/{location_id}/automation/evaluate`
- `frontend/src/features/automation/StrategyPanel.tsx` (mounted in `#automation`),
  calls in `frontend/src/services/api.ts`
- `backend/tests/test_automation_strategies.py`, `test_automation_service.py`

## Exercise: add a third strategy

Example: `LightAwareStrategy` (key `"light_aware"`) — behaves like aggressive,
but on bright readings (`light` above a threshold) waters only below `low`,
because evaporation is high and a bright midday soak wastes water.

1. In `strategy.py`, write `class LightAwareStrategy(AutomationStrategy)` with
   `key = "light_aware"` and a `decide(context)` that uses `context.light`
   (treat `None` as "not bright").
2. Add `LightAwareStrategy()` to the tuple that builds `_STRATEGIES`.
3. Add unit tests with fake contexts, including one where it disagrees with
   both existing strategies.

Nothing else changes: no migration (keys aren't constrained in the database), no
service or router change (they call `decide` polymorphically), and no frontend
change (the dropdown loads `GET /api/automation/strategies`). The context already
carries the zone's latest light reading.