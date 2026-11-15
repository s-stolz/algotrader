import unittest
from unittest.mock import AsyncMock, patch

import httpx
from app import market_cache
from app.database import get_db
from app.models import markets
from main import app
from sqlalchemy import create_engine, delete, insert
from test_market_editing import Session

SPEC = dict(
    symbol="EURUSD",
    exchange="CSV",
    market_type="Forex",
    min_move=0.00001,
    timezone="UTC",
    settlement_currency="USD",
    contract_multiplier=1,
    minimum_quantity=1,
    quantity_step=1,
)


class CandleWriteIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        markets.create(self.engine)
        self.connection = self.engine.connect()
        self.session = Session(self.connection)
        self.connection.execute(insert(markets).values(symbol_id=1, **SPEC))
        self.connection.commit()

        async def database():
            yield self.session

        app.dependency_overrides[get_db] = database
        market_cache._rebuild_cache([])
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        market_cache._rebuild_cache([])
        self.connection.close()
        self.engine.dispose()

    async def test_explicit_id_rejects_recreated_name_and_mismatched_identity(self):
        self.connection.execute(delete(markets).where(markets.c.symbol_id == 1))
        self.connection.execute(insert(markets).values(symbol_id=2, **SPEC))
        self.connection.commit()
        for path, extra in (
            ("/candles", {}),
            ("/candles/historical", {"start_ms": 0, "end_ms": 59999}),
        ):
            with self.subTest(path=path):
                for identity, symbol, expected in ((1, "EURUSD", 404), (2, "GBPUSD", 409)):
                    response = await self.client.post(
                        path,
                        json=dict(
                            market_id=identity,
                            symbol=symbol,
                            exchange="CSV",
                            candles=[],
                            **extra,
                        ),
                    )
                    self.assertEqual(response.status_code, expected, response.text)

    async def test_upload_binds_the_source_checked_id_instead_of_resolving_again(self):
        self.connection.execute(delete(markets).where(markets.c.symbol_id == 1))
        self.connection.execute(insert(markets).values(symbol_id=2, **SPEC))
        self.connection.commit()
        stale_custom = {**SPEC, "symbol_id": 1, "source_type": "custom"}
        with patch("main.crud.get_markets", new=AsyncMock(return_value=[stale_custom])):
            response = await self.client.post(
                "/candles/upload",
                json=dict(
                    symbol="EURUSD",
                    exchange="CSV",
                    candles=[],
                ),
            )
        self.assertEqual(response.status_code, 404, response.text)
