from __future__ import annotations

import unittest
from decimal import Decimal

from app.api.serialization import serialize_symbol_light, serialize_tick_stream_status, to_jsonable
from app.domain.value_objects import SymbolDescriptor, SymbolId, TickStreamStatus


class SerializationTests(unittest.TestCase):
    def test_symbol_light_serializer(self) -> None:
        symbol = SymbolDescriptor(symbol_id=SymbolId(1), symbol_name="EURUSD", enabled=True)
        payload = serialize_symbol_light(symbol)
        self.assertEqual(payload["symbolId"], 1)
        self.assertEqual(payload["symbolName"], "EURUSD")

    def test_tick_stream_status_serializer(self) -> None:
        status = TickStreamStatus(
            running=True, started_at=1.0, last_tick_at=2.0, uptime_seconds=1.0
        )
        payload = serialize_tick_stream_status(status)
        self.assertIn("startedAt", payload)

    def test_decimal_jsonable(self) -> None:
        self.assertEqual(to_jsonable(Decimal("1.23")), 1.23)


if __name__ == "__main__":
    unittest.main()
