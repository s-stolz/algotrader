"""Transactional single-slot primitives for caller-owned backtest scheduling."""

from __future__ import annotations

from typing import Any, Mapping

from app.models import (
    backtest_closed_trades,
    backtest_commands,
    backtest_events,
    backtest_execution_slot,
    backtest_fills,
    backtest_queue_turns,
    backtest_runs,
    backtest_worker_heartbeats,
    backtests,
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
    # Serialize with claims so a delayed heartbeat cannot erase a newly claimed owner.
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
    existing = (
        (
            await session.execute(
                select(backtest_worker_heartbeats).where(
                    backtest_worker_heartbeats.c.worker_id == worker_id
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        existing is not None
        and slot["owner_token"] is not None
        and existing["owner_token"] == slot["owner_token"]
        and owner_token != slot["owner_token"]
    ):
        await session.commit()
        return dict(existing)
    statement = pg_insert(backtest_worker_heartbeats).values(
        worker_id=worker_id,
        owner_token=owner_token,
        heartbeat_at=func.clock_timestamp(),
        fault_code=fault_code,
        fault_message=fault_message,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[backtest_worker_heartbeats.c.worker_id],
        set_={
            "owner_token": statement.excluded.owner_token,
            "heartbeat_at": func.clock_timestamp(),
            "fault_code": statement.excluded.fault_code,
            "fault_message": statement.excluded.fault_message,
        },
    ).returning(backtest_worker_heartbeats)
    row = (await session.execute(statement)).mappings().one()
    await session.commit()
    return dict(row)


async def read_queue_state(session) -> dict:
    # All lifecycle mutations take the exclusive slot lock. Share it until the
    # reader's transaction closes so active ownership and turns cannot disagree.
    await session.execute(
        select(backtest_execution_slot.c.slot_id)
        .where(backtest_execution_slot.c.slot_id == 1)
        .with_for_update(read=True)
    )
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
                        backtest_runs.c.backtest_id,
                        backtest_runs.c.run_ordinal,
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
        backtest = (
            await session.execute(
                select(backtests.c.accepted_at).where(
                    backtests.c.backtest_id == turn["backtest_id"]
                )
            )
        ).scalar_one()
        members = (
            (
                await session.execute(
                    select(
                        backtest_runs.c.run_id,
                        backtest_runs.c.run_ordinal,
                        backtest_runs.c.status,
                    )
                    .where(backtest_runs.c.backtest_id == turn["backtest_id"])
                    .order_by(backtest_runs.c.run_ordinal)
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
                "run_id": next_member["run_id"],
                "backtest_id": turn["backtest_id"],
                "submitted_at": backtest,
                "next_run_ordinal": next_member["run_ordinal"],
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
        "queued_entries": entries,
    }


async def _seed_claim_heartbeat(session, *, worker_id: str, owner_token: str) -> None:
    heartbeat = pg_insert(backtest_worker_heartbeats).values(
        worker_id=worker_id,
        owner_token=owner_token,
        heartbeat_at=func.clock_timestamp(),
        fault_code=None,
        fault_message=None,
    )
    await session.execute(
        heartbeat.on_conflict_do_update(
            index_elements=[backtest_worker_heartbeats.c.worker_id],
            set_={
                "owner_token": owner_token,
                "heartbeat_at": func.clock_timestamp(),
                "fault_code": None,
                "fault_message": None,
            },
        )
    )


async def claim(session, *, run_id: str, owner_token: str, started_at, worker_id: str) -> bool:
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
        backtest = (
            await session.execute(
                select(backtests.c.status, backtests.c.started_at)
                .where(backtests.c.backtest_id == turn["backtest_id"])
                .with_for_update()
            )
        ).one()
        if backtest.status not in {"queued", "running"}:
            await session.rollback()
            return False
        selected_run_id = (
            await session.execute(
                select(backtest_runs.c.run_id)
                .where(
                    backtest_runs.c.backtest_id == turn["backtest_id"],
                    backtest_runs.c.status == "queued",
                )
                .order_by(backtest_runs.c.run_ordinal)
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
        if backtest.started_at is None:
            await _transition_backtest(
                session,
                turn["backtest_id"],
                "running",
                "started",
                started_at,
                run_id,
                started_at=started_at,
            )
        await _seed_claim_heartbeat(session, worker_id=worker_id, owner_token=owner_token)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return True


async def _transition_backtest(
    session,
    backtest_id: str,
    status: str,
    event_type: str,
    occurred_at,
    trigger_run_id: str | None,
    reason: str | None = None,
    command_id: str | None = None,
    **timestamps,
) -> None:
    current = (
        await session.execute(
            select(backtests.c.lifecycle_revision, backtests.c.status)
            .where(backtests.c.backtest_id == backtest_id)
            .with_for_update()
        )
    ).one()
    revision = current.lifecycle_revision + 1
    await session.execute(
        update(backtests)
        .where(backtests.c.backtest_id == backtest_id)
        .values(status=status, lifecycle_revision=revision, **timestamps)
    )
    await session.execute(
        insert(backtest_events).values(
            backtest_id=backtest_id,
            revision=revision,
            event_type=event_type,
            prior_status=current.status,
            status=status,
            occurred_at=occurred_at,
            trigger_run_id=trigger_run_id,
            reason=reason,
            command_id=command_id,
        )
    )


class BacktestCommandConflictError(ValueError):
    pass


async def _active_member_matches(session, run_id: str | None, backtest_id: str) -> bool:
    if run_id is None:
        return False
    return (
        await session.execute(
            select(backtest_runs.c.run_id).where(
                backtest_runs.c.run_id == run_id,
                backtest_runs.c.backtest_id == backtest_id,
                backtest_runs.c.status.in_(["running", "cancelling"]),
            )
        )
    ).first() is not None


def _control_target(policy: Mapping[str, Any], status: str, active: bool) -> str | None:
    if status in policy["effective_statuses"]:
        return None
    if status not in policy["accepted_statuses"]:
        raise BacktestCommandConflictError("Backtest is no longer controllable")
    return policy["active_status"] if active else policy["idle_status"]


def _command_result(
    backtest_id: str, command: str, command_id: str, status: str, revision: int
) -> dict:
    result = {"backtest_id": backtest_id, "status": status, "lifecycle_revision": revision}
    if command == "cancel":
        result["command_id"] = command_id
    return result


async def _apply_backtest_cancellation(
    session, backtest_id: str, command: str, prior_status: str, next_status: str, occurred_at
) -> None:
    if command != "cancel" or next_status == prior_status:
        return
    await session.execute(
        update(backtest_runs)
        .where(backtest_runs.c.backtest_id == backtest_id, backtest_runs.c.status == "queued")
        .values(
            status="cancelled",
            cancel_requested_at=occurred_at,
            cancellation_source="backtest",
            cancellation_reason="backtest_cancel_requested",
            completed_at=occurred_at,
        )
    )
    await session.execute(
        update(backtest_runs)
        .where(backtest_runs.c.backtest_id == backtest_id, backtest_runs.c.status == "running")
        .values(
            status="cancelling",
            cancel_requested_at=occurred_at,
            cancellation_source="backtest",
            cancellation_reason="backtest_cancel_requested",
        )
    )


def _command_timestamps(command: str, next_status: str, occurred_at) -> dict:
    if command != "cancel":
        return {}
    timestamps = {
        "cancel_requested_at": occurred_at,
        "cancellation_source": "user",
        "cancellation_reason": "user_requested",
    }
    if next_status == "cancelled":
        timestamps["completed_at"] = occurred_at
    return timestamps


async def control_backtest(
    session, *, backtest_id: str, command: str, command_id: str, policy: Mapping[str, Any]
) -> dict | None:
    """Serialize a control command with claims and settlement at the slot boundary."""
    if command not in {"pause", "resume", "cancel"}:
        raise ValueError("Unknown backtest command")
    try:
        slot = (
            await session.execute(
                select(backtest_execution_slot.c.run_id)
                .where(backtest_execution_slot.c.slot_id == 1)
                .with_for_update()
            )
        ).one()
        backtest = (
            await session.execute(
                select(backtests.c.status, backtests.c.lifecycle_revision)
                .where(backtests.c.backtest_id == backtest_id)
                .with_for_update()
            )
        ).one_or_none()
        if backtest is None:
            await session.rollback()
            return None
        prior = (
            await session.execute(
                select(
                    backtest_commands.c.command,
                    backtest_commands.c.status,
                    backtest_commands.c.lifecycle_revision,
                ).where(
                    backtest_commands.c.backtest_id == backtest_id,
                    backtest_commands.c.command_id == command_id,
                )
            )
        ).one_or_none()
        if prior is not None:
            await session.rollback()
            if prior.command != command:
                raise BacktestCommandConflictError("Command identity belongs to another action")
            return _command_result(
                backtest_id, command, command_id, prior.status, prior.lifecycle_revision
            )
        active = await _active_member_matches(session, slot.run_id, backtest_id)
        next_status = _control_target(policy, backtest.status, active)
        if next_status is None:
            next_status = backtest.status
            revision = backtest.lifecycle_revision
        else:
            revision = backtest.lifecycle_revision + 1
        if next_status != backtest.status and policy["queue_action"] == "remove":
            await session.execute(
                delete(backtest_queue_turns).where(
                    backtest_queue_turns.c.backtest_id == backtest_id
                )
            )
        elif next_status != backtest.status and not active:
            await session.execute(insert(backtest_queue_turns).values(backtest_id=backtest_id))
        occurred_at = (await session.execute(select(func.now()))).scalar_one()
        await _apply_backtest_cancellation(
            session, backtest_id, command, backtest.status, next_status, occurred_at
        )
        if next_status != backtest.status:
            await _transition_backtest(
                session,
                backtest_id,
                next_status,
                command,
                occurred_at,
                None,
                command_id=command_id,
                **_command_timestamps(command, next_status, occurred_at),
            )
        await session.execute(
            insert(backtest_commands).values(
                backtest_id=backtest_id,
                command_id=command_id,
                command=command,
                status=next_status,
                lifecycle_revision=revision,
                occurred_at=occurred_at,
            )
        )
        await session.commit()
        return _command_result(backtest_id, command, command_id, next_status, revision)
    except Exception:
        await session.rollback()
        raise


async def _reconcile_backtest_after_run(session, backtest_id: str, run_id: str, at) -> None:
    backtest_status = (
        await session.execute(
            select(backtests.c.status)
            .where(backtests.c.backtest_id == backtest_id)
            .with_for_update()
        )
    ).scalar_one()
    statuses = (
        (
            await session.execute(
                select(backtest_runs.c.status).where(backtest_runs.c.backtest_id == backtest_id)
            )
        )
        .scalars()
        .all()
    )
    queued = "queued" in statuses
    active = any(status in {"running", "cancelling"} for status in statuses)
    if not queued and not active:
        await session.execute(
            delete(backtest_queue_turns).where(backtest_queue_turns.c.backtest_id == backtest_id)
        )
        terminal_status = "cancelled" if backtest_status == "cancelling" else "completed"
        if backtest_status != terminal_status:
            await _transition_backtest(
                session,
                backtest_id,
                terminal_status,
                terminal_status,
                at,
                run_id,
                completed_at=at,
            )
    elif backtest_status == "pausing" and not active:
        await _transition_backtest(session, backtest_id, "paused", "paused", at, run_id)
    elif queued and backtest_status in {"queued", "running"}:
        existing_turn = (
            await session.execute(
                select(backtest_queue_turns.c.turn_id)
                .where(backtest_queue_turns.c.backtest_id == backtest_id)
                .limit(1)
            )
        ).first()
        if existing_turn is None and not active:
            await session.execute(insert(backtest_queue_turns).values(backtest_id=backtest_id))


async def cancel_run(session, *, run_id: str, requested_at) -> str:
    """Accept one user cancellation in slot order; never release active capacity."""
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
        run = (
            (
                await session.execute(
                    select(backtest_runs.c.status, backtest_runs.c.backtest_id)
                    .where(backtest_runs.c.run_id == run_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if run is None:
            await session.rollback()
            return "not_found"
        if run["status"] in {"cancelling", "cancelled"}:
            await session.rollback()
            return "accepted"
        if run["status"] in {"succeeded", "failed"}:
            await session.rollback()
            return "conflict"
        if run["status"] == "running" and (slot["run_id"] != run_id or slot["owner_token"] is None):
            await session.rollback()
            return "ownership_unconfirmed"
        queued = run["status"] == "queued"
        await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == run["status"])
            .values(
                status="cancelled" if queued else "cancelling",
                cancel_requested_at=requested_at,
                cancellation_source="user",
                cancellation_reason="user_requested",
                completed_at=requested_at if queued else None,
            )
        )
        backtest_status = (
            await session.execute(
                select(backtests.c.status).where(backtests.c.backtest_id == run["backtest_id"])
            )
        ).scalar_one()
        await _transition_backtest(
            session,
            run["backtest_id"],
            backtest_status,
            "member_cancelled" if queued else "member_cancel_requested",
            requested_at,
            run_id,
            reason="user_requested",
        )
        if queued:
            await _reconcile_backtest_after_run(session, run["backtest_id"], run_id, requested_at)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return "accepted"


async def settle(session, *, run_id: str, owner_token: str, terminal: dict) -> bool:
    """Fence a terminal write and release capacity only after all rows commit."""

    data = dict(terminal)
    fills = data.pop("fills", [])
    trades = data.pop("trades", [])
    status = data.pop("status")
    if status not in {"succeeded", "failed", "cancelled"}:
        raise ValueError("invalid terminal status")
    if status == "cancelled" and (
        fills
        or trades
        or any(
            data.get(key) is not None
            for key in (
                "error_code",
                "error_message",
                "result_schema_version",
                "metrics",
                "diagnostics",
                "replay_descriptor",
            )
        )
    ):
        raise ValueError("cancelled run cannot have result artifacts")
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
        backtest_id = (
            await session.execute(
                select(backtest_runs.c.backtest_id).where(backtest_runs.c.run_id == run_id)
            )
        ).scalar_one()
        stored_data = {key: value for key, value in data.items() if value is not None}
        expected_status = "cancelling" if status == "cancelled" else "running"
        run = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.run_id == run_id, backtest_runs.c.status == expected_status)
            .values(status=status, **stored_data)
        )
        if run.rowcount != 1:
            await session.rollback()
            return False
        if fills:
            await session.execute(
                insert(backtest_fills), [{"run_id": run_id, **fill} for fill in fills]
            )
        if trades:
            await session.execute(
                insert(backtest_closed_trades),
                [{"run_id": run_id, **trade} for trade in trades],
            )
        await _reconcile_backtest_after_run(session, backtest_id, run_id, data["completed_at"])
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
                    select(backtest_runs.c.run_id, backtest_runs.c.backtest_id).where(
                        backtest_runs.c.status.in_(("running", "cancelling"))
                    )
                )
            )
            .mappings()
            .all()
        )
        failed = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.status == "running")
            .values(
                status="failed",
                completed_at=completed_at,
                error_code=error_code,
                error_message=error_message,
            )
        )
        cancelled = await session.execute(
            update(backtest_runs)
            .where(backtest_runs.c.status == "cancelling")
            .values(status="cancelled", completed_at=completed_at)
        )
        for run in interrupted:
            await _reconcile_backtest_after_run(
                session, run["backtest_id"], run["run_id"], completed_at
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return failed.rowcount + cancelled.rowcount


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
