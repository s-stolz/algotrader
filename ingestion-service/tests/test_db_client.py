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

        with self.assertRaises(DatabaseAccessorClientError):
            db_client.get_latest_m1_candle("EURUSD")

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
            symbol="EURUSD",
            candles=[],
            start_ms=60000,
            end_ms=119999,
            exchange="FX",
            market_id=None,
        )

    def test_write_failure_propagates(self) -> None:
        db_client = DatabaseClient()
        self.addCleanup(db_client.close)
        db_client._client = Mock()
        db_client._client.insert_candles.side_effect = DatabaseAccessorClientError("boom")
        with self.assertRaises(DatabaseAccessorClientError):
            db_client.write_candles("EURUSD", [{"timestamp_ms": 1000}])

    def test_bound_market_identity_is_forwarded_for_live_and_recovery_writes(self):
        client = DatabaseClient()
        self.addCleanup(client.close)
        client._client = Mock()
        client._client.insert_candles.return_value = {"added_candles": 1}
        candles = [{"timestamp_ms": 60000}]
        client.write_candles("EURUSD", candles, "FX", market_id=7)
        client.write_historical_candles("EURUSD", candles, 60000, 119999, "FX", market_id=7)
        self.assertEqual(client._client.insert_candles.call_args.kwargs["market_id"], 7)
        self.assertEqual(client._client.write_historical_candles.call_args.kwargs["market_id"], 7)

    def test_deleted_market_failure_never_falls_back_to_name_only_write(self):
        client = DatabaseClient()
        self.addCleanup(client.close)
        client._client = Mock()
        client._client.insert_candles.side_effect = DatabaseAccessorClientError(
            "Market not found", status_code=404
        )
        with self.assertRaises(DatabaseAccessorClientError):
            client.write_candles("EURUSD", [{"timestamp_ms": 60000}], "FX", market_id=7)
        self.assertEqual(client._client.insert_candles.call_count, 1)
        self.assertEqual(client._client.insert_candles.call_args.kwargs["market_id"], 7)


if __name__ == "__main__":
    unittest.main()
