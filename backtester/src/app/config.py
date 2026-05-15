"""Minimal runtime configuration for backtester orchestration."""

from dataclasses import dataclass

from domain.enums import DataGranularity
from domain.types import ExecutionConfig


@dataclass(frozen=True)
class BacktesterConfig:
    default_initial_capital: float = 10_000.0
    default_data_granularity: DataGranularity = DataGranularity.BAR
    default_persist_result: bool = False


def build_default_execution_config() -> ExecutionConfig:
    """Constructs the default execution semantics for v1 bar-mode runs."""
    return ExecutionConfig()
