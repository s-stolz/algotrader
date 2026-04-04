"""Streaming update engine with rolling buffers and pending inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np

from ..core.bars import BarBuffer
from ..core.history import HistoryPolicy
from ..core.params import ParamGrid
from ..core.registry import Indicator, IndicatorRegistry
from ..core.results import ResultBuffer
from ..core.tensor import Tensor


@dataclass
class Registration:
    """Internal registration record for an indicator/timeframe pair."""
    indicator_id: str
    indicator: Indicator
    timeframe: str
    param_grid: ParamGrid
    result_buffer: ResultBuffer
    required_asset_idx: Optional[np.ndarray]
    pending: Dict[int, tuple[np.ndarray, int]]
    max_delay_ms: Optional[int]
    max_delay_bars: Optional[int]


class UpdateEngine:
    """Incremental update engine for streaming bar feeds.

    - Maintains rolling bar buffers per timeframe.
    - Supports partial asset updates and cross-asset dependency buffering.
    - Stores vectorized state keyed by (indicator_id, param_id, timeframe).
    """
    def __init__(
        self,
        registry: IndicatorRegistry,
        history: HistoryPolicy,
        max_delay_ms: Optional[int] = None,
        max_delay_bars: Optional[int] = None,
    ) -> None:
        self.registry = registry
        self.history = history
        self.max_delay_ms = max_delay_ms
        self.max_delay_bars = max_delay_bars

        self._bar_buffers: Dict[str, BarBuffer] = {}
        self._registrations: Dict[str, list[Registration]] = {}
        self._states: Dict[tuple[str, str, str], dict] = {}
        self._bar_counters: Dict[str, int] = {}

    def register_indicator(
        self,
        indicator_id: str,
        timeframe: str,
        assets: Iterable,
        fields: Iterable[str],
        param_grid: Optional[ParamGrid] = None,
        history: Optional[HistoryPolicy] = None,
        max_delay_ms: Optional[int] = None,
        max_delay_bars: Optional[int] = None,
        allow_out_of_order: bool = False,
    ) -> None:
        """Register an indicator for streaming updates on a timeframe."""
        if timeframe not in self._bar_buffers:
            self._bar_buffers[timeframe] = BarBuffer(
                assets=assets,
                fields=fields,
                history=history or self.history,
                allow_out_of_order=allow_out_of_order,
            )
            self._bar_counters[timeframe] = 0

        indicator = self.registry.get(indicator_id)
        grid = param_grid or ParamGrid({})
        bar_buffer = self._bar_buffers[timeframe]

        required_idx = None
        if indicator.spec.required_assets:
            required_idx = np.array(
                [bar_buffer.asset_index[a] for a in indicator.spec.required_assets],
                dtype=int,
            )

        result_buffer = ResultBuffer(
            assets=bar_buffer.assets,
            outputs=indicator.spec.outputs or ["value"],
            param_ids=grid.param_ids,
            param_names=grid.param_names,
            param_values=grid.grid_params,
            history=history or self.history,
            allow_out_of_order=allow_out_of_order,
        )

        registration = Registration(
            indicator_id=indicator_id,
            indicator=indicator,
            timeframe=timeframe,
            param_grid=grid,
            result_buffer=result_buffer,
            required_asset_idx=required_idx,
            pending={},
            max_delay_ms=max_delay_ms or self.max_delay_ms,
            max_delay_bars=max_delay_bars or self.max_delay_bars,
        )

        self._registrations.setdefault(timeframe, []).append(registration)

    def on_bar(
        self,
        timeframe: str,
        timestamp_ms: int,
        new_row: np.ndarray,
        asset_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, Tensor]:
        """Submit a new bar row and return latest indicator updates."""
        if timeframe not in self._bar_buffers:
            raise KeyError(f"No bar buffer registered for timeframe: {timeframe}")

        bar_buffer = self._bar_buffers[timeframe]
        full_row, full_mask = self._normalize_row(bar_buffer, new_row, asset_mask)
        is_new = bar_buffer.append(timestamp_ms, full_row, full_mask)

        if is_new:
            self._bar_counters[timeframe] += 1
            for reg in self._registrations.get(timeframe, []):
                reg.result_buffer.append(timestamp_ms)

        updated: Dict[str, Tensor] = {}
        for reg in self._registrations.get(timeframe, []):
            tensor = self._update_registration(
                reg,
                bar_buffer=bar_buffer,
                timestamp_ms=int(timestamp_ms),
                new_row=full_row,
                asset_mask=full_mask,
                bar_index=self._bar_counters[timeframe],
            )
            if tensor is not None:
                updated[reg.indicator_id] = tensor
        return updated

    def get_result_buffer(self, indicator_id: str, timeframe: str) -> ResultBuffer:
        """Return the rolling ResultBuffer for a registered indicator."""
        for reg in self._registrations.get(timeframe, []):
            if reg.indicator_id == indicator_id:
                return reg.result_buffer
        raise KeyError(f"No registration for indicator {indicator_id} at {timeframe}")

    def _update_registration(
        self,
        reg: Registration,
        bar_buffer: BarBuffer,
        timestamp_ms: int,
        new_row: np.ndarray,
        asset_mask: np.ndarray,
        bar_index: int,
    ) -> Optional[Tensor]:
        if reg.required_asset_idx is not None:
            pending_entry = reg.pending.get(timestamp_ms)
            if pending_entry is None:
                mask = np.zeros(len(reg.required_asset_idx), dtype=bool)
                first_index = bar_index
            else:
                mask, first_index = pending_entry
            req_mask = asset_mask[reg.required_asset_idx]
            mask = mask | req_mask
            reg.pending[timestamp_ms] = (mask, first_index)
            if not mask.all():
                self._evict_pending(reg, bar_buffer, timestamp_ms, bar_index)
                return None
            reg.pending.pop(timestamp_ms, None)

        outputs = reg.indicator.spec.outputs or ["value"]
        values = np.full(
            (len(bar_buffer.assets), len(outputs), len(reg.param_grid.param_ids)),
            np.nan,
            dtype=np.float64,
        )

        if not reg.result_buffer.has_timestamp(timestamp_ms):
            reg.result_buffer.append(timestamp_ms)

        for p_idx, (param_id, params) in enumerate(reg.param_grid):
            warmup = reg.indicator.spec.warmup(params)
            if len(bar_buffer) < warmup:
                continue

            state_key = (reg.indicator_id, param_id, reg.timeframe)
            state = self._states.get(state_key)

            if reg.indicator.spec.supports_update:
                if state is None:
                    warmup_data = bar_buffer.tail(warmup)
                    state = reg.indicator.init_state(warmup_data, params)
                state, latest = reg.indicator.update(
                    state, new_row=new_row, asset_mask=asset_mask, timestamp_ms=timestamp_ms
                )
                self._states[state_key] = state
                latest_values = _unwrap_latest(latest)
            else:
                warmup_data = bar_buffer.tail(warmup)
                batch_result = reg.indicator.batch(warmup_data, params)
                tensor = _ensure_latest_tensor(batch_result, outputs)
                latest_values = tensor.data[-1, :, :, 0]

            if latest_values.shape != (len(bar_buffer.assets), len(outputs)):
                raise ValueError("Latest values shape mismatch")
            values[:, :, p_idx] = latest_values

        reg.result_buffer.update(timestamp_ms, values, asset_mask=None)
        return Tensor(
            data=values[np.newaxis, :, :, :],
            dims=("time", "asset", "output", "param"),
            coords={
                "time": np.array([timestamp_ms], dtype=np.int64),
                "asset": bar_buffer.assets.copy(),
                "output": np.array(outputs, dtype=object),
                "param": np.array(reg.param_grid.param_ids, dtype=object),
            },
            attrs={
                "param_names": reg.param_grid.param_names,
                "param_values": reg.param_grid.grid_params,
            },
        )

    def _evict_pending(
        self,
        reg: Registration,
        bar_buffer: BarBuffer,
        current_ts: int,
        current_bar_index: int,
    ) -> None:
        earliest = bar_buffer.earliest_timestamp()
        to_drop = []
        for ts, (mask, bar_idx) in reg.pending.items():
            if earliest is not None and ts < earliest:
                to_drop.append(ts)
                continue
            if reg.max_delay_ms is not None and current_ts - ts > reg.max_delay_ms:
                to_drop.append(ts)
                continue
            if reg.max_delay_bars is not None and current_bar_index - bar_idx > reg.max_delay_bars:
                to_drop.append(ts)
                continue
        for ts in to_drop:
            reg.pending.pop(ts, None)

    @staticmethod
    def _normalize_row(
        bar_buffer: BarBuffer,
        new_row: np.ndarray,
        asset_mask: Optional[np.ndarray],
    ) -> tuple[np.ndarray, np.ndarray]:
        expected = (len(bar_buffer.assets), len(bar_buffer.fields))
        if new_row.shape != expected:
            raise ValueError(f"new_row shape {new_row.shape} does not match {expected}")
        if asset_mask is None:
            asset_mask = np.ones(len(bar_buffer.assets), dtype=bool)
        if asset_mask.shape[0] != len(bar_buffer.assets):
            raise ValueError("asset_mask length must match asset dimension")
        return new_row, asset_mask


def _unwrap_latest(result) -> np.ndarray:
    if isinstance(result, Tensor):
        if result.dims == ("asset", "output"):
            return result.data
        if result.dims == ("time", "asset", "output"):
            return result.data[-1]
    if isinstance(result, np.ndarray):
        return result
    raise TypeError("update must return Tensor or ndarray for latest values")


def _require_tensor_coord(tensor: Tensor, name: str) -> np.ndarray:
    value = tensor.coords.get(name)
    if value is None:
        raise ValueError(f"Tensor coord '{name}' is required")
    return value


def _ensure_latest_tensor(result, outputs: list[str]) -> Tensor:
    if isinstance(result, Tensor):
        tensor = result
    elif hasattr(result, "tensor"):
        tensor = result.tensor
    else:
        raise TypeError("batch must return Tensor or IndicatorResult")

    if tensor.dims == ("time", "asset", "output", "param"):
        return tensor

    if tensor.dims == ("time", "asset", "output"):
        data = tensor.data[:, :, :, np.newaxis]
        output_coord = tensor.coords.get("output")
        if output_coord is None:
            output_coord = np.array(outputs, dtype=object)
        return Tensor(
            data=data,
            dims=("time", "asset", "output", "param"),
            coords={
                "time": _require_tensor_coord(tensor, "time"),
                "asset": _require_tensor_coord(tensor, "asset"),
                "output": output_coord,
                "param": np.array(["p0"], dtype=object),
            },
        )

    raise ValueError("Unsupported tensor dims for latest extraction")
