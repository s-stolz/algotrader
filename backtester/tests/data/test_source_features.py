"""Source data behavior, independent of any custom trading strategy."""

import unittest
from dataclasses import replace

import numpy as np
import pandas as pd
from app.backtest_runner import run_backtest, run_backtest_with_market_data
from data.indicators import build_feature_frame
from data.market_data import load_market_data_bundle
from data.source_features import SourceFeatureStream
from domain.enums import AllowedDirections, BacktestEngine
from domain.types import BacktestRequest, ExecutionConfig, ProtectiveExitSpec, StrategyConfig
from indicator_engine import BarTensor
from indicator_engine.indicators.currency_strength import CurrencyStrength
from strategies.base import BarStrategyModel, IndicatorFeatureRequirement, StrategyDefinition
from strategies.conditions import ConditionRule

DAY = 86_400_000
STEP = 300_000
START = 20000 * DAY
ASSETS = CurrencyStrength.spec.required_assets or []


def candles(symbol, times, close):
    return pd.DataFrame(
        dict(
            timestamp_ms=times, symbol=symbol, open=1.0, high=2.1, low=1.0, close=close, volume=1.0
        )
    )


def fixture(count=8):
    times = START + np.arange(-1, count) * STEP
    sources = {
        asset: candles(asset, times, 1.0 + np.arange(len(times)) * (i + 1) / 1000)
        for i, asset in enumerate(ASSETS)
    }
    return candles("TEST", times, 2.0), sources


def strategy(protection=None):
    model = BarStrategyModel(
        entry_conditions=(ConditionRule.above("close", "open"),),
        exit_conditions=(ConditionRule.below("close", "open"),),
        target_quantity=1,
        protective_exit=protection or ProtectiveExitSpec(),
    )
    return StrategyDefinition(
        strategy_id="source_fixture",
        feature_specs=("strength",),
        indicator_requirements=(
            IndicatorFeatureRequirement(
                feature_name="strength",
                indicator_id="currency_strength",
                output_key="EUR",
                output_asset="FX",
            ),
        ),
        decision_model=model.build_signals,
        position_builder=model.build_positions,
        bar_model=model,
    )


def request(engine=BacktestEngine.VECTORIZED, end=START + 8 * STEP):
    return BacktestRequest(
        symbols=["TEST"],
        timeframe="M5",
        start_ms=START,
        end_ms=end,
        initial_capital=10000,
        strategy=StrategyConfig(strategy_id="source_fixture"),
        engine=engine,
        execution=ExecutionConfig(allowed_directions=AllowedDirections.LONG_ONLY),
    )


