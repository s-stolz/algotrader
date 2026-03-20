from __future__ import annotations

from typing import Dict

import numpy as np

from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase
from .utils import rolling_mean


class SMA(IndicatorBase):
    """Simple Moving Average (SMA)."""
    spec = IndicatorSpec(
        id="sma",
        name="Simple Moving Average",
        parameters={
            "window": {"type": "int", "default": 20, "min": 1},
            "source": {
                "type": "string",
                "default": "close",
                "options": ["close", "open", "high", "low"],
            },
        },
        outputs=["sma"],
        required_fields=["close"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("window", 20)),
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute SMA over the requested source field."""
        window = int(params.get("window", 20))
        source = params.get("source", "close")
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        series = data.data[:, :, field_idx]
        sma = rolling_mean(series, window)
        out = sma[:, :, np.newaxis]
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["sma"], dtype=object),
            },
        )
