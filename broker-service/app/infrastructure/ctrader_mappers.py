from __future__ import annotations

from decimal import Decimal
from typing import Callable

from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOACommissionType,
    ProtoOADeal,
    ProtoOADealStatus,
    ProtoOAOrder,
    ProtoOAOrderStatus,
    ProtoOAOrderType,
    ProtoOAPosition,
    ProtoOATrendbar,
    ProtoOATrendbarPeriod,
    ProtoOATimeInForce,
    ProtoOATradeSide,
)

from app.domain.models import Account, Deal, Order, Position, Symbol, Tick, Trendbar
from app.domain.models.deal import ClosePositionDetail
from app.domain.models.position import TradeData
from app.domain.value_objects import SymbolDescriptor, Timeframe


# Type alias for symbol lookup function
SymbolLookup = Callable[[int], SymbolDescriptor | None]


def map_trader(trader, is_live: bool = False) -> Account:
    """Map a ProtoOATrader to an Account domain model."""
    digits = trader.moneyDigits or 2
    return Account(
        broker_name=trader.brokerName,
        account_id=trader.ctidTraderAccountId,
        trader_login=trader.traderLogin,
        currency=trader.depositAssetId,  # TODO: map id to currency
        balance=_money(trader.balance, digits),
        leverage=trader.maxLeverage,
        is_live=is_live,
        money_digits=digits,
    )


def map_position(position: ProtoOAPosition, symbol_lookup: SymbolLookup) -> Position:
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOAOrderTriggerMethod,
        ProtoOAPositionStatus,
    )

    info = symbol_lookup(position.tradeData.symbolId)

    # Map stop loss trigger method if present (safely handle missing field)
    trigger_method = None
    try:
        if position.HasField("stopLossTriggerMethod"):
            trigger_method = ProtoOAOrderTriggerMethod.Name(position.stopLossTriggerMethod)
    except ValueError:
        pass

    # Map tradeData nested object
    trade_data = TradeData(
        symbol_id=position.tradeData.symbolId,
        volume=position.tradeData.volume,
        trade_side=ProtoOATradeSide.Name(position.tradeData.tradeSide),
        open_timestamp=position.tradeData.openTimestamp
        if position.tradeData.HasField("openTimestamp") else None,
        label=position.tradeData.label
        if position.tradeData.HasField("label") else None,
        guaranteed_stop_loss=position.tradeData.guaranteedStopLoss
        if position.tradeData.HasField("guaranteedStopLoss") else None,
        comment=position.tradeData.comment if position.tradeData.HasField("comment") else None,
        measurement_units=getattr(position.tradeData, "measurementUnits", None),
        close_timestamp=getattr(position.tradeData, "closeTimestamp", None),
    )

    return Position(
        # Required fields
        position_id=position.positionId,
        trade_data=trade_data,
        position_status=ProtoOAPositionStatus.Name(position.positionStatus),
        swap=position.swap,

        # Optional fields
        price=_decimal_or_none(position.price),
        stop_loss=_decimal_or_none(position.stopLoss),
        take_profit=_decimal_or_none(position.takeProfit),
        utc_last_update_timestamp=position.utcLastUpdateTimestamp if position.HasField(
            "utcLastUpdateTimestamp") else None,
        commission=position.commission if position.HasField("commission") else None,
        margin_rate=_decimal_or_none(position.marginRate),
        mirroring_commission=position.mirroringCommission if position.HasField(
            "mirroringCommission") else None,
        guaranteed_stop_loss=position.guaranteedStopLoss if position.HasField(
            "guaranteedStopLoss") else None,
        used_margin=position.usedMargin if position.HasField("usedMargin") else None,
        stop_loss_trigger_method=trigger_method,
        money_digits=position.moneyDigits if position.HasField("moneyDigits") else None,
        trailing_stop_loss=position.trailingStopLoss if position.HasField(
            "trailingStopLoss") else None,

        # Convenience fields
        symbol=info.symbol_name if info else None,
    )


