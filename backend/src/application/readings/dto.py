from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReadingDto(BaseModel):
    device_id: UUID
    value: float
    unit: str
    source: Literal["simulation", "mqtt", "vendor"]
    recorded_at: datetime