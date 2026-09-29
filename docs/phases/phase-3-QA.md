## A. The pattern

### 1. State the intent of Abstract Factory in plain language. What goes wrong when related products are chosen independently (`if format` for each piece) instead of as a family?

> [!NOTE]
> **Your Answer**
>
> Abstract Factory gives the client one factory that creates a whole set of related objects that are guaranteed to belong together, without the client naming any concrete classes. The client picks a family once and gets a consistent kit.
>
> When each piece is chosen with its own `if`, nothing connects those choices. Each object can be individually valid while the combination is wrong — for example a simulated moisture sensor paired with a real edge water pump. The code still runs, so the bug is silent until something downstream fails. The conditionals also get duplicated for every product, so adding a new family means editing every branch, and copy-pasting a piece from one family's branch into another is an easy mistake.

### 2. Name the main participants (abstract factory, concrete factory, abstract products, concrete products, client). How does choosing a factory at the start commit the client to one family?

> [!NOTE]
> **Your Answer**
>
> - **Abstract factory** (`DeviceFamilyFactory`): declares one creation method per kind of product (`create_sensors()`, `create_actuators()`) plus `create_device_set()` for the whole kit.
> - **Concrete factory** (`SimulationDeviceFactory`, `EdgeDeviceFactory`): implements those methods for exactly one family.
> - **Abstract product** (`Device`, with role sensor/actuator): the type the client works with.
> - **Concrete products**: the family-specific devices each factory builds (e.g. "Sim water pump" vs "Edge pump relay", with different protocols and config).
> - **Client** (`DeviceFamilyService`): chooses a factory and uses what it returns, never constructing devices itself.
>
> The client resolves the factory once (`get_family_factory(family)`) and then gets every device through that same object. A concrete factory can only produce its own family's devices, so after that first choice there is no code path through which a device from another family could enter the kit. Consistency is guaranteed by the structure rather than by repeated checks.

### 3. When should you use Abstract Factory, and when should you skip it (for example only one product type per request, or mixing siblings is valid)?

> [!NOTE]
> **Your Answer**
>
> Use it when products naturally form families that must not be mixed (simulation vs edge hardware, UI themes, platform widgets), when the environment is chosen once and then many related objects are created from it, and when we want new families to be addable without changing client code.
>
> Skip it when only one product type is created per request (Factory Method is enough, as in Phase 2), when mixing implementations is actually valid so there is no consistency rule to enforce, or when there are so few families and products that a simple configuration object is clearer. It is also a poor fit when new *kinds* of product are added often, because every concrete factory must then be updated.

## B. This phase of the application

### 4. In this lab, what is a device family, and what does `create_device_set()` (or your equivalent) return? Why must a simulation kit and an edge kit not mix incompatible siblings?

> [!NOTE]
> **Your Answer**
>
> A device family is the environment a set of devices belongs to: `simulation` (development/test devices with simulated values) or `edge` (stub hardware devices with I2C/GPIO protocol settings). It is stored as `device_family` on each device row.
>
> `create_device_set()` returns a list of four domain `Device` objects: two sensors (moisture, light) and two actuators (water pump, grow light), all with the same `device_family` and that family's config.
>
> They must not mix because the devices are designed to work together. A simulated sensor produces fake readings; if it controlled a real edge pump, the pump would act on data that doesn't reflect the real greenhouse. Mismatched protocols (`simulated` vs `gpio`) also mean the devices couldn't communicate as a coherent set.

### 5. Phase 2 Factory Method creators still exist. How does Abstract Factory compose them rather than replace them? What would you lose if you deleted the sensor creators and inlined all construction inside the family factory?

> [!NOTE]
> **Your Answer**
>
> Each family factory builds its sensors by calling the Phase 2 creators through `SENSOR_CREATORS["moisture"]` and `SENSOR_CREATORS["light"]`. The resulting `Sensor` is converted into a `Device` by `_sensor_as_device()`, which adds `role="sensor"`, the family key, and the family's extra config (e.g. `protocol`). Sensor-type knowledge stays in the creators; the family factory only adds family-level knowledge on top.
>
> If the creators were deleted and inlined, each sensor type's defaults (unit, sampling interval, moisture threshold) would be duplicated in every family factory. Changing a default would mean editing every family, and the copies could drift apart. `/api/sensors` and the Phase 2 creator tests depend on the creators, so they would break too. The separation of responsibilities — "what a moisture sensor is" vs "what a simulation kit contains" — would be lost.

