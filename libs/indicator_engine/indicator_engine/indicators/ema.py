from __future__ import annotations

from typing import Dict

import numpy as np

from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase
from .utils import ema


class EMA(IndicatorBase):
    """Exponential Moving Average (EMA)."""

    spec = IndicatorSpec(
        id="ema",
        name="Exponential Moving Average",
        parameters={
            "window": {"type": "int", "default": 20, "min": 1},
            "source": {
                "type": "string",
                "default": "close",
                "options": ["close", "open", "high", "low"],
            },
        },
        outputs=["ema"],
        required_fields=["close"],
        supports_update=True,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("window", 20)),
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute EMA over the requested source field."""
        window = int(params.get("window", 20))
        source = params.get("source", "close")
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        series = data.data[:, :, field_idx]
        values = ema(series, window)
        values[: window - 1] = np.nan
        out = values[:, :, np.newaxis]
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["ema"], dtype=object),
            },
        )

    def init_state(self, data: BarTensor, params: Dict) -> Dict:
        """Seed through the prior bar; UpdateEngine applies the current row next."""
        source_idx = int(np.where(data.fields == params.get("source", "close"))[0][0])
        window = int(params.get("window", 20))
        history = ema(data.data[:-1, :, source_idx], window)
        previous = history[-1] if len(history) else np.full(len(data.assets), np.nan)
        return {
            "source_idx": source_idx,
            "window": window,
            "latest": previous,
            "prior": previous,
            "timestamp": None,
        }

    def update(self, state: Dict, *, new_row, asset_mask, timestamp_ms):
        """Advance the recurrence, replacing rather than compounding same-bar updates."""
        previous = state["prior"] if state["timestamp"] == timestamp_ms else state["latest"]
        values = ema(np.stack([previous, new_row[:, state["source_idx"]]]), state["window"])[-1]
        latest = np.where(asset_mask, values, state["latest"])
        state = {**state, "prior": previous, "latest": latest, "timestamp": timestamp_ms}
        return state, latest[:, np.newaxis]
