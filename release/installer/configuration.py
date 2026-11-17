"""Prompt for local setup inputs and render the existing topology contract."""

from __future__ import annotations

import getpass
import secrets
import sys
from typing import Any

from scripts import generate_env

from .docker import Docker, bind_mount
from .model import InstallationError, Locations, Release, protected_write

REGISTRATION_URL = "https://help.ctrader.com/open-api/api-application/"
CALLBACK = "http://localhost:8080/redirect"


def ask(label: str, default: str = "", *, hidden: bool = False) -> str:
    prompt = f"{label}" + (f" [{default}]" if default and not hidden else "") + ": "
    value = (getpass.getpass(prompt) if hidden else input(prompt)).strip() or default
    if "\n" in value or "\r" in value or "\x00" in value:
        raise InstallationError("Values must be a single line.")
    return value


def choose(label: str, options: dict[str, str], default: str) -> str:
    print(f"\n{label}")
    for key, description in options.items():
        print(f"  {key:<8} {description}")
    while True:
        value = ask("Your choice", default)
        if value in options:
            return value
        print("Choose one of the listed values.")


def prepare_release(locations: Locations, release: Release) -> None:
    folder = locations.release_dir(release.version)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("release.json", "compose.yaml"):
        source = locations.bundle / name
        target = folder / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise InstallationError(
                f"Release {release.version} changed. Published releases are immutable."
            )
        protected_write(target, source.read_bytes())
    protected_write(folder / "installer-image.txt", release.images["installer"] + "\n")
    protected_write(folder / "topology.yaml", generate_env.TOPOLOGY_PATH.read_bytes())


def apply_release_network(topology: dict[str, Any]) -> None:
    """Packaged listeners and proxy targets are fixed, including legacy overrides."""
    topology["mode"] = "production"
    services = topology["services"]
    for name in ("database_accessor_api", "indicator_api", "broker_service", "ingestion_service"):
        services[name]["network"]["port"] = 8080
    services["backtester"]["api"]["network"]["port"] = 8080
    services["realtime_service"]["network"]["websocket"]["port"] = 8080
    services["realtime_service"]["network"]["health"]["port"] = 8081
    services["frontend"]["network"]["port"] = 8080
    topology["infrastructure"]["timescaledb"]["network"]["port"] = 5432
    topology["infrastructure"]["redis"]["network"]["port"] = 6379


def require_callback_port(docker: Docker, release: Release) -> None:
    try:
        docker.run(
            [
                "run",
                "--rm",
                "--publish",
                "127.0.0.1:8080:8080",
                "--entrypoint",
                "true",
                release.images["installer"],
            ]
        )
    except InstallationError as exc:
        raise InstallationError(
            "Cannot reserve localhost:8080 for the cTrader callback. Close the application "
            "or stop the development service using port 8080, then rerun setup or reconnect. "
            "Keep the registered redirect URI http://localhost:8080/redirect. "
            f"Docker reported: {exc}"
        ) from exc


def render_configuration(locations: Locations, record: dict[str, Any]) -> None:
    topology = generate_env.load_topology(
        locations.release_dir(record["version"]) / "topology.yaml",
        locations.config / "topology.local.yaml",
    )
    apply_release_network(topology)
    values = generate_env.read_env(locations.config / ".env.secrets.local")
    if record.get("account_id") and (
        values.get("ACCOUNT_ID") != record["account_id"]
        or values.get("CTRADER_HOST_TYPE") != record["environment"]
    ):
        raise InstallationError(
            "Account and environment cannot change; use a separate installation."
        )
    environments = generate_env.build_env(topology, values)
    missing = generate_env.validate(*environments[1:])
    if missing:
        raise InstallationError("Missing setup values: " + ", ".join(sorted(set(missing))))
    for name, environment in zip(
        (".env.shared", ".env.secrets.db", ".env.secrets.runtime", ".env.secrets.broker"),
        environments,
        strict=True,
    ):
        protected_write(locations.config / name, generate_env.format_env(environment))


