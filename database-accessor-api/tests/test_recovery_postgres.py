"""Real accessor recovery transactions on an isolated Timescale schema."""

import asyncio
from pathlib import Path

from sqlalchemy import text
from test_historical_candles_postgres import HistoricalStorageTests


class RecoveryStorageTests(HistoricalStorageTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        response = await self.client.get("/markets/EURUSD", params={"exchange": "FX"})
        self.symbol_id = response.json()["symbol_id"]

    async def begin(self, start=60000, target=179999, account="account1"):
        response = await self.client.post(
            "/recoveries/begin",
            json={
                "symbol_id": self.symbol_id,
                "account_id": account,
                "start_ms": start,
                "target_ms": target,
                "trigger": "startup",
            },
        )
        response.raise_for_status()
        return response.json()

    async def pending(self, account="account1"):
        response = await self.client.get(
            f"/recoveries/{self.symbol_id}", params={"account_id": account}
        )
        response.raise_for_status()
        return response.json()["pending"]

    async def advance(self, pending, next_ms):
        response = await self.client.post(
            "/recoveries/advance",
            json={
                **{
                    key: pending[key]
                    for key in ("symbol_id", "account_id", "recovery_id", "revision")
                },
                "expected_start_ms": pending["next_ms"],
                "next_ms": next_ms,
            },
        )
        response.raise_for_status()
        return response.json()["updated"]

    async def test_new_revision_retains_earliest_boundary_and_rejects_stale_completion(self):
        old = await self.begin()
        newer = await self.begin(120000, 299999)
        self.assertEqual(newer["next_ms"], 60000)
        self.assertEqual(newer["target_ms"], 299999)
        self.assertGreater(newer["revision"], old["revision"])
        self.assertFalse(await self.advance(old, 180000))
        self.assertEqual(await self.pending(), newer)
        self.assertTrue(await self.advance(newer, 180000))
        self.assertFalse(await self.advance(newer, 240000))
        progress = await self.pending()
        self.assertEqual(progress["next_ms"], 180000)
        self.assertTrue(await self.advance(progress, 300000))
        self.assertIsNone(await self.pending())
        recreated = await self.begin()
        self.assertNotEqual(recreated["recovery_id"], old["recovery_id"])
        self.assertFalse(await self.advance(old, 180000))

    async def test_concurrent_merge_and_completion_never_lose_new_interruption(self):
        for _ in range(10):
            old = await self.begin()
            _, newer = await asyncio.gather(self.advance(old, 180000), self.begin(120000, 299999))
            actual = await self.pending()
            self.assertEqual(actual["recovery_id"], newer["recovery_id"])
            self.assertLessEqual(actual["next_ms"], 120000)
            self.assertEqual(actual["target_ms"], 299999)
        separate = await self.begin(180000, 299999, account="account2")
        self.assertTrue(await self.advance(separate, 300000))
        self.assertIsNotNone(await self.pending())

    async def test_forward_migration_matches_storage_and_retains_pending(self):
        migration = (
            Path(__file__).resolve().parents[2]
            / "timescaledb-init/migrations/V001__pending_recovery.sql"
        )
        async with self.engine.begin() as connection:
            await connection.execute(text("DROP TABLE pending_recoveries"))
            await connection.execute(text(migration.read_text()))
        old = await self.begin()
        # Disposing all connections models a fresh accessor process reading durable state.
        await self.engine.dispose()
        self.assertEqual(await self.pending(), old)

    async def test_empty_closed_interval_completes_without_requesting_open_candle(self):
        empty = await self.begin(180000, 179999)
        self.assertTrue(await self.advance(empty, 180000))
        self.assertIsNone(await self.pending())

    async def test_invalid_requests_do_not_mutate_pending(self):
        old = await self.begin()
        for payload in (
            {
                "symbol_id": self.symbol_id,
                "account_id": "account1",
                "start_ms": 5,
                "target_ms": 3,
                "trigger": "startup",
            },
            {
                "symbol_id": self.symbol_id,
                "account_id": "",
                "start_ms": 0,
                "target_ms": 59999,
                "trigger": "startup",
            },
        ):
            response = await self.client.post("/recoveries/begin", json=payload)
            self.assertEqual(response.status_code, 422)
        self.assertFalse(await self.advance(old, 300000))
        self.assertEqual(await self.pending(), old)
