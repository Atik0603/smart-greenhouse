import uuid

import pytest

from src.domain.automation.context import LocationAutomationContext
from src.domain.automation.errors import UnknownStrategyError
from src.domain.automation.strategy import (
    AggressiveStrategy,
    AutomationStrategy,
    ConservativeStrategy,
    get_strategy,
    strategy_keys,
)


def ctx(moisture: float, low: float = 0.20, high: float = 0.40) -> LocationAutomationContext:
    return LocationAutomationContext(
        location_id=uuid.uuid4(), zone_id=uuid.uuid4(), moisture=moisture, low=low, high=high
    )


# --- The defining difference: same context, different answers ---

def test_same_context_different_strategies_disagree():
    context = ctx(0.25)  # between low (0.20) and midpoint (0.30)

    conservative = ConservativeStrategy().decide(context)
    aggressive = AggressiveStrategy().decide(context)

    assert conservative.action == "wait"
    assert aggressive.action == "irrigate"


# --- Each strategy across the whole range ---

@pytest.mark.parametrize(
    "moisture, expected",
    [(0.10, "irrigate"), (0.19, "irrigate"), (0.20, "wait"), (0.25, "wait"), (0.45, "wait")],
)
def test_conservative_irrigates_only_below_low(moisture, expected):
    assert ConservativeStrategy().decide(ctx(moisture)).action == expected


@pytest.mark.parametrize(
    "moisture, expected",
    [(0.10, "irrigate"), (0.25, "irrigate"), (0.29, "irrigate"), (0.30, "wait"), (0.45, "wait")],
)
def test_aggressive_irrigates_below_midpoint(moisture, expected):
    assert AggressiveStrategy().decide(ctx(moisture)).action == expected


def test_scores_are_urgency_between_zero_and_one():
    assert AggressiveStrategy().decide(ctx(0.25)).score == 0.5
    assert ConservativeStrategy().decide(ctx(0.0)).score == 1.0   # very dry is clamped to 1
    assert ConservativeStrategy().decide(ctx(0.30)).score == 0.0


def test_reasons_explain_the_decision():
    assert "low threshold 0.20" in ConservativeStrategy().decide(ctx(0.25)).reason
    assert "midpoint 0.30" in AggressiveStrategy().decide(ctx(0.25)).reason


# --- Registry ---

def test_registry_returns_strategy_objects_by_key():
    assert isinstance(get_strategy("conservative"), ConservativeStrategy)
    assert isinstance(get_strategy("aggressive"), AggressiveStrategy)
    assert strategy_keys() == ["aggressive", "conservative"]


def test_unknown_key_is_rejected():
    with pytest.raises(UnknownStrategyError, match="nope"):
        get_strategy("nope")


def test_every_registered_strategy_implements_the_interface():
    for key in strategy_keys():
        assert isinstance(get_strategy(key), AutomationStrategy)


def test_interface_cannot_be_instantiated_without_decide():
    class Broken(AutomationStrategy):
        key = "broken"

    with pytest.raises(TypeError):
        Broken()


# --- Context guard ---

def test_context_rejects_low_not_below_high():
    with pytest.raises(ValueError):
        ctx(0.3, low=0.4, high=0.4)