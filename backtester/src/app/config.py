"""Minimal runtime configuration for backtester orchestration."""

import math
from dataclasses import dataclass

from domain.enums import DataGranularity
from domain.types import ExecutionConfig


@dataclass(frozen=True)
class BacktesterConfig:
    default_initial_capital: float = 10_000.0
    default_data_granularity: DataGranularity = DataGranularity.BAR
    default_persist_result: bool = False
    worker_poll_interval_seconds: float = 1.0

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.worker_poll_interval_seconds)
            or self.worker_poll_interval_seconds <= 0
        ):
            raise ValueError("worker_poll_interval_seconds must be positive and finite")


def build_default_execution_config() -> ExecutionConfig:
    """Constructs the default execution semantics for v1 bar-mode runs."""
    return ExecutionConfig()
