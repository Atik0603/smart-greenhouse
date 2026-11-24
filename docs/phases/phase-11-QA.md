## A. Pattern

1. State the intent of Observer in plain language. What is a **one-to-many** dependency here, and why must the subject notify dependents **without** knowing their concrete classes?

> [!NOTE]
> **_Your Answer_**
>
> Observer lets one part of a program announce that something happened, and any number of other parts react to it, without the announcer knowing who they are. In a game, when an enemy dies, the combat code announces it, and the achievement tracker, score display and quest log each react in their own way; the combat code never imports any of them.
>
> The **one-to-many** dependency here is one event and many interested listeners. When a tracked moisture reading is stored, `ReadingCreated` goes to the threshold subscriber today, and in Phase 12 also to the dashboard WebSocket. One `CommandFailed` or `ActuatorStateChanged` can likewise have several listeners.
>
> The subject (my `EventBus`) must not know the concrete classes, because then every new reaction would mean changing the code that announces. `ReadingIngest` would have to import the alert writer, then the socket, then whatever comes next, and it would grow with every feature. Because publishers only call `bus.publish(event)`, I can add, remove or reorder listeners in one place (`build_event_bus`) without touching ingest, commands or the state service.

2. Name the participants (**subject / event bus**, **observer / subscriber**, **concrete observers**, **event**, **publisher**). What does `subscribe` / `unsubscribe` / `publish` (or `notify`) each do? This example’s `EventBus` implements `subscribe` and `publish` only.

> [!NOTE]
> **_Your Answer_**
>
> - **Subject / event bus:** `EventBus`, which keeps a list of handlers per event class.
> - **Observer / subscriber:** any handler, a function that takes an event.
> - **Concrete observers:** `MoistureThresholdSubscriber` (handles `ReadingCreated`) and `AlertPersistenceSubscriber` (handles `ThresholdCrossed`, `CommandFailed` and `ActuatorStateChanged`).
> - **Events:** frozen dataclasses describing something that already happened: `ReadingCreated`, `ThresholdCrossed`, `CommandFailed`, `ActuatorStateChanged`, and `AlertCreated` for Phase 12.
> - **Publishers:** the code where things happen: `ReadingIngest`, `CommandService` and `ActuatorStateService` (my transition service). The threshold subscriber is also a publisher, since it publishes `ThresholdCrossed`.
>
> `subscribe(event_class, handler)` registers a handler for one event class, appended to that class's list. `publish(event)` looks up the handlers for `type(event)` and calls each one in subscription order. `unsubscribe` would remove a handler; my bus doesn't have it, because subscriptions are set up once when the app starts and last as long as the process.

3. When should you use Observer, and when should you skip it (only one listener forever; or you need a strict multi-step workflow with guaranteed order)?

> [!NOTE]
> **_Your Answer_**
>
> I'd use Observer when several independent parts need to react to the same thing, when new reactions are expected later, and when the part that acts shouldn't depend on the parts that react. All three hold here: alerts now, the WebSocket in Phase 12, maybe metrics later.
>
> I'd skip it when there will only ever be one listener, because a direct method call is simpler, easier to read and easier to debug than routing through a bus. I'd also skip it for a strict multi-step workflow where each step depends on the previous one and order and success are guaranteed, such as my command path: guard, then execute, then save state, then log. If those were separate subscribers, a failing step would just be logged and skipped (my bus isolates failures), and the workflow would silently continue in a broken state. That's why the command flow stays a normal sequence of calls inside `CommandService`, and only its *outcomes* are published.

## B. This phase of the application

4. Give at least two **domain events** you publish in this lab, including `reading.created` (only when `tracking_enabled` is true), a threshold-crossed event, command-failed, and `ActuatorStateChanged`. The persistence subscriber stores `state.changed` only when that state is `error`. Who publishes `reading.created`, and why do a manual read, the simulation sampler, and MQTT translation share that one ingest publish? Why must a publisher **not** import the alerts repository or the UI?

