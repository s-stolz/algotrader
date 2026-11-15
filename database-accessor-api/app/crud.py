from datetime import datetime, timezone
from typing import Optional

from app.models import (
    backtest_closed_trades,
    backtest_events,
    backtest_execution_slot,
    backtest_fills,
    backtest_queue_turns,
    backtest_runs,
    backtests,
    candles,
    markets,
)
from sqlalchemy import cast, delete, exists, func, insert, null, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

CAGG_VIEW_BY_MINUTES: dict[int, str] = {
    5: "candles_agg_m5",
    15: "candles_agg_m15",
    30: "candles_agg_m30",
    60: "candles_agg_h1",
    240: "candles_agg_h4",
    1440: "candles_agg_d1",
}

M1_LIMIT_CHUNK_WINDOW_SIZE = 2


def _epoch_ms_to_utc_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


async def insert_market(session, market_data: dict):
    """
    Insert a new market into the database

    :param session: SQLAlchemy session
    :param market_data: Market data as a dictionary

    :return: The symbol_id of the newly inserted market
    :rtype: int
    """
    market_data = dict(market_data)
    market_data["live_start_ms"] = (
        int(datetime.now(timezone.utc).timestamp() * 1000) // 60000 * 60000
        if market_data.get("source_type") == "broker"
        else None
    )
    stmt = insert(markets).values(**market_data).returning(markets.c.symbol_id)
    result = await session.execute(stmt)
    identity = result.scalar_one()
    await session.commit()
    return identity


async def update_market(session, symbol_id: int, market_data: dict):
    """Update metadata without rebinding its stored Candle source."""
    from app.market_sources import validate_source_edit

    result = await session.execute(
        select(markets).where(markets.c.symbol_id == symbol_id).with_for_update()
    )
    current = result.mappings().first()
    if current is None:
        return None
    validate_source_edit(dict(current), market_data)
    stmt = (
        update(markets)
        .where(markets.c.symbol_id == symbol_id)
        .values(**market_data)
        .returning(markets.c.symbol_id)
    )
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()
    await session.commit()
    return identity


async def delete_market(session, symbol_id: int):
    """
    Delete a market and all candles from that market from the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id

    :return: Number of rows in candles deleted
    :rtype: int
    """
    from app.history_downloads.storage import ensure_no_active_job, lock_market

    market = await lock_market(session, symbol_id)
    if market["source_type"] == "broker":
        await ensure_no_active_job(session, symbol_id)
    stmt = delete(candles).where(candles.c.symbol_id == symbol_id)
    candles_result = await session.execute(stmt)

    stmt = delete(markets).where(markets.c.symbol_id == symbol_id)
    market_result = await session.execute(stmt)

    await session.commit()

    return {
        "market_deleted": bool(market_result.rowcount),
        "deleted_candles": candles_result.rowcount,
    }


async def get_markets(session, symbol: Optional[str] = None, exchange: Optional[str] = None):
    """
    Get all markets from the database

    :param session: SQLAlchemy session

    :return: List of markets as dictionaries
    """
    stmt = select(markets)
    if symbol:
        stmt = stmt.where(markets.c.symbol == symbol)
    if exchange:
        stmt = stmt.where(markets.c.exchange == exchange)

    result = await session.execute(stmt)
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_market_by_id(session, market_id: int):
    result = await session.execute(select(markets).where(markets.c.symbol_id == market_id))
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def get_market_coverage(session, market_id: int):
    result = await session.execute(
        select(
            func.min(candles.c.timestamp_utc),
            func.max(candles.c.timestamp_utc),
            func.count(),
        ).where(candles.c.symbol_id == market_id)
    )
    oldest, latest, count = result.one()

    def timestamp_ms(value):
        if value is None:
            return None
        return int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)

    return {
        "market_id": market_id,
        "oldest_timestamp_ms": timestamp_ms(oldest),
        "latest_timestamp_ms": timestamp_ms(latest),
        "candle_count": count,
    }


