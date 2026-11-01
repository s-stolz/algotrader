"""Indicator metadata and warmup policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .history import InputHistory, InputHistoryPlan


@dataclass(frozen=True)
class IndicatorSpec:
    """Static metadata for an indicator implementation.

    The `warmup` method returns the minimum bar count before output is ready.
    `plan_history` additionally accounts for anchored calculation history;
    a minimum warmup alone does not describe a cumulative indicator's inputs.
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
    output_assets: Optional[List[str]] = None
    input_history: InputHistory = field(default_factory=InputHistory)

    def plan_history(self, *, start_ms: int, params: Dict[str, Any]) -> InputHistoryPlan:
        """Resolve required input history before an adapter fetches candles."""
        return self.input_history.plan(start_ms=start_ms, warmup_bars=self.warmup(params))

    def warmup(self, params: Dict[str, Any]) -> int:
        if self.warmup_fn is None:
            return 1
        value = int(self.warmup_fn(params))
        return max(1, value)
