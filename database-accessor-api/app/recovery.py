"""Transactional pending M1 recovery, independent of ingestion retry policy."""

from uuid import uuid4

from app.models import pending_recoveries
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert


async def load_recovery(session, symbol_id: int, account_id: str):
    result = await session.execute(
        select(pending_recoveries).where(
            pending_recoveries.c.symbol_id == symbol_id,
            pending_recoveries.c.account_id == account_id,
        )
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def begin_recovery(
    session, symbol_id: int, account_id: str, start_ms: int, target_ms: int, trigger: str
):
    from sqlalchemy import func

    statement = insert(pending_recoveries).values(
        symbol_id=symbol_id,
        account_id=account_id,
        recovery_id=str(uuid4()),
        revision=1,
        next_ms=start_ms,
        target_ms=target_ms,
        trigger=trigger,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["symbol_id", "account_id"],
        set_={
            "revision": pending_recoveries.c.revision + 1,
            "next_ms": func.least(pending_recoveries.c.next_ms, start_ms),
            "target_ms": func.greatest(pending_recoveries.c.target_ms, target_ms),
            "trigger": trigger,
        },
    ).returning(pending_recoveries)
    try:
        result = await session.execute(statement)
        row = dict(result.mappings().one())
        await session.commit()
        return row
    except Exception:
        await session.rollback()
        raise


async def advance_recovery(session, symbol_id: int, account_id: str, data):
    table = pending_recoveries
    condition = (
        (table.c.symbol_id == symbol_id)
        & (table.c.account_id == account_id)
        & (table.c.recovery_id == data.recovery_id)
        & (table.c.revision == data.revision)
        & (table.c.next_ms == data.expected_start_ms)
        & (data.next_ms <= table.c.target_ms + 1)
    )
    # The same conditional predicate protects both progress and completion.
    try:
        completed = await session.execute(
            delete(table)
            .where(condition, table.c.target_ms < data.next_ms)
            .returning(table.c.recovery_id)
        )
        updated = completed.first() is not None
        if not updated:
            progress = await session.execute(
                update(table)
                .where(condition)
                .values(next_ms=data.next_ms)
                .returning(table.c.recovery_id)
            )
            updated = progress.first() is not None
        await session.commit()
        return updated
    except Exception:
        await session.rollback()
        raise
