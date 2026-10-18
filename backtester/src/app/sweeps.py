"""Stateless, deterministic Parameter Sweep validation and expansion."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from itertools import product
from typing import Callable, Iterable, Mapping, TypeVar, cast

from db_accessor_client import normalize_timeframe_code
from domain.enums import AllowedDirections
from domain.types import BacktestRequest, BacktestRequestSnapshot, StrategyConfig
from strategies.registry import (
    InvalidParameterCombinationError,
    InvalidStrategyParameterError,
    StrategyVersionUnavailableError,
    strategy_catalog,
    validate_parameter_value,
)

from app.backtest_runs import (
    InvalidBacktestRequestError,
    _validate_execution,
    _validate_request_shape,
    _validate_submission,
)

T = TypeVar("T")


@dataclass(frozen=True)
class SweepDefinition:
    shared_request: BacktestRequest
    market_ids: tuple[int, ...]
    timeframes: tuple[str, ...]
    parameters: Mapping[str, Mapping[str, object]]
    allowed_directions: tuple[str, ...]


class SweepPreviewService:
    """The same pure expansion operation can be reused by batch acceptance."""

    def __init__(
        self,
        *,
        markets: Callable[[], list[dict[str, object]]],
        max_candidate_count: int = 1_000,
    ) -> None:
        if type(max_candidate_count) is not int or max_candidate_count <= 0:
            raise ValueError("max_candidate_count must be positive")
        self._markets = markets
        self.max_candidate_count = max_candidate_count

    def expand(self, definition: SweepDefinition) -> dict[str, object]:
        shared = definition.shared_request
        schema = _strategy_schema(definition)
        selected_markets, timeframes, directions = _selection_axes(definition, self._markets)
        parameter_axes, normalized_parameters = _parameter_axes(
            definition, schema, self.max_candidate_count
        )

        raw_count = len(selected_markets) * len(timeframes) * len(directions)
        for _, values in parameter_axes:
            raw_count *= len(values)
        if raw_count > self.max_candidate_count:
            raise InvalidBacktestRequestError(
                f"Raw candidate count {raw_count} exceeds "
                f"max_sweep_candidate_count {self.max_candidate_count}"
            )

        # Validate shared settings with a real member shape before expanding combinations.
        probe = replace(
            shared,
            symbols=[str(selected_markets[0]["symbol"])],
            exchange=str(selected_markets[0]["exchange"]),
            timeframe=timeframes[0],
            execution=replace(
                shared.execution, allowed_directions=AllowedDirections(directions[0])
            ),
            strategy=StrategyConfig(
                shared.strategy.strategy_id, {}, shared.strategy.strategy_version
            ),
        )
        _validate_request_shape(probe)
        _validate_execution(probe)
        candidates, ready_count = _candidate_rows(
            shared, selected_markets, timeframes, parameter_axes, directions
        )
        if ready_count == 0:
            raise InvalidBacktestRequestError("Parameter Sweep has no Ready candidates")
        return {
            "max_sweep_candidate_count": self.max_candidate_count,
            "normalized_selections": {
                "markets": selected_markets,
                "timeframes": timeframes,
                "parameters": normalized_parameters,
                "allowed_directions": directions,
            },
            "raw_count": raw_count,
            "ready_count": ready_count,
            "excluded_count": raw_count - ready_count,
            "candidates": candidates,
        }


def _strategy_schema(definition: SweepDefinition) -> list[dict[str, object]]:
    strategy = definition.shared_request.strategy
    entry = next(
        (item for item in strategy_catalog() if item["strategy_id"] == strategy.strategy_id),
        None,
    )
    if entry is None or entry["strategy_version"] != strategy.strategy_version:
        raise StrategyVersionUnavailableError("strategy_version_unavailable")
    schema = cast(list[dict[str, object]], entry["parameters"])
    unknown = set(definition.parameters) - {str(field["name"]) for field in schema}
    if unknown:
        name = sorted(unknown)[0]
        raise InvalidStrategyParameterError(name, f"Unknown strategy parameter: {name}")
    return schema


def _selection_axes(
    definition: SweepDefinition, markets: Callable[[], list[dict[str, object]]]
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    if not definition.market_ids or not definition.timeframes or not definition.allowed_directions:
        raise InvalidBacktestRequestError(
            "Markets, Timeframes, and Allowed Directions must be nonempty"
        )
    market_by_id = {market.get("symbol_id"): market for market in markets()}
    selected_markets: list[dict[str, object]] = []
    for market_id in _unique(definition.market_ids):
        market = market_by_id.get(market_id)
        if (
            type(market_id) is not int
            or market is None
            or not market.get("symbol")
            or not market.get("exchange")
        ):
            raise InvalidBacktestRequestError(f"Market is unavailable: {market_id}")
        selected_markets.append(
            {"symbol_id": market_id, "symbol": market["symbol"], "exchange": market["exchange"]}
        )
    try:
        timeframes = _unique(normalize_timeframe_code(code) for code in definition.timeframes)
    except (TypeError, ValueError) as exc:
        raise InvalidBacktestRequestError("Unsupported Timeframe") from exc
    try:
        directions = _unique(
            AllowedDirections(value).value for value in definition.allowed_directions
        )
    except ValueError as exc:
        raise InvalidBacktestRequestError("Unsupported Allowed Directions") from exc
    return selected_markets, timeframes, directions


def _parameter_axes(
    definition: SweepDefinition, schema: list[dict[str, object]], limit: int
) -> tuple[list[tuple[str, list[object]]], dict[str, dict[str, object]]]:
    axes: list[tuple[str, list[object]]] = []
    normalized: dict[str, dict[str, object]] = {}
    for field in schema:
        name = str(field["name"])
        axis = definition.parameters.get(name)
        if axis is None:
            if "default" not in field:
                raise InvalidStrategyParameterError(
                    name, f"Missing required strategy parameter: {name}"
                )
            values = [validate_parameter_value(field, field["default"])]
            normalized[name] = {"mode": "default", "values": values}
        else:
            mode = axis.get("mode")
            if mode == "constant" and "value" in axis:
                raw_values = [axis["value"]]
            elif mode == "values":
                supplied = axis.get("values")
                if not isinstance(supplied, list) or not supplied:
                    raise InvalidStrategyParameterError(name, f"Invalid values for {name}")
                raw_values = supplied
            elif mode == "range":
                if field["type"] not in ("int", "float") or "choices" in field:
                    raise InvalidStrategyParameterError(name, f"{name} does not support ranges")
                raw_values = _range_values(name, axis, str(field["type"]), limit)
            else:
                raise InvalidStrategyParameterError(name, f"Invalid input mode for {name}")
            values = _unique(validate_parameter_value(field, value) for value in raw_values)
            normalized[name] = {"mode": mode, "values": values}
            if mode == "range":
                normalized[name]["range"] = {key: axis[key] for key in ("start", "stop", "step")}
        axes.append((name, values))
    return axes, normalized


def _candidate_rows(
    shared: BacktestRequest,
    markets: list[dict[str, object]],
    timeframes: list[str],
    parameter_axes: list[tuple[str, list[object]]],
    directions: list[str],
) -> tuple[list[dict[str, object]], int]:
    candidates: list[dict[str, object]] = []
    ready_count = 0
    axes = [markets, timeframes, *(values for _, values in parameter_axes), directions]
    for ordinal, combination in enumerate(product(*axes)):
        market, timeframe, *tail = combination
        assert isinstance(market, dict)
        parameters = dict(zip((name for name, _ in parameter_axes), tail[:-1]))
        direction = str(tail[-1])
        request = replace(
            shared,
            symbols=[str(market["symbol"])],
            exchange=str(market["exchange"]),
            timeframe=str(timeframe),
            strategy=StrategyConfig(
                shared.strategy.strategy_id, parameters, shared.strategy.strategy_version
            ),
            execution=replace(shared.execution, allowed_directions=AllowedDirections(direction)),
        )
        row: dict[str, object] = {
            "candidate_ordinal": ordinal,
            "market": market,
            "timeframe": timeframe,
            "parameters": parameters,
            "allowed_directions": direction,
        }
        try:
            resolved = _validate_submission(request)
        except InvalidParameterCombinationError as exc:
            row.update(
                {
                    "status": "excluded",
                    "issues": [{"code": exc.code, "fields": list(exc.fields), "message": str(exc)}],
                }
            )
        else:
            row.update(
                {
                    "status": "ready",
                    "member_ordinal": ready_count,
                    "request": dict(BacktestRequestSnapshot.from_request(resolved).payload),
                }
            )
            ready_count += 1
        candidates.append(row)
    return candidates, ready_count


def _unique(values: Iterable[T]) -> list[T]:
    result: list[T] = []
    seen: set[tuple[type, object]] = set()
    for value in values:
        key = (type(value), value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _range_values(name: str, axis: Mapping[str, object], kind: str, limit: int) -> list[object]:
    try:
        if any(type(axis[key]) not in (int, float, str) for key in ("start", "stop", "step")):
            raise ValueError
        start, stop, step = (Decimal(str(axis[key])) for key in ("start", "stop", "step"))
        if not all(value.is_finite() for value in (start, stop, step)) or step <= 0 or start > stop:
            raise ValueError
        if kind == "int" and any(
            value != value.to_integral_value() for value in (start, stop, step)
        ):
            raise ValueError
        count = int((stop - start) // step) + 1
        if count > limit:
            raise InvalidBacktestRequestError(
                f"Raw candidate count exceeds max_sweep_candidate_count {limit}"
            )
        return [
            int(start + step * index) if kind == "int" else float(start + step * index)
            for index in range(count)
        ]
    except InvalidBacktestRequestError:
        raise
    except (KeyError, ValueError, InvalidOperation, OverflowError) as exc:
        raise InvalidStrategyParameterError(name, f"Invalid range for {name}") from exc
