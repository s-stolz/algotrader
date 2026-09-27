from __future__ import annotations

import unittest
from unittest.mock import patch

from adapters.api.app import create_app
from app.backtest_runs import BacktestRunService
from app.sweeps import SweepPreviewService
from db_accessor_client import DatabaseAccessorClientError
from fastapi.testclient import TestClient
from strategies.examples.sma_crossover import build_sma_crossover_strategy
from strategies.registry import RegisteredStrategy

from .test_backtests_routes import _FakeRunRepository, _valid_payload


def _definition() -> dict:
    definition = {
        **{
            key: value
            for key, value in _valid_payload().items()
            if key not in ("symbols", "timeframe", "exchange")
        },
        "markets": [2, 1, 2],
        "timeframes": ["m5", "M1", "M5"],
        "parameter_axes": {
            "fast_window": {"mode": "range", "start": 4, "stop": 6, "step": 1},
            "slow_window": {"mode": "values", "values": [5, 7]},
            "quantity": {"mode": "range", "start": 0.1, "stop": 0.3, "step": 0.1},
        },
        "allowed_directions": ["long_only", "short_only", "long_only"],
    }
    definition["strategy"].pop("parameters")
    return definition


class TestSweepPreviewRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = _FakeRunRepository()
        self.service = SweepPreviewService(
            markets=lambda: [
                {"symbol_id": 1, "symbol": "EURUSD", "exchange": "FX"},
                {"symbol_id": 2, "symbol": "USDJPY", "exchange": "FX"},
            ],
            max_candidate_count=200,
        )
        self.client = TestClient(
            create_app(
                service=BacktestRunService(repository=self.repository),
                preview_service=self.service,
            )
        )

    def tearDown(self) -> None:
        self.client.close()

    def test_complete_ordered_preview_and_no_history(self) -> None:
        response = self.client.post("/backtests/sweeps/preview", json=_definition())
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(
            self.client.get("/backtests/capabilities").json(),
            {"max_sweep_candidate_count": 200, "batch_acceptance_enabled": True},
        )
        self.assertEqual(preview["raw_count"], 144)
        self.assertEqual(preview["ready_count"], 96)
        self.assertEqual(preview["excluded_count"], 48)
        self.assertEqual(len(preview["candidates"]), 144)
        self.assertEqual(preview["normalized_selections"]["timeframes"], ["M5", "M1"])
        self.assertEqual(preview["normalized_selections"]["markets"][0]["symbol_id"], 2)
        rows = preview["candidates"]
        self.assertEqual([row["candidate_ordinal"] for row in rows], list(range(144)))
        self.assertEqual(
            [row["allowed_directions"] for row in rows[:2]], ["long_only", "short_only"]
        )
        self.assertEqual(rows[0]["parameters"]["quantity"], 0.1)
        self.assertEqual(rows[4]["parameters"]["quantity"], 0.3)
        self.assertEqual(rows[0]["request"]["symbols"], ["USDJPY"])
        excluded = [row for row in rows if row["status"] == "excluded"]
        self.assertTrue(
            all(
                row["issues"]
                == [
                    {
                        "code": "invalid_parameter_combination",
                        "fields": ["fast_window", "slow_window"],
                        "message": "Fast window must be smaller than slow window",
                    }
                ]
                for row in excluded
            )
        )
        self.assertEqual(
            [row["member_ordinal"] for row in rows if row["status"] == "ready"], list(range(96))
        )
        self.assertEqual(self.repository.runs_by_id, {})

    def test_invalid_value_limit_and_empty_valid_set_reject(self) -> None:
        definition = _definition()
        definition["parameter_axes"]["fast_window"] = {"mode": "values", "values": [True, 4]}
        self.assertEqual(
            self.client.post("/backtests/sweeps/preview", json=definition).json()["detail"]["code"],
            "invalid_strategy_parameter",
        )
        definition = _definition()
        definition["parameter_axes"]["fast_window"] = {
            "mode": "range",
            "start": 1,
            "stop": 1000,
            "step": 1,
        }
        oversized = self.client.post("/backtests/sweeps/preview", json=definition)
        self.assertEqual(oversized.status_code, 422)
        self.assertIn("max_sweep_candidate_count", oversized.text)
        definition = _definition()
        definition["parameter_axes"]["fast_window"] = {"mode": "constant", "value": 10}
        definition["parameter_axes"]["slow_window"] = {"mode": "constant", "value": 5}
        empty = self.client.post("/backtests/sweeps/preview", json=definition)
        self.assertEqual(empty.status_code, 422)
        self.assertIn("no Ready", empty.text)
        self.assertEqual(self.repository.runs_by_id, {})

    def test_unreachable_decimal_stop_and_limit_before_pruning(self) -> None:
        definition = _definition()
        definition["markets"] = [1]
        definition["timeframes"] = ["M1"]
        definition["allowed_directions"] = ["long_only"]
        definition["parameter_axes"] = {
            "fast_window": {"mode": "constant", "value": 1},
            "slow_window": {"mode": "constant", "value": 2},
            "quantity": {"mode": "range", "start": 0.1, "stop": 0.31, "step": 0.1},
        }
        response = self.client.post("/backtests/sweeps/preview", json=definition)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["normalized_selections"]["parameters"]["quantity"]["values"],
            [0.1, 0.2, 0.3],
        )
        definition["parameter_axes"]["fast_window"] = {
            "mode": "range",
            "start": 1,
            "stop": 201,
            "step": 1,
        }
        oversize = self.client.post("/backtests/sweeps/preview", json=definition)
        self.assertEqual(oversize.status_code, 422)
        self.assertIn("max_sweep_candidate_count", oversize.text)
        self.assertEqual(self.repository.runs_by_id, {})

    def test_typed_deduplication_keeps_exact_strings_and_null(self) -> None:
        from strategies import registry

        def build_probe(
            *,
            enabled: bool = True,
            count: int = 2,
            ratio: float = 1.0,
            label: str | None = None,
        ):
            return build_sma_crossover_strategy()

        registry.strategy_catalog()
        probe = RegisteredStrategy("typed_probe", 1, build_probe)
        definition = _definition()
        definition["strategy"] = {
            "strategy_id": "typed_probe",
            "strategy_version": 1,
        }
        definition["markets"] = [1]
        definition["timeframes"] = ["M1"]
        definition["allowed_directions"] = ["long_only"]
        definition["parameter_axes"] = {
            "enabled": {"mode": "values", "values": [True, False, True]},
            "count": {"mode": "values", "values": [2, 2]},
            "ratio": {"mode": "values", "values": [1, 1.0]},
            "label": {"mode": "values", "values": [" x", "x", None, None]},
        }
        with patch.dict(registry._REGISTRY, {"typed_probe": probe}):
            response = self.client.post("/backtests/sweeps/preview", json=definition)
            self.assertEqual(response.status_code, 200, response.text)
            preview = response.json()
            self.assertEqual(preview["raw_count"], 6)
            self.assertEqual(
                preview["normalized_selections"]["parameters"]["ratio"]["values"], [1.0]
            )
            self.assertEqual(
                preview["normalized_selections"]["parameters"]["label"]["values"], [" x", "x", None]
            )
            self.assertEqual(
                [row["parameters"]["enabled"] for row in preview["candidates"]],
                [True, True, True, False, False, False],
            )
            definition["parameter_axes"]["count"] = {"mode": "values", "values": [True]}
            self.assertEqual(
                self.client.post("/backtests/sweeps/preview", json=definition).status_code, 422
            )
        self.assertEqual(self.repository.runs_by_id, {})

    def test_stale_version_and_unexpected_validator_failure(self) -> None:
        definition = _definition()
        definition["strategy"]["strategy_version"] = 999
        self.assertEqual(
            self.client.post("/backtests/sweeps/preview", json=definition).status_code, 409
        )
        definition = _definition()
        from strategies import registry

        original = registry.current_strategy("sma_crossover")
        broken = RegisteredStrategy(
            original.strategy_id,
            original.strategy_version,
            original.builder,
            original.display_name,
            lambda _: (_ for _ in ()).throw(RuntimeError("secret")),
        )
        with patch.dict(registry._REGISTRY, {"sma_crossover": broken}):
            with self.assertRaises(RuntimeError):
                self.client.post("/backtests/sweeps/preview", json=definition)
        self.assertEqual(self.repository.runs_by_id, {})

    def test_unavailable_market_catalog_has_safe_service_error(self) -> None:
        def unavailable():
            raise DatabaseAccessorClientError("secret connection detail")

        with TestClient(
            create_app(preview_service=SweepPreviewService(markets=unavailable))
        ) as client:
            response = client.post("/backtests/sweeps/preview", json=_definition())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "market_catalog_unavailable",
                "message": "Market catalog unavailable",
            },
        )
