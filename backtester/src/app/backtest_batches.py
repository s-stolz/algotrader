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

    def list(self) -> list[dict[str, Any]]:
        return self._with_client(
            lambda client: [
                self._batch_with_outcomes(client, batch) for batch in client.list_backtest_batches()
            ]
        )

    def get(self, batch_id: str) -> dict[str, Any]:
        return self._with_client(
            lambda client: self._batch_with_outcomes(client, client.get_backtest_batch(batch_id))
        )

    def members(self, batch_id: str) -> list[dict[str, Any]]:
        return self._with_client(lambda client: client.list_backtest_batch_members(batch_id))

    def events(self, batch_id: str) -> list[dict[str, Any]]:
        return self._with_client(lambda client: client.list_backtest_batch_events(batch_id))

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
    accepted_at = value.pop("accepted_at")
    if isinstance(accepted_at, datetime):
        value["accepted_at_ms"] = int(accepted_at.timestamp() * 1000)
    else:
        value["accepted_at_ms"] = int(
            datetime.fromisoformat(str(accepted_at).replace("Z", "+00:00")).timestamp() * 1000
        )
    return value
