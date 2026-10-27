## A. Pattern

1. State the intent of Facade in plain language. What problem appears when every HTTP handler (or every UI screen) repeats the same multi-step dance across repositories and services?

> [!NOTE]
> ***Your Answer***
>
> Facade gives one simple entry point to a set of subsystems, so callers ask for what they want instead of coordinating every part themselves. In my app, `LocationOverviewFacade.get_overview(location_id)` is that entry point: one call returns the whole location overview.
>
> Without it, every handler or screen that needs the snapshot has to repeat the same sequence: load the location and zones, find the assigned devices, fetch their newest readings, read the saved strategy, and run evaluate only when a key exists. That logic gets duplicated, and the copies drift apart: one screen counts unassigned devices, another forgets empty zones, and a bug fixed in one place stays in the others. Every caller also becomes coupled to every subsystem, so a change in any repository ripples into all of them, and a UI that does the dance itself needs several network round trips.

2. A facade orchestrates collaborators. What should it not become (a god object that owns all domain logic)? Where should irrigation policy, sensor translation, and persistence stay instead?

> [!NOTE]
> ***Your Answer***
>
> A facade should not become a god object that owns business rules, writes SQL, or grows a method for everything the app does. My facade only **fetches, groups and maps**. It contains no irrigation rule, no sensor-format handling and no queries of its own.
>
> - **Irrigation policy** stays in the Phase 6 strategies. The facade calls `AutomationService.evaluate`, which calls `decide`; it never reimplements the decision.
> - **Sensor translation** stays in the Phase 5 adapters and `ReadingIngest`. The facade only reads readings that are already normalized in `sensor_readings`.
> - **Persistence and queries** stay in the repositories (`get_location`, `list_assigned_in_location`, `latest_by_device`, `AutomationRuleRepository`).
>
> If I ever found myself writing `if moisture < ...` inside the facade, that would be a sign the logic belongs in a strategy instead.

3. When should you use Facade, and when should you skip it (a single repository call is enough; or you actually need to translate a mismatched interface)?

> [!NOTE]
> ***Your Answer***
>
> I would use Facade when a client needs one coordinated result from several subsystems, when the same multi-step sequence would otherwise be repeated in several places, or when I want to protect clients from changes inside the subsystems. The overview fits all three.
>
> I would skip it when a single repository or service call is enough, because a facade around one call is just an extra pass-through layer. I would also skip it when the real problem is a mismatched interface, e.g. a vendor SDK returning a different format; that's Adapter, not Facade. A facade also shouldn't become the only way into the system: my Automation panel still talks to the automation endpoints directly, because saving a strategy is a single, focused operation.

## B. This phase of the application

4. What does `GET /api/locations/{location_id}/overview` return? Name the main pieces of the overview DTO: location, assigned device counts, and `zones` (thresholds, assigned devices, and those devices’ latest readings, including `tracking_enabled` and `sampling_interval_seconds`), plus strategy key and last recommendation. Why may those reading rows come from the sampler or MQTT ingest, not only from `POST /read`? Why is overview scoped by `location_id`?

> [!NOTE]
> ***Your Answer***
>
> It returns one `LocationOverviewDto`:
>
> - **`location`**: `{ id, name }`.
> - **`device_counts`**: `{ sensor, actuator }`, counting only assigned devices (this `location_id` and a non-null `zone_id`).
> - **`zones`**: every zone of the location, including empty ones. Each has `id`, `name`, `moisture_threshold_low`, `moisture_threshold_high`, its assigned `devices` (`id`, `device_type`, `role`, `display_name`), and `latest_readings`: one newest row per device that has one (`device_id`, `value`, `unit`, `recorded_at`, `tracking_enabled`, `sampling_interval_seconds`). The last two are copied from the device, not stored on `sensor_readings`.
> - **`strategy_key`**: the saved key, or `null`.
> - **`last_recommendation`**: `{ action, reason }` computed by evaluate on this request, or `null` when no key is saved (still HTTP 200).
>
> The readings can come from any source because Phase 5 has one ingest path: manual reads, the simulation sampler and translated MQTT payloads all end up in the same `sensor_readings` table. "Latest" means newest by `recorded_at`, whatever produced it. Filtering to `POST /read` would hide most real data. In my Bay C test, the sensor's reading came from that shared table, and the overview didn't care how it got there.
>
> It is scoped by `location_id` because the location is the unit the operator manages: zones, thresholds and the saved strategy (one row per location in `automation_rules`) all belong to a location. Using `location_id` everywhere also keeps the naming consistent across phases, with no `greenhouse_id`.

5. Why does this phase not require a new business table? What already exists from Phases 2–6 that the facade only composes?

> [!NOTE]
> ***Your Answer***
>
> The overview is a **read model**: a new view of data that is already stored, not new data. Everything it shows is already persisted:
>
> - `devices` with roles and families (Phases 2–3), zone and location assignment (Phase 4), and sampling settings (Phase 5)
> - `locations` and `zones` with thresholds (Phase 4)
> - `sensor_readings` (Phase 5)
> - `automation_rules` with the saved strategy key (Phase 6)
>
> The recommendation is computed by evaluate on every request, so it doesn't need storing either. A new table would duplicate this data, would have to be kept in sync on every write, and could show stale values. The optional SQL view wasn't needed; the existing tables are enough.

