import unittest
from unittest.mock import patch

import pandas as pd
from adapters.db_accessor import DatabaseAccessorHistoricalDataAdapter


class _FakeClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame
        self.last_kwargs: dict | None = None

    def get_candles(self, **kwargs) -> pd.DataFrame:
        self.last_kwargs = kwargs
        return self._frame.copy()


class TestDatabaseAccessorHistoricalDataAdapter(unittest.TestCase):
    def test_fetch_bars_maps_request_and_response_shape(self) -> None:
        source = pd.DataFrame(
            {
                "timestamp_ms": [1000, 2000],
                "open": [1.1, 1.2],
                "high": [1.2, 1.3],
                "low": [1.0, 1.1],
                "close": [1.15, 1.25],
                "volume": [100.0, 120.0],
            }
        )
        client = _FakeClient(source)
        adapter = DatabaseAccessorHistoricalDataAdapter(client=client)

        bars = adapter.fetch_bars(
            symbol="EURUSD",
            timeframe="M15",
            start_ms=1_000_000,
            end_ms=2_000_000,
            exchange="FX",
        )

        self.assertIsNotNone(client.last_kwargs)
        assert client.last_kwargs is not None
        self.assertEqual(client.last_kwargs["symbol"], "EURUSD")
        self.assertEqual(client.last_kwargs["timeframe"], "M15")
        self.assertEqual(client.last_kwargs["start_ms"], 1_000_000)
        self.assertEqual(client.last_kwargs["end_ms"], 2_000_000)
        self.assertEqual(client.last_kwargs["exchange"], "FX")
        self.assertTrue(client.last_kwargs["include_timestamp_ms"])

        self.assertEqual(
            list(bars.columns),
            ["timestamp_ms", "symbol", "open", "high", "low", "close", "volume"],
        )
        self.assertEqual(bars["symbol"].tolist(), ["EURUSD", "EURUSD"])
        self.assertEqual(bars["timestamp_ms"].tolist(), [1000, 2000])

    def test_fetch_bars_uses_default_client_import_path(self) -> None:
        source = pd.DataFrame(
            {
                "timestamp_ms": [3000, 4000],
                "open": [1.3, 1.4],
                "high": [1.4, 1.5],
                "low": [1.2, 1.3],
                "close": [1.35, 1.45],
                "volume": [130.0, 140.0],
            }
        )

        class _FakeDatabaseAccessorClient:
            instances: list["_FakeDatabaseAccessorClient"] = []

            def __init__(self) -> None:
                self.last_kwargs: dict | None = None
                self.__class__.instances.append(self)

            def __enter__(self) -> "_FakeDatabaseAccessorClient":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                _ = (exc_type, exc, tb)

            def get_candles(self, **kwargs) -> pd.DataFrame:
                self.last_kwargs = kwargs
                return source.copy()

        with patch(
            "adapters.db_accessor._import_database_accessor_client",
            return_value=_FakeDatabaseAccessorClient,
        ):
            adapter = DatabaseAccessorHistoricalDataAdapter()
            bars = adapter.fetch_bars(
                symbol="EURUSD",
                timeframe="M15",
                start_ms=3_000_000,
                end_ms=4_000_000,
                exchange="FX",
            )

        self.assertEqual(len(_FakeDatabaseAccessorClient.instances), 1)
        instance = _FakeDatabaseAccessorClient.instances[0]
        self.assertIsNotNone(instance.last_kwargs)
        assert instance.last_kwargs is not None
        self.assertEqual(instance.last_kwargs["symbol"], "EURUSD")
        self.assertEqual(instance.last_kwargs["timeframe"], "M15")
        self.assertEqual(instance.last_kwargs["start_ms"], 3_000_000)
        self.assertEqual(instance.last_kwargs["end_ms"], 4_000_000)
        self.assertEqual(instance.last_kwargs["exchange"], "FX")
        self.assertTrue(instance.last_kwargs["include_timestamp_ms"])
        self.assertEqual(
            list(bars.columns),
            ["timestamp_ms", "symbol", "open", "high", "low", "close", "volume"],
        )
        self.assertEqual(bars["symbol"].tolist(), ["EURUSD", "EURUSD"])
        self.assertEqual(bars["timestamp_ms"].tolist(), [3000, 4000])


if __name__ == "__main__":
    unittest.main()
