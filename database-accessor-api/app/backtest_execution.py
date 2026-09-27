"""Transactional single-slot primitives for caller-owned backtest scheduling."""

from __future__ import annotations

from typing import Any, Mapping

from app.models import (
    backtest_batch_commands,
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
    trigger_run_id: str | None,
    reason: str | None = None,
    command_id: str | None = None,
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
            reason=reason,
            command_id=command_id,
        )
    )


class BatchCommandConflictError(ValueError):
    pass


async def _active_member_matches(session, run_id: str | None, batch_id: str) -> bool:
    if run_id is None:
        return False
    return (
        await session.execute(
            select(backtest_runs.c.run_id).where(
                backtest_runs.c.run_id == run_id,
                backtest_runs.c.batch_id == batch_id,
                backtest_runs.c.status.in_(["running", "cancelling"]),
            )
        )
    ).first() is not None


def _control_target(policy: Mapping[str, Any], status: str, active: bool) -> str | None:
    if status in policy["effective_statuses"]:
        return None
    if status not in policy["accepted_statuses"]:
        raise BatchCommandConflictError("Batch is no longer controllable")
    return policy["active_status"] if active else policy["idle_status"]


def _command_result(
    batch_id: str, command: str, command_id: str, status: str, revision: int
) -> dict:
    result = {"batch_id": batch_id, "status": status, "lifecycle_revision": revision}
    if command == "cancel":
        result["command_id"] = command_id
    return result


