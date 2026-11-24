from sqlalchemy.orm import Session

from src.application.actuators.composition import build_actuator_port
from src.application.commands.service import CommandService
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.command_log_repository import CommandLogRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.application.events.composition import get_event_bus


def build_command_service(db: Session) -> CommandService:
    """Commands always go through the decorated port from Phase 9."""
    return CommandService(
        devices=DeviceRepository(db),
        states=ActuatorStateRepository(db),
        port=build_actuator_port(db),
        log=CommandLogRepository(db),
        bus=get_event_bus(),
    )