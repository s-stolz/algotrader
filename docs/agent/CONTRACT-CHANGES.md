# Contract Changes

Use this map when a change affects a durable cross-service interface. Root
`CONTEXT.md` remains the canonical summary; this file tells agents which local
contexts and tests to inspect.

## Change Map

| Contract | Producers | Consumers | Docs to update | Verification |
| --- | --- | --- | --- | --- |
| Candle transport fields (`timestamp_ms`, `open`, `high`, `low`, `close`, `volume`) | `database-accessor-api`, `broker-service`, `ingestion-service` | `frontend`, `indicator-api`, `backtester`, `libs/db_accessor_client` | Root `CONTEXT.md`, producer and consumer contexts | Relevant backend tests plus `make test frontend` when chart data changes |
| Redis Candle payload (`o`, `h`, `l`, `c`, `v`, `t`) | `broker-service` | `webserver`, `ingestion-service`, `indicator-api` live streams | Root `CONTEXT.md`, `broker-service/CONTEXT.md`, `webserver/CONTEXT.md`, `ingestion-service/CONTEXT.md`, `indicator-api/CONTEXT.md` | Broker stream tests plus consumer parsing tests where available |
| Tick payload (`b`, `a`, `t`) | `broker-service` | `webserver`, future UI consumers | Root `CONTEXT.md`, `broker-service/CONTEXT.md`, `webserver/CONTEXT.md` | Broker stream tests and WebSocket fanout tests where available |
| Timeframe support | `broker-service`, `database-accessor-api`, `timescaledb-init`, `libs/db_accessor_client` | `frontend`, `indicator-api`, `ingestion-service`, `backtester` | Root `CONTEXT.md`, all affected area contexts, `config/topology.schema.md` if topology changes | Storage/query tests, shared client tests, frontend gate if UI options change |
| Indicator historical response | `indicator-api`, `libs/indicator_engine` | `frontend`, future backtester integrations | Root `CONTEXT.md` if cross-service, `indicator-api/CONTEXT.md`, `frontend/CONTEXT.md`, `libs/CONTEXT.md` | `make test indicator_engine` plus indicator-api service tests when present |
| Indicator live stream (`indicators:{account_id}:{exchange}:{symbol}:{timeframe}:{stream_id}` fields `t`, `s`, `i`, `d`) | `indicator-api` | `webserver`, `frontend` | Root `CONTEXT.md`, `indicator-api/CONTEXT.md`, `webserver/CONTEXT.md`, `frontend/CONTEXT.md` | Live manager tests, WebSocket tests, frontend WebSocket tests |
| WebSocket protocol messages | `webserver` | `frontend` | `webserver/CONTEXT.md`, `frontend/CONTEXT.md`; root `CONTEXT.md` if message semantics become cross-service | Webserver protocol tests plus `frontend/test/utils/websocketService.spec.ts` |
| Market identity (`symbol_id`, `symbol`, `exchange`, `market_type`, `min_move`, `timezone`) | `database-accessor-api`, `timescaledb-init` | `frontend`, `indicator-api`, `backtester`, `broker-service` where symbols are bridged | Root `CONTEXT.md`, `database-accessor-api/CONTEXT.md`, `timescaledb-init/CONTEXT.md`, affected consumers | Database accessor tests and affected consumer tests |
| Order, Position, Deal contracts | `broker-service` | `frontend` or future automation modules | Root `CONTEXT.md` for durable vocabulary, `broker-service/CONTEXT.md`, affected consumer context | Broker route tests and consumer contract tests |
| Runtime configuration and generated env files | `config/topology.yaml`, `scripts/generate_env.py` | Docker Compose, frontend proxy, Python modules reading env | `config/CONTEXT.md`, `README.md` if human setup changes, ADR when ownership changes | `make validate-config`; stack smoke test when ports or hosts change |
| Timescale storage shape and continuous aggregates | `timescaledb-init`, `database-accessor-api` | `ingestion-service`, `indicator-api`, `backtester`, `frontend` through queries | Root `CONTEXT.md`, `timescaledb-init/CONTEXT.md`, `database-accessor-api/CONTEXT.md`, affected consumer contexts | Database accessor tests; stack test when SQL migration behavior changes |
| Durable backtest run persistence | `backtester`, `database-accessor-api`, `timescaledb-init` | `backtester`, `libs/db_accessor_client` | Root `CONTEXT.md`, `backtester/CONTEXT.md`, `database-accessor-api/CONTEXT.md`, `timescaledb-init/CONTEXT.md`, `libs/CONTEXT.md`, ADR-0005 | Backtester, database accessor, and shared client tests plus Python verification |

## Update Rule

If a change modifies a contract in this table, update the producer context and
every consumer context that must know the new interface. If the change only
changes an implementation behind the same interface, leave root `CONTEXT.md`
alone and update only the relevant area context when it adds durable locality
knowledge.
