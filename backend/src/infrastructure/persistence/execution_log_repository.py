from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import ActuatorExecutionLogRow


@dataclass(frozen=True)
class ExecutionRecord:
    id: UUID
    device_id: UUID
    success: bool
    policy_applied: list[str]
    message: str | None
    created_at: datetime


class ExecutionLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self, device_id: UUID, success: bool, policy_applied: list[str], message: str | None
    ) -> None:
        self.db.add(
            ActuatorExecutionLogRow(
                device_id=device_id,
                success=success,
                policy_applied=list(policy_applied),
                message=message,
            )
        )
        self.db.commit()

    def list_recent(self, limit: int) -> list[ExecutionRecord]:
        rows = (
            self.db.query(ActuatorExecutionLogRow)
            .order_by(ActuatorExecutionLogRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            ExecutionRecord(
                id=row.id,
                device_id=row.device_id,
                success=row.success,
                policy_applied=list(row.policy_applied),
                message=row.message,
                created_at=row.created_at,
            )
            for row in rows
        ]