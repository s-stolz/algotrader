"""Indicator result tensors and rolling result buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np

from .history import HistoryPolicy
from .tensor import Tensor


@dataclass(frozen=True)
class IndicatorResult:
    """Wrapper around a result Tensor."""
    tensor: Tensor


class ResultBuffer:
    """Rolling or unbounded buffer for indicator result tensors."""
    def __init__(
        self,
        assets: Iterable,
        outputs: Iterable[str],
        param_ids: Iterable[str],
        param_names: Optional[Iterable[str]],
        param_values: Optional[Iterable[Dict[str, object]]],
        history: HistoryPolicy,
        dtype: np.dtype = np.dtype(np.float64),
        allow_out_of_order: bool = False,
        initial_capacity: int = 1024,
    ) -> None:
        self.assets = np.array(list(assets), dtype=object)
        self.outputs = np.array(list(outputs), dtype=object)
        self.param_ids = np.array(list(param_ids), dtype=object)
        self.param_names = list(param_names) if param_names is not None else []
        self.param_values = list(param_values) if param_values is not None else []
        self.asset_index = {asset: i for i, asset in enumerate(self.assets)}
        self.history = history
        self.allow_out_of_order = allow_out_of_order
        self.dtype = dtype

        if history.mode == "rolling":
            capacity = history.max_rows or 0
        else:
            capacity = history.max_rows or initial_capacity

        if capacity <= 0:
            raise ValueError("ResultBuffer capacity must be > 0")

        self._capacity = int(capacity)
        self._size = 0
        self._start = 0
        self._time = np.empty(self._capacity, dtype=np.int64)
        self._data = np.empty(
            (self._capacity, len(self.assets), len(self.outputs), len(self.param_ids)),
            dtype=self.dtype,
        )
        self._ts_to_pos: Dict[int, int] = {}

    def __len__(self) -> int:
        return self._size

    def has_timestamp(self, timestamp_ms: int) -> bool:
        return int(timestamp_ms) in self._ts_to_pos

    def append(
        self,
        timestamp_ms: int,
        row: Optional[np.ndarray] = None,
        asset_mask: Optional[np.ndarray] = None,
    ) -> bool:
        ts = int(timestamp_ms)
        if ts in self._ts_to_pos:
            pos = self._ts_to_pos[ts]
            if row is not None:
                self._update_row(pos, row, asset_mask)
            return False

        if not self.allow_out_of_order:
            latest = self.latest_timestamp()
            if latest is not None and ts < latest:
                raise ValueError(
                    f"Out-of-order timestamp {ts} < latest {latest} not allowed"
                )

        if self.history.mode == "unbounded" and self._size >= self._capacity:
            self._grow_capacity(self._capacity * 2)

        if self._size < self._capacity:
            pos = (self._start + self._size) % self._capacity
            self._size += 1
        else:
            pos = self._start
            evicted_ts = int(self._time[pos])
            self._ts_to_pos.pop(evicted_ts, None)
            self._start = (self._start + 1) % self._capacity

        self._time[pos] = ts
        self._ts_to_pos[ts] = pos
        self._data[pos, :, :, :] = np.nan
        if row is not None:
            self._update_row(pos, row, asset_mask)
        return True

    def update(self, timestamp_ms: int, row: np.ndarray, asset_mask: Optional[np.ndarray] = None) -> None:
        ts = int(timestamp_ms)
        if ts not in self._ts_to_pos:
            raise KeyError(f"Timestamp not found in ResultBuffer: {ts}")
        pos = self._ts_to_pos[ts]
        self._update_row(pos, row, asset_mask)

    def view(self) -> Tensor:
        data, time = self._ordered_view()
        return Tensor(
            data=data,
            dims=("time", "asset", "output", "param"),
            coords={
                "time": time,
                "asset": self.assets.copy(),
                "output": self.outputs.copy(),
                "param": self.param_ids.copy(),
            },
            attrs={
                "param_names": list(self.param_names),
                "param_values": list(self.param_values),
            },
        )

    def earliest_timestamp(self) -> Optional[int]:
        if self._size == 0:
            return None
        return int(self._time[self._start])

    def latest_timestamp(self) -> Optional[int]:
        if self._size == 0:
            return None
        idx = (self._start + self._size - 1) % self._capacity
        return int(self._time[idx])

    def _update_row(
        self,
        pos: int,
        row: np.ndarray,
        asset_mask: Optional[np.ndarray],
    ) -> None:
        expected = (len(self.assets), len(self.outputs), len(self.param_ids))
        if row.shape != expected:
            raise ValueError(f"Row shape {row.shape} does not match {expected}")
        if asset_mask is None:
            self._data[pos, :, :, :] = row
            return
        if asset_mask.shape[0] != len(self.assets):
            raise ValueError("asset_mask length must match asset dimension")
        self._data[pos, asset_mask, :, :] = row[asset_mask, :, :]

    def _ordered_view(self) -> Tuple[np.ndarray, np.ndarray]:
        if self._size == 0:
            return (
                np.empty(
                    (0, len(self.assets), len(self.outputs), len(self.param_ids)),
                    dtype=self.dtype,
                ),
                np.empty((0,), dtype=np.int64),
            )
        if self._start == 0 and self._size == self._capacity:
            return self._data.copy(), self._time.copy()
        idx = [(self._start + i) % self._capacity for i in range(self._size)]
        return self._data[idx].copy(), self._time[idx].copy()

    def _grow_capacity(self, new_capacity: int) -> None:
        data, time = self._ordered_view()
        self._capacity = int(new_capacity)
        self._data = np.empty(
            (self._capacity, len(self.assets), len(self.outputs), len(self.param_ids)),
            dtype=self.dtype,
        )
        self._time = np.empty(self._capacity, dtype=np.int64)
        self._data[: data.shape[0], :, :, :] = data
        self._time[: time.shape[0]] = time
        self._start = 0
        self._size = data.shape[0]
        self._ts_to_pos = {int(ts): i for i, ts in enumerate(time)}
