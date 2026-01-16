from app.application.interfaces import BrokerPort
from app.domain.value_objects import AccountId, PositionId
from app.domain.models import Deal


class PositionService:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    async def close_position(
        self,
        account_id: AccountId,
        position_id: PositionId,
        close_volume: int | None = None,
    ):
        return await self._broker.close_position(account_id, position_id, close_volume)

    async def get_open_positions(self, account_id: AccountId):
        return await self._broker.get_open_positions(account_id)

    async def get_deal_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Deal]:
        return await self._broker.get_deal_history(account_id, from_ts, to_ts)
