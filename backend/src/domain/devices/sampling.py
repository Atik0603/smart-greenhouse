MIN_SAMPLING_INTERVAL_SECONDS = 5


class SamplingConfigError(ValueError):
    """Raised when sampling settings break a domain rule."""


def validate_sampling_interval(seconds: int) -> None:
    if seconds < MIN_SAMPLING_INTERVAL_SECONDS:
        raise SamplingConfigError(
            f"sampling_interval_seconds must be at least {MIN_SAMPLING_INTERVAL_SECONDS} (got {seconds})"
        )