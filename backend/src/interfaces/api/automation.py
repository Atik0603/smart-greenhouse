from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.automation.dto import (
    AutomationRuleDto,
    EvaluationDto,
    StrategySaveRequest,
)
from src.application.automation.service import AutomationService
from src.domain.automation.errors import (
    LocationNotFoundError,
    NoStrategySelectedError,
    UnknownStrategyError,
)
from src.infrastructure.persistence.automation_repository import (
    AutomationContextRepository,
    AutomationRuleRepository,
)
from src.infrastructure.db import get_db   

router = APIRouter(prefix="/api", tags=["automation"])

NOT_FOUND = {404: {"description": "Location not found"}}
BAD_KEY = {400: {"description": "Unknown strategy key"}}
NO_RULE = {409: {"description": "No strategy saved for this location yet"}}


def get_automation_service(db: Session = Depends(get_db)) -> AutomationService:
    return AutomationService(AutomationRuleRepository(db), AutomationContextRepository(db))


@router.get(
    "/automation/strategies",
    response_model=list[str],
    summary="List the strategy keys the backend knows",
)
def list_strategies(service: AutomationService = Depends(get_automation_service)) -> list[str]:
    return service.list_strategy_keys()


@router.get(
    "/locations/{location_id}/automation",
    response_model=AutomationRuleDto | None,
    responses=NOT_FOUND,
    summary="Get the saved strategy for a location (null if none saved yet)",
)
def get_rule(
    location_id: UUID,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationRuleDto | None:
    try:
        return service.get_rule(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/locations/{location_id}/automation",
    response_model=AutomationRuleDto,
    responses={**NOT_FOUND, **BAD_KEY},
    summary="Save (create or replace) the strategy for a location",
)
def save_rule(
    location_id: UUID,
    body: StrategySaveRequest,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationRuleDto:
    try:
        return service.save_strategy(location_id, body.strategy_key)
    except UnknownStrategyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/locations/{location_id}/automation/evaluate",
    response_model=EvaluationDto,
    responses={**NOT_FOUND, **BAD_KEY, **NO_RULE},
    summary="Evaluate every zone of a location with its saved strategy",
)
def evaluate(
    location_id: UUID,
    service: AutomationService = Depends(get_automation_service),
) -> EvaluationDto:
    try:
        return service.evaluate(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NoStrategySelectedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownStrategyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc