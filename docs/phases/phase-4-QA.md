## A. Pattern

### 1. State the intent of Builder in plain language. Why does construction of a complex object need stepwise assembly and validation at the end (`build()`), instead of a telescoping constructor or a half-filled dict written straight to the database?

> [!NOTE]
> **Your Answer**
>
> Builder lets me put a complex object together step by step, and only hands me the finished object once a single `build()` call has checked that the whole thing is valid. If any rule fails, `build()` raises an error and no product exists.
>
> A location is a good example: it has a name and a variable number of zones, each with thresholds and a schedule, plus rules that involve several fields at once (at least one zone, unique zone names, low < high). A telescoping constructor with many parameters and defaults happily creates an object with a missing piece, such as zero zones, and nothing notices because the object looks complete. Positional arguments are also easy to pass in the wrong order. A half-filled dict written straight to the database is worse: it skips validation entirely, so each code path has to remember its own checks and they drift apart. With a builder, all the rules live in `build()`, and anything that reaches the database has passed them.

### 2. Name the main participants (product, builder, optional director, client). Until `build()` succeeds, is the intermediate object a finished domain product? Why does that distinction matter?

> [!NOTE]
> **Your Answer**
>
> - **Product:** `LocationConfig`, containing a frozen `Location` with a tuple of frozen `Zone`s. It is only created by `build()`.
> - **Builder:** `LocationConfigBuilder`, which stores the name and zones in progress, offers the steps `with_name()` and `add_zone()`, and validates in `build()`.
> - **Director (optional):** a fixed sequence of builder steps. In my lab the mapper `build_config_from_request()` plays this role by turning the request DTO into `with_name` + one `add_zone` per zone + `build()`. The UI wizard is the user-facing version of the same sequence.
> - **Client:** `LocationConfigService`, which asks for a built config and then passes it to the repository.
>
> No. Until `build()` succeeds, all I have is the builder's internal scratch state (a name and a list of zones), not a product. It may be incomplete or invalid, for example with no zones yet. The distinction matters because only a product can be trusted by the rest of the system. The service only ever saves what `build()` returned, so it's impossible to persist something that is still halfway through being assembled.

### 3. List at least three kinds of invalid configuration a location/zone `build()` should reject in this lab (name, zones, moisture thresholds). Why must those rules live in the domain builder, not only in the HTTP layer?

> [!NOTE]
> **Your Answer**
>
> My `build()` rejects:
> - a missing or blank location name
> - a location with no zones
> - a zone with an empty name
> - thresholds outside the VWC range 0.0–1.0
> - a low threshold that is not strictly less than the high one (including equal values)
> - two zones with the same name in one location (case-insensitive)
>
> These rules describe what a valid location *is*, so they belong to the domain. The HTTP endpoint is only one way in: tests, scripts, a future import or another endpoint can also create locations, and if the rules lived only in FastAPI/Pydantic, those paths would skip them. Keeping them in the domain also lets me reuse them: my zone add/edit endpoints call the same `validate_zone_fields()` that `build()` uses, so there is exactly one definition of a valid zone. It also means the rules can be tested without HTTP or a database, which is what my builder unit tests do.

## B. This phase of the application

### 4. What aggregate does the builder produce (location plus zones)? Why does this course use `location_id` (and never `greenhouse_id`) as the name for that scope?

> [!NOTE]
> **Your Answer**
>
> The builder produces a `LocationConfig` wrapping a `Location` aggregate: the location's name plus a tuple of its zones, each zone with a name, low/high moisture thresholds and a schedule. The location is the root; the zones only exist as part of it, which is why they are saved together and deleted with it (`ON DELETE CASCADE`).
>
> The scope being configured is a location, such as a bay or room, not the whole greenhouse. Naming it `location_id` everywhere (zones, devices, DTOs, routes) keeps the naming accurate and consistent, and it allows several locations inside one greenhouse product without renaming anything later. Later phases (automation rules, alerts, the overview) also refer to `location_id`, so using one name from the start avoids mismatched columns and confusing mappings.

### 5. Describe the path from API request to persistence: DTO → builder steps → `build()` → repository. What must not be persisted if `build()` raises `ConfigurationError` (or equivalent)? Why does assigning a device wait until the zone row exists, and why does the client send only `zone_id`?

> [!NOTE]
> **Your Answer**
>
> 1. `POST /api/locations/config` receives JSON, which FastAPI parses into `LocationConfigCreateRequest` (types only).
> 2. `LocationConfigService.create_config()` calls the mapper `build_config_from_request()`, which runs `with_name(location_name)` and one `add_zone(...)` per zone.
> 3. `build()` validates and returns an unsaved `LocationConfig` (all ids `None`), or raises `ConfigurationError`.
> 4. Only on success does `LocationRepository.save_config()` write the location and its zones in one transaction and read them back with their new ids.
> 5. The router maps the result to `LocationConfigResponse`; a `ConfigurationError` becomes HTTP 400.
>
> If `build()` raises, nothing is persisted: no location row and no zone rows. The repository is never even called.
>
> A device can only be assigned to a zone that has an id, and a zone only gets its id when its row is saved, so assignment has to happen afterwards through `ZoneAssignmentService`, not inside the builder. The client sends only `zone_id` because the location is a *consequence* of the zone: the service reads the zone's `location_id` and writes both columns in the same update. If the client could send its own `location_id`, a device could end up claiming to be in a zone of Bay A while its location says Bay C.

