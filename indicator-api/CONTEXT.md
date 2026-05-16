# Indicator API Context

FastAPI service for historical indicator calculations and live indicator streams.

## Owned Interfaces

- Historical Indicator response shape for frontend consumers.
- Live Indicator stream lifecycle and Redis output payload.
- Candle adaptation from database-accessor-api and Redis Candle streams into
  `indicator_engine`.
- Warmup, parameter preparation, trim, timestamp, and tensor response formatting.

## Key Modules

- `app/routes/indicators.py`: historical indicator route.
- `app/routes/live_indicator_streams.py`: live stream start, stop, and status routes.
- `app/services/historical_indicator_service.py`: candle fetching, parameter
  preparation, warmup adjustment, batch engine invocation, and response formatting.
- `app/services/live_indicator_manager.py`: live stream specs, Redis input,
  warmup seeding, update engine invocation, and Redis indicator output.
- `app/services/candle_cache.py`: recent candle cache used for live warmup.
- `app/candles.py`: shared database-accessor client calls returning DataFrames.
- `app/utils.py`: parameter, warmup, trim, timestamp, and tensor formatting helpers.

## Contracts

- Historical responses wrap `indicator_info` and `indicator_data` under `data`.
- Indicator output timestamps follow root `CONTEXT.md`.
- Live indicator Redis input is the candle stream defined in root `CONTEXT.md`.
- Live indicator Redis output is
  `indicators:{account_id}:{exchange}:{symbol}:{timeframe}:{stream_id}` with fields
  `t`, `s`, `i`, and `d`.
- `currency_strength` is not supported for live streaming in the current v1 path.

## Change Triggers

- Historical and live paths adapt candles to `indicator_engine` differently.
  Check both when changing candle shape, warmup, or field ordering.
- `indicator_engine` is the deeper compute module; keep UI metadata and transport
  response formatting outside that library.
- If live stream output changes, update `webserver/CONTEXT.md` and
  `frontend/CONTEXT.md`.

## Verification

- Use service-level tests for routes/managers when added.
- Use `make test indicator_engine` for shared engine behavior.
