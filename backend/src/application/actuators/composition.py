from sqlalchemy.orm import Session

from src.domain.actuators.ports import ActuatorPort
from src.infrastructure.adapters.actuators.logging_decorator import LoggingActuatorDecorator
from src.infrastructure.adapters.actuators.max_runtime_decorator import MaxRunTimeActuatorDecorator
from src.infrastructure.adapters.actuators.simulation import SimulationActuatorAdapter
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository


def build_actuator_port(db: Session) -> ActuatorPort:
    """The ONE place that decides the stack: Logging → MaxRunTime → Simulation."""
    states = ActuatorStateRepository(db)
    return LoggingActuatorDecorator(
        MaxRunTimeActuatorDecorator(
            SimulationActuatorAdapter(),
            state_lookup=states.get_state_since,
        ),
        log_repo=ExecutionLogRepository(db),
    )