import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app import crud


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class _FakeRow:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = [_FakeRow(row) for row in rows]

    def fetchall(self) -> list[_FakeRow]:
        return self._rows


@dataclass
class _ExecuteCall:
    sql: str
    params: dict


class _FakeSession:
    def __init__(
        self,
        *,
        chunks: list[dict],
        candle_rows_by_window: dict[tuple[datetime, datetime], list[dict]],
    ) -> None:
        self.chunks = chunks
        self.candle_rows_by_window = candle_rows_by_window
        self.calls: list[_ExecuteCall] = []

    async def execute(self, statement, params=None) -> _FakeResult:
        call_params = dict(params or {})
        sql = str(statement)
        self.calls.append(_ExecuteCall(sql=sql, params=call_params))

        if "timescaledb_information.chunks" in sql:
            return _FakeResult(self.chunks)

        window = (call_params["window_start"], call_params["window_end"])
        rows = self.candle_rows_by_window.get(window, [])
        return _FakeResult(rows[: call_params["limit"]])

    def candle_calls(self) -> list[_ExecuteCall]:
        return [call for call in self.calls if "timescaledb_information.chunks" not in call.sql]


class M1LimitCandleQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_limit_read_walks_recent_chunk_windows_until_limit(self) -> None:
        first_window = (_dt(15), _dt(17))
        second_window = (_dt(13), _dt(15))
        session = _FakeSession(
            chunks=[
                {"range_start": _dt(16), "range_end": _dt(17)},
                {"range_start": _dt(15), "range_end": _dt(16)},
                {"range_start": _dt(14), "range_end": _dt(15)},
                {"range_start": _dt(13), "range_end": _dt(14)},
            ],
            candle_rows_by_window={
                first_window: [
                    {
                        "timestamp_ms": _ms(_dt(16, 12)),
                        "open": 1.6,
                        "high": 1.7,
                        "low": 1.5,
                        "close": 1.65,
                        "volume": 160,
                    }
                ],
                second_window: [
                    {
                        "timestamp_ms": _ms(_dt(14, 12)),
                        "open": 1.4,
                        "high": 1.5,
                        "low": 1.3,
                        "close": 1.45,
                        "volume": 140,
                    },
                    {
                        "timestamp_ms": _ms(_dt(13, 12)),
                        "open": 1.3,
                        "high": 1.4,
                        "low": 1.2,
                        "close": 1.35,
                        "volume": 130,
                    },
                ],
            },
        )

        candles = await crud._get_m1_candles(
            session,
            symbol_id=40,
            start_ms=None,
            end_ms=None,
            limit=3,
        )

        self.assertEqual(
            [candle["timestamp_ms"] for candle in candles],
            [_ms(_dt(13, 12)), _ms(_dt(14, 12)), _ms(_dt(16, 12))],
        )
        candle_calls = session.candle_calls()
        self.assertEqual(len(candle_calls), 2)
        self.assertEqual(candle_calls[0].params["window_start"], _dt(15))
        self.assertEqual(candle_calls[0].params["window_end"], _dt(17))
        self.assertEqual(candle_calls[0].params["limit"], 3)
        self.assertEqual(candle_calls[1].params["window_start"], _dt(13))
        self.assertEqual(candle_calls[1].params["window_end"], _dt(15))
        self.assertEqual(candle_calls[1].params["limit"], 2)

    async def test_limit_read_preserves_start_and_end_filters(self) -> None:
        start_ms = _ms(_dt(15, 12))
        end_ms = _ms(_dt(16, 12))
        session = _FakeSession(
            chunks=[
                {"range_start": _dt(16), "range_end": _dt(17)},
                {"range_start": _dt(15), "range_end": _dt(16)},
            ],
            candle_rows_by_window={
                (_dt(15), _dt(17)): [
                    {
                        "timestamp_ms": _ms(_dt(16, 10)),
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.05,
                        "volume": 100,
                    }
                ],
            },
        )

        candles = await crud._get_m1_candles(
            session,
            symbol_id=40,
            start_ms=start_ms,
            end_ms=end_ms,
            limit=2,
        )

        self.assertEqual(len(candles), 1)
        chunk_call = session.calls[0]
        self.assertIn(
            "range_end::timestamptz > to_timestamp(:start_ms / 1000.0)",
            chunk_call.sql,
        )
        self.assertIn(
            "range_start::timestamptz < to_timestamp(:end_ms / 1000.0)",
            chunk_call.sql,
        )
        self.assertIn("range_start::timestamptz AS range_start", chunk_call.sql)
        self.assertIn("range_end::timestamptz AS range_end", chunk_call.sql)
        self.assertIn("ORDER BY range_end::timestamptz DESC", chunk_call.sql)
        self.assertEqual(chunk_call.params["start_ms"], start_ms)
        self.assertEqual(chunk_call.params["end_ms"], end_ms)

        candle_call = session.candle_calls()[0]
        self.assertIn("timestamp_utc >= :window_start", candle_call.sql)
        self.assertIn("timestamp_utc < :window_end", candle_call.sql)
        self.assertIn(
            "timestamp_utc >= to_timestamp(:start_ms / 1000.0)",
            candle_call.sql,
        )
        self.assertIn(
            "timestamp_utc < to_timestamp(:end_ms / 1000.0)",
            candle_call.sql,
        )
        self.assertEqual(candle_call.params["start_ms"], start_ms)
        self.assertEqual(candle_call.params["end_ms"], end_ms)

    async def test_limit_read_returns_empty_when_no_chunks_match(self) -> None:
        session = _FakeSession(chunks=[], candle_rows_by_window={})

        candles = await crud._get_m1_candles(
            session,
            symbol_id=40,
            start_ms=None,
            end_ms=None,
            limit=500,
        )

        self.assertEqual(candles, [])
        self.assertEqual(session.candle_calls(), [])

    async def test_latest_m1_candle_uses_chunk_window_limit_path(self) -> None:
        session = _FakeSession(
            chunks=[
                {"range_start": _dt(16), "range_end": _dt(17)},
                {"range_start": _dt(15), "range_end": _dt(16)},
            ],
            candle_rows_by_window={
                (_dt(15), _dt(17)): [
                    {
                        "timestamp_ms": _ms(_dt(16, 12)),
                        "open": 1.6,
                        "high": 1.7,
                        "low": 1.5,
                        "close": 1.65,
                        "volume": 160,
                    }
                ],
            },
        )

        candle = await crud.get_latest_m1_candle(session, symbol_id=40)

        if candle is None:
            self.fail("Expected latest candle, got None")
        self.assertEqual(candle["timestamp_ms"], _ms(_dt(16, 12)))
        candle_calls = session.candle_calls()
        self.assertEqual(len(candle_calls), 1)
        self.assertEqual(candle_calls[0].params["limit"], 1)
        self.assertIn("timestamp_utc >= :window_start", candle_calls[0].sql)
        self.assertIn("timestamp_utc < :window_end", candle_calls[0].sql)


if __name__ == "__main__":
    unittest.main()
