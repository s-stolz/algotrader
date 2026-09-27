"""Transactional single-slot primitives for caller-owned backtest scheduling."""

from __future__ import annotations

from app.models import (
    backtest_closed_trades,
    backtest_execution_slot,
    backtest_fills,
    backtest_runs,
)
from sqlalchemy import func, insert, select, update


async def read_slot(session) -> dict:
    slot_query = select(
        backtest_execution_slot.c.owner_token,
        backtest_execution_slot.c.run_id,
        backtest_execution_slot.c.fault_code,
        backtest_execution_slot.c.fault_message,
    )
    row = (await session.execute(slot_query)).mappings().one()
    return dict(row)


async def claim(session, *, run_id: str, owner_token: str, started_at) -> bool:
    """Reserve the slot and claim only the oldest queued run in one transaction."""

    oldest_queued = (
        select(backtest_runs.c.run_id)
        .where(backtest_runs.c.status == "queued", backtest_runs.c.batch_id.is_(None))
        .order_by(backtest_runs.c.submitted_at.asc(), backtest_runs.c.run_id.asc())
        .limit(1)
        .scalar_subquery()
    )
    try:
        slot = await session.execute(
            update(backtest_execution_slot)
            .where(
                backtest_execution_slot.c.slot_id == 1,
                backtest_execution_slot.c.owner_token.is_(None),
                backtest_execution_slot.c.run_id.is_(None),
                backtest_execution_slot.c.fault_code.is_(None),
                oldest_queued == run_id,
                ~select(backtest_runs.c.run_id).where(backtest_runs.c.status == "running").exists(),
            )
            .values(owner_token=owner_token, run_id=run_id, updated_at=started_at)
        )
        if slot.rowcount != 1:
            await session.rollback()
            return False
        run = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == "queued")
            .values(status="running", started_at=started_at)
        )
        if run.rowcount != 1:
            await session.rollback()
            return False
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return True


async def settle(session, *, run_id: str, owner_token: str, terminal: dict) -> bool:
    """Fence a terminal write and release capacity only after all rows commit."""

    data = dict(terminal)
    fills = data.pop("fills", [])
    trades = data.pop("trades", [])
    status = data.pop("status")
    if status not in {"succeeded", "failed"}:
        raise ValueError("terminal status must be succeeded or failed")
    if status == "failed" and (
        fills
        or trades
        or data.get("result_schema_version") is not None
        or data.get("metrics") is not None
        or data.get("diagnostics") is not None
        or data.get("replay_descriptor") is not None
    ):
        raise ValueError("failed run cannot have result artifacts")

    try:
        slot = await session.execute(
            select(backtest_execution_slot.c.slot_id)
            .where(
                backtest_execution_slot.c.slot_id == 1,
                backtest_execution_slot.c.owner_token == owner_token,
                backtest_execution_slot.c.run_id == run_id,
            )
            .with_for_update()
        )
        if slot.first() is None:
            await session.rollback()
            return False
        run = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == "running")
            .values(status=status, **data)
        )
        if run.rowcount != 1:
            await session.rollback()
            return False
        if fills:
            await session.execute(
                insert(backtest_fills).values([{"run_id": run_id, **fill} for fill in fills])
            )
        if trades:
            await session.execute(
                insert(backtest_closed_trades).values(
                    [{"run_id": run_id, **trade} for trade in trades]
                )
            )
        await session.execute(
            update(backtest_execution_slot)
            .where(backtest_execution_slot.c.slot_id == 1)
            .values(owner_token=None, run_id=None, updated_at=data["completed_at"])
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return True


async def reconcile(session, *, completed_at, error_code: str, error_message: str) -> int | None:
    """Fail interrupted work only after an operator has verified and cleared a held slot."""

    try:
        slot = await session.execute(
            select(backtest_execution_slot.c.owner_token, backtest_execution_slot.c.fault_code)
            .where(backtest_execution_slot.c.slot_id == 1)
            .with_for_update()
        )
        owner_token, fault_code = slot.one()
        if owner_token is not None or fault_code is not None:
            await session.rollback()
            return None
        result = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.status == "running", backtest_runs.c.batch_id.is_(None))
            .values(
                status="failed",
                completed_at=completed_at,
                error_code=error_code,
                error_message=error_message,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return result.rowcount


async def record_fault(session, *, run_id: str, owner_token: str, code: str, message: str) -> bool:
    try:
        result = await session.execute(
            update(backtest_execution_slot)
            .where(
                backtest_execution_slot.c.slot_id == 1,
                backtest_execution_slot.c.owner_token == owner_token,
                backtest_execution_slot.c.run_id == run_id,
            )
            .values(fault_code=code, fault_message=message, updated_at=func.now())
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return result.rowcount == 1
