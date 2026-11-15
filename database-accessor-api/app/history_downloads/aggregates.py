from datetime import datetime, timezone

from app.crud import CAGG_VIEW_BY_MINUTES
from sqlalchemy import text


async def refresh_inserted_history(session, job) -> None:
    if job["first_inserted_ms"] is None:
        return
    if session.get_bind().dialect.name != "postgresql":
        return
    # Timescale refresh owns its transaction; keep the job fenced in the caller
    # while refreshing on a separate autocommit connection.
    async with session.bind.connect() as connection:
        connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await refresh_views(connection, job)


async def refresh_views(connection, job) -> None:
    for minutes, view in CAGG_VIEW_BY_MINUTES.items():
        if await connection.scalar(text("SELECT to_regclass(:view)"), {"view": view}) is None:
            continue
        bucket_ms = minutes * 60000
        start_ms = job["first_inserted_ms"] // bucket_ms * bucket_ms
        end_ms = (job["last_inserted_ms"] // bucket_ms + 1) * bucket_ms
        await connection.execute(
            text(
                "CALL refresh_continuous_aggregate(CAST(:view AS regclass), "
                "CAST(:start AS timestamptz), CAST(:end AS timestamptz))"
            ),
            dict(
                view=view,
                start=datetime.fromtimestamp(start_ms / 1000, timezone.utc),
                end=datetime.fromtimestamp(end_ms / 1000, timezone.utc),
            ),
        )
