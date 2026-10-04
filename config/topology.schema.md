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

Use [topology.yaml](topology.yaml) for exact setting names and defaults.
The generator validates presence and resource values; service settings enforce
runtime-specific constraints. Backtester API/worker tuning is grouped under
`services.backtester`; stream limits and cTrader settings belong to
`services.broker_service`.

Worker polling and heartbeat intervals are positive; the stale threshold must
exceed the heartbeat interval. The sweep candidate limit is a positive integer.
Broker stream `max_length: null` preserves the existing unlimited retention and
omits the corresponding `BROKER_*_STREAM_MAXLEN` variable from the generated file.
Broker `streams.redis_db` selects its Redis database independently of the shared
Redis database setting.

## Infrastructure database settings

- `infrastructure.redis.database`: integer logical database index.
- `infrastructure.timescaledb.database.name`: database name.
- `infrastructure.timescaledb.database.user`: database user.
- `infrastructure.timescaledb.database.echo`: boolean SQL echo setting.

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
`lookback_days` (positive integer) or `start_date` (quoted
`YYYY-MM-DD`, no future dates). Set the other option to `null`, including when
switching modes in an override. Dates begin at midnight UTC. Run `make config`
and recreate affected containers after editing overrides.
