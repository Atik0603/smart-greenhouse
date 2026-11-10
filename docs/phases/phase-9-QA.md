## A. Pattern

1. State the intent of Decorator in plain language. Why is stacking wrappers a flexible alternative to a combinatorial explosion of subclasses (`LoggingRetryMaxRuntimeActuator`, …)?

> [!NOTE]
> ***Your Answer***
>
> Decorator adds behaviour to an object by wrapping it in another object with the same interface. The wrapper does its own extra work and then passes the call on to the object inside, or refuses to. Because every wrapper looks exactly like the original, wrappers can be stacked, and the caller can't tell how many there are. It's like a takeaway order: the kitchen makes the meal, someone packs it, someone attaches the receipt, and the customer still just receives "a meal".
>
> With inheritance, each combination of behaviours needs its own subclass: `LoggingActuator`, `MaxRuntimeActuator`, `LoggingMaxRuntimeActuator`, and with a retry policy added, every mix of three. The number of classes grows with every combination, and the same code is repeated in each one. With decorators, each policy is written once as one small class, and combinations are built at runtime by wrapping. In my lab, adding a new policy is one new class plus one wrapper line in `build_actuator_port`.

2. Name the participants (component, concrete component, decorator, concrete decorators). What interface does every decorator present to the caller, and why must that match the wrapped component?

> [!NOTE]
> ***Your Answer***
>
> - **Component:** `ActuatorPort`, the interface with `apply(device_id, command, payload) -> AppliedCommand`.
> - **Concrete component:** `SimulationActuatorAdapter` from Phase 5, the innermost object that actually performs the command.
> - **Decorator:** any class that implements `ActuatorPort` and holds an inner `ActuatorPort`, which it forwards calls to.
> - **Concrete decorators:** `LoggingActuatorDecorator` and `MaxRunTimeActuatorDecorator`.
>
> Every decorator presents exactly the same interface: `ActuatorPort.apply` with the same parameters and the same return type. It has to match, because callers (and other decorators) treat each layer as "an `ActuatorPort`" without knowing what's inside. If one decorator renamed the method, added a required argument or returned something else, it could no longer be stacked or swapped, and the caller would have to know which layer it was talking to. That defeats the purpose of the pattern. In my code, each decorator also returns the inner result unchanged.

3. Order matters. Using logging and retry (or logging and max-run-time) as an example, explain how wrapping A around B can change what you observe compared with wrapping B around A.

> [!NOTE]
> ***Your Answer***
>
> The outer wrapper sees everything that comes into the stack; the inner one only sees what the outer wrapper lets through.
>
> In my lab the order is **logging → max-run-time → adapter**. Logging is outermost, so it observes every attempt. When max-run-time blocks a command, the error travels back out through logging, which writes a row with `success=false`, `["maxRunTime", "logging"]` and "Max run time exceeded", then re-raises.
>
> If I reversed it (**max-run-time → logging → adapter**), max-run-time would raise before the call ever reached logging. The blocked attempt would leave **no row at all**, and the execution log would only show successful commands. I wrote a test for this, `test_wrong_order_loses_the_blocked_attempt`, which builds the stack the wrong way round and asserts the log stays empty.
>
> With retry it works the same way: logging outside retry records one row per logical call, while logging inside retry records one row per inner attempt.

## B. This phase of the application

4. What is `ActuatorPort` here, and which at least two decorators did you stack around the real adapter (for example logging and max run-time)? Where is the chain wired (composition root / factory), and why not inside the HTTP router?

> [!NOTE]
> ***Your Answer***
>
> `ActuatorPort` is the Phase 5 interface for sending a command to an actuator: `apply(device_id, command, payload) -> AppliedCommand`. The real (simulated) implementation is `SimulationActuatorAdapter`.
>
> Around it I stacked two decorators:
> - `MaxRunTimeActuatorDecorator`, which refuses commands when the actuator has been `running` for at least 30 minutes.
> - `LoggingActuatorDecorator`, outermost, which writes a row to `actuator_execution_log` for every attempt.
>
> The chain is wired in one function, `build_actuator_port(db)` in `application/actuators/composition.py`, which returns an `ActuatorPort` built from logging → max-run-time → simulation adapter. The router gets the finished port through its dependency and never sees the layers.
>
> I kept it out of the router because the router's job is HTTP: parse the request, call the service, map errors (404, 400, 409). If it built the stack, or checked the 30-minute rule itself with an `if`, the policy logic would live in the interface layer, and every other caller (like Phase 10's Command) would have to repeat it. With a composition root, adding or removing a policy changes one function.

5. Max run-time can short-circuit: the inner adapter is never called. Why must a blocked attempt still produce a row in `actuator_execution_log` with `success=false` and the policy named in `policy_applied`?

> [!NOTE]
> ***Your Answer***
>
> The log is meant to be a complete record of what was *attempted*, not just what worked. A blocked attempt is often the most important thing to see: it tells the operator that someone or something tried to control the pump and a safety policy stopped it. If blocked attempts left no trace, the log would suggest nothing happened, and a pump that keeps being commanded while stuck in `running` would go unnoticed.
>
> `success=false` shows the command didn't run, and naming the policy (`["maxRunTime", "logging"]`) explains *why*, so the operator doesn't have to guess between a policy, a hardware error or a bug. Because logging is the outermost decorator, it catches the `PolicyViolationError`, writes that row, then re-raises so the caller still gets the 409. My repository commits the row immediately, so it survives even though the HTTP request ends in an error. The integration test `test_failed_policy_writes_execution_row` checks both: a 409 response and the failed row in the table.

