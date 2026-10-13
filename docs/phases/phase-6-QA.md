1. State the intent of Strategy in plain language. How does the **context** use a strategy, and why must “choose which algorithm” stay separate from “run the algorithm”?
> [!NOTE]
> ***Your Answer***
>
> Strategy puts each version of an algorithm in its own class behind one shared interface, so the algorithms can be swapped without changing the code that uses them. The context holds a reference to one strategy object and delegates the work to it: it calls one method (in my lab, `decide(context)`) without knowing which concrete class it is talking to. It's like a GPS app: the "Navigate" button stays the same whether I pick fastest, scenic or avoid tolls; only the routing engine behind it changes.
>
> Choosing and running must stay separate because they change for different reasons. The *choice* is configuration (the grower picks a policy, stored in the database). The *algorithm* is business logic (how to decide whether to water). If the context did both, every new policy would mean editing the context. In my code, choosing happens once through the registry (`get_strategy(saved_key)`), and running is a single polymorphic call (`strategy.decide(context)`) in `AutomationService`. Adding a new algorithm means adding a class, not editing the place that runs it.
 
2. Name the participants (**strategy**, **concrete strategies**, **context**, **client**). What goes wrong when all policies live as `if/elif` inside the context (or inside an HTTP router)?
> [!NOTE]
> ***Your Answer***
>
> - **Strategy:** the common interface. In my lab this is the abstract class `AutomationStrategy` with `decide(context) -> Recommendation`.
> - **Concrete strategies:** `ConservativeStrategy` and `AggressiveStrategy`, each with its own irrigation rule.
> - **Context:** the object that holds a strategy and delegates to it. In my lab that's `AutomationService.evaluate`: it loads the saved key, gets the strategy object and calls `decide` for each zone. (My `LocationAutomationContext` is the *input data* passed to `decide`, like `Parcel` in the shipping example, not the pattern's "context" role.)
> - **Client:** whoever chooses the strategy. Here, the operator picks a key in the dashboard panel, which saves it through `PUT /api/locations/{location_id}/automation`.
>
> If all policies lived as `if/elif` in the service or the router, the algorithms and the selection logic would be fused in one hotspot. Every new policy would mean editing a method that also handles HTTP status codes and database access, which risks breaking the existing branches. The tests would have to go through the whole router to test one formula. Two developers adding two policies would edit the same method and get merge conflicts. And the method would keep growing until nobody wanted to touch it.
 
3. When should you use Strategy, and when should you skip it (one algorithm only; or the variation is a **lifecycle mode** rather than a chosen policy)?
> [!NOTE]
> ***Your Answer***
>
> I would use Strategy when several algorithms answer the same question in different ways (here: "should this zone be watered?"), when the choice should change at runtime without changing code (the operator switches policy in the UI), and when I want each policy in its own small, testable class.
>
> I would skip it when there is only one algorithm and no real reason to expect more, because the interface and registry would just be overhead. If the "strategies" are tiny one-liners, a dictionary of functions can be enough until they grow. I would also skip it when the behaviour changes because of a **lifecycle mode**, for example a device being idle, watering or faulted, and the object itself moves between those modes. That is the State pattern, because the change comes from the object's own lifecycle, not from someone choosing a policy.
 
## B. This phase of the application
 
4. In this lab, what does a strategy’s `decide(context)` return (action + reason)? Give a concrete difference you implemented (or were required to implement) between **conservative** and **aggressive** on the **same** moisture reading and zone thresholds.
> [!NOTE]
> ***Your Answer***
>
> `decide(context)` returns a `Recommendation` with `action` (`"irrigate"` or `"wait"`), a human-readable `reason`, and an optional `score`, which I used as urgency from 0 to 1.
>
> - **Conservative** waters only when moisture is below the zone's **low** threshold.
> - **Aggressive** waters whenever moisture is below the **midpoint** of the zone's band, `(low + high) / 2`, to keep the soil in the upper half of the range.
>
> Example with a zone of low 0.20, high 0.40 and a moisture reading of 0.25:
> - Conservative: `wait`, "Moisture 0.25 is at or above the low threshold 0.20"
> - Aggressive: `irrigate`, "Moisture 0.25 is below the midpoint 0.30", score 0.5
>
> They disagree whenever moisture is between low and the midpoint. I proved this in a unit test with a fake context, in the API by saving each key and evaluating the same reading, and in the dashboard panel. My boundary tests also caught a floating-point bug: `(0.20 + 0.40) / 2` is `0.30000000000000004` in Python, so a reading of exactly 0.30 was wrongly marked "irrigate." I fixed it by rounding the midpoint to 4 decimals, the precision the thresholds are stored with (`Numeric(5, 4)`).
>
> The evaluate response still has one top-level `action` and `reason` as required. I added a `zones` list on top, so the operator can see which zone caused the result.
 