> [!NOTE]
> **_Your Answer_**
>
> I publish four domain events (plus `AlertCreated` for Phase 12):
>
> - **`ReadingCreated`** (`reading.created`) from `ReadingIngest.record`, after a reading is stored, **only if the device's `tracking_enabled` is true**. It carries `device_id`, `value`, `unit`, `source`, `recorded_at`, and the device's `location_id` and `zone_id`.
> - **`ThresholdCrossed`** (`threshold.crossed`) from `MoistureThresholdSubscriber`, when a `vwc` reading in a zone is strictly below the zone's low threshold.
> - **`CommandFailed`** (`command.failed`) from `CommandService`, when an accepted command fails, e.g. "Max run time exceeded".
> - **`ActuatorStateChanged`** (`state.changed`) after every successful state save, from both `CommandService` and the transition service. Only the `error` state becomes an alert.
>
> `ReadingIngest.record` publishes `reading.created`. Manual reads, the sampler and translated MQTT payloads share it because `record` is the single writer of `sensor_readings`: all three already pass through it, so putting the publish there gives one rule for every source. With separate publish code per source, they could easily drift apart, for example the sampler forgetting the tracking check (one of the listed pitfalls).
>
> Publishers must not import the alerts repository or the UI because their job ends at "this happened." If `ReadingIngest` wrote alerts itself, ingest would depend on the alerts table, and any change to alerting would mean editing ingest. Adding the Phase 12 socket would then mean editing it again. A test in my suite reads the three publisher files and fails if `AlertRepository` appears in them.

5. What does `AlertPersistenceSubscriber` (or your equivalent) do when it handles an event? Name the three stored rows: `threshold.crossed` / `warning` / `Moisture below zone low`, `command.failed` / `warning` / the failure message, and `state.changed` / `critical` / `Actuator entered error`. Why do alerts live in the `alerts` table so the event feed still shows them after a **refresh**?

> [!NOTE]
> **_Your Answer_**
>
> It turns an event into one active row in `alerts`. It opens a fresh database session, inserts the row with the event's `device_id`, `location_id` and `zone_id` (null for unassigned devices), commits, and then publishes `AlertCreated` so Phase 12's socket can push it. It's the only code that writes alerts.
>
> The three stored rows:
>
> | `event_type` | `severity` | `message` |
> |---|---|---|
> | `threshold.crossed` | warning | Moisture below zone low |
> | `command.failed` | warning | the failure message, e.g. Max run time exceeded |
> | `state.changed` | critical | Actuator entered error (only when the new state is `error`) |
>
> Alerts live in the table because events themselves are momentary: they exist only while `publish` runs. If alerts were only kept in React state, or only pushed to the browser, a page refresh, a second browser or a backend restart would lose them, and an operator who wasn't looking at the moment would never see them. With rows in `alerts`, the feed asks `GET /api/alerts`, and refreshing the page shows exactly the same list. It also lets Phase 13 resolve alerts later.

6. The dashboard Event feed **polls** `GET /api/alerts` every 5 seconds in this phase. `services/realtime.ts` is only a **stub**. Why is full WebSocket **not** required in this phase? What should Phase 12 plug into so you do **not** re-implement pub/sub inside socket handlers? Phase 12 subscribes a dashboard socket to this same bus, and the example publishes `AlertCreated` after each insert for that socket.

> [!NOTE]
> **_Your Answer_**
>
> This phase is about the Observer pattern inside the backend: publishers, the bus and subscribers, with alerts stored in the database. Polling every 5 seconds is enough to prove the whole path works end to end (reading → event → subscriber → row → API → feed). A WebSocket only changes how quickly the browser hears about it, and it's a separate concern with its own problems (connections, reconnects, hardening), which is what Phase 12 is for.
>
> Phase 12 should plug into the **same `EventBus`**, not build a second pub/sub. Its dashboard socket handler subscribes to `AlertCreated` (and possibly `ReadingCreated` and `ActuatorStateChanged`) through `get_event_bus()` and forwards each event to the connected browsers. `AlertCreated` is already published after every insert, so nothing on the publisher side has to change. On the frontend, `subscribeRealtime` in `realtime.ts` already has the final shape, and my `EventFeed` already calls it and cleans up with the returned unsubscribe function. Phase 12 fills in the body, and the feed can reload as soon as an event arrives instead of waiting for the next poll.

7. Describe the must-demo path: a **tracked** low-moisture reading leads to an alert row that appears in the feed after poll. Which objects collaborate (reading pipeline → bus → subscriber → API → UI), and which object must **not** write the alert directly? What is stored, and what is not published, when `tracking_enabled` is false?

> [!NOTE]
> **_Your Answer_**
>
> 1. A reading for a moisture sensor assigned to a zone arrives through `ReadingIngest.record`, whether from a manual read, the sampler or MQTT. The reading is stored in `sensor_readings`.
> 2. The device is tracked, so `ReadingIngest` publishes `ReadingCreated` with the value and the device's `location_id` and `zone_id`.
> 3. The **bus** calls `MoistureThresholdSubscriber.on_reading`. The unit is `vwc`, the zone is set, and the value (e.g. 0.10) is strictly below the zone's low (0.20), so it publishes `ThresholdCrossed`.
> 4. The bus calls `AlertPersistenceSubscriber.on_threshold`, which inserts a `threshold.crossed` / warning / "Moisture below zone low" row with that zone and location, and publishes `AlertCreated`.
> 5. `GET /api/alerts` returns the row, newest first, and it can be filtered by that `zone_id`.
> 6. The **`EventFeed`** in `#events` polls every 5 seconds and shows it with an amber WARNING badge.
>
> `ReadingIngest` must **not** write the alert itself, and neither may the sensor router or any adapter. They only publish. Only `AlertPersistenceSubscriber` writes alerts.
>
> When `tracking_enabled` is false, the reading **is still stored** in `sensor_readings`, but `ReadingCreated` is **not published**, so no threshold check runs and no alert is created. I tested both cases: same value, tracking on gives one alert, and tracking off gives a stored reading and no alert.

## C. Compare, contrast, and scenarios

8. Contrast Observer with **Facade**. Facade simplifies **calling into** a subsystem. Observer **fans out** notifications after something happened. How do both appear in this greenhouse (Phase 7 overview vs this phase)?

> [!NOTE]
> **_Your Answer_**
>
> They work in opposite directions. **Facade** is about asking: one caller wants a combined answer from many subsystems and calls one simple method. **Observer** is about telling: one part reports that something happened, and many listeners react, without the reporter knowing them.
>
> In my greenhouse, the Phase 7 **facade** is `LocationOverviewFacade.get_overview(location_id)`. The dashboard calls it once, and it pulls the location, zones, assigned devices, latest readings and the strategy recommendation from their subsystems into one DTO. The call is synchronous, has one caller, and returns an answer.
>
> In Phase 11, **Observer** is the `EventBus`. `ReadingIngest`, `CommandService` and the transition service push events out, and the threshold and alert subscribers react. Nobody waits for an answer, and the publisher doesn't know how many listeners there are. The two even meet in the dashboard: the overview *pulls* the current snapshot, while the event feed shows the *results* of events that were pushed through the bus and stored as alerts.

9. Contrast Observer with **Command**. Command captures **intent to act**. Observer propagates **outcomes**. How can `execute()` publish an event without the command class knowing who persists alerts?

> [!NOTE]
> **_Your Answer_**
>
> A **command** is a request that something *should* happen: `StartPumpCommand` says "start this pump," goes through the state guard and the decorated port, and is recorded in `command_log`. An **event** is a fact that something *did* happen: `CommandFailed` says "this command failed with this message."
>
> In my code, the command classes themselves don't publish anything. They only call `port.apply`. The publishing happens one level up, in `CommandService`, which already handles the outcome: when the invoker raises, it records the `failed` row and then calls `bus.publish(CommandFailed(...))`. After a completed command that changes state, it publishes `ActuatorStateChanged`. `CommandService` receives the bus through its constructor and only imports `EventBus` and the event classes, never `AlertRepository`. It knows *that* it should announce a failure, but not *who* listens. The alert row is written by `AlertPersistenceSubscriber`, and Phase 12's socket can listen to the same event without the command code changing. If a command class ever did need to publish, it would work the same way: receive the bus and publish an event, without knowing the subscribers.

10. One subscriber throws during `notify` / `publish` and aborts the loop, so later subscribers never run. Why is that a trap? What should the bus do so a failing alert writer does not block metrics (or later WebSocket) subscribers?

> [!NOTE]
> **_Your Answer_**
>
> It's a trap because subscribers are supposed to be independent, and the publisher doesn't even know they exist. If one subscriber's exception stopped the loop, a bug in the alert writer (say, a database error) would silently stop the metrics subscriber and the Phase 12 WebSocket from ever hearing about the event. Whether they run would depend on the order they happened to be subscribed in. Worse, the exception would travel back into the publisher: a sensor reading could fail to return, or a command request could error out, because of an alerting problem it has nothing to do with.
>
> My `EventBus.publish` calls each handler inside `try/except Exception`, logs the error with its traceback, and continues with the next handler. A failing alert writer is then visible in the logs, but metrics and the socket still receive the event, and the publisher continues normally (the reading stays stored and the command response is still returned). I tested it: the first handler raises a `ZeroDivisionError`, and the second still receives the event. The trade-off is that a broken subscriber doesn't make anything visibly fail, so its own behaviour (here, the rows it writes) has to be tested directly.