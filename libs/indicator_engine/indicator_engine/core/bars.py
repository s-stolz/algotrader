"""Aligned bar data structures and rolling buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np

from .history import HistoryPolicy


@dataclass(frozen=True)
class BarTensor:
    """Dense bar tensor with aligned time and asset axes.

    data shape: (time, asset, field)
    """

    data: np.ndarray  # shape (time, asset, field)
    time: np.ndarray
    assets: np.ndarray
    fields: np.ndarray

    def to_dict(self) -> Dict[str, np.ndarray]:
        return {
            "time": self.time,
            "asset": self.assets,
            "field": self.fields,
        }


DataBundle = Dict[str, BarTensor]


class BarBuffer:
    """Rolling or unbounded buffer for bar data.

    - Enforces aligned time index across assets.
    - Supports partial asset updates via asset masks.
    - Uses rolling eviction or dynamic growth based on HistoryPolicy.
    """

    def __init__(
        self,
        assets: Iterable,
        fields: Iterable[str],
        history: HistoryPolicy,
        dtype: np.dtype = np.dtype(np.float64),
        allow_out_of_order: bool = False,
        initial_capacity: int = 1024,
    ) -> None:
        self.assets = np.array(list(assets), dtype=object)
        self.fields = np.array(list(fields), dtype=object)
        self.asset_index = {asset: i for i, asset in enumerate(self.assets)}
        self.field_index = {field: i for i, field in enumerate(self.fields)}
        self.history = history
        self.allow_out_of_order = allow_out_of_order
        self.dtype = dtype

        if history.mode == "rolling":
            capacity = history.max_rows or 0
        else:
            capacity = history.max_rows or initial_capacity

        if capacity <= 0:
            raise ValueError("BarBuffer capacity must be > 0")

        self._capacity = int(capacity)
        self._size = 0
        self._start = 0
        self._time = np.empty(self._capacity, dtype=np.int64)
        self._data = np.empty(
            (self._capacity, len(self.assets), len(self.fields)),
            dtype=self.dtype,
        )
        self._ts_to_pos: Dict[int, int] = {}

    def __len__(self) -> int:
        return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    def earliest_timestamp(self) -> Optional[int]:
        if self._size == 0:
            return None
        return int(self._time[self._start])

    def latest_timestamp(self) -> Optional[int]:
        if self._size == 0:
            return None
        idx = (self._start + self._size - 1) % self._capacity
        return int(self._time[idx])

    def has_timestamp(self, timestamp_ms: int) -> bool:
        return int(timestamp_ms) in self._ts_to_pos

    def append(
        self,
        timestamp_ms: int,
        row: np.ndarray,
        asset_mask: Optional[np.ndarray] = None,
    ) -> bool:
        """Append a full or partial row at timestamp_ms.

        Returns True if a new row was appended, False if an existing row was updated.
        """
        ts = int(timestamp_ms)
        if ts in self._ts_to_pos:
            pos = self._ts_to_pos[ts]
            self._update_row(pos, row, asset_mask)
            return False

        if not self.allow_out_of_order:
            latest = self.latest_timestamp()
            if latest is not None and ts < latest:
                raise ValueError(f"Out-of-order timestamp {ts} < latest {latest} not allowed")

        if self.history.mode == "unbounded" and self._size >= self._capacity:
            self._grow_capacity(self._capacity * 2)

        if self._size < self._capacity:
            pos = (self._start + self._size) % self._capacity
            self._size += 1
        else:
            # rolling overwrite oldest
            pos = self._start
            evicted_ts = int(self._time[pos])
            self._ts_to_pos.pop(evicted_ts, None)
            self._start = (self._start + 1) % self._capacity

        self._time[pos] = ts
        self._ts_to_pos[ts] = pos
        self._data[pos, :, :] = np.nan
        self._update_row(pos, row, asset_mask)
        return True

    def append_partial(
        self,
        timestamp_ms: int,
        row: np.ndarray,
        asset_ids: Iterable,
    ) -> bool:
        """Append a row for a subset of assets, filling others with NaN."""
        mask = np.zeros(len(self.assets), dtype=bool)
        full = np.full((len(self.assets), len(self.fields)), np.nan, dtype=self.dtype)
        asset_ids = list(asset_ids)
        if row.shape[0] != len(asset_ids):
            raise ValueError("row first dimension must match asset_ids length")
        for i, asset in enumerate(asset_ids):
            if asset not in self.asset_index:
                raise KeyError(f"Asset not found in buffer: {asset}")
            idx = self.asset_index[asset]
            mask[idx] = True
            full[idx, :] = row[i, :]
        return self.append(timestamp_ms, full, mask)

    def view(self) -> BarTensor:
        """Return an ordered BarTensor snapshot of the buffer."""
        data, time = self._ordered_view()
        return BarTensor(
            data=data,
            time=time,
            assets=self.assets.copy(),
            fields=self.fields.copy(),
        )

    def tail(self, count: int) -> BarTensor:
        """Return the last `count` rows as a BarTensor snapshot."""
        if count <= 0:
            return BarTensor(
                data=np.empty((0, len(self.assets), len(self.fields)), dtype=self.dtype),
                time=np.empty((0,), dtype=np.int64),
                assets=self.assets.copy(),
                fields=self.fields.copy(),
            )
        data, time = self._ordered_view()
        return BarTensor(
            data=data[-count:],
            time=time[-count:],
            assets=self.assets.copy(),
            fields=self.fields.copy(),
        )

    def _update_row(
        self,
        pos: int,
        row: np.ndarray,
        asset_mask: Optional[np.ndarray],
    ) -> None:
        if row.shape != (len(self.assets), len(self.fields)):
            raise ValueError(
                f"Row shape {row.shape} does not match ({len(self.assets)}, {len(self.fields)})"
            )
        if asset_mask is None:
            self._data[pos, :, :] = row
            return
        if asset_mask.shape[0] != len(self.assets):
            raise ValueError("asset_mask length must match asset dimension")
        self._data[pos, asset_mask, :] = row[asset_mask, :]

    def _ordered_view(self) -> Tuple[np.ndarray, np.ndarray]:
        if self._size == 0:
            return (
                np.empty((0, len(self.assets), len(self.fields)), dtype=self.dtype),
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
            (self._capacity, len(self.assets), len(self.fields)),
            dtype=self.dtype,
        )
        self._time = np.empty(self._capacity, dtype=np.int64)
        self._data[: data.shape[0], :, :] = data
        self._time[: time.shape[0]] = time
        self._start = 0
        self._size = data.shape[0]
        self._ts_to_pos = {int(ts): i for i, ts in enumerate(time)}
