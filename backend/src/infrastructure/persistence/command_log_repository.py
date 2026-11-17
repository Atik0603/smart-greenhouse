from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import CommandLogRow


@dataclass(frozen=True)
class CommandLogRecord:
    id: UUID
    command_type: str
    device_id: UUID
    payload: dict
    status: str
    error_message: str | None
    created_at: datetime


class CommandLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        command_type: str,
        device_id: UUID,
        payload: dict,
        status: str,
        error_message: str | None = None,
    ) -> CommandLogRecord:
        row = CommandLogRow(
            command_type=command_type,
            device_id=device_id,
            payload=dict(payload),
            status=status,
            error_message=error_message,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)          # load the server-generated id and created_at
        return self._to_record(row)

    def list_recent(self, limit: int) -> list[CommandLogRecord]:
        rows = (
            self.db.query(CommandLogRow)
            .order_by(CommandLogRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: CommandLogRow) -> CommandLogRecord:
        return CommandLogRecord(
            id=row.id,
            command_type=row.command_type,
            device_id=row.device_id,
            payload=dict(row.payload),
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )