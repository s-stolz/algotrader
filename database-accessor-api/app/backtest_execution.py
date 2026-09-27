"""Transactional single-slot primitives for caller-owned backtest scheduling."""

from __future__ import annotations

from app.models import (
    backtest_batch_events,
    backtest_batches,
    backtest_closed_trades,
    backtest_execution_slot,
    backtest_fills,
    backtest_queue_turns,
    backtest_runs,
    backtest_worker_heartbeats,
)
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert


async def read_slot(session) -> dict:
    slot_query = select(
        backtest_execution_slot.c.owner_token,
        backtest_execution_slot.c.run_id,
        backtest_execution_slot.c.fault_code,
        backtest_execution_slot.c.fault_message,
    )
    row = (await session.execute(slot_query)).mappings().one()
    return dict(row)


async def record_heartbeat(
    session,
    *,
    worker_id: str,
    owner_token: str | None,
    fault_code: str | None,
    fault_message: str | None,
) -> dict:
    # The database clock is authoritative; a worker cannot claim freshness with its own clock.
    statement = pg_insert(backtest_worker_heartbeats).values(
        worker_id=worker_id,
        owner_token=owner_token,
        heartbeat_at=func.now(),
        fault_code=fault_code,
        fault_message=fault_message,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[backtest_worker_heartbeats.c.worker_id],
        set_={
            "owner_token": statement.excluded.owner_token,
            "heartbeat_at": func.now(),
            "fault_code": statement.excluded.fault_code,
            "fault_message": statement.excluded.fault_message,
        },
    ).returning(backtest_worker_heartbeats)
    row = (await session.execute(statement)).mappings().one()
    await session.commit()
    return dict(row)


async def read_queue_state(session) -> dict:
    snapshot_at = (await session.execute(select(func.now()))).scalar_one()
    slot = await read_slot(session)
    active = None
    if slot["run_id"] is not None:
        active_row = (
            (
                await session.execute(
                    select(
                        backtest_runs.c.run_id,
                        backtest_runs.c.started_at,
                        backtest_runs.c.batch_id,
                        backtest_runs.c.member_ordinal,
                    ).where(backtest_runs.c.run_id == slot["run_id"])
                )
            )
            .mappings()
            .one_or_none()
        )
        active = dict(active_row) if active_row else None
    heartbeat_query = select(backtest_worker_heartbeats)
    if slot["owner_token"] is not None:
        heartbeat_query = heartbeat_query.where(
            backtest_worker_heartbeats.c.owner_token == slot["owner_token"]
        )
    heartbeats = (
        (
            await session.execute(
                heartbeat_query.order_by(backtest_worker_heartbeats.c.heartbeat_at.desc()).limit(1)
            )
        )
        .mappings()
        .all()
    )
    turns = (
        (
            await session.execute(
                select(backtest_queue_turns).order_by(backtest_queue_turns.c.turn_id)
            )
        )
        .mappings()
        .all()
    )
    entries = []
    for turn in turns:
        if turn["batch_id"] is None:
            run = (
                await session.execute(
                    select(backtest_runs.c.submitted_at).where(
                        backtest_runs.c.run_id == turn["run_id"]
                    )
                )
            ).scalar_one()
            entries.append(
                {
                    "entry_type": "standalone",
                    "run_id": turn["run_id"],
                    "batch_id": None,
                    "submitted_at": run,
                    "next_member_ordinal": None,
                    "outcome_counts": None,
                }
            )
            continue
        batch = (
            await session.execute(
                select(backtest_batches.c.accepted_at).where(
                    backtest_batches.c.batch_id == turn["batch_id"]
                )
            )
        ).scalar_one()
        members = (
            (
                await session.execute(
                    select(
                        backtest_runs.c.run_id,
                        backtest_runs.c.member_ordinal,
                        backtest_runs.c.status,
                    )
                    .where(backtest_runs.c.batch_id == turn["batch_id"])
                    .order_by(backtest_runs.c.member_ordinal)
                )
            )
            .mappings()
            .all()
        )
        next_member = next((member for member in members if member["status"] == "queued"), None)
        if next_member is None:
            continue
        entries.append(
            {
                "entry_type": "batch",
                "run_id": next_member["run_id"],
                "batch_id": turn["batch_id"],
                "submitted_at": batch,
                "next_member_ordinal": next_member["member_ordinal"],
                "outcome_counts": {
                    status: sum(member["status"] == status for member in members)
                    for status in (
                        "queued",
                        "running",
                        "cancelling",
                        "succeeded",
                        "failed",
                        "cancelled",
                    )
                },
            }
        )
    return {
        "snapshot_at": snapshot_at,
        "slot": slot,
        "active_run": active,
        "heartbeats": [dict(row) for row in heartbeats],
        "queued_runs": [
            {"run_id": entry["run_id"], "submitted_at": entry["submitted_at"]}
            for entry in entries
            if entry["entry_type"] == "standalone"
        ],
        "queued_entries": entries,
    }


