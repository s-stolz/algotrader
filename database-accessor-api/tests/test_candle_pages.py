import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

for name, value in {
    "TIMESCALEDB_USER": "test",
    "TIMESCALEDB_PASSWORD": "test",
    "TIMESCALEDB_HOST": "localhost",
    "TIMESCALEDB_PORT": "5432",
    "TIMESCALEDB_DB": "test",
}.items():
    os.environ.setdefault(name, value)

import main  # noqa: E402
from app.candle_pages import forward_candles  # noqa: E402


class ForwardCandlePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_ascending_queries_use_raw_history_for_aggregate_gaps(self):
        for timeframe in [1, 5, 60]:
            with self.subTest(timeframe=timeframe):
                row = {"timestamp_ms": 300000, "close": 2}
                session = SimpleNamespace(
                    execute=AsyncMock(
                        return_value=SimpleNamespace(
                            fetchall=lambda: [SimpleNamespace(_mapping=row)]
                        )
                    )
                )
                result = await forward_candles(session, 7, timeframe, 300000, 900000, 500)
                self.assertEqual(result, [row])
                query, params = session.execute.call_args.args
                self.assertIn("LIMIT :limit", str(query))
                self.assertNotIn("DESC", str(query))
                self.assertIn("FROM candles", str(query))
                self.assertEqual(params["limit"], 500)
                self.assertEqual(params["start_ms"], 300000)

    async def test_forward_route_is_opt_in_and_validates_bounds(self):
        async def db():
            yield object()

        main.app.dependency_overrides[main.get_db] = db
        try:
            with (
                patch.object(main.market_cache, "ensure_market_cache", AsyncMock()),
                patch.object(main.market_cache, "resolve_symbol_id", return_value=7),
                patch.object(main, "forward_candles", AsyncMock(return_value=[])) as forward,
                patch.object(main.crud, "get_candles", AsyncMock(return_value=[])) as backward,
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/candles/EURUSD",
                        params={
                            "timeframe": "M5",
                            "from_start": "true",
                            "start_ms": 300000,
                            "end_ms": 900000,
                            "limit": 500,
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    forward.assert_awaited_once()
                    backward.assert_not_awaited()
                    for query in [
                        {"limit": 501},
                        {"limit": 500},
                        {"start_ms": 1, "end_ms": 1, "limit": 500},
                    ]:
                        response = await client.get(
                            "/candles/EURUSD",
                            params={"timeframe": "M5", "from_start": "true", **query},
                        )
                        self.assertEqual(response.status_code, 422)
                    await client.get("/candles/EURUSD", params={"timeframe": "M5", "limit": 500})
                    backward.assert_awaited_once()
        finally:
            main.app.dependency_overrides.pop(main.get_db, None)
