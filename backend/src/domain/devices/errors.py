class DeviceNotFoundError(Exception):
    def __init__(self, device_id) -> None:
        super().__init__(f"Device {device_id} not found")
        self.device_id = device_id