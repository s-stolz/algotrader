# Indicator API Context

Adapts historical and live Candles to `indicator_engine`, owning warmup,
parameters, response formatting, and live-stream lifecycle.

## Historical and Live Paths

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
- `currency_strength` and `opening_range` are unsupported for live streaming.
  Catalog metadata declares `supports_live: false`; clients must avoid subscribing
  these historical-only indicators. Opening range is catalog ID 7; its dedicated
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

Use `make test indicator_engine` for shared computation. Route/manager changes
also need tests of service adaptation and affected WebSocket consumers; engine
coverage alone does not verify transport or live-stream behavior.

# Indicator live Candle context

**Live Indicator input:** the existing timestamp and OHLCV values of a Redis
Candle. Publication continuity does not become an Indicator field or parameter.

**Publication continuity:** backend delivery-session metadata. Legacy and enriched
Candles remain valid inputs; a session change does not rebuild an active Indicator.

For compatibility, recovery scope and upgrade order, read
[live publication continuity](../docs/contracts/recovery.md#live-publication-continuity).
