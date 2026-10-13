from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class StrategySaveRequest(BaseModel):
    strategy_key: str


class AutomationRuleDto(BaseModel):
    location_id: UUID
    strategy_key: str
    updated_at: datetime


class ZoneRecommendationDto(BaseModel):
    zone_id: UUID
    zone_name: str
    moisture: float | None
    action: Literal["irrigate", "wait"]
    reason: str
    score: float | None = None


class EvaluationDto(BaseModel):
    location_id: UUID
    strategy_key: str
    action: Literal["irrigate", "wait"]
    reason: str
    zones: list[ZoneRecommendationDto]