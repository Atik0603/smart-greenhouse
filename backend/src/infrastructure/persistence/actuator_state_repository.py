from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.actuators.state import INITIAL_STATE
from src.infrastructure.persistence.models import ActuatorStateRow


class ActuatorStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_states(self, device_ids: list[UUID]) -> dict[UUID, str]:
        """Stored state per device, in ONE query. Devices without a row are absent."""
        if not device_ids:
            return {}
        rows = (
            self.db.query(ActuatorStateRow)
            .filter(ActuatorStateRow.device_id.in_(device_ids))
            .all()
        )
        return {row.device_id: row.state for row in rows}

    def get_state(self, device_id: UUID) -> str:
        """Stored state, or the initial state for an actuator created after the migration."""
        return self.get_states([device_id]).get(device_id, INITIAL_STATE)

    def save_state(self, device_id: UUID, state: str) -> None:
        row = self.db.get(ActuatorStateRow, device_id)
        if row is None:
            self.db.add(ActuatorStateRow(device_id=device_id, state=state))
        else:
            row.state = state
        self.db.commit()