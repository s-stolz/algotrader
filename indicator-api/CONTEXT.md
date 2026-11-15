# Indicator API Context

Adapts historical and live Candles to `indicator_engine`, owning warmup,
parameters, response formatting, and live-stream lifecycle.

## Historical and Live Paths

Live stream requests require the durable `market_id`. The live manager validates
the stored Broker Market against the configured cTrader account/environment and
resolves every declared input to a Broker Market in the same exchange. Custom
Markets never acquire live streams; their historical calculations remain available.
The Market identity participates in stream identity, preventing same-symbol
datasets from sharing a live session.

- `app/services/historical_indicator_service.py` fetches Candles, prepares
  parameters/warmup, invokes the batch engine, and formats the response.
  Responses wrap `indicator_info` and `indicator_data` under `data`.
- Daily anchored history uses `app/services/anchored_indicator_service.py` and
  the shared indicator-engine daily input adapter. Resolve the requested output
  timestamps before expanding a limited request to its declared local-day anchor;
  fetch each source's required predecessor separately. Missing inputs within the
  declared session window invalidate subsequent same-day outputs causally.
  Currency strength retains its full UTC-day requirement. Unavailable output is omitted, never replaced with
  older values outside the selected output window. Ordinary rolling indicators
  retain their existing warmup path.
- `app/services/live_indicator_manager.py` owns live specs, Redis input, warmup
  seeding, update-engine calls, and Redis output. `app/services/candle_cache.py`
  supplies recent warmup data.
- These paths adapt Candles differently. Changes to shape, warmup, or field order
  must check both; common formatting helpers live in `app/utils.py`.
- Live output uses the Indicator stream name in [root context](../CONTEXT.md),
  with fields `t`, `s`, `i`, `d`. Consumers are realtime-service and frontend.
- `currency_strength` supports live updates through `services/live_daily_basket.py`.
  It captures a cursor on each required source before fetching history, seeds the
  full UTC day and each source's predecessor, and waits for all seven pairs at
  each candle timestamp. Subsequent revisions use the latest same-candle values.
  Missing daily inputs pause output; storage history is retried every five seconds
  until complete. Redis read failures or source publication-session changes also
  require a fresh snapshot, including the last forming candle once it closes.
  Resuming within that candle does not clear recovery; its authoritative close
  must be fetched after rollover. At UTC midnight, retain each source's latest
  observed predecessor timestamp and wait until storage reaches it before seeding
  the new day. Predecessor timestamps may differ between sources.
  `services/live_daily_history.py` builds closed snapshots from raw M1 closes,
  grouped into the requested timeframe, so recovery does not depend on aggregate
  refresh timing. Higher-timeframe buckets wait for raw storage progress through
  their final minute (or later, across a market closure). Pending ingestion
  recovery and unconfirmed writes are checked before and after snapshot reads;
  overlapping work keeps the snapshot pending. These checks do not prove general
  historical completeness; the daily input adapter still validates required bars.
  Ingestion remains responsible for durable source backfill. Rebuilt values use
  the historical adapter's completeness rules; corrected earlier outputs carry
  the optional Redis `replay: "1"` marker. Recovery is silent in the chart.
- `GET /indicators/{id}` exposes catalog metadata, including required `inputs`,
  so realtime-service can acquire the basket without duplicating engine policy.
  Deploy indicator-api before realtime-service consumers of this endpoint.
- `opening_range` remains unsupported for live streaming. Its catalog metadata
  declares `supports_live: false`; clients must avoid subscribing it.
  Opening range is catalog ID 7; its dedicated
  `opening_range` output renderer consumes bounds, readiness, and timestamp
  coordinates together rather than plotting each numeric field as a price.
- The indicator catalog includes the stable engine `indicator_id` alongside its
  numeric API `id`. Saved chart configurations resolve through this mapping;
  consumers must not infer an API ID from a display name or hardcoded ID table.
- The shared [indicator catalog](../libs/indicator_engine/README.md#adding-an-indicator)
  owns public identities, presentation and live eligibility. Keep transport
  formatting here and renderer implementations in frontend; shared numerical
  computation remains independent of presentation. See
  [ADR-0009](../docs/adr/0009-shared-indicator-registration-catalog.md).

## Verification

Use `make test indicator-api` for service adaptation and routes, and
`make test indicator_engine` for shared computation. Route/manager changes also
need affected WebSocket consumer tests; engine coverage alone does not verify
transport or live-stream behavior.

# Indicator live Candle context

**Live Indicator input:** the existing timestamp and OHLCV values of a Redis
Candle. Publication continuity does not become an Indicator field or parameter.

**Publication continuity:** backend delivery-session metadata. Legacy and enriched
Candles remain valid inputs. Rolling single-symbol indicators ignore session
changes; daily basket indicators rebuild their cumulative state after a change.

For compatibility, recovery scope and upgrade order, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
