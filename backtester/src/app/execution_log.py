"""Policy for bounded inspection of saved execution records."""

from typing import Any, Callable

from db_accessor_client import DatabaseAccessorClientError
from domain.types import BACKTEST_RESULT_SCHEMA_VERSION

from app.backtest_runs import (
    BacktestRunConflictError,
    BacktestRunNotFoundError,
    BacktestRunPersistenceError,
)


class ExecutionLogService:
    def __init__(self, read_page: Callable[[str, int, int, bool], dict[str, Any]]) -> None:
        self._read_page = read_page

    def get_page(
        self, run_id: str, page: int, page_size: int, include_unexecuted: bool
    ) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("Invalid execution-log pagination")
        try:
            result = self._read_page(run_id, page, page_size, include_unexecuted)
        except DatabaseAccessorClientError as exc:
            if exc.status_code == 404:
                raise BacktestRunNotFoundError(run_id) from exc
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        except Exception as exc:
            raise BacktestRunPersistenceError("Backtest persistence unavailable") from exc
        if result.get("status") != "succeeded":
            raise BacktestRunConflictError("Execution log requires a succeeded run")
        if result.get("result_schema_version") != BACKTEST_RESULT_SCHEMA_VERSION:
            raise BacktestRunConflictError("Execution log result schema is unsupported")
        return {key: result[key] for key in ("run_id", "page", "page_size", "total", "items")}
