# Topology Schema

`config/topology.yaml` is the tracked source of truth for non-secret configuration.

## Root keys
- `mode` (string): runtime mode (`development`, `production`, etc.)
- `public.host` (string): host used for browser-facing URLs
- `services` (map): service host/port topology
- `infrastructure` (map): shared infra hosts/ports/databases
- `webserver` (map): webserver stream tuning values
- `ingestion` (map): ingestion-service tuning values
- `backtester` (map): backtester worker tuning values
- `broker` (map): broker-service non-secret tuning values

## Required service keys
- `services.database_accessor_api.host` (string)
- `services.database_accessor_api.port` (int)
- `services.database_accessor_api.published_port` (int)
- `services.indicator_api.host` (string)
- `services.indicator_api.port` (int)
- `services.indicator_api.published_port` (int)
- `services.backtester_api.host` (string)
- `services.backtester_api.port` (int)
- `services.backtester_api.published_port` (int)
- `services.backtester_api.log_level` (string)
- `services.backtester_api.log_format` (`pretty` or `json`)
- `services.broker_service.host` (string)
- `services.broker_service.port` (int)
- `services.broker_service.published_port` (int)
- `services.webserver.host` (string)
- `services.webserver.ws_port` (int)
- `services.webserver.ws_published_port` (int)
- `services.webserver.health_port` (int)
- `services.webserver.health_published_port` (int)
- `services.frontend.host` (string)
- `services.frontend.port` (int)
- `services.frontend.published_port` (int)

## Required infrastructure keys
- `infrastructure.redis.host` (string)
- `infrastructure.redis.port` (int)
- `infrastructure.redis.published_port` (int)
- `infrastructure.redis.db` (int)
- `infrastructure.timescaledb.host` (string)
- `infrastructure.timescaledb.port` (int)
- `infrastructure.timescaledb.published_port` (int)
- `infrastructure.timescaledb.user` (string)
- `infrastructure.timescaledb.database` (string)
- `infrastructure.timescaledb.echo` (bool)

## Required backtester keys
- `backtester.worker_poll_interval_seconds` (positive float, default topology value `1.0`)

## Secrets
Secrets are not stored in `config/topology.yaml`. Put them in `config/.env.secrets.local`.
