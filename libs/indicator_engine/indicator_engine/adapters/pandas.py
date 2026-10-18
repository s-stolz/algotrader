"""Pandas adapters for BarTensor and indicator result tensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, cast

import numpy as np

from ..core.bars import BarTensor
from ..core.tensor import Tensor

if TYPE_CHECKING:
    import pandas as pd


def bars_from_dataframe(
    df: "pd.DataFrame",
    assets: Optional[Iterable[object]] = None,
) -> BarTensor:
    """Convert a pandas DataFrame into a BarTensor.

    Supports MultiIndex columns (field, asset) or single-asset columns.
    """
    import pandas as pd

    if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels == 2:
        fields = list(df.columns.levels[0])
        assets_for_df = list(df.columns.levels[1])
        data = np.full((len(df), len(assets_for_df), len(fields)), np.nan, dtype=np.float64)
        for f_idx, field in enumerate(fields):
            for a_idx, asset in enumerate(assets_for_df):
                data[:, a_idx, f_idx] = df[(field, asset)].to_numpy()
        return BarTensor(
            data=data,
            time=df.index.to_numpy(),
            assets=np.array(assets_for_df, dtype=object),
            fields=np.array(fields, dtype=object),
        )

    # Single-asset columns
    asset_list = [0] if assets is None else list(assets)
    if len(asset_list) != 1:
        raise ValueError("Single-asset DataFrame conversion expects exactly one asset identifier")
    fields = list(df.columns)
    data = np.full((len(df), 1, len(fields)), np.nan, dtype=np.float64)
    for f_idx, field in enumerate(fields):
        data[:, 0, f_idx] = df[field].to_numpy()
    return BarTensor(
        data=data,
        time=df.index.to_numpy(),
        assets=np.array(asset_list, dtype=object),
        fields=np.array(fields, dtype=object),
    )


def bars_to_dataframe(bar: BarTensor) -> "pd.DataFrame":
    """Convert a BarTensor into a pandas DataFrame with MultiIndex columns."""
    import pandas as pd

    columns = pd.MultiIndex.from_product([bar.fields, bar.assets])
    df = pd.DataFrame(index=bar.time, columns=columns)
    for f_idx, field in enumerate(bar.fields):
        for a_idx, asset in enumerate(bar.assets):
            df[(field, asset)] = bar.data[:, a_idx, f_idx]
    return df


def result_to_dataframe(tensor: Tensor) -> "pd.DataFrame":
    """Convert a result Tensor into a pandas DataFrame.

    Expects dims (time, asset, output, param).
    """
    import pandas as pd

    time, asset_vals, output_vals, param_ids = _result_coords(tensor)
    param_names_list, param_values_list, include_param_levels = _result_param_metadata(
        tensor=tensor,
        param_ids=param_ids,
    )
    multi_assets = len(asset_vals) > 1
    multi_params = len(param_ids) > 1
    columns, column_data = _result_columns(
        data=tensor.data,
        asset_vals=asset_vals,
        output_vals=output_vals,
        param_ids=param_ids,
        multi_assets=multi_assets,
        multi_params=multi_params,
        include_param_levels=include_param_levels,
        param_names_list=param_names_list,
        param_values_list=param_values_list,
    )

    if not columns:
        return pd.DataFrame(index=time)

    column_index = _result_column_index(
        pd_module=pd,
        columns=columns,
        multi_assets=multi_assets,
        multi_params=multi_params,
        include_param_levels=include_param_levels,
        param_names_list=param_names_list,
    )

    stacked = np.column_stack(column_data)
    return pd.DataFrame(stacked, index=time, columns=column_index)


def _result_coords(
    tensor: Tensor,
) -> tuple[np.ndarray, list[object], list[object], list[object]]:
    if tensor.dims != ("time", "asset", "output", "param"):
        raise ValueError("result_to_dataframe expects dims (time, asset, output, param)")

    time = tensor.coords.get("time")
    asset = tensor.coords.get("asset")
    output = tensor.coords.get("output")
    param = tensor.coords.get("param")
    if time is None or asset is None or output is None or param is None:
        raise ValueError("Tensor coords must include time, asset, output, param")
    return np.asarray(list(time)), list(asset), list(output), list(param)


def _result_param_metadata(
    *,
    tensor: Tensor,
    param_ids: list[object],
) -> tuple[list[str], list[Dict[str, Any]] | None, bool]:
    param_names_raw = tensor.attrs.get("param_names")
    param_values_raw = tensor.attrs.get("param_values")
    param_names = cast(Optional[Iterable[str]], param_names_raw)
    param_values = cast(Optional[Iterable[Dict[str, Any]]], param_values_raw)

    param_names_list = list(param_names) if param_names is not None else []
    param_values_list = list(param_values) if param_values is not None else None
    include_param_levels = (
        bool(param_names_list)
        and bool(param_values_list)
        and len(param_ids) > 1
        and param_values_list is not None
        and len(param_values_list) == len(param_ids)
    )
    return param_names_list, param_values_list, include_param_levels


def _result_columns(
    *,
    data: np.ndarray,
    asset_vals: list[object],
    output_vals: list[object],
    param_ids: list[object],
    multi_assets: bool,
    multi_params: bool,
    include_param_levels: bool,
    param_names_list: list[str],
    param_values_list: list[Dict[str, Any]] | None,
) -> tuple[list[tuple[object, ...]], list[np.ndarray]]:
    columns: list[tuple[object, ...]] = []
    column_data: list[np.ndarray] = []

    for a_idx, asset_id in enumerate(asset_vals):
        for o_idx, out in enumerate(output_vals):
            for p_idx, param_id in enumerate(param_ids):
                columns.append(
                    _result_column_tuple(
                        asset_id=asset_id,
                        out=out,
                        param_id=param_id,
                        p_idx=p_idx,
                        multi_assets=multi_assets,
                        multi_params=multi_params,
                        include_param_levels=include_param_levels,
                        param_names_list=param_names_list,
                        param_values_list=param_values_list,
                    )
                )
                column_data.append(data[:, a_idx, o_idx, p_idx])

    return columns, column_data


def _result_column_tuple(
    *,
    asset_id: object,
    out: object,
    param_id: object,
    p_idx: int,
    multi_assets: bool,
    multi_params: bool,
    include_param_levels: bool,
    param_names_list: list[str],
    param_values_list: list[Dict[str, Any]] | None,
) -> tuple[object, ...]:
    if include_param_levels:
        assert param_values_list is not None
        param_map = param_values_list[p_idx]
        param_tuple = tuple(param_map[name] for name in param_names_list)
    elif multi_params:
        param_tuple = (param_id,)
    else:
        param_tuple = ()

    col_items: list[object] = [asset_id, out] if multi_assets else [out]
    col_items.extend(param_tuple)
    return tuple(col_items)


def _result_column_index(
    *,
    pd_module: Any,
    columns: list[tuple[object, ...]],
    multi_assets: bool,
    multi_params: bool,
    include_param_levels: bool,
    param_names_list: list[str],
) -> Any:
    if (multi_assets or include_param_levels or multi_params) and len(columns[0]) > 1:
        names = ["asset", "output"] if multi_assets else ["output"]
        if include_param_levels:
            names = names + param_names_list
        elif multi_params:
            names = names + ["param"]
        return pd_module.MultiIndex.from_tuples(columns, names=names)
    return pd_module.Index([col[0] for col in columns])
