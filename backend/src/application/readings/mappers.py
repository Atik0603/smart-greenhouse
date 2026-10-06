from src.application.readings.dto import ReadingDto
from src.domain.sensors.reading import Reading


def reading_to_dto(reading: Reading) -> ReadingDto:
    return ReadingDto(
        device_id=reading.device_id,
        value=reading.value,
        unit=reading.unit,
        source=reading.source,
        recorded_at=reading.recorded_at,
    )