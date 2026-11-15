import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
from app.market_sources import MarketSourceConflictError, verify_broker_market
from app.models import candles
from sqlalchemy import insert
from test_market_editing import MarketEditingTests

BINDING = {
    "source_type": "broker",
    "broker_provider": "ctrader",
    "broker_account_id": "account1",
    "broker_environment": "demo",
    "broker_symbol_id": 17,
}


class MarketSourceTests(MarketEditingTests):
    async def create_broker(self):
        with patch("main.verify_broker_market", new=AsyncMock()):
            response = await self.client.post("/markets", json={**self.spec, **BINDING})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["symbol_id"]

    async def test_custom_is_default_and_source_cannot_be_changed(self):
        response = await self.client.post("/markets", json=self.spec)
        identity = response.json()["symbol_id"]
        market = (await self.client.get(f"/markets/id/{identity}")).json()
        self.assertEqual(market["source_type"], "custom")
        self.assertIsNone(market["live_start_ms"])
        response = await self.client.put(f"/markets/id/{identity}", json={**self.spec, **BINDING})
        self.assertEqual(response.status_code, 409, response.text)

    async def test_broker_binding_and_names_are_immutable_but_specs_editable(self):
        identity = await self.create_broker()
        market = (await self.client.get(f"/markets/id/{identity}")).json()
        self.assertEqual(market["live_start_ms"] % 60000, 0)
        self.assertGreater(market["live_start_ms"], 0)
        for changes in (
            {"symbol": "GBPUSD"},
            {"exchange": "OTHER"},
            {"broker_symbol_id": 18},
            {"broker_account_id": "another"},
            {"broker_environment": "live"},
        ):
            response = await self.client.put(
                f"/markets/id/{identity}", json={**self.spec, **BINDING, **changes}
            )
            self.assertEqual(response.status_code, 409, response.text)
        response = await self.client.put(
            f"/markets/id/{identity}", json={**self.spec, **BINDING, "min_move": 0.001}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            (await self.client.get(f"/markets/id/{identity}")).json()["live_start_ms"],
            market["live_start_ms"],
        )

    async def test_incomplete_and_mixed_bindings_are_rejected(self):
        for source in (
            {"source_type": "broker"},
            {"broker_symbol_id": 1},
            {**BINDING, "source_type": "custom"},
            {**BINDING, "broker_symbol_id": 0},
            {**BINDING, "live_start_ms": 0},
        ):
            response = await self.client.post("/markets", json={**self.spec, **source})
            self.assertEqual(response.status_code, 422, response.text)

    async def test_upload_boundary_rejects_broker_without_writing(self):
        await self.create_broker()
        with patch("app.crud.insert_candles", new=AsyncMock()) as write:
            response = await self.client.post(
                "/candles/upload", json={"symbol": "EURUSD", "candles": []}
            )
            self.assertEqual(response.status_code, 409, response.text)
            write.assert_not_awaited()

    async def test_empty_and_populated_coverage_uses_raw_m1_boundaries(self):
        response = await self.client.post("/markets", json=self.spec)
        identity = response.json()["symbol_id"]
        path = f"/markets/id/{identity}/coverage"
        self.assertEqual(
            (await self.client.get(path)).json(),
            dict(
                market_id=identity,
                oldest_timestamp_ms=None,
                latest_timestamp_ms=None,
                candle_count=0,
            ),
        )
        for minute in (1, 4):
            self.connection.execute(
                insert(candles).values(
                    symbol_id=identity,
                    timestamp_utc=datetime.fromtimestamp(minute * 60, timezone.utc),
                    open=1,
                    high=2,
                    low=1,
                    close=2,
                    volume=3,
                )
            )
        self.connection.commit()
        self.assertEqual(
            (await self.client.get(path)).json(),
            dict(
                market_id=identity,
                oldest_timestamp_ms=60000,
                latest_timestamp_ms=240000,
                candle_count=2,
            ),
        )
        self.assertEqual((await self.client.get("/markets/id/999/coverage")).status_code, 404)

    async def test_verification_rejects_forged_instrument_and_wrong_connection(self):
        payload = {**self.spec, **BINDING}
        with patch.dict(os.environ, {"ACCOUNT_ID": "account1", "CTRADER_HOST_TYPE": "demo"}):
            with self.assertRaises(MarketSourceConflictError):
                await verify_broker_market({**payload, "broker_account_id": "other"})
            client = httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json={**payload, "broker_symbol_id": 999})
                )
            )
            with patch("app.market_sources.httpx.AsyncClient", return_value=client):
                with self.assertRaises(MarketSourceConflictError):
                    await verify_broker_market(payload)