5. Where do the numbers in `LocationAutomationContext` (or your equivalent) come from? Latest moisture may already be in `sensor_readings` from a manual read, the simulation sampler, or MQTT translation — why does this phase not add a scheduler or a broker? Why must strategies receive a plain context object, not SQLAlchemy rows or FastAPI types? Why are thresholds read from **zones**, not hardcoded in the strategy class?
> [!NOTE]
> ***Your Answer***
>
> The numbers come from the database, through `AutomationContextRepository`. For each zone in the location, `low` and `high` come from `zones.moisture_threshold_low/high`, and `moisture` is the newest row in `sensor_readings` among devices with `device_type = "moisture_sensor"` and that zone's `zone_id`. Light is fetched the same way for light sensors. The repository copies these values into a plain `ZoneSnapshot`, and the service builds one `LocationAutomationContext` per zone from it. A device from another zone, or an unassigned one, is never used. A zone without a moisture sensor gets `wait` with the reason "No moisture sensor in this zone."
>
> This phase does not add a scheduler or broker because getting readings into the database is already handled by Phase 5's single ingest path (`ReadingIngest`), whether the reading came from a manual read, the sampler or a translated MQTT payload. Strategy is about *deciding* from data that already exists. Adding ingestion here would mix two responsibilities and duplicate a pipeline another phase owns. My query simply takes the latest row, whatever produced it.
>
> Strategies receive a plain object so they stay pure domain code. If they got SQLAlchemy rows, they could trigger hidden lazy-loading queries, and they would break whenever a column is renamed. With FastAPI types they would be tied to HTTP. With plain values, I can unit test them in milliseconds with a hand-made context and no database, which is how I found the floating-point bug. They can also be reused from anywhere, such as a scheduler, the Phase 7 facade or a CLI.
>
> Thresholds come from `zones` because each zone is configured by the grower (Phase 4), and different crops need different moisture bands. The strategy defines *how* to decide (below low, or below the midpoint); the zone defines *the numbers*. Hardcoding `0.3` in a class would ignore the configuration, give every zone the same band, and require a code change for every new crop.
 
6. The active `strategy_key` is **persisted** per `location_id` (for example in `automation_rules`). Why must `POST .../automation/evaluate` use the **saved** key rather than a key the client sends only in that request? What happens on the next evaluate after the operator changes strategy but moisture stays the same?
> [!NOTE]
> ***Your Answer***
>
> The saved key is the location's single source of truth for its automation policy. If each request could send its own key, two clients could evaluate the same location with different policies and get conflicting recommendations, and nothing would record which policy was actually in force. With the persisted key, the dashboard, later phases (the Phase 7 facade, future scheduled runs) and any other caller all get the same answer, and `automation_rules.updated_at` shows when the policy last changed. That's also why I return 409 "No strategy selected for this location yet" when no rule is saved, instead of silently using a default: every recommendation traces back to a choice someone actually saved. Saving uses an upsert on the unique `location_id`, so there is always at most one active strategy per location.
>
> On the next evaluate after the operator switches strategy, the service loads the new key, gets the other strategy object and calls its `decide` with exactly the same context. If the moisture is between low and the midpoint, the action flips, e.g. from `wait` with conservative to `irrigate` with aggressive at 0.25 in a 0.20–0.40 zone. Outside that band the action stays the same, but the reason changes, since it now refers to the midpoint instead of the low threshold. The `strategy_key` field in the response always shows which policy produced the result. In my panel, the old result is cleared when a new strategy is saved, and if the dropdown differs from the saved key, the panel warns that Evaluate uses the saved strategy.
 
