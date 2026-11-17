from src.application.actuators.dto import ExecutionDto
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

MAX_LIMIT = 200


class ActuatorExecutionService:
    """Read side of the execution log. Commands (Phase 10) are the only write path."""

    def __init__(self, log: ExecutionLogRepository) -> None:
        self._log = log

    def list_recent(self, limit: int = 20) -> list[ExecutionDto]:
        limit = max(1, min(limit, MAX_LIMIT))
        return [ExecutionDto(**record.__dict__) for record in self._log.list_recent(limit)]