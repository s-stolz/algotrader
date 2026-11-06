# Dependency migration results

Implementation: 2026-11-06. This supersedes the conservative sequencing recommendations in the original [upgrade plan](dependency-upgrade-plan.md). The agreed policy is latest stable packages and active LTS runtimes, with individually approved compatibility exceptions. No backup or restore rehearsal was requested; the PostgreSQL export/import was the required major-version migration itself.

## Versions and exceptions

- Python services: 3.15.2, including the broker; local service environments recreated on 3.15.2. Package metadata permits 3.12–3.15, preserving the supported development range.
- Node: 26.13.0 active LTS, selected by `.nvmrc` and the frontend Dockerfile; installed locally through nvm.
- PostgreSQL: 17.2 → 18.6. TimescaleDB: 2.18.0 → 2.31.0. The extension was upgraded on PostgreSQL 17 first, then the database transferred to PostgreSQL 18 with the same extension version.
- Redis server: 7.4.12 → 8.10.3. Existing Redis volume retained.
- Exact Python targets are in `constraints-shared.txt`; frontend targets and complete resolution are in `frontend/package.json` and `frontend/package-lock.json`.
- **Approved exception:** TypeScript stays at 6.0.3 because current typescript-eslint requires TypeScript <6.1.
- **Approved exception:** cTrader SDK 0.9.2 retains its required Twisted, protobuf, requests and pyOpenSSL versions. `broker-service/constraints.override.txt` retains service-identity 24.2.0 because newer identity requires a cryptography version incompatible with the SDK's pyOpenSSL pin. No fork or replacement was introduced.

## Migration changes

- Replaced deprecated pandas in-place operations with returned DataFrames, preserving sorting, filtering and indexing. Updated a warmup count expression for current pandas typing. Datetime-index fallback conversion now explicitly uses milliseconds; regression coverage checks millisecond, microsecond and nanosecond indexes.
- Selected RESP2 explicitly at Redis consumer boundaries to preserve response structures, with matching type narrowing for stream reads.
- Migrated frontend tooling to Vite 8, Vitest 5, ESLint 10 and jsdom 31; upgraded Vue, Pinia, Router, UI and chart libraries to audited stable targets.
- Selected ESM icon entry points after browser validation found CommonJS wrapper objects rendering as empty components under Vite 8. Added SVG assertions to chart-mode control coverage.
- Restored creation-modal scrolling after Naive UI renamed its internal card content class. The modal now uses the supported content-style property; a rendered-component regression and desktop, mobile and short-window browser checks cover the fix. The subsequent full frontend gate passed with 408 unit tests.
- Updated style assertions for jsdom's resolved CSS variables and supplied the theme variable missing from two focus fixtures.
- Made broker callback synchronization explicit in its test instead of relying on executor scheduling, and made the realtime test wait for notification delivery rather than an earlier connection flag. The ingestion recovery test now waits for its injected storage failure as well as paused writes, avoiding an earlier transient pause.
- Added the accessor's HTTPX development dependency and a `--dev` installation option used by local environment setup. Clean service images do not acquire test-only dependencies. The Makefile now resolves the root interpreter absolutely so shared-library tests cannot fall back to an unconfigured global Python.

## Storage preservation

Before and after the PostgreSQL transfer, counts matched exactly: 9,106,327 candles, 8 markets, 3 Backtests, 3 Runs and 21 migration-ledger records. PostgreSQL 18 uses the `timescaledb_data_pg18` Compose volume mounted at `/var/lib/postgresql`, matching the image's new data layout. The original PostgreSQL 17 volume was not overwritten or deleted. The temporary migration transfer file and migration/test containers were removed after validation.

## Validation

- `make verify` passed on Python 3.15.2 / Node 26.13.0: Python lint/types and backend suites, plus frontend formatting/readability/tooling/lint/types/layout, 407 unit tests and production build. After the final timestamp correction, all 335 backtester tests and all Python type checks passed again; the 3 adapter tests also passed in the final Linux image.
- `make validate-config`: 50 tests, 15 opt-in skips; configuration valid. All seven local environments passed installed-pin checks and `pip check`.
- Linux backtester suite passed (334 tests before the final additional timestamp regression; 3 opt-in skips), exercising Linux process supervision. Accessor and broker Linux suites passed with their cross-service fixture directories/test dependencies supplied. Linux realtime passed all 5 tests. Linux ingestion passed all 51 tests (3 opt-in skips) when run serially; earlier resource-contention timeouts were not accepted as passing evidence.
- The isolated `scripts/smoke_recovery.py` acceptance harness passed process restart, history, inactivity, storage and migration checks against PostgreSQL 18 / Timescale 2.31 / Redis 8.10.3. It used a separate combined test environment with SQLAlchemy's asyncio extra and the compatible broker dependency set.
- Final deployed stack: all configured health checks passed; broker cTrader/Redis/stream/token components report up and worker queue health is healthy. Deployed backtest smoke: queued → running → succeeded, with 2 fills and 1 trade; deliberate failure produced a failed run with no fill/trade artifacts.
- Browser: candles rendered, chart mode switched and survived navigation, saved history loaded, creation drawer opened/closed, no console warnings/errors after ESM icon correction.

The original audit documents remain historical observations, not the current installed inventory. Unit-suite skips do not stand in for live storage/transport coverage; those checks are reported separately above.

## Remaining limitations

`npm audit` reports 14 moderate findings through development-tool dependency paths (glob/minimatch), with zero high or critical findings after compatible transitive updates fixed lodash/lodash-es. Current parent packages constrain the affected major versions; moving them requires upstream support or a separately evaluated override/tooling change. No forced incompatible overrides or tool replacements were applied. See [glob advisory](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4) and [minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249). The build also retains its large-bundle advisory. These are not a claim of a complete security audit.
