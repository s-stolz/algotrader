"""Public execution-log page schema and persistence reader wiring."""

from typing import Annotated, Any, Literal

from app.execution_log import ExecutionLogService
from db_accessor_client import DatabaseAccessorClient
from pydantic import BaseModel, Field

from adapters.api.schemas import BacktestTradeResponseSchema


class UnexecutedOrderSchema(BaseModel):
    order_id: str
    outcome: str
    side: Literal["buy", "sell"] | None
    planned_price: float | None = Field(allow_inf_nan=False)
    planned_quantity: float | None = Field(allow_inf_nan=False)


class TradeLogItemSchema(BaseModel):
    kind: Literal["trade"]
    timestamp_ms: int
    trade: BacktestTradeResponseSchema


class OrderLogItemSchema(BaseModel):
    kind: Literal["unexecuted_order"]
    timestamp_ms: int
    order: UnexecutedOrderSchema


class ExecutionLogPageSchema(BaseModel):
    run_id: str
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    items: list[Annotated[TradeLogItemSchema | OrderLogItemSchema, Field(discriminator="kind")]]


def get_execution_log_service() -> ExecutionLogService:
    def read_page(run_id: str, page: int, page_size: int, include: bool) -> dict[str, Any]:
        with DatabaseAccessorClient() as client:
            return client.get_backtest_execution_log(
                run_id, page=page, page_size=page_size, include_unexecuted=include
            )

    return ExecutionLogService(read_page)
