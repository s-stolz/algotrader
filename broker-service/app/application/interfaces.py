from abc import abstractmethod
from typing import Protocol

from app.domain.models import Account, Deal, Order, Position, Symbol, Tick, Trendbar
from app.domain.value_objects import (
    AccountId,
    OrderId,
    PositionId,
    SymbolDescriptor,
    TickStreamOptions,
    TickStreamStatus,
    Timeframe,
    TrendbarStreamOptions,
    TrendbarStreamStatus,
)


class BrokerPort(Protocol):
    @abstractmethod
    async def list_accounts(self) -> list[Account]: ...

    @abstractmethod
    async def get_open_orders(self, account_id: AccountId) -> list[Order]: ...

    @abstractmethod
    async def get_order_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Order]: ...

    @abstractmethod
    async def place_order(self, account_id: AccountId, order: dict) -> Order: ...

    @abstractmethod
    async def cancel_order(self, account_id: AccountId, order_id: OrderId) -> None: ...

    @abstractmethod
    async def get_open_positions(self, account_id: AccountId) -> list[Position]: ...

    @abstractmethod
    async def get_deal_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Deal]: ...

    @abstractmethod
    async def close_position(
        self,
        account_id: AccountId,
        position_id: PositionId,
        close_volume: int | None = None,
    ) -> Position: ...


class MarketDataPort(Protocol):
    """Market data operations exposed by broker."""

    @abstractmethod
    async def get_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> list[Trendbar]: ...

    @abstractmethod
    async def list_symbols(self, account_id: AccountId | None = None) -> list[SymbolDescriptor]: ...

    @abstractmethod
    async def get_symbol(self, account_id: AccountId, symbol: str) -> Symbol: ...


class RedisPublisherPort(Protocol):
    @abstractmethod
    async def publish_tick(self, tick: Tick, account_id: AccountId, symbol: str) -> None: ...

    @abstractmethod
    async def publish_candle(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        candle: Trendbar,
    ) -> None: ...

    @abstractmethod
    async def publish_order_event(self, account_id: AccountId, event: dict) -> None: ...

    @abstractmethod
    async def publish_trade_event(self, account_id: AccountId, event: dict) -> None: ...


class StreamRegistryPort(Protocol):
    @abstractmethod
    async def start_tick_stream(
        self,
        account_id: AccountId,
        symbol: str,
        options: TickStreamOptions,
    ) -> TickStreamStatus: ...

    @abstractmethod
    async def stop_tick_stream(self, account_id: AccountId, symbol: str) -> None: ...

    @abstractmethod
    async def get_tick_stream_status(self, account_id: AccountId,
                                     symbol: str) -> TickStreamStatus: ...


class TrendbarStreamRegistryPort(Protocol):
    @abstractmethod
    async def start_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        options: TrendbarStreamOptions | None = None,
    ) -> TrendbarStreamStatus: ...

    @abstractmethod
    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> None: ...

    @abstractmethod
    async def get_trendbar_stream_status(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus: ...
