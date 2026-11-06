# Dependency upgrade plan

Historical audit and initial plan. See [implementation results](dependency-upgrade-results.md) for the final scope, approved exceptions and validation.

Audit date: 2026-11-06. This is a planning snapshot; no dependencies or running services were changed. Targets are candidates until the compatibility gates below pass. Recheck registry releases when implementing.

## Inventory and evidence

- [Python services, shared libraries and developer tooling](python-dependency-audit.md): dependency versions, update availability and migration notes.
- [Frontend dependencies and tooling](frontend-dependency-audit.md): declared, resolved and observed versions, targets and migration notes.
- Runtime/storage observations below were read directly from running Docker containers. Floating image tags do not identify installed patch versions.

| Component | Repository declaration | Observed running version | Candidate and decision |
| --- | --- | --- | --- |
| Frontend Node.js | `node:20-bookworm` | 20.20.2 | Move to Node 24 LTS first; evaluate 26 LTS after toolchain validation |
| Python services | Python 3.12 images | 3.12 image line; patch not measured | Refresh 3.12 security patches first; evaluate 3.14 separately after SDK/numeric wheel compatibility |
| PostgreSQL | Timescale `latest-pg17` image | 17.2 | 17.11, paired with a compatible Timescale image; keep major 17 initially |
| TimescaleDB extension | `latest-pg17` | 2.18.0 | 2.31.0 candidate; rehearse supported extension upgrade path on restored data |
| Redis server | `redis:7-alpine` | 7.4.12 | Evaluate stable 8.10 line separately from redis-py upgrades; select exact patch/image digest during rehearsal |

Node 20 is end-of-life; 24 remains supported and 26 is active LTS. The conservative Node 24 stepping stone is a project recommendation, not an upstream requirement. [Node release schedule](https://github.com/nodejs/Release).

Python 3.12 remains in security support; upstream lists 3.12.16, 3.14.10 and 3.15.2. Keeping 3.12 initially avoids combining interpreter changes with dependency migrations. [Python releases](https://www.python.org/getit/).

PostgreSQL lists 17.11 as the current 17 patch and 18.6 as the newer stable major. Patch updates include security and correctness fixes; major upgrades require pg_upgrade or dump/restore. [Version policy](https://www.postgresql.org/support/versioning/).

Timescale 2.31 improves compressed-data UPDATE/DELETE and aggregation, adds continuous-aggregate refresh statistics, and fixes correctness issues involving compressed chunks and aggregate invalidation. It renames a debug column-scan setting; experimental integer compression remains off by default. These matter to candle corrections and higher-timeframe reads. Check every intervening release and image/extension compatibility before selecting the upgrade path. [Timescale release notes](https://github.com/timescale/timescaledb/releases).

Redis 8.10 introduces more flexible stream consumption and core/stream performance improvements. New commands are optional; preserve existing stream delivery semantics during the server migration. [Redis 8.10 changes](https://redis.io/docs/latest/develop/whats-new/8-10/). Review licensing and persistence compatibility when selecting the exact distribution.

## Ordered implementation batches

| Order | Scope | Work and reason | Acceptance gate |
| --- | --- | --- | --- |
| 0 | All services | Preserve observed package inventories and current image digests; establish reproducible resolved environments. Reconcile host/container drift before changing shared pins. Baseline tests and representative backtest outputs. | Clean dependency resolution, pip check/npm dependency tree, existing tests pass; save rollback artifacts |
| 1 | Runtime and maintenance | Prioritize websockets 16.0 → 17.4 for the fragmentation memory-exhaustion fix (see Python report). Replace Node 20 with supported LTS; patch Python 3.12 images. Apply compatible package patch/minor updates in small groups. Keep broker SDK constraints isolated. | Build all images; affected service tests; frontend lint/types/tests/build |
| 2 | Shared Python HTTP/API stack | Upgrade shared client/logging dependencies and FastAPI/Pydantic/Uvicorn as a compatible set. Validate accessor first, then broker/ingestion, indicator, backtester API/worker and realtime consumers. Shared constraints require coordinated rebuilds. | Serialization, validation errors, timestamps, cancellation and connection lifecycle remain compatible; Python types |
| 3 | Storage maintenance | Rehearse PostgreSQL 17 patch plus Timescale extension upgrade on a restored copy. Pin tested image digest. Do not combine this with PostgreSQL 18 or schema redesign. | Backup restore proven; migration ledger, candle upsert, compression, aggregate refresh and durable backtest integration checks |
| 4 | Numerical engine | Upgrade NumPy within supported ABI bounds, then pandas major separately, coordinating indicator_engine, indicator-api and backtester. | Indicator/backtest golden outputs, NaN handling, timestamps, dtype and memory/performance checks; explain any numeric changes |
| 5 | Messaging | Upgrade redis-py and remaining messaging clients with server unchanged first; then Redis server in its own batch. Rebuild broker, ingestion, indicator, realtime and backtester consumers. | Reconnect, subscription cleanup, duplicate/replayed candles, stream delivery, queued cancellation and verified worker exit |
| 6 | Frontend major migrations | Follow frontend report's peer-compatible order: build/test tooling, Vue ecosystem, Pinia/Router and chart API changes as distinct batches. | `make test frontend`; chart overlays and time conversion, workspace commands/history, reconnect and layout review |
| 7 | Optional runtime majors | Evaluate Python 3.14 (or newer only with full ecosystem support), Node 26 and PostgreSQL 18 independently. | Native wheels on slim and Alpine images, broker handshake, Linux worker supervision, full integration and restore rehearsal |

Urgent confirmed security fixes take precedence over this sequence. This audit is release/migration research, not a complete vulnerability or OS-package scan. Transitive dependencies should move through compatible parent dependency resolution, not indiscriminate independent major bumps.

## Rollout and verification

Each batch should be a separate reviewable change with exact version/digest targets, dependency resolution evidence, relevant release-note deltas and rollback instructions. For application-only changes retain prior images and resolved environments. For storage changes use a tested backup/restore recovery path; do not assume old binaries can read upgraded persisted state.

Use [repository gates](../agent/COMMANDS.md): affected `make test <area>`, `make typecheck-python` for Python changes and `make verify` at integration. Run opt-in PostgreSQL and transport checks explicitly; ordinary unit tests do not establish live coverage. Use the [worker cutover procedure](../operations/backtest-worker-recovery.md) before deployments with queued/running backtests. Never release a held execution slot based solely on a stale heartbeat.

This planning change only requires documentation link/path checks. Application tests are implementation acceptance criteria, not tests claimed to have been run for this audit.
