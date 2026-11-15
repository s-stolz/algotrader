from __future__ import annotations

import time
from collections import OrderedDict

import pandas as pd
from db_accessor_client import timeframe_to_minutes


class CandleCache:
    def __init__(self, *, ttl_seconds: int = 180, max_entries: int = 128) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._store: OrderedDict[str, tuple[float, pd.DataFrame]] = OrderedDict()

    @staticmethod
    def _cache_key(*, exchange: str | None, symbol: str, timeframe: str) -> str:
        exchange_part = (exchange or "na").upper()
        return f"{exchange_part}:{symbol.upper()}:{timeframe.upper()}"

    def put(
        self,
        *,
        exchange: str | None,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
        valid_until: float | None = None,
    ) -> None:
        if candles is None or candles.empty:
            return

        self._evict_expired()
        key = self._cache_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        self._store.pop(key, None)
        expires_at = time.time() + self.ttl_seconds
        if valid_until is not None:
            expires_at = min(expires_at, valid_until)
        self._store[key] = (expires_at, candles.copy())
        self._store.move_to_end(key)

        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def put_current(
        self,
        *,
        exchange: str | None,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
        end_ms: int | None,
        read_started_at: float,
    ) -> None:
        if candles is None or candles.empty:
            return
        # Storage can advance at every M1 close, including within larger bars.
        valid_until = (read_started_at // 60 + 1) * 60
        if time.time() >= valid_until:
            return
        if end_ms is not None:
            minutes = timeframe_to_minutes(timeframe)
            # Calendar-sized buckets need authoritative latest reads instead.
            if minutes > 1440 or 1440 % minutes:
                return
            period_ms = minutes * 60_000
            bucket_ms = int(read_started_at * 1000) // period_ms * period_ms
            last_ms = int(pd.Timestamp(candles.index[-1]).value // 1_000_000)
            if end_ms < bucket_ms or not bucket_ms - period_ms <= last_ms <= bucket_ms:
                return
        self.put(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            valid_until=valid_until,
        )

    def get_tail(
        self,
        *,
        exchange: str | None,
        symbol: str,
        timeframe: str,
        bars: int,
    ) -> pd.DataFrame | None:
        self._evict_expired()
        key = self._cache_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        item = self._store.get(key)
        if item is None:
            return None

        expires_at, df = item
        if expires_at <= time.time():
            self._store.pop(key, None)
            return None

        if bars <= 0:
            return None

        self._store.move_to_end(key)
        return df.tail(bars).copy()

    def _evict_expired(self) -> None:
        now = time.time()
        expired_keys = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        for key in expired_keys:
            self._store.pop(key, None)
