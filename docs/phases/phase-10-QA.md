## A. Pattern
 
1. State the intent of Command in plain language. What does it mean to objectify a request, and what can you do with that object that you cannot do with a bare `actuator.start()` call (queue, audit, undo, history)?
> [!NOTE]
> ***Your Answer***
>
> Command turns a request into an object, so the request can be handled like data instead of being a call that happens and disappears. It's like an order ticket in a restaurant: the waiter writes down "table 4, steak, medium" instead of shouting at the cook. The ticket can wait in line, be checked, be refused, and stay on the spike afterwards as a record.
>
> Objectifying a request means the command object carries everything needed to perform it later: what to do, to which device, with which data, and how to execute it. In my lab, `StartPumpCommand(device_id)` holds the device id, `command_type = "start_pump"`, `target_state = "running"` and an `execute(port)` method.
>
> With a bare `actuator.start()` call, nothing remains once it returns. With an object, I can check it against the actuator's state before running it, **audit** it (every attempt becomes a `command_log` row, even rejected ones), show a **history** in the UI, and, because the invoker is one place that runs every command, add **queuing** or **undo** later without changing the commands or the router.
 
2. Name the participants (command, receiver, invoker, client). Who creates the command, who triggers `execute()`, and who actually changes actuator/hardware state?
> [!NOTE]
> ***Your Answer***
>
> - **Command:** the abstract `Command` class, plus the concrete `StartPumpCommand`, `StopPumpCommand` and `SetLightLevelCommand`.
> - **Receiver:** the `ActuatorPort`, the Phase 9 decorated stack (Logging → MaxRunTime → `SimulationActuatorAdapter`).
> - **Invoker:** `CommandInvoker`, which runs any command with `run(command, port)`.
> - **Client:** `CommandService`, called by `POST /api/commands`.
>
> The **client creates** the command: `CommandService` turns the request's `command_type` into an object through the registry (`command_for`). After the State guard approves it, the **invoker triggers** `execute()`. The **receiver changes the actuator**: the command's `execute` calls `port.apply(...)`, and the adapter at the bottom of the stack performs it.
>
> The *lifecycle state* in `actuator_states` is a separate concern: the service changes it through `ActuatorContext.transition` only after `apply` completed, so State keeps ownership of the lifecycle.
 
3. If a command supports undo, when must it capture the data needed to reverse the action? Why is “capture before mutate” critical?
> [!NOTE]
> ***Your Answer***
>
> It must capture the data **before** it changes anything, as part of executing, before the call to the receiver. For example, a `SetLightLevelCommand` with undo would read and store the light's current level, and only then send the new one. Undo would send the stored level back.
>
> It's critical because after the change, the old value is gone. Reading it afterwards would return the *new* value, so undo would "restore" what was just set and do nothing. Other commands could also change the device between execute and undo, so the command needs its own snapshot from the moment it ran, not whatever the device says later. My commands don't implement undo yet, but because each request is already an object with its own `device_id` and `payload`, the snapshot would simply be one more field on the command.
 
## B. This phase of the application
 
4. Which command types did you implement (for example `start_pump`, `stop_pump`, `set_light_level`)? Why does the HTTP handler create a command and pass it to an invoker (or application service) instead of calling the actuator adapter from the router?
> [!NOTE]
> ***Your Answer***
>
> I implemented `start_pump` (target `running`), `stop_pump` (target `idle`) and `set_light_level` (target `running`, payload `{ "level": n }` from 0 to 100, default 1). A registry maps each type string to its class, so adding a command is one class and one registry entry.
>
> The router doesn't call the adapter because every command needs the same steps in the same order: check the device, check the state, run through the policy decorators, update the state, and record the outcome. If each route called the port directly, each would have to repeat those steps, and it would be easy to skip the State guard or the decorators. Rejected requests would leave no trace. With `POST /api/commands` → `CommandService` → `CommandInvoker`, there's one path for every command, it always uses the decorated port from `build_actuator_port`, and every attempt lands in `command_log`. For the same reason I removed the Phase 9 demo route, which called the port directly.
 
5. Walk through the execute path: (1) consult State / `allowed_commands`, (2) if illegal → rejected, (3) if legal → decorated `apply`, update `actuator_states`, log success or failed. Why must a rejected command not change actuator state and not reach inner `apply`?
> [!NOTE]
> ***Your Answer***
>
> In `CommandService.submit`:
>
> 1. Load the device. Missing, or not an actuator → 404, no row. Build the command; an unknown type or bad payload → 400, no row.
> 2. **Guard:** build an `ActuatorContext` from the saved state and check `command_type in allowed_commands()`. If not → write a `rejected` row and return it as a 409. Nothing else happens.
> 3. If legal → `CommandInvoker.run(command, port)`, through Logging → MaxRunTime → simulation adapter. If a policy or the adapter raises → write a `failed` row (200); the state stays as it was.
> 4. After a completed apply → `ActuatorContext.transition(target_state)` and save, only if the target differs from the current state.
> 5. Write a `success` row (200).
>
> A rejected command must not reach `apply` because "illegal in this state" means the action shouldn't happen at all. Sending `stop_pump` to an idle pump, or `set_light_level` to a pump, could make the hardware do something the lifecycle says is impossible. It must not change `actuator_states` because the state would then stop matching the real device. My tests check both: after a rejected command, the spy port has no calls, there are no state saves, and there's no execution-log row, but there is a `rejected` row in `command_log`.
 
