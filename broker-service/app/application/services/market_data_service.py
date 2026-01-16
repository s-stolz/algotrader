from app.application.interfaces import (
    MarketDataPort,
    StreamRegistryPort,
    TrendbarStreamRegistryPort,
)
from app.domain.models import Symbol
from app.domain.value_objects import (
    AccountId,
    SymbolDescriptor,
    TickStreamOptions,
    Timeframe,
    TrendbarStreamOptions,
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
    ):
        return await self._streams.start_tick_stream(account_id, symbol, options)

    async def stop_tick_stream(self, account_id: AccountId, symbol: str) -> None:
        await self._streams.stop_tick_stream(account_id, symbol)

    async def tick_stream_status(self, account_id: AccountId, symbol: str):
        return await self._streams.get_tick_stream_status(account_id, symbol)

    async def get_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ):
        return await self._market_data_port.get_trendbars(
            account_id,
            symbol,
            timeframe,
            from_ts,
            to_ts,
            limit,
        )

    async def list_symbols(self, account_id: AccountId | None = None) -> list[SymbolDescriptor]:
        return await self._market_data_port.list_symbols(account_id)

    async def get_symbol(self, account_id: AccountId, symbol: str) -> Symbol:
        return await self._market_data_port.get_symbol(account_id, symbol.upper())

    async def start_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        options: TrendbarStreamOptions | None = None,
    ):
        return await self._trendbar_streams.start_trendbar_stream(
            account_id, symbol, timeframe, options
        )

    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        await self._trendbar_streams.stop_trendbar_stream(account_id, symbol, timeframe)

    async def trendbar_stream_status(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ):
        return await self._trendbar_streams.get_trendbar_stream_status(
            account_id, symbol, timeframe
        )
