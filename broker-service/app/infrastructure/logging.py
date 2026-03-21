from algotrader_logger import configure_logging as configure_shared_logging


def configure_logging(level: str = "INFO", fmt: str = "pretty") -> None:
    """Configure shared logging for broker-service."""
    configure_shared_logging(
        service_name="broker-service",
        level=level,
        format=fmt,
    )
