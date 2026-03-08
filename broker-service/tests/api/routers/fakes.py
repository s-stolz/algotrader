from __future__ import annotations

from decimal import Decimal

from app.domain.models import Account, Deal, Order, Position, Symbol, TradeData, Trendbar
from app.domain.value_objects import (
    AccountId,
    OrderType,
    SymbolDescriptor,
    SymbolId,
    TickStreamStatus,
    Timeframe,
    TrendbarStreamStatus,
)


class FakeOrderService:
    async def place_order(self, account_id: AccountId, payload: dict):
        return {"status": "accepted", "orderId": 7, "echo": payload}

    async def cancel_order(self, account_id: AccountId, order_id: int) -> None:
        return None

    async def get_open_orders(self, account_id: AccountId):
        td = TradeData(symbol_id=1, volume=100, trade_side="BUY")
        return [Order(order_id=10, trade_data=td, order_type=OrderType.MARKET, order_status="OPEN")]

    async def get_order_history(
        self, account_id: AccountId, from_ts: int | None = None, to_ts: int | None = None
    ):
        return []


class FakePositionService:
    async def close_position(
        self, account_id: AccountId, position_id: int, close_volume: int | None = None
    ):
        td = TradeData(symbol_id=1, volume=100, trade_side="BUY")
        return Position(
            position_id=int(position_id), trade_data=td, position_status="CLOSED", swap=0
        )

    async def get_open_positions(self, account_id: AccountId):
        td = TradeData(symbol_id=1, volume=100, trade_side="BUY")
        return [Position(position_id=1, trade_data=td, position_status="OPEN", swap=0)]

    async def get_deal_history(
        self, account_id: AccountId, from_ts: int | None = None, to_ts: int | None = None
    ):
        return [
            Deal(
                deal_id=1,
                order_id=2,
                position_id=3,
                volume=100,
                filled_volume=100,
                symbol_id=1,
                create_timestamp=1000,
                execution_timestamp=1000,
                trade_side="BUY",
                deal_status="FILLED",
                execution_price=Decimal("1.23"),
            )
        ]


class FakeAccountService:
    async def list_accounts(self):
        return [
            Account(
                broker_name="demo",
                account_id=1,
                balance=Decimal("1000.50"),
                money_digits=2,
            )
        ]


class FakeMarketDataService:
    async def list_symbols(self, account_id: AccountId | None = None):
        return [SymbolDescriptor(symbol_id=SymbolId(1), symbol_name="EURUSD", enabled=True)]

    async def get_symbol(self, account_id: AccountId, symbol: str):
        return Symbol(
            symbol_id=1,
            symbol_name=symbol,
            digits=5,
            pip_position=4,
            commission=0,
            commission_type="USD_PER_LOT",
        )

    async def start_tick_stream(self, account_id: AccountId, symbol: str, options):
        return TickStreamStatus(
            running=True, started_at=100.0, last_tick_at=101.0, uptime_seconds=1.0
        )

    async def stop_tick_stream(self, account_id: AccountId, symbol: str):
        return None

    async def tick_stream_status(self, account_id: AccountId, symbol: str):
        return TickStreamStatus(
            running=True, started_at=100.0, last_tick_at=101.0, uptime_seconds=1.0
        )

    async def get_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ):
        return [
            Trendbar(
                o=Decimal("1.1"),
                h=Decimal("1.2"),
                l=Decimal("1.0"),
                c=Decimal("1.15"),
                v=10,
                t=12345,
            )
        ]

    async def stream_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ):
        yield Trendbar(
            o=Decimal("1.1"), h=Decimal("1.2"), l=Decimal("1.0"), c=Decimal("1.15"), v=10, t=12345
        )

    async def start_trendbar_stream(
        self, account_id: AccountId, symbol: str, timeframe: Timeframe, options=None
    ):
        return TrendbarStreamStatus(
            running=True, started_at=100.0, last_bar_at=101.0, uptime_seconds=1.0
        )

    async def stop_trendbar_stream(self, account_id: AccountId, symbol: str, timeframe: Timeframe):
        return None

    async def trendbar_stream_status(
        self, account_id: AccountId, symbol: str, timeframe: Timeframe
    ):
        return TrendbarStreamStatus(
            running=True, started_at=100.0, last_bar_at=101.0, uptime_seconds=1.0
        )


class FakeRedis:
    async def ping(self):
        return True


class FakeContainer:
    broker_connected = True
    active_streams = 1
    active_trendbar_streams = 2
    redis = FakeRedis()
    token_lifecycle_component = {"status": "up", "detail": "ok"}
