"""Stateless, deterministic Backtest validation and expansion."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
from itertools import product
from typing import Any, Callable, Iterable, Mapping, TypeVar, cast

from db_accessor_client import normalize_timeframe_code
from domain.enums import AllowedDirections
from domain.risk import InstrumentSpec
from domain.schedule import DailyTradingSchedule
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
class BacktestDefinition:
    shared_request: BacktestRequest
    market_ids: tuple[int, ...]
    timeframes: tuple[str, ...]
    parameters: Mapping[str, Mapping[str, object]]
    allowed_directions: tuple[str, ...]
    daily_schedules: tuple[DailyTradingSchedule, ...] | None = None


class BacktestPreviewService:
    """The same pure expansion operation can be reused by backtest acceptance."""

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

    def expand(self, definition: BacktestDefinition) -> dict[str, object]:
        shared = definition.shared_request
        schema = _strategy_schema(definition)
        selected_markets, timeframes, directions = _selection_axes(definition, self._markets)
        schedules = _schedule_axis(definition)
        parameter_axes, normalized_parameters = _parameter_axes(
            definition, schema, self.max_candidate_count
        )

        raw_count = len(selected_markets) * len(timeframes) * len(directions) * len(schedules)
        for _, values in parameter_axes:
            raw_count *= len(values)
        if raw_count > self.max_candidate_count:
            raise InvalidBacktestRequestError(
                f"Raw candidate count {raw_count} exceeds "
                f"max_backtest_candidate_count {self.max_candidate_count}"
            )

        # Validate shared settings with a real member shape before expanding combinations.
        probe = replace(
            shared,
            symbols=[str(selected_markets[0]["symbol"])],
            exchange=str(selected_markets[0]["exchange"]),
            instrument=_instrument(selected_markets[0]) if shared.execution.sizing else None,
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
            shared, selected_markets, timeframes, parameter_axes, directions, schedules
        )
        if ready_count == 0:
            raise InvalidBacktestRequestError("Backtest has no Ready candidates")
        return {
            "max_backtest_candidate_count": self.max_candidate_count,
            "normalized_selections": {
                "markets": selected_markets,
                "timeframes": timeframes,
                "parameters": normalized_parameters,
                "allowed_directions": directions,
                **(
                    {"daily_schedules": [asdict(schedule) for schedule in schedules if schedule]}
                    if definition.daily_schedules is not None
                    else {}
                ),
            },
            "raw_count": raw_count,
            "ready_count": ready_count,
            "excluded_count": raw_count - ready_count,
            "candidates": candidates,
        }


def _schedule_axis(definition: BacktestDefinition) -> list[DailyTradingSchedule | None]:
    if definition.daily_schedules is None:
        return [definition.shared_request.execution.daily_schedule]
    if definition.shared_request.execution.daily_schedule is not None:
        raise InvalidBacktestRequestError(
            "Use daily_schedules or execution.daily_schedule, not both"
        )
    if not definition.daily_schedules or any(
        not isinstance(schedule, DailyTradingSchedule) for schedule in definition.daily_schedules
    ):
        raise InvalidBacktestRequestError(
            "Daily schedules must contain valid schedule alternatives"
        )
    return list(_unique(definition.daily_schedules))


def _strategy_schema(definition: BacktestDefinition) -> list[dict[str, object]]:
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
    definition: BacktestDefinition, markets: Callable[[], list[dict[str, object]]]
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
        min_move = market.get("min_move")
        if min_move is not None and (
            isinstance(min_move, bool)
            or not isinstance(min_move, (int, float))
            or not math.isfinite(min_move)
            or min_move <= 0
        ):
            raise InvalidBacktestRequestError(
                f"Market min_move must be positive and finite: {market_id}"
            )
        selected_markets.append(
            {
                **{
                    key: market[key]
                    for key in (
                        "settlement_currency",
                        "contract_multiplier",
                        "minimum_quantity",
                        "quantity_step",
                    )
                    if key in market
                },
                "symbol_id": market_id,
                "symbol": market["symbol"],
                "exchange": market["exchange"],
                **({"min_move": min_move} if min_move is not None else {}),
            }
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
    definition: BacktestDefinition, schema: list[dict[str, object]], limit: int
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
    schedules: list[DailyTradingSchedule | None],
) -> tuple[list[dict[str, object]], int]:
    candidates: list[dict[str, object]] = []
    ready_count = 0
    axes = [markets, timeframes, *(values for _, values in parameter_axes), directions, schedules]
    for ordinal, combination in enumerate(product(*axes)):
        market, timeframe, *tail = combination
        assert isinstance(market, dict)
        parameters = dict(zip((name for name, _ in parameter_axes), tail[:-2]))
        direction = str(tail[-2])
        schedule = cast(DailyTradingSchedule | None, tail[-1])
        request = replace(
            shared,
            symbols=[str(market["symbol"])],
            exchange=str(market["exchange"]),
            market_min_move=cast(float | None, market.get("min_move")),
            instrument=_instrument(market) if shared.execution.sizing else None,
            timeframe=str(timeframe),
            strategy=StrategyConfig(
                shared.strategy.strategy_id, parameters, shared.strategy.strategy_version
            ),
            execution=replace(
                shared.execution,
                allowed_directions=AllowedDirections(direction),
                daily_schedule=schedule,
            ),
        )
        row: dict[str, object] = {
            "candidate_ordinal": ordinal,
            "market": market,
            "timeframe": timeframe,
            "parameters": parameters,
            "allowed_directions": direction,
            **({"daily_schedule": asdict(schedule)} if schedule is not None else {}),
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
                    "run_ordinal": ready_count,
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
                f"Raw candidate count exceeds max_backtest_candidate_count {limit}"
            )
        return [
            int(start + step * index) if kind == "int" else float(start + step * index)
            for index in range(count)
        ]
    except InvalidBacktestRequestError:
        raise
    except (KeyError, ValueError, InvalidOperation, OverflowError) as exc:
        raise InvalidStrategyParameterError(name, f"Invalid range for {name}") from exc


def _instrument(market: dict[str, object]) -> InstrumentSpec:
    try:
        return InstrumentSpec(
            **{
                key: cast(Any, market[key])
                for key in (
                    "symbol_id",
                    "settlement_currency",
                    "contract_multiplier",
                    "minimum_quantity",
                    "quantity_step",
                    "min_move",
                )
            }
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidBacktestRequestError(f"Invalid instrument specifications: {exc}") from exc
