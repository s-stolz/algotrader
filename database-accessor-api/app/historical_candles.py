"""Authoritative closed M1 persistence; ordinary live inserts remain insert-only."""

from datetime import datetime, timezone

from app.models import candles
from sqlalchemy.dialects.postgresql import insert


async def write_historical_candles(session, symbol_id: int, values: list[dict]) -> int:
    if not values:
        return 0
    # Collapse repeated timestamps before PostgreSQL's single-statement upsert.
    by_timestamp = {value["timestamp_ms"]: value for value in values}
    rows = [
        {
            "symbol_id": symbol_id,
            "timestamp_utc": datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
            **{field: value[field] for field in ("open", "high", "low", "close", "volume")},
        }
        for timestamp, value in sorted(by_timestamp.items())
    ]
    statement = insert(candles).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["symbol_id", "timestamp_utc"],
        set_={
            field: getattr(statement.excluded, field)
            for field in ("open", "high", "low", "close", "volume")
        },
    )
    try:
        result = await session.execute(statement)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return result.rowcount