class SourceFeatureTests(unittest.TestCase):
    def test_crossovers_begin_with_in_window_snapshots_in_both_engines(self):
        bars, sources = fixture()
        bars.loc[bars.timestamp_ms.isin([START - STEP, START + STEP]), "close"] = 0.5
        original = strategy()
        model = replace(
            original.require_v1_parity_model(),
            entry_conditions=(ConditionRule.crossover("close", "open"),),
        )
        original = replace(original, bar_model=model)
        results = [
            run_backtest(
                request=request(engine), bars=bars, strategy=original, feature_bars=sources
            )
            for engine in BacktestEngine
        ]
        self.assertEqual(results[0].fills, results[1].fills)
        self.assertEqual([fill.timestamp_ms for fill in results[0].fills], [START + 3 * STEP])

    def test_short_entries_are_blocked_but_short_cover_remains_available(self):
        bars, sources = fixture()
        bars["close"] = 0.5
        bars.loc[bars.timestamp_ms == START + 3 * STEP, "close"] = 2.0
        sources[ASSETS[0]] = sources[ASSETS[0]].loc[lambda f: f.timestamp_ms != START + 2 * STEP]
        results = [
            run_backtest(
                request=replace(
                    request(engine),
                    execution=ExecutionConfig(allowed_directions=AllowedDirections.SHORT_ONLY),
                ),
                bars=bars,
                strategy=strategy(),
                feature_bars=sources,
            )
            for engine in BacktestEngine
        ]
        self.assertEqual(results[0].fills, results[1].fills)
        self.assertEqual(
            [fill.timestamp_ms for fill in results[0].fills], [START + STEP, START + 4 * STEP]
        )

    def test_stream_values_match_batch_through_gaps_and_daily_recovery(self):
        bars, sources = fixture(300)
        sources[ASSETS[2]] = sources[ASSETS[2]].loc[lambda f: f.timestamp_ms != START + 2 * STEP]
        expected = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        stream = SourceFeatureStream(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        actual = [stream.update(int(t)) for t in bars.timestamp_ms]
        np.testing.assert_allclose([f["strength"] for f in actual], expected.strength)
        self.assertEqual(
            [f["indicators_available"] for f in actual], expected.indicators_available.tolist()
        )
        self.assertEqual(actual[-1]["indicators_available"], 1.0)

    def test_source_symbol_mismatch_is_rejected(self):
        bars, sources = fixture()
        sources[ASSETS[0]] = sources[ASSETS[1]]
        with self.assertRaisesRegex(ValueError, "different symbol"):
            build_feature_frame(
                bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
            )

    def test_midday_request_uses_full_anchor_history(self):
        bars, sources = fixture(160)
        model = strategy()
        full = build_feature_frame(bars=bars, strategy=model, timeframe="M5", feature_bars=sources)
        later = build_feature_frame(
            bars=bars.loc[bars.timestamp_ms >= START + 12 * 3_600_000],
            strategy=model,
            timeframe="M5",
            feature_bars=sources,
        )
        np.testing.assert_allclose(
            later.strength, full.loc[full.index.isin(later.index), "strength"]
        )

    def test_features_match_full_daily_indicator_and_preserve_trade_timestamps(self):
        bars, sources = fixture()
        featured = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        tensor = BarTensor(
            data=np.stack([sources[a][["close"]].to_numpy() for a in ASSETS], axis=1),
            time=bars.timestamp_ms.to_numpy(),
            assets=np.array(ASSETS),
            fields=np.array(["close"]),
        )
        expected = CurrencyStrength().batch(tensor, {}).data[:, 0, 0]
        np.testing.assert_allclose(featured.strength, expected)
        self.assertEqual(featured.timestamp_ms.tolist(), bars.timestamp_ms.tolist())

    def test_gap_invalidates_only_current_and_later_decisions_that_day(self):
        bars, sources = fixture()
        complete = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        sources[ASSETS[0]] = sources[ASSETS[0]].loc[lambda f: f.timestamp_ms != START + 2 * STEP]
        missing = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        np.testing.assert_allclose(missing.strength.iloc[:3], complete.strength.iloc[:3])
        self.assertTrue(missing.strength.iloc[3:].isna().all())
        self.assertEqual(missing.timestamp_ms.tolist(), bars.timestamp_ms.tolist())

    def test_all_sources_missing_same_bar_is_detected(self):
        bars, sources = fixture()
        sources = {a: f.loc[f.timestamp_ms != START + 2 * STEP] for a, f in sources.items()}
        featured = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        self.assertEqual(featured.indicators_available.tolist(), [0, 1, 1, 0, 0, 0, 0, 0, 0])

    def test_missing_mapping_is_error_but_empty_source_skips_without_dropping_bars(self):
        bars, sources = fixture()
        sources.pop(ASSETS[0])
        with self.assertRaisesRegex(ValueError, "Missing required indicator sources"):
            run_backtest(request=request(), bars=bars, strategy=strategy(), feature_bars=sources)
        sources[ASSETS[0]] = pd.DataFrame()
        for engine in BacktestEngine:
            result = run_backtest(
                request=request(engine), bars=bars, strategy=strategy(), feature_bars=sources
            )
            self.assertEqual(result.fills, [])
            self.assertEqual(len(result.equity_curve), 8)

    def test_missing_history_invalidates_session_and_next_complete_day_recovers(self):
        bars, sources = fixture()
        next_bars, next_sources = fixture()
        next_bars.timestamp_ms += DAY
        for frame in next_sources.values():
            frame.timestamp_ms += DAY
        bars = pd.concat([bars.iloc[2:], next_bars], ignore_index=True)
        sources = {
            a: pd.concat([f.iloc[2:], next_sources[a]], ignore_index=True)
            for a, f in sources.items()
        }
        featured = build_feature_frame(
            bars=bars, strategy=strategy(), timeframe="M5", feature_bars=sources
        )
        self.assertTrue(
            (featured.loc[featured.timestamp_ms < START + DAY, "indicators_available"] == 0).all()
        )
        self.assertTrue(
            (featured.loc[featured.timestamp_ms >= START + DAY, "indicators_available"] == 1).all()
        )

    def test_both_engines_preserve_signal_exit_during_source_gap(self):
        bars, sources = fixture()
        bars.loc[bars.timestamp_ms == START + 3 * STEP, "close"] = 0.5
        sources[ASSETS[0]] = sources[ASSETS[0]].loc[lambda f: f.timestamp_ms != START + 2 * STEP]
        results = [
            run_backtest(
                request=request(engine), bars=bars, strategy=strategy(), feature_bars=sources
            )
            for engine in BacktestEngine
        ]
        self.assertEqual(results[0].fills, results[1].fills)
        self.assertEqual(results[0].equity_curve, results[1].equity_curve)
        self.assertEqual(
            [f.timestamp_ms for f in results[0].fills], [START + STEP, START + 4 * STEP]
        )

    def test_both_engines_keep_protective_exit_and_suppress_reentry(self):
        bars, sources = fixture()
        bars.loc[bars.timestamp_ms == START + 3 * STEP, "low"] = 0.5
        sources[ASSETS[0]] = sources[ASSETS[0]].loc[lambda f: f.timestamp_ms != START + 2 * STEP]
        model = strategy(ProtectiveExitSpec(stop_loss_pct=10))
        results = [
            run_backtest(request=request(engine), bars=bars, strategy=model, feature_bars=sources)
            for engine in BacktestEngine
        ]
        self.assertEqual(results[0].fills, results[1].fills)
        self.assertEqual(len(results[0].fills), 2)
        self.assertEqual(results[0].fills[-1].timestamp_ms, START + 3 * STEP)


class SourceLoaderTests(unittest.TestCase):
    def test_deduplicated_loading_matches_supplied_data_for_each_engine(self):
        bars, sources = fixture()
        sources["TEST"] = bars

        class Adapter:
            def __init__(self):
                self.calls = []

            def fetch_bars(self, *, symbol, timeframe, start_ms, end_ms, exchange=None, limit=None):
                self.calls.append((symbol, start_ms, end_ms, limit, exchange))
                frame = sources[symbol]
                if start_ms is not None:
                    frame = frame.loc[frame.timestamp_ms >= start_ms]
                frame = frame.loc[frame.timestamp_ms < end_ms]
                return frame.tail(limit) if limit is not None else frame.copy()

        model = strategy()
        model = replace(model, indicator_requirements=model.indicator_requirements * 2)
        for engine in BacktestEngine:
            adapter = Adapter()
            loaded = run_backtest_with_market_data(
                request=request(engine), strategy=model, data_adapter=adapter
            )
            supplied = run_backtest(
                request=request(engine), bars=bars, strategy=model, feature_bars=sources
            )
            self.assertEqual(loaded.fills, supplied.fills)
            self.assertEqual(loaded.equity_curve, supplied.equity_curve)
            self.assertEqual(len(adapter.calls), len(sources) * 2)
            self.assertEqual(set(c[0] for c in adapter.calls), set(sources))

    def test_traded_source_is_fetched_only_once_per_interval(self):
        bars, sources = fixture()
        calls = []

        class Adapter:
            def fetch_bars(self, **kwargs):
                calls.append(kwargs)
                return sources[kwargs["symbol"]]

        bundle = load_market_data_bundle(
            request=replace(request(), symbols=[ASSETS[0]]),
            strategy=strategy(),
            data_adapter=Adapter(),
        )
        self.assertEqual(len(calls), len(ASSETS) * 2)
        self.assertEqual(bundle.traded_bars.symbol.unique().tolist(), [ASSETS[0]])
