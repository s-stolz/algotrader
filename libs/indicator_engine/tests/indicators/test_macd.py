import unittest

import numpy as np
import pandas as pd
from indicator_engine import run
from indicator_engine.core.bars import BarTensor
from indicator_engine.core.history import HistoryPolicy
from indicator_engine.core.params import ParamGrid
from indicator_engine.defaults import get_update_engine
from indicator_engine.indicators.macd import MACD


class MACDTests(unittest.TestCase):
    def test_macd_constant_series_is_nan_during_warmup_then_zero(self) -> None:
        bar = BarTensor(
            data=np.array(
                [[[10.0]], [[10.0]], [[10.0]], [[10.0]], [[10.0]], [[10.0]]],
                dtype=np.float64,
            ),
            time=np.array([1000, 2000, 3000, 4000, 5000, 6000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        out = MACD().batch(bar, {"fast": 2, "slow": 3, "signal": 2, "source": "close"})
        macd = out.data[:, 0, 0]
        signal = out.data[:, 0, 1]
        hist = out.data[:, 0, 2]

        self.assertTrue(np.all(np.isnan(macd[:4])))
        self.assertTrue(np.all(np.isnan(signal[:4])))
        self.assertTrue(np.all(np.isnan(hist[:4])))
        self.assertTrue(np.allclose(macd[4:], 0.0))
        self.assertTrue(np.allclose(signal[4:], 0.0))
        self.assertTrue(np.allclose(hist[4:], 0.0))

    def test_streaming_matches_batch_after_buffer_rollover_and_bar_replacement(self) -> None:
        engine = get_update_engine(history=HistoryPolicy(mode="rolling", max_rows=5))
        params = {"fast": 2, "slow": 3, "signal": 2, "source": "close"}
        engine.register_indicator(
            indicator_id="macd",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
            param_grid=ParamGrid(params),
        )
        rows = []
        for i in range(30):
            row = [10.0 + (i % 7), 20.0 - (i % 5)]
            if i == 12:
                row[0] = np.nan
            timestamp = (i + 1) * 60_000
            engine.on_bar("M1", timestamp, np.array([[99.0], [99.0]]))
            tensor = engine.on_bar("M1", timestamp, np.asarray(row)[:, np.newaxis])["macd"]
            rows.append(row)
            for asset_idx in range(2):
                batch = run("macd", pd.DataFrame({"close": [r[asset_idx] for r in rows]}), params)
                np.testing.assert_allclose(
                    tensor.data[0, asset_idx, :, 0],
                    batch.iloc[-1].to_numpy(),
                    equal_nan=True,
                    atol=1e-14,
                )

    def test_macd_raises_for_unknown_source_field(self) -> None:
        bar = BarTensor(
            data=np.array([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float64),
            time=np.array([1000, 2000, 3000], dtype=np.int64),
            assets=np.array(["EURUSD"], dtype=object),
            fields=np.array(["close"], dtype=object),
        )

        with self.assertRaises(KeyError):
            MACD().batch(bar, {"fast": 2, "slow": 3, "signal": 2, "source": "open"})


if __name__ == "__main__":
    unittest.main()
