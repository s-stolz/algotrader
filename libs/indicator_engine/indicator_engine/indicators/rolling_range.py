"""Trailing candle extremes, including the current candle."""

import numpy as np
import pandas as pd

from ..catalog import IndicatorRegistration
from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase


class RollingRange(IndicatorBase):
    spec = IndicatorSpec(
        id="rolling_range",
        name="Rolling High / Low",
        parameters={"window": {"type": "int", "default": 20, "min": 1, "max": 5000}},
        outputs=["highest_high", "lowest_low"],
        required_fields=["high", "low"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: int(params.get("window", 20)),
    )

    def batch(self, data: BarTensor, params: dict) -> Tensor:
        window = params.get("window", 20)
        if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= 5000:
            raise ValueError("window must be an integer between 1 and 5000")
        values = []
        for field, operation in (("high", "max"), ("low", "min")):
            column = int(np.flatnonzero(data.fields == field)[0])
            rolling = pd.DataFrame(data.data[:, :, column]).rolling(window, min_periods=window)
            values.append(getattr(rolling, operation)().to_numpy())
        return Tensor(
            data=np.stack(values, axis=-1),
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(self.spec.outputs, dtype=object),
            },
        )


ROLLING_RANGE_REGISTRATION = IndicatorRegistration(
    public_id=8,
    implementation=RollingRange,
    supports_live=True,
    overlay=True,
    outputs={
        "highest_high": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#EF5350"}},
        "lowest_low": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#26A69A"}},
    },
)
