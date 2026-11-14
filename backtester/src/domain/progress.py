"""Best-effort stage observation, independent of simulation and lifecycle policy."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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


@contextmanager
def observe_progress(callback: Callable[[ProgressStage], None]) -> Iterator[None]:
    """Observe monotonically advancing stages only within this execution context."""
    last = -1

    def advance(stage: ProgressStage) -> None:
        nonlocal last
        index = STAGES.index(stage)
        if index > last:
            last = index
            callback(stage)

    token = _observer.set(advance)
    try:
        yield
    finally:
        _observer.reset(token)


def report_progress(stage: ProgressStage) -> None:
    observer = _observer.get()
    if observer is not None:
        observer(stage)
