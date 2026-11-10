"""Bounded execution-log projection; ordering and pagination remain in PostgreSQL."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Terminal outcomes are explicit: an unknown future event must not become a rejection.
TERMINAL_OUTCOMES = (
    "cancel",
    "expired",
    "gap_expired",
    "run_end_expired",
    "run_end_unexecuted",
    "schedule_cancelled",
    "constraint_cancelled",
    "reduce_only_cancelled",
    "oco_cancelled",
    "stop_cancelled",
    "account_depleted_cancelled",
    "insufficient_margin",
    "invalid_stop",
    "below_minimum_quantity",
    "account_depleted",
    "position_open_ignored",
    "replaced",
    "rejected",
)

# The full diagnostic array is inspected only inside PostgreSQL and only when requested.
_ORDER_CTES = """
, raw_events AS (
    SELECT event, ordinal
    FROM backtest_runs r,
         jsonb_array_elements(CASE WHEN jsonb_typeof(r.diagnostics->'order_events') = 'array'
             THEN r.diagnostics->'order_events' ELSE '[]'::jsonb END)
         WITH ORDINALITY AS e(event, ordinal)
    WHERE r.run_id = :run_id
      AND jsonb_typeof(event->'order_id') = 'string' AND event->>'order_id' <> ''
), terminals AS (
    SELECT DISTINCT ON (event->>'order_id') event, ordinal
    FROM raw_events e
    WHERE event->>'outcome' = ANY(:terminal_outcomes)
      AND jsonb_typeof(event->'timestamp_ms') = 'number'
      AND CASE WHEN jsonb_typeof(event->'timestamp_ms') = 'number' THEN
          abs((event->>'timestamp_ms')::numeric) <= 8640000000000000
          AND trunc((event->>'timestamp_ms')::numeric) = (event->>'timestamp_ms')::numeric
          ELSE false END
      AND NOT EXISTS (
          SELECT 1 FROM raw_events filled
          WHERE filled.event->>'order_id' = e.event->>'order_id'
            AND filled.event->>'outcome' = 'filled'
      )
    ORDER BY event->>'order_id', ordinal DESC
), latest_fields AS (
    SELECT DISTINCT ON (e.event->>'order_id', field.key)
           e.event->>'order_id' AS order_id, field.key, field.value
    FROM raw_events e JOIN terminals t ON e.event->>'order_id' = t.event->>'order_id'
         AND e.ordinal <= t.ordinal
    CROSS JOIN LATERAL jsonb_each(e.event) AS field
    WHERE field.key IN ('side', 'limit_price', 'entry_price', 'quantity', 'requested_quantity')
    ORDER BY e.event->>'order_id', field.key, e.ordinal DESC
), order_metadata AS (
    SELECT order_id, jsonb_object_agg(key, value) AS fields
    FROM latest_fields GROUP BY order_id
), order_rows AS (
    SELECT (t.event->>'timestamp_ms')::bigint AS timestamp_ms,
           1 AS kind_order, t.ordinal AS sequence, t.event->>'order_id' AS identity,
           jsonb_build_object(
             'kind', 'unexecuted_order', 'timestamp_ms', (t.event->>'timestamp_ms')::bigint,
             'order', jsonb_build_object(
                'order_id', t.event->>'order_id', 'outcome', t.event->>'outcome',
                'side', CASE WHEN metadata.fields->>'side' IN ('buy', 'sell')
                             THEN metadata.fields->'side' ELSE NULL END,
                'planned_price', CASE WHEN jsonb_typeof(COALESCE(metadata.fields->'limit_price',
                    metadata.fields->'entry_price')) = 'number'
                    THEN COALESCE(metadata.fields->'limit_price', metadata.fields->'entry_price')
                    ELSE NULL END,
                'planned_quantity', CASE WHEN jsonb_typeof(COALESCE(metadata.fields->'quantity',
                    metadata.fields->'requested_quantity')) = 'number'
                    THEN COALESCE(metadata.fields->'quantity',
                                  metadata.fields->'requested_quantity')
                    ELSE NULL END
             )
           ) AS item
    FROM terminals t LEFT JOIN order_metadata metadata
      ON metadata.order_id = t.event->>'order_id'
)

"""

_TRADE_CTE = """
WITH trade_rows AS (
    SELECT exit_timestamp_ms AS timestamp_ms, 0 AS kind_order,
           trade_sequence AS sequence, trade_id AS identity,
           jsonb_build_object(
               'kind', 'trade', 'timestamp_ms', exit_timestamp_ms,
               'trade', (to_jsonb(t) - 'run_id' - 'trade_sequence') ||
                   jsonb_build_object('sequence', trade_sequence)
           ) AS item
    FROM backtest_closed_trades t WHERE run_id = :run_id
)
"""


async def get_execution_log(
    session: AsyncSession, run_id: str, *, page: int, page_size: int, include_unexecuted: bool
) -> dict | None:
    """Return at most page_size items and a snapshot-consistent total, including empty pages."""
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid execution-log pagination")
    order_ctes = _ORDER_CTES if include_unexecuted else ""
    union = " UNION ALL SELECT * FROM order_rows" if include_unexecuted else ""
    sql = (
        _TRADE_CTE
        + order_ctes
        + f"""
, timeline AS (SELECT * FROM trade_rows{union}),
page_rows AS (
    SELECT * FROM timeline
    ORDER BY timestamp_ms DESC, kind_order ASC, sequence DESC, identity ASC
    LIMIT :page_size OFFSET :offset
)
SELECT r.run_id, r.status, r.result_schema_version,
       (SELECT count(*) FROM timeline) AS total,
       COALESCE((SELECT jsonb_agg(item ORDER BY timestamp_ms DESC, kind_order ASC,
                                sequence DESC, identity ASC) FROM page_rows), '[]'::jsonb) AS items
FROM backtest_runs r WHERE r.run_id = :run_id
"""
    )
    params = {
        "run_id": run_id,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
        "terminal_outcomes": list(TERMINAL_OUTCOMES),
    }
    result = await session.execute(text(sql), params)
    row = result.mappings().first()
    return {**dict(row), "page": page, "page_size": page_size} if row else None
