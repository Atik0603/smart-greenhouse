class UnknownStrategyError(Exception):
    """Raised when a strategy key doesn't match any registered strategy."""


class LocationNotFoundError(Exception):
    """The location id doesn't exist (HTTP 404)."""


class NoStrategySelectedError(Exception):
    """No strategy has been saved for this location yet (HTTP 409)."""