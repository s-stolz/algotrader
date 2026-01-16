from app.application.interfaces import BrokerPort
from app.domain.value_objects import AccountId, OrderId


class OrderService:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    async def place_order(self, account_id: AccountId, payload: dict):
        return await self._broker.place_order(account_id, payload)

    async def cancel_order(self, account_id: AccountId, order_id: OrderId) -> None:
        await self._broker.cancel_order(account_id, order_id)

    async def get_open_orders(self, account_id: AccountId):
        return await self._broker.get_open_orders(account_id)

    async def get_order_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ):
        return await self._broker.get_order_history(account_id, from_ts, to_ts)
