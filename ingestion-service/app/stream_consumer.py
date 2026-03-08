"""Redis stream consumer for market data."""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from redis.asyncio import Redis

logger = logging.getLogger("ingestion-service.stream_consumer")


# Timeframe mapping: string code to minutes
TIMEFRAME_TO_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


class StreamConsumer:
    """Consumes candle data from Redis streams using XREAD."""

    def __init__(
        self,
        redis: Redis,
        account_id: str,
        batch_size: int = 100,
        block_ms: int = 5000
    ):
        """Initialize the stream consumer.

        Args:
            redis: Async Redis client
            account_id: Broker account ID for stream key construction
            batch_size: Maximum number of messages to read per XREAD call
            block_ms: Milliseconds to block waiting for new messages
        """
        self.redis = redis
        self.account_id = account_id
        self.batch_size = batch_size
        self.block_ms = block_ms
        self._running = False
        self._last_ids: Dict[str, str] = {}  # stream_key -> last_message_id
        self._pending_open_candles: Dict[str, Dict[str, Any]] = {}

    def get_stream_key(self, symbol: str, timeframe: str) -> str:
        """Build Redis stream key for a symbol/timeframe.

        Args:
            symbol: Symbol name (e.g., "EURUSD")
            timeframe: Timeframe code (e.g., "M1")

        Returns:
            Stream key (e.g., "candles:12345:EURUSD:M1")
        """
        return f"candles:{self.account_id}:{symbol}:{timeframe}"

    def set_last_id(self, stream_key: str, last_id: str) -> None:
        """Set the last processed message ID for a stream.

        Args:
            stream_key: Redis stream key
            last_id: Message ID to start reading after
        """
        self._last_ids[stream_key] = last_id
        logger.debug(f"Set last ID for {stream_key}: {last_id}")

    @staticmethod
    def _decode_bytes(value: Union[bytes, str]) -> str:
        """Decode bytes to string if needed.

        Args:
            value: Either bytes or string

        Returns:
            String value
        """
        return value.decode() if isinstance(value, bytes) else value

    def _parse_redis_candle(self, redis_data: Dict[bytes, bytes]) -> Dict[str, Any]:
        """Transform Redis stream message to candle dictionary.

        Args:
            redis_data: Raw data from Redis stream (bytes keys/values)

        Returns:
            Candle dictionary with keys: timestamp, open, high, low, close, volume
        """
        # Redis data format from broker-service:
        # o/h/l/c/v/t where t is epoch milliseconds.
        timestamp_ms = int(redis_data[b"t"].decode())
        logger.debug(f"Transforming candle {redis_data}")

        return {
            "t": timestamp_ms,
            "o": float(redis_data[b"o"].decode()),
            "h": float(redis_data[b"h"].decode()),
            "l": float(redis_data[b"l"].decode()),
            "c": float(redis_data[b"c"].decode()),
            "v": float(redis_data[b"v"].decode()),
        }

    def _process_stream_messages(
        self,
        stream_key: str,
        messages: List,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Process raw Redis stream messages into candles.

        Returns:
            Tuple of (candles list, last_message_id or None)
        """
        candles = []
        last_id = None
        pending = self._pending_open_candles.get(stream_key)

        for _stream, entries in messages:
            for msg_id, data in entries:
                msg_id_str = self._decode_bytes(msg_id)
                last_id = msg_id_str

                try:
                    candle = self._parse_redis_candle(data)

                    if pending is None:
                        pending = candle
                        continue

                    if candle["t"] > pending["t"]:
                        candles.append(pending)
                        pending = candle
                        continue

                    if candle["t"] == pending["t"]:
                        pending = candle
                        continue

                    logger.warning(
                        "Received out-of-order candle for %s (pending=%s, incoming=%s)",
                        stream_key,
                        pending["t"],
                        candle["t"],
                    )
                except Exception as e:
                    logger.error(f"Error transforming message {msg_id_str}: {e}")
                    continue

        if pending is not None:
            self._pending_open_candles[stream_key] = pending

        return candles, last_id

    async def consume_stream(
        self,
        stream_key: str,
        symbol_id: int,
        callback: callable,
        start_id: str = "0-0"
    ):
        """Consume messages from a single Redis stream.

        Args:
            stream_key: Redis stream key to consume
            symbol_id: Database symbol ID for the callback
            callback: Async function(symbol_id, candles) called with batched candles
            start_id: Message ID to start reading from (default: "0-0" for beginning)
        """
        last_id = self._last_ids.get(stream_key, start_id)
        logger.info(f"Starting consumption of {stream_key} from ID {last_id}")

        self._running = True

        while self._running:
            try:
                messages = await self.redis.xread(
                    {stream_key: last_id},
                    count=self.batch_size,
                    block=self.block_ms
                )

                if not messages:
                    continue

                candles, new_last_id = self._process_stream_messages(stream_key, messages)

                if candles:
                    logger.debug(f"Consumed {len(candles)} candles from {stream_key}")
                    logger.debug(f"New Candle for {stream_key}: {candles}")
                    await callback(symbol_id, candles)

                if new_last_id:
                    self._last_ids[stream_key] = new_last_id
                    last_id = new_last_id

            except asyncio.CancelledError:
                logger.info(f"Consumer for {stream_key} cancelled")
                break
            except Exception as e:
                logger.error(f"Error consuming {stream_key}: {e}")
                await asyncio.sleep(5)

    async def backfill_from_stream(
        self,
        stream_key: str,
        symbol_id: int,
        start_id: str,
        end_id: str,
        callback: callable
    ) -> int:
        """Backfill historical data from a stream between two message IDs.

        Args:
            stream_key: Redis stream key
            symbol_id: Database symbol ID
            start_id: Starting message ID (exclusive)
            end_id: Ending message ID (inclusive, or "+" for latest)
            callback: Async function(symbol_id, candles) called with batched candles

        Returns:
            Number of candles backfilled
        """
        logger.info(f"Backfilling {stream_key} from {start_id} to {end_id}")

        current_id = start_id
        total_candles = 0

        while True:
            try:
                # Use XRANGE for backfilling historical data
                messages = await self.redis.xrange(
                    stream_key,
                    min=f"({current_id}",  # Exclusive start
                    max=end_id,
                    count=self.batch_size
                )

                if not messages:
                    break

                candles = []
                for msg_id, data in messages:
                    msg_id_str = self._decode_bytes(msg_id)

                    try:
                        candle = self._parse_redis_candle(data)
                        candles.append(candle)
                        current_id = msg_id_str
                    except Exception as e:
                        logger.error(f"Error transforming message {msg_id_str}: {e}")
                        continue

                if candles:
                    await callback(symbol_id, candles)
                    total_candles += len(candles)
                    logger.info(f"Backfilled {len(candles)} candles from {stream_key}")

                if len(messages) < self.batch_size:
                    # Reached the end
                    break

            except Exception as e:
                logger.error(f"Error during backfill of {stream_key}: {e}")
                break

        logger.info(f"Backfill complete: {total_candles} candles from {stream_key}")
        return total_candles

    def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        logger.info("Stream consumer stopped")
