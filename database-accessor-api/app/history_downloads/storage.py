"""Locked, fenced persistence for historical extension jobs and their Candle pages."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from app import crud
from app.models import candles, markets
from app.models import history_download_jobs as jobs
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

ACTIVE_STATUSES = ("queued", "downloading")


class DownloadConflictError(ValueError):
    pass


class DownloadNotFoundError(LookupError):
    pass


@asynccontextmanager
async def transaction(session):
    try:
        yield
        await session.commit()
    except Exception:
        await session.rollback()
        raise


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def read_job(session, job_id: str) -> dict[str, Any] | None:
    result = await session.execute(select(jobs).where(jobs.c.id == job_id))
    row = result.mappings().first()
    return dict(row) if row else None


async def list_jobs(session, market_id: int | None, active_only: bool, limit: int = 50):
    statement = select(jobs)
    if market_id is not None:
        statement = statement.where(jobs.c.market_id == market_id)
    if active_only:
        statement = statement.where(jobs.c.status.in_(ACTIVE_STATUSES))
    ordering = (
        (jobs.c.created_at.asc(), jobs.c.id)
        if active_only
        else (jobs.c.status.in_(ACTIVE_STATUSES).desc(), jobs.c.created_at.desc(), jobs.c.id)
    )
    statement = statement.order_by(*ordering).limit(limit)
    result = await session.execute(statement)
    return [dict(row) for row in result.mappings()]


async def lock_market(session, market_id: int):
    result = await session.execute(
        select(markets).where(markets.c.symbol_id == market_id).with_for_update()
    )
    row = result.mappings().first()
    if row is None:
        raise DownloadNotFoundError("Market not found")
    return dict(row)


async def locked_job(session, job_id: str):
    current = await read_job(session, job_id)
    if current is None:
        raise DownloadNotFoundError("Historical download not found")
    await lock_market(session, current["market_id"])
    result = await session.execute(select(jobs).where(jobs.c.id == job_id).with_for_update())
    row = result.mappings().first()
    if row is None:
        raise DownloadNotFoundError("Historical download not found")
    return dict(row)


async def ensure_no_active_job(session, market_id: int, except_id: str | None = None):
    statement = select(jobs.c.id).where(
        jobs.c.market_id == market_id, jobs.c.status.in_(ACTIVE_STATUSES)
    )
    if except_id is not None:
        statement = statement.where(jobs.c.id != except_id)
    if await session.scalar(statement) is not None:
        raise DownloadConflictError("Cancel the active historical download first")


async def create_job(session, data):
    async with transaction(session):
        market = await lock_market(session, data.market_id)
        existing = await read_job(session, str(data.request_id))
        if existing is not None:
            if any(
                existing[key] != getattr(data, key)
                for key in ("market_id", "start_ms", "candle_count")
            ):
                raise DownloadConflictError("Request ID already belongs to another download")
            return existing
        if market["source_type"] != "broker":
            raise DownloadConflictError("Historical downloads require a broker market")
        await ensure_no_active_job(session, data.market_id)
        coverage = await crud.get_market_coverage(session, data.market_id)
        now = utc_now()
        end = coverage["oldest_timestamp_ms"]
        if end is None:
            end = int(now.timestamp() * 1000) // 60000 * 60000
        if data.start_ms is not None and data.start_ms >= end:
            raise DownloadConflictError("Start date must precede the oldest stored candle")
        values = dict(
            id=str(data.request_id),
            request_id=str(data.request_id),
            market_id=data.market_id,
            status="queued",
            start_ms=data.start_ms,
            candle_count=data.candle_count,
            end_exclusive_ms=end,
            cursor_ms=end,
            fetched_count=0,
            inserted_count=0,
            source_snapshot=market,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        result = await session.execute(insert(jobs).values(**values).returning(jobs))
        return dict(result.mappings().one())


def is_owned(job, owner_token: str, revision: int) -> bool:
    return (
        job["status"] == "downloading"
        and job["owner_token"] == owner_token
        and job["revision"] == revision
        and job["lease_expires_at"] is not None
        and as_utc(job["lease_expires_at"]) > utc_now()
    )


async def change_job(session, job_id: str, values):
    result = await session.execute(
        update(jobs).where(jobs.c.id == job_id).values(**values).returning(jobs)
    )
    return dict(result.mappings().one())


async def claim_job(session, job_id: str, data):
    async with transaction(session):
        job = await locked_job(session, job_id)
        now = utc_now()
        reclaimable = job["status"] == "downloading" and as_utc(job["lease_expires_at"]) <= now
        if job["status"] != "queued" and not reclaimable:
            return None
        return await change_job(
            session,
            job_id,
            dict(
                status="downloading",
                owner_token=data.owner_token,
                revision=job["revision"] + 1,
                lease_expires_at=now + timedelta(seconds=data.lease_seconds),
                updated_at=now,
            ),
        )


async def heartbeat_job(session, job_id: str, data):
    async with transaction(session):
        job = await locked_job(session, job_id)
        if not is_owned(job, data.owner_token, data.revision):
            return None
        now = utc_now()
        return await change_job(
            session,
            job_id,
            dict(
                lease_expires_at=now + timedelta(seconds=data.lease_seconds),
                updated_at=now,
            ),
        )


def validate_page(job, data) -> None:
    if data.expected_cursor_ms != job["cursor_ms"]:
        raise DownloadConflictError("Historical cursor changed")
    if job["start_ms"] is not None and data.next_cursor_ms < job["start_ms"]:
        raise DownloadConflictError("Historical page precedes the accepted start date")
    if job["candle_count"] is not None:
        remaining = job["candle_count"] - job["inserted_count"]
        if len(data.candles) > remaining:
            raise DownloadConflictError("Historical page exceeds the additional candle count")


async def insert_page(session, market_id: int, values) -> list[int]:
    if not values:
        return []
    rows = [
        dict(
            symbol_id=market_id,
            timestamp_utc=datetime.fromtimestamp(value.timestamp_ms / 1000, timezone.utc),
            **value.model_dump(exclude={"timestamp_ms"}),
        )
        for value in values
    ]
    statement = (
        pg_insert(candles)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["symbol_id", "timestamp_utc"])
        .returning(candles.c.timestamp_utc)
    )
    result = await session.execute(statement)
    return [int(as_utc(value).timestamp() * 1000) for value in result.scalars()]


def inserted_extent(job, inserted: list[int]):
    values = [*inserted]
    for key in ("first_inserted_ms", "last_inserted_ms"):
        if job[key] is not None:
            values.append(job[key])
    return (min(values), max(values)) if values else (None, None)


async def commit_page(session, job_id: str, data):
    async with transaction(session):
        job = await locked_job(session, job_id)
        if not is_owned(job, data.owner_token, data.revision):
            return None
        validate_page(job, data)
        inserted = await insert_page(session, job["market_id"], data.candles)
        first, last = inserted_extent(job, inserted)
        now = utc_now()
        return await change_job(
            session,
            job_id,
            dict(
                cursor_ms=data.next_cursor_ms,
                fetched_count=job["fetched_count"] + data.fetched_count,
                inserted_count=job["inserted_count"] + len(inserted),
                first_inserted_ms=first,
                last_inserted_ms=last,
                revision=job["revision"] + 1,
                updated_at=now,
                lease_expires_at=now + timedelta(seconds=120),
            ),
        )


async def transition_job(session, job_id: str, data):
    from .aggregates import refresh_inserted_history

    async with transaction(session):
        job = await locked_job(session, job_id)
        if not is_owned(job, data.owner_token, data.revision):
            return None
        if data.status == "completed":
            reached_date = job["start_ms"] is not None and job["cursor_ms"] == job["start_ms"]
            reached_count = (
                job["candle_count"] is not None and job["inserted_count"] >= job["candle_count"]
            )
            exhausted = job["cursor_ms"] == 0 and data.availability_reason is not None
            if not (reached_date or reached_count or exhausted):
                raise DownloadConflictError("Download has not reached its requested history")
            await refresh_inserted_history(session, job)
        return await change_job(
            session,
            job_id,
            dict(
                status=data.status,
                owner_token=None,
                lease_expires_at=None,
                revision=job["revision"] + 1,
                updated_at=utc_now(),
                failure_reason=data.failure_reason,
                availability_reason=data.availability_reason,
            ),
        )


async def cancel_job(session, job_id: str):
    async with transaction(session):
        job = await locked_job(session, job_id)
        if job["status"] not in ACTIVE_STATUSES:
            return job
        return await change_job(
            session,
            job_id,
            dict(
                status="cancelled",
                owner_token=None,
                lease_expires_at=None,
                revision=job["revision"] + 1,
                updated_at=utc_now(),
            ),
        )


async def retry_job(session, job_id: str):
    async with transaction(session):
        job = await locked_job(session, job_id)
        if job["status"] in ACTIVE_STATUSES:
            return job
        if job["status"] == "completed":
            raise DownloadConflictError("Completed downloads cannot be retried")
        await ensure_no_active_job(session, job["market_id"], except_id=job_id)
        return await change_job(
            session,
            job_id,
            dict(
                status="queued",
                owner_token=None,
                lease_expires_at=None,
                revision=job["revision"] + 1,
                updated_at=utc_now(),
                failure_reason=None,
                availability_reason=None,
            ),
        )
