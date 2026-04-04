from __future__ import annotations

from typing import Dict

import numpy as np

from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase


class RSI(IndicatorBase):
    """Relative Strength Index (RSI)."""
    spec = IndicatorSpec(
        id="rsi",
        name="Relative Strength Index",
        parameters={
            "length": {"type": "int", "default": 14, "min": 1},
            "source": {
                "type": "string",
                "default": "close",
                "options": ["close", "open", "high", "low"],
            },
        },
        outputs=["rsi"],
        required_fields=["close"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("length", 14)) + 1,
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute RSI using Wilder's smoothing."""
        length = int(params.get("length", 14))
        source = params.get("source", "close")
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        series = data.data[:, :, field_idx]
        rsi = _rsi(series, length)
        out = rsi[:, :, np.newaxis]
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["rsi"], dtype=object),
            },
        )


def _rsi(series: np.ndarray, length: int) -> np.ndarray:
    if length <= 0:
        raise ValueError("length must be > 0")
    t_len, a_len = series.shape
    out = np.full_like(series, np.nan, dtype=np.float64)
    for a_idx in range(a_len):
        x = series[:, a_idx]
        if t_len < length + 1:
            continue
        deltas = np.diff(x)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        if np.isnan(x[: length + 1]).any():
            continue
        avg_gain = np.mean(gains[:length])
        avg_loss = np.mean(losses[:length])
        if np.isnan(avg_gain) or np.isnan(avg_loss):
            continue
        rs = np.inf if avg_loss == 0 else avg_gain / avg_loss
        out[length, a_idx] = 100.0 - (100.0 / (1.0 + rs))
        for t in range(length, len(deltas)):
            gain = gains[t]
            loss = losses[t]
            if np.isnan(gain) or np.isnan(loss):
                out[t + 1, a_idx] = np.nan
                avg_gain = np.nan
                avg_loss = np.nan
                continue
            if np.isnan(avg_gain) or np.isnan(avg_loss):
                out[t + 1, a_idx] = np.nan
                continue
            avg_gain = (avg_gain * (length - 1) + gain) / length
            avg_loss = (avg_loss * (length - 1) + loss) / length
            rs = np.inf if avg_loss == 0 else avg_gain / avg_loss
            out[t + 1, a_idx] = 100.0 - (100.0 / (1.0 + rs))
    return out