7. Strategy **recommends** (irrigate / wait). It should not itself start a pump. Why keep **decide** separate from **execute**? Which later pattern is meant to carry out the action?
> [!NOTE]
> ***Your Answer***
>
> Deciding has no side effects, but executing changes the physical world, and mixing them causes several problems:
>
> - **Testability:** `decide` is a pure function of its context. I can test it with fake numbers and no pump, no actuator and no database. If it started the pump, every test would need a fake actuator.
> - **Safety and review:** a recommendation can be shown to the operator first, logged, or ignored. Pressing "Evaluate" in my panel just shows the answer. If deciding also watered, every click would turn on a pump.
> - **Single responsibility:** the strategy answers "should we?", while execution handles "how, on which device, and what if it fails?" Those concerns change for different reasons, and every strategy would otherwise duplicate the execution code.
> - **Flexibility:** the same recommendation can later be executed now, scheduled, or confirmed manually, without changing any strategy.
>
> Carrying out the action is meant for the **Command** pattern later in the course. A command will wrap the request (for example "irrigate zone North for 30 s") as an object that can be executed through the actuator port from Phase 5, logged, queued, and possibly undone.
 
## C. Compare, contrast, and scenarios
 
8. Contrast Strategy with **State** (Phase 8). Both delegate to an object with the same shape. Who typically **changes** the active object, and is the variation a **policy** or a **lifecycle**?
> [!NOTE]
> ***Your Answer***
>
> They look alike in code: in both, a context delegates to a polymorphic object and swaps it to change behaviour. The difference is who changes the active object, and why.
>
> In **Strategy**, the **client** chooses the active object from outside, and the variation is a **policy**: different ways of doing the same job that are all valid at the same time. In my lab, the operator picks conservative or aggressive in the dashboard, and it stays that way until they change it. The strategies don't know about each other and never switch themselves.
>
> In **State**, the **object itself** (or its state objects) changes the active state as things happen, and the variation is a **lifecycle**: modes the object passes through, like a ticket going from open to closed, or a device from idle to watering to faulted. Each state usually knows which states can come next, and the allowed actions depend on the current mode.
>
> The question I ask is "who changes the active object?" If an outside choice changes it, it's Strategy. If the object's own events move it along, it's State.
 
9. Contrast Strategy with **Adapter** (Phase 5) and with **Builder** (Phase 4). Which one translates a foreign API, which one assembles a valid aggregate, and which one swaps an algorithm?
> [!NOTE]
> ***Your Answer***
>
> - **Adapter translates a foreign API.** In Phase 5, each sensor source (simulation, vendor stub, MQTT payload) speaks its own format, and adapters such as `MqttSensorAdapter.translate(...)` convert it into one common `Reading` behind `SensorPort`. The behaviour is the same ("give me a reading"); only the interface is different.
> - **Builder assembles a valid aggregate.** In Phase 4, `LocationConfigBuilder` collects a location name and zones step by step, and `build()` validates everything (name required, at least one zone, low < high, unique zone names) before anything is saved. It's about *constructing* one valid complex object.
> - **Strategy swaps an algorithm.** In Phase 6, conservative and aggressive are different *decisions* on the same input, and the operator can switch between them at runtime.
>
> The three phases also connect: Builder created the zones and thresholds, Adapter got the readings into `sensor_readings` in one format, and Strategy uses both to make its decision.
 
10. A classmate writes one “mega-strategy” that still contains `if conservative` / `if aggressive` inside a single class. Another strategy class calls the actuator adapter to water immediately. Explain why each is a trap.
> [!NOTE]
> ***Your Answer***
>
> **The mega-strategy** only *looks* like the pattern. The `if/elif` chain has just moved from the router into a class, so all the original problems are still there: adding a policy means editing that class, every branch must be tested through one method, and two people adding policies will conflict in the same file. There is no polymorphism. The registry and the interface become decoration, because the real choice still happens in a conditional. In my design, each policy is its own class, the registry only maps a key to an object, and adding a third policy (for example a light-aware one) means one new class plus one registry entry, without changing any existing class.
>
> **The strategy that calls the actuator** mixes deciding with executing. Evaluating would then have side effects: every press of "Evaluate," every test run and every dashboard refresh could start a real pump. The strategy would depend on infrastructure (the actuator adapter), so it could no longer be unit tested with a plain context. There would be no chance to preview, log or confirm the action, and every other strategy would have to duplicate the same execution code. Failures in the pump (a timeout, a device offline) would also become the decision code's problem. A strategy should only return a `Recommendation`; carrying it out belongs to a separate step, which is the later Command pattern using the actuator port.