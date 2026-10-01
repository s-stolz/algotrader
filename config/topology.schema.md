# Topology Schema

`config/topology.yaml` owns tracked, non-secret configuration. Settings are grouped
by the component that uses them. Docker Compose and applications consume the
existing generated environment variables; YAML nesting does not change their names.

## Root structure

| Key | Purpose |
| --- | --- |
| `mode` | Runtime mode, such as `development`. |
| `public.host` | Browser and local CLI host, such as `localhost`. |
| `services` | Application networking, logging, resources, and runtime tuning. |
| `infrastructure` | Redis and TimescaleDB networking, resources, and database settings. |

There are no separate root-level `backtester`, `broker`, `ingestion`, `webserver`,
or `docker_resources` sections. Existing local topology customizations must move
with their owning component; the generator and CLI read the new paths directly.

## Component structure

| Component path | Settings groups |
| --- | --- |
| `services.database_accessor_api` | `network`, `logging`, `resources` |
| `services.indicator_api` | `network`, `logging`, `resources` |
| `services.backtester` | Shared `logging`, `api`, `worker`, `sweeps` |
| `services.backtester.api` | `network`, `resources` |
| `services.backtester.worker` | `resources`, `poll_interval_seconds`, `heartbeat` |
| `services.broker_service` | `network`, `logging`, `resources`, `streams`, `ctrader` |
| `services.ingestion_service` | `logging`, `resources`, `consumer`, `history` |
| `services.webserver` | `network`, `logging`, `resources`, `consumer`, `streams` |
| `services.frontend` | `network`, `resources` |
| `infrastructure.redis` | `network`, `resources`, `database` |
| `infrastructure.timescaledb` | `network`, `resources`, `database` |

Backtester API and worker share logging because both consume `BACKTESTER_LOG_*`.
They have independent resources because they run in separate containers. Workers
have no network endpoint, so they require no host or port settings.

## Networking

Single-endpoint components use:

```yaml
network:
  host: database-accessor-api
  port: 8000
  published_port: 8000
```

`host` is the internal service hostname. `port` is the internal port;
`published_port` is the port exposed on the host. Internal URLs and frontend proxy
targets use the internal host and port. The local backtester CLI uses `public.host`
and `services.database_accessor_api.network.published_port`, falling back to
`network.port` when the published port is absent.

Webserver shares one hostname across two named endpoints:

```yaml
network:
  host: webserver
  websocket:
    port: 8765
    published_port: 8765
  health:
    port: 8080
    published_port: 8080
```

The browser WebSocket URL uses `public.host` and `network.websocket.published_port`.
Ports are integers; hostnames are strings.

## Logging and resources

`logging` contains `level` (for example `INFO`) and `format` (`pretty` or `json`).
Ingestion logging also supplies the legacy `LOG_LEVEL` / `LOG_FORMAT` aliases.

Each container owns a `resources` mapping:

```yaml
resources:
  cpus: 0.5
  memory_reservation_mb: 256
```

- `cpus` must be finite and positive. `1.0` allows one CPU's worth of execution time.
- `memory_reservation_mb` must be a positive integer in MiB. Docker receives the
  `m` suffix. This is a soft reservation, not preallocated memory, a hard cap, or
  protection against running out of memory.

The generator maps these paths to the existing `COMPOSE_<SERVICE>_CPUS` and
`COMPOSE_<SERVICE>_MEMORY_RESERVATION` variables. For example,
`services.backtester.worker.resources.cpus` generates `COMPOSE_BACKTESTER_WORKER_CPUS`.
Compose service names and container names do not change with topology grouping.

## Runtime tuning

All fields below are required in the tracked topology. Numeric constraints
specified here describe the runtime contract; the generator validates presence
and resource values, while service settings enforce their own runtime constraints.

| Path under `services` | Fields and tracked defaults |
| --- | --- |
| `backtester.worker` | `poll_interval_seconds: 1.0` |
| `backtester.worker.heartbeat` | `interval_seconds: 5.0`, `stale_after_seconds: 30.0` |
| `backtester.sweeps` | `max_candidate_count: 1000` |
| `webserver.consumer` | `block_ms: 5000`, `batch_size: 100` |
| `webserver.streams` | `queue_size: 1000`, `max_length: 10000` |
| `ingestion_service.consumer` | `block_ms: 5000`, `batch_size: 100` |
| `broker_service.streams` | `redis_db: 0` |
| `broker_service.streams.ticks` | `queue_size: 1000`, `max_length: null` |
| `broker_service.streams.candles` | `max_length: null` |
| `broker_service.streams.limits` | `max_symbol_streams: 20`, `max_trendbar_streams: 10` |
| `broker_service.ctrader` | `request_timeout_seconds: 20.0` |

Worker polling and heartbeat intervals are positive; the stale threshold must
exceed the heartbeat interval. The sweep candidate limit is a positive integer.
Broker stream `max_length: null` preserves the existing unlimited retention and
omits the corresponding `BROKER_*_STREAM_MAXLEN` variable from the generated file.
Broker `streams.redis_db` selects its Redis database independently of the shared
Redis database setting.

## Infrastructure database settings

- `infrastructure.redis.database`: integer logical database index (default `0`).
- `infrastructure.timescaledb.database.name`: database name (default `finance_data`).
- `infrastructure.timescaledb.database.user`: database user (default `postgres`).
- `infrastructure.timescaledb.database.echo`: boolean SQL echo setting (default `false`).

TimescaleDB name and user generate both the `TIMESCALEDB_*` application variables
and `POSTGRES_*` image aliases.

## Generation and verification

Run `make config` after edits. `make validate-config` validates inputs and runs
configuration tests, including a fixture covering every generated variable with
empty secret inputs. If intentionally changing a default, update that fixture
with the corresponding runtime expectations.

Use `docker compose --env-file config/.env.shared config --quiet` to validate
Compose interpolation. Apply changed runtime values with `make up-detached`
between backtests. A structure-only edit that produces identical env files needs
no container restart.

## Secrets

Credentials remain in `config/.env.secrets.local`; they are never moved into the
tracked topology. Generated env files remain gitignored.

## Machine overrides and ingestion history

`config/topology.local.yaml` is an optional gitignored partial mapping merged
recursively over `topology.yaml` before validation and generation. Omitted fields
retain defaults; explicit `null` replaces a default. Unknown keys and changes from
mapping to scalar (or vice versa) are rejected. Copy `topology.local.example.yaml`
to get started. Keep secrets in `.env.secrets.local`.

`services.ingestion_service.history` requires exactly one active option:
`lookback_days` (positive integer, tracked default `90`) or `start_date` (quoted
`YYYY-MM-DD`, no future dates). Set the other option to `null`, including when
switching modes in an override. Dates begin at midnight UTC. Run `make config`
and recreate affected containers after editing overrides.
