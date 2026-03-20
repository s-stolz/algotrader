from __future__ import annotations

from typing import Dict

import numpy as np

from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase
from .utils import rolling_mean, rolling_std


class BBANDS(IndicatorBase):
    """Bollinger Bands."""
    spec = IndicatorSpec(
        id="bbands",
        name="Bollinger Bands",
        parameters={
            "length": {"type": "int", "default": 20, "min": 1},
            "lower_std": {"type": "float", "default": 2.0, "min": 0.0},
            "upper_std": {"type": "float", "default": 2.0, "min": 0.0},
            "ma_mode": {
                "type": "string",
                "default": "SMA",
                "options": ["SMA", "EMA"],
            },
            "source": {
                "type": "string",
                "default": "close",
                "options": ["close", "open", "high", "low"],
            },
        },
        outputs=["lower", "mid", "upper"],
        required_fields=["close"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("length", 20)),
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute lower/mid/upper bands using rolling mean and std."""
        length = int(params.get("length", 20))
        lower_std = float(params.get("lower_std", 2.0))
        upper_std = float(params.get("upper_std", 2.0))
        source = params.get("source", "close")
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        series = data.data[:, :, field_idx]
        mid = rolling_mean(series, length)
        std = rolling_std(series, length)
        lower = mid - lower_std * std
        upper = mid + upper_std * std
        out = np.stack([lower, mid, upper], axis=2)
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["lower", "mid", "upper"], dtype=object),
            },
        )
