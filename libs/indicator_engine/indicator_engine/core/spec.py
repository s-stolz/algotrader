"""Indicator metadata and warmup policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class IndicatorSpec:
    """Static metadata for an indicator implementation.

    The `warmup` method returns the number of bars required to produce
    stable outputs for a given parameter set. This is used by engines
    to fetch enough history and to trim initial NaNs.
    """
    id: str
    name: str
    description: str = ""
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    required_assets: Optional[List[str]] = None
    supports_update: bool = False
    supports_vectorized: bool = False
    warmup_fn: Optional[Callable[[Dict[str, Any]], int]] = None

    def warmup(self, params: Dict[str, Any]) -> int:
        if self.warmup_fn is None:
            return 1
        value = int(self.warmup_fn(params))
        return max(1, value)
