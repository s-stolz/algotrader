import unittest

import numpy as np
from indicator_engine import BatchEngine, HistoryPolicy, UpdateEngine, get_registry
from indicator_engine.core.bars import BarTensor
from indicator_engine.indicators.currency_strength import CurrencyStrength


class CurrencyStrengthTests(unittest.TestCase):
    @staticmethod
    def _required_assets() -> list[str]:
        return [
            "EURUSD",
            "USDJPY",
            "USDCHF",
            "GBPUSD",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
        ]

    def test_currency_strength_raises_when_required_assets_missing(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[1.1]]], dtype=np.float64),
            time=np.array([1000, 2000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(KeyError):
            CurrencyStrength().batch(bar, {})

    def test_currency_strength_constant_prices_are_zero_after_first_row(self) -> None:
        assets = self._required_assets()
        rows = 4
        cols = len(assets)
        data = np.full((rows, cols, 1), 1.0, dtype=np.float64)
        bar = BarTensor(
            data=data,
            time=np.array([1000, 2000, 3000, 4000], dtype=np.int64),
            assets=np.array(assets, dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = CurrencyStrength().batch(bar, {})

        self.assertEqual(out.data.shape, (rows, 1, 8))
        self.assertTrue(np.isnan(out.data[0, 0, :]).all())
        self.assertTrue(np.allclose(out.data[1:, 0, :], 0.0))
        self.assertEqual(out.coords["asset"].tolist(), ["FX"])


class CurrencyStrengthUpdateTests(unittest.TestCase):
    def _bars(self, count: int = 580) -> BarTensor:
        assets = list(reversed(CurrencyStrength.spec.required_assets or []))
        assets.append("EXTRA")
        random = np.random.default_rng(42)
        prices = np.exp(np.cumsum(random.normal(0, 0.001, (count, len(assets))), axis=0))
        return BarTensor(
            data=prices[:, :, np.newaxis],
            time=86_400_000 * 20000 - 300_000 + np.arange(count) * 300_000,
            assets=np.array(assets, dtype=object),
            fields=np.array(["close"], dtype=object),
        )

    def _engine(self, bars: BarTensor) -> UpdateEngine:
        engine = UpdateEngine(get_registry(), HistoryPolicy(mode="rolling", max_rows=2))
        engine.register_indicator("currency_strength", "M5", assets=bars.assets, fields=bars.fields)
        return engine

    def test_aggregate_updates_match_batch_across_days_with_tiny_buffer(self) -> None:
        bars = self._bars()
        expected = BatchEngine(get_registry()).run("currency_strength", bars).tensor
        engine = self._engine(bars)
        values = []
        for timestamp, row in zip(bars.time, bars.data, strict=True):
            result = engine.on_bar("M5", int(timestamp), row)["currency_strength"]
            self.assertEqual(result.coords["asset"].tolist(), ["FX"])
            values.append(result.data[0])
        np.testing.assert_allclose(values, expected.data, rtol=1e-12, atol=1e-12)
        stored = engine.get_result_buffer("currency_strength", "M5").view()
        self.assertEqual(stored.coords["asset"].tolist(), ["FX"])
        np.testing.assert_allclose(stored.data, expected.data[-2:])

    def test_correction_replaces_current_return_including_midnight(self) -> None:
        bars = self._bars(5)
        engine = self._engine(bars)
        for index, timestamp in enumerate(bars.time):
            engine.on_bar("M5", int(timestamp), bars.data[index])
            bars.data[index] *= 1.001
            actual = engine.on_bar("M5", int(timestamp), bars.data[index])["currency_strength"]
            prefix = BarTensor(
                data=bars.data[: index + 1],
                time=bars.time[: index + 1],
                assets=bars.assets,
                fields=bars.fields,
            )
            expected = CurrencyStrength().batch(prefix, {})
            np.testing.assert_allclose(actual.data[0, :, :, 0], expected.data[-1])

    def test_split_asset_arrivals_use_assembled_candle(self) -> None:
        bars = self._bars(8)
        engine = self._engine(bars)
        first_mask = np.arange(len(bars.assets)) % 2 == 0
        values = []
        for timestamp, row in zip(bars.time, bars.data, strict=True):
            first = np.where(first_mask[:, None], row, np.nan)
            second = np.where(~first_mask[:, None], row, np.nan)
            self.assertNotIn(
                "currency_strength", engine.on_bar("M5", int(timestamp), first, first_mask)
            )
            result = engine.on_bar("M5", int(timestamp), second, ~first_mask)
            values.append(result["currency_strength"].data[0, :, :, 0])
        expected = CurrencyStrength().batch(bars, {})
        np.testing.assert_allclose(values, expected.data)

    def test_nan_inputs_preserve_batch_calculation_semantics(self) -> None:
        bars = self._bars(8)
        bars.data[3, 0, 0] = np.nan
        engine = self._engine(bars)
        values = [
            engine.on_bar("M5", int(timestamp), row)["currency_strength"].data[0, :, :, 0]
            for timestamp, row in zip(bars.time, bars.data, strict=True)
        ]
        np.testing.assert_allclose(values, CurrencyStrength().batch(bars, {}).data)

    def test_seeded_state_matches_batch_without_reapplying_current_candle(self) -> None:
        bars = self._bars(100)
        indicator = CurrencyStrength()
        state = indicator.init_state(bars, {})
        _, actual = indicator.update(
            state,
            new_row=bars.data[-1],
            asset_mask=np.ones(len(bars.assets), dtype=bool),
            timestamp_ms=int(bars.time[-1]),
        )
        np.testing.assert_allclose(actual, indicator.batch(bars, {}).data[-1])


if __name__ == "__main__":
    unittest.main()
