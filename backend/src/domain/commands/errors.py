class UnknownCommandError(ValueError):
    """No command class is registered for this type (HTTP 400, no log row)."""


class InvalidCommandPayloadError(ValueError):
    """The payload doesn't fit the command, e.g. a light level out of range (HTTP 400)."""