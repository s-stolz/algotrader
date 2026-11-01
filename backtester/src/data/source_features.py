"""Batch and sequential adapters over aligned multi-source indicator inputs."""

from typing import Mapping

import numpy as np
import pandas as pd
from db_accessor_client.timeframes import timeframe_to_minutes
from indicator_engine import BatchEngine, HistoryPolicy, ParamGrid, UpdateEngine, get_registry
from strategies.base import IndicatorFeatureRequirement, StrategyDefinition

from data.indicator_inputs import IndicatorInput, prepare_indicator_inputs


def build_source_features(
    *,
    bars: pd.DataFrame,
    strategy: StrategyDefinition,
    timeframe: str,
    feature_bars: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    strategy.require_v1_parity_model()
    featured = bars.copy()
    available = np.ones(len(bars), dtype=bool)
    for requirement in strategy.indicator_requirements:
        values = {}
        for block in prepare_indicator_inputs(
            requirement=requirement,
            symbol=str(bars["symbol"].iloc[0]),
            timeframe=timeframe,
            bars=bars,
            feature_bars=feature_bars,
        ):
            tensor = (
                BatchEngine(get_registry())
                .run(requirement.indicator_id, block.bars, ParamGrid(dict(requirement.parameters)))
                .tensor
            )
            asset = requirement.output_asset or str(bars["symbol"].iloc[0])
            asset_idx = list(tensor.coords["asset"]).index(asset)
            output_idx = _output_index(
                tensor.coords["output"], requirement.resolve_output_key(str(bars["symbol"].iloc[0]))
            )
            output = tensor.data[:, asset_idx, output_idx, 0]
            for timestamp, value, ready in zip(
                block.bars.time, output, block.available, strict=True
            ):
                if timestamp in values and not ready:
                    continue  # A daily seed must not overwrite the preceding day's final output.
                values[int(timestamp)] = float(value) if ready else np.nan
        if requirement.capture_at_utc_minute is not None:
            offset = (requirement.capture_at_utc_minute - timeframe_to_minutes(timeframe)) * 60_000
            timestamps = bars["timestamp_ms"].to_numpy(dtype=np.int64)
            capture_times = timestamps // 86_400_000 * 86_400_000 + offset
            captured = pd.Series(capture_times).map(values).to_numpy(dtype=np.float64)
            column = np.where(timestamps >= capture_times, captured, np.nan)
        else:
            column = (
                bars["timestamp_ms"]
                .map(lambda t: values.get(int(t), np.nan))
                .to_numpy(dtype=np.float64)
            )
        featured[requirement.feature_name] = column
        available &= np.isfinite(column)
    featured["indicators_available"] = available.astype(float)
    return featured


class SourceFeatureStream:
    """Advance each source timeline only through the current completed traded bar."""

    def __init__(
        self,
        *,
        bars: pd.DataFrame,
        strategy: StrategyDefinition,
        timeframe: str,
        feature_bars: Mapping[str, pd.DataFrame],
    ) -> None:
        symbol = str(bars["symbol"].iloc[0])
        self._features = [
            _SourceFeature(
                requirement,
                symbol,
                timeframe,
                prepare_indicator_inputs(
                    requirement=requirement,
                    symbol=symbol,
                    timeframe=timeframe,
                    bars=bars,
                    feature_bars=feature_bars,
                ),
            )
            for requirement in strategy.indicator_requirements
        ]

    def update(self, timestamp_ms: int) -> dict[str, float]:
        features = {
            item.requirement.feature_name: item.update(timestamp_ms) for item in self._features
        }
        features["indicators_available"] = float(all(np.isfinite(v) for v in features.values()))
        return features


class _SourceFeature:
    def __init__(
        self,
        requirement: IndicatorFeatureRequirement,
        symbol: str,
        timeframe: str,
        blocks: list[IndicatorInput],
    ) -> None:
        self.requirement = requirement
        self._symbol = symbol
        self._timeframe = timeframe
        self._blocks = iter(blocks)
        self._block: IndicatorInput | None = None
        self._row = 0
        self._capture_offset = (
            None
            if requirement.capture_at_utc_minute is None
            else (requirement.capture_at_utc_minute - timeframe_to_minutes(timeframe)) * 60_000
        )
        self._captured_day: int | None = None
        self._captured_value = np.nan
        self._engine: UpdateEngine | None = None

    def _advance_block(self) -> bool:
        self._block = next(self._blocks, None)
        if self._block is None:
            return False
        self._row = 0
        registry = get_registry()
        warmup = registry.get(self.requirement.indicator_id).spec.warmup(
            dict(self.requirement.parameters)
        )
        self._engine = UpdateEngine(
            registry, HistoryPolicy(mode="rolling", max_rows=max(2, warmup))
        )
        self._engine.register_indicator(
            self.requirement.indicator_id,
            self._timeframe,
            assets=self._block.bars.assets,
            fields=self._block.bars.fields,
            param_grid=ParamGrid(dict(self.requirement.parameters)),
        )
        return True

    def update(self, timestamp_ms: int) -> float:
        value = self._advance(timestamp_ms)
        if self._capture_offset is None:
            return value
        return self._captured_value if self._captured_day == timestamp_ms // 86_400_000 else np.nan

    def _advance(self, timestamp_ms: int) -> float:
        value = np.nan
        while True:
            if self._block is None or self._row == len(self._block.bars.time):
                if not self._advance_block():
                    return value
            assert self._block is not None and self._engine is not None
            timestamp = int(self._block.bars.time[self._row])
            if timestamp > timestamp_ms:
                return value
            tensor = self._engine.on_bar(
                self._timeframe, timestamp, self._block.bars.data[self._row]
            )[self.requirement.indicator_id]
            if self._capture_offset is not None and timestamp % 86_400_000 == self._capture_offset:
                self._captured_day = timestamp // 86_400_000
                self._captured_value = (
                    float(
                        tensor.latest_value(
                            asset=self.requirement.output_asset or self._symbol,
                            output=self.requirement.resolve_output_key(self._symbol),
                        )
                    )
                    if self._block.available[self._row]
                    else np.nan
                )
            if timestamp == timestamp_ms:
                if self._block.available[self._row]:
                    value = float(
                        tensor.latest_value(
                            asset=self.requirement.output_asset or self._symbol,
                            output=self.requirement.resolve_output_key(self._symbol),
                        )
                    )
                self._row += 1
                return value
            self._row += 1


def _output_index(outputs: np.ndarray, key: str | None) -> int:
    if key is None and len(outputs) == 1:
        return 0
    if key not in outputs:
        raise ValueError(f"Indicator output {key!r} is not available")
    return list(outputs).index(key)
