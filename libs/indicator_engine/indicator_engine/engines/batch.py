"""Batch computation engine for indicators."""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from ..core.bars import BarTensor, DataBundle
from ..core.params import ParamGrid
from ..core.registry import IndicatorRegistry
from ..core.results import IndicatorResult
from ..core.tensor import Tensor


class BatchEngine:
    """Run indicator computations over full bar tensors."""

    def __init__(self, registry: IndicatorRegistry) -> None:
        self.registry = registry

    def run(
        self,
        indicator_id: str,
        data: BarTensor | DataBundle,
        param_grid: Optional[ParamGrid] = None,
        timeframe: Optional[str] = None,
    ) -> IndicatorResult:
        """Run a batch indicator computation.

        - If data is a DataBundle, timeframe is required.
        - Returns a Tensor with dims (time, asset, output, param).
        """
        if isinstance(data, dict):
            if timeframe is None:
                raise ValueError("timeframe is required when data is a DataBundle")
            if timeframe not in data:
                raise KeyError(f"timeframe not found in DataBundle: {timeframe}")
            bar = data[timeframe]
        else:
            bar = data

        indicator = self.registry.get(indicator_id)
        grid = param_grid or ParamGrid({})

        if indicator.spec.supports_vectorized and hasattr(indicator, "batch_vectorized"):
            result = indicator.batch_vectorized(bar, grid)
            tensor = _unwrap_tensor(result)
            tensor = _ensure_dims(
                tensor,
                param_ids=grid.param_ids,
                output_names=indicator.spec.outputs,
            )
            tensor = _with_param_metadata(tensor, grid)
            return IndicatorResult(tensor=tensor)

        per_param = []
        for param_id, params in grid:
            result = indicator.batch(bar, params)
            tensor = _unwrap_tensor(result)
            tensor = _ensure_dims(
                tensor,
                param_ids=[param_id],
                output_names=indicator.spec.outputs,
            )
            per_param.append(tensor)

        combined = _concat_param(per_param, grid.param_ids)
        combined = _with_param_metadata(combined, grid)
        return IndicatorResult(tensor=combined)


def _unwrap_tensor(result) -> Tensor:
    if isinstance(result, IndicatorResult):
        return result.tensor
    if isinstance(result, Tensor):
        return result
    raise TypeError("Indicator batch must return Tensor or IndicatorResult")


def _require_coord(coords: dict[str, np.ndarray], name: str) -> np.ndarray:
    value = coords.get(name)
    if value is None:
        raise ValueError(f"Tensor coord '{name}' is required")
    return value


def _ensure_dims(tensor: Tensor, param_ids: Iterable[str], output_names: list[str]) -> Tensor:
    dims = list(tensor.dims)
    data = tensor.data
    coords = dict(tensor.coords)

    if "time" not in dims or "asset" not in dims:
        raise ValueError("Tensor must include time and asset dimensions")

    if "output" not in dims:
        data = np.expand_dims(data, axis=data.ndim)
        dims.append("output")
        coords["output"] = np.array(output_names or ["value"], dtype=object)
    elif coords.get("output") is None:
        coords["output"] = np.array(output_names or ["value"], dtype=object)

    if "param" not in dims:
        data = np.expand_dims(data, axis=data.ndim)
        dims.append("param")

    param_axis = dims.index("param")
    param_ids_list = list(param_ids)
    if data.shape[param_axis] != len(param_ids_list):
        raise ValueError("Param dimension length does not match param_ids")
    coords["param"] = np.array(param_ids_list, dtype=object)

    order = [dims.index(dim) for dim in ("time", "asset", "output", "param")]
    data = np.transpose(data, axes=order)

    if "time" not in coords:
        coords["time"] = _require_coord(tensor.coords, "time")
    if "asset" not in coords:
        coords["asset"] = _require_coord(tensor.coords, "asset")

    time = _require_coord(coords, "time")
    asset = _require_coord(coords, "asset")
    output = _require_coord(coords, "output")
    param = _require_coord(coords, "param")

    return Tensor(
        data=data,
        dims=("time", "asset", "output", "param"),
        coords={
            "time": time,
            "asset": asset,
            "output": output,
            "param": param,
        },
        attrs=dict(tensor.attrs),
    )


def _concat_param(tensors: list[Tensor], param_ids: list[str]) -> Tensor:
    if not tensors:
        raise ValueError("No tensors to concatenate")
    base = tensors[0]
    time = _require_coord(base.coords, "time")
    asset = _require_coord(base.coords, "asset")
    output = _require_coord(base.coords, "output")
    for tensor in tensors[1:]:
        if not np.array_equal(time, _require_coord(tensor.coords, "time")):
            raise ValueError("Time coords mismatch across params")
        if not np.array_equal(asset, _require_coord(tensor.coords, "asset")):
            raise ValueError("Asset coords mismatch across params")
        if not np.array_equal(output, _require_coord(tensor.coords, "output")):
            raise ValueError("Output coords mismatch across params")

    data = np.concatenate([t.data for t in tensors], axis=3)
    return Tensor(
        data=data,
        dims=("time", "asset", "output", "param"),
        coords={
            "time": time,
            "asset": asset,
            "output": output,
            "param": np.array(param_ids, dtype=object),
        },
        attrs=dict(base.attrs),
    )


def _with_param_metadata(tensor: Tensor, grid: ParamGrid) -> Tensor:
    attrs = dict(tensor.attrs)
    attrs["param_names"] = grid.param_names
    attrs["param_values"] = grid.grid_params
    return Tensor(
        data=tensor.data,
        dims=tensor.dims,
        coords=tensor.coords,
        attrs=attrs,
    )
