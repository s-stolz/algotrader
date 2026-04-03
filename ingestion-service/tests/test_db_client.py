from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.db_client import DatabaseClient
from db_accessor_client import DatabaseAccessorClientError


class DatabaseClientTests(unittest.TestCase):
    def test_get_latest_m1_candle_uses_dedicated_client_method(self) -> None:
        db_client = DatabaseClient()
        db_client._client = Mock()
        db_client._client.get_latest_m1_candle.return_value = {"timestamp_ms": 1000}

        result = db_client.get_latest_m1_candle("EURUSD", exchange="FX")

        self.assertEqual(result, {"timestamp_ms": 1000})
        db_client._client.get_latest_m1_candle.assert_called_once_with(
            symbol="EURUSD",
            exchange="FX",
        )

    def test_get_latest_m1_candle_returns_none_on_client_error(self) -> None:
        db_client = DatabaseClient()
        db_client._client = Mock()
        db_client._client.get_latest_m1_candle.side_effect = DatabaseAccessorClientError("boom")

        result = db_client.get_latest_m1_candle("EURUSD")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
