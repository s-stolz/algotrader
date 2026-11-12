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

# Count and sort narrow identities before loading any page payloads.
_TRADE_CTE = """
WITH trade_rows AS (
    SELECT exit_timestamp_ms AS timestamp_ms, 0 AS kind_order,
           trade_sequence AS sequence, trade_id AS identity, NULL::text AS outcome
    FROM backtest_closed_trades WHERE run_id = :run_id
)
"""


# Keep only eligibility fields from the full diagnostic scan.
_ORDER_CTES = """
, raw_events AS (
    SELECT event->>'order_id' AS order_id, event->>'outcome' AS outcome, ordinal,
           event->'timestamp_ms' AS event_timestamp
    FROM backtest_runs r,
         jsonb_array_elements(CASE WHEN jsonb_typeof(r.diagnostics->'order_events') = 'array'
             THEN r.diagnostics->'order_events' ELSE '[]'::jsonb END)
         WITH ORDINALITY AS e(event, ordinal)
    WHERE r.run_id = :run_id
      AND jsonb_typeof(event->'order_id') = 'string' AND event->>'order_id' <> ''
), filled_orders AS MATERIALIZED (
    SELECT DISTINCT order_id FROM raw_events WHERE outcome = 'filled'
), order_rows AS (
    SELECT DISTINCT ON (order_id)
           (event_timestamp #>> '{}')::bigint AS timestamp_ms, 1 AS kind_order,
           ordinal AS sequence, order_id AS identity, outcome
    FROM raw_events e
    WHERE outcome = ANY(:terminal_outcomes)
      AND jsonb_typeof(event_timestamp) = 'number'
      AND CASE WHEN jsonb_typeof(event_timestamp) = 'number' THEN
          abs((event_timestamp #>> '{}')::numeric) <= 8640000000000000
          AND trunc((event_timestamp #>> '{}')::numeric) = (event_timestamp #>> '{}')::numeric
          ELSE false END
      AND NOT EXISTS (
          SELECT 1 FROM filled_orders filled WHERE filled.order_id = e.order_id
      )
    ORDER BY order_id, ordinal DESC
)
"""


_TRADE_ITEMS_CTE = """
, trade_items AS (
    SELECT p.timestamp_ms, p.kind_order, p.sequence, p.identity,
           jsonb_build_object(
               'kind', 'trade', 'timestamp_ms', p.timestamp_ms,
               'trade', (to_jsonb(t) - 'run_id' - 'trade_sequence') ||
                   jsonb_build_object('sequence', t.trade_sequence)
           ) AS item
    FROM page_rows p JOIN backtest_closed_trades t
      ON t.run_id = :run_id AND t.trade_sequence = p.sequence
    WHERE p.kind_order = 0
)
"""


_ORDER_ITEMS_CTES = """
, page_order_events AS MATERIALIZED (
    SELECT p.identity AS order_id, e.ordinal, e.event
    FROM backtest_runs r
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(r.diagnostics->'order_events') = 'array'
             THEN r.diagnostics->'order_events' ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS e(event, ordinal)
    JOIN page_rows p ON p.kind_order = 1 AND p.identity = e.event->>'order_id'
                   AND e.ordinal <= p.sequence
    WHERE r.run_id = :run_id AND jsonb_typeof(e.event->'order_id') = 'string'
), latest_fields AS (
    SELECT DISTINCT ON (e.order_id, field.key) e.order_id, field.key, field.value
    FROM page_order_events e
    CROSS JOIN LATERAL jsonb_each(e.event) AS field
    WHERE field.key IN ('side', 'limit_price', 'entry_price', 'quantity', 'requested_quantity')
    ORDER BY e.order_id, field.key, e.ordinal DESC
), order_metadata AS (
    SELECT order_id, jsonb_object_agg(key, value) AS fields
    FROM latest_fields GROUP BY order_id
), order_items AS (
    SELECT p.timestamp_ms, p.kind_order, p.sequence, p.identity,
           jsonb_build_object(
             'kind', 'unexecuted_order', 'timestamp_ms', p.timestamp_ms,
             'order', jsonb_build_object(
                'order_id', p.identity, 'outcome', p.outcome,
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
    FROM page_rows p LEFT JOIN order_metadata metadata ON metadata.order_id = p.identity
    WHERE p.kind_order = 1
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
    order_items_ctes = _ORDER_ITEMS_CTES if include_unexecuted else ""
    items_union = " UNION ALL SELECT * FROM order_items" if include_unexecuted else ""
    sql = (
        _TRADE_CTE
        + order_ctes
        + f"""
, timeline AS (SELECT * FROM trade_rows{union}),
page_rows AS MATERIALIZED (
    SELECT * FROM timeline
    ORDER BY timestamp_ms DESC, kind_order ASC, sequence DESC, identity ASC
    LIMIT :page_size OFFSET :offset
)
"""
        + _TRADE_ITEMS_CTE
        + order_items_ctes
        + f"""
, page_items AS (SELECT * FROM trade_items{items_union})
SELECT r.run_id, r.status, r.result_schema_version,
       (SELECT count(*) FROM timeline) AS total,
       COALESCE((SELECT jsonb_agg(item ORDER BY timestamp_ms DESC, kind_order ASC,
                                sequence DESC, identity ASC) FROM page_items), '[]'::jsonb) AS items
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
