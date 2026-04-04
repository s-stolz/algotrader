from __future__ import annotations

from typing import Dict

import numpy as np

from ..core.bars import BarTensor
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase


class CurrencyStrength(IndicatorBase):
    """Currency strength index computed from fixed major FX pairs."""
    spec = IndicatorSpec(
        id="currency_strength",
        name="Currency Strength",
        parameters={},
        outputs=["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "USD"],
        required_fields=["close"],
        required_assets=[
            "EURUSD",
            "USDJPY",
            "USDCHF",
            "GBPUSD",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
        ],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: 2,
    )

    def batch(self, data: BarTensor, params: Dict) -> Tensor:
        """Compute currency strength from the fixed FX basket."""
        source = "close"
        if source not in data.fields:
            raise KeyError(f"Field not found: {source}")
        field_idx = int(np.where(data.fields == source)[0][0])
        required = self.spec.required_assets or []
        missing = [asset for asset in required if asset not in data.assets]
        if missing:
            raise KeyError(f"Missing required assets: {missing}")
        indices = [int(np.where(data.assets == asset)[0][0]) for asset in required]

        close = data.data[:, indices, field_idx]
        prev = np.vstack([np.full((1, close.shape[1]), np.nan), close[:-1]])

        pair = {name: i for i, name in enumerate(required)}

        def get_val(prev_val: np.ndarray, curr_val: np.ndarray) -> np.ndarray:
            return (curr_val - prev_val) / ((curr_val + prev_val) / 2.0) * 10000.0

        def get_val_m(
            prev_val1: np.ndarray,
            curr_val1: np.ndarray,
            prev_val2: np.ndarray,
            curr_val2: np.ndarray,
        ) -> np.ndarray:
            return get_val(prev_val1 * prev_val2, curr_val1 * curr_val2)

        def get_val_d(
            prev_val1: np.ndarray,
            curr_val1: np.ndarray,
            prev_val2: np.ndarray,
            curr_val2: np.ndarray,
        ) -> np.ndarray:
            return get_val(prev_val1 / prev_val2, curr_val1 / curr_val2)

        eurusd = get_val(prev[:, pair["EURUSD"]], close[:, pair["EURUSD"]])
        gbpusd = get_val(prev[:, pair["GBPUSD"]], close[:, pair["GBPUSD"]])
        usdjpy = get_val(prev[:, pair["USDJPY"]], close[:, pair["USDJPY"]])
        audusd = get_val(prev[:, pair["AUDUSD"]], close[:, pair["AUDUSD"]])
        nzdusd = get_val(prev[:, pair["NZDUSD"]], close[:, pair["NZDUSD"]])
        usdcad = get_val(prev[:, pair["USDCAD"]], close[:, pair["USDCAD"]])
        usdchf = get_val(prev[:, pair["USDCHF"]], close[:, pair["USDCHF"]])

        eurgbp = get_val_d(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
        )
        eurjpy = get_val_m(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
        )
        euraud = get_val_d(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
        )
        eurnzd = get_val_d(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
        )
        eurcad = get_val_d(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
        )
        eurchf = get_val_m(
            prev[:, pair["EURUSD"]],
            close[:, pair["EURUSD"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        gbpjpy = get_val_m(
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
        )
        gbpaud = get_val_m(
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
        )
        gbpnzd = get_val_m(
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
        )
        gbpcad = get_val_m(
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
        )
        gbpchf = get_val_m(
            prev[:, pair["GBPUSD"]],
            close[:, pair["GBPUSD"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        jpyaud = get_val_d(
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
        )
        jpynzd = get_val_d(
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
        )
        jpycad = get_val_d(
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
        )
        jpychf = get_val_d(
            prev[:, pair["USDJPY"]],
            close[:, pair["USDJPY"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        audnzd = get_val_m(
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
        )
        audcad = get_val_m(
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
        )
        audchf = get_val_m(
            prev[:, pair["AUDUSD"]],
            close[:, pair["AUDUSD"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        nzdcad = get_val_m(
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
        )
        nzdchf = get_val_m(
            prev[:, pair["NZDUSD"]],
            close[:, pair["NZDUSD"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        cadchf = get_val_m(
            prev[:, pair["USDCAD"]],
            close[:, pair["USDCAD"]],
            prev[:, pair["USDCHF"]],
            close[:, pair["USDCHF"]],
        )

        strength = np.full((close.shape[0], 8), np.nan, dtype=np.float64)
        strength[:, 0] = (
            eurusd + eurgbp + eurjpy + euraud + eurnzd + eurcad + eurchf
        ) / 7.0
        strength[:, 1] = (
            gbpusd + eurgbp + gbpjpy + gbpaud + gbpnzd + gbpcad + gbpchf
        ) / 7.0
        strength[:, 2] = (
            usdjpy + eurjpy + gbpjpy + jpyaud + jpynzd + jpycad + jpychf
        ) / 7.0
        strength[:, 3] = (
            audusd + euraud + gbpaud + jpyaud + audnzd + audcad + audchf
        ) / 7.0
        strength[:, 4] = (
            nzdusd + eurnzd + gbpnzd + jpynzd + audnzd + nzdcad + nzdchf
        ) / 7.0
        strength[:, 5] = (
            usdcad + eurcad + gbpcad + jpycad + audcad + nzdcad + cadchf
        ) / 7.0
        strength[:, 6] = (
            usdchf + eurchf + gbpchf + jpychf + audchf + nzdchf + cadchf
        ) / 7.0
        strength[:, 7] = (
            -eurusd - gbpusd + usdjpy - audusd - nzdusd + usdcad + usdchf
        ) / 7.0

        time = data.time
        if np.issubdtype(time.dtype, np.datetime64):
            dates = time.astype("datetime64[D]")
        else:
            dates = time.astype("datetime64[ms]").astype("datetime64[D]")

        out = np.full_like(strength, np.nan, dtype=np.float64)
        for col in range(strength.shape[1]):
            running = 0.0
            last_date = None
            for t in range(strength.shape[0]):
                if last_date is None or dates[t] != last_date:
                    running = 0.0
                    last_date = dates[t]
                val = strength[t, col]
                if np.isnan(val):
                    out[t, col] = np.nan
                    continue
                running += val
                out[t, col] = running

        out = out[:, np.newaxis, :]
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": np.array(["FX"], dtype=object),
                "output": np.array(self.spec.outputs, dtype=object),
            },
        )
