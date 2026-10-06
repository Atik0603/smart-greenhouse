## A. Pattern

### 1. State the intent of Adapter in plain language. What problem appears when business code speaks a vendor or legacy protocol (odd field names, units, XML, status codes) directly?

> [!NOTE]
> 
>
> Adapter lets my code work with something whose interface doesn't fit, by putting a small translator in between. My application defines the interface it wants (a port), and each adapter converts one foreign format into it, like a travel plug adapter between my laptop and a foreign socket.
>
> If business code spoke the vendor protocol directly, the vendor's field names (`rawPermille`, `timestampMs`), units, error formats and quirks would spread through services and routers. Every caller would need its own conversions and `if vendor == ...` branches, so the same translation would be repeated and could drift. Swapping or adding a vendor would mean editing business logic, and testing that logic would require the real SDK or protocol. The application ends up shaped by someone else's design instead of its own.

### 2. Name the participants (target / port, adaptee, adapter, client). What does the adapter translate, and what must it not decide (business policy)?

> [!NOTE]
> 
>
> - **Target / port:** the interface my application wants. In my lab that's `SensorPort.read(device) -> Reading` (and `ActuatorPort.apply(...)`).
> - **Adaptee:** the thing with the incompatible interface, e.g. `AcmeSensorSdkStub.fetch(serial, kind)` returning vendor-shaped dicts, or an MQTT payload dict.
> - **Adapter:** implements the port and translates: `VendorStubSensorAdapter`, `MqttSensorAdapter`, `SimulationSensorAdapter`.
> - **Client:** code that only knows the port. Here that's `ReadingIngest`, and through it the sampler and the read endpoint.
>
> The adapter translates **shape and representation**: field names, units and scales (`rawPermille / 1000` → vwc), timestamp formats (epoch ms → timezone-aware UTC datetime), and errors (vendor `KeyError` → my `SensorReadError`). It must not decide **business policy**: whether to water, what counts as too dry, which zone thresholds apply, or when to sample. It reports what the device says, in my format, and nothing more.

### 3. GoF distinguishes an object adapter (composition) from a class adapter (inheritance). Which does modern code prefer, and why?

> [!NOTE]
> 
>
> Modern code prefers the **object adapter**: the adapter *holds* an instance of the adaptee and calls it. My `VendorStubSensorAdapter` does this: it receives an `AcmeSensorSdkStub` in its constructor and calls `self._sdk.fetch(...)`.
>
> Composition is preferred because:
> - The adapter exposes **only the port's interface**. With a class adapter (inheriting from both the port and the adaptee), all the vendor's methods would also be callable on the adapter, leaking the foreign API back into my code.
> - The adaptee can be **swapped**, e.g. a fake SDK with a fixed random seed in tests, or a different SDK version, without changing the adapter class.
> - It works with adaptees I can't or shouldn't subclass (final classes, objects created by a vendor factory), and it avoids multiple inheritance and the tight coupling to the adaptee's internals that comes with it.

## B. This phase of the application

### 4. What is `SensorPort` in this lab, and what normalized value type (for example `Reading`) do adapters return? Why do application services depend on the port rather than on a simulation driver or vendor SDK?

> [!NOTE]
> 
>
> `SensorPort` is an abstract base class in the domain layer with one method, `read(device: Device) -> Reading`. It has no FastAPI, SQLAlchemy, Pydantic or network code. Every adapter returns a `Reading`: a frozen value object with `device_id`, `value` (float), `unit` (`vwc`, `lux`), `source` (`simulation`, `vendor`, `mqtt`) and a timezone-aware `recorded_at`. `Reading` validates its own timezone and source, so no adapter can produce a broken one.
>
> `ReadingIngest` depends on the port because then it doesn't care where a value came from. It receives a selector function, calls `.read(device)`, and saves the `Reading`. That means adding a new device type only adds an adapter and a selector entry; the service, sampler, routers and database schema stay unchanged. It also keeps the service testable without a vendor SDK, and keeps device-specific code in one layer (infrastructure) instead of spreading it into business logic.

### 5. You need three translations onto the same normalized reading: a simulation adapter, a vendor stub, and an MQTT translator that accepts a payload dict. Why is the different raw shape the point of the exercise? How does `source` (`simulation`, `vendor`, or `mqtt`) show which adapter produced the reading, and why must the MQTT translator not open a broker in this phase? Phase 12 may deliver that same dict on a device HTTP route or through an optional broker — why must this phase still not open either transport?

> [!NOTE]
> 
>
> Translation only means something if the inputs actually differ. If every adapter received data already shaped like `Reading`, there would be nothing to adapt. That's why my vendor stub deliberately uses `kind: "SOIL"`, `rawPermille`, `rawDeciLux` and `timestampMs`, and the MQTT input is a loose dict with optional fields. Three different inputs end up as one identical `Reading` type, which is the pattern's whole value.
>
> Each adapter writes its own fixed `source` value, so every stored row records which adapter produced it. The UI shows it as a badge, and it's useful for debugging and for later phases that may treat simulated and real data differently.
>
> The MQTT translator must not open a broker because translation and transport are separate responsibilities. `translate(device_id, payload)` is pure: dict in, `Reading` out, which I can test with a plain dict (my test even replaces `socket.socket` to prove no connection is made). Opening a broker or an HTTP route now would add infrastructure that can fail, slow down or need configuration, before anything uses it, and it would mix "how a message arrives" into "what a message means." In Phase 12, the device HTTP route or the optional broker subscriber will receive the same dict and call this same `translate()` and then `ReadingIngest.record(..., reading=...)`. The transport is added around a translator that already works and is tested, and nothing in this phase has to change.