6. Distinguish `rejected` vs `failed` vs `success` in `command_log`. Give one greenhouse example of each. Why is “illegal in this state” not the same as “policy or adapter error after the command was accepted”?
> [!NOTE]
> ***Your Answer***
>
> - **rejected:** the command isn't legal in the actuator's current state, so it was never attempted. Example: `stop_pump` on an idle pump ("'stop_pump' is not allowed while the actuator is idle").
> - **failed:** the command was legal and accepted, it was attempted, but a policy or the adapter stopped it. Example: `stop_pump` on a pump that has been `running` for 30 minutes, blocked by the max-run-time decorator with "Max run time exceeded".
> - **success:** accepted, applied and completed. Example: `start_pump` on an idle pump, which then becomes `running`.
>
> They differ in *where* the problem is and *what happened*. "Illegal in this state" is a lifecycle rule, checked before anything runs: the request itself makes no sense right now, and nothing reached the actuator. "Policy or adapter error" happens *after* acceptance: the request made sense, the system tried, and something on the way stopped it, whether a safety policy, a dead relay or a timeout. That's why they're visible differently: a rejected command appears only in `command_log` (409), while a failed one appears in `command_log` *and* in `actuator_execution_log`, because it did reach the port (200 with `status: failed`). An operator fixes them differently too: a rejected command needs a different command, while a failed one needs someone to look at the policy or the device.
 
7. Why is `command_log` a different table from Phase 9 `actuator_execution_log`? What concern does each log record (operator intent vs policy/adapter attempt)?
> [!NOTE]
> ***Your Answer***
>
> They answer different questions at different layers.
>
> - **`command_log`** records **operator intent and its outcome**: who asked for which command (`command_type`, `payload`) on which device, and whether it was `success`, `failed` or `rejected`. It includes requests that never reached the actuator.
> - **`actuator_execution_log`** records **what reached the actuator port**: each `apply` attempt, whether it succeeded, and which policies acted on it (`policy_applied`). It knows nothing about commands or states; it's written by the logging decorator.
>
> Keeping them separate means each stays correct for its own layer. A rejected command is one row in `command_log` and none in the execution log, because nothing was attempted. A max-run-time block is a `failed` row in `command_log` *and* a `success=false` row with `["maxRunTime", "logging"]` in the execution log. Merging them would mix "what was requested" with "what the hardware layer did," and the port would have to know about command statuses it has no business knowing.
 
## C. Compare, contrast, and scenarios
 
8. Contrast Command with Strategy. Strategy is an interchangeable algorithm (decide / quote). Command is a side-effectful request with history. How do they cooperate in this app (Phase 6 recommends; Phase 10 executes)?
> [!NOTE]
> ***Your Answer***
>
> **Strategy** is about *how to decide*. It's a pure calculation with no side effects: in Phase 6, `ConservativeStrategy` or `AggressiveStrategy` looks at moisture and thresholds and returns a `Recommendation` (`irrigate` or `wait`). It changes nothing, and running it twice gives the same answer.
>
> **Command** is about *doing something*. It's a request with side effects: `StartPumpCommand` actually goes to the actuator, can change its state, and leaves a history row whatever happens.
>
> They cooperate as "decide, then act." The strategy says the North zone should be irrigated, and the overview shows that recommendation. An operator, or later an automated step, turns that into a `start_pump` command for the pump in that zone, which then goes through the State guard, the decorators and `command_log`. Keeping them separate means a recommendation can be shown, ignored or overridden without ever touching the hardware, and executing a command doesn't need to know how the decision was made. Phase 6 deliberately returned a recommendation instead of starting a pump, and Phase 10 is where executing finally happens.
 
9. Contrast Command with State. Who triggers the action, and who decides whether it is legal? Why must commands not bypass state guards?
> [!NOTE]
> ***Your Answer***
>
> **Command** represents what someone *wants* to happen, and it's triggered from outside: the operator clicks a button, the frontend posts to `/api/commands`, and the service and invoker run it. **State** decides whether that is *legal right now*: `ActuatorContext.allowed_commands()` says what the current lifecycle state permits, and `transition` moves the lifecycle after a completed command. So Command carries the request, and State is the authority on whether it's allowed and what the next state is.
>
> Commands must not bypass the guard because then nothing would protect the lifecycle. A `stop_pump` sent to an idle pump, or a `set_light_level` sent to a pump, would reach the actuator. The stored state could also jump into a combination the transition table never allowed, and the database would no longer describe the real device. In my service, the guard runs before the invoker is even called, and the same `ActuatorContext` performs the transition afterwards, so a command can't reach the port or change the state without State's approval.
 
10. The controls UI should disable actions that are not in `allowed_commands`. Why must the backend still reject illegal commands even if the UI is correct? What happens if a classmate’s command calls the raw adapter and skips State and Decorator?
> [!NOTE]
> ***Your Answer***
>
> The UI is only a convenience, not a security boundary. The API can be called without it: from Scalar, a script, PowerShell, or another client. A page can also be **stale**: if I start a pump in one tab, another tab still shows Start enabled until it refreshes. I tested exactly that, and the backend answered 409 with a `rejected` row while the pump's state stayed unchanged. Only the backend's guard protects every caller.
>
> If a classmate's command called the raw `SimulationActuatorAdapter` directly, it would skip both safety layers. Without **State**, illegal commands would reach the actuator and the stored lifecycle could stop matching the device. Without the **Decorator** stack, the max-run-time policy wouldn't apply, so a pump running too long would keep accepting commands, and the `actuator_execution_log` would miss those attempts entirely. My command service avoids this by getting its port only from `build_actuator_port`, which always returns the full Logging → MaxRunTime → Simulation stack, and by checking `allowed_commands` before the invoker runs.
 