async def _apply_batch_cancellation(
    session, batch_id: str, command: str, prior_status: str, next_status: str, occurred_at
) -> None:
    if command != "cancel" or next_status == prior_status:
        return
    await session.execute(
        update(backtest_runs)
        .where(backtest_runs.c.batch_id == batch_id, backtest_runs.c.status == "queued")
        .values(
            status="cancelled",
            cancel_requested_at=occurred_at,
            cancellation_source="batch",
            cancellation_reason="batch_cancel_requested",
            completed_at=occurred_at,
        )
    )
    await session.execute(
        update(backtest_runs)
        .where(backtest_runs.c.batch_id == batch_id, backtest_runs.c.status == "running")
        .values(
            status="cancelling",
            cancel_requested_at=occurred_at,
            cancellation_source="batch",
            cancellation_reason="batch_cancel_requested",
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


async def control_batch(
    session, *, batch_id: str, command: str, command_id: str, policy: Mapping[str, Any]
) -> dict | None:
    """Serialize a control command with claims and settlement at the slot boundary."""
    if command not in {"pause", "resume", "cancel"}:
        raise ValueError("Unknown batch command")
    try:
        slot = (
            await session.execute(
                select(backtest_execution_slot.c.run_id)
                .where(backtest_execution_slot.c.slot_id == 1)
                .with_for_update()
            )
        ).one()
        batch = (
            await session.execute(
                select(backtest_batches.c.status, backtest_batches.c.lifecycle_revision)
                .where(backtest_batches.c.batch_id == batch_id)
                .with_for_update()
            )
        ).one_or_none()
        if batch is None:
            await session.rollback()
            return None
        prior = (
            await session.execute(
                select(
                    backtest_batch_commands.c.command,
                    backtest_batch_commands.c.status,
                    backtest_batch_commands.c.lifecycle_revision,
                ).where(
                    backtest_batch_commands.c.batch_id == batch_id,
                    backtest_batch_commands.c.command_id == command_id,
                )
            )
        ).one_or_none()
        if prior is not None:
            await session.rollback()
            if prior.command != command:
                raise BatchCommandConflictError("Command identity belongs to another action")
            return _command_result(
                batch_id, command, command_id, prior.status, prior.lifecycle_revision
            )
        active = await _active_member_matches(session, slot.run_id, batch_id)
        next_status = _control_target(policy, batch.status, active)
        if next_status is None:
            next_status = batch.status
            revision = batch.lifecycle_revision
        else:
            revision = batch.lifecycle_revision + 1
        if next_status != batch.status and policy["queue_action"] == "remove":
            await session.execute(
                delete(backtest_queue_turns).where(backtest_queue_turns.c.batch_id == batch_id)
            )
        elif next_status != batch.status and not active:
            await session.execute(insert(backtest_queue_turns).values(batch_id=batch_id))
        occurred_at = (await session.execute(select(func.now()))).scalar_one()
        await _apply_batch_cancellation(
            session, batch_id, command, batch.status, next_status, occurred_at
        )
        if next_status != batch.status:
            await _transition_batch(
                session,
                batch_id,
                next_status,
                command,
                occurred_at,
                None,
                command_id=command_id,
                **_command_timestamps(command, next_status, occurred_at),
            )
        await session.execute(
            insert(backtest_batch_commands).values(
                batch_id=batch_id,
                command_id=command_id,
                command=command,
                status=next_status,
                lifecycle_revision=revision,
                occurred_at=occurred_at,
            )
        )
        await session.commit()
        return _command_result(batch_id, command, command_id, next_status, revision)
    except Exception:
        await session.rollback()
        raise


async def _reconcile_batch_after_run(session, batch_id: str, run_id: str, at) -> None:
    batch_status = (
        await session.execute(
            select(backtest_batches.c.status)
            .where(backtest_batches.c.batch_id == batch_id)
            .with_for_update()
        )
    ).scalar_one()
    statuses = (
        (
            await session.execute(
                select(backtest_runs.c.status).where(backtest_runs.c.batch_id == batch_id)
            )
        )
        .scalars()
        .all()
    )
    queued = "queued" in statuses
    active = any(status in {"running", "cancelling"} for status in statuses)
    if not queued and not active:
        await session.execute(
            delete(backtest_queue_turns).where(backtest_queue_turns.c.batch_id == batch_id)
        )
        terminal_status = "cancelled" if batch_status == "cancelling" else "completed"
        if batch_status != terminal_status:
            await _transition_batch(
                session,
                batch_id,
                terminal_status,
                terminal_status,
                at,
                run_id,
                completed_at=at,
            )
    elif batch_status == "pausing" and not active:
        await _transition_batch(session, batch_id, "paused", "paused", at, run_id)
    elif queued and batch_status in {"queued", "running"}:
        existing_turn = (
            await session.execute(
                select(backtest_queue_turns.c.turn_id)
                .where(backtest_queue_turns.c.batch_id == batch_id)
                .limit(1)
            )
        ).first()
        if existing_turn is None and not active:
            await session.execute(insert(backtest_queue_turns).values(batch_id=batch_id))


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
                    select(backtest_runs.c.status, backtest_runs.c.batch_id)
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
        if run["batch_id"] is not None:
            batch_status = (
                await session.execute(
                    select(backtest_batches.c.status).where(
                        backtest_batches.c.batch_id == run["batch_id"]
                    )
                )
            ).scalar_one()
            await _transition_batch(
                session,
                run["batch_id"],
                batch_status,
                "member_cancelled" if queued else "member_cancel_requested",
                requested_at,
                run_id,
                reason="user_requested",
            )
        if queued:
            if run["batch_id"] is None:
                await session.execute(
                    delete(backtest_queue_turns).where(backtest_queue_turns.c.run_id == run_id)
                )
            else:
                await _reconcile_batch_after_run(session, run["batch_id"], run_id, requested_at)
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
        batch_id = (
            await session.execute(
                select(backtest_runs.c.batch_id).where(backtest_runs.c.run_id == run_id)
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
                insert(backtest_fills).values([{"run_id": run_id, **fill} for fill in fills])
            )
        if trades:
            await session.execute(
                insert(backtest_closed_trades).values(
                    [{"run_id": run_id, **trade} for trade in trades]
                )
            )
        if batch_id is not None:
            await _reconcile_batch_after_run(session, batch_id, run_id, data["completed_at"])
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
            if run["batch_id"] is not None:
                await _reconcile_batch_after_run(
                    session, run["batch_id"], run["run_id"], completed_at
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
