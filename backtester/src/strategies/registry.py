"""Discover versioned strategy modules and validate their public parameters."""

from __future__ import annotations

import importlib
import inspect
import math
import pkgutil
from dataclasses import dataclass
from types import UnionType
from typing import Annotated, Callable, Mapping, Union, get_args, get_origin, get_type_hints

from domain.types import StrategyConfig

from strategies.base import StrategyDefinition


@dataclass(frozen=True)
class ParameterInfo:
    minimum: int | float | None = None
    maximum: int | float | None = None
    exclusive_minimum: bool = False
    exclusive_maximum: bool = False
    choices: tuple[int | float | str, ...] | None = None
    description: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class RegisteredStrategy:
    strategy_id: str
    strategy_version: int
    builder: Callable[..., StrategyDefinition]
    display_name: str | None = None
    validator: Callable[[Mapping[str, object]], None] | None = None


class InvalidParameterCombinationError(ValueError):
    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.code = "invalid_parameter_combination"
        self.fields = fields


class InvalidStrategyParameterError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.code = "invalid_strategy_parameter"
        self.fields = (field,)


class StrategyVersionUnavailableError(ValueError):
    pass


def reject_combination(*fields: str, message: str) -> None:
    if not fields or not message or "\n" in message:
        raise ValueError("Invalid strategy validator rejection")
    raise InvalidParameterCombinationError(tuple(fields), message)


_REGISTRY: dict[str, RegisteredStrategy] = {}
_DISCOVERED = False


def register_strategy(
    strategy_id: str,
    strategy_version: int,
    *,
    display_name: str | None = None,
    validator: Callable[[Mapping[str, object]], None] | None = None,
) -> Callable[[Callable[..., StrategyDefinition]], Callable[..., StrategyDefinition]]:
    def decorate(builder: Callable[..., StrategyDefinition]) -> Callable[..., StrategyDefinition]:
        if not strategy_id or type(strategy_version) is not int or strategy_version <= 0:
            raise ValueError("Strategy identity requires an ID and positive integer version")
        if strategy_id in _REGISTRY:
            raise ValueError(f"Duplicate strategy_id {strategy_id!r}")
        entry = RegisteredStrategy(strategy_id, strategy_version, builder, display_name, validator)
        _parameter_schema(entry)
        _REGISTRY[strategy_id] = entry
        return builder

    return decorate


def _discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    for package_name in ("strategies.examples", "strategies.custom"):
        package = importlib.import_module(package_name)
        for module in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            if not module.ispkg:
                importlib.import_module(module.name)
    _DISCOVERED = True


def current_strategy(strategy_id: str) -> RegisteredStrategy:
    _discover()
    try:
        return _REGISTRY[strategy_id]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy_id {strategy_id!r}") from exc


def strategy_catalog() -> list[dict[str, object]]:
    _discover()
    return [
        {
            "strategy_id": entry.strategy_id,
            "strategy_version": entry.strategy_version,
            "display_name": entry.display_name or entry.strategy_id,
            "parameters": _parameter_schema(entry),
        }
        for entry in sorted(_REGISTRY.values(), key=lambda item: item.strategy_id)
    ]


def _parameter_schema(entry: RegisteredStrategy) -> list[dict[str, object]]:
    signature = inspect.signature(entry.builder)
    hints = get_type_hints(entry.builder, include_extras=True)
    schema: list[dict[str, object]] = []
    for parameter in signature.parameters.values():
        kind, nullable, metadata = _parameter_type(parameter, hints.get(parameter.name))
        field: dict[str, object] = {
            "name": parameter.name,
            "type": kind,
            "nullable": nullable,
            "required": parameter.default is inspect.Parameter.empty,
        }
        if parameter.default is not inspect.Parameter.empty:
            field["default"] = parameter.default
        for key, value in (
            ("minimum", metadata.minimum),
            ("maximum", metadata.maximum),
            ("exclusive_minimum", metadata.exclusive_minimum or None),
            ("exclusive_maximum", metadata.exclusive_maximum or None),
            ("choices", list(metadata.choices) if metadata.choices is not None else None),
            ("description", metadata.description),
            ("display_name", metadata.display_name),
        ):
            if value is not None:
                field[key] = value
        if "default" in field:
            _validated_value(field, {})
        schema.append(field)
    return schema


def _parameter_type(
    parameter: inspect.Parameter, annotated: object
) -> tuple[str, bool, ParameterInfo]:
    if parameter.kind not in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        raise ValueError(f"Unsupported parameter kind: {parameter.name}")
    metadata = ParameterInfo()
    if get_origin(annotated) is Annotated:
        annotated, *extras = get_args(annotated)
        if len(extras) != 1 or not isinstance(extras[0], ParameterInfo):
            raise ValueError(f"Unsupported parameter metadata: {parameter.name}")
        metadata = extras[0]
    nullable = False
    if get_origin(annotated) in (UnionType, Union):
        members = get_args(annotated)
        if len(members) != 2 or type(None) not in members:
            raise ValueError(f"Unsupported parameter type: {parameter.name}")
        annotated = next(member for member in members if member is not type(None))
        nullable = True
    if annotated not in (bool, int, float, str):
        raise ValueError(f"Unsupported parameter type: {parameter.name}")
    kind = annotated.__name__
    if kind == "bool" and metadata.choices is not None:
        raise ValueError("Boolean choices are implicit")
    if kind in ("bool", "str") and (metadata.minimum is not None or metadata.maximum is not None):
        raise ValueError(f"Numeric bounds require numeric parameter: {parameter.name}")
    _validate_metadata(parameter.name, kind, metadata)
    return kind, nullable, metadata