6. The overview HTTP handler should call only the facade, not reading/strategy/device repositories directly. Why? How does that help tests and later changes to the query shape?

> [!NOTE]
> ***Your Answer***
>
> The handler's job is HTTP: take the path parameter, call one method, return the DTO, and map `LocationNotFoundError` to 404. If it also called the repositories, the assembly logic would live in the interface layer, and any other caller (a test, a CLI, a later phase) would have to copy it. In my `overview.py`, the imports show the rule directly: the facade, its DTO, one error and the session dependency, with no repositories and no `AutomationService`. The wiring lives in `build_location_overview_facade(db)`, in one place.
>
> For tests, the facade takes its collaborators through the constructor, so it can be tested with fakes, and my integration test can exercise the whole thing through one route. For later changes, I can change the query shape behind the facade (for example, switch to a SQL view, combine queries, add caching, or include actuator state in Phase 8) without touching the router or the frontend, as long as the DTO stays the same.

7. The location selector may use the existing locations list. The Overview cards come from one overview fetch, and Refresh repeats that same fetch. Why must the React page not stitch device, reading, and automation calls together to build the same snapshot? How does a new reading or a saved strategy show up on overview without extra frontend glue?

> [!NOTE]
> ***Your Answer***
>
> If React stitched several responses together, the assembly rules (what counts as assigned, grouping by zone, evaluating only when a key exists) would be duplicated in the browser, and every future client would have to reimplement them. It would need several round trips, and the responses would come from slightly different moments, so the snapshot might not be consistent. The page would also be coupled to every subsystem's endpoints. In my `OverviewPanel`, the only data call for the cards is `getLocationOverview(locationId)`, used both when a location is selected and on Refresh. The browser's Network tab shows exactly one request per refresh. Inside a zone card I pair devices with their readings using a `Map`, but those come from the same response, so that's rendering, not stitching.
>
> A new reading or a saved strategy reaches the overview without any frontend glue because nothing is cached. The reading is written to `sensor_readings` by the existing ingest path, and the strategy is written to `automation_rules` by the Automation panel. The next overview GET queries the tables again and runs evaluate again, so pressing Refresh shows the new state.

## C. Compare, contrast, and scenarios

8. Contrast Facade with Adapter. One makes an existing interface usable; the other makes a subsystem simpler to call. Which is which, and how do both appear in this greenhouse app (Phase 5 vs Phase 7)?

> [!NOTE]
> ***Your Answer***
>
> **Adapter makes an existing interface usable.** It converts one interface into the one the client expects. In Phase 5, `MqttSensorAdapter` and `VendorStubSensorAdapter` translate foreign payload formats into the common `Reading` behind `SensorPort`. It wraps one thing and keeps the same behaviour; only the interface changes.
>
> **Facade makes a subsystem simpler to call.** It puts a new, simpler interface in front of several of my own components. In Phase 7, `LocationOverviewFacade` combines locations, devices, readings and automation behind one `get_overview` method. It's one-to-many, and the interface is new, designed for what the dashboard needs.
>
> The two phases also meet: the readings the facade shows were translated by the Phase 5 adapters before they were stored.

9. This phase mentions N+1 queries. What is an N+1 problem in an overview that lists latest readings for many devices, and what can the facade (or its repository) do about it without putting SQL in the router?

> [!NOTE]
> ***Your Answer***
>
> An N+1 problem is one query to get a list of N items, followed by one more query for each item in a loop: here, one query for the devices and then one "latest reading" query per device. With 50 devices that's 51 round trips, and the overview gets slower as the greenhouse grows.
>
> The fix belongs in the repository. I added `ReadingRepository.latest_by_device(device_ids)`, which gets the newest reading for **all** assigned devices in one query, using Postgres `DISTINCT ON (device_id) ... ORDER BY device_id, recorded_at DESC` with an `IN` filter. The existing `(device_id, recorded_at DESC)` index supports it. In the same way, `DeviceRepository.list_assigned_in_location` loads all assigned devices in one query, instead of calling `list_devices_in_zone` once per zone. The facade just calls these methods, and the router contains no SQL at all.
>
> One known exception remains: `evaluate` still looks up moisture once per zone inside the automation service. Zones are few, so I accepted and documented it, instead of reimplementing `decide` in the facade. If it ever mattered, it could be optimized inside the automation repository without changing the facade.

10. A classmate hides every error behind a generic “overview failed,” so a missing location, a DB outage, and a strategy error look the same. Why is that a trap for a facade?

> [!NOTE]
> ***Your Answer***
>
> A facade should hide *complexity*, not *failures*. Because it sits on top of several subsystems, it has more possible failure sources than any single repository, and a generic message hides which one failed. The cases need different reactions:
>
> - **Missing location**: a client error (404), so the user should pick another location.
> - **Database outage**: a server error (500/503), so retry later and alert someone.
> - **Strategy error**: a configuration problem in the automation subsystem that needs fixing there.
>
> With one generic message, the API breaks its own documented contract (Scalar documents 404 for a missing location), the frontend can't show a useful message, tests can't check that the right error happens, and debugging gets much harder because the real cause disappears. In my facade, `LocationNotFoundError` propagates as a typed error and the router maps it to 404. "No strategy saved" isn't treated as an error at all; it returns 200 with null fields. Unexpected errors are not swallowed: they surface as a 500 with the traceback in the logs.