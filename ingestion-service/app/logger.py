"""Logging configuration."""
import logging
import sys


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the ingestion service."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    return logging.getLogger("ingestion-service")
