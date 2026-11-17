from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.commands.base import Command


class StartPumpCommand(Command):
    command_type = "start_pump"
    target_state = "running"

    def execute(self, port: ActuatorPort) -> AppliedCommand:
        return port.apply(self.device_id, "start_pump", {})


class StopPumpCommand(Command):
    command_type = "stop_pump"
    target_state = "idle"

    def execute(self, port: ActuatorPort) -> AppliedCommand:
        return port.apply(self.device_id, "stop_pump", {})