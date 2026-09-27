"""Authoritative Parameter Sweep acceptance and immutable batch inspection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, ContextManager, Mapping, Protocol
from uuid import uuid4

from domain.types import BacktestRequestSnapshot
from strategies.registry import StrategyVersionUnavailableError, strategy_catalog

from app.sweeps import SweepDefinition, SweepPreviewService


class BatchClient(Protocol):
    def create_backtest_batch(self, batch: dict[str, Any]) -> Mapping[str, Any]: ...
    def list_backtest_batches(self) -> list[dict[str, Any]]: ...
    def get_backtest_batch(self, batch_id: str) -> Mapping[str, Any]: ...
    def list_backtest_batch_members(self, batch_id: str) -> list[dict[str, Any]]: ...
    def list_backtest_batch_events(self, batch_id: str) -> list[dict[str, Any]]: ...
    def control_backtest_batch(
        self, batch_id: str, command: str, command_id: str, policy: dict[str, Any]
    ) -> Mapping[str, Any]: ...


BATCH_CONTROL_POLICY: dict[str, dict[str, Any]] = {
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
}


class BacktestBatchService:
    def __init__(
        self,
        *,
        preview: SweepPreviewService,
        client: BatchClient | None = None,
        client_factory: Callable[[], ContextManager[BatchClient]] | None = None,
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._preview = preview
        self._client = client
        self._client_factory = client_factory
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))

    def accept(self, submission_id: str, definition: SweepDefinition) -> dict[str, Any]:
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
                "member_ordinal": row["member_ordinal"],
                "request_schema_version": 3,
                "request": row["request"],
            }
            for row in candidates
            if row["status"] == "ready"
        ]
        payload = {
            "batch_id": self._new_id(),
            "submission_id": submission_id,
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
            lambda client: self._batch_with_outcomes(client, client.create_backtest_batch(payload))
        )

    def list(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str | None = None,
        with_failed_members: bool | None = None,
    ) -> list[dict[str, Any]]:
        batches = self._with_client(
            lambda client: [
                self._batch_with_outcomes(client, batch) for batch in client.list_backtest_batches()
            ]
        )
        return [
            batch
            for batch in batches
            if (symbol is None or symbol in batch["markets"])
            and (timeframe is None or timeframe in batch["timeframes"])
            and (strategy is None or strategy == batch["strategy_id"])
            and (with_failed_members is None or batch["has_failed_members"] == with_failed_members)
        ]

    def get(self, batch_id: str) -> dict[str, Any]:
        return self._with_client(
            lambda client: self._batch_with_outcomes(client, client.get_backtest_batch(batch_id))
        )

    def members(self, batch_id: str) -> list[dict[str, Any]]:
        return self._with_client(lambda client: client.list_backtest_batch_members(batch_id))

    def events(self, batch_id: str) -> list[dict[str, Any]]:
        return self._with_client(
            lambda client: [
                {**event, "occurred_at_ms": _timestamp_ms(event["occurred_at"])}
                for event in client.list_backtest_batch_events(batch_id)
            ]
        )

    def control(self, batch_id: str, command: str, command_id: str) -> dict[str, Any]:
        if command not in BATCH_CONTROL_POLICY:
            raise ValueError("Unknown batch command")
        if not command_id or len(command_id) > 36:
            raise ValueError("Invalid command identity")
        return self._with_client(
            lambda client: dict(
                client.control_backtest_batch(
                    batch_id, command, command_id, BATCH_CONTROL_POLICY[command]
                )
            )
        )

    @staticmethod
    def _batch_with_outcomes(client: BatchClient, batch: Mapping[str, Any]) -> dict[str, Any]:
        members = client.list_backtest_batch_members(str(batch["batch_id"]))
        return _project_batch(batch, members)

    def _with_client(self, operation: Callable[[BatchClient], Any]) -> Any:
        if self._client is not None:
            return operation(self._client)
        if self._client_factory is None:
            raise RuntimeError("Batch persistence client is required")
        with self._client_factory() as client:
            return operation(client)


def _project_batch(batch: Mapping[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    value = dict(batch)
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
    value["active_member_ordinal"] = next(
        (member["member_ordinal"] for member in members if member["status"] == "running"),
        None,
    )
    value["next_member_ordinal"] = next(
        (member["member_ordinal"] for member in members if member["status"] == "queued"),
        None,
    )
    for field in ("started_at", "completed_at"):
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
