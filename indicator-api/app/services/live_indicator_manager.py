from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import redis.asyncio as aioredis
from algotrader_logger import get_logger
from db_accessor_client import normalize_timeframe_code
from db_accessor_client.market_sources import BrokerMarketResolver
from indicator_engine import HistoryPolicy, ParamGrid, get_update_engine

from app import ENGINE_REGISTRY, get_engine_id, supports_live
from app.candles import get_candles
from app.schemas_live import (
    LiveIndicatorStartResponse,
    LiveIndicatorStatusResponse,
    LiveIndicatorStopResponse,
    LiveIndicatorStreamRequest,
    LiveIndicatorWarmupInfo,
)
from app.services.candle_cache import CandleCache
from app.services.live_daily_basket import LiveDailyBasket

if TYPE_CHECKING:
    from redis.typing import EncodableT, FieldT

log = get_logger(__name__)


CANDLE_FIELDS = ["open", "high", "low", "close", "volume"]


def _redis_socket_timeout_seconds(block_ms: int) -> float | None:
    if block_ms <= 0:
        return None
    return (block_ms / 1000.0) + 1.0


@dataclass(frozen=True)
class LiveStreamSpec:
    account_id: str
    symbol: str
    timeframe: str
    indicator_id: int
    exchange: str | None
    parameters: dict[str, Any]
    market_id: int

    @property
    def engine_id(self) -> str:
        return get_engine_id(self.indicator_id)

    @property
    def stream_id(self) -> str:
        raw = json.dumps(self._canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def exchange_key(self) -> str:
        return (self.exchange or "na").upper()

    @property
    def candle_stream_key(self) -> str:
        return f"candles:{self.account_id}:{self.symbol}:{self.timeframe}"

    @property
    def indicator_stream_key(self) -> str:
        return (
            f"indicators:{self.account_id}:{self.exchange_key}:"
            f"{self.symbol}:{self.timeframe}:{self.stream_id}"
        )

    @property
    def signature_key(self) -> str:
        return json.dumps(self._canonical(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_request(cls, request: LiveIndicatorStreamRequest) -> "LiveStreamSpec":
        timeframe_code = normalize_timeframe_code(request.timeframe)
        params = dict(request.parameters or {})
        return cls(
            account_id=request.account_id,
            symbol=request.symbol.upper(),
            timeframe=timeframe_code,
            indicator_id=int(request.indicator_id),
            exchange=request.exchange,
            parameters=params,
            market_id=request.market_id,
        )

    def _canonical(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "market_id": self.market_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "indicator_id": self.indicator_id,
            "exchange": self.exchange or "",
            "parameters": self.parameters,
        }


@dataclass
class LiveSession:
    spec: LiveStreamSpec
    ref_count: int
    task: asyncio.Task | None
    update_engine: Any
    running: bool
    daily_basket: LiveDailyBasket | None = None


class LiveIndicatorManager:
    def __init__(
        self, candle_cache: CandleCache, market_resolver: BrokerMarketResolver | None = None
    ):
        self.candle_cache = candle_cache
        self.market_resolver = market_resolver or BrokerMarketResolver(
            os.getenv("ACCOUNT_ID", ""), os.getenv("CTRADER_HOST_TYPE", "")
        )
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_block_ms = int(os.getenv("INDICATOR_REDIS_BLOCK_MS", "5000"))
        self.redis_batch_size = int(os.getenv("INDICATOR_REDIS_BATCH_SIZE", "100"))
        self.stream_maxlen = int(os.getenv("INDICATOR_STREAM_MAXLEN", "10000"))
        self.history_rows = int(os.getenv("INDICATOR_LIVE_HISTORY_ROWS", "5000"))

        self._redis: aioredis.Redis | None = None
        self._sessions_by_key: dict[str, LiveSession] = {}
        self._key_by_stream_id: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def start_stream(
        self,
        request: LiveIndicatorStreamRequest,
    ) -> LiveIndicatorStartResponse:
        spec = LiveStreamSpec.from_request(request)
        self._validate_live_indicator(spec)
        request = await self._resolve_market_request(request)
        spec = LiveStreamSpec.from_request(request)

        async with self._lock:
            existing = self._sessions_by_key.get(spec.signature_key)
            if existing is not None:
                existing.ref_count += 1
                warmup = self._build_warmup_info(spec=spec, seeded_bars=0, source="existing")
                return LiveIndicatorStartResponse(
                    stream_id=spec.stream_id,
                    redis_stream_key=spec.indicator_stream_key,
                    status="already_running",
                    warmup=warmup,
                )

            redis = await self._ensure_redis()
            daily_basket = None
            update_engine = None
            history = ENGINE_REGISTRY.get(spec.engine_id).spec.resolve_input_history(
                spec.parameters
            )
            if history.anchor == "utc_day":
                daily_basket = LiveDailyBasket(spec)
                await daily_basket.initialize(redis)
                seeded_bars, source = 0, "none"
            else:
                update_engine = get_update_engine(
                    history=HistoryPolicy(mode="rolling", max_rows=self.history_rows),
                    registry=ENGINE_REGISTRY,
                )
                update_engine.register_indicator(
                    indicator_id=spec.engine_id,
                    timeframe=spec.timeframe,
                    assets=[spec.symbol],
                    fields=CANDLE_FIELDS,
                    param_grid=ParamGrid(spec.parameters),
                    allow_out_of_order=True,
                )

                seeded_bars, source = await self._seed_warmup(spec, update_engine)

            session = LiveSession(
                spec=spec,
                ref_count=1,
                task=None,
                update_engine=update_engine,
                running=True,
                daily_basket=daily_basket,
            )
            session.task = asyncio.create_task(self._run_session(session))
            session.task.add_done_callback(
                lambda task, stream_id=spec.stream_id: self._on_session_done(stream_id, task)
            )
            self._sessions_by_key[spec.signature_key] = session
            self._key_by_stream_id[spec.stream_id] = spec.signature_key

            return LiveIndicatorStartResponse(
                stream_id=spec.stream_id,
                redis_stream_key=spec.indicator_stream_key,
                status="started",
                warmup=self._build_warmup_info(spec=spec, seeded_bars=seeded_bars, source=source),
            )

    async def _resolve_market_request(
        self, request: LiveIndicatorStreamRequest
    ) -> LiveIndicatorStreamRequest:
        if request.account_id != self.market_resolver.account_id:
            raise ValueError("Live indicator account must match the connected broker account")
        market = await self.market_resolver.resolve(request.market_id)
        required = ENGINE_REGISTRY.get(get_engine_id(request.indicator_id)).spec.required_assets
        await self.market_resolver.dependencies(market, required or [])
        if request.symbol.upper() != market["symbol"].upper():
            raise ValueError("Live indicator symbol does not match market_id")
        if request.exchange is not None and request.exchange != market["exchange"]:
            raise ValueError("Live indicator exchange does not match market_id")
        return request.model_copy(
            update={"symbol": market["symbol"], "exchange": market["exchange"]}
        )

    async def stop_stream(
        self,
        request: LiveIndicatorStreamRequest,
    ) -> LiveIndicatorStopResponse:
        if request.account_id != self.market_resolver.account_id:
            raise ValueError("Live indicator account must match the connected broker account")
        spec = LiveStreamSpec.from_request(request)

        async with self._lock:
            session = next(
                (
                    item
                    for item in self._sessions_by_key.values()
                    if item.spec.market_id == spec.market_id
                    and item.spec.account_id == spec.account_id
                    and item.spec.timeframe == spec.timeframe
                    and item.spec.indicator_id == spec.indicator_id
                    and item.spec.parameters == spec.parameters
                ),
                None,
            )
            if session is None:
                return LiveIndicatorStopResponse(stream_id=spec.stream_id, stopped=False)
            spec = session.spec

            session.ref_count = max(0, session.ref_count - 1)
            if session.ref_count > 0:
                return LiveIndicatorStopResponse(stream_id=spec.stream_id, stopped=False)

            session.running = False
            if session.task:
                session.task.cancel()
            self._sessions_by_key.pop(spec.signature_key, None)
            self._key_by_stream_id.pop(spec.stream_id, None)

        if session.task:
            try:
                await session.task
            except asyncio.CancelledError:
                pass

        return LiveIndicatorStopResponse(stream_id=spec.stream_id, stopped=True)

    async def get_status(self, stream_id: str) -> LiveIndicatorStatusResponse | None:
        async with self._lock:
            key = self._key_by_stream_id.get(stream_id)
            if key is None:
                return None
            session = self._sessions_by_key.get(key)
            if session is None:
                return None

            return LiveIndicatorStatusResponse(
                stream_id=stream_id,
                market_id=session.spec.market_id,
                running=session.running,
                account_id=session.spec.account_id,
                symbol=session.spec.symbol,
                timeframe=session.spec.timeframe,
                indicator_id=session.spec.indicator_id,
                exchange=session.spec.exchange,
                ref_count=session.ref_count,
                redis_stream_key=session.spec.indicator_stream_key,
            )

    async def shutdown(self) -> None:
        async with self._lock:
            sessions = list(self._sessions_by_key.values())
            self._sessions_by_key.clear()
            self._key_by_stream_id.clear()

        for session in sessions:
            session.running = False
            if session.task:
                session.task.cancel()

        for session in sessions:
            if session.task:
                try:
                    await session.task
                except asyncio.CancelledError:
                    pass

        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                decode_responses=True,
                protocol=2,
                socket_timeout=_redis_socket_timeout_seconds(self.redis_block_ms),
            )
        redis = self._redis
        assert redis is not None
        ping_result = redis.ping()
        if inspect.isawaitable(ping_result):
            await ping_result
        return redis

    def _validate_live_indicator(self, spec: LiveStreamSpec) -> None:
        if not supports_live(spec.indicator_id):
            raise ValueError(f"{spec.engine_id} is not supported for live streaming in v1")

    def _build_warmup_info(
        self,
        *,
        spec: LiveStreamSpec,
        seeded_bars: int,
        source: str,
    ) -> LiveIndicatorWarmupInfo:
        indicator = ENGINE_REGISTRY.get(spec.engine_id)
        required = indicator.spec.warmup(spec.parameters)
        return LiveIndicatorWarmupInfo(
            required_bars=max(1, int(required)),
            seeded_bars=max(0, int(seeded_bars)),
            source=source,  # type: ignore[arg-type]
        )

    async def _seed_warmup(self, spec: LiveStreamSpec, update_engine: Any) -> tuple[int, str]:
        indicator = ENGINE_REGISTRY.get(spec.engine_id)
        warmup = max(1, int(indicator.spec.warmup(spec.parameters)))

        warmup_df = self.candle_cache.get_tail(
            exchange=spec.exchange,
            symbol=spec.symbol,
            timeframe=spec.timeframe,
            bars=warmup,
        )
        source = "cache"

        if warmup_df is None or warmup_df.empty or len(warmup_df) < warmup:
            warmup_df = await get_candles(
                symbol=spec.symbol,
                timeframe=spec.timeframe,
                start_ms=None,
                end_ms=None,
                limit=warmup,
                exchange=spec.exchange,
            )
            source = "database"

        if warmup_df is None or warmup_df.empty:
            return 0, "none"

        seeded = 0
        cols = [c for c in CANDLE_FIELDS if c in warmup_df.columns]
        if len(cols) != len(CANDLE_FIELDS):
            return 0, "none"

        for timestamp, row in warmup_df[CANDLE_FIELDS].iterrows():
            row_values = row.to_numpy(dtype=np.float64)[np.newaxis, :]
            timestamp_ms = _to_timestamp_ms(timestamp)
            update_engine.on_bar(
                timeframe=spec.timeframe,
                timestamp_ms=timestamp_ms,
                new_row=row_values,
            )
            seeded += 1

        return seeded, source

    async def _run_session(self, session: LiveSession) -> None:
        redis = await self._ensure_redis()
        if session.daily_basket is not None:
            await session.daily_basket.run(
                redis, maxlen=self.stream_maxlen, count=self.redis_batch_size
            )
            return
        last_id = "$"
        spec = session.spec

        while session.running:
            results = await self._read_session_results(
                redis=redis,
                stream_key=spec.candle_stream_key,
                last_id=last_id,
                stream_id=spec.stream_id,
            )
            if not results:
                continue

            for _, messages in results:
                for message_id, fields in messages:
                    last_id = message_id
                    try:
                        await self._process_session_message(
                            session=session,
                            redis=redis,
                            fields=fields,
                        )
                    except Exception as exc:
                        log.error(
                            "Live stream processing error for %s (stream=%s): %s",
                            spec.symbol,
                            spec.stream_id,
                            exc,
                        )

    async def _read_session_results(
        self,
        *,
        redis: aioredis.Redis,
        stream_key: str,
        last_id: str,
        stream_id: str,
    ) -> Any:
        try:
            return await redis.xread(
                {stream_key: last_id},
                count=self.redis_batch_size,
                block=self.redis_block_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error(f"Live stream read error for {stream_id}: {exc}")
            await asyncio.sleep(1)
            return None

    async def _process_session_message(
        self,
        *,
        session: LiveSession,
        redis: aioredis.Redis,
        fields: dict[str, Any],
    ) -> None:
        candle = _parse_candle_fields(fields)
        if candle is None:
            return

        updated = session.update_engine.on_bar(
            timeframe=session.spec.timeframe,
            timestamp_ms=candle["timestamp_ms"],
            new_row=_candle_row(candle),
        )
        tensor = updated.get(session.spec.engine_id)
        if tensor is None:
            return

        output_values = _tensor_output_values(tensor)
        if output_values is None:
            return

        payload: dict[FieldT, EncodableT] = {
            "t": str(candle["timestamp_ms"]),
            "s": session.spec.stream_id,
            "i": str(session.spec.indicator_id),
            "d": json.dumps(output_values, separators=(",", ":")),
        }
        await redis.xadd(
            session.spec.indicator_stream_key,
            payload,
            maxlen=self.stream_maxlen,
            approximate=True,
        )

    def _on_session_done(self, stream_id: str, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except Exception as err:
            log.error("Live stream task completion check failed for %s: %s", stream_id, err)
            return
        if exc is not None:
            log.error("Live stream task crashed for %s: %s", stream_id, exc)


def _parse_candle_fields(fields: dict[str, Any]) -> dict[str, float | int] | None:
    try:
        return {
            "timestamp_ms": int(fields["t"]),
            "open": float(fields["o"]),
            "high": float(fields["h"]),
            "low": float(fields["l"]),
            "close": float(fields["c"]),
            "volume": float(fields["v"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _candle_row(candle: dict[str, float | int]) -> np.ndarray:
    return np.array(
        [
            [
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                candle["volume"],
            ]
        ],
        dtype=np.float64,
    )


def _tensor_output_values(tensor: Any) -> dict[str, float | None] | None:
    output_names = tensor.coords.get("output")
    if output_names is None:
        return None
    return {
        str(output_name): _safe_float(tensor.data[0, 0, o_idx, 0])
        for o_idx, output_name in enumerate(output_names)
    }


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _to_timestamp_ms(value: Any) -> int:
    if isinstance(value, pd.Timestamp):
        return int(value.value // 1_000_000)

    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Cannot convert timestamp value to epoch ms: {value}")
    return int(ts.value // 1_000_000)
