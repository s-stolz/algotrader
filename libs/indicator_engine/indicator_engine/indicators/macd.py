from __future__ import annotations

from typing import Dict

import numpy as np

from ..catalog import IndicatorRegistration
from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase
from .utils import ema


class MACD(IndicatorBase):
    """Moving Average Convergence Divergence (MACD)."""

    spec = IndicatorSpec(
        id="macd",
        name="Moving Average Convergence Divergence",
        parameters={
            "fast": {"type": "int", "default": 12, "min": 1},
            "slow": {"type": "int", "default": 26, "min": 1},
            "signal": {"type": "int", "default": 9, "min": 1},
            "source": {
                "type": "string",
                "default": "close",
                "options": ["close", "open", "high", "low"],
            },
        },
        outputs=["macd", "signal", "hist"],
        required_fields=["close"],
        supports_update=True,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("slow", 26)) + int(params.get("signal", 9)),
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute MACD, signal, and histogram series."""
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        source = params.get("source", "close")
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        series = data.data[:, :, field_idx]
        ema_fast = ema(series, fast)
        ema_slow = ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal)
        hist = macd_line - signal_line
        out = np.stack([macd_line, signal_line, hist], axis=2)
        warmup = self.spec.warmup(params)
        if warmup > 1:
            out[: warmup - 1, :, :] = np.nan
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["macd", "signal", "hist"], dtype=object),
            },
        )

    def init_state(self, data: BarTensor, params: Dict) -> Dict:
        """Seed through the prior bar; UpdateEngine applies the current row next."""
        source_idx = int(np.where(data.fields == params.get("source", "close"))[0][0])
        fast, slow, signal = (
            int(params.get(key, default))
            for key, default in (("fast", 12), ("slow", 26), ("signal", 9))
        )
        series = data.data[:-1, :, source_idx]
        fast_values = ema(series, fast)
        slow_values = ema(series, slow)
        signal_values = ema(fast_values - slow_values, signal)
        previous = np.stack([fast_values[-1], slow_values[-1], signal_values[-1]])
        return {
            "source_idx": source_idx,
            "periods": (fast, slow, signal),
            "latest": previous,
            "prior": previous,
            "timestamp": None,
        }

    def update(self, state: Dict, *, new_row, asset_mask, timestamp_ms):
        """Advance the recurrence, replacing rather than compounding same-bar updates."""
        previous = state["prior"] if state["timestamp"] == timestamp_ms else state["latest"]
        fast, slow, signal = state["periods"]
        source = new_row[:, state["source_idx"]]
        fast_values = ema(np.stack([previous[0], source]), fast)[-1]
        slow_values = ema(np.stack([previous[1], source]), slow)[-1]
        macd_values = fast_values - slow_values
        signal_values = ema(np.stack([previous[2], macd_values]), signal)[-1]
        latest = np.where(
            asset_mask, np.stack([fast_values, slow_values, signal_values]), state["latest"]
        )
        state = {**state, "prior": previous, "latest": latest, "timestamp": timestamp_ms}
        macd_values = latest[0] - latest[1]
        return state, np.stack([macd_values, latest[2], macd_values - latest[2]], axis=1)


MACD_REGISTRATION = IndicatorRegistration(
    public_id=4,
    implementation=MACD,
    supports_live=True,
    overlay=False,
    outputs={
        "hist": {
            "type": "histogram",
            "plotOptions": {
                "color": "#089981",
                "negativeColor": "#f23645",
                "priceFormat": {"minMove": 1e-05},
            },
        },
        "macd": {
            "type": "line",
            "plotOptions": {
                "lineWidth": 2,
                "color": "#2962ff",
                "priceFormat": {"minMove": 1e-05},
            },
        },
        "signal": {
            "type": "line",
            "plotOptions": {
                "lineWidth": 2,
                "color": "#f23645",
                "priceFormat": {"minMove": 1e-05},
            },
        },
    },
)
