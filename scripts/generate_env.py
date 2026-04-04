#!/usr/bin/env python3
"""Generate config env files from tracked topology and local secrets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required for scripts/generate_env.py. "
        "Install it with: python -m pip install pyyaml"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parent.parent
TOPOLOGY_PATH = ROOT_DIR / "config" / "topology.yaml"
SECRETS_PATH = ROOT_DIR / "config" / ".env.secrets.local"
OUTPUT_SHARED_PATH = ROOT_DIR / "config" / ".env.shared"
OUTPUT_DB_SECRETS_PATH = ROOT_DIR / "config" / ".env.secrets.db"
OUTPUT_RUNTIME_SECRETS_PATH = ROOT_DIR / "config" / ".env.secrets.runtime"
OUTPUT_BROKER_SECRETS_PATH = ROOT_DIR / "config" / ".env.secrets.broker"
REQUIRED_SECRETS = (
    "TIMESCALEDB_PASSWORD",
    "CTRADER_CLIENT_ID",
    "CTRADER_SECRET",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_REFRESH_TOKEN",
    "CTRADER_HOST_TYPE",
    "ACCOUNT_ID",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate config/.env.shared, config/.env.secrets.db, "
            "config/.env.secrets.runtime, and config/.env.secrets.broker "
            "from config/topology.yaml and config/.env.secrets.local"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing .env file",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="validate inputs and print missing keys without writing .env",
    )
    return parser.parse_args()


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing topology file: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError("Topology root must be a mapping")
    return data


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid env line in {path}: {raw_line}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def required(topology: dict[str, Any], path: str) -> Any:
    current: Any = topology
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Missing topology key: {path}")
        current = current[part]
    return current


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_env(
    topology: dict[str, Any],
    secrets: dict[str, str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    mode = required(topology, "mode")
    public_host = required(topology, "public.host")

    db_api_host = required(topology, "services.database_accessor_api.host")
    db_api_port = required(topology, "services.database_accessor_api.port")
    db_api_published_port = required(topology, "services.database_accessor_api.published_port")
    db_api_log_level = required(topology, "services.database_accessor_api.log_level")
    db_api_log_format = required(topology, "services.database_accessor_api.log_format")

    indicator_host = required(topology, "services.indicator_api.host")
    indicator_port = required(topology, "services.indicator_api.port")
    indicator_published_port = required(topology, "services.indicator_api.published_port")
    indicator_log_level = required(topology, "services.indicator_api.log_level")
    indicator_log_format = required(topology, "services.indicator_api.log_format")

    broker_host = required(topology, "services.broker_service.host")
    broker_port = required(topology, "services.broker_service.port")
    broker_published_port = required(topology, "services.broker_service.published_port")
    broker_log_level = required(topology, "services.broker_service.log_level")
    broker_log_format = required(topology, "services.broker_service.log_format")

    webserver_host = required(topology, "services.webserver.host")
    webserver_ws_port = required(topology, "services.webserver.ws_port")
    webserver_ws_published_port = required(topology, "services.webserver.ws_published_port")
    webserver_health_port = required(topology, "services.webserver.health_port")
    webserver_health_published_port = required(topology, "services.webserver.health_published_port")
    webserver_log_level = required(topology, "services.webserver.log_level")
    webserver_log_format = required(topology, "services.webserver.log_format")

    frontend_host = required(topology, "services.frontend.host")
    frontend_port = required(topology, "services.frontend.port")
    frontend_published_port = required(topology, "services.frontend.published_port")

    redis_host = required(topology, "infrastructure.redis.host")
    redis_port = required(topology, "infrastructure.redis.port")
    redis_published_port = required(topology, "infrastructure.redis.published_port")
    redis_db = required(topology, "infrastructure.redis.db")

    timescaledb_host = required(topology, "infrastructure.timescaledb.host")
    timescaledb_port = required(topology, "infrastructure.timescaledb.port")
    timescaledb_published_port = required(topology, "infrastructure.timescaledb.published_port")
    timescaledb_user = required(topology, "infrastructure.timescaledb.user")
    timescaledb_db = required(topology, "infrastructure.timescaledb.database")
    timescaledb_echo = required(topology, "infrastructure.timescaledb.echo")

    webserver_redis_block_ms = required(topology, "webserver.redis_block_ms")
    webserver_redis_batch_size = required(topology, "webserver.redis_batch_size")
    webserver_stream_queue_size = required(topology, "webserver.stream_queue_size")
    webserver_max_stream_length = required(topology, "webserver.max_stream_length")

    ingestion_log_level = required(topology, "ingestion.log_level")
    ingestion_log_format = required(topology, "ingestion.log_format")
    ingestion_batch_size = required(topology, "ingestion.consumer_batch_size")
    ingestion_block_ms = required(topology, "ingestion.consumer_block_ms")

    broker_redis_stream_db = required(topology, "broker.redis_stream_db")
    broker_tick_queue_size = required(topology, "broker.tick_queue_size")
    broker_tick_stream_maxlen = required(topology, "broker.tick_stream_maxlen")
    broker_candle_stream_maxlen = required(topology, "broker.candle_stream_maxlen")
    broker_max_symbol_streams = required(topology, "broker.max_symbol_streams")
    broker_max_trendbar_streams = required(topology, "broker.max_trendbar_streams")
    broker_request_timeout = required(topology, "broker.ctrader_request_timeout_seconds")

    redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
    broker_redis_url = f"redis://{redis_host}:{redis_port}/{broker_redis_stream_db}"

    shared_env = {
        "MODE": stringify(mode),
        "PUBLIC_HOST": stringify(public_host),
        "DATABASE_ACCESSOR_HOST": stringify(db_api_host),
        "DATABASE_ACCESSOR_PORT": stringify(db_api_port),
        "DATABASE_ACCESSOR_PUBLISHED_PORT": stringify(db_api_published_port),
        "DATABASE_ACCESSOR_BASE_URL": f"http://{db_api_host}:{db_api_port}",
        "DATABASE_ACCESSOR_LOG_LEVEL": stringify(db_api_log_level),
        "DATABASE_ACCESSOR_LOG_FORMAT": stringify(db_api_log_format),
        "INDICATOR_API_HOST": stringify(indicator_host),
        "INDICATOR_API_PORT": stringify(indicator_port),
        "INDICATOR_API_PUBLISHED_PORT": stringify(indicator_published_port),
        "INDICATOR_API_BASE_URL": f"http://{indicator_host}:{indicator_port}",
        "INDICATOR_API_LOG_LEVEL": stringify(indicator_log_level),
        "INDICATOR_API_LOG_FORMAT": stringify(indicator_log_format),
        "BROKER_SERVICE_HOST": stringify(broker_host),
        "BROKER_SERVICE_PORT": stringify(broker_port),
        "BROKER_SERVICE_PUBLISHED_PORT": stringify(broker_published_port),
        "BROKER_SERVICE_BASE_URL": f"http://{broker_host}:{broker_port}",
        "BROKER_LOG_LEVEL": stringify(broker_log_level),
        "BROKER_LOG_FORMAT": stringify(broker_log_format),
        "WEBSERVER_HOST": stringify(webserver_host),
        "WEBSERVER_WS_PORT": stringify(webserver_ws_port),
        "WEBSERVER_WS_PUBLISHED_PORT": stringify(webserver_ws_published_port),
        "WEBSERVER_HEALTH_PORT": stringify(webserver_health_port),
        "WEBSERVER_HEALTH_PUBLISHED_PORT": stringify(webserver_health_published_port),
        "WEBSERVER_LOG_LEVEL": stringify(webserver_log_level),
        "WEBSERVER_LOG_FORMAT": stringify(webserver_log_format),
        "FRONTEND_HOST": stringify(frontend_host),
        "FRONTEND_PORT": stringify(frontend_port),
        "FRONTEND_PUBLISHED_PORT": stringify(frontend_published_port),
        "REDIS_HOST": stringify(redis_host),
        "REDIS_PORT": stringify(redis_port),
        "REDIS_PUBLISHED_PORT": stringify(redis_published_port),
        "REDIS_DB": stringify(redis_db),
        "REDIS_URL": redis_url,
        "TIMESCALEDB_HOST": stringify(timescaledb_host),
        "TIMESCALEDB_PORT": stringify(timescaledb_port),
        "TIMESCALEDB_PUBLISHED_PORT": stringify(timescaledb_published_port),
        "TIMESCALEDB_USER": stringify(timescaledb_user),
        "TIMESCALEDB_DB": stringify(timescaledb_db),
        "TIMESCALEDB_ECHO": stringify(timescaledb_echo),
        "VITE_PROXY_DATA_ACCESSOR_TARGET": f"http://{db_api_host}:{db_api_port}",
        "VITE_PROXY_INDICATOR_TARGET": f"http://{indicator_host}:{indicator_port}",
        "VITE_WS_URL": f"ws://{public_host}:{webserver_ws_published_port}",
        "INGESTION_LOG_LEVEL": stringify(ingestion_log_level),
        "INGESTION_LOG_FORMAT": stringify(ingestion_log_format),
        "LOG_LEVEL": stringify(ingestion_log_level),
        "LOG_FORMAT": stringify(ingestion_log_format),
        "CONSUMER_BATCH_SIZE": stringify(ingestion_batch_size),
        "CONSUMER_BLOCK_MS": stringify(ingestion_block_ms),
        "WEBSERVER_REDIS_BLOCK_MS": stringify(webserver_redis_block_ms),
        "WEBSERVER_REDIS_BATCH_SIZE": stringify(webserver_redis_batch_size),
        "WEBSERVER_STREAM_QUEUE_SIZE": stringify(webserver_stream_queue_size),
        "WEBSERVER_MAX_STREAM_LENGTH": stringify(webserver_max_stream_length),
        "BROKER_REDIS_URL": broker_redis_url,
        "BROKER_TOKEN_REDIS_KEY": "broker:auth:ctrader:current",
        "BROKER_TOKEN_REFRESH_EARLY_SECONDS": "604800",
        "BROKER_TOKEN_REFRESH_RETRY_DELAY_SECONDS": "30",
        "BROKER_TOKEN_REFRESH_MAX_RETRIES": "3",
        "BROKER_TICK_QUEUE_SIZE": stringify(broker_tick_queue_size),
        "BROKER_TICK_STREAM_MAXLEN": stringify(broker_tick_stream_maxlen),
        "BROKER_CANDLE_STREAM_MAXLEN": stringify(broker_candle_stream_maxlen),
        "BROKER_MAX_SYMBOL_STREAMS": stringify(broker_max_symbol_streams),
        "BROKER_MAX_TRENDBAR_STREAMS": stringify(broker_max_trendbar_streams),
        "BROKER_CTRADER_REQUEST_TIMEOUT_SECONDS": stringify(broker_request_timeout),
        "CTRADER_TOKEN_URL": "https://openapi.ctrader.com/apps/token",
        "CTRADER_ACCESS_TOKEN_EXPIRES_IN_SECONDS": "2628000",
        "CTRADER_TOKEN_REQUEST_TIMEOUT_SECONDS": "10.0",
    }

    db_secrets_env: dict[str, str] = {}
    runtime_secrets_env = {
        "ACCOUNT_ID": secrets.get("ACCOUNT_ID", ""),
    }
    broker_secrets_env = {
        "CTRADER_CLIENT_ID": secrets.get("CTRADER_CLIENT_ID", ""),
        "CTRADER_SECRET": secrets.get("CTRADER_SECRET", ""),
        "CTRADER_ACCESS_TOKEN": secrets.get("CTRADER_ACCESS_TOKEN", ""),
        "CTRADER_REFRESH_TOKEN": secrets.get("CTRADER_REFRESH_TOKEN", ""),
        "CTRADER_HOST_TYPE": secrets.get("CTRADER_HOST_TYPE", ""),
    }

    timescaledb_password = secrets.get("TIMESCALEDB_PASSWORD", "")
    db_secrets_env["TIMESCALEDB_PASSWORD"] = timescaledb_password
    db_secrets_env["POSTGRES_PASSWORD"] = timescaledb_password
    return shared_env, db_secrets_env, runtime_secrets_env, broker_secrets_env


def validate(
    db_secrets_env: dict[str, str],
    runtime_secrets_env: dict[str, str],
    broker_secrets_env: dict[str, str],
) -> list[str]:
    merged = {**db_secrets_env, **runtime_secrets_env, **broker_secrets_env}
    missing = [key for key in REQUIRED_SECRETS if not merged.get(key)]
    if not db_secrets_env.get("TIMESCALEDB_PASSWORD"):
        missing.append("TIMESCALEDB_PASSWORD")
    return missing


def format_env(env: dict[str, str]) -> str:
    lines = [
        "# GENERATED FILE - DO NOT EDIT",
        "# Source: config/topology.yaml + config/.env.secrets.local",
    ]
    for key in sorted(env.keys()):
        if key in {"BROKER_TICK_STREAM_MAXLEN", "BROKER_CANDLE_STREAM_MAXLEN"} and env[key] == "":
            continue
        lines.append(f"{key}={env[key]}")
    lines.append("")
    return "\n".join(lines)


def write_output(path: Path, content: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    return True


def main() -> int:
    args = parse_args()
    topology = read_yaml(TOPOLOGY_PATH)
    secrets = read_env(SECRETS_PATH)
    shared_env, db_secrets_env, runtime_secrets_env, broker_secrets_env = build_env(topology, secrets)
    missing = validate(db_secrets_env, runtime_secrets_env, broker_secrets_env)

    if missing:
        print("Missing required secret values:")
        for key in missing:
            print(f"  - {key}")
        return 1

    if args.validate:
        print("Configuration is valid.")
        return 0

    if not args.force and (
        OUTPUT_SHARED_PATH.exists()
        or OUTPUT_DB_SECRETS_PATH.exists()
        or OUTPUT_RUNTIME_SECRETS_PATH.exists()
        or OUTPUT_BROKER_SECRETS_PATH.exists()
    ):
        print(
            f"{OUTPUT_SHARED_PATH}, {OUTPUT_DB_SECRETS_PATH}, "
            f"{OUTPUT_RUNTIME_SECRETS_PATH}, or "
            f"{OUTPUT_BROKER_SECRETS_PATH} already exists. "
            "Use --force to overwrite."
        )
        return 1

    outputs = (
        (OUTPUT_SHARED_PATH, format_env(shared_env)),
        (OUTPUT_DB_SECRETS_PATH, format_env(db_secrets_env)),
        (OUTPUT_RUNTIME_SECRETS_PATH, format_env(runtime_secrets_env)),
        (OUTPUT_BROKER_SECRETS_PATH, format_env(broker_secrets_env)),
    )
    for path, content in outputs:
        if write_output(path, content):
            print(f"Wrote {path}")
        else:
            print(f"Unchanged {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