def authorize(
    locations: Locations, docker: Docker, release: Release, record: dict[str, Any] | None = None
) -> None:
    source = locations.config / ".env.secrets.local"
    existing = generate_env.read_env(source)
    draft = generate_env.read_env(locations.config / "onboarding.env")
    defaults = {**draft, **existing}
    if record is not None and (
        existing.get("ACCOUNT_ID") != record["account_id"]
        or existing.get("CTRADER_HOST_TYPE") != record["environment"]
    ):
        raise InstallationError(
            "Account and environment cannot change; use a separate installation."
        )
    print("Use the client ID and secret from your approved cTrader Open API application.")
    print(f"Application registration guide\n  {REGISTRATION_URL}")
    print(f"Save this exact redirect URI in the application settings\n  {CALLBACK}\n")
    client_id = ask("Application client ID", defaults.get("CTRADER_CLIENT_ID", ""))
    saved_secret = defaults.get("CTRADER_SECRET", "")
    secret_label = (
        "Application secret (hidden, Enter keeps saved secret)"
        if saved_secret
        else "Application secret (hidden)"
    )
    client_secret = ask(secret_label, saved_secret, hidden=True)
    if not client_id or not client_secret:
        raise InstallationError("Application credentials are required; rerun setup after approval.")
    environment = defaults.get("CTRADER_HOST_TYPE", "demo")
    if record is None:
        environment = choose(
            "Broker environment", {"demo": "Demo account", "live": "Live account"}, environment
        )
    scope = choose(
        "Broker access",
        {
            "accounts": "View-only access for market data and backtesting",
            "trading": "Market data, backtesting, and permission to submit broker orders",
        },
        "accounts",
    )
    inputs = {
        "CTRADER_CLIENT_ID": client_id,
        "CTRADER_SECRET": client_secret,
        "CTRADER_HOST_TYPE": environment,
    }
    if record is not None:
        shared = generate_env.read_env(locations.config / ".env.shared")
        inputs["BROKER_REDIS_URL"] = shared["BROKER_REDIS_URL"]
        inputs["BROKER_TOKEN_REDIS_KEY"] = shared["BROKER_TOKEN_REDIS_KEY"]
    protected_write(locations.config / "onboarding.env", generate_env.format_env(inputs))
    output = locations.config / "broker.env"
    command = ["run", "--rm", "--interactive"]
    if sys.stdin.isatty():
        command.append("--tty")
    command += [
        "--publish",
        "127.0.0.1:8080:8080",
        "--env-file",
        str(locations.config / "onboarding.env"),
        "--mount",
        bind_mount(docker.host_path(locations.config), "/config"),
    ]
    if record is not None:
        command += ["--network", record["project"] + "_default"]
    command += [
        release.images["broker-service"],
        "python",
        "-m",
        "app.onboarding",
        "authorize",
        "--bind-address",
        "0.0.0.0",
        "--scope",
        scope,
        "--output",
        "/config/broker.env",
    ]
    if record is not None:
        command += ["--expected-account-id", record["account_id"], "--replace-token-state"]
    docker.run(command)
    credentials = generate_env.read_env(output)
    if record is not None and credentials.get("ACCOUNT_ID") != record["account_id"]:
        raise InstallationError("Reconnect must keep the installed account.")
    merged = {**existing, **credentials}
    merged.setdefault("TIMESCALEDB_PASSWORD", secrets.token_hex(32))
    protected_write(source, generate_env.format_env(merged))
    output.unlink(missing_ok=True)
    (locations.config / "onboarding.env").unlink(missing_ok=True)


def choose_port(docker: Docker, release: Release, default: int = 8000) -> int:
    value = str(default)
    while True:
        if not value.isdigit() or not 1024 <= int(value) <= 65535 or int(value) == 8080:
            print("Choose a port from 1024 to 65535 other than the OAuth callback port 8080.")
            value = ask("Application port", str(default))
            continue
        try:
            docker.run(
                [
                    "run",
                    "--rm",
                    "--publish",
                    f"127.0.0.1:{value}:8080",
                    "--entrypoint",
                    "true",
                    release.images["installer"],
                ]
            )
            return int(value)
        except InstallationError:
            print("That port could not be reserved. Choose another available port.")
            value = ask("Application port", str(default + 1))
