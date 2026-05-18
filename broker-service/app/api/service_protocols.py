from __future__ import annotations

from typing import Any, AsyncIterator, Mapping, Protocol

from app.domain.models import Account, Deal, Order, Position, Symbol, Trendbar
from app.domain.value_objects import (
    AccountId,
    OrderId,
    PositionId,
    SymbolDescriptor,
    TickStreamOptions,
    TickStreamStatus,
    Timeframe,
    TrendbarStreamStatus,
)


class AccountServicePort(Protocol):
    async def list_accounts(self) -> list[Account]: ...


class OrderServicePort(Protocol):
    async def place_order(
        self,
        account_id: AccountId,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]: ...

    async def cancel_order(self, account_id: AccountId, order_id: OrderId) -> None: ...

    async def get_open_orders(self, account_id: AccountId) -> list[Order]: ...

    async def get_order_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Order]: ...


class PositionServicePort(Protocol):
    async def close_position(
        self,
        account_id: AccountId,
        position_id: PositionId,
        close_volume: int | None = None,
    ) -> Position: ...

    async def get_open_positions(self, account_id: AccountId) -> list[Position]: ...

    async def get_deal_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Deal]: ...


class MarketDataServicePort(Protocol):
    async def list_symbols(self, account_id: AccountId | None = None) -> list[SymbolDescriptor]: ...

    async def get_symbol(self, account_id: AccountId, symbol: str) -> Symbol: ...

    async def start_tick_stream(
        self,
        account_id: AccountId,
        symbol: str,
        options: TickStreamOptions,
    ) -> TickStreamStatus: ...

    async def stop_tick_stream(self, account_id: AccountId, symbol: str) -> None: ...

    async def tick_stream_status(self, account_id: AccountId, symbol: str) -> TickStreamStatus: ...

    async def get_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> list[Trendbar]: ...

    def stream_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> AsyncIterator[Trendbar]: ...

    async def start_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus: ...

    async def stop_trendbar_stream(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> None: ...

    async def trendbar_stream_status(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
    ) -> TrendbarStreamStatus: ...
