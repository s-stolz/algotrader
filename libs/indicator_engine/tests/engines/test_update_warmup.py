import unittest

import numpy as np

from indicator_engine.core.history import HistoryPolicy
from indicator_engine.core.params import ParamGrid
from indicator_engine.defaults import get_registry
from indicator_engine.engines.update import UpdateEngine


class UpdateEngineWarmupTests(unittest.TestCase):
    def test_sma_emits_nan_until_warmup_is_reached(self) -> None:
        engine = UpdateEngine(registry=get_registry(), history=HistoryPolicy(mode="rolling", max_rows=50))
        engine.register_indicator(
            indicator_id="sma",
            timeframe="M1",
            assets=["EURUSD"],
            fields=["close"],
            param_grid=ParamGrid({"window": [3], "source": ["close"]}),
        )

        v1 = engine.on_bar("M1", 1000, np.array([[1.0]], dtype=np.float64))["sma"].data[0, 0, 0, 0]
        v2 = engine.on_bar("M1", 2000, np.array([[2.0]], dtype=np.float64))["sma"].data[0, 0, 0, 0]
        v3 = engine.on_bar("M1", 3000, np.array([[3.0]], dtype=np.float64))["sma"].data[0, 0, 0, 0]

        self.assertTrue(np.isnan(v1))
        self.assertTrue(np.isnan(v2))
        self.assertAlmostEqual(v3, 2.0)

    def test_rsi_emits_nan_until_warmup_then_value(self) -> None:
        engine = UpdateEngine(registry=get_registry(), history=HistoryPolicy(mode="rolling", max_rows=50))
        engine.register_indicator(
            indicator_id="rsi",
            timeframe="M1",
            assets=["EURUSD"],
            fields=["close"],
            param_grid=ParamGrid({"length": [2], "source": ["close"]}),
        )

        v1 = engine.on_bar("M1", 1000, np.array([[1.0]], dtype=np.float64))["rsi"].data[0, 0, 0, 0]
        v2 = engine.on_bar("M1", 2000, np.array([[2.0]], dtype=np.float64))["rsi"].data[0, 0, 0, 0]
        v3 = engine.on_bar("M1", 3000, np.array([[3.0]], dtype=np.float64))["rsi"].data[0, 0, 0, 0]

        self.assertTrue(np.isnan(v1))
        self.assertTrue(np.isnan(v2))
        self.assertAlmostEqual(v3, 100.0)

    def test_macd_warmup_gate_delays_output_until_slow_plus_signal(self) -> None:
        engine = UpdateEngine(registry=get_registry(), history=HistoryPolicy(mode="rolling", max_rows=50))
        engine.register_indicator(
            indicator_id="macd",
            timeframe="M1",
            assets=["EURUSD"],
            fields=["close"],
            param_grid=ParamGrid({"fast": [2], "slow": [3], "signal": [2], "source": ["close"]}),
        )

        vals = []
        for i, ts in enumerate([1000, 2000, 3000, 4000, 5000], start=1):
            value = engine.on_bar("M1", ts, np.array([[10.0]], dtype=np.float64))["macd"].data[0, 0, 0, 0]
            vals.append(value)

        self.assertTrue(np.isnan(vals[0]))
        self.assertTrue(np.isnan(vals[1]))
        self.assertTrue(np.isnan(vals[2]))
        self.assertTrue(np.isnan(vals[3]))
        self.assertAlmostEqual(vals[4], 0.0)


if __name__ == "__main__":
    unittest.main()