def _validate_metadata(name: str, kind: str, metadata: ParameterInfo) -> None:
    _validate_bounds(name, metadata)
    if metadata.choices is None:
        return
    if not metadata.choices:
        raise ValueError(f"Choices must be nonempty: {name}")
    for choice in metadata.choices:
        if _valid_choice(kind, choice):
            continue
        raise ValueError(f"Invalid choice for parameter: {name}")


def _validate_bounds(name: str, metadata: ParameterInfo) -> None:
    if metadata.exclusive_minimum and metadata.minimum is None:
        raise ValueError(f"Exclusive minimum requires a minimum: {name}")
    if metadata.exclusive_maximum and metadata.maximum is None:
        raise ValueError(f"Exclusive maximum requires a maximum: {name}")
    for bound in (metadata.minimum, metadata.maximum):
        if bound is not None and (
            isinstance(bound, bool)
            or not isinstance(bound, (int, float))
            or not math.isfinite(bound)
        ):
            raise ValueError(f"Invalid numeric bound: {name}")
    if metadata.minimum is not None and metadata.maximum is not None:
        if metadata.minimum > metadata.maximum:
            raise ValueError(f"Minimum exceeds maximum: {name}")


def _valid_choice(kind: str, choice: object) -> bool:
    if kind == "int":
        return type(choice) is int
    if kind == "float":
        return (
            isinstance(choice, (int, float))
            and not isinstance(choice, bool)
            and math.isfinite(choice)
        )
    return kind == "str" and type(choice) is str


def validate_parameters(config: StrategyConfig) -> StrategyConfig:
    entry = current_strategy(config.strategy_id)
    if config.strategy_version is not None and config.strategy_version != entry.strategy_version:
        raise StrategyVersionUnavailableError("strategy_version_unavailable")
    schema = _parameter_schema(entry)
    unknown = set(config.parameters) - {str(field["name"]) for field in schema}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise InvalidStrategyParameterError(
            sorted(unknown)[0],
            f"Invalid parameters for strategy {config.strategy_id!r}: unknown {names}",
        )
    resolved: dict[str, object] = {}
    for field in schema:
        name = str(field["name"])
        try:
            resolved[name] = _validated_value(field, config.parameters)
        except ValueError as exc:
            raise InvalidStrategyParameterError(name, str(exc)) from exc
    if entry.validator is not None:
        try:
            entry.validator(resolved)
        except InvalidParameterCombinationError:
            raise
        except Exception as exc:
            raise RuntimeError("Strategy parameter validator failed") from exc
    return StrategyConfig(entry.strategy_id, resolved, entry.strategy_version)


def _validated_value(field: Mapping[str, object], provided: Mapping[str, object]) -> object:
    name = str(field["name"])
    if name in provided:
        value = provided[name]
    elif "default" in field:
        value = field["default"]
    else:
        raise ValueError(f"Missing required strategy parameter: {name}")
    kind = field["type"]
    if value is None:
        if not field["nullable"]:
            raise ValueError(f"{name} cannot be null")
        return None
    if kind == "float" and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    elif type(value).__name__ != kind:
        raise ValueError(f"{name} must be {kind}")
    _validate_constraints(name, value, field)
    return value


def _validate_constraints(name: str, value: object, field: Mapping[str, object]) -> None:
    minimum = field.get("minimum")
    maximum = field.get("maximum")
    choices = field.get("choices")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(minimum, (int, float)):
            is_below_minimum = (
                value <= minimum if field.get("exclusive_minimum") else value < minimum
            )
            if is_below_minimum:
                phrase = "greater than" if field.get("exclusive_minimum") else "at least"
                raise ValueError(f"{name} must be {phrase} {minimum}")
        if isinstance(maximum, (int, float)):
            is_above_maximum = (
                value >= maximum if field.get("exclusive_maximum") else value > maximum
            )
            if is_above_maximum:
                phrase = "less than" if field.get("exclusive_maximum") else "at most"
                raise ValueError(f"{name} must be {phrase} {maximum}")
    if isinstance(choices, list) and value not in choices:
        raise ValueError(f"{name} must be one of {choices}")


def resolve_strategy_and_parameters(
    config: StrategyConfig,
) -> tuple[StrategyDefinition, StrategyConfig]:
    resolved = validate_parameters(config)
    entry = current_strategy(resolved.strategy_id)
    return entry.builder(**resolved.parameters), resolved


def resolve_strategy(config: StrategyConfig) -> StrategyDefinition:
    strategy, _ = resolve_strategy_and_parameters(config)
    return strategy
