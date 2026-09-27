"""Minimal runtime configuration for backtester orchestration."""

import math
import os
from dataclasses import dataclass

from domain.enums import DataGranularity
from domain.types import ExecutionConfig


@dataclass(frozen=True)
class BacktesterConfig:
    default_initial_capital: float = 10_000.0
    default_data_granularity: DataGranularity = DataGranularity.BAR
    default_persist_result: bool = False
    worker_poll_interval_seconds: float = 1.0
    worker_heartbeat_interval_seconds: float = 5.0
    worker_stale_after_seconds: float = 30.0
    max_sweep_candidate_count: int = 1_000

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.worker_poll_interval_seconds)
            or self.worker_poll_interval_seconds <= 0
        ):
            raise ValueError("worker_poll_interval_seconds must be positive and finite")
        if type(self.max_sweep_candidate_count) is not int or self.max_sweep_candidate_count <= 0:
            raise ValueError("max_sweep_candidate_count must be a positive integer")
        if (
            not math.isfinite(self.worker_heartbeat_interval_seconds)
            or self.worker_heartbeat_interval_seconds <= 0
        ):
            raise ValueError("worker_heartbeat_interval_seconds must be positive and finite")
        if (
            not math.isfinite(self.worker_stale_after_seconds)
            or self.worker_stale_after_seconds <= self.worker_heartbeat_interval_seconds
        ):
            raise ValueError("worker_stale_after_seconds must exceed heartbeat interval")

    @classmethod
    def from_env(cls) -> "BacktesterConfig":
        return cls(
            worker_poll_interval_seconds=float(
                os.getenv("BACKTESTER_WORKER_POLL_INTERVAL_SECONDS", "1.0")
            ),
            worker_heartbeat_interval_seconds=float(
                os.getenv("BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS", "5.0")
            ),
            worker_stale_after_seconds=float(
                os.getenv("BACKTESTER_WORKER_STALE_AFTER_SECONDS", "30.0")
            ),
            max_sweep_candidate_count=int(
                os.getenv("BACKTESTER_MAX_SWEEP_CANDIDATE_COUNT", "1000")
            ),
        )


def build_default_execution_config() -> ExecutionConfig:
    """Constructs the default execution semantics for v1 bar-mode runs."""
    return ExecutionConfig()
