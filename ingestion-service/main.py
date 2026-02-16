"""Main entry point for the ingestion service."""
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.broker_client import BrokerClient
from app.config import load_config
from app.db_client import DatabaseClient
from app.logger import setup_logging
from app.stream_consumer import StreamConsumer
from app.utils import epoch_ms_to_iso
from redis.asyncio import Redis


class IngestionService:
    """Orchestrates data ingestion from Redis streams to database."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_CODE_M1 = "M1"
    CHUNK_SIZE = 10000
    MAX_BACKFILL_DAYS = 365
    REDIS_NEW_MESSAGES_ONLY = "$"
    REDIS_STREAM_START = "0-0"

    @staticmethod
    def _format_candle_for_db(candle: Dict[str, Any]) -> Dict[str, Any]:
        """Transform broker candle format to database format.

        Args:
            candle: Broker candle with keys: o, h, l, c, v, t, digits

        Returns:
            Database candle with keys: timestamp, open, high, low, close, volume
        """
        return {
            'timestamp': epoch_ms_to_iso(candle['t']),
            'open': candle['o'],
            'high': candle['h'],
            'low': candle['l'],
            'close': candle['c'],
            'volume': candle['v']
        }

    def __init__(self):
        """Initialize the ingestion service."""
        self.config = load_config()
        self.logger = setup_logging(self.config.log_level)

        self.db_client = DatabaseClient(self.config.db_api_base_url)
        self.broker_client = BrokerClient(
            self.config.broker_service_base_url,
            self.config.broker_account_id
        )
        self.redis: Redis | None = None
        self.consumer: StreamConsumer | None = None

        self.markets: List[Dict[str, Any]] = []
        self.consumer_tasks: List[asyncio.Task] = []
        self._shutdown = False

    async def startup(self) -> None:
        """Initialize connections and load configuration."""
        self.logger.info("Starting ingestion service...")

        self.redis = Redis.from_url(
            self.config.redis_url,
            decode_responses=False  # We handle decoding manually
        )
        await self.redis.ping()
        self.logger.info(f"Connected to Redis at {self.config.redis_url}")

        self.consumer = StreamConsumer(
            redis=self.redis,
            account_id=self.config.broker_account_id,
            batch_size=self.config.consumer_batch_size,
            block_ms=self.config.consumer_block_ms
        )

        self.markets = self.db_client.get_markets()
        if not self.markets:
            self.logger.warning("No markets found in database. Waiting for markets to be created...")
        else:
            self.logger.info(f"Loaded {len(self.markets)} markets: {[m['symbol'] for m in self.markets]}")

    def _calculate_time_gap(self, latest_candle: Optional[Dict], symbol: str) -> timedelta:
        """Calculate time gap from latest candle to now.

        Args:
            latest_candle: Latest candle dict or None
            symbol: Symbol name for logging

        Returns:
            Time gap as timedelta
        """
        if latest_candle is None:
            self.logger.info(f"{symbol} M1: No data in database")
            return timedelta(days=self.MAX_BACKFILL_DAYS)

        latest_ts = datetime.fromisoformat(latest_candle["timestamp"].replace("Z", "+00:00"))
        time_gap = datetime.now() - latest_ts

        self.logger.debug(
            f"{symbol} M1: Latest candle at {latest_ts.isoformat()} "
            f"({time_gap.total_seconds() / 3600:.1f}h ago)"
        )
        return time_gap

    def _needs_backfill(self, time_gap: timedelta, timeframe_minutes: int) -> bool:
        """Determine if backfill is needed based on time gap.

        Args:
            time_gap: Time since latest candle
            timeframe_minutes: Candle timeframe in minutes

        Returns:
            True if backfill needed
        """
        expected_gap = timedelta(minutes=timeframe_minutes * 2)
        return time_gap > expected_gap

    async def _backfill_symbol(
        self,
        symbol_id: int,
        symbol: str,
        latest_ts: datetime,
        timeframe: str = None
    ) -> None:
        """Backfill historical data for a single symbol.

        Args:
            symbol_id: Database symbol ID
            symbol: Symbol name
            latest_ts: Timestamp to backfill from
            timeframe: Timeframe code (default: M1)
        """
        if timeframe is None:
            timeframe = self.TIMEFRAME_CODE_M1

        self.logger.info(f"Backfilling {symbol} {timeframe} from streaming API...")

        candles = []
        async for candle in self.broker_client.stream_trendbars(
            symbol,
            timeframe=timeframe,
            start_time=latest_ts.isoformat(),
            end_time=datetime.now().isoformat()
        ):
            candles.append(candle)

        if candles:
            await self.write_candles_callback(symbol_id, candles)
            self.logger.info(f"Backfilled {len(candles)} candles for {symbol} {timeframe}")
        else:
            self.logger.debug(f"No backfill data available for {symbol} {timeframe}")

    async def check_and_backfill(self) -> None:
        """Check for missing data and backfill from REST API."""
        self.logger.info("Checking for missing data and starting backfill...")

        timeframe_minutes = self.TIMEFRAME_M1

        for market in self.markets:
            symbol_id = market["symbol_id"]
            symbol = market["symbol"]

            latest_candle = self.db_client.get_latest_candle(symbol_id, timeframe_minutes)
            time_gap = self._calculate_time_gap(latest_candle, symbol)

            if self._needs_backfill(time_gap, timeframe_minutes):
                latest_ts = (
                    datetime.fromisoformat(latest_candle["timestamp"].replace("Z", "+00:00"))
                    if latest_candle
                    else datetime(2025, 1, 1)
                )
                await self._backfill_symbol(symbol_id, symbol, latest_ts)

        self.logger.info("Backfill check complete")

    async def _write_candles_in_chunks(
        self,
        symbol_id: int,
        candles: List[Dict[str, Any]],
        chunk_size: int = None
    ) -> None:
        """Write candles to database in chunks.

        Args:
            symbol_id: Database symbol ID
            candles: List of formatted candle dictionaries
            chunk_size: Number of candles per chunk (default: 10000)
        """
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE

        total_chunks = (len(candles) + chunk_size - 1) // chunk_size

        for i in range(0, len(candles), chunk_size):
            chunk = candles[i:i + chunk_size]
            chunk_num = i // chunk_size + 1

            await asyncio.to_thread(
                self.db_client.write_candles,
                symbol_id,
                chunk
            )

            self.logger.info(
                f"Wrote {len(chunk)} candles for symbol_id={symbol_id} "
                f"(chunk {chunk_num}/{total_chunks})"
            )

    async def write_candles_callback(self, symbol_id: int, candles: List[Dict[str, Any]]) -> None:
        """Callback to write candles to database.

        Args:
            symbol_id: Database symbol ID
            candles: List of candle dictionaries in broker format
        """
        if not candles:
            return

        mapped_candles = [self._format_candle_for_db(candle) for candle in candles]
        await self._write_candles_in_chunks(symbol_id, mapped_candles)

    async def start_consumers(self) -> None:
        """Start consuming from all configured streams."""
        self.logger.info("Starting stream consumers...")

        for market in self.markets:
            symbol_id = market["symbol_id"]
            symbol = market["symbol"]

            timeframe_code = self.TIMEFRAME_CODE_M1
            stream_key = self.consumer.get_stream_key(symbol, timeframe_code)

            await self.broker_client.start_trendbar_stream(
                symbol,
                timeframe=timeframe_code,
                only_completed_bars=True,
            )

            task = asyncio.create_task(
                self.consumer.consume_stream(
                    stream_key=stream_key,
                    symbol_id=symbol_id,
                    callback=self.write_candles_callback,
                    start_id=self.REDIS_NEW_MESSAGES_ONLY
                )
            )
            self.consumer_tasks.append(task)

            self.logger.info(f"Started consumer for {stream_key}")

        self.logger.info(f"Started {len(self.consumer_tasks)} stream consumers")

    async def shutdown(self) -> None:
        """Gracefully shutdown the service."""
        self.logger.info("Shutting down ingestion service...")
        self._shutdown = True

        # Stop consumer
        if self.consumer:
            self.consumer.stop()

        # Cancel all consumer tasks
        for task in self.consumer_tasks:
            task.cancel()

        if self.consumer_tasks:
            await asyncio.gather(*self.consumer_tasks, return_exceptions=True)

        # Close Redis connection
        if self.redis:
            await self.redis.close()
            self.logger.info("Closed Redis connection")

        # Close broker client
        await self.broker_client.aclose()
        self.logger.info("Closed broker client")

        # Close database client
        self.db_client.close()
        self.logger.info("Closed database client")

        self.logger.info("Ingestion service stopped")

    async def run(self) -> None:
        """Main run loop."""
        try:
            await self.startup()

            await self.check_and_backfill()

            await self.start_consumers()

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

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_shutdown(sig):
        service.logger.info(f"Received signal {sig}")
        asyncio.create_task(service.shutdown())

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))

    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