def map_order(order: ProtoOAOrder, symbol_lookup: SymbolLookup) -> Order:
    """Map a ProtoOAOrder to an Order domain model following official ProtoOAOrder structure.

    See: https://help.ctrader.com/open-api/model-messages/#protooaorder
    """
    info = symbol_lookup(order.tradeData.symbolId)

    # Map trigger method if present
    trigger_method = None
    if order.HasField("stopTriggerMethod"):
        from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAOrderTriggerMethod
        trigger_method = ProtoOAOrderTriggerMethod.Name(order.stopTriggerMethod)

    # Map tradeData nested object
    trade_data = TradeData(symbol_id=order.tradeData.symbolId, volume=order.tradeData.volume,
                           trade_side=ProtoOATradeSide.Name(order.tradeData.tradeSide),
                           open_timestamp=order.tradeData.openTimestamp
                           if order.tradeData.HasField("openTimestamp") else None,
                           label=order.tradeData.label
                           if order.tradeData.HasField("label") else None,
                           guaranteed_stop_loss=order.tradeData.guaranteedStopLoss
                           if order.tradeData.HasField("guaranteedStopLoss") else None,
                           comment=order.tradeData.comment
                           if order.tradeData.HasField("comment") else None,
                           measurement_units=getattr(order.tradeData, "measurementUnits", None),
                           close_timestamp=getattr(order.tradeData, "closeTimestamp", None),)

    return Order(
        order_id=order.orderId,
        trade_data=trade_data,
        order_type=ProtoOAOrderType.Name(order.orderType),
        order_status=ProtoOAOrderStatus.Name(order.orderStatus),

        # Optional fields from ProtoOAOrder
        expiration_timestamp=order.expirationTimestamp if order.HasField(
            "expirationTimestamp") else None,
        execution_price=_decimal_or_none(order.executionPrice),
        executed_volume=order.executedVolume if order.HasField("executedVolume") else None,
        utc_last_update_timestamp=order.utcLastUpdateTimestamp if order.HasField(
            "utcLastUpdateTimestamp") else None,

        base_slippage_price=_decimal_or_none(order.baseSlippagePrice),
        slippage_in_points=order.slippageInPoints if order.HasField("slippageInPoints") else None,
        closing_order=order.closingOrder if order.HasField("closingOrder") else None,
        limit_price=_decimal_or_none(order.limitPrice),
        stop_price=_decimal_or_none(order.stopPrice),
        stop_loss=_decimal_or_none(order.stopLoss),
        take_profit=_decimal_or_none(order.takeProfit),

        client_order_id=order.clientOrderId if order.HasField("clientOrderId") else None,
        time_in_force=ProtoOATimeInForce.Name(
            order.timeInForce) if order.HasField("timeInForce") else None,
        position_id=order.positionId if order.HasField("positionId") else None,
        relative_stop_loss=order.relativeStopLoss if order.HasField("relativeStopLoss") else None,
        relative_take_profit=order.relativeTakeProfit if order.HasField(
            "relativeTakeProfit") else None,
        is_stop_out=order.isStopOut if order.HasField("isStopOut") else None,
        trailing_stop_loss=order.trailingStopLoss if order.HasField("trailingStopLoss") else None,
        stop_trigger_method=trigger_method,

        # Convenience fields
        symbol=info.symbol_name if info else None,
    )


def map_deal(deal: ProtoOADeal, symbol_lookup: SymbolLookup) -> Deal:
    """Map a ProtoOADeal to a Deal domain model.

    See: https://help.ctrader.com/open-api/model-messages/#protooadeal
    """
    symbol = symbol_lookup(deal.symbolId)

    # Map closePositionDetail if present
    close_detail = None
    if deal.HasField("closePositionDetail"):
        detail = deal.closePositionDetail
        close_detail = ClosePositionDetail(
            entry_price=Decimal(str(detail.entryPrice)),
            gross_profit=detail.grossProfit, swap=detail.swap, commission=detail.commission,
            balance=detail.balance,
            quote_to_deposit_conversion_rate=Decimal(str(detail.quoteToDepositConversionRate))
            if detail.HasField("quoteToDepositConversionRate") else None,
            closed_volume=detail.closedVolume if detail.HasField("closedVolume") else None,
            balance_version=detail.balanceVersion if detail.HasField("balanceVersion") else None,
            money_digits=detail.moneyDigits if detail.HasField("moneyDigits") else None,
            pnl_conversion_fee=detail.pnlConversionFee
            if detail.HasField("pnlConversionFee") else None,)

    return Deal(
        deal_id=deal.dealId,
        order_id=deal.orderId,
        position_id=deal.positionId,
        volume=deal.volume,
        filled_volume=deal.filledVolume,
        symbol_id=deal.symbolId,
        create_timestamp=deal.createTimestamp,
        execution_timestamp=deal.executionTimestamp,
        trade_side=ProtoOATradeSide.Name(deal.tradeSide),
        deal_status=ProtoOADealStatus.Name(deal.dealStatus),
        utc_last_update_timestamp=deal.utcLastUpdateTimestamp
        if deal.HasField("utcLastUpdateTimestamp")
        else None,
        execution_price=_decimal_or_none(deal.executionPrice),
        margin_rate=_decimal_or_none(deal.marginRate),
        commission=deal.commission if deal.HasField("commission") else None,
        base_to_usd_conversion_rate=_decimal_or_none(deal.baseToUsdConversionRate),
        close_position_detail=close_detail,
        money_digits=deal.moneyDigits if deal.HasField("moneyDigits") else None,
        label=getattr(deal, "label", None),
        comment=getattr(deal, "comment", None),
        symbol=symbol.symbol_name if symbol else None,
    )


