import unittest

import numpy as np
import pandas as pd
from data.indicator_inputs import prepare_indicator_inputs
from data.source_features import SourceFeatureStream, build_source_features
from strategies.base import BarStrategyModel, IndicatorFeatureRequirement, StrategyDefinition

DAY = 86_400_000
MINUTE = 60_000
START = 20000 * DAY
PARAMS = {"start_time": "09:00", "end_time": "09:15", "extension_end_time": "11:00"}


def fixture():
    return pd.DataFrame(
        {
            "timestamp_ms": START + np.arange(540, 570, 5) * MINUTE,
            "symbol": "TEST",
            "open": 10.0,
            "close": 10.0,
            "volume": 1.0,
            "high": [11, 14, 12, 100, 200, 300],
            "low": [8, 9, 7, 1, 0, -1],
        }
    )


def definition():
    model = BarStrategyModel((), (), 1)
    requirements = tuple(
        IndicatorFeatureRequirement(name, "opening_range", name, PARAMS)
        for name in ("range_high", "range_low", "ready")
    )
    return StrategyDefinition(
        strategy_id="range_input_fixture",
        feature_specs=tuple(r.feature_name for r in requirements),
        indicator_requirements=requirements,
        decision_model=model.build_signals,
        position_builder=model.build_positions,
        bar_model=model,
    )


class RangeInputTests(unittest.TestCase):
    def test_complete_formation_needs_no_midnight_candles_or_predecessor(self):
        bars = fixture()
        features = build_source_features(
            bars=bars, strategy=definition(), timeframe="M5", feature_bars={}
        )
        self.assertEqual(features.range_high.tolist(), [11, 14, 14, 14, 14, 14])
        self.assertEqual(features.range_low.tolist(), [8, 8, 7, 7, 7, 7])
        self.assertEqual(features.ready.tolist(), [0, 0, 0, 1, 1, 1])
        self.assertEqual(features.indicators_available.tolist(), [1] * len(bars))

    def test_missing_formation_candle_invalidates_range(self):
        bars = fixture().drop(index=1)
        features = build_source_features(
            bars=bars, strategy=definition(), timeframe="M5", feature_bars={}
        )
        self.assertEqual(features.indicators_available.tolist(), [1, 0, 0, 0, 0])

    def test_missing_or_invalid_candles_after_cutoff_do_not_erase_frozen_range(self):
        bars = fixture().drop(index=4)
        bars.loc[3, ["high", "low"]] = np.nan
        features = build_source_features(
            bars=bars, strategy=definition(), timeframe="M5", feature_bars={}
        )
        self.assertEqual(features.range_high.tolist(), [11, 14, 14, 14, 14])
        self.assertEqual(features.indicators_available.tolist(), [1] * len(bars))

    def test_sequential_features_match_batch(self):
        bars = fixture()
        expected = build_source_features(
            bars=bars, strategy=definition(), timeframe="M5", feature_bars={}
        )
        stream = SourceFeatureStream(
            bars=bars, strategy=definition(), timeframe="M5", feature_bars={}
        )
        actual = pd.DataFrame([stream.update(int(t)) for t in bars.timestamp_ms])
        np.testing.assert_allclose(actual, expected[actual.columns])

    def test_clock_boundaries_must_align_with_timeframe(self):
        requirement = IndicatorFeatureRequirement(
            "high", "opening_range", "range_high", {**PARAMS, "start_time": "09:03"}
        )
        with self.assertRaisesRegex(ValueError, "align"):
            prepare_indicator_inputs(
                requirement=requirement,
                symbol="TEST",
                timeframe="M5",
                bars=fixture(),
                feature_bars={},
            )
