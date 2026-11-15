"""Exercise a release's real images and disposable database without broker secrets."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

from release.build_bundle import verify_public
from release.installer.model import Release
from scripts import generate_env

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, env=env, check=True)


def report_failure(project: str) -> None:
    """Retain process exit and probe evidence before disposable containers disappear."""
    for service in ("timescaledb-1", "redis-1", "database-accessor-api-1", "frontend", "upstreams"):
        container = f"{project}-{service}"
        for args in (
            ["docker", "inspect", "--format", "{{json .State}}", container],
            ["docker", "logs", "--tail", "100", container],
        ):
            try:
                subprocess.run(args, check=False, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(f"Could not collect diagnostics for {container}: {exc}", flush=True)


@contextmanager
def retain_failure_diagnostics(project: str) -> Iterator[None]:
    try:
        yield
    except Exception:
        report_failure(project)
        raise


def wait_for_frontend(fetch: list[str]) -> None:
    for _ in range(60):
        ready = subprocess.run(
            [*fetch, "http://127.0.0.1:8080/health"], capture_output=True, check=False
        )
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Production frontend did not become ready")


def smoke(manifest: Path, platform: str) -> None:
    release = Release.read(manifest)
    verify_public(release.images)
    for name, image in release.images.items():
        run(["docker", "pull", "--platform", platform, image])
        if name in {"timescaledb", "redis", "frontend", "installer"}:
            continue
        modules = "fastapi, uvicorn" if name != "realtime-service" else "websockets, redis"
        if name in {"backtester", "indicator-api"}:
            modules += ", numpy, pandas"
        run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                platform,
                "--entrypoint",
                "python",
                image,
                "-c",
                f"import {modules}; import platform; print(platform.machine())",
            ]
        )
    with tempfile.TemporaryDirectory(prefix="algotrader-release-smoke-") as temporary:
        folder = Path(temporary)
        topology = generate_env.read_yaml(ROOT / "config/topology.yaml")
        secrets = {key: "unused-smoke-value" for key in generate_env.REQUIRED_SECRETS}
        secrets.update(ACCOUNT_ID="1", CTRADER_HOST_TYPE="demo")
        environments = generate_env.build_env(topology, secrets)
        for name, values in zip(
            (".env.shared", ".env.secrets.db", ".env.secrets.runtime", ".env.secrets.broker"),
            environments,
            strict=True,
        ):
            (folder / name).write_text(generate_env.format_env(values))
        compose = yaml.safe_load((ROOT / "release/compose.yaml").read_text())
        for service in compose["services"].values():
            service["platform"] = platform
            for env_file in service.get("env_file", []):
                env_file["path"] = str(folder / Path(env_file["path"]).name)
        compose_path = folder / "compose.yaml"
        compose_path.write_text(yaml.safe_dump(compose))
        project = "algotrader-smoke-" + uuid.uuid4().hex[:12]
        command = [
            "docker",
            "compose",
            "-p",
            project,
            "--env-file",
            str(folder / ".env.shared"),
            "-f",
            str(compose_path),
        ]
        environment = {**os.environ, **release.environment()}
        try:
            with retain_failure_diagnostics(project):
                run(
                    [
                        *command,
                        "up",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        "360",
                        "timescaledb",
                        "redis",
                        "database-accessor-api",
                    ],
                    env=environment,
                )
                market = {
                    "symbol": "SMOKE",
                    "exchange": "CSV",
                    "market_type": "Stock",
                    "min_move": 0.01,
                    "timezone": "UTC",
                    "settlement_currency": "USD",
                    "contract_multiplier": 1,
                    "minimum_quantity": 1,
                    "quantity_step": 1,
                    "source_type": "custom",
                }
                candle_batch = {
                    "symbol": "SMOKE",
                    "exchange": "CSV",
                    "candles": [
                        {
                            "timestamp_ms": 1700000040000,
                            "open": 10,
                            "high": 12,
                            "low": 9,
                            "close": 11,
                            "volume": 5,
                        }
                    ],
                }
                script = f"""
    import json
    import urllib.request
    for path, payload in [("markets", {market!r}), ("candles/upload", {candle_batch!r})]:
        request = urllib.request.Request(
            "http://localhost:8000/" + path, data=json.dumps(payload).encode(),
            headers={{"Content-Type": "application/json"}},
        )
        urllib.request.urlopen(request).read()
    market = json.load(urllib.request.urlopen("http://localhost:8000/markets/SMOKE?exchange=CSV"))
    assert market["source_type"] == "custom"
    print("Custom market and uploaded candle persisted")
    """
                run(
                    [*command, "exec", "-T", "database-accessor-api", "python", "-c", script],
                    env=environment,
                )
                # Resolve all frontend upstreams without connecting to an actual broker.
                aliases = [
                    item
                    for name in (
                        "indicator-api",
                        "backtester-api",
                        "broker-service",
                        "realtime-service",
                        "ingestion-service",
                    )
                    for item in ("--network-alias", name)
                ]
                run(
                    [
                        "docker",
                        "run",
                        "--detach",
                        "--name",
                        project + "-upstreams",
                        "--network",
                        project + "_default",
                        *aliases,
                        release.images["redis"],
                    ],
                    env=environment,
                )
                run(
                    [
                        "docker",
                        "run",
                        "--detach",
                        "--platform",
                        platform,
                        "--name",
                        project + "-frontend",
                        "--network",
                        project + "_default",
                        release.images["frontend"],
                    ],
                    env=environment,
                )
                fetch = ["docker", "exec", project + "-frontend", "wget", "--quiet", "-O", "-"]
                wait_for_frontend(fetch)
                root_html = subprocess.check_output([*fetch, "http://127.0.0.1:8080/"]).decode()
                asset = re.search(r'src="(/assets/[^"]+\.js)"', root_html)
                if asset is None:
                    raise RuntimeError("Production frontend did not serve its compiled entrypoint")
                if not subprocess.check_output([*fetch, "http://127.0.0.1:8080" + asset.group(1)]):
                    raise RuntimeError("Production frontend asset is empty")
                candles = json.loads(
                    subprocess.check_output(
                        [
                            *fetch,
                            "http://127.0.0.1:8080/api/data-accessor/candles/SMOKE?exchange=CSV&timeframe=M1&limit=1",
                        ]
                    )
                )
                if len(candles) != 1 or candles[0]["timestamp_ms"] != 1700000040000:
                    raise RuntimeError("Production proxy did not return the custom chart candle")
                run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--platform",
                        platform,
                        release.images["installer"],
                        "--help",
                    ],
                    env=environment,
                )
        finally:
            subprocess.run(
                ["docker", "rm", "--force", project + "-frontend", project + "-upstreams"],
                check=False,
                capture_output=True,
            )
            run([*command, "down", "--volumes", "--remove-orphans"], env=environment)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"), required=True)
    args = parser.parse_args()
    smoke(args.manifest, args.platform)


if __name__ == "__main__":
    main()
