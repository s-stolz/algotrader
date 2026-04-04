"""Main entry point for the ingestion service."""

import asyncio
import signal
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.broker_client import BrokerClient
from app.config import load_config
from app.db_client import DatabaseClient
from app.logger import setup_logging
from app.stream_consumer import StreamConsumer
from redis.asyncio import Redis


@dataclass
class SymbolRuntimeState:
    """Runtime state for a single symbol stream."""

    symbol_id: int
    symbol: str
    exchange: str
    stream_key: str
    recovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class IngestionService:
    """Orchestrates data ingestion from Redis streams to database."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_CODE_M1 = "M1"
    CHUNK_SIZE = 10000
    MAX_BACKFILL_DAYS = 365 * 5
    REDIS_STREAM_START = "0-0"

    @staticmethod
    def _format_candle_for_db(candle: Dict[str, Any]) -> Dict[str, Any]:
        """Transform broker candle format to database format."""
        return {
            "timestamp_ms": int(candle["t"]),
            "open": candle["o"],
            "high": candle["h"],
            "low": candle["l"],
            "close": candle["c"],
            "volume": candle["v"],
        }

    @staticmethod
    def _utc_now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    @staticmethod
    def _ms_to_iso(value: int) -> str:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()

    @staticmethod
    def _decode_redis_id(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    def __init__(self):
        """Initialize the ingestion service."""
        self.config = load_config()
        self.logger = setup_logging(self.config.log_level, self.config.log_format)

        self.db_client = DatabaseClient()
        self.broker_client = BrokerClient(
            self.config.broker_service_base_url,
            self.config.broker_account_id,
        )
        self.redis: Redis | None = None
        self.consumer: StreamConsumer | None = None

        self.markets: List[Dict[str, Any]] = []
        self.runtime_states: List[SymbolRuntimeState] = []
        self._state_by_id: Dict[int, SymbolRuntimeState] = {}
        self.consumer_tasks: List[asyncio.Task] = []
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None

        self._shutdown = False
        self._is_shutting_down = False
        self._broker_connected: Optional[bool] = None

    async def startup(self) -> None:
        """Initialize connections and load configuration."""
        self.logger.info("Starting ingestion service...")

        self.redis = Redis.from_url(
            self.config.redis_url,
            decode_responses=False,
        )
        await self.redis.ping()
        self.logger.info(f"Connected to Redis at {self.config.redis_url}")

        self.consumer = StreamConsumer(
            redis=self.redis,
            account_id=self.config.broker_account_id,
            batch_size=self.config.consumer_batch_size,
            block_ms=self.config.consumer_block_ms,
        )

        self.markets = self.db_client.get_markets()
        if not self.markets:
            self.logger.warning(
                "No markets found in database. Waiting for markets to be created..."
            )
            return

        self.runtime_states = [
            SymbolRuntimeState(
                symbol_id=market["symbol_id"],
                symbol=market["symbol"],
                exchange=market.get("exchange", ""),
                stream_key=self.consumer.get_stream_key(market["symbol"], self.TIMEFRAME_CODE_M1),
            )
            for market in self.markets
        ]
        self._state_by_id = {state.symbol_id: state for state in self.runtime_states}
        self.logger.info(
            f"Loaded {len(self.markets)} markets: {[m['symbol'] for m in self.markets]}"
        )

    def _needs_backfill(self, latest_ts_ms: int, timeframe_minutes: int) -> bool:
        expected_gap_ms = int(timedelta(minutes=timeframe_minutes * 2).total_seconds() * 1000)
        return (self._utc_now_ms() - latest_ts_ms) > expected_gap_ms

    def _get_frozen_watermark(self, symbol: str, exchange: str) -> int:
        latest_candle = self.db_client.get_latest_m1_candle(
            symbol, exchange=exchange or None
        )
        if not latest_candle:
            fallback = self._utc_now_ms() - int(
                timedelta(days=self.MAX_BACKFILL_DAYS).total_seconds() * 1000
            )
            self.logger.info(
                f"{symbol} M1: No data in database, using fallback watermark {self._ms_to_iso(fallback)}"
            )
            return fallback

        latest_ts = int(latest_candle["timestamp_ms"])
        self.logger.info(f"{symbol} M1: Frozen startup watermark at {self._ms_to_iso(latest_ts)}")
        return latest_ts

    async def _snapshot_startup_watermarks(self) -> Dict[int, int]:
        if not self.runtime_states:
            return {}

        concurrency = max(1, self.config.startup_watermark_concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(state: SymbolRuntimeState) -> tuple[int, int]:
            async with semaphore:
                watermark = await asyncio.to_thread(
                    self._get_frozen_watermark,
                    state.symbol,
                    state.exchange,
                )
                return state.symbol_id, watermark

        pairs = await asyncio.gather(*(worker(state) for state in self.runtime_states))
        return {symbol_id: watermark for symbol_id, watermark in pairs}

    async def _backfill_symbol(
        self,
        symbol_id: int,
        symbol: str,
        from_ts: int,
        to_ts: int,
        timeframe: Optional[str] = None,
    ) -> None:
        if timeframe is None:
            timeframe = self.TIMEFRAME_CODE_M1

        self.logger.info(
            f"Backfilling {symbol} {timeframe} from {self._ms_to_iso(from_ts)} to {self._ms_to_iso(to_ts)}"
        )

        candles: List[Dict[str, Any]] = []
        async for candle in self.broker_client.stream_trendbars(
            symbol,
            timeframe=timeframe,
            start_time=from_ts,
            end_time=to_ts,
        ):
            candles.append(candle)

        if candles:
            await self.write_candles_callback(symbol_id, candles)
            self.logger.info(f"Backfilled {len(candles)} candles for {symbol} {timeframe}")
        else:
            self.logger.debug(f"No backfill data available for {symbol} {timeframe}")

    async def _run_startup_backfill(self, watermarks: Dict[int, int]) -> None:
        if not self.runtime_states:
            return

        self.logger.info("Starting startup backfill phase")
        concurrency = max(1, self.config.startup_backfill_concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(state: SymbolRuntimeState) -> None:
            from_ts_ms = watermarks[state.symbol_id]
            if not self._needs_backfill(from_ts_ms, self.TIMEFRAME_M1):
                self.logger.info(f"{state.symbol} M1: Backfill skipped, data is up to date")
                return

            async with semaphore:
                await self._backfill_symbol(
                    symbol_id=state.symbol_id,
                    symbol=state.symbol,
                    from_ts=from_ts_ms,
                    to_ts=self._utc_now_ms(),
                )

        await asyncio.gather(*(worker(state) for state in self.runtime_states))
        self.logger.info("Startup backfill phase complete")

    async def _write_candles_in_chunks(
        self,
        symbol: str,
        exchange: str | None,
        candles: List[Dict[str, Any]],
        chunk_size: Optional[int] = None,
    ) -> None:
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE

        total_chunks = (len(candles) + chunk_size - 1) // chunk_size
        for i in range(0, len(candles), chunk_size):
            chunk = candles[i : i + chunk_size]
            chunk_num = i // chunk_size + 1

            await asyncio.to_thread(
                self.db_client.write_candles,
                symbol,
                chunk,
                exchange or None,
            )
            self.logger.info(
                f"Wrote {len(chunk)} candles for {symbol} "
                f"(chunk {chunk_num}/{total_chunks})"
            )

    async def write_candles_callback(self, symbol_id: int, candles: List[Dict[str, Any]]) -> None:
        """Callback to write candles to database."""
        if not candles:
            return

        mapped_candles = [self._format_candle_for_db(candle) for candle in candles]
        state = self._state_by_id.get(symbol_id)
        if state is None:
            self.logger.warning("Skipping candles for unknown symbol_id=%s", symbol_id)
            return
        await self._write_candles_in_chunks(state.symbol, state.exchange, mapped_candles)

    async def _get_stream_tail_id(self, stream_key: str) -> str:
        """Get current tail ID of a stream; returns 0-0 if stream is empty."""
        if self.redis is None:
            raise RuntimeError("Redis client not initialized")

        entries = await self.redis.xrevrange(stream_key, count=1)
        if not entries:
            return self.REDIS_STREAM_START

        message_id = entries[0][0]
        return self._decode_redis_id(message_id)

    async def _startup_backfill_for_state(
        self,
        state: SymbolRuntimeState,
        watermarks: Dict[int, int],
        semaphore: asyncio.Semaphore,
    ) -> None:
        from_ts_ms = watermarks[state.symbol_id]
        if not self._needs_backfill(from_ts_ms, self.TIMEFRAME_M1):
            self.logger.info(f"{state.symbol} M1: Backfill skipped, data is up to date")
            return

        async with semaphore:
            await self._backfill_symbol(
                symbol_id=state.symbol_id,
                symbol=state.symbol,
                from_ts=from_ts_ms,
                to_ts=self._utc_now_ms(),
            )

    async def start_consumers(self, startup_watermarks: Optional[Dict[int, int]] = None) -> None:
        """Start stream consumers and optionally run startup backfill per symbol immediately."""
        if self.consumer is None:
            raise RuntimeError("Consumer is not initialized")

        self.logger.info("Starting stream consumers...")
        if startup_watermarks is not None:
            self.logger.info("Starting startup backfill phase")

        concurrency = max(1, self.config.startup_stream_start_concurrency)
        semaphore = asyncio.Semaphore(concurrency)
        backfill_tasks: list[asyncio.Task] = []
        backfill_semaphore = asyncio.Semaphore(max(1, self.config.startup_backfill_concurrency))

        async def worker(state: SymbolRuntimeState) -> asyncio.Task:
            async with semaphore:
                tail_id = await self._get_stream_tail_id(state.stream_key)

                await self.broker_client.start_trendbar_stream(
                    state.symbol,
                    timeframe=self.TIMEFRAME_CODE_M1,
                )

                task = asyncio.create_task(
                    self.consumer.consume_stream(
                        stream_key=state.stream_key,
                        symbol_id=state.symbol_id,
                        callback=self.write_candles_callback,
                        start_id=tail_id,
                    )
                )
                self.logger.info(f"Started consumer for {state.stream_key} from ID {tail_id}")

                if startup_watermarks is not None:
                    backfill_tasks.append(
                        asyncio.create_task(
                            self._startup_backfill_for_state(
                                state=state,
                                watermarks=startup_watermarks,
                                semaphore=backfill_semaphore,
                            )
                        )
                    )
                return task

        tasks = await asyncio.gather(*(worker(state) for state in self.runtime_states))
        self.consumer_tasks.extend(tasks)

        self.logger.info(f"Started {len(tasks)} stream consumers")

        if backfill_tasks:
            await asyncio.gather(*backfill_tasks)
            self.logger.info("Startup backfill phase complete")

    async def _is_broker_connected(self) -> bool:
        """Broker is considered connected only when broker-service is up and cTrader is authenticated."""
        try:
            health = await self.broker_client.get_meta_health()
            ctrader = health.get("components", {}).get("ctrader", {})
            return ctrader.get("status") == "up"
        except Exception:
            return False

    async def _recover_symbol_after_reconnect(self, state: SymbolRuntimeState) -> None:
        async with state.recovery_lock:
            backoff = max(1, self.config.recovery_backoff_initial_seconds)
            max_backoff = max(backoff, self.config.recovery_backoff_max_seconds)

            while not self._shutdown:
                if not await self._is_broker_connected():
                    self.logger.warning(
                        f"Skipping recovery for {state.symbol}: broker/cTrader not connected"
                    )
                    return

                try:
                    from_ts = self._get_frozen_watermark(state.symbol, state.exchange)
                    await self.broker_client.start_trendbar_stream(
                        state.symbol,
                        timeframe=self.TIMEFRAME_CODE_M1,
                    )
                    await self._backfill_symbol(
                        symbol_id=state.symbol_id,
                        symbol=state.symbol,
                        from_ts=from_ts,
                        to_ts=self._utc_now_ms(),
                    )
                    self.logger.info(f"Recovery complete for {state.symbol}")
                    return
                except Exception as exc:
                    self.logger.error(
                        f"Recovery failed for {state.symbol}: {exc}. Retrying in {backoff}s",
                        exc_info=True,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(max_backoff, backoff * 2)

    async def _run_recovery(self) -> None:
        if not self.runtime_states:
            return

        self.logger.info("Broker reconnect detected, running recovery backfill")
        concurrency = max(1, self.config.startup_backfill_concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(state: SymbolRuntimeState) -> None:
            async with semaphore:
                await self._recover_symbol_after_reconnect(state)

        await asyncio.gather(
            *(worker(state) for state in self.runtime_states), return_exceptions=False
        )
        self.logger.info("Reconnect recovery finished")

    def _trigger_recovery(self) -> None:
        if self._recovery_task and not self._recovery_task.done():
            self.logger.info("Recovery already running, skipping duplicate trigger")
            return
        self._recovery_task = asyncio.create_task(self._run_recovery())

    async def _monitor_broker_connectivity(self) -> None:
        """Monitor broker/cTrader connectivity and trigger recovery on reconnect transitions."""
        poll_seconds = max(1, self.config.broker_health_poll_seconds)
        while not self._shutdown:
            connected = await self._is_broker_connected()

            if self._broker_connected is None:
                self._broker_connected = connected
                self.logger.info(f"Initial broker connectivity state: connected={connected}")
            elif connected and not self._broker_connected:
                self.logger.warning("Broker connection restored, triggering recovery")
                self._broker_connected = connected
                self._trigger_recovery()
            elif not connected and self._broker_connected:
                self.logger.warning("Broker/cTrader connection lost")
                self._broker_connected = connected
            else:
                self._broker_connected = connected

            await asyncio.sleep(poll_seconds)

    async def shutdown(self) -> None:
        """Gracefully shutdown the service."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        self.logger.info("Shutting down ingestion service...")
        self._shutdown = True

        if self.consumer:
            self.consumer.stop()

        if self._health_monitor_task:
            self._health_monitor_task.cancel()

        if self._recovery_task:
            self._recovery_task.cancel()

        for task in self.consumer_tasks:
            task.cancel()

        await asyncio.gather(*self.consumer_tasks, return_exceptions=True)

        if self._health_monitor_task:
            await asyncio.gather(self._health_monitor_task, return_exceptions=True)

        if self._recovery_task:
            await asyncio.gather(self._recovery_task, return_exceptions=True)

        if self.redis:
            await self.redis.close()
            self.logger.info("Closed Redis connection")

        await self.broker_client.aclose()
        self.logger.info("Closed broker client")

        self.db_client.close()
        self.logger.info("Closed database client")

        self.logger.info("Ingestion service stopped")

    async def run(self) -> None:
        """Main run loop."""
        try:
            await self.startup()

            if self.runtime_states:
                startup_watermarks = await self._snapshot_startup_watermarks()
                await self.start_consumers(startup_watermarks=startup_watermarks)

            self._health_monitor_task = asyncio.create_task(self._monitor_broker_connectivity())

            while not self._shutdown:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Fatal error in run loop: {e}", exc_info=True)
        finally:
            await self.shutdown()


async def main():
    """Main entry point."""
    service = IngestionService()

    loop = asyncio.get_event_loop()

    def handle_shutdown(sig):
        service.logger.info(f"Received signal {sig}")
        asyncio.create_task(service.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))

    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
