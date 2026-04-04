"""Parameter grid utilities for deterministic sweeps."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, Iterator, List, Tuple

import numpy as np

ParamSet = Dict[str, Any]


def _normalize_values(values: Any) -> List[Any]:
    if isinstance(values, (list, tuple, np.ndarray)):
        return list(values)
    if isinstance(values, set):
        return sorted(values)
    return [values]


@dataclass(frozen=True)
class ParamGrid:
    """Deterministic Cartesian product of parameter values.

    Parameter names are sorted to ensure stable ordering. Each combination
    receives a deterministic `param_id` based on ordering.
    """

    param_space: Dict[str, Any]

    _names: List[str] = field(init=False, repr=False)
    _values: List[Tuple[str, List[Any]]] = field(init=False, repr=False)
    _grid_params: List[ParamSet] = field(init=False, repr=False)
    _param_ids: List[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_names", sorted(self.param_space.keys()))
        norm_values = [(_name, _normalize_values(self.param_space[_name])) for _name in self._names]
        object.__setattr__(self, "_values", norm_values)
        grid_params: List[ParamSet] = []
        param_ids: List[str] = []
        if not self._names:
            grid_params.append({})
            param_ids.append("default")
        else:
            value_lists = [vals for _, vals in self._values]
            for idx, combo in enumerate(product(*value_lists)):
                params = {name: combo[i] for i, name in enumerate(self._names)}
                grid_params.append(params)
                param_ids.append(self._param_id(params))
        object.__setattr__(self, "_grid_params", grid_params)
        object.__setattr__(self, "_param_ids", param_ids)

    def __len__(self) -> int:
        return len(self._grid_params)

    def __iter__(self) -> Iterator[Tuple[str, ParamSet]]:
        for param_id, params in zip(self._param_ids, self._grid_params):
            yield param_id, params

    @property
    def param_ids(self) -> List[str]:
        return list(self._param_ids)

    @property
    def param_names(self) -> List[str]:
        return list(self._names)

    @property
    def grid_params(self) -> List[ParamSet]:
        return list(self._grid_params)

    def to_coords(self) -> np.ndarray:
        return np.array(self._param_ids, dtype=object)

    def _param_id(self, params: ParamSet) -> str:
        if not self._names:
            return "default"
        parts = [f"{name}={params[name]}" for name in self._names]
        return "|".join(parts)