def map_trendbar(
    bar: ProtoOATrendbar,
    bid_price: int | None = None,
    digits: int = 5,
) -> Trendbar:
    """Map a ProtoOATrendbar to a Trendbar domain model.

    Args:
        bar: The protobuf trendbar message.
        bid_price: Optional current bid price for live bars (overrides deltaClose).
        digits: Number of decimal places for price formatting.
    """
    scale = Decimal("100000")
    base_low = Decimal(bar.low)

    def calc_price(delta: int) -> Decimal:
        return (base_low + Decimal(delta)) / scale

    # For live trendbars from ProtoOASpotEvent, use the current bid price
    # as the close since it represents the latest market price.
    close_price = Decimal(
        bid_price) / scale if bid_price is not None else calc_price(bar.deltaClose)

    return Trendbar(
        o=calc_price(bar.deltaOpen),
        h=calc_price(bar.deltaHigh),
        l=base_low / scale,
        c=close_price,
        v=bar.volume,
        t=bar.utcTimestampInMinutes * 60 * 1000,
        digits=digits,
    )


def map_tick(event_bid: int, event_ask: int, timestamp: int, digits: int) -> Tick:
    """Map raw tick data to a Tick domain model.

    Note: cTrader ProtoOASpotEvent bid/ask values are always sent as integers
    with a fixed scale of 100000 (5 decimal places). The digits parameter is
    used to format the result to the symbol's configured precision.
    """
    scale = 100000
    bid = event_bid / scale
    ask = event_ask / scale
    return Tick(
        b=bid,
        a=ask,
        t=timestamp,
        digits=digits,
    )


def map_symbol_data(info: SymbolDescriptor, symbol_data) -> Symbol:
    """Map protobuf symbol data to a Symbol domain model."""
    commission_type_name = _extract_commission_type(symbol_data)
    return Symbol(
        symbol_id=int(info.symbol_id),
        symbol_name=info.symbol_name,
        digits=symbol_data.digits,
        pip_position=symbol_data.pipPosition,
        commission=getattr(symbol_data, "commission", 0),
        commission_type=commission_type_name,
    )


def resolve_timeframe(period: ProtoOATrendbarPeriod | int) -> Timeframe:
    """Convert a protobuf trendbar period to a Timeframe value object."""
    try:
        if isinstance(period, int):
            name = ProtoOATrendbarPeriod.Name(period)
        else:
            name = ProtoOATrendbarPeriod.Name(int(period))
        return Timeframe(name)
    except Exception:
        raise ValueError(f"Unsupported trendbar period value: {period}")


# ------------------------------------------------------------------ private helpers


def _extract_commission_type(symbol_data) -> str | None:
    """Extract commission type name from symbol data."""
    commission_type_val = getattr(symbol_data, "commissionType", None)
    if commission_type_val is None:
        return None
    try:
        return ProtoOACommissionType.Name(commission_type_val)
    except ValueError:
        return None


def _money(value: int, digits: int) -> Decimal:
    """Convert a raw money value to Decimal with proper decimal places."""
    return Decimal(value) / (Decimal(10) ** digits)


def _decimal_or_none(value: float | int | None) -> Decimal | None:
    """Convert a value to Decimal, or return None if the value is None."""
    if value is None:
        return None
    return Decimal(str(value))
