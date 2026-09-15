1. State the intent of Factory Method in plain language. What problem appears when callers scatter new / constructors (or a growing if type == ...) across the application?


Factory Method's intent is to separate deciding what to create and how to configure it from using the thing once it exists. Instead of a class exposing "here's a constructor, figure out the right arguments yourself," a creator exposes one method that returns a ready-to-use object, and the caller never touches the constructor directly.

The problem with scattered new/constructors or a growing if type == ...: every caller that needs to create an object has to know every concrete type that exists and that type's configuration details (defaults, required arguments, validation). When a new variant is added, you don't add code in one place — you have to find and edit every call site that has that if/elif chain, and it's easy to miss one or let defaults drift out of sync between them.

2. Name the main participants of Factory Method (product, concrete product, creator, concrete creator, client). For each, give one sentence: what it is responsible for.


Product — the common interface/type that client code depends on after creation; it doesn't know or care which concrete creator built it.
Concrete product — one specific implementation of that interface .
Creator — declares the factory method's signature 
Concrete creator — implements the factory method for exactly one variant, owning that variant's defaults/configuration.
Client — the code that asks a creator for a product and then uses the product interface; it depends on the creator/product abstractions, never on concrete constructors.

3. How do you add a new product variant when creators are polymorphic (new class + registry entry) versus when creation lives in one shared if/elif function? Why does that difference matter for extension?

With polymorphic creators, adding a variant means writing one new class (the new concrete creator) and adding one line to the registry — nothing that already exists gets modified. With a single shared if/elif function, adding a variant means editing that function's body directly, which risks breaking existing branches, requires re-testing the whole function (not just the new piece), and means every caller of that function is coupled to a growing pile of type-specific knowledge in one place. The difference matters because it's the classic "closed for modification, open for extension" idea — extension by addition is safer than extension by editing shared code.

4. In this lab, what is the product and what are the concrete creators? Why must the API handler (or sensor service) go through a creator/registry instead of constructing MoistureSensor / LightSensor itself?

The product is the Sensor domain entity — a plain data object (device_type, display_name, default_config, id) that the rest of the app (repository, API, frontend) works with uniformly regardless of which sensor type it represents. The concrete creators are MoistureSensorCreator and LightSensorCreator, each producing a Sensor with that type's specific defaults.

The API handler/service must go through the registry rather than constructing Sensor(device_type="moisture_sensor", ...) directly because that would mean the interfaces layer (or application layer) has to know each type's exact default configuration itself — duplicating knowledge that belongs to the creators, and reintroducing the same "edit this function for every new type" problem the pattern exists to avoid.

5. POST /api/sensors accepts a short type key such as "moisture" or "light", while the stored/returned field is device_type (for example moisture_sensor). Why are those two fields different? Who decides the stored device_type and default_config?

type ("moisture", "light") is a short lookup key — it's only used to find the right creator in the registry dict; it's an API/interface-layer concern. device_type ("moisture_sensor", "light_sensor") is the actual domain value stored on the Sensor entity and persisted to the database — it's more descriptive/canonical because it's meant to be meaningful data, not just a dispatch key.

The concrete creator decides both device_type and default_config — that's the whole point of the pattern: each creator hard-codes the domain value and defaults appropriate to its type, so nothing upstream (the router, the service) has to know those specifics.

6. Why is there a single devices table with role="sensor" instead of a dedicated sensors table? What later phase does that choice prepare for?

A single table with a role discriminator column lets multiple related device categories share one schema and one set of common columns (id, type, display name, config, timestamp) without duplicating structure across separate tables. It prepares specifically for Phase 3, which adds actuators into this same devices table — if sensors had their own dedicated table, Phase 3 would need either a second near-identical table or a migration to merge/restructure, instead of just inserting rows with role="actuator".

7. What should happen when the client posts an unknown type? Where should that rejection be decided (registry/service vs router constructing a concrete class anyway)?

An unknown type should be rejected before any database write — the registry lookup (SENSOR_CREATORS.get(type_key)) returning None is where that's decided, in the application service, which raises a domain-level error (UnknownSensorTypeError). The router then translates that into an HTTP 400. The rejection must happen in the registry/service layer, not by falling through to "construct some default concrete class anyway" — silently defaulting to a real sensor type would insert bad/misleading data instead of surfacing the caller's mistake.

8. Contrast Factory Method with a simple factory (one function full of if type == ...). When is the simple factory “good enough,” and why does this phase still want polymorphic creators?

A simple factory (one function, if type == ..., returning the right object) is genuinely good enough when there are very few variants, they rarely change, and centralizing the branching in one readable function doesn't create real pain yet — it's simpler to read than a full creator-class hierarchy for a trivial case. This phase wants polymorphic creators instead because sensor types are an explicit extension point the course intends to grow (temperature next, per the exercise; more in later phases), and each type's defaults are naturally owned by its own small class rather than crowded into one growing function's body.

9. Contrast Factory Method with Abstract Factory (Phase 3). Factory Method answers which question? Abstract Factory answers which different question? Why is Factory Method enough for Phase 2 sensors?

Factory Method answers: "which concrete product should I build, this one time, for this one request?" — it produces a single object. Abstract Factory answers a different, broader question: "which whole family of related products, that must all match/be consistent with each other, should I build together?" — e.g. a PDF export kit needing a matching cover + TOC + body, all from the same "family."

Factory Method is enough for Phase 2 because sensors are independent of each other — creating a moisture sensor has no consistency requirement with creating a light sensor at the same time. There's no "family" that needs to stay matched, so the added structure of Abstract Factory (Phase 3, when actuators + sensors may need to be created together as a device_family) isn't needed yet.

10. A classmate puts SQLAlchemy session commits (or FastAPI request parsing) inside a concrete creator. Why is that a trap? Where should persistence and HTTP stay instead?
Putting SQLAlchemy commits or FastAPI request parsing inside a concrete creator breaks the domain layer's independence — the whole reason Sensor and the creators avoid importing SQLAlchemy/FastAPI/Pydantic is so they can be tested and reasoned about without a database or HTTP framework at all. If a creator did its own commit, then we couldn't test its defaults without spinning up Postgres, and we wouldd lose the clean separation where the service orchestrates "create, then save" as two distinct steps. Persistence belongs in the repository (infrastructure layer); HTTP parsing/validation belongs in the router (interfaces layer). A creator's only job is producing a correctly-configured in-memory Sensor.