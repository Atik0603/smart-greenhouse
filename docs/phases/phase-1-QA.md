## A. Pattern

**1. What is a design pattern? What is it not?**
A design pattern is a reusable, named solution shape to a design problem that recurs across different projects. It is a way of arranging classes/objects and their responsibilities. It is like using a design stategy to solve reaccuring problem in the code base.

**2. Three GoF families + placement**
- Creational: concerned with how objects get created, so the system isn't tightly coupled to concrete classes when instantiating them.
- Structural: concerned with how classes/objects are composed into larger structures while keeping those structures flexible.
- Behavioral: concerned with how responsibility and communication are distributed between objects.
- Factory Method → Creational.
- Strategy → Behavioral.

**3. When to skip a pattern / risk of applying too early**
We skip a pattern when the feature is small, stable, and unlikely to grow. Applying a pattern too early risks over-engineering. We pay ongoing complexity and maintenance cost for flexibility the project doesn't actually need yet, which can make the code harder to read and change than if we just had written it plainly.

## B. This phase of the application

**4. Why ship an empty-but-running slice?**
Phase 1 proves that the whole chain Docker, Postgres, FastAPI, Alembic, and the React frontend actually integrates end-to-end, before any real business logic exists. A folder of unimplemented classes would prove the code compiles/parses, but says nothing about whether the pieces can actually talk to each other in practice (wrong ports, broken CORS, bad connection strings, etc. all things that only surface when we actually run the stack together).

**5. Four backend layers**
- domain: core business rules/entities, framework-agnostic. Must not contain FastAPI routes or SQLAlchemy models.
- application: use cases that orchestrate domain logic. Must not contain raw SQL or HTTP-specific code.
- infrastructure: settings, database engine/session, external system connectivity. Must not contain HTTP routing.
- interfaces/api: FastAPI app entry and routes. Must not contain core business rules — it should just translate HTTP requests into calls on the layers below.

**6. /health and /scalar**
`/health` returns `{status: "ok"|"degraded", db: "ok"|"fail"}`. It checks the database rather than just reporting the process is alive because a process can be running while its database dependency is down or misconfigured, reporting only "process up" would hide real failures that matter operationally. 
`/scalar` is used for API docs per the course's tooling choice, and `/docs` (FastAPI's built-in Swagger UI) is disabled to avoid having two competing docs UIs live at once.

**7. Why Alembic before any schema?**
Introducing the migration toolchain before any product schema proves migrations actually run cleanly against the real Postgres instance early, when there's nothing at stake yet. If we created tables by hand first and added migrations later, the database's real state and  migration history would already be out of sync from day one. Alembic wouldn't have a true baseline to diff against, making later migrations unreliable and hard to reproduce across environments/teammates.

## C. Compare, contrast, and scenarios

**8. Dependency direction**
Dependencies point inward: interfaces/api and infrastructure may depend on domain and application, but never the reverse. Domain code must not import FastAPI, SQLAlchemy, or HTTP-schema Pydantic models because domain logic should stay independent of any specific framework or delivery mechanism. swapping the web framework or database library later shouldn't force changes to core business rules.

**9. Frontend can't show a healthy badge**
Check, in order: is the backend actually running and reachable on the expected port; is CORS configured to allow the frontend's origin; does the `/health` response actually match the shape the frontend expects (`status`, `db`). This is a Phase 1 concern, not a later-pattern concern, because none of it involves business logic or GoF patterns at all, it's purely about whether the stack's plumbing (network, CORS, contract) is wired correctly.

**10. What's still missing after Phase 1**
Still missing: real business entities and use cases (e.g. devices, sensor readings), any actual data persisted through migrations beyond the baseline, and any GoF patterns applied to real problems. Later phases add behavior by building on top of the existing layers — new domain entities, new use cases, new routes without needing to restructure the foundation. since the layering and tooling were already proven out in Phase 1.