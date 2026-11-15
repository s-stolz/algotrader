"""Best-effort stage observation, independent of simulation and lifecycle policy."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

ProgressStage = Literal[
    "loading_data", "preparing_indicators", "simulating", "calculating_results", "saving"
]
STAGES: tuple[ProgressStage, ...] = (
    "loading_data",
    "preparing_indicators",
    "simulating",
    "calculating_results",
    "saving",
)
_observer: ContextVar[Callable[[ProgressStage], None] | None] = ContextVar(
    "run_progress", default=None
)

_simulation_observer: ContextVar[Callable[[int, int], None] | None] = ContextVar(
    "simulation_progress", default=None
)
CANDLE_PROGRESS_INTERVAL = 1_000


@dataclass
class CandleProgress:
    total: int
    processed: int = 0

    def report(self) -> None:
        observer = _simulation_observer.get()
        if observer is not None:
            observer(self.processed, self.total)

    def begin_candle(self) -> None:
        # Report completed work before starting the next candle.
        if self.processed % CANDLE_PROGRESS_INTERVAL == 0:
            self.report()
        self.processed += 1


@contextmanager
def observe_progress(
    callback: Callable[[ProgressStage], None],
    on_simulation: Callable[[int, int], None] | None = None,
) -> Iterator[None]:
    """Observe monotonically advancing stages only within this execution context."""
    last = -1

    def advance(stage: ProgressStage) -> None:
        nonlocal last
        index = STAGES.index(stage)
        if index > last:
            last = index
            callback(stage)

    token = _observer.set(advance)
    simulation_token = _simulation_observer.set(on_simulation)
    try:
        yield
    finally:
        _observer.reset(token)
        _simulation_observer.reset(simulation_token)


def report_progress(stage: ProgressStage) -> None:
    observer = _observer.get()
    if observer is not None:
        observer(stage)
