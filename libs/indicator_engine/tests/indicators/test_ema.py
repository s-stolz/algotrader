import unittest

import numpy as np
import pandas as pd
from indicator_engine import run
from indicator_engine.core.history import HistoryPolicy
from indicator_engine.core.params import ParamGrid
from indicator_engine.defaults import get_update_engine


class EMATests(unittest.TestCase):
    def test_registered_ema_values_warmup_source_and_streaming_parity(self) -> None:
        frame = pd.DataFrame({"close": [1.0, 2.0, 4.0, 8.0], "open": [2.0, 4.0, 8.0, 16.0]})
        result = run("ema", frame, {"window": 3, "source": "open"})
        expected = [np.nan, np.nan, 5.5, 10.75]
        np.testing.assert_allclose(result["ema"], expected, equal_nan=True)
        engine = get_update_engine(history=HistoryPolicy(mode="rolling", max_rows=50))
        engine.register_indicator(
            indicator_id="ema",
            timeframe="M1",
            assets=["TEST"],
            fields=["open"],
            param_grid=ParamGrid({"window": 3, "source": "open"}),
        )
        streamed = []
        for i, value in enumerate(frame["open"]):
            engine.on_bar("M1", (i + 1) * 60_000, np.array([[99.0]]))
            tensor = engine.on_bar("M1", (i + 1) * 60_000, np.array([[value]]))["ema"]
            streamed.append(float(tensor.data[0, 0, 0, 0]))
        np.testing.assert_allclose(streamed, expected, equal_nan=True)

    def test_window_one_returns_source_without_warmup(self) -> None:
        result = run("ema", pd.DataFrame({"close": [2.0, 4.0, 1.0]}), {"window": 1})
        np.testing.assert_allclose(result["ema"], [2.0, 4.0, 1.0])
