import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from app import market_cache
from app.database import get_db
from app.models import candles, market_aliases, markets
from main import app
from sqlalchemy import create_engine, insert, select


class MarketEditingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for table in (markets, market_aliases, candles):
            table.create(self.engine)
        self.connection = self.engine.connect()
        self.session = Session(self.connection)

        @asynccontextmanager
        async def sessions():
            yield self.session

        self.sessions = sessions

        async def database():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = database
        market_cache._rebuild_cache([])
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.spec = dict(
            symbol="EURUSD",
            exchange="IC TRADING",
            market_type="Forex",
            min_move=0.00001,
            timezone="UTC",
            settlement_currency="USD",
            contract_multiplier=1,
            minimum_quantity=1000,
            quantity_step=1000,
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        market_cache._rebuild_cache([])
        self.connection.close()
        self.engine.dispose()

    async def test_edit_keeps_identity_candles_and_historical_alias(self):
        created = await self.client.post("/markets", json=self.spec)
        self.assertEqual(created.status_code, 200, created.text)
        identity = created.json()["symbol_id"]
        async with self.sessions() as session:
            await session.execute(
                insert(candles).values(
                    symbol_id=identity,
                    timestamp_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    open=1,
                    high=2,
                    low=1,
                    close=2,
                    volume=3,
                )
            )
            await session.commit()
        edited = await self.client.put(
            f"/markets/id/{identity}", json={**self.spec, "symbol": "EURUSDNEW", "min_move": 0.001}
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        async with self.sessions() as session:
            row = (await session.execute(select(candles))).mappings().one()
            self.assertEqual(row["symbol_id"], identity)
            self.assertEqual(row["close"], 2)
            alias = await session.scalar(
                select(market_aliases.c.symbol_id).where(market_aliases.c.symbol == "EURUSD")
            )
            self.assertEqual(alias, identity)
        duplicate = await self.client.post("/markets", json=self.spec)
        self.assertEqual(duplicate.status_code, 409)

    async def test_missing_specs_and_invalid_values_are_rejected(self):
        for key in (
            "settlement_currency",
            "contract_multiplier",
            "minimum_quantity",
            "quantity_step",
        ):
            value = dict(self.spec)
            value.pop(key)
            response = await self.client.post("/markets", json=value)
            self.assertEqual(response.status_code, 422)
        response = await self.client.post("/markets", json={**self.spec, "quantity_step": 0})
        self.assertEqual(response.status_code, 422)


class Session:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement):
        return self.connection.execute(statement)

    async def scalar(self, statement):
        return self.connection.scalar(statement)

    async def commit(self):
        self.connection.commit()

    async def rollback(self):
        self.connection.rollback()
