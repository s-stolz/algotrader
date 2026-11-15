"""Validated Candle stream frames shared by synchronous and asynchronous clients."""

import json

from .errors import DatabaseAccessorClientError


def parse_candle_frame(line: str):
    try:
        frame = json.loads(line)
        if frame == {"type": "complete"}:
            return None
        if frame.get("type") == "candles" and isinstance(frame.get("candles"), list):
            if len(frame["candles"]) > 1024:
                raise ValueError("Oversized Candle batch")
            return frame["candles"]
    except (ValueError, AttributeError, TypeError) as exc:
        raise DatabaseAccessorClientError("Invalid Candle stream") from exc
    raise DatabaseAccessorClientError("Invalid Candle stream")
