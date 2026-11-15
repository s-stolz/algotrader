"""Causal daily opening ranges shared by strategies and chart adapters."""

from dataclasses import dataclass

import numpy as np

from ..catalog import IndicatorRegistration
from ..core.bars import BarTensor
from ..core.history import InputHistory
from ..core.session import SessionBounds, SessionWindow
from ..core.spec import IndicatorSpec
from ..core.tensor import Tensor
from .base import IndicatorBase


@dataclass(frozen=True)
class _Configuration:
    window: SessionWindow
    extension: SessionWindow


def _minute(value: object) -> int:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("Range times must use HH:MM")
    if not value[:2].isdigit() or not value[3:].isdigit():
        raise ValueError("Range times must use HH:MM")
    try:
        hour, minute = int(value[:2]), int(value[3:])
    except ValueError as exc:
        raise ValueError("Range times must use HH:MM") from exc
    if not (0 <= hour <= 24 and 0 <= minute < 60) or (hour == 24 and minute != 0):
        raise ValueError("Range times must be between 00:00 and 24:00")
    return hour * 60 + minute


def _configuration(params: dict) -> _Configuration:
    start = _minute(params.get("start_time", "00:00"))
    end = _minute(params.get("end_time", "01:00"))
    extension = _minute(params.get("extension_end_time", "24:00"))
    if extension < end:
        raise ValueError("Range extension must end at or after the range cutoff")
    timezone = params.get("timezone", "UTC")
    if not isinstance(timezone, str):
        raise ValueError("Range timezone must be an IANA timezone name")
    return _Configuration(
        SessionWindow(timezone, start, end), SessionWindow(timezone, start, extension)
    )


def _history(params: dict) -> InputHistory:
    return InputHistory(anchor="daily", session=_configuration(params).window)


class OpeningRange(IndicatorBase):
    """Include candles opened in [start, end); ready begins at the cutoff candle.

    Empty, not-yet-started ranges use finite zero bounds and ready=0. Consumers
    must check ready before trading. Invalid formation prices propagate NaNs.
    """

    spec = IndicatorSpec(
        id="opening_range",
        name="Opening Range",
        parameters={
            "start_time": {"type": "string", "default": "00:00"},
            "end_time": {"type": "string", "default": "01:00"},
            "extension_end_time": {"type": "string", "default": "24:00"},
            "timezone": {"type": "string", "default": "UTC"},
        },
        outputs=[
            "range_high",
            "range_low",
            "ready",
            "range_start_ms",
            "range_end_ms",
            "extension_end_ms",
        ],
        required_fields=["high", "low"],
        supports_update=True,
        input_history=InputHistory(anchor="daily"),
        input_history_fn=_history,
    )

    def batch(self, data: BarTensor, params: dict) -> Tensor:
        config = _configuration(params)
        times = data.time.astype("datetime64[ms]").astype(np.int64)
        if np.any(np.diff(times) <= 0):
            raise ValueError("Opening range candles must have increasing timestamps")
        high_idx, low_idx = _field_indices(data)
        values = np.zeros((len(times), len(data.assets), len(self.spec.outputs)))
        offset = 0
        while offset < len(times):
            bounds = config.window.bounds(int(times[offset]))
            extension = config.extension.bounds(int(times[offset])).end_ms
            end = int(np.searchsorted(times, bounds.day_end_ms))
            values[offset:end] = _batch_session(
                times[offset:end],
                data.data[offset:end, :, high_idx],
                data.data[offset:end, :, low_idx],
                bounds,
                extension,
            )
            offset = end
        return Tensor(
            values,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(self.spec.outputs, dtype=object),
            },
        )

    def init_state(self, data: BarTensor, params: dict) -> dict:
        high_idx, low_idx = _field_indices(data)
        state = {
            "config": _configuration(params),
            "high_idx": high_idx,
            "low_idx": low_idx,
            "snapshot": None,
            "prior": None,
            "timestamp": None,
            "bounds": None,
        }
        times = data.time.astype("datetime64[ms]").astype(np.int64)
        for timestamp, row in zip(times[:-1], data.data[:-1], strict=True):
            state, _ = self.update(
                state,
                new_row=row,
                asset_mask=np.ones(len(data.assets), dtype=bool),
                timestamp_ms=int(timestamp),
            )
        return state

    def update(self, state: dict, *, new_row, asset_mask, timestamp_ms):
        if state["timestamp"] is not None and timestamp_ms < state["timestamp"]:
            raise ValueError("Opening range updates must be chronological")
        config = state["config"]
        bounds = state["bounds"]
        if bounds is None or not bounds.day_start_ms <= timestamp_ms < bounds.day_end_ms:
            bounds = config.window.bounds(timestamp_ms)
        same_candle = timestamp_ms == state["timestamp"]
        prior = state["prior"] if same_candle else state["snapshot"]
        snapshot = _advance_snapshot(
            prior,
            bounds,
            timestamp_ms,
            new_row[:, state["high_idx"]],
            new_row[:, state["low_idx"]],
            asset_mask,
        )
        if same_candle:
            snapshot[~asset_mask] = state["snapshot"][1][~asset_mask]
        extension = config.extension.bounds(timestamp_ms).end_ms
        output = _snapshot_values(snapshot, timestamp_ms, bounds, extension)
        return {
            **state,
            "snapshot": (bounds.day_start_ms, snapshot),
            "prior": prior,
            "timestamp": timestamp_ms,
            "bounds": bounds,
        }, output


