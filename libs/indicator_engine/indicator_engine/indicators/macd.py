from __future__ import annotations

from typing import Dict

import numpy as np

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
        supports_update=False,
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
