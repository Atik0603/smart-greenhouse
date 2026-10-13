from uuid import UUID

from src.application.automation.dto import (
    AutomationRuleDto,
    EvaluationDto,
    ZoneRecommendationDto,
)
from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.errors import LocationNotFoundError, NoStrategySelectedError
from src.domain.automation.strategy import (
    AutomationStrategy,
    Recommendation,
    get_strategy,
    strategy_keys,
)
from src.infrastructure.persistence.automation_repository import (
    AutomationContextRepository,
    AutomationRuleRepository,
    ZoneSnapshot,
)


class AutomationService:
    def __init__(
        self, rules: AutomationRuleRepository, contexts: AutomationContextRepository
    ) -> None:
        self._rules = rules
        self._contexts = contexts

    def list_strategy_keys(self) -> list[str]:
        return strategy_keys()

    def get_rule(self, location_id: UUID) -> AutomationRuleDto | None:
        self._require_location(location_id)
        rule = self._rules.get(location_id)
        return None if rule is None else AutomationRuleDto(**rule.__dict__)

    def save_strategy(self, location_id: UUID, strategy_key: str) -> AutomationRuleDto:
        get_strategy(strategy_key)            # unknown key → UnknownStrategyError, nothing saved
        self._require_location(location_id)
        rule = self._rules.upsert(location_id, strategy_key)
        return AutomationRuleDto(**rule.__dict__)

    def evaluate(self, location_id: UUID) -> EvaluationDto:
        self._require_location(location_id)
        rule = self._rules.get(location_id)
        if rule is None:
            raise NoStrategySelectedError(
                "No strategy selected for this location yet. Save one first."
            )
        strategy = get_strategy(rule.strategy_key)   # rejected before any decide()

        zone_results = [
            self._evaluate_zone(location_id, snap, strategy)
            for snap in self._contexts.list_zone_snapshots(location_id)
        ]
        action, reason = self._summarise(zone_results)
        return EvaluationDto(
            location_id=location_id,
            strategy_key=rule.strategy_key,
            action=action,
            reason=reason,
            zones=zone_results,
        )

    # --- helpers ---

    def _require_location(self, location_id: UUID) -> None:
        if not self._contexts.location_exists(location_id):
            raise LocationNotFoundError(f"Location {location_id} not found")

    def _evaluate_zone(
        self, location_id: UUID, snap: ZoneSnapshot, strategy: AutomationStrategy
    ) -> ZoneRecommendationDto:
        if not snap.has_moisture_sensor:
            rec = Recommendation("wait", "No moisture sensor in this zone")
        elif snap.moisture is None:
            rec = Recommendation("wait", "Moisture sensor has no readings yet")
        else:
            context = LocationAutomationContext(
                location_id=location_id,
                zone_id=snap.zone_id,
                moisture=snap.moisture,
                low=snap.low,
                high=snap.high,
                light=snap.light,
            )
            rec = strategy.decide(context)     # ← the polymorphic call

        return ZoneRecommendationDto(
            zone_id=snap.zone_id,
            zone_name=snap.zone_name,
            moisture=snap.moisture,
            action=rec.action,
            reason=rec.reason,
            score=rec.score,
        )

    @staticmethod
    def _summarise(zones: list[ZoneRecommendationDto]) -> tuple[str, str]:
        thirsty = [z.zone_name for z in zones if z.action == "irrigate"]
        if thirsty:
            return "irrigate", f"{len(thirsty)} of {len(zones)} zone(s) need water: {', '.join(thirsty)}"
        return "wait", f"No zone needs water ({len(zones)} zone(s) checked)"