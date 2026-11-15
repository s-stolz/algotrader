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
    for key, description in options.items():
        print(f"  {key}: {description}")
    while True:
        value = ask(label, default)
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
    protected_write(folder / "topology.yaml", generate_env.TOPOLOGY_PATH.read_bytes())


def render_configuration(locations: Locations, record: dict[str, Any]) -> None:
    topology = generate_env.load_topology(
        locations.release_dir(record["version"]) / "topology.yaml",
        locations.config / "topology.local.yaml",
    )
    topology["mode"] = "production"
    values = generate_env.read_env(locations.config / ".env.secrets.local")
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
    print(f"Register your own cTrader application: {REGISTRATION_URL}")
    print(f"After approval, register this exact redirect URI: {CALLBACK}")
    client_id = ask("Application client ID", defaults.get("CTRADER_CLIENT_ID", ""))
    client_secret = ask(
        "Application secret (blank keeps existing)", defaults.get("CTRADER_SECRET", ""), hidden=True
    )
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
            "accounts": "Market data and backtesting",
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
        inputs["BROKER_REDIS_URL"] = "redis://redis:6379/0"
        inputs["BROKER_TOKEN_REDIS_KEY"] = "broker:auth:ctrader:current"
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
        command += ["--expected-account-id", existing["ACCOUNT_ID"], "--replace-token-state"]
    docker.run(command)
    credentials = generate_env.read_env(output)
    if record is not None and credentials.get("ACCOUNT_ID") != existing.get("ACCOUNT_ID"):
        raise InstallationError("Reconnect must keep the installed account.")
    merged = {**existing, **credentials}
    merged.setdefault("TIMESCALEDB_PASSWORD", secrets.token_hex(32))
    protected_write(source, generate_env.format_env(merged))
    output.unlink(missing_ok=True)
    (locations.config / "onboarding.env").unlink(missing_ok=True)


def choose_port(docker: Docker, release: Release, default: int = 8088) -> int:
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
