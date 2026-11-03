## A. Pattern

1. State the intent of the State pattern in plain language. What problem appears when lifecycle is modelled as boolean flags and scattered `if` guards?

> [!NOTE]
> ***Your Answer***
>
> State lets an object change how it behaves depending on which lifecycle state it is in, by moving each state's rules into its own class. The object (the context) holds its current state object and delegates to it, so it appears to change behaviour when the state changes. In my lab, an actuator such as the pump relay is always in exactly one state (`off`, `idle`, `running`, `maintenance` or `error`), and each state class knows where it can go next and which commands lead there. It's like a washing machine: the same buttons do different things depending on whether it's idle, running or faulted.
>
> When lifecycle is modelled as boolean flags (`is_running`, `is_fault`) with scattered `if` guards, the rules end up spread across routers, services and the UI. Each place has to remember every combination, and one path always forgets a rule, e.g. powering off a pump in the middle of watering. The flags can also contradict each other (see question 9). Adding a new state means finding and editing every `if`. With State, a rule is written in one class, and a change touches one place.

2. Name the participants (context, state interface, concrete states, client). How does a successful command lead to a transition, and where do guards live?

> [!NOTE]
> ***Your Answer***
>
> - **Context:** `ActuatorContext`. It holds the current state object and delegates to it.
> - **State interface:** the abstract class `ActuatorState`, with `transitions()` returning each legal target state and the command that causes the move.
> - **Concrete states:** `OffState`, `IdleState`, `RunningState`, `MaintenanceState` and `ErrorState`.
> - **Client:** the code that triggers a change. In my lab, `ActuatorStateService`, called by `POST /api/devices/{id}/transition` (and in Phase 10, by the Command objects).
>
> A successful command leads to a transition like this: the service loads the stored state name from `actuator_states`, builds an `ActuatorContext` from it, and calls `context.transition(target)`. The context asks the current state object `can_move_to(target)`. If yes, it swaps to the target state object. Only after `transition` returns does the service save the new state to the database.
>
> The guards live in the domain: each state object's `transitions()` table says what is legal, and `ActuatorContext.transition` checks it and raises `IllegalTransitionError` before anything changes. The router and React contain no transition rules.

3. What is `allowed_commands` (or equivalent) for? Why is exposing “what can I do now?” better than letting the UI guess from a raw state string?

> [!NOTE]
> ***Your Answer***
>
> `allowed_commands` is the list of command names that are legal from the actuator's current state, for example `["start_pump", "begin_maintenance", "power_off"]` for an idle pump and `["stop_pump"]` for a running one. It is derived from the current state in the domain, and the device JSON carries it next to `state`.
>
> If the UI only got a raw string like `"running"`, it would have to know what that means: which buttons to show, and which commands each state allows. That copies the transition rules into React, so the rules exist twice and drift apart the moment one is edited (for example, after adding a state). With `allowed_commands`, the backend answers "what can I do now?" and the UI only displays the answer. It is also device-aware: a `grow_light` gets `lights_on` while a `water_pump` gets `start_pump`, which the UI would otherwise have to hard-code. And it's the same list Phase 10's Command will check before executing.

## B. This phase of the application

4. Which actuator states did you implement (for example idle, running, error)? Sketch the legal transitions (which command or event moves idle → running, running → idle, into error, and out of error).

> [!NOTE]
> ***Your Answer***
>
> I implemented five states: `off`, `idle`, `running`, `maintenance` and `error`. Everything not in this table is illegal.
>
> | From | To | Command or event |
> |---|---|---|
> | `off` | `idle` | `power_on` |
> | `idle` | `running` | `start` (`start_pump` / `lights_on`) |
> | `idle` | `maintenance` | `begin_maintenance` |
> | `idle` | `off` | `power_off` |
> | `idle` | `error` | system event |
> | `running` | `idle` | `stop` (`stop_pump` / `lights_off`) |
> | `running` | `error` | system event |
> | `maintenance` | `idle` | `end_maintenance` |
> | `maintenance` | `error` | system event |
> | `error` | `idle` | `reset` |
> | `error` | `maintenance` | `begin_maintenance` |
>
> The main rule is that a running device must stop first. `running → off` and `running → maintenance` are illegal, so a pump can't be cut off or serviced mid-watering. Every powered state can fail, but a device that is off can't, and after an error it is either reset or sent to maintenance. `error` is a system event rather than a user command, so it is a legal target but never appears in `allowed_commands`. Start and stop command names depend on the device type.

5. Why is actuator state stored in `actuator_states` (or equivalent) rather than only in process memory? What must still be true after you restart the backend?

> [!NOTE]
> ***Your Answer***
>
> A process-memory state would be lost on every restart or reload, and all actuators would silently go back to a default, even if a pump was really running. It would also be wrong with more than one backend process, because each would hold its own copy. The state is real data about a device, so it belongs in the database, in `actuator_states` (`device_id` primary key and foreign key, `state`, `updated_at`). The service loads it fresh on every request and keeps nothing on the service or the FastAPI process.
>
> After a restart, every actuator must report the same state as before. I tested this: I moved a pump to `running`, restarted the backend container, and the device list still showed `running`. Every actuator must also still resolve a state. The migration seeded `idle` for existing actuators (14 actuators, 14 rows), and a missing row, for an actuator provisioned later, means the initial state `idle`. A database CHECK constraint on `state` guarantees that only the five valid names can be stored.

6. An illegal transition must raise a domain error and must not update the database. Why? Which HTTP status is reasonable for that case (400 or 409), and why should the rule live in the domain rather than in React?

