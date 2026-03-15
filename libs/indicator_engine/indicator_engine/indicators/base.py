"""Base class for indicator implementations."""

from __future__ import annotations

from typing import Any, Dict

from ..core.spec import IndicatorSpec


class IndicatorBase:
    """Base class for indicators with batch/update hooks."""
    spec: IndicatorSpec

    def batch(self, *args, **kwargs):
        raise NotImplementedError

    def batch_vectorized(self, *args, **kwargs):
        raise NotImplementedError

    def init_state(self, *args, **kwargs):
        raise NotImplementedError

    def update(self, *args, **kwargs):
        raise NotImplementedError
