import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure basic structured logging."""

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