### 6. Saving a location and its zones must be one transaction. What goes wrong if the location row commits and a later zone insert fails? How does that relate to "no half-built aggregates in the database"?

> [!NOTE]
> **Your Answer**
>
> If the location were committed on its own and then a zone insert failed, the database would contain a location with some or none of its zones. That breaks the rule `build()` just enforced ("at least one zone"), even though the builder approved the config. The API would return an error, yet the half-saved location would still appear in the list, and later features that expect every location to have zones would misbehave.
>
> My `save_config()` avoids this: it inserts the location, uses `flush()` to get its generated id inside the open transaction, inserts all the zones with that id, and commits once. On any exception it calls `rollback()`, which also undoes the flushed location. So the whole aggregate is saved or nothing is. This is the database side of the same principle as the builder: `build()` stops half-built objects from existing in memory, and the transaction stops them from existing in the database.

### 7. The configuration wizard UI collects fields in steps. How does that UI map to Builder without turning React (or the HTTP handler) into the place that owns domain validation?

> [!NOTE]
> **Your Answer**
>
> The form mirrors the builder's steps: a location-name field (like `with_name`) and an "Add zone" button that adds another zone row (like `add_zone`). But React only collects input; it doesn't build or save anything piece by piece. On submit it sends one request with the whole configuration, and the backend runs it through the real builder.
>
> The frontend does run some quick checks (empty name, 0–1 range, low < high, duplicate names), but only to give instant feedback. The domain `build()` is still the authority: if the server returns 400, the UI shows the server's message. The HTTP handler stays thin as well. It passes the DTO to the service and translates `ConfigurationError` into a 400, without containing any rules itself. If I removed the frontend checks, the system would still reject every invalid config, just with a server message instead of an inline one.

## C. Compare, contrast, and scenarios

### 8. Contrast Builder with Factory Method and with Abstract Factory. Which pattern answers "which type?", which answers "which matching kit?", and which answers "how do we assemble one valid whole in steps?"

> [!NOTE]
> **Your Answer**
>
> - **Factory Method** answers "which type?". In Phase 2, a creator such as `MoistureSensorCreator` decides how to build one sensor with type-specific defaults, in one call.
> - **Abstract Factory** answers "which matching kit?". In Phase 3, `SimulationDeviceFactory` or `EdgeDeviceFactory` creates a whole set of sensors and actuators that belong to the same family.
> - **Builder** answers "how do we assemble one valid whole in steps?". In Phase 4, `LocationConfigBuilder` collects a name and any number of zones supplied by the client, then validates the whole configuration in `build()`.
>
> The main difference is who supplies the details and when the object exists. With the factories, the factory knows the recipe and returns a finished object immediately. With Builder, the client supplies the parts gradually, and the finished object only exists after validation passes.

### 9. Fluent method chaining (`builder.add_zone(...).build()`) is a coding style. Why is a fluent interface not the same thing as the Builder pattern?

> [!NOTE]
> **Your Answer**
>
> A fluent interface only means that methods return `self` so calls can be chained on one line. It's about how the code reads. Plenty of classes that aren't builders are fluent (query builders, string formatters), and a builder works just as well without chaining:
>
> ```python
> builder = LocationConfigBuilder()
> builder.with_name("Bay A")
> builder.add_zone("North", 0.2, 0.4)
> config = builder.build()
> ```
>
> What makes it Builder is the structure: a separate object accumulates parts in steps, and a final `build()` validates the whole thing and returns an immutable product, or refuses. A class could offer chained setters that modify a live domain object with no final validation, and it would be fluent but not a builder, because nothing stops a half-configured object from being used.

### 10. A classmate validates thresholds only in FastAPI / Pydantic and leaves `build()` empty. Another mutates builder fields after `build()` while treating the product as immutable. Explain why each is a trap.

> [!NOTE]
> **Your Answer**
>
> **Validating only in FastAPI/Pydantic:** the builder then accepts anything, so every path that doesn't go through that exact endpoint (tests, scripts, a future import, another endpoint) can create invalid locations. It also splits the rules: the zone add/edit endpoints would need their own copy, and copies drift. There is a practical problem too: Pydantic errors return 422, while the requirements expect 400 with a domain message. Pydantic should check types; the domain should check business rules.
>
> **Mutating the builder after `build()`:** this is a trap if the product shares data with the builder, for example if `build()` passed the builder's own `list` of zones into the product. Adding a zone to the builder afterwards would silently change a location that was already validated, and possibly already saved, without `build()` ever re-checking it. I avoid this by converting the list to a `tuple` in `build()`, using `frozen=True` dataclasses, and copying the schedule dict in `add_zone()`, so the product doesn't share mutable state with the builder. Even so, the right habit is to treat a builder as used up after `build()`: for another config, start a new builder, and to change a saved location, use the zone management operations.