async def insert_candles(session, symbol_id: int, candles_data: list[dict]):
    """
    Insert candles into the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id
    :param candles_data: List of candles to insert

    :return: Number of candles added
    :rtype: int
    """
    values = [
        {
            "symbol_id": symbol_id,
            "timestamp_utc": _epoch_ms_to_utc_datetime(candle["timestamp_ms"]),
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
        }
        for candle in candles_data
    ]

    stmt = pg_insert(candles).values(values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["symbol_id", "timestamp_utc"])
    result = await session.execute(stmt)
    await session.commit()

    added = result.rowcount if result.rowcount is not None else len(values)
    return added


async def get_candles(
    session,
    symbol_id: int,
    timeframe: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Get candles from the database

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id
    :param timeframe: Timeframe in minutes
    :param start_ms: Start timestamp in epoch ms (optional)
    :param end_ms: End timestamp in epoch ms (optional)
    :param limit: Maximum number of candles to return (optional)

    :return: List of candles as dictionaries
    :rtype: list[dict]
    """

    if timeframe == 1:
        return await _get_m1_candles(session, symbol_id, start_ms, end_ms, limit)

    cagg_view = CAGG_VIEW_BY_MINUTES.get(timeframe)
    if cagg_view:
        try:
            candles_data = await _get_cagg_candles(
                session, cagg_view, symbol_id, start_ms, end_ms, limit
            )
            if candles_data:
                return candles_data
        except SQLAlchemyError:
            pass

        # Continuous aggregate policies only materialize a rolling time window.
        # If older buckets are not materialized, fallback to direct bucketing
        # to avoid returning false empty pages during lazy-loading.
        return await _get_bucketed_candles(session, symbol_id, timeframe, start_ms, end_ms, limit)

    return await _get_bucketed_candles(session, symbol_id, timeframe, start_ms, end_ms, limit)


def _build_time_filters(
    *,
    column: str,
    start_ms: Optional[int],
    end_ms: Optional[int],
) -> tuple[list[str], dict]:
    filters = []
    params: dict[str, int] = {}

    if start_ms is not None:
        filters.append(f"{column} >= to_timestamp(:start_ms / 1000.0)")
        params["start_ms"] = start_ms

    if end_ms is not None:
        filters.append(f"{column} < to_timestamp(:end_ms / 1000.0)")
        params["end_ms"] = end_ms

    return filters, params


async def _execute_candle_query(session, sql: str, params: dict, limit: Optional[int]):
    result = await session.execute(text(sql), params)
    rows = result.fetchall()
    if limit is not None:
        rows = list(reversed(rows))
    return [dict(row._mapping) for row in rows]


async def _get_candle_chunk_windows(
    session,
    *,
    start_ms: Optional[int],
    end_ms: Optional[int],
    window_size: int = M1_LIMIT_CHUNK_WINDOW_SIZE,
) -> list[tuple[datetime, datetime]]:
    where_clauses = [
        "hypertable_schema = 'public'",
        "hypertable_name = 'candles'",
    ]
    params: dict[str, int] = {}

    if start_ms is not None:
        where_clauses.append("range_end::timestamptz > to_timestamp(:start_ms / 1000.0)")
        params["start_ms"] = start_ms

    if end_ms is not None:
        where_clauses.append("range_start::timestamptz < to_timestamp(:end_ms / 1000.0)")
        params["end_ms"] = end_ms

    sql = f"""
        SELECT
            range_start::timestamptz AS range_start,
            range_end::timestamptz AS range_end
        FROM timescaledb_information.chunks
        WHERE {" AND ".join(where_clauses)}
        ORDER BY range_end::timestamptz DESC
    """
    result = await session.execute(text(sql), params)
    chunks = [dict(row._mapping) for row in result.fetchall()]

    windows = []
    for index in range(0, len(chunks), window_size):
        chunk_batch = chunks[index : index + window_size]
        windows.append(
            (
                chunk_batch[-1]["range_start"],
                chunk_batch[0]["range_end"],
            )
        )
    return windows


async def _get_m1_limited_candles_by_chunk_window(
    session,
    *,
    symbol_id: int,
    window_start: datetime,
    window_end: datetime,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: int,
) -> list[dict]:
    where_clauses = [
        "symbol_id = :symbol_id",
        "timestamp_utc >= :window_start",
        "timestamp_utc < :window_end",
    ]
    time_filters, params = _build_time_filters(
        column="timestamp_utc",
        start_ms=start_ms,
        end_ms=end_ms,
    )
    where_clauses.extend(time_filters)
    params.update(
        {
            "symbol_id": symbol_id,
            "window_start": window_start,
            "window_end": window_end,
            "limit": limit,
        }
    )

    sql = f"""
        SELECT
            CAST(EXTRACT(EPOCH FROM timestamp_utc) * 1000 AS BIGINT) AS timestamp_ms,
            open,
            high,
            low,
            close,
            volume
        FROM candles
        WHERE {" AND ".join(where_clauses)}
        ORDER BY timestamp_utc DESC
        LIMIT :limit
    """
    result = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in result.fetchall()]


async def _get_m1_limited_candles(
    session,
    symbol_id: int,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: int,
):
    rows_desc: list[dict] = []
    chunk_windows = await _get_candle_chunk_windows(
        session,
        start_ms=start_ms,
        end_ms=end_ms,
    )

    for window_start, window_end in chunk_windows:
        remaining = limit - len(rows_desc)
        if remaining <= 0:
            break

        rows_desc.extend(
            await _get_m1_limited_candles_by_chunk_window(
                session,
                symbol_id=symbol_id,
                window_start=window_start,
                window_end=window_end,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=remaining,
            )
        )

    return list(reversed(rows_desc[:limit]))


async def _get_m1_candles(
    session,
    symbol_id: int,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: Optional[int],
):
    if limit is not None:
        return await _get_m1_limited_candles(session, symbol_id, start_ms, end_ms, limit)

    where_clauses = ["symbol_id = :symbol_id"]
    time_filters, params = _build_time_filters(
        column="timestamp_utc",
        start_ms=start_ms,
        end_ms=end_ms,
    )
    where_clauses.extend(time_filters)
    params["symbol_id"] = symbol_id
    if limit is not None:
        params["limit"] = limit

    sql = f"""
        SELECT
            CAST(EXTRACT(EPOCH FROM timestamp_utc) * 1000 AS BIGINT) AS timestamp_ms,
            open,
            high,
            low,
            close,
            volume
        FROM candles
        WHERE {" AND ".join(where_clauses)}
        ORDER BY timestamp_utc {"DESC" if limit else "ASC"}
        {"LIMIT :limit" if limit is not None else ""}
    """
    return await _execute_candle_query(session, sql, params, limit)


async def _get_cagg_candles(
    session,
    cagg_view: str,
    symbol_id: int,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: Optional[int],
):
    where_clauses = ["symbol_id = :symbol_id"]
    time_filters, params = _build_time_filters(
        column="bucket_ts",
        start_ms=start_ms,
        end_ms=end_ms,
    )
    where_clauses.extend(time_filters)
    params["symbol_id"] = symbol_id
    if limit is not None:
        params["limit"] = limit

    sql = f"""
        SELECT
            CAST(EXTRACT(EPOCH FROM bucket_ts) * 1000 AS BIGINT) AS timestamp_ms,
            open,
            high,
            low,
            close,
            volume
        FROM {cagg_view}
        WHERE {" AND ".join(where_clauses)}
        ORDER BY bucket_ts {"DESC" if limit else "ASC"}
        {"LIMIT :limit" if limit is not None else ""}
    """
    return await _execute_candle_query(session, sql, params, limit)


async def _get_bucketed_candles(
    session,
    symbol_id: int,
    timeframe: int,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: Optional[int],
):
    where_clauses = ["symbol_id = :symbol_id"]
    time_filters, params = _build_time_filters(
        column="timestamp_utc",
        start_ms=start_ms,
        end_ms=end_ms,
    )
    where_clauses.extend(time_filters)
    params["symbol_id"] = symbol_id
    params["timeframe"] = timeframe
    if limit is not None:
        params["limit"] = limit

    sql = f"""
        SELECT
            CAST(EXTRACT(EPOCH FROM bucket_ts) * 1000 AS BIGINT) AS timestamp_ms,
            first(open, timestamp_utc) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            last(close, timestamp_utc) AS close,
            SUM(volume) AS volume
        FROM (
            SELECT
                time_bucket(make_interval(mins => :timeframe), timestamp_utc) AS bucket_ts,
                timestamp_utc,
                open,
                high,
                low,
                close,
                volume
            FROM candles
            WHERE {" AND ".join(where_clauses)}
        ) source
        GROUP BY bucket_ts
        ORDER BY bucket_ts {"DESC" if limit else "ASC"}
        {"LIMIT :limit" if limit is not None else ""}
    """
    return await _execute_candle_query(session, sql, params, limit)


async def get_latest_m1_candle(session, symbol_id: int):
    candles_data = await _get_m1_limited_candles(
        session,
        symbol_id,
        start_ms=None,
        end_ms=None,
        limit=1,
    )
    return candles_data[0] if candles_data else None


async def delete_candles(session, symbol_id: int):
    """
    Delete all candles for a given symbol_id

    :param session: SQLAlchemy session
    :param symbol_id: Market symbol_id

    :return: Number of candles deleted
    :rtype: int
    """
    stmt = delete(candles).where(candles.c.symbol_id == symbol_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def rename_backtest(session, backtest_id: str, name: str | None):
    from app.schemas import ExperimentNameUpdateIn

    name = ExperimentNameUpdateIn(name=name).name
    try:
        result = await session.execute(
            update(backtests)
            .where(backtests.c.backtest_id == backtest_id)
            .values(name=name)
            .returning(backtests)
        )
        row = result.fetchone()
        saved = dict(row._mapping) if row else None
        await session.commit()
        return saved
    except Exception:
        await session.rollback()
        raise


def _run_columns(include_diagnostics: bool):
    return [
        (
            column
            if include_diagnostics or column.name != "diagnostics"
            else null().label("diagnostics")
        )
        for column in backtest_runs.c
    ]


async def get_backtest_run(session, run_id: str, *, include_diagnostics: bool = True):
    stmt = select(*_run_columns(include_diagnostics)).where(backtest_runs.c.run_id == run_id)
    result = await session.execute(stmt)
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_backtest_fills(session, run_id: str):
    stmt = (
        select(backtest_fills)
        .where(backtest_fills.c.run_id == run_id)
        .order_by(backtest_fills.c.fill_sequence.asc())
    )
    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]


async def get_backtest_trades(session, run_id: str):
    stmt = (
        select(backtest_closed_trades)
        .where(backtest_closed_trades.c.run_id == run_id)
        .order_by(backtest_closed_trades.c.trade_sequence.asc())
    )
    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]


class BacktestDeletionConflictError(ValueError):
    pass


async def delete_backtest(session, backtest_id: str) -> bool:
    try:
        slot = (
            await session.execute(select(backtest_execution_slot.c.run_id).with_for_update())
        ).scalar_one()
        backtest = (
            await session.execute(
                select(backtests.c.status)
                .where(backtests.c.backtest_id == backtest_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if backtest is None:
            await session.rollback()
            return False
        if backtest not in {"completed", "cancelled"}:
            raise BacktestDeletionConflictError(
                "Cancel and settle this backtest before deleting it"
            )
        members = (
            (
                await session.execute(
                    select(backtest_runs.c.run_id, backtest_runs.c.status)
                    .where(backtest_runs.c.backtest_id == backtest_id)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        if slot in {member["run_id"] for member in members} or any(
            member["status"] not in {"succeeded", "failed", "cancelled"} for member in members
        ):
            raise BacktestDeletionConflictError(
                "Cancel and settle all backtest members before deleting it"
            )
        result = await session.execute(
            delete(backtests).where(
                backtests.c.backtest_id == backtest_id,
                backtests.c.status.in_(["completed", "cancelled"]),
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return result.rowcount == 1


class BacktestSubmissionConflictError(ValueError):
    pass


async def create_backtest(session, payload: dict):
    """Accept a complete materialized backtest in one transaction."""
    data = dict(payload)
    members = data.pop("members")
    existing = await get_backtest_by_submission(session, data["submission_id"])
    if existing is not None:
        if existing["accepted_definition"] != data["accepted_definition"]:
            raise BacktestSubmissionConflictError("submission_id belongs to a different definition")
        return existing
    data.update(status="queued", lifecycle_revision=0)
    try:
        await session.execute(select(backtest_execution_slot.c.slot_id).with_for_update())
        await session.execute(insert(backtests).values(**data))
        await session.execute(
            insert(backtest_runs).values(
                [
                    {
                        "run_id": member["run_id"],
                        "backtest_id": data["backtest_id"],
                        "run_ordinal": member["run_ordinal"],
                        "status": "queued",
                        "submitted_at": data["accepted_at"],
                        "request_schema_version": member["request_schema_version"],
                        "request": member["request"],
                    }
                    for member in members
                ]
            )
        )
        await session.execute(
            insert(backtest_events).values(
                backtest_id=data["backtest_id"],
                revision=0,
                event_type="accepted",
                prior_status=None,
                status="queued",
                occurred_at=data["accepted_at"],
            )
        )
        await session.execute(insert(backtest_queue_turns).values(backtest_id=data["backtest_id"]))
        await session.commit()
        return await get_backtest(session, data["backtest_id"])
    except IntegrityError as exc:
        await session.rollback()
        existing = await get_backtest_by_submission(session, data["submission_id"])
        if existing is not None:
            if existing["accepted_definition"] != data["accepted_definition"]:
                raise BacktestSubmissionConflictError(
                    "submission_id belongs to a different definition"
                ) from exc
            return existing
        raise
    except Exception:
        await session.rollback()
        raise


async def get_backtest_by_submission(session, submission_id: str):
    result = await session.execute(
        select(backtests).where(backtests.c.submission_id == submission_id)
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_backtest(session, backtest_id: str):
    result = await session.execute(select(backtests).where(backtests.c.backtest_id == backtest_id))
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def list_backtests(session):
    result = await session.execute(
        select(backtests).order_by(backtests.c.accepted_at.desc(), backtests.c.backtest_id.asc())
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def list_backtest_members(session, backtest_id: str, *, include_diagnostics: bool = True):
    result = await session.execute(
        select(*_run_columns(include_diagnostics))
        .where(backtest_runs.c.backtest_id == backtest_id)
        .order_by(backtest_runs.c.run_ordinal.asc())
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def list_backtest_events(session, backtest_id: str):
    result = await session.execute(
        select(backtest_events)
        .where(backtest_events.c.backtest_id == backtest_id)
        .order_by(backtest_events.c.revision.asc())
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def list_backtest_runs(
    session,
    *,
    status: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy: str | None = None,
    engine: str | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    backtest_id: str | None = None,
    include_diagnostics: bool = True,
):
    stmt = select(*_run_columns(include_diagnostics))
    if backtest_id is not None:
        stmt = stmt.where(backtest_runs.c.backtest_id == backtest_id)
    if status is not None:
        stmt = stmt.where(backtest_runs.c.status == status)
    if symbol is not None:
        stmt = stmt.where(_symbol_membership_filter(session, symbol))
    if timeframe is not None:
        stmt = stmt.where(backtest_runs.c.request["timeframe"].as_string() == timeframe)
    if strategy is not None:
        stmt = stmt.where(
            backtest_runs.c.request["strategy"]["strategy_id"].as_string() == strategy
        )
    if engine is not None:
        stmt = stmt.where(backtest_runs.c.request["engine"].as_string() == engine)
    if submitted_from is not None:
        stmt = stmt.where(backtest_runs.c.submitted_at >= submitted_from)
    if submitted_to is not None:
        stmt = stmt.where(backtest_runs.c.submitted_at <= submitted_to)
    stmt = stmt.order_by(
        backtest_runs.c.submitted_at.desc(),
        backtest_runs.c.run_id.asc(),
    )
    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]


def _symbol_membership_filter(session, symbol: str):
    bind = session.get_bind() if hasattr(session, "get_bind") else session.engine
    if bind.dialect.name == "postgresql":
        symbols = cast(backtest_runs.c.request["symbols"], JSONB)
        return symbols.contains([symbol])

    symbols = func.json_each(
        backtest_runs.c.request,
        "$.symbols",
    ).table_valued("key", "value")
    return exists(select(1).select_from(symbols).where(symbols.c.value == symbol))
