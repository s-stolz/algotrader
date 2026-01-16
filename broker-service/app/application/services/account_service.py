from app.application.interfaces import BrokerPort
from app.domain.models import Account


class AccountService:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    async def list_accounts(self) -> list[Account]:
        return await self._broker.list_accounts()
