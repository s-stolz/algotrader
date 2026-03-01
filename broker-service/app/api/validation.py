from __future__ import annotations

import json
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request

from app.api.contracts import ClosePositionRequestBody, OrderRequestBody
from app.domain.value_objects import OrderType, TradeSide

ORDER_TYPE_VALUES = frozenset(member.value for member in OrderType)
TRADE_SIDE_VALUES = frozenset(member.value for member in TradeSide)


def _validation_error(loc: list[str], message: str, input_value: Any) -> RequestValidationError:
    return RequestValidationError(
        [{
            "type": "value_error",
            "loc": ["body", *loc],
            "msg": message,
            "input": input_value,
        }]
    )


async def read_json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise RequestValidationError(
            [{
                "type": "json_invalid",
                "loc": ["body", exc.lineno, exc.colno],
                "msg": "JSON decode error",
                "input": {},
            }]
        ) from exc

    if not isinstance(body, dict):
        raise _validation_error([], "Input should be a valid dictionary", body)
    return body


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise RequestValidationError(
            [{
                "type": "missing",
                "loc": ["body", key],
                "msg": "Field required",
                "input": payload,
            }]
        )
    if not isinstance(value, str):
        raise _validation_error([key], "Input should be a valid string", value)
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if not isinstance(value, str):
        raise _validation_error([key], "Input should be a valid string", value)
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if value is None:
        raise RequestValidationError(
            [{
                "type": "missing",
                "loc": ["body", key],
                "msg": "Field required",
                "input": payload,
            }]
        )
    if not isinstance(value, int) or isinstance(value, bool):
        raise _validation_error([key], "Input should be a valid integer", value)
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise _validation_error([key], "Input should be a valid integer", value)
    return value


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _validation_error([key], "Input should be a valid number", value)
    return float(value)


def parse_order_request(payload: dict[str, Any]) -> OrderRequestBody:
    order_type = _required_str(payload, "orderType")
    trade_side = _required_str(payload, "tradeSide")

    if order_type not in ORDER_TYPE_VALUES:
        raise _validation_error(["orderType"], "Input should be a valid enum value", order_type)
    if trade_side not in TRADE_SIDE_VALUES:
        raise _validation_error(["tradeSide"], "Input should be a valid enum value", trade_side)

    result: OrderRequestBody = {
        "symbol": _required_str(payload, "symbol"),
        "orderType": order_type,
        "tradeSide": trade_side,
        "volume": _required_int(payload, "volume"),
    }

    optional_float_keys = ["limitPrice", "stopPrice", "stopLoss", "takeProfit"]
    optional_int_keys = ["expirationTimestamp"]
    optional_str_keys = ["timeInForce", "comment", "label", "clientOrderId"]

    for key in optional_float_keys:
        value = _optional_float(payload, key)
        if value is not None:
            result[key] = value
    for key in optional_int_keys:
        value = _optional_int(payload, key)
        if value is not None:
            result[key] = value
    for key in optional_str_keys:
        value = _optional_str(payload, key)
        if value is not None:
            result[key] = value

    return result


def parse_close_position_request(payload: dict[str, Any]) -> ClosePositionRequestBody:
    result: ClosePositionRequestBody = {}
    value = _optional_int(payload, "closeQuantity")
    if value is not None:
        result["closeQuantity"] = value
    return result


def parse_tick_stream_body(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    queue_size = _optional_int(payload, "queueSize")
    if queue_size is not None and queue_size < 1:
        raise _validation_error(["queueSize"], "Input should be greater than or equal to 1", queue_size)

    max_stream_length = _optional_int(payload, "maxStreamLength")
    if max_stream_length is not None and max_stream_length < 100:
        raise _validation_error(
            ["maxStreamLength"],
            "Input should be greater than or equal to 100",
            max_stream_length,
        )

    return queue_size, max_stream_length
