"""Authoritative Backtest acceptance and immutable backtest inspection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, ContextManager, Mapping, Protocol
from uuid import uuid4

from domain.experiment_names import normalize_experiment_name
from domain.types import BacktestRequestSnapshot
from strategies.registry import StrategyVersionUnavailableError, strategy_catalog

from app.backtest_definitions import BacktestDefinition, BacktestPreviewService


class BacktestClient(Protocol):
    def create_backtest(self, backtest: dict[str, Any]) -> Mapping[str, Any]: ...
    def rename_backtest(self, backtest_id: str, name: str | None) -> Mapping[str, Any]: ...
    def list_backtests(self) -> list[dict[str, Any]]: ...
    def get_backtest(self, backtest_id: str) -> Mapping[str, Any]: ...
    def list_backtest_members(self, backtest_id: str) -> list[dict[str, Any]]: ...
    def list_backtest_events(self, backtest_id: str) -> list[dict[str, Any]]: ...
    def delete_backtest(self, backtest_id: str) -> None: ...
    def control_backtest(
        self, backtest_id: str, command: str, command_id: str, policy: dict[str, Any]
    ) -> Mapping[str, Any]: ...


BACKTEST_CONTROL_POLICY: dict[str, dict[str, Any]] = {
    "pause": {
        "accepted_statuses": ["queued", "running"],
        "effective_statuses": ["pausing", "paused"],
        "active_status": "pausing",
        "idle_status": "paused",
        "queue_action": "remove",
    },
    "resume": {
        "accepted_statuses": ["pausing", "paused"],
        "effective_statuses": ["queued", "running"],
        "active_status": "running",
        "idle_status": "running",
        "queue_action": "append",
    },
    "cancel": {
        "accepted_statuses": ["queued", "running", "pausing", "paused"],
        "effective_statuses": ["cancelling", "cancelled"],
        "active_status": "cancelling",
        "idle_status": "cancelled",
        "queue_action": "remove",
    },
}


class BacktestService:
    def __init__(
        self,
        *,
        preview: BacktestPreviewService,
        client: BacktestClient | None = None,
        client_factory: Callable[[], ContextManager[BacktestClient]] | None = None,
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._preview = preview
        self._client = client
        self._client_factory = client_factory
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))

    def accept(
        self, submission_id: str, definition: BacktestDefinition, *, name: str | None = None
    ) -> dict[str, Any]:
        name = normalize_experiment_name(name)
        if not submission_id or len(submission_id) > 36:
            raise ValueError("submission_id must be a nonempty client-generated identity")
        # Expansion reads the current Market catalog, strategy version, constraints,
        # defaults, and limit. No client preview rows or token cross this boundary.
        expanded = self._preview.expand(definition)
        metadata = next(
            (
                item
                for item in strategy_catalog()
                if item["strategy_id"] == definition.shared_request.strategy.strategy_id
                and item["strategy_version"] == definition.shared_request.strategy.strategy_version
            ),
            None,
        )
        if metadata is None:
            raise StrategyVersionUnavailableError("strategy_version_unavailable")
        shared = dict(BacktestRequestSnapshot.from_request(definition.shared_request).payload)
        for key in ("symbols", "exchange", "timeframe"):
            shared.pop(key)
        accepted_definition = {
            "schema_version": 1,
            "shared_request": shared,
            "normalized_selections": expanded["normalized_selections"],
        }
        candidates = expanded["candidates"]
        assert isinstance(candidates, list)
        members = [
            {
                "run_id": self._new_id(),
                "run_ordinal": row["run_ordinal"],
                "request_schema_version": 3,
                "request": row["request"],
            }
            for row in candidates
            if row["status"] == "ready"
        ]
        payload = {
            "backtest_id": self._new_id(),
            "submission_id": submission_id,
            "name": name,
            "accepted_at": self._now().isoformat(),
            "definition_schema_version": 1,
            "accepted_definition": accepted_definition,
            "strategy_metadata": metadata,
            "raw_count": expanded["raw_count"],
            "member_count": expanded["ready_count"],
            "excluded_count": expanded["excluded_count"],
            "members": members,
        }
        return self._with_client(
            lambda client: self._backtest_with_outcomes(client, client.create_backtest(payload))
        )

    def list(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        with_failed_members: bool | None = None,
    ) -> list[dict[str, Any]]:
        backtests = self._with_client(
            lambda client: [
                self._backtest_with_outcomes(client, backtest)
                for backtest in client.list_backtests()
            ]
        )
        return [
            backtest
            for backtest in backtests
            if (symbol is None or symbol in backtest["markets"])
            and (timeframe is None or timeframe in backtest["timeframes"])
            and (strategy is None or strategy == backtest["strategy_id"])
            and (
                with_failed_members is None or backtest["has_failed_members"] == with_failed_members
            )
        ]

    def get(self, backtest_id: str) -> dict[str, Any]:
        return self._with_client(
            lambda client: self._backtest_with_outcomes(client, client.get_backtest(backtest_id))
        )

    def rename(self, backtest_id: str, name: str | None) -> dict[str, Any]:
        name = normalize_experiment_name(name)
        return self._with_client(lambda client: dict(client.rename_backtest(backtest_id, name)))

    def members(self, backtest_id: str) -> list[dict[str, Any]]:
        return self._with_client(lambda client: client.list_backtest_members(backtest_id))

    def events(self, backtest_id: str) -> list[dict[str, Any]]:
        return self._with_client(
            lambda client: [
                {
                    **{key: value for key, value in event.items() if key != "occurred_at"},
                    "occurred_at_ms": _timestamp_ms(event["occurred_at"]),
                }
                for event in client.list_backtest_events(backtest_id)
            ]
        )

    def control(self, backtest_id: str, command: str, command_id: str) -> dict[str, Any]:
        if command not in BACKTEST_CONTROL_POLICY:
            raise ValueError("Unknown backtest command")
        if not command_id or len(command_id) > 36:
            raise ValueError("Invalid command identity")
        return self._with_client(
            lambda client: dict(
                client.control_backtest(
                    backtest_id, command, command_id, BACKTEST_CONTROL_POLICY[command]
                )
            )
        )

    def delete(self, backtest_id: str) -> None:
        self._with_client(lambda client: client.delete_backtest(backtest_id))

    @staticmethod
    def _backtest_with_outcomes(
        client: BacktestClient, backtest: Mapping[str, Any]
    ) -> dict[str, Any]:
        members = client.list_backtest_members(str(backtest["backtest_id"]))
        return _project_backtest(backtest, members)

    def _with_client(self, operation: Callable[[BacktestClient], Any]) -> Any:
        if self._client is not None:
            return operation(self._client)
        if self._client_factory is None:
            raise RuntimeError("Backtest persistence client is required")
        with self._client_factory() as client:
            return operation(client)


def _project_backtest(backtest: Mapping[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    value = dict(backtest)
    counts = {
        status: sum(member["status"] == status for member in members)
        for status in ("queued", "running", "cancelling", "succeeded", "failed", "cancelled")
    }
    value["outcome_counts"] = counts
    value["settled_count"] = counts["succeeded"] + counts["failed"] + counts["cancelled"]
    value["executed_count"] = counts["succeeded"] + counts["failed"]
    value["total_count"] = value["member_count"]
    value["has_failed_members"] = counts["failed"] > 0
    value["markets"] = list(
        dict.fromkeys(symbol for member in members for symbol in member["request"]["symbols"])
    )
    value["exchanges"] = list(
        dict.fromkeys(
            member["request"]["exchange"]
            for member in members
            if member["request"]["exchange"] is not None
        )
    )
    value["market_contexts"] = [
        {"symbol": symbol, "exchange": exchange}
        for exchange, symbol in dict.fromkeys(
            (member["request"]["exchange"], symbol)
            for member in members
            for symbol in member["request"]["symbols"]
        )
    ]
    value["timeframes"] = list(dict.fromkeys(member["request"]["timeframe"] for member in members))
    value["strategy_id"] = value["strategy_metadata"]["strategy_id"]
    value["strategy_version"] = value["strategy_metadata"]["strategy_version"]
    value["active_run_ordinal"] = next(
        (
            member["run_ordinal"]
            for member in members
            if member["status"] in {"running", "cancelling"}
        ),
        None,
    )
    value["next_run_ordinal"] = next(
        (member["run_ordinal"] for member in members if member["status"] == "queued"),
        None,
    )
    for field in ("started_at", "completed_at", "cancel_requested_at"):
        value[f"{field}_ms"] = _timestamp_ms(value[field]) if value.get(field) is not None else None
        value.pop(field, None)
    accepted_at = value.pop("accepted_at")
    if isinstance(accepted_at, datetime):
        value["accepted_at_ms"] = int(accepted_at.timestamp() * 1000)
    else:
        value["accepted_at_ms"] = int(
            datetime.fromisoformat(str(accepted_at).replace("Z", "+00:00")).timestamp() * 1000
        )
    return value


def _timestamp_ms(value: Any) -> int:
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