6. How does max run-time know the actuator has been running too long (for example `actuator_states.updated_at` from Phase 8)? Why is that data from State, not something the decorator should invent as a second lifecycle?

> [!NOTE]
> ***Your Answer***
>
> It asks for the actuator's current state and when it last changed: `actuator_states.state` and `actuator_states.updated_at` from Phase 8, through `ActuatorStateRepository.get_state_since`. The decorator receives that lookup function and a clock in its constructor. If the state is `running` and `clock() - updated_at` is at least 30 minutes, it blocks. An actuator with no state row is treated as not running.
>
> The data has to come from State because the lifecycle already has one owner. If the decorator kept its own "started running at" timestamp, there would be two lifecycles that could disagree. For example, a pump stopped through the transition endpoint would still look "running" to the decorator. Its in-memory record would also be lost on every restart, which is exactly the problem Phase 8 solved by persisting state. Reading the persisted state keeps one source of truth, and injecting the lookup keeps the decorator testable with a fake (my unit tests simulate "running for 31 minutes" without waiting).
>
> One limitation I kept on purpose: the rule blocks every command once the limit is reached, including `stop_pump`, because that's the literal requirement. A real system would let stop commands through, which Phase 10 can refine using the state guards.

7. `GET /api/actuators/executions` feeds the dashboard execution log. Why persist attempts in the database instead of only printing to stdout? What should the UI show after a blocked attempt and a refresh?

> [!NOTE]
> ***Your Answer***
>
> Printed logs are for developers, not users. They disappear when the container restarts, can't be queried, and the dashboard can't read them. Persisting each attempt in `actuator_execution_log` makes the history durable, queryable (newest first, with a limit, served by the `created_at DESC` index), and available through an API that the UI and tests can use. It also turns the log into part of the system's behaviour: my integration tests check the rows directly. The requirements even list "logging only with print and skipping the table" as a pitfall.
>
> After a blocked attempt and a refresh, the execution log shows a new row at the top: the time, the device, a red **BLOCKED** badge, the policies `maxRunTime` and `logging`, and the message "Max run time exceeded". A successful attempt shows a green **SUCCESS** badge, the policy `logging` only, and no message (a dash). The panel also explains that commands aren't validated yet, so any command succeeds until the actuator has been running for 30 minutes.

## C. Compare, contrast, and scenarios

8. Contrast Decorator with Adapter. Both wrap. One keeps the interface and adds behaviour; the other changes the interface and translates. Which is which in this greenhouse (Phase 9 vs Phase 5)?

> [!NOTE]
> ***Your Answer***
>
> **Adapter changes the interface and translates.** In Phase 5, `MqttSensorAdapter` and `VendorStubSensorAdapter` take something with a foreign format (an MQTT payload, a vendor SDK value in milli-units) and present it as `SensorPort.read` returning a common `Reading`. The thing inside speaks a different language, and the adapter converts it.
>
> **Decorator keeps the interface and adds behaviour.** In Phase 9, `LoggingActuatorDecorator` and `MaxRunTimeActuatorDecorator` wrap an `ActuatorPort` and *are* `ActuatorPort`s themselves, with the same `apply` method and return type. They don't translate anything; they add logging and a safety policy around a call that already has the right shape.
>
> So both hold a wrapped object, but the question is whether the interface changes. Adapter: yes, foreign to ours. Decorator: no, ours to ours, with extra behaviour.

9. Contrast Decorator with inheritance of combined policies. How does composition let you add or remove a policy without a new subclass for every combination?

> [!NOTE]
> ***Your Answer***
>
> With inheritance, the policies are fixed into the class hierarchy at compile time. To get logging plus max run time I'd need a `LoggingMaxRunTimeActuator`, and with a third policy, a subclass for every combination I want to use. The order is also hardcoded in each class, and the same policy code is repeated or inherited in awkward chains.
>
> With composition, each policy is a separate class that wraps "any `ActuatorPort`", and the combination is chosen when the objects are built. In my lab that's `build_actuator_port`:
>
> ```python
> LoggingActuatorDecorator(MaxRunTimeActuatorDecorator(SimulationActuatorAdapter(), ...), ...)
> ```
>
> To remove max run time, I delete one wrapper. To add, say, a quiet-hours policy, I write one class and wrap it in one more line. The order is chosen in the same place. None of this needs a new subclass, and the service, router, table and UI don't change; a new policy's name simply appears in `policy_applied`.

10. A classmate’s decorator changes the method signature “a little” (extra required argument, different return type). Another ignores wrap order and cannot explain whether logging runs once per logical call or per inner attempt. Explain why each is a trap.

> [!NOTE]
> ***Your Answer***
>
> **Changing the signature "a little"** breaks the core rule of the pattern: every decorator must be usable anywhere an `ActuatorPort` is expected. With an extra required argument, the caller (and the next decorator out) would have to know it's talking to this specific wrapper, so it can no longer be stacked or removed freely. A different return type is just as bad: the layer above expects an `AppliedCommand` and gets something else. It would effectively become a new interface, more like a badly done adapter. In my code every layer has exactly `apply(device_id, command, payload) -> AppliedCommand` and forwards the inner result.
>
> **Ignoring wrap order** means not knowing what the system actually does. The order decides what each layer observes. Logging outside a retry decorator writes one row per logical call; logging inside it writes one row per inner attempt; and logging inside a blocking policy writes nothing for blocked calls at all. Without knowing the order, you can't say whether the execution log is complete or what a row means, so the numbers in the log can't be trusted. That's why I fixed the order in one composition root, documented it, and tested the wrong order explicitly.