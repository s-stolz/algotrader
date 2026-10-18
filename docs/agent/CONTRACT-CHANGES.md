# Contract Changes

Before changing an interface, identify its producer and actual consumers using
this map and code references. Root [CONTEXT.md](../../CONTEXT.md) owns shared
summaries; linked references own details. Area contexts describe local obligations.

## Affected Areas

Paths below are relative to the repository root; use the
[context map](../CONTEXT-MAP.md) to open each area's guidance.

| Contract | Producer → consumers | Verification focus |
| --- | --- | --- |
| Candle transport / Market identity | broker, ingestion, accessor → frontend, indicator-api, backtester, shared client | Serialization, timestamp conversion, symbol resolution, consumer parsing |
| Redis Candles / Ticks | broker → webserver, ingestion, indicator-api (Candles) | Publication, parsing, closed-candle handling, stream lifecycle |
| Historical / live Indicators | indicator-api + indicator engine → webserver (live), frontend | Tensor formatting, warmup, stream lifecycle, client validation |
| WebSocket messages | webserver → frontend | Subscription/fanout and `frontend/test/utils/websocketService.spec.ts` |
| Timeframe support | broker, accessor, Timescale, shared client → frontend, indicator-api, ingestion, backtester | Queries/aggregates and each supported consumer; UI options alone are insufficient |
| Broker Orders / Positions / Deals | broker → current route callers | Validation, protobuf mapping, consumer contracts |
| Runtime env | topology + generator → Compose, Vite proxy, Python services; CLI also reads topology | Config mapping fixture, validation, affected stack smoke |
| SQL schema / aggregates | Timescale migrations → accessor → query consumers | Forward migration, query behavior, live storage tests |
| Backtest run/batch persistence, commands, queue | backtester policy + accessor transactions + Timescale constraints → shared client, worker, frontend | Public contracts, sync/async clients, live transaction races, process cleanup, Workspace polling/controls |
| Strategy catalog / sweeps / saved configuration reuse | backtester registry and API → frontend, worker, persisted snapshots | Exact versions, defaults, pure validation, deterministic preview/acceptance, historical compatibility |
| Equity Replay / execution logs | backtester + accessor → frontend analysis/overlays | Fingerprint compatibility, ordered Fills/Trades, unavailable states, sampling |

For backtest changes, read [shared contracts](../contracts/backtests.md).
Worker capacity/recovery changes also require the
[recovery guide](../operations/backtest-worker-recovery.md).

## Completion

- Update the authoritative contract and each affected area context whose local
  responsibility changes. Keep shared rules in their owner, linked by consumers.
- Verify producer behavior and affected consumer interpretation with the relevant
  [commands](COMMANDS.md), including live storage/process checks where needed.
- For implementation-only changes, update context only if new durable locality
  knowledge is needed. For changed architecture trade-offs, consult
  [ADRs](../adr/README.md).
