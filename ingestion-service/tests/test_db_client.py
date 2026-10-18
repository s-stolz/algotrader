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

    def test_latest_candle_failures_propagate(self) -> None:
        db_client = DatabaseClient()
        db_client._client = Mock()
        db_client._client.get_latest_m1_candle.side_effect = DatabaseAccessorClientError("boom")

        for method in ("get_latest_m1_candle", "get_latest_candle"):
            with self.subTest(method=method):
                getattr(db_client._client, method).side_effect = DatabaseAccessorClientError("boom")
                arguments = ("EURUSD", "M1") if method == "get_latest_candle" else ("EURUSD",)
                with self.assertRaises(DatabaseAccessorClientError):
                    getattr(db_client, method)(*arguments)

    def test_successful_empty_latest_result_remains_none(self) -> None:
        db_client = DatabaseClient()
        self.addCleanup(db_client.close)
        db_client._client = Mock()
        db_client._client.get_latest_m1_candle.return_value = None
        self.assertIsNone(db_client.get_latest_m1_candle("EURUSD"))

    def test_historical_write_failure_propagates(self) -> None:
        db_client = DatabaseClient()
        self.addCleanup(db_client.close)
        db_client._client = Mock()
        db_client._client.write_historical_candles.side_effect = DatabaseAccessorClientError("boom")
        with self.assertRaises(DatabaseAccessorClientError):
            db_client.write_historical_candles("EURUSD", [], 60000, 119999, "FX")
        db_client._client.write_historical_candles.assert_called_once_with(
            symbol="EURUSD", candles=[], start_ms=60000, end_ms=119999, exchange="FX"
        )

    def test_write_failure_propagates(self) -> None:
        db_client = DatabaseClient()
        self.addCleanup(db_client.close)
        db_client._client = Mock()
        db_client._client.insert_candles.side_effect = DatabaseAccessorClientError("boom")
        with self.assertRaises(DatabaseAccessorClientError):
            db_client.write_candles("EURUSD", [{"timestamp_ms": 1000}])


if __name__ == "__main__":
    unittest.main()