async def claim(session, *, run_id: str, owner_token: str, started_at) -> bool:
    """Serialize global queue selection and slot ownership in one transaction."""
    try:
        slot = (
            (
                await session.execute(
                    select(backtest_execution_slot)
                    .where(backtest_execution_slot.c.slot_id == 1)
                    .with_for_update()
                )
            )
            .mappings()
            .one()
        )
        if slot["owner_token"] is not None or slot["fault_code"] is not None:
            await session.rollback()
            return False
        if (
            await session.execute(
                select(backtest_runs.c.run_id).where(backtest_runs.c.status == "running").limit(1)
            )
        ).first() is not None:
            await session.rollback()
            return False
        turn = (
            (
                await session.execute(
                    select(backtest_queue_turns)
                    .order_by(backtest_queue_turns.c.turn_id)
                    .limit(1)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if turn is None:
            await session.rollback()
            return False
        if turn["batch_id"] is None:
            selected_run_id = turn["run_id"]
        else:
            batch = (
                await session.execute(
                    select(backtest_batches.c.status)
                    .where(backtest_batches.c.batch_id == turn["batch_id"])
                    .with_for_update()
                )
            ).scalar_one()
            if batch not in {"queued", "running"}:
                await session.rollback()
                return False
            selected_run_id = (
                await session.execute(
                    select(backtest_runs.c.run_id)
                    .where(
                        backtest_runs.c.batch_id == turn["batch_id"],
                        backtest_runs.c.status == "queued",
                    )
                    .order_by(backtest_runs.c.member_ordinal)
                    .limit(1)
                )
            ).scalar_one_or_none()
        if selected_run_id != run_id:
            await session.rollback()
            return False
        await session.execute(
            update(backtest_execution_slot)
            .where(backtest_execution_slot.c.slot_id == 1)
            .values(owner_token=owner_token, run_id=run_id, updated_at=started_at)
        )
        run = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == "queued")
            .values(status="running", started_at=started_at)
        )
        if run.rowcount != 1:
            await session.rollback()
            return False
        await session.execute(
            delete(backtest_queue_turns).where(backtest_queue_turns.c.turn_id == turn["turn_id"])
        )
        if turn["batch_id"] is not None and batch == "queued":
            await _transition_batch(
                session,
                turn["batch_id"],
                "running",
                "started",
                started_at,
                run_id,
                started_at=started_at,
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return True


async def _transition_batch(
    session,
    batch_id: str,
    status: str,
    event_type: str,
    occurred_at,
    trigger_run_id: str,
    **timestamps,
) -> None:
    current = (
        await session.execute(
            select(backtest_batches.c.lifecycle_revision, backtest_batches.c.status)
            .where(backtest_batches.c.batch_id == batch_id)
            .with_for_update()
        )
    ).one()
    revision = current.lifecycle_revision + 1
    await session.execute(
        update(backtest_batches)
        .where(backtest_batches.c.batch_id == batch_id)
        .values(status=status, lifecycle_revision=revision, **timestamps)
    )
    await session.execute(
        insert(backtest_batch_events).values(
            batch_id=batch_id,
            revision=revision,
            event_type=event_type,
            prior_status=current.status,
            status=status,
            occurred_at=occurred_at,
            trigger_run_id=trigger_run_id,
        )
    )


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
        batch_id = (
            await session.execute(
                select(backtest_runs.c.batch_id).where(backtest_runs.c.run_id == run_id)
            )
        ).scalar_one()
        stored_data = {key: value for key, value in data.items() if value is not None}
        run = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == "running")
            .values(status=status, **stored_data)
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
        if batch_id is not None:
            remaining = (
                await session.execute(
                    select(backtest_runs.c.run_id)
                    .where(
                        backtest_runs.c.batch_id == batch_id,
                        backtest_runs.c.status == "queued",
                    )
                    .limit(1)
                )
            ).first()
            if remaining is not None:
                await session.execute(insert(backtest_queue_turns).values(batch_id=batch_id))
            else:
                await _transition_batch(
                    session,
                    batch_id,
                    "completed",
                    "completed",
                    data["completed_at"],
                    run_id,
                    completed_at=data["completed_at"],
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
        interrupted = (
            (
                await session.execute(
                    select(backtest_runs.c.run_id, backtest_runs.c.batch_id).where(
                        backtest_runs.c.status == "running"
                    )
                )
            )
            .mappings()
            .all()
        )
        result = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.status == "running")
            .values(
                status="failed",
                completed_at=completed_at,
                error_code=error_code,
                error_message=error_message,
            )
        )
        for run in interrupted:
            if run["batch_id"] is None:
                continue
            batch_id = run["batch_id"]
            remaining = (
                await session.execute(
                    select(backtest_runs.c.run_id)
                    .where(
                        backtest_runs.c.batch_id == batch_id,
                        backtest_runs.c.status == "queued",
                    )
                    .limit(1)
                )
            ).first()
            if remaining is not None:
                await session.execute(insert(backtest_queue_turns).values(batch_id=batch_id))
            else:
                await _transition_batch(
                    session,
                    batch_id,
                    "completed",
                    "completed",
                    completed_at,
                    run["run_id"],
                    completed_at=completed_at,
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
