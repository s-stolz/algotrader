from typing import AsyncIterator

from app.application.interfaces import (
    MarketDataPort,
    StreamRegistryPort,
    TrendbarStreamRegistryPort,
)
from app.domain.models import Symbol, Trendbar
from app.domain.value_objects import (
    AccountId,
    SymbolDescriptor,
    TickStreamOptions,
    TickStreamStatus,
    Timeframe,
    TrendbarStreamStatus,
)


class MarketDataService:
    def __init__(
        self,
        market_data_port: MarketDataPort,
        streams: StreamRegistryPort,
        trendbar_streams: TrendbarStreamRegistryPort,
    ) -> None:
        self._market_data_port = market_data_port
        self._streams = streams
        self._trendbar_streams = trendbar_streams

    async def start_tick_stream(
        self,
        account_id: AccountId,
        symbol: str,
        options: TickStreamOptions,
        expected_symbol_id: int | None = None,
    ) -> TickStreamStatus:
        return await self._streams.start_tick_stream(
            account_id, symbol, options, expected_symbol_id
        )

    async def stop_tick_stream(
        self, account_id: AccountId, symbol: str, expected_symbol_id: int | None = None
    ) -> None:
        await self._streams.stop_tick_stream(account_id, symbol, expected_symbol_id)

    async def tick_stream_status(self, account_id: AccountId, symbol: str) -> TickStreamStatus:
        return await self._streams.get_tick_stream_status(account_id, symbol)

    def stream_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
        expected_symbol_id: int | None = None,
    ) -> AsyncIterator[Trendbar]:
        return self._market_data_port.stream_trendbars(
            account_id,
            symbol,
            timeframe,
            from_ts,
            to_ts,
            limit,
            expected_symbol_id,
        )

    async def list_symbols(
        self, account_id: AccountId | None = None, *, refresh: bool = False
    ) -> list[SymbolDescriptor]:
        return await self._market_data_port.list_symbols(account_id, refresh=refresh)

    async def get_symbol(self, account_id: AccountId, symbol: str) -> Symbol:
        return await self._market_data_port.get_symbol(account_id, symbol.upper())

    async def start_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        expected_symbol_id: int | None = None,
    ) -> TrendbarStreamStatus:
        return await self._trendbar_streams.start_trendbar_stream(
            account_id, symbol, timeframe, expected_symbol_id
        )

    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        expected_symbol_id: int | None = None,
    ) -> None:
        await self._trendbar_streams.stop_trendbar_stream(
            account_id, symbol, timeframe, expected_symbol_id
        )

    async def trendbar_stream_status(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus:
        return await self._trendbar_streams.get_trendbar_stream_status(
            account_id, symbol, timeframe
        )
