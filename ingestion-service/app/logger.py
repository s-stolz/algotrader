"""Shared logging configuration for ingestion-service."""

import logging

from algotrader_logger import configure_logging


def setup_logging(log_level: str = "INFO", log_format: str = "pretty") -> logging.Logger:
    """Configure logging for the ingestion service."""
    configure_logging(
        service_name="ingestion-service",
        level=log_level,
        format=log_format,
    )
    return logging.getLogger("ingestion-service")
