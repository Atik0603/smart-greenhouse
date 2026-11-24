import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[Any], None]


class EventBus:
    """In-process publish/subscribe. Publishers know the bus, never the subscribers."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_class: type, handler: Handler) -> None:
        self._handlers[event_class].append(handler)

    def publish(self, event: object) -> None:
        for handler in list(self._handlers.get(type(event), [])):
            try:
                handler(event)
            except Exception:
                # One broken subscriber must not stop the others (or the publisher).
                logger.exception(
                    "Subscriber %r failed on %s", handler, type(event).__name__
                )