### 6. Why add a `device_family` column on the existing `devices` table (with a default/backfill such as `"simulation"`) instead of a new table per family? What happens to Phase 2 sensor rows if you forget the backfill?

> [!NOTE]
> **Your Answer**
>
> A family is a label on a device, not a different kind of data: simulation and edge devices have exactly the same columns. One table with a `device_family` column (plus an index for filtering) keeps all devices in one place, so listing and filtering is a simple `WHERE`, and adding a new family requires no migration at all. A table per family would duplicate the schema and need a new table for every family. It follows the same reasoning as the Phase 2 `role` column.
>
> Without a backfill, adding a `NOT NULL` column fails outright, because the existing Phase 2 rows have no value for it. If the column were made nullable instead, the old sensors would have `NULL` family: they would disappear from any family-filtered list, and mapping them to `DeviceDto` (where `device_family` is a required string) would fail. The `server_default="simulation"` gives every existing row a valid family during the migration.

### 7. `POST /api/devices/provision` returns a kit (expected size: two sensors and two actuators). `GET /api/devices` can filter by `family` and `role`. Why must the UI be able to filter by family? Why do `/api/sensors` routes from Phase 2 still need to work?

> [!NOTE]
> **Your Answer**
>
> The user works in one environment at a time. If the list showed every family together, simulation and edge devices would appear side by side, making it easy to confuse or pair devices from different families — the exact problem the pattern prevents on the backend. Filtering by family (done in SQL, through the `family` query parameter) keeps the dashboard consistent with the backend's family boundaries, and switching families reloads only that family's devices.
>
> `/api/sensors` must keep working because each phase extends the application rather than replacing it. The dashboard's Sensors section, the Phase 2 tests, and any other client depend on those routes, and they still demonstrate Factory Method. Breaking existing endpoints to add a new feature would be a regression. The sensor save path now also sets `device_family="simulation"`, so sensors created there stay consistent with the new model.

## C. Compare, contrast, and scenarios

### 8. Draw the contrast in one paragraph: Factory Method vs Abstract Factory. Use the questions "which one product?" versus "which product line?" and mention that Abstract Factory often uses Factory Method–style methods inside.

> [!NOTE]
> **Your Answer**
>
> Factory Method answers "which one product?": a creator subclass decides how to build a single object, such as `MoistureSensorCreator` producing one moisture sensor with the right defaults, and the risk it removes is wrong configuration of that one object. Abstract Factory answers "which product line?": a concrete factory produces a whole set of related objects that must match, such as `SimulationDeviceFactory` producing two sensors and two actuators that all belong to the simulation family, and the risk it removes is mismatched siblings. The two are complementary: each creation method in an abstract factory (`create_sensors()`, `create_actuators()`) is itself a Factory Method–style method, and in this lab the family factories even call the Phase 2 creators directly. Abstract Factory is essentially several factory methods grouped under one family rule.

### 9. A DTO or HTTP handler constructs concrete simulation/edge device types directly, bypassing the family factory. What consistency bug can that reintroduce? How should HTTP stay on the abstract factory / service instead?

> [!NOTE]
> **Your Answer**
>
> It reintroduces mixed kits: the handler could create a simulation sensor next to an edge actuator, tag a device with one family but give it another family's config (e.g. `device_family="edge"` with `protocol="simulated"`), or build an incomplete kit with only sensors. It also duplicates the family defaults in the HTTP layer, where they drift from the factories, and skips the unknown-family validation. The guarantee the pattern provides only holds if every kit is created through a factory.
>
> The router should stay thin: it reads the `family` query parameter, calls `DeviceFamilyService.provision_family(family)`, converts `UnknownDeviceFamilyError` into HTTP 400, and maps the returned domain devices to `DeviceDto` with the mapper. The service resolves the factory and persists the kit; the router never constructs a `Device` and never contains family-specific logic.

### 10. Someone proposes a single "god factory" that creates locations, readings, and devices "because we already have a factory." Why is that a misuse of Abstract Factory?

> [!NOTE]
> **Your Answer**
>
> Abstract Factory exists to create a family of related products that must be consistent with each other. Locations, readings, and devices are not a family: they are separate concepts with different lifecycles and different reasons to change. Grouping them just because "it's a factory" gives the class low cohesion and several unrelated responsibilities, so it grows without limit, and every change to one concept touches the same class. It also breaks the pattern's extension story: every concrete factory would have to implement location and reading creation too, even though those have nothing to do with simulation vs edge. Each concept should get the creational approach that fits it — for example Builder for step-by-step location configuration in Phase 4 — and the family factory should keep producing only device kits.