### 6. Readings are appended to `sensor_readings` (history grows). Why not keep only the latest value in memory or overwrite a single row, and which later phase consumes this history? Why do a manual read, the simulation sampler, and (later) MQTT share one writer of that table? Why does the sampler skip devices with tracking off and MQTT devices, and why do sensor cards poll the latest stored reading until Phase 12?

> [!NOTE]
> 
>
> Values only in memory disappear on every restart or reload, and a single overwritten row loses everything except the last moment. Appending rows keeps a real history. Phase 6 (Strategy) evaluates each zone using the latest moisture among that zone's sensors, read from this table; Phase 7's overview shows latest readings per zone; and the optional Phase 13 charts plot the history. The `(device_id, recorded_at DESC)` index keeps "latest per device" fast as the table grows.
>
> All writes go through `ReadingIngest.record` so the rules are applied in exactly one place: the device must exist and be a sensor, the reading must belong to that device, and every row has the same normalized shape. It also gives Phase 11 (Observer) a single point at which to publish `reading.created`, no matter whether the reading came from a button, the sampler or MQTT.
>
> The sampler skips **tracking off** devices because the user explicitly turned automatic sampling off for them. It skips **MQTT** devices because they push their own readings; the backend can't pull from them, and generating values for them would mix invented data into a real device's history. Both filters are in the database query, so they can't be forgotten.
>
> The cards poll `GET …/readings?limit=1` every few seconds so that sampler-generated rows appear without a manual click, and because the value comes from the database, a page refresh still shows the last stored reading. Polling is a temporary approach: Phase 12 adds a WebSocket that pushes `reading.created` to the dashboard, so the browser no longer has to keep asking.

### 7. `POST /api/sensors/{id}/read` runs an adapter, persists, and returns a DTO. What HTTP status is appropriate when the device is missing versus when the adapter fails? Why must the router never see vendor-shaped types?

> [!NOTE]
> 
>
> A **missing device** is **404 Not Found**: the resource in the URL doesn't exist (`DeviceNotFoundError`). An **adapter failure** is a **400**-level error with a readable `detail`, following the phase requirements: I return 400 for `SensorReadError`, which covers an MQTT device being push-only, an actuator not being a sensor, an unknown device type or a malformed vendor payload. A successful read returns **201 Created**, since it creates a new row. (For a real network device that fails to respond, a 5xx such as 502 could also be argued, since the failure would be upstream rather than in the request, but the requirements ask for 400 here.)
>
> The router must never see vendor-shaped types because then the translation would no longer be contained. If the router handled `rawPermille` or vendor exceptions, it would depend on that vendor, and changing vendors would mean changing HTTP code. In my design the router only knows `ReadingIngest`, `ReadingDto` and two domain errors. Vendor field names exist in exactly one file, `vendor_stub.py`.

## C. Compare, contrast, and scenarios

### 8. Contrast Adapter with Facade. Adapter changes the shape of an existing interface; Facade simplifies how to use a subsystem. Give a greenhouse-shaped example of each (Adapter this phase; Facade in Phase 7).

> [!NOTE]
>
>
> **Adapter** makes one existing interface fit a different expected interface. The amount of functionality stays about the same; only the shape changes. In this phase, `VendorStubSensorAdapter` wraps the vendor's `fetch(serial, kind)`, which returns `{"kind": "SOIL", "rawPermille": 412, ...}`, and presents it as `SensorPort.read(device) -> Reading`.
>
> **Facade** offers one simple entry point in front of a whole subsystem with many parts. It doesn't translate one interface into another; it hides how several pieces are combined. In Phase 7, a greenhouse overview could be a facade: one call such as "get the overview for this location" that internally uses the location repository, the zones, the device assignments and the latest readings, so the dashboard doesn't have to call and combine five services itself.
>
> In short: Adapter answers "this doesn't fit"; Facade answers "this is too complicated to use directly."

### 9. Contrast Adapter with Decorator. Both wrap an object. What is different about the interface they present to the client?

> [!NOTE]
> 
>
> An **Adapter** presents a **different** interface from the object it wraps. The wrapped vendor SDK offers `fetch(serial, kind)`; the adapter offers `read(device)`. Its purpose is to convert.
>
> A **Decorator** presents the **same** interface as the object it wraps and adds behaviour around it. In Phase 9, a decorator will implement `ActuatorPort` and wrap another `ActuatorPort` (for example my `SimulationActuatorAdapter`), adding things like logging, safety limits or retries before passing the call on. Because the interface is unchanged, decorators can be stacked, and the client can't tell whether it's talking to the plain adapter or a decorated one. An adapter can't be stacked that way, because its inside and outside interfaces differ.

### 10. A classmate puts irrigation policy ("if moisture < 0.3 then water") inside the vendor adapter. Why is that a trap? Where should that decision live instead (later Strategy), and what should stay in the adapter?

> [!NOTE]
>
>
> It mixes two jobs with different reasons to change. Translation changes when the *vendor* changes; irrigation policy changes when the *greenhouse rules* change. Putting policy in the adapter causes several problems:
> - The rule only applies to devices that happen to use that vendor. Simulation and MQTT sensors would need copies of it, and the copies would drift.
> - The hard-coded `0.3` ignores the per-zone thresholds from Phase 4. The adapter doesn't know the device's zone, and shouldn't.
> - Reading a sensor would cause side effects (watering), so a simple "Read now" or a test read could turn on a pump.
> - The policy couldn't be tested or swapped without the vendor adapter.
>
> The decision belongs in the application layer, in Phase 6's Strategy: for each zone, an evaluation strategy compares the zone's own thresholds with the latest moisture from the sensors assigned to that zone, and decides what to do. Different strategies can then be swapped without touching any device code. The adapter should keep only translation (raw format → `Reading`, vendor errors → `SensorReadError`) and, for actuators, applying a command it's given. That's the rule in the requirements: translation and apply only.