> [!NOTE]
> ***Your Answer***
>
> The stored state has to stay a true description of the device. If an illegal move were saved, the database would claim a pump is `off` when the real device, which the move never reached, is still running. After that, every later decision (such as which commands are allowed) would be built on wrong data. So `ActuatorContext.transition` raises `IllegalTransitionError` before anything changes, and the service calls `save_state` only after `transition` returns. I tested it: after a rejected `running → off`, the row still said `running`, and a rejected first move on an actuator with no row left no row behind.
>
> I used **409 Conflict** for it. The request is well-formed and the target is a real state, but it conflicts with the resource's current state. I kept **400** for requests that are wrong in themselves: an unknown state name (`UnknownStateError`) or a sensor, which has no lifecycle. A missing device is 404.
>
> The rule lives in the domain rather than in React because React can be bypassed: Scalar, a script, the Phase 10 Command or a second client all call the API directly. Only a backend check protects the data for every caller. If React also encoded the rules, there would be two copies to keep in sync. My demo selector in React deliberately offers illegal targets, so the user sees the backend's explanation ("Cannot move from 'running' to 'off'. Legal targets: idle, error").

7. Device JSON gains `state` and `allowed_commands`. How does the dashboard use those fields (badges, disable illegal buttons)? How does this prepare Phase 10 Command?

> [!NOTE]
> ***Your Answer***
>
> The dashboard only displays what the backend sends. `ActuatorStateBadge` shows the `state` as a coloured badge (idle slate, running emerald, error red, maintenance amber, off dark) and uses `allowed_commands` for the hover tooltip ("Allowed commands: stop_pump"). Sensors return `state: null` and `allowed_commands: []`, so they get no badge. When a transition succeeds, the demo control updates the device with the state the backend returned, so the badge changes immediately. After a reload, the badge shows the persisted state. Because the fields are on the `DeviceDto`, they also appear on the devices list, the zone device list and the zone assignment response.
>
> It prepares Phase 10 because the command names (`start_pump`, `stop_pump`, `lights_on`, ...) are already defined next to the states, and `allowed_commands` is the exact list a Command will check before it executes. Command objects can then ask the state guard "is this legal now?" instead of inventing their own rules, and full control buttons can be built from `allowed_commands` (showing or disabling buttons) without adding any transition logic to React.

## C. Compare, contrast, and scenarios

8. Contrast State with Strategy. Both look like “context delegates to an object.” Who typically changes the active object, and is the variation a lifecycle or a selectable policy? Give a greenhouse example of each (this phase vs Phase 6).

> [!NOTE]
> ***Your Answer***
>
> In both patterns, a context holds an object with a common interface and delegates to it. The difference is who changes the active object and why.
>
> - **Strategy (Phase 6)** is a **selectable policy**. The **client** chooses the active object from outside, and the options are interchangeable ways of doing the same job. In my greenhouse, the grower picks `conservative` or `aggressive` in the dashboard, and it's saved as the location's `strategy_key`. The strategies don't know about each other and never switch themselves.
> - **State (Phase 8)** is a **lifecycle**. The **context itself** changes the active object as the device moves through its life, and each state knows which states can follow it. In my greenhouse, a pump goes `idle → running → idle`, and `ActuatorContext.transition` swaps the state object, which decides what is legal. Nobody "chooses" `running` as a policy; it's where the device currently is.
>
> My test is: "who changes the active object?" If an outside choice does, and the objects are alternatives, it's Strategy. If the object's own events move it along a path, and the objects name each other as next steps, it's State.

9. Contrast State with a pile of booleans (`is_running`, `is_fault`, `is_maintenance`). Why do illegal combinations of flags appear, and how do explicit state objects (or a transition table) prevent that?

> [!NOTE]
> ***Your Answer***
>
> With three independent booleans there are 2³ = 8 possible combinations, but only a few mean something. Nothing stops `is_running = True` and `is_maintenance = True` at the same time (a pump that is both running and being serviced), or a fault flag that stays set after a reset. Each place that sets a flag has to remember to clear the others, and one forgotten line creates a combination the rest of the code never planned for. Every `if` that reads the flags then has to guess what such a combination means.
>
> A single state has exactly one value out of a closed set, so a contradictory combination can't be represented. In my lab the state is one string in `actuator_states`, limited by a CHECK constraint to the five valid names, and each state object lists the only moves allowed from it. To get from one state to another, the only path is `transition`, which checks that table. Illegal moves like `running → maintenance` are rejected, so the device can't enter a state combination that was never designed.

10. A classmate puts HTTP status mapping or SQLAlchemy commits inside a concrete state class. Another state mutates a flag directly and skips `transition` / `set_state`. Explain why each is a trap.

> [!NOTE]
> ***Your Answer***
>
> **HTTP mapping or database commits inside a state class** mix the lifecycle rules with infrastructure. The state would depend on FastAPI and SQLAlchemy, so it could no longer be unit tested with a plain context (my 11 legal and illegal edges are tested with no database at all). A state that commits could also save before the whole operation is validated, which breaks the "guard first, save only afterwards" rule. And reusing it from somewhere else, like Phase 10's Command, would drag HTTP and the database along. In my design, the states only describe transitions, the service saves, and the router maps errors to 400, 404 and 409.
>
> **A state that mutates a flag directly and skips `transition`** bypasses the one place that enforces the rules. The guard, the check that the move is legal, never runs, so illegal states become possible again, and the change might not be saved or might be saved inconsistently. It also spreads transition logic into every state, which brings back the scattered `if` guards the pattern was meant to remove. In my design, `ActuatorContext.transition` is the only way to change state, it checks the table first and assigns last, and `state` is a read-only property.