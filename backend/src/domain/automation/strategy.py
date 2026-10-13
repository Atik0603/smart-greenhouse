from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.errors import UnknownStrategyError

Action = Literal["irrigate", "wait"]


@dataclass(frozen=True)
class Recommendation:
    action: Action
    reason: str
    score: float | None = None   # urgency 0..1, 0 = no need, 1 = very dry


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class AutomationStrategy(ABC):
    """The interface. Every algorithm answers the same question the same way."""

    key: str

    @abstractmethod
    def decide(self, context: LocationAutomationContext) -> Recommendation: ...


class ConservativeStrategy(AutomationStrategy):
    """Water only when the soil is actually below the zone's low threshold."""

    key = "conservative"

    def decide(self, context: LocationAutomationContext) -> Recommendation:
        c = context
        if c.moisture < c.low:
            urgency = (c.low - c.moisture) / (c.high - c.low)
            return Recommendation(
                action="irrigate",
                reason=f"Moisture {c.moisture:.2f} is below the low threshold {c.low:.2f}",
                score=round(_clamp01(urgency), 2),
            )
        return Recommendation(
            action="wait",
            reason=f"Moisture {c.moisture:.2f} is at or above the low threshold {c.low:.2f}",
            score=0.0,
        )


class AggressiveStrategy(AutomationStrategy):
    """Keep the soil in the upper half of the range: water below the midpoint."""

    key = "aggressive"

    def decide(self, context: LocationAutomationContext) -> Recommendation:
        c = context
        midpoint = (c.low + c.high) / 2
        if c.moisture < midpoint:
            urgency = (midpoint - c.moisture) / (midpoint - c.low)
            return Recommendation(
                action="irrigate",
                reason=f"Moisture {c.moisture:.2f} is below the midpoint {midpoint:.2f}",
                score=round(_clamp01(urgency), 2),
            )
        return Recommendation(
            action="wait",
            reason=f"Moisture {c.moisture:.2f} is at or above the midpoint {midpoint:.2f}",
            score=0.0,
        )


# --- Registry: the ONE place that maps keys to strategy objects ---

_STRATEGIES: dict[str, AutomationStrategy] = {
    s.key: s for s in (ConservativeStrategy(), AggressiveStrategy())
}


def get_strategy(key: str) -> AutomationStrategy:
    try:
        return _STRATEGIES[key]
    except KeyError:
        raise UnknownStrategyError(
            f"Unknown strategy '{key}'. Known strategies: {', '.join(strategy_keys())}"
        ) from None


def strategy_keys() -> list[str]:
    return sorted(_STRATEGIES)