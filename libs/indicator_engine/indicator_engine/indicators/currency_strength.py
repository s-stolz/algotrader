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
        close, prev, pair = _currency_strength_inputs(
            data,
            source="close",
            required_assets=self.spec.required_assets,
        )
        strength = _raw_currency_strength(close=close, prev=prev, pair=pair)
        out = _daily_cumulative_strength(strength=strength, time=data.time)[:, np.newaxis, :]
        return Tensor(
            data=out,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": np.array(["FX"], dtype=object),
                "output": np.array(self.spec.outputs, dtype=object),
            },
        )


def _currency_strength_inputs(
    data: BarTensor,
    *,
    source: str,
    required_assets: list[str] | None,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    if source not in data.fields:
        raise KeyError(f"Field not found: {source}")
    required = required_assets or []
    missing = [asset for asset in required if asset not in data.assets]
    if missing:
        raise KeyError(f"Missing required assets: {missing}")

    field_idx = int(np.where(data.fields == source)[0][0])
    indices = [int(np.where(data.assets == asset)[0][0]) for asset in required]
    close = data.data[:, indices, field_idx]
    prev = np.vstack([np.full((1, close.shape[1]), np.nan), close[:-1]])
    return close, prev, {name: idx for idx, name in enumerate(required)}


def _pair_return(prev_val: np.ndarray, curr_val: np.ndarray) -> np.ndarray:
    return (curr_val - prev_val) / ((curr_val + prev_val) / 2.0) * 10000.0


def _mul_pair_return(
    prev_val1: np.ndarray,
    curr_val1: np.ndarray,
    prev_val2: np.ndarray,
    curr_val2: np.ndarray,
) -> np.ndarray:
    return _pair_return(prev_val1 * prev_val2, curr_val1 * curr_val2)


def _div_pair_return(
    prev_val1: np.ndarray,
    curr_val1: np.ndarray,
    prev_val2: np.ndarray,
    curr_val2: np.ndarray,
) -> np.ndarray:
    return _pair_return(prev_val1 / prev_val2, curr_val1 / curr_val2)


def _series_for_pair(
    *,
    pair: dict[str, int],
    prev: np.ndarray,
    close: np.ndarray,
    asset: str,
) -> np.ndarray:
    return _pair_return(prev[:, pair[asset]], close[:, pair[asset]])


def _raw_currency_strength(
    *,
    close: np.ndarray,
    prev: np.ndarray,
    pair: dict[str, int],
) -> np.ndarray:
    eurusd = _series_for_pair(pair=pair, prev=prev, close=close, asset="EURUSD")
    gbpusd = _series_for_pair(pair=pair, prev=prev, close=close, asset="GBPUSD")
    usdjpy = _series_for_pair(pair=pair, prev=prev, close=close, asset="USDJPY")
    audusd = _series_for_pair(pair=pair, prev=prev, close=close, asset="AUDUSD")
    nzdusd = _series_for_pair(pair=pair, prev=prev, close=close, asset="NZDUSD")
    usdcad = _series_for_pair(pair=pair, prev=prev, close=close, asset="USDCAD")
    usdchf = _series_for_pair(pair=pair, prev=prev, close=close, asset="USDCHF")

    eurgbp = _div_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
    )
    eurjpy = _mul_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
    )
    euraud = _div_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
    )
    eurnzd = _div_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
    )
    eurcad = _div_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
    )
    eurchf = _mul_pair_return(
        prev[:, pair["EURUSD"]],
        close[:, pair["EURUSD"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )

    gbpjpy = _mul_pair_return(
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
    )
    gbpaud = _mul_pair_return(
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
    )
    gbpnzd = _mul_pair_return(
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
    )
    gbpcad = _mul_pair_return(
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
    )
    gbpchf = _mul_pair_return(
        prev[:, pair["GBPUSD"]],
        close[:, pair["GBPUSD"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )

    jpyaud = _div_pair_return(
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
    )
    jpynzd = _div_pair_return(
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
    )
    jpycad = _div_pair_return(
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
    )
    jpychf = _div_pair_return(
        prev[:, pair["USDJPY"]],
        close[:, pair["USDJPY"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )

    audnzd = _mul_pair_return(
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
    )
    audcad = _mul_pair_return(
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
    )
    audchf = _mul_pair_return(
        prev[:, pair["AUDUSD"]],
        close[:, pair["AUDUSD"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )

    nzdcad = _mul_pair_return(
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
    )
    nzdchf = _mul_pair_return(
        prev[:, pair["NZDUSD"]],
        close[:, pair["NZDUSD"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )
    cadchf = _mul_pair_return(
        prev[:, pair["USDCAD"]],
        close[:, pair["USDCAD"]],
        prev[:, pair["USDCHF"]],
        close[:, pair["USDCHF"]],
    )

    strength = np.full((close.shape[0], 8), np.nan, dtype=np.float64)
    strength[:, 0] = (eurusd + eurgbp + eurjpy + euraud + eurnzd + eurcad + eurchf) / 7.0
    strength[:, 1] = (gbpusd + eurgbp + gbpjpy + gbpaud + gbpnzd + gbpcad + gbpchf) / 7.0
    strength[:, 2] = (usdjpy + eurjpy + gbpjpy + jpyaud + jpynzd + jpycad + jpychf) / 7.0
    strength[:, 3] = (audusd + euraud + gbpaud + jpyaud + audnzd + audcad + audchf) / 7.0
    strength[:, 4] = (nzdusd + eurnzd + gbpnzd + jpynzd + audnzd + nzdcad + nzdchf) / 7.0
    strength[:, 5] = (usdcad + eurcad + gbpcad + jpycad + audcad + nzdcad + cadchf) / 7.0
    strength[:, 6] = (usdchf + eurchf + gbpchf + jpychf + audchf + nzdchf + cadchf) / 7.0
    strength[:, 7] = (-eurusd - gbpusd + usdjpy - audusd - nzdusd + usdcad + usdchf) / 7.0
    return strength


def _daily_cumulative_strength(*, strength: np.ndarray, time: np.ndarray) -> np.ndarray:
    if np.issubdtype(time.dtype, np.datetime64):
        dates = time.astype("datetime64[D]")
    else:
        dates = time.astype("datetime64[ms]").astype("datetime64[D]")

    out = np.full_like(strength, np.nan, dtype=np.float64)
    for col in range(strength.shape[1]):
        running = 0.0
        last_date = None
        for idx in range(strength.shape[0]):
            if last_date is None or dates[idx] != last_date:
                running = 0.0
                last_date = dates[idx]
            value = strength[idx, col]
            if np.isnan(value):
                out[idx, col] = np.nan
                continue
            running += value
            out[idx, col] = running
    return out
