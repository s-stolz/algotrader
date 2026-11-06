# Python dependency audit

Observed 2026-11-06. Installed means local `.venv` metadata or live container `pip list`; these are separate environments. Latest means PyPI JSON `info.version`, not a tested compatible resolution. All services declare Python >=3.12,<3.13. No packages were changed.

## Resolution and scope

`constraints-shared.txt` pins the main runtime versions; the lower bounds in pyproject files are not the installed versions. Build requirements are setuptools>=68 and wheel in all nine Python projects. Root tools come from requirements.root.txt. Transitive packages are not fully locked: container and local installations differ, notably python-dateutil 4.0.0 versus 2.9.0.post0. Resolve and capture complete dependency sets before upgrades.

## Direct inventory by project

### backtester

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `db-accessor-client` | 0.1.0 | 0.1.0 | internal workspace package |
| `indicator-engine` | 0.0.0 | 0.0.0 | internal workspace package |
| `fastapi>=0.128.0` | 0.128.0 | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| `pandas>=2.1.0` | 2.3.2 | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| `numpy>=1.24.0` | 2.2.6 | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| `pydantic>=2.12.0` | 2.12.2 | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| `PyYAML>=6.0` | 6.0.3 | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| `uvicorn[standard]>=0.40.0` | 0.40.0 | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| `redis>=7.1.0` | 7.1.0 | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| `ruff>=0.14.11` | not installed | not installed / no own container | [0.17.4](https://pypi.org/project/ruff/) |
| `black>=24.4.2` | not installed | not installed / no own container | [26.10.1](https://pypi.org/project/black/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### broker-service

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `algotrader-logger` | 0.1.0 | 0.1.0 | internal workspace package |
| `fastapi>=0.128.0` | 0.128.0 | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| `uvicorn[standard]>=0.40.0` | 0.40.0 | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| `redis>=7.1.0` | 7.1.0 | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| `ctrader-open-api>=0.9.2` | 0.9.2 | 0.9.2 | [0.9.2](https://pypi.org/project/ctrader-open-api/) |
| `service_identity>=24.2.0` | 24.2.0 | 24.2.0 | [26.1.0](https://pypi.org/project/service_identity/) |
| `httpx>=0.28.1` | 0.28.1 | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| `ruff>=0.14.11` | not installed | not installed / no own container | [0.17.4](https://pypi.org/project/ruff/) |
| `black>=24.4.2` | not installed | not installed / no own container | [26.10.1](https://pypi.org/project/black/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### database-accessor-api

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `algotrader-logger` | 0.1.0 | 0.1.0 | internal workspace package |
| `fastapi` | 0.128.0 | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| `uvicorn[standard]` | 0.40.0 | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| `sqlalchemy[asyncio]` | 2.0.50 | 2.0.50 | [2.1.8](https://pypi.org/project/sqlalchemy/) |
| `asyncpg` | 0.31.0 | 0.31.0 | [0.32.0](https://pypi.org/project/asyncpg/) |
| `pydantic` | 2.12.2 | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| `ruff>=0.14.11` | not installed | not installed / no own container | [0.17.4](https://pypi.org/project/ruff/) |
| `black>=24.4.2` | not installed | not installed / no own container | [26.10.1](https://pypi.org/project/black/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### indicator-api

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `algotrader-logger` | 0.1.0 | 0.1.0 | internal workspace package |
| `db-accessor-client` | 0.1.0 | 0.1.0 | internal workspace package |
| `indicator-engine` | 0.0.0 | 0.0.0 | internal workspace package |
| `fastapi>=0.116.1` | 0.128.0 | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| `uvicorn[standard]>=0.24.0` | 0.40.0 | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| `pydantic>=2.0.0` | 2.12.2 | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| `pandas>=2.3.2` | 2.3.2 | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| `numpy>=2.2.6` | 2.2.6 | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| `httpx>=0.28.1` | 0.28.1 | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| `redis>=7.1.0` | 7.1.0 | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| `ruff>=0.14.11` | not installed | not installed / no own container | [0.17.4](https://pypi.org/project/ruff/) |
| `black>=24.4.2` | not installed | not installed / no own container | [26.10.1](https://pypi.org/project/black/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### ingestion-service

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `algotrader-logger` | 0.1.0 | 0.1.0 | internal workspace package |
| `db-accessor-client` | 0.1.0 | 0.1.0 | internal workspace package |
| `redis>=7.1.0` | 7.1.0 | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| `httpx>=0.28.1` | 0.28.1 | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### libs/algotrader_logger

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### libs/db_accessor_client

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `httpx>=0.28.1` | 0.28.1 | not installed / no own container | [0.28.1](https://pypi.org/project/httpx/) |
| `pandas>=2.3.0` | 2.3.2 | not installed / no own container | [3.1.1](https://pypi.org/project/pandas/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### libs/indicator_engine

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `numpy>=2.2.6` | 2.2.6 | not installed / no own container | [2.5.4](https://pypi.org/project/numpy/) |
| `pandas>=2.3.2` | 2.3.2 | not installed / no own container | [3.1.1](https://pypi.org/project/pandas/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### realtime-service

| Dependency declaration | Local installed | Container installed | Latest stable candidate |
|---|---|---|---|
| `algotrader-logger` | 0.1.0 | 0.1.0 | internal workspace package |
| `websockets>=16.0` | 16.0 | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| `redis>=7.1.0` | 7.1.0 | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| `httpx>=0.28.1` | 0.28.1 | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| `aiohttp>=3.9.0` | 3.14.1 | 3.14.1 | [3.14.5](https://pypi.org/project/aiohttp/) |
| `setuptools>=68` | 84.2.1 | not installed / no own container | [84.2.1](https://pypi.org/project/setuptools/) |
| `wheel` | 0.48.0 | not installed / no own container | [0.48.0](https://pypi.org/project/wheel/) |

### Root tooling

| Package | Local installed | Latest |
|---|---|---|
| black | 26.5.1 | [26.10.1](https://pypi.org/project/black/) |
| ruff | 0.15.17 | [0.17.4](https://pypi.org/project/ruff/) |
| pyright | 1.1.409 | [1.1.414](https://pypi.org/project/pyright/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |

## Recommended sequence and important changes

1. **Capture reproducible baselines.** Save full resolutions for each Linux image and local development environment; preserve shared constraints. Verify the existing test gates before upgrading. Keep Python 3.12 during library changes. Candidate versions in this report still require dependency resolution and tests.
2. **Prioritize WebSocket protection:** websockets 16.0 → 17.4 in realtime and every Uvicorn service. 17.4 limits fragmented messages to prevent memory-exhaustion denial of service. 17 requires Python 3.11+, removes old module aliases, makes several boolean arguments keyword-only, and changes handshake hooks for non-GET/HTTP-1.0 requests. Check handshake rejection, fragmentation, disconnects, subscriptions, and reconnect recovery. [Official changelog](https://websockets.readthedocs.io/en/stable/project/changelog.html).
3. **Low-risk runtime maintenance:** aiohttp 3.14.1 → 3.14.5 and python-dotenv 1.2.1 → 1.2.4; retain HTTPX 0.28.1 and PyYAML 6.0.3 (already latest). Upgrade resolver-selected transitives with their owning package, not as an independent blanket operation. Validate HTTP timeout/error paths and environment loading. [aiohttp history](https://docs.aiohttp.org/en/stable/changes.html), [dotenv releases](https://github.com/theskumar/python-dotenv/releases).
4. **ASGI/API stack:** FastAPI 0.128.0 → 0.162.0, Pydantic 2.12.2 → 2.14.3, Uvicorn 0.40.0 → 0.54.0; resolve Starlette and pydantic-core together. FastAPI adds strict JSON Content-Type checking after the installed version, and the latest metadata adds opentelemetry-api as a dependency. Check browser/shared-client headers, 204 bodies, 404/409 contracts, OpenAPI snapshots, validation/serialization, startup and shutdown. Stage accessor first, then indicator API, backtester API/worker, broker. [FastAPI notes](https://fastapi.tiangolo.com/release-notes/), [Pydantic history](https://docs.pydantic.dev/latest/changelog/), [Uvicorn notes](https://www.uvicorn.org/release-notes/).
5. **Persistence separately:** SQLAlchemy 2.0.50 → 2.1.8 and asyncpg 0.31.0 → 0.32.0. SQLAlchemy 2.1 makes session autoflush unconditional and no longer installs greenlet by default; this repository already requests sqlalchemy[asyncio], which retains greenlet. Mapped dataclass defaults and composite None behavior also change. Exercise transaction/rollback, lifecycle concurrency, deletion and migrations against disposable PostgreSQL before consumers. [SQLAlchemy migration](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html), [asyncpg releases](https://github.com/MagicStack/asyncpg/releases).
6. **Redis client migration across all five consumers:** redis-py 7.1.0 → 8.1.0. Version 8 defaults to RESP3 while retaining legacy response shapes by default; connection/socket timeout defaults become five seconds, pools default to 100 connections and retries increase to ten with jitter. Explicitly choose protocol, socket timeouts and retry policy; verify blocking Streams reads, cancellation, reconnection, pub/sub and held execution-slot recovery. Keep the Redis server upgrade separate. [redis-py releases](https://github.com/redis/redis-py/releases).
7. **Numerical stack in two changes:** NumPy 2.2.6 → 2.5.4 first, then pandas 2.3.2 → 3.1.1. NumPy target supports Python 3.12. pandas 3 makes Copy-on-Write mandatory, infers dedicated string dtype and changes datetime-resolution assumptions. Validate epoch-ms conversion explicitly, view/mutation behavior, NaNs, dtypes, candle ordering and numerical parity. Order: indicator_engine and db_accessor_client, then indicator-api/backtester, then ingestion (which receives pandas through the shared client). Preserve benchmark and deterministic backtest outputs. [NumPy releases](https://numpy.org/doc/stable/release.html), [pandas 3 migration](https://pandas.pydata.org/pandas-docs/stable/whatsnew/v3.0.0.html).
8. **Broker dependency blocker, investigate in parallel:** ctrader-open-api 0.9.2 is already latest but pins Twisted==24.3.0, pyOpenSSL==24.1.0, protobuf==3.20.1, requests==2.32.3, inputimeout==1.0.4. Do not override those blindly; arrange upstream support or a deliberately maintained/tested SDK fork before upgrading them. service-identity 24.2.0 → 26.1.0 must be resolved against this TLS stack. Test TLS verification, authentication, reconnect, command correlation and tick/candle parsing with a demo broker. [SDK authoritative dependency metadata](https://pypi.org/pypi/ctrader-open-api/0.9.2/json).
9. **Tooling in an isolated change:** Black 26.5.1 → 26.10.1, Ruff 0.15.17 → 0.17.4, Pyright 1.1.409 → 1.1.414; review formatting/rule/type-check differences independently of runtime migration. setuptools 84.2.1 and wheel 0.48.0 already match latest.

## Verification and rollout

Use `make test <area>` for each changed service, `make test indicator_engine` and `make test db_accessor_client` for shared numerical/client work, `make typecheck-python` for all Python changes, then `make verify`. Run live storage tests and `make smoke-backtester` in a disposable Compose project. Backtester API and worker have identical observed package inventories and should be rebuilt/released together; follow the worker recovery runbook. Keep previous image digests for rollback. No upgrade compatibility tests were run for this research-only change.

## Complete installed dependency appendix

Includes direct, transitive, build and development packages observed in all local environments and running service containers. “Latest” is an update check, not approval to bypass dependency constraints. Internal packages have no public-registry target. Each registry version was fetched from `https://pypi.org/pypi/<name>/json`.

### Container: backtester-api

| Package | Installed | Registry latest |
|---|---|---|
| annotated-doc | 0.0.5 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.8.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| backtester | 0.0.0 | internal |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.5.0 | [8.5.0](https://pypi.org/project/click/) |
| db-accessor-client | 0.1.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.9.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| indicator-engine | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dateutil | 4.0.0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.6 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.5 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.6 | [2026.6](https://pypi.org/project/tzdata/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.23.0 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.3.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |

### Container: backtester-worker

| Package | Installed | Registry latest |
|---|---|---|
| annotated-doc | 0.0.5 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.8.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| backtester | 0.0.0 | internal |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.5.0 | [8.5.0](https://pypi.org/project/click/) |
| db-accessor-client | 0.1.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.9.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| indicator-engine | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dateutil | 4.0.0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.6 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.5 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.6 | [2026.6](https://pypi.org/project/tzdata/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.23.0 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.3.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |

### Container: broker-service

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.5 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.8.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| attrs | 26.1.0 | [26.1.0](https://pypi.org/project/attrs/) |
| Automat | 25.4.16 | [25.4.16](https://pypi.org/project/Automat/) |
| broker-service | 0.0.0 | internal |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| cffi | 2.1.1 | [2.1.1](https://pypi.org/project/cffi/) |
| charset-normalizer | 3.5.2 | [3.5.2](https://pypi.org/project/charset-normalizer/) |
| click | 8.5.0 | [8.5.0](https://pypi.org/project/click/) |
| constantly | 23.10.4 | [23.10.4](https://pypi.org/project/constantly/) |
| cryptography | 42.0.8 | [50.0.2](https://pypi.org/project/cryptography/) |
| ctrader_open_api | 0.9.2 | [0.9.2](https://pypi.org/project/ctrader_open_api/) |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.9.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| hyperlink | 21.0.0 | [21.0.0](https://pypi.org/project/hyperlink/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| Incremental | 24.11.0 | [24.11.0](https://pypi.org/project/Incremental/) |
| inputimeout | 1.0.4 | [1.0.4](https://pypi.org/project/inputimeout/) |
| packaging | 26.3 | [26.3](https://pypi.org/project/packaging/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| protobuf | 3.20.1 | [7.36.2](https://pypi.org/project/protobuf/) |
| pyasn1 | 0.6.5 | [0.6.5](https://pypi.org/project/pyasn1/) |
| pyasn1_modules | 0.4.2 | [0.4.2](https://pypi.org/project/pyasn1_modules/) |
| pycparser | 3.12 | [3.12](https://pypi.org/project/pycparser/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| pyOpenSSL | 24.1.0 | [26.4.0](https://pypi.org/project/pyOpenSSL/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| requests | 2.32.3 | [2.34.2](https://pypi.org/project/requests/) |
| service-identity | 24.2.0 | [26.1.0](https://pypi.org/project/service-identity/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| Twisted | 24.3.0 | [26.10.0](https://pypi.org/project/Twisted/) |
| typing-inspection | 0.4.5 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| urllib3 | 2.8.0 | [2.8.0](https://pypi.org/project/urllib3/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.23.0 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.3.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| zope.interface | 8.7 | [8.7](https://pypi.org/project/zope.interface/) |

### Container: database-accessor-api

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.5 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.8.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| asyncpg | 0.31.0 | [0.32.0](https://pypi.org/project/asyncpg/) |
| click | 8.5.0 | [8.5.0](https://pypi.org/project/click/) |
| database-accessor-api | 0.0.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| greenlet | 3.5.6 | [3.5.6](https://pypi.org/project/greenlet/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httptools | 0.9.0 | [0.9.0](https://pypi.org/project/httptools/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| SQLAlchemy | 2.0.50 | [2.1.8](https://pypi.org/project/SQLAlchemy/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.5 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.23.0 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.3.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |

### Container: indicator-api

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.5 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.8.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.5.0 | [8.5.0](https://pypi.org/project/click/) |
| db-accessor-client | 0.1.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.9.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| indicator-api | 0.0.0 | internal |
| indicator-engine | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dateutil | 4.0.0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.6 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.5 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.6 | [2026.6](https://pypi.org/project/tzdata/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.23.0 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.3.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |

### Container: ingestion-service

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| db-accessor-client | 0.1.0 | internal |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| ingestion-service | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| python-dateutil | 4.0.0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| pytz | 2026.6 | [2026.6](https://pypi.org/project/pytz/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.6 | [2026.6](https://pypi.org/project/tzdata/) |

### Container: realtime-service

| Package | Installed | Registry latest |
|---|---|---|
| aiohappyeyeballs | 2.7.1 | [2.7.1](https://pypi.org/project/aiohappyeyeballs/) |
| aiohttp | 3.14.1 | [3.14.5](https://pypi.org/project/aiohttp/) |
| aiosignal | 1.4.0 | [1.4.0](https://pypi.org/project/aiosignal/) |
| algotrader-logger | 0.1.0 | internal |
| anyio | 4.16.0 | [4.16.0](https://pypi.org/project/anyio/) |
| attrs | 26.1.0 | [26.1.0](https://pypi.org/project/attrs/) |
| certifi | 2026.10.23 | [2026.10.23](https://pypi.org/project/certifi/) |
| frozenlist | 1.8.0 | [1.8.0](https://pypi.org/project/frozenlist/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.20 | [3.20](https://pypi.org/project/idna/) |
| multidict | 6.9.1 | [7.2.1](https://pypi.org/project/multidict/) |
| pip | 25.0.1 | [26.3](https://pypi.org/project/pip/) |
| propcache | 0.5.4 | [0.5.4](https://pypi.org/project/propcache/) |
| realtime-service | 0.0.0 | internal |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| typing_extensions | 4.16.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| yarl | 1.25.1 | [1.25.1](https://pypi.org/project/yarl/) |

### Local: .venv

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| black | 26.5.1 | [26.10.1](https://pypi.org/project/black/) |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.4.1 | [8.5.0](https://pypi.org/project/click/) |
| coverage | 7.14.1 | [7.17.2](https://pypi.org/project/coverage/) |
| db-accessor-client | 0.1.0 | internal |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| indicator-engine | 0.0.0 | internal |
| iniconfig | 2.3.0 | [2.3.1](https://pypi.org/project/iniconfig/) |
| mypy_extensions | 1.1.0 | [1.2.0](https://pypi.org/project/mypy_extensions/) |
| nodeenv | 1.10.0 | [1.12.0](https://pypi.org/project/nodeenv/) |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pathspec | 1.1.1 | [1.1.1](https://pypi.org/project/pathspec/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| platformdirs | 4.10.0 | [4.14.5](https://pypi.org/project/platformdirs/) |
| pluggy | 1.6.0 | [1.7.0](https://pypi.org/project/pluggy/) |
| Pygments | 2.20.0 | [2.21.0](https://pypi.org/project/Pygments/) |
| pyright | 1.1.409 | [1.1.414](https://pypi.org/project/pyright/) |
| pytest | 9.0.3 | [9.2.0](https://pypi.org/project/pytest/) |
| pytest-cov | 7.1.0 | [7.1.0](https://pypi.org/project/pytest-cov/) |
| python-dateutil | 2.9.0.post0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| pytokens | 0.4.1 | [0.4.1](https://pypi.org/project/pytokens/) |
| pytz | 2026.2 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| ruff | 0.15.17 | [0.17.4](https://pypi.org/project/ruff/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| six | 1.17.0 | [1.17.0](https://pypi.org/project/six/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.2 | [2026.6](https://pypi.org/project/tzdata/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |

### Local: backtester/.venv

| Package | Installed | Registry latest |
|---|---|---|
| annotated-doc | 0.0.4 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.7.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| backtester | 0.0.0 | internal |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.4.1 | [8.5.0](https://pypi.org/project/click/) |
| db-accessor-client | 0.1.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.8.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| indicator-engine | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dateutil | 2.9.0.post0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.2 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| six | 1.17.0 | [1.17.0](https://pypi.org/project/six/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.2 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.2 | [2026.6](https://pypi.org/project/tzdata/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.22.1 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchdog | 3.0.0 | [7.1.0](https://pypi.org/project/watchdog/) |
| watchfiles | 1.2.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |

### Local: broker-service/.venv

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.4 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.7.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| attrs | 26.1.0 | [26.1.0](https://pypi.org/project/attrs/) |
| Automat | 25.4.16 | [25.4.16](https://pypi.org/project/Automat/) |
| broker-service | 0.0.0 | internal |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| cffi | 2.0.0 | [2.1.1](https://pypi.org/project/cffi/) |
| charset-normalizer | 3.4.7 | [3.5.2](https://pypi.org/project/charset-normalizer/) |
| click | 8.4.1 | [8.5.0](https://pypi.org/project/click/) |
| constantly | 23.10.4 | [23.10.4](https://pypi.org/project/constantly/) |
| cryptography | 42.0.8 | [50.0.2](https://pypi.org/project/cryptography/) |
| ctrader_open_api | 0.9.2 | [0.9.2](https://pypi.org/project/ctrader_open_api/) |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.8.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| hyperlink | 21.0.0 | [21.0.0](https://pypi.org/project/hyperlink/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| Incremental | 24.11.0 | [24.11.0](https://pypi.org/project/Incremental/) |
| inputimeout | 1.0.4 | [1.0.4](https://pypi.org/project/inputimeout/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| protobuf | 3.20.1 | [7.36.2](https://pypi.org/project/protobuf/) |
| pyasn1 | 0.6.3 | [0.6.5](https://pypi.org/project/pyasn1/) |
| pyasn1_modules | 0.4.2 | [0.4.2](https://pypi.org/project/pyasn1_modules/) |
| pycparser | 3.0 | [3.12](https://pypi.org/project/pycparser/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| pyOpenSSL | 24.1.0 | [26.4.0](https://pypi.org/project/pyOpenSSL/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| requests | 2.32.3 | [2.34.2](https://pypi.org/project/requests/) |
| service-identity | 24.2.0 | [26.1.0](https://pypi.org/project/service-identity/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| Twisted | 24.3.0 | [26.10.0](https://pypi.org/project/Twisted/) |
| typing-inspection | 0.4.2 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| urllib3 | 2.7.0 | [2.8.0](https://pypi.org/project/urllib3/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.22.1 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.2.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |
| zope.interface | 8.5 | [8.7](https://pypi.org/project/zope.interface/) |

### Local: database-accessor-api/.venv

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.4 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.7.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| asyncpg | 0.31.0 | [0.32.0](https://pypi.org/project/asyncpg/) |
| certifi | 2026.7.22 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.4.1 | [8.5.0](https://pypi.org/project/click/) |
| database-accessor-api | 0.0.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| greenlet | 3.5.1 | [3.5.6](https://pypi.org/project/greenlet/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.8.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| SQLAlchemy | 2.0.50 | [2.1.8](https://pypi.org/project/SQLAlchemy/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.2 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.22.1 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchfiles | 1.2.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |

### Local: indicator-api/.venv

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| annotated-doc | 0.0.4 | [0.0.5](https://pypi.org/project/annotated-doc/) |
| annotated-types | 0.7.0 | [0.8.0](https://pypi.org/project/annotated-types/) |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| click | 8.4.1 | [8.5.0](https://pypi.org/project/click/) |
| db-accessor-client | 0.1.0 | internal |
| fastapi | 0.128.0 | [0.162.0](https://pypi.org/project/fastapi/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httptools | 0.8.0 | [0.9.0](https://pypi.org/project/httptools/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| indicator-api | 0.0.0 | internal |
| indicator-engine | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| pydantic | 2.12.2 | [2.14.3](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.41.4 | [2.50.4](https://pypi.org/project/pydantic_core/) |
| python-dateutil | 2.9.0.post0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.2 | [2026.6](https://pypi.org/project/pytz/) |
| PyYAML | 6.0.3 | [6.0.3](https://pypi.org/project/PyYAML/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| six | 1.17.0 | [1.17.0](https://pypi.org/project/six/) |
| starlette | 0.50.0 | [1.10.0](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.2 | [0.4.5](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.2 | [2026.6](https://pypi.org/project/tzdata/) |
| uvicorn | 0.40.0 | [0.54.0](https://pypi.org/project/uvicorn/) |
| uvloop | 0.22.1 | [0.23.0](https://pypi.org/project/uvloop/) |
| watchdog | 3.0.0 | [7.1.0](https://pypi.org/project/watchdog/) |
| watchfiles | 1.2.0 | [1.3.0](https://pypi.org/project/watchfiles/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |

### Local: ingestion-service/.venv

| Package | Installed | Registry latest |
|---|---|---|
| algotrader-logger | 0.1.0 | internal |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| db-accessor-client | 0.1.0 | internal |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| ingestion-service | 0.0.0 | internal |
| numpy | 2.2.6 | [2.5.4](https://pypi.org/project/numpy/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pandas | 2.3.2 | [3.1.1](https://pypi.org/project/pandas/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| python-dateutil | 2.9.0.post0 | [4.0.0](https://pypi.org/project/python-dateutil/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| pytz | 2026.2 | [2026.6](https://pypi.org/project/pytz/) |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| six | 1.17.0 | [1.17.0](https://pypi.org/project/six/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| tzdata | 2026.2 | [2026.6](https://pypi.org/project/tzdata/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |

### Local: realtime-service/.venv

| Package | Installed | Registry latest |
|---|---|---|
| aiohappyeyeballs | 2.6.2 | [2.7.1](https://pypi.org/project/aiohappyeyeballs/) |
| aiohttp | 3.14.1 | [3.14.5](https://pypi.org/project/aiohttp/) |
| aiosignal | 1.4.0 | [1.4.0](https://pypi.org/project/aiosignal/) |
| algotrader-logger | 0.1.0 | internal |
| anyio | 4.13.0 | [4.16.0](https://pypi.org/project/anyio/) |
| attrs | 26.1.0 | [26.1.0](https://pypi.org/project/attrs/) |
| certifi | 2026.5.20 | [2026.10.23](https://pypi.org/project/certifi/) |
| frozenlist | 1.8.0 | [1.8.0](https://pypi.org/project/frozenlist/) |
| h11 | 0.16.0 | [0.16.0](https://pypi.org/project/h11/) |
| httpcore | 1.0.9 | [1.0.9](https://pypi.org/project/httpcore/) |
| httpx | 0.28.1 | [0.28.1](https://pypi.org/project/httpx/) |
| idna | 3.18 | [3.20](https://pypi.org/project/idna/) |
| multidict | 6.7.1 | [7.2.1](https://pypi.org/project/multidict/) |
| packaging | 26.2 | [26.3](https://pypi.org/project/packaging/) |
| pip | 26.3 | [26.3](https://pypi.org/project/pip/) |
| propcache | 0.5.2 | [0.5.4](https://pypi.org/project/propcache/) |
| python-dotenv | 1.2.1 | [1.2.4](https://pypi.org/project/python-dotenv/) |
| realtime-service | 0.0.0 | internal |
| redis | 7.1.0 | [8.1.0](https://pypi.org/project/redis/) |
| setuptools | 84.2.1 | [84.2.1](https://pypi.org/project/setuptools/) |
| typing_extensions | 4.15.0 | [4.16.0](https://pypi.org/project/typing_extensions/) |
| websockets | 16.0 | [17.4](https://pypi.org/project/websockets/) |
| wheel | 0.48.0 | [0.48.0](https://pypi.org/project/wheel/) |
| yarl | 1.24.2 | [1.25.1](https://pypi.org/project/yarl/) |