def _field_indices(data: BarTensor) -> tuple[int, int]:
    if "high" not in data.fields or "low" not in data.fields:
        raise KeyError("Opening range requires high and low fields")
    return int(np.flatnonzero(data.fields == "high")[0]), int(
        np.flatnonzero(data.fields == "low")[0]
    )


def _batch_session(times, high, low, bounds: SessionBounds, extension: int) -> np.ndarray:
    forming = ((times >= bounds.start_ms) & (times < bounds.end_ms))[:, None]
    valid = np.isfinite(high) & np.isfinite(low) & (high >= low)
    highs = np.maximum.accumulate(np.where(forming, np.where(valid, high, np.nan), -np.inf), axis=0)
    lows = np.minimum.accumulate(np.where(forming, np.where(valid, low, np.nan), np.inf), axis=0)
    seen = np.logical_or.accumulate(np.broadcast_to(forming, high.shape), axis=0)
    started = np.logical_or.accumulate((times[:, None] == bounds.start_ms) & valid, axis=0)
    result = np.zeros((*high.shape, 6))
    result[:, :, 0] = np.where(seen, highs, 0.0)
    result[:, :, 1] = np.where(seen, lows, 0.0)
    result[:, :, 2] = (
        (times[:, None] >= bounds.end_ms) & started & np.isfinite(highs) & np.isfinite(lows)
    )
    result[:, :, 3:] = (bounds.start_ms, bounds.end_ms, extension)
    return result


def _advance_snapshot(prior, bounds: SessionBounds, timestamp_ms, high, low, asset_mask):
    if prior is None or prior[0] != bounds.day_start_ms:
        snapshot = np.zeros((len(high), 4))
        snapshot[:, 0] = -np.inf
        snapshot[:, 1] = np.inf
    else:
        snapshot = prior[1].copy()
    if bounds.start_ms <= timestamp_ms < bounds.end_ms:
        valid = np.isfinite(high) & np.isfinite(low) & (high >= low)
        snapshot[asset_mask, 0] = np.maximum(
            snapshot[asset_mask, 0], np.where(valid, high, np.nan)[asset_mask]
        )
        snapshot[asset_mask, 1] = np.minimum(
            snapshot[asset_mask, 1], np.where(valid, low, np.nan)[asset_mask]
        )
        snapshot[asset_mask, 2] = 1
        if timestamp_ms == bounds.start_ms:
            snapshot[asset_mask, 3] = valid[asset_mask]
    return snapshot


def _snapshot_values(snapshot, timestamp_ms, bounds: SessionBounds, extension: int):
    output = np.zeros((len(snapshot), 6))
    output[:, 0] = np.where(snapshot[:, 2], snapshot[:, 0], 0.0)
    output[:, 1] = np.where(snapshot[:, 2], snapshot[:, 1], 0.0)
    output[:, 2] = (
        (timestamp_ms >= bounds.end_ms)
        & (snapshot[:, 3] == 1)
        & np.isfinite(snapshot[:, 0])
        & np.isfinite(snapshot[:, 1])
    )
    output[:, 3:] = (bounds.start_ms, bounds.end_ms, extension)
    return output


OPENING_RANGE_REGISTRATION = IndicatorRegistration(
    public_id=7,
    implementation=OpeningRange,
    supports_live=False,
    overlay=True,
    outputs={
        "range_high": {
            "type": "opening_range",
            "label": "Range",
            "plotOptions": {
                "color": "#2962ff",
                "fillColor": "rgba(41, 98, 255, 0.12)",
                "lineWidth": 1,
                "showExtensions": True,
            },
        }
    },
)
