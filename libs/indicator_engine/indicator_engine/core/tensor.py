"""Lightweight tensor wrapper with named dimensions and coordinates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

import numpy as np


@dataclass(frozen=True)
class Tensor:
    """Dense tensor with named dimensions and coordinate arrays.

    data:
        NumPy array of any dimensionality.
    dims:
        Tuple of dimension names in the same order as data axes.
    coords:
        Optional mapping from dimension name to coordinate array.
    attrs:
        Optional free-form metadata.
    """
    data: np.ndarray
    dims: Tuple[str, ...]
    coords: Dict[str, np.ndarray] = field(default_factory=dict)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data.ndim != len(self.dims):
            raise ValueError(
                f"Tensor dims length {len(self.dims)} does not match data.ndim {self.data.ndim}"
            )

    def dim_index(self, name: str) -> int:
        try:
            return self.dims.index(name)
        except ValueError as exc:
            raise KeyError(f"Dimension not found: {name}") from exc

    def copy(self) -> "Tensor":
        return Tensor(
            data=self.data.copy(),
            dims=tuple(self.dims),
            coords={k: v.copy() for k, v in self.coords.items()},
            attrs=dict(self.attrs),
        )
