from __future__ import annotations

import time
from collections import OrderedDict

import pandas as pd


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
    ) -> None:
        if candles is None or candles.empty:
            return

        self._evict_expired()
        key = self._cache_key(exchange=exchange, symbol=symbol, timeframe=timeframe)
        self._store.pop(key, None)
        self._store[key] = (time.time() + self.ttl_seconds, candles.copy())
        self._store.move_to_end(key)

        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

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
