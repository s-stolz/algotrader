# Indicator API Context

Adapts historical and live Candles to `indicator_engine`, owning warmup,
parameters, response formatting, and live-stream lifecycle.

## Historical and Live Paths

- `app/services/historical_indicator_service.py` fetches Candles, prepares
  parameters/warmup, invokes the batch engine, and formats the response.
  Responses wrap `indicator_info` and `indicator_data` under `data`.
- `app/services/live_indicator_manager.py` owns live specs, Redis input, warmup
  seeding, update-engine calls, and Redis output. `app/services/candle_cache.py`
  supplies recent warmup data.
- These paths adapt Candles differently. Changes to shape, warmup, or field order
  must check both; common formatting helpers live in `app/utils.py`.
- Live output uses the Indicator stream name in [root context](../CONTEXT.md),
  with fields `t`, `s`, `i`, `d`. Consumers are webserver and frontend.
- `currency_strength` is unsupported for live streaming.
- Keep UI metadata and transport formatting here or in frontend; shared compute
  belongs to [indicator_engine](../libs/CONTEXT.md#indicator-engine).

## Verification

Use `make test indicator_engine` for shared computation. Route/manager changes
also need tests of service adaptation and affected WebSocket consumers; engine
coverage alone does not verify transport or live-stream behavior.
