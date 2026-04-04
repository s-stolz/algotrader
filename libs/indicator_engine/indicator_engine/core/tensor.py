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

    def latest(self, dim: str = "time") -> "Tensor":
        """Return a Tensor sliced to the latest value along a named dimension."""
        if dim not in self.dims:
            raise KeyError(f"Dimension not found: {dim}")

        axis = self.dim_index(dim)
        sliced = np.take(self.data, indices=-1, axis=axis)
        new_dims = tuple(name for name in self.dims if name != dim)
        new_coords = {k: v.copy() for k, v in self.coords.items() if k != dim}
        return Tensor(data=sliced, dims=new_dims, coords=new_coords, attrs=dict(self.attrs))

    def scalar(self) -> float:
        """Return a scalar float when all dimensions are singleton."""
        if self.data.size != 1:
            raise ValueError(
                f"Tensor is not scalar-like; expected size 1 but got shape {self.data.shape}"
            )
        return float(self.data.reshape(-1)[0])

    def latest_value(
        self,
        *,
        asset: object | None = None,
        output: object | None = None,
        param: object | None = None,
    ) -> float:
        """Return latest scalar value for indicator tensors.

        Uses the latest `time` slot when present. For `asset`, `output`, and `param`
        dimensions, a selector can be provided. If a selector is omitted, the
        dimension must have length 1.
        """
        current = self.latest("time") if "time" in self.dims else self
        selectors = {"asset": asset, "output": output, "param": param}

        for dim_name in ("asset", "output", "param"):
            if dim_name not in current.dims:
                continue
            axis = current.dim_index(dim_name)
            dim_size = current.data.shape[axis]
            selector = selectors[dim_name]

            if selector is None:
                if dim_size != 1:
                    raise ValueError(
                        f"Dimension '{dim_name}' has size {dim_size}; provide `{dim_name}=...`"
                    )
                index = 0
            else:
                coord = current.coords.get(dim_name)
                if coord is None:
                    raise ValueError(
                        f"Coordinate for dimension '{dim_name}' is required when selecting by name"
                    )
                matches = np.where(coord == selector)[0]
                if len(matches) == 0:
                    raise KeyError(f"Unknown {dim_name} selector: {selector!r}")
                index = int(matches[0])

            current = Tensor(
                data=np.take(current.data, indices=index, axis=axis),
                dims=tuple(name for name in current.dims if name != dim_name),
                coords={k: v.copy() for k, v in current.coords.items() if k != dim_name},
                attrs=dict(current.attrs),
            )

        return current.scalar()
