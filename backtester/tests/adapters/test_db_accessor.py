import unittest
from unittest.mock import patch

import pandas as pd
from adapters.db_accessor import DatabaseAccessorHistoricalDataAdapter


class _FakeClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame
        self.last_kwargs: dict | None = None

    def stream_candles(self, **kwargs):
        self.last_kwargs = kwargs
        for row in self._frame.to_dict("records"):
            yield [row]

    def get_candles(self, **kwargs) -> pd.DataFrame:
        self.last_kwargs = kwargs
        return self._frame.copy()


class TestDatabaseAccessorHistoricalDataAdapter(unittest.TestCase):
    def test_empty_stream_returns_canonical_empty_frame(self) -> None:
        adapter = DatabaseAccessorHistoricalDataAdapter(client=_FakeClient(pd.DataFrame()))
        bars = adapter.fetch_bars(symbol="EURUSD", timeframe="M1", start_ms=0, end_ms=10)
        self.assertTrue(bars.empty)
        self.assertIn("timestamp_ms", bars.columns)
        self.assertIn("symbol", bars.columns)

    def test_stream_failure_does_not_return_partial_history(self) -> None:
        class BrokenClient(_FakeClient):
            def stream_candles(self, **kwargs):
                yield [{"timestamp_ms": 1}]
                raise RuntimeError("Incomplete Candle stream")

        adapter = DatabaseAccessorHistoricalDataAdapter(client=BrokenClient(pd.DataFrame()))
        with self.assertRaisesRegex(RuntimeError, "Incomplete Candle stream"):
            adapter.fetch_bars(symbol="EURUSD", timeframe="M1", start_ms=0, end_ms=10)

    def test_count_based_warmup_keeps_bulk_request(self) -> None:
        client = _FakeClient(pd.DataFrame())
        adapter = DatabaseAccessorHistoricalDataAdapter(client=client)
        adapter.fetch_bars(symbol="EURUSD", timeframe="M1", start_ms=None, end_ms=10, limit=5)
        assert client.last_kwargs is not None
        self.assertEqual(client.last_kwargs["limit"], 5)
        self.assertTrue(client.last_kwargs["include_timestamp_ms"])

    def test_datetime_index_resolution_preserves_epoch_milliseconds(self) -> None:
        for unit in ("ms", "us", "ns"):
            with self.subTest(unit=unit):
                source = pd.DataFrame(
                    {name: [1.0, 2.0] for name in ("open", "high", "low", "close", "volume")},
                    index=pd.date_range("2026-01-01", periods=2, freq="min", tz="UTC").as_unit(
                        unit
                    ),
                )
                adapter = DatabaseAccessorHistoricalDataAdapter(client=_FakeClient(source))
                bars = adapter.fetch_bars(
                    symbol="EURUSD",
                    timeframe="M1",
                    start_ms=1767225600000,
                    end_ms=1767225720000,
                    exchange="FX",
                    limit=2,
                )
                self.assertEqual(bars["timestamp_ms"].tolist(), [1767225600000, 1767225660000])

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
        self.assertNotIn("limit", client.last_kwargs)
        self.assertNotIn("include_timestamp_ms", client.last_kwargs)

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

            def stream_candles(self, **kwargs):
                self.last_kwargs = kwargs
                yield source.to_dict("records")

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
        self.assertNotIn("include_timestamp_ms", instance.last_kwargs)
        self.assertEqual(
            list(bars.columns),
            ["timestamp_ms", "symbol", "open", "high", "low", "close", "volume"],
        )
        self.assertEqual(bars["symbol"].tolist(), ["EURUSD", "EURUSD"])
        self.assertEqual(bars["timestamp_ms"].tolist(), [3000, 4000])


if __name__ == "__main__":
    unittest.main()
