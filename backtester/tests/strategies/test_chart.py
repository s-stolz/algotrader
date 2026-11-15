import unittest
from unittest.mock import patch

from indicator_engine import get_registry
from strategies.base import IndicatorFeatureRequirement
from strategies.chart import snapshot_chart_indicators
from strategies.examples.macd_ema import build_macd_ema_strategy
from strategies.examples.sma_crossover import build_sma_crossover_strategy


class ChartIndicatorSnapshotTests(unittest.TestCase):
    def test_saves_resolved_parameters_for_each_distinct_calculation(self):
        strategy = build_sma_crossover_strategy(fast_window=3, slow_window=8)
        self.assertEqual(
            snapshot_chart_indicators(strategy),
            {
                "schema_version": 1,
                "items": [
                    {"indicator_id": "sma", "parameters": {"window": 3, "source": "close"}},
                    {"indicator_id": "sma", "parameters": {"window": 8, "source": "close"}},
                ],
            },
        )

    def test_multiple_outputs_share_one_chart_indicator(self):
        snapshot = snapshot_chart_indicators(build_macd_ema_strategy())
        self.assertEqual([item["indicator_id"] for item in snapshot["items"]], ["macd", "ema"])
        self.assertEqual(
            snapshot["items"][0]["parameters"],
            {
                "fast": 12,
                "slow": 26,
                "signal": 9,
                "source": "close",
            },
        )

    def test_implicit_and_explicit_defaults_deduplicate_and_remain_saved(self):
        strategy = build_sma_crossover_strategy()
        parameters = {"window": 20}
        strategy.indicator_requirements = (
            IndicatorFeatureRequirement("one", "sma", "sma", parameters),
            IndicatorFeatureRequirement("two", "sma", "sma", {"window": 20, "source": "close"}),
        )
        snapshot = snapshot_chart_indicators(strategy)
        parameters["window"] = 99
        schema = get_registry().get("sma").spec.parameters["source"]
        with patch.dict(schema, {"default": "open"}):
            self.assertEqual(
                snapshot["items"],
                [
                    {"indicator_id": "sma", "parameters": {"window": 20, "source": "close"}},
                ],
            )

    def test_no_indicator_requirements_produces_an_explicit_empty_snapshot(self):
        strategy = build_sma_crossover_strategy()
        strategy.indicator_requirements = ()
        self.assertEqual(snapshot_chart_indicators(strategy), {"schema_version": 1, "items": []})
