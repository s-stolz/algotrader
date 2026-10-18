"""Main entry point for the ingestion service."""

import asyncio
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Dict, List, Optional, cast

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
    protection_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    live_ready: asyncio.Event = field(default_factory=asyncio.Event)
    recovery_requested: asyncio.Event = field(default_factory=asyncio.Event)
    handoff_start_ms: int | None = None
    continuity: str | None = None
    live_boundary_ms: int | None = None


class IngestionService:
    """Orchestrates data ingestion from Redis streams to database."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_CODE_M1 = "M1"
    CHUNK_SIZE: int = 10000
    MAX_BACKFILL_DAYS = 365 * 5
    REDIS_STREAM_START = "0-0"
    HISTORY_WINDOW_MS = 24 * 60 * 60000

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

    @staticmethod
    def _redis_socket_timeout_seconds(block_ms: int) -> float | None:
        if block_ms <= 0:
            return None
        return (block_ms / 1000.0) + 1.0

    def __init__(self):
        """Initialize the ingestion service."""
        self.config = load_config()
        self._history_start_ms = self.config.history_start_ms(self._utc_now_ms())
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
        self._broker_instance_id: str | None = None
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None

        self._owned_tasks: set[asyncio.Task] = set()
        self._history_semaphore = asyncio.Semaphore(
            max(1, self.config.startup_backfill_concurrency)
        )
        self._boundary_semaphore = asyncio.Semaphore(
            max(1, self.config.startup_watermark_concurrency)
        )
        self._stream_semaphore = asyncio.Semaphore(
            max(1, self.config.startup_stream_start_concurrency)
        )
        self._shutdown = False
        self._is_shutting_down = False
        self._shutdown_complete = asyncio.Event()
        self._broker_connected: Optional[bool] = None

    async def startup(self) -> None:
        """Initialize connections and load configuration."""
        self.logger.info("Starting ingestion service...")
        self.logger.info(f"History download boundary: {self._ms_to_iso(self._history_start_ms)}")

        self.redis = Redis.from_url(
            self.config.redis_url,
            decode_responses=False,
            socket_timeout=self._redis_socket_timeout_seconds(self.config.consumer_block_ms),
        )
        self.markets = await self._own_task(self._load_markets())
        self.logger.info("Connected to Redis and loaded Market sources")

        self.consumer = StreamConsumer(
            redis=self.redis,
            account_id=self.config.broker_account_id,
            batch_size=self.config.consumer_batch_size,
            block_ms=self.config.consumer_block_ms,
            backoff_initial_seconds=self.config.recovery_backoff_initial_seconds,
            backoff_max_seconds=self.config.recovery_backoff_max_seconds,
        )

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

    async def _load_markets(self) -> List[Dict[str, Any]]:
        """Retry dependency initialization before any Market can admit live writes."""
        backoff = max(1, self.config.recovery_backoff_initial_seconds)
        while not self._shutdown:
            try:
                assert self.redis is not None
                await cast(Awaitable[bool], self.redis.ping())
                return await self._db_call(self.db_client.get_markets)
            except Exception:
                self.logger.exception(
                    "Source initialization failed trigger=dependency retry=%s", backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(max(backoff, self.config.recovery_backoff_max_seconds), backoff * 2)
        return []

    def _get_frozen_watermark(self, symbol: str, exchange: str) -> int:
        latest_candle = self.db_client.get_latest_m1_candle(symbol, exchange=exchange or None)
        if not latest_candle:
            fallback = self._history_start_ms
            self.logger.info(
                f"{symbol} M1: No data in database, using fallback watermark "
                f"{self._ms_to_iso(fallback)}"
            )
            return fallback

        latest_ts = max(int(latest_candle["timestamp_ms"]), self._history_start_ms)
        self.logger.info(f"{symbol} M1: Frozen startup watermark at {self._ms_to_iso(latest_ts)}")
        return latest_ts

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

        if timeframe != self.TIMEFRAME_CODE_M1:
            raise ValueError("Historical persistence accepts only M1 Candles")
        to_ts = min(to_ts, (self._utc_now_ms() // 60000) * 60000 - 1)
        if from_ts > to_ts:
            return

        self.logger.info(
            f"Backfilling {symbol} {timeframe} from {self._ms_to_iso(from_ts)} "
            f"to {self._ms_to_iso(to_ts)}"
        )

        if to_ts - from_ts >= self.HISTORY_WINDOW_MS:
            for start in range(from_ts, to_ts + 1, self.HISTORY_WINDOW_MS):
                await self._backfill_symbol(
                    symbol_id,
                    symbol,
                    start,
                    min(to_ts, start + self.HISTORY_WINDOW_MS - 1),
                    timeframe,
                )
            return

        candles: List[Dict[str, Any]] = []
        seen: set[int] = set()
        async for candle in self.broker_client.stream_trendbars(
            symbol,
            timeframe=timeframe,
            start_time=from_ts,
            end_time=to_ts,
        ):
            timestamp = int(candle["t"])
            if not from_ts <= timestamp <= to_ts or timestamp % 60000:
                raise ValueError("Broker returned a Candle outside the closed M1 interval")
            if timestamp in seen or len(candles) >= self.HISTORY_WINDOW_MS // 60000 + 1:
                raise ValueError("Broker returned duplicate or excessive M1 Candles")
            seen.add(timestamp)
            candles.append(candle)

        if candles:
            state = self._state_by_id[symbol_id]
            mapped = [self._format_candle_for_db(candle) for candle in candles]
            await self._write_candles_in_chunks(
                state.symbol, state.exchange, mapped, historical_interval=(from_ts, to_ts)
            )
            self.logger.info(f"Backfilled {len(candles)} candles for {symbol} {timeframe}")
        else:
            self.logger.debug(f"No backfill data available for {symbol} {timeframe}")

    async def _write_candles_in_chunks(
        self,
        symbol: str,
        exchange: str | None,
        candles: List[Dict[str, Any]],
        chunk_size: Optional[int] = None,
        historical_interval: tuple[int, int] | None = None,
    ) -> None:
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE

        total_chunks = (len(candles) + chunk_size - 1) // chunk_size
        for i in range(0, len(candles), chunk_size):
            chunk = candles[i : i + chunk_size]
            chunk_num = i // chunk_size + 1

            if historical_interval is None:
                await self._db_call(self.db_client.write_candles, symbol, chunk, exchange or None)
            else:
                await self._db_call(
                    self.db_client.write_historical_candles,
                    symbol,
                    chunk,
                    historical_interval[0],
                    historical_interval[1],
                    exchange or None,
                )
            self.logger.info(
                f"Wrote {len(chunk)} candles for {symbol} " f"(chunk {chunk_num}/{total_chunks})"
            )

    async def observe_continuity(self, symbol_id: int, continuity: str | None) -> None:
        """Protect a new publication session before its messages can affect storage."""
        state = self._state_by_id[symbol_id]
        if continuity is not None and continuity == state.continuity:
            return
        await self.request_recovery(
            state, "continuity-change" if continuity is not None else "invalid-continuity"
        )
        state.continuity = continuity

    async def observe_interruption(self, symbol_id: int, trigger: str) -> None:
        """Protect dependency loss even when the producer session is unchanged."""
        state = self._state_by_id[symbol_id]
        # A partial batch may have moved latest already. Retain the last fully
        # confirmed live boundary, captured before any writes in that batch.
        start = state.live_boundary_ms if trigger == "live-write-failure" else None
        await self.request_recovery(state, trigger, start)

    async def write_candles_callback(self, symbol_id: int, candles: List[Dict[str, Any]]) -> None:
        """Callback to write candles to database."""
        if not candles:
            return

        mapped_candles = [self._format_candle_for_db(candle) for candle in candles]
        state = self._state_by_id.get(symbol_id)
        if state is None:
            self.logger.warning("Skipping candles for unknown symbol_id=%s", symbol_id)
            return
        if (
            state.handoff_start_ms is not None
            and state.handoff_start_ms + 60000 <= self._utc_now_ms()
        ):
            # The open minute at subscription establishment was excluded from
            # the first closed target. Queued closed bars can arrive before that
            # minute closes, so retain protection until a saved target covers it.
            await self.request_recovery(
                state,
                "startup-handoff",
                min(state.handoff_start_ms, min(int(candle["t"]) for candle in candles)),
                establish_handoff=False,
            )
        while not self._shutdown:
            await state.live_ready.wait()
            async with state.protection_lock:
                if not state.live_ready.is_set():
                    continue
                assert state.live_boundary_ms is not None
                guard = await self._db_call(
                    self.db_client.begin_live_write,
                    state.symbol_id,
                    self.config.broker_account_id,
                    state.live_boundary_ms,
                )
                await self._write_candles_in_chunks(state.symbol, state.exchange, mapped_candles)
                state.live_boundary_ms = max(
                    state.live_boundary_ms or 0,
                    max(candle["timestamp_ms"] for candle in mapped_candles),
                )
                await self._db_call(self.db_client.finish_live_write, guard)
                return

    async def _get_stream_tail_id(self, stream_key: str) -> str:
        """Get current tail ID of a stream; returns 0-0 if stream is empty."""
        if self.redis is None:
            raise RuntimeError("Redis client not initialized")

        entries = await self.redis.xrevrange(stream_key, count=1)
        if not entries:
            return self.REDIS_STREAM_START

        message_id = entries[0][0]
        return self._decode_redis_id(message_id)

    async def _db_call(self, operation, *args):
        # Cancelling an await cannot cancel its synchronous HTTP thread. Drain it
        # before closing clients so no owned write continues after shutdown.
        task = asyncio.create_task(asyncio.to_thread(operation, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception:
                # Cleanup must retain cancellation even if the drained HTTP
                # operation failed; recovery must not enter retry sleep here.
                pass
            raise

    def _own_task(self, coroutine) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._owned_tasks.add(task)
        task.add_done_callback(self._owned_tasks.discard)
        return task

    async def _save_recovery(
        self,
        state: SymbolRuntimeState,
        trigger: str,
        start_ms: int | None = None,
        *,
        establish_handoff: bool = True,
    ) -> dict[str, Any]:
        account = self.config.broker_account_id
        pending = await self._db_call(self.db_client.get_pending_recovery, state.symbol_id, account)
        guard = await self._db_call(self.db_client.get_live_write_guard, state.symbol_id, account)
        if guard is not None:
            start_ms = (
                min(start_ms, guard["boundary_ms"])
                if start_ms is not None
                else guard["boundary_ms"]
            )
        if pending is not None:
            # Accepted work is never bounded again by a moving history policy.
            start_ms = (
                min(pending["next_ms"], start_ms) if start_ms is not None else pending["next_ms"]
            )
        elif start_ms is None:
            start_ms = await self._db_call(self._get_frozen_watermark, state.symbol, state.exchange)
        assert start_ms is not None
        if state.handoff_start_ms is not None:
            start_ms = min(start_ms, state.handoff_start_ms)
        target = (self._utc_now_ms() // 60000) * 60000 - 1
        new_handoff = target + 1 if establish_handoff else None
        if new_handoff is not None:
            # Save and handoff share one frozen clock boundary. Retain the
            # earliest excluded minute even if persistence fails or time moves.
            state.handoff_start_ms = (
                min(state.handoff_start_ms, new_handoff)
                if state.handoff_start_ms is not None
                else new_handoff
            )
        saved = await self._db_call(
            self.db_client.begin_recovery, state.symbol_id, account, start_ms, target, trigger
        )
        # Only retire a recovered guard after its boundary is durably pending.
        # Every later live attempt installs its own guard before Candle writes.
        if guard is not None:
            await self._db_call(self.db_client.finish_live_write, guard)
        # Durable pending work may retire the old minute while a new trigger
        # excludes a later one. Neither can be replaced by the receipt's clock.
        unresolved_handoffs = [
            minute
            for minute in (state.handoff_start_ms, new_handoff)
            if minute is not None and saved["target_ms"] < minute + 59999
        ]
        state.handoff_start_ms = min(unresolved_handoffs) if unresolved_handoffs else None
        self.logger.info(
            "Recovery protected market=%s account=%s M1 interval=[%s,%s] trigger=%s revision=%s",
            state.symbol,
            account,
            saved["next_ms"],
            saved["target_ms"],
            trigger,
            saved["revision"],
        )
        return saved

    async def request_recovery(
        self,
        state: SymbolRuntimeState,
        trigger: str,
        start_ms: int | None = None,
        *,
        establish_handoff: bool = True,
    ) -> None:
        """Durably merge an interruption before allowing affected live writes."""
        state.live_ready.clear()
        async with state.protection_lock:
            async with self._boundary_semaphore:
                await self._save_recovery(
                    state, trigger, start_ms, establish_handoff=establish_handoff
                )
            state.recovery_requested.set()
            state.live_ready.set()

    async def _start_market(self, state: SymbolRuntimeState) -> None:
        backoff = max(1, self.config.recovery_backoff_initial_seconds)
        while not self._shutdown:
            try:
                async with state.protection_lock:
                    # Load accepted work BEFORE a fresh latest snapshot or stream setup.
                    async with self._boundary_semaphore:
                        pending = await self._db_call(
                            self.db_client.get_pending_recovery,
                            state.symbol_id,
                            self.config.broker_account_id,
                        )
                        guard = await self._db_call(
                            self.db_client.get_live_write_guard,
                            state.symbol_id,
                            self.config.broker_account_id,
                        )
                        boundaries = ([pending["next_ms"]] if pending is not None else []) + (
                            [guard["boundary_ms"]] if guard is not None else []
                        )
                        start = (
                            min(boundaries)
                            if boundaries
                            else await self._db_call(
                                self._get_frozen_watermark, state.symbol, state.exchange
                            )
                        )
                    async with self._stream_semaphore:
                        tail_id = await self._get_stream_tail_id(state.stream_key)
                        await self.broker_client.start_trendbar_stream(state.symbol, timeframe="M1")
                    # Time is captured after subscription: history bridges the tail/setup interval.
                    async with self._boundary_semaphore:
                        await self._save_recovery(state, "startup", start)
                    state.live_boundary_ms = start
                    state.recovery_requested.set()
                    state.live_ready.set()
                    self._own_task(self._recover_market(state))
                    assert self.consumer is not None
                    self.consumer_tasks.append(
                        self._own_task(
                            self.consumer.consume_stream(
                                stream_key=state.stream_key,
                                symbol_id=state.symbol_id,
                                callback=self.write_candles_callback,
                                start_id=tail_id,
                                continuity_callback=self.observe_continuity,
                                interruption_callback=self.observe_interruption,
                            )
                        )
                    )
                return
            except Exception:
                self.logger.exception(
                    "Recovery startup protected market=%s account=%s M1 trigger=startup retry=%s",
                    state.symbol,
                    self.config.broker_account_id,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(max(backoff, self.config.recovery_backoff_max_seconds), backoff * 2)

    async def _recover_market(self, state: SymbolRuntimeState) -> None:
        async with state.recovery_lock:
            while not self._shutdown:
                await state.recovery_requested.wait()
                state.recovery_requested.clear()
                backoff = max(1, self.config.recovery_backoff_initial_seconds)
                while not self._shutdown:
                    pending = None
                    try:
                        # Release scarce capacity before sleeping, including on persistence failure.
                        async with self._history_semaphore:
                            pending = await self._db_call(
                                self.db_client.get_pending_recovery,
                                state.symbol_id,
                                self.config.broker_account_id,
                            )
                            if pending is None:
                                break
                            start, target = pending["next_ms"], pending["target_ms"]
                            end = min(target, start + self.HISTORY_WINDOW_MS - 1)
                            if end >= (self._utc_now_ms() // 60000) * 60000:
                                raise RuntimeError("Pending historical window is not closed yet")
                            self.logger.info(
                                "Recovering market=%s account=%s M1 interval=[%s,%s] "
                                "trigger=%s revision=%s",
                                state.symbol,
                                self.config.broker_account_id,
                                start,
                                end,
                                pending["trigger"],
                                pending["revision"],
                            )
                            await self._backfill_symbol(state.symbol_id, state.symbol, start, end)
                            updated = await self._db_call(
                                self.db_client.advance_recovery, pending, end + 1
                            )
                        if updated:
                            self.logger.info(
                                "Recovery window complete market=%s account=%s M1 "
                                "interval=[%s,%s] trigger=%s",
                                state.symbol,
                                self.config.broker_account_id,
                                start,
                                end,
                                pending["trigger"],
                            )
                        backoff = max(1, self.config.recovery_backoff_initial_seconds)
                        # Give other ready Markets a turn between finite windows.
                        await asyncio.sleep(0)
                    except Exception:
                        self.logger.exception(
                            "Recovery failed market=%s account=%s M1 pending=%s retry=%s",
                            state.symbol,
                            self.config.broker_account_id,
                            pending,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(
                            max(backoff, self.config.recovery_backoff_max_seconds), backoff * 2
                        )

    async def start_consumers(self) -> None:
        """Start independent protected startup operations; history never blocks the run loop."""
        if self.consumer is None:
            raise RuntimeError("Consumer is not initialized")
        for state in self.runtime_states:
            self._own_task(self._start_market(state))

    async def _is_broker_connected(self) -> bool:
        """Require an available broker-service and authenticated cTrader connection."""
        try:
            health = await self.broker_client.get_meta_health()
            ctrader = health.get("components", {}).get("ctrader", {})
            connected = ctrader.get("status") == "up"
            instance_id = health.get("instance_id")
            if connected and isinstance(instance_id, str) and instance_id:
                self._broker_instance_id = instance_id
            return connected
        except Exception:
            return False

    async def _recover_symbol_after_reconnect(self, state: SymbolRuntimeState) -> None:
        backoff = max(1, self.config.recovery_backoff_initial_seconds)
        while not self._shutdown:
            try:
                state.live_ready.clear()
                async with state.protection_lock:
                    # Persist the old boundary before renewed publication can advance it.
                    async with self._boundary_semaphore:
                        await self._save_recovery(state, "broker-reconnect", None)
                    async with self._stream_semaphore:
                        await self.broker_client.start_trendbar_stream(state.symbol, timeframe="M1")
                    # Include all closed minutes elapsed during subscription retries.
                    async with self._boundary_semaphore:
                        await self._save_recovery(state, "broker-reconnect", None)
                    state.recovery_requested.set()
                    state.live_ready.set()
                return
            except Exception:
                self.logger.exception(
                    "Recovery protection failed market=%s account=%s M1 "
                    "trigger=broker-reconnect retry=%s",
                    state.symbol,
                    self.config.broker_account_id,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(max(backoff, self.config.recovery_backoff_max_seconds), backoff * 2)

    async def _run_recovery(self) -> None:
        await asyncio.gather(
            *(self._recover_symbol_after_reconnect(state) for state in self.runtime_states)
        )

    def _trigger_recovery(self) -> None:
        self._recovery_task = self._own_task(self._run_recovery())

    async def _monitor_broker_connectivity(self) -> None:
        """Monitor broker/cTrader connectivity and trigger recovery on reconnect transitions."""
        poll_seconds = max(1, self.config.broker_health_poll_seconds)
        while not self._shutdown:
            previous_instance = self._broker_instance_id
            connected = await self._is_broker_connected()
            restarted = (
                previous_instance is not None and previous_instance != self._broker_instance_id
            )

            if self._broker_connected is None:
                self._broker_connected = connected
                self.logger.info(f"Initial broker connectivity state: connected={connected}")
            elif connected and (not self._broker_connected or restarted):
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
            await self._shutdown_complete.wait()
            return

        self._is_shutting_down = True
        try:
            self.logger.info("Shutting down ingestion service...")
            self._shutdown = True

            if self.consumer:
                self.consumer.stop()

            if self._health_monitor_task:
                self._health_monitor_task.cancel()

            for task in self._owned_tasks:
                task.cancel()

            await asyncio.gather(*self._owned_tasks, return_exceptions=True)

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
        finally:
            self._shutdown_complete.set()

    async def run(self) -> None:
        """Main run loop."""
        try:
            await self.startup()

            if self.runtime_states:
                await self.start_consumers()

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
