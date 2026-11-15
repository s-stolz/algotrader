from unittest.mock import AsyncMock, Mock


def live_market_resolver(symbol="EURUSD"):
    return Mock(
        account_id="123",
        resolve=AsyncMock(return_value={"symbol_id": 1, "symbol": symbol, "exchange": "BROKER"}),
        dependencies=AsyncMock(return_value=[]),
    )
