"""Vectorized condition helpers for strategies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


class ConditionOperator(str, Enum):
    CROSSOVER = "crossover"
    CROSSUNDER = "crossunder"
    ABOVE = "above"
    BELOW = "below"


@dataclass(frozen=True)
class ConditionRule:
    left_feature: str
    operator: ConditionOperator
    right_feature: str

    def __post_init__(self) -> None:
        if not isinstance(self.left_feature, str):
            raise ValueError("condition left_feature must be a non-empty string")
        if not isinstance(self.right_feature, str):
            raise ValueError("condition right_feature must be a non-empty string")

        left_feature = self.left_feature.strip()
        right_feature = self.right_feature.strip()
        if not left_feature:
            raise ValueError("condition left_feature must be non-empty")
        if not right_feature:
            raise ValueError("condition right_feature must be non-empty")
        object.__setattr__(self, "left_feature", left_feature)
        object.__setattr__(self, "right_feature", right_feature)
        object.__setattr__(self, "operator", ConditionOperator(self.operator))

    @classmethod
    def crossover(cls, left_feature: str, right_feature: str) -> "ConditionRule":
        return cls(
            left_feature=left_feature,
            operator=ConditionOperator.CROSSOVER,
            right_feature=right_feature,
        )

    @classmethod
    def crossunder(cls, left_feature: str, right_feature: str) -> "ConditionRule":
        return cls(
            left_feature=left_feature,
            operator=ConditionOperator.CROSSUNDER,
            right_feature=right_feature,
        )

    @classmethod
    def above(cls, left_feature: str, right_feature: str) -> "ConditionRule":
        return cls(
            left_feature=left_feature,
            operator=ConditionOperator.ABOVE,
            right_feature=right_feature,
        )

    @classmethod
    def below(cls, left_feature: str, right_feature: str) -> "ConditionRule":
        return cls(
            left_feature=left_feature,
            operator=ConditionOperator.BELOW,
            right_feature=right_feature,
        )

    def evaluate_vectorized(
        self,
        feature_map: Mapping[str, ArrayLike],
    ) -> NDArray[np.bool_]:
        left, right = self._vectorized_operands(feature_map)
        if self.operator == ConditionOperator.CROSSOVER:
            return crossover(left, right)
        if self.operator == ConditionOperator.CROSSUNDER:
            return crossunder(left, right)
        if self.operator == ConditionOperator.ABOVE:
            return above(left, right)
        if self.operator == ConditionOperator.BELOW:
            return below(left, right)
        raise ValueError(f"Unsupported condition operator: {self.operator}")

    def evaluate_sequential(
        self,
        *,
        previous: Mapping[str, float] | None,
        current: Mapping[str, float],
    ) -> bool:
        current_left = self._scalar_operand(current, self.left_feature)
        current_right = self._scalar_operand(current, self.right_feature)
        if not math.isfinite(current_left) or not math.isfinite(current_right):
            return False

        if self.operator == ConditionOperator.ABOVE:
            return current_left > current_right
        if self.operator == ConditionOperator.BELOW:
            return current_left < current_right

        if previous is None:
            return False

        previous_left = self._scalar_operand(previous, self.left_feature)
        previous_right = self._scalar_operand(previous, self.right_feature)
        if not math.isfinite(previous_left) or not math.isfinite(previous_right):
            return False

        if self.operator == ConditionOperator.CROSSOVER:
            return current_left > current_right and previous_left <= previous_right
        if self.operator == ConditionOperator.CROSSUNDER:
            return current_left < current_right and previous_left >= previous_right

        raise ValueError(f"Unsupported condition operator: {self.operator}")

    def _vectorized_operands(
        self,
        feature_map: Mapping[str, ArrayLike],
    ) -> tuple[ArrayLike, ArrayLike]:
        missing = [
            feature_name
            for feature_name in (self.left_feature, self.right_feature)
            if feature_name not in feature_map
        ]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"condition is missing required feature(s): {missing_text}")
        return feature_map[self.left_feature], feature_map[self.right_feature]

    @staticmethod
    def _scalar_operand(feature_map: Mapping[str, float], feature_name: str) -> float:
        if feature_name not in feature_map:
            raise ValueError(f"condition is missing required feature(s): {feature_name}")
        return float(feature_map[feature_name])


def _as_comparable_arrays(
    left: ArrayLike,
    right: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    left_arr = np.asarray(left, dtype=np.float64)
    right_arr = np.asarray(right, dtype=np.float64)
    if left_arr.shape != right_arr.shape:
        raise ValueError("left and right arrays must have the same shape")
    return left_arr, right_arr


def crossover(left: ArrayLike, right: ArrayLike) -> NDArray[np.bool_]:
    """Return a mask where `left` crosses above `right`."""

    left_arr, right_arr = _as_comparable_arrays(left, right)

    if left_arr.size == 0:
        return np.asarray([], dtype=np.bool_)

    prev_left = np.concatenate(([np.nan], left_arr[:-1]))
    prev_right = np.concatenate(([np.nan], right_arr[:-1]))

    current_valid = np.isfinite(left_arr) & np.isfinite(right_arr)
    previous_valid = np.isfinite(prev_left) & np.isfinite(prev_right)

    return (left_arr > right_arr) & (prev_left <= prev_right) & current_valid & previous_valid


def crossunder(left: ArrayLike, right: ArrayLike) -> NDArray[np.bool_]:
    """Return a mask where `left` crosses below `right`."""

    left_arr, right_arr = _as_comparable_arrays(left, right)

    if left_arr.size == 0:
        return np.asarray([], dtype=np.bool_)

    prev_left = np.concatenate(([np.nan], left_arr[:-1]))
    prev_right = np.concatenate(([np.nan], right_arr[:-1]))

    current_valid = np.isfinite(left_arr) & np.isfinite(right_arr)
    previous_valid = np.isfinite(prev_left) & np.isfinite(prev_right)

    return (left_arr < right_arr) & (prev_left >= prev_right) & current_valid & previous_valid


def above(left: ArrayLike, right: ArrayLike) -> NDArray[np.bool_]:
    """Return element-wise `left > right` comparison."""

    left_arr, right_arr = _as_comparable_arrays(left, right)
    valid = np.isfinite(left_arr) & np.isfinite(right_arr)
    return (left_arr > right_arr) & valid


def below(left: ArrayLike, right: ArrayLike) -> NDArray[np.bool_]:
    """Return element-wise `left < right` comparison."""

    left_arr, right_arr = _as_comparable_arrays(left, right)
    valid = np.isfinite(left_arr) & np.isfinite(right_arr)
    return (left_arr < right_arr) & valid
