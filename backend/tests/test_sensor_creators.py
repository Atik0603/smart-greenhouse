from src.domain.sensors.creators import (
    LightSensorCreator,
    MoistureSensorCreator,
    SENSOR_CREATORS,
)


def test_moisture_creator_defaults_include_moisture_threshold():
    creator = MoistureSensorCreator()
    sensor = creator.create_sensor("Bed 1")

    assert sensor.device_type == "moisture_sensor"
    assert "moisture_threshold" in sensor.default_config
    assert sensor.default_config["unit"] == "percent"


def test_light_creator_uses_different_unit_and_type():
    creator = LightSensorCreator()
    sensor = creator.create_sensor("Bed 1")

    assert sensor.device_type == "light_sensor"
    assert sensor.default_config["unit"] == "lux"
    assert "moisture_threshold" not in sensor.default_config


def test_registry_maps_type_keys_to_correct_creator_classes():
    assert isinstance(SENSOR_CREATORS["moisture"], MoistureSensorCreator)
    assert isinstance(SENSOR_CREATORS["light"], LightSensorCreator)


def test_unregistered_type_key_is_absent_from_registry():
    assert SENSOR_CREATORS.get("temperature") is None