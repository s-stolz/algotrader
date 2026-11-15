"""Lightweight succeeded-run reads preserve artifact validation and omit diagnostics."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

from adapters.api.app import create_app
from adapters.api.schemas import BacktestRunRequestSchema, BacktestRunResponseSchema
from app.backtest_runs import BacktestRunService
from app.backtests import BacktestService
from domain.enums import BacktestRunStatus
from fastapi.testclient import TestClient

from .test_backtests_routes import _FakeRunRepository, _seed_run, _valid_payload


class LightweightRunRoutesTests(unittest.TestCase):
    def setUp(self):
        repository = _FakeRunRepository()
        service = BacktestRunService(repository=repository)
        queued = _seed_run(service, BacktestRunRequestSchema(**_valid_payload()).to_domain())
        self.record = replace(
            queued,
            status=BacktestRunStatus.SUCCEEDED,
            result_schema_version=3,
            metrics={"profit_factor": None, "trade_count": 0},
            diagnostics=None,
        )
        repository.runs_by_id[self.record.run_id] = self.record
        repository.listed_runs = [self.record]
        self.members = Mock(spec=BacktestService)
        self.members.members.return_value = [
            {
                "run_id": self.record.run_id,
                "backtest_id": self.record.backtest_id,
                "run_ordinal": 0,
                "status": "succeeded",
                "submitted_at": datetime.now(timezone.utc),
                "request_schema_version": self.record.request_snapshot.schema_version,
                "request": dict(self.record.request_snapshot.payload),
                "result_schema_version": 3,
                "metrics": {"profit_factor": None, "trade_count": 0},
                "diagnostics": None,
            }
        ]
        self.client = TestClient(create_app(service=service, backtest_service=self.members))

    def test_detail_list_and_members_serialize_omitted_diagnostics(self):
        for path, is_list in [
            ("/backtests/runs/run-1", False),
            ("/backtests/runs", True),
            ("/backtests/backtest-1/runs", True),
        ]:
            response = self.client.get(path + "?include_diagnostics=false")
            self.assertEqual(response.status_code, 200, response.text)
            run = response.json()[0] if is_list else response.json()
            self.assertEqual(run["metrics"], {"profit_factor": None, "trade_count": 0})
            self.assertEqual(run["result_schema_version"], 3)
            self.assertNotIn("diagnostics", run)
        self.members.members.assert_called_with("backtest-1", include_diagnostics=False)

    def test_profit_factor_public_run_and_member_round_trips(self):
        for value in (0.0, 2.5, "infinity", None):
            with self.subTest(value=value):
                assert isinstance(self.record.metrics, dict)
                self.record.metrics["profit_factor"] = value
                self.members.members.return_value[0]["metrics"]["profit_factor"] = value
                for path in ("/backtests/runs/run-1", "/backtests/backtest-1/runs"):
                    response = self.client.get(path + "?include_diagnostics=false")
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    run = body[0] if isinstance(body, list) else body
                    self.assertEqual(run["metrics"]["profit_factor"], value)

    def test_public_projection_rejects_missing_or_invalid_profit_factor(self):
        for metrics in (
            {},
            *(
                {"profit_factor": value}
                for value in (True, False, -1, float("nan"), float("inf"), "2", "Infinity")
            ),
        ):
            with self.subTest(metrics=metrics), self.assertRaisesRegex(ValueError, "profit_factor"):
                BacktestRunResponseSchema.from_domain(
                    replace(self.record, metrics=metrics), include_diagnostics=False
                )

    def test_full_projection_still_requires_diagnostics(self):
        for path in ["/backtests/runs/run-1", "/backtests/runs", "/backtests/backtest-1/runs"]:
            self.assertEqual(self.client.get(path).status_code, 503)
        with self.assertRaisesRegex(ValueError, "missing result artifacts"):
            BacktestRunResponseSchema.from_domain(self.record)

    def test_lightweight_projection_still_requires_metrics_and_result_version(self):
        for changes in [{"metrics": None}, {"result_schema_version": None}]:
            with self.assertRaisesRegex(ValueError, "missing result artifacts"):
                BacktestRunResponseSchema.from_domain(
                    replace(self.record, **changes), include_diagnostics=False
                )

    def test_explicit_projection_omits_diagnostics_even_when_present(self):
        result = BacktestRunResponseSchema.from_domain(
            replace(self.record, diagnostics={"order_events": []}), include_diagnostics=False
        )
        self.assertNotIn("diagnostics", result.model_dump(exclude_none=True))
