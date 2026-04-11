"""Vectorized condition helpers for strategies."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


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
    return left_arr > right_arr


def below(left: ArrayLike, right: ArrayLike) -> NDArray[np.bool_]:
    """Return element-wise `left < right` comparison."""

    left_arr, right_arr = _as_comparable_arrays(left, right)
    return left_arr < right_arr
