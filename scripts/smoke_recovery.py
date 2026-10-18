"""Run recovery acceptance against owned disposable services, never the local stack."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def wait_until(check, description):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {description}")


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python", default=sys.executable, help="Combined service test environment"
    )
    parser.add_argument("--backtester-python", help="Backtester acceptance interpreter")
    parser.add_argument("--output", type=Path, help="New evidence directory (must not exist)")
    parser.add_argument("--timescale-image", default="timescale/timescaledb:latest-pg17")
    parser.add_argument("--redis-image", default="redis:7-alpine")
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="recovery-smoke-")) / "evidence"
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    identity = uuid4().hex[:12]
    database = "vibe9_smoke_" + identity
    user, password = "recovery_test", "synthetic-test-only"
    containers = []
    accessor = None
    report: dict[str, Any] = dict(
        status="running", checks=[], containers=[], cleanup=[], output=str(output)
    )
    environment = dict(os.environ)
    # Host configuration and opt-in URLs must never select existing services.
    for key in list(environment):
        if key.startswith(("HISTORY_TEST_", "RECOVERY_TEST_", "RECOVERY_MIGRATION_TEST_")):
            environment.pop(key)

    def run(name, command, *, env=None, input_text=None, timeout=240):
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env or environment,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        (output / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        report["checks"].append(
            dict(
                name=name,
                command=command,
                exit_code=result.returncode,
                seconds=round(time.monotonic() - started, 3),
                log=f"{name}.log",
            )
        )
        print(f"{name}: exit {result.returncode}", flush=True)
        if result.returncode:
            raise RuntimeError(f"{name} failed; see {output / (name + '.log')}")
        if name.startswith("test-") and (
            "skipped=" in result.stdout or "... skipped " in result.stdout
        ):
            raise RuntimeError(f"{name} skipped required acceptance; see its log")
        return result.stdout.strip()

    def service_env(area):
        paths = [ROOT / area, ROOT / "libs/db_accessor_client", ROOT / "libs/algotrader_logger"]
        return dict(
            environment,
            PYTHONPATH=os.pathsep.join(
                [*(str(path) for path in paths), environment.get("PYTHONPATH", "")]
            ),
        )

    try:
        report["sha"] = run("identity", ["git", "rev-parse", "HEAD"])
        report["diff"] = run("diff", ["git", "diff", "--stat"])
        run(
            "dependencies",
            [
                args.python,
                "-c",
                "import httpx, redis, sqlalchemy, asyncpg, uvicorn, ctrader_open_api",
            ],
        )
        for kind, image, port, extra in (
            (
                "timescale",
                args.timescale_image,
                5432,
                [
                    "-e",
                    f"POSTGRES_USER={user}",
                    "-e",
                    f"POSTGRES_PASSWORD={password}",
                    "-e",
                    f"POSTGRES_DB={database}",
                ],
            ),
            ("redis", args.redis_image, 6379, []),
        ):
            name = f"vibe10r1-smoke-{identity}-{kind}"
            container = run(
                f"start-{kind}",
                ["docker", "run", "-d", "--name", name, "-p", f"127.0.0.1::{port}", *extra, image],
            )
            containers.append(container)
            details = json.loads(run(f"inspect-{kind}", ["docker", "inspect", container]))[0]
            report["containers"].append(details)
            host_port = details["NetworkSettings"]["Ports"][f"{port}/tcp"][0]["HostPort"]
            if kind == "timescale":
                db_container, db_name, db_port = container, name, host_port
            else:
                redis_container, redis_port = container, host_port
        wait_until(
            lambda: subprocess.run(
                [
                    "docker",
                    "exec",
                    db_container,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    user,
                    "-d",
                    database,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0,
            "Timescale",
        )
        wait_until(
            lambda: subprocess.run(
                ["docker", "exec", redis_container, "redis-cli", "ping"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0,
            "Redis",
        )
        run(
            "install-migration-python",
            ["docker", "exec", db_container, "apk", "add", "--no-cache", "python3"],
        )
        run(
            "copy-migrations",
            [
                "docker",
                "cp",
                str(ROOT / "timescaledb-init/migrations"),
                f"{db_container}:/tmp/recovery-migrations",
            ],
        )
        run(
            "copy-runner",
            [
                "docker",
                "cp",
                str(ROOT / "scripts/migrate_db.py"),
                f"{db_container}:/tmp/migrate_db.py",
            ],
        )
        migration = [
            "docker",
            "exec",
            "-e",
            f"POSTGRES_DB={database}",
            "-e",
            f"POSTGRES_USER={user}",
            db_container,
            "python3",
            "/tmp/migrate_db.py",
            "--in-container",
            "--migrations-dir",
            "/tmp/recovery-migrations",
        ]
        run("migrate", migration)
        run("migrate-replay", migration)
        run(
            "storage-version",
            [
                "docker",
                "exec",
                db_container,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-c",
                "SELECT version(); "
                "SELECT extversion FROM pg_extension WHERE extname='timescaledb'; "
                "TABLE schema_migrations;",
            ],
        )
        environment.update(
            TIMESCALEDB_USER=user,
            TIMESCALEDB_PASSWORD=password,
            TIMESCALEDB_HOST="127.0.0.1",
            TIMESCALEDB_PORT=db_port,
            TIMESCALEDB_DB=database,
            DATABASE_ACCESSOR_LOG_LEVEL="WARNING",
            HISTORY_TEST_DATABASE_URL=f"postgresql+asyncpg://{user}:{password}@127.0.0.1:{db_port}/{database}",
            RECOVERY_MIGRATION_TEST_CONTAINER=db_name,
            RECOVERY_MIGRATION_TEST_USER=user,
            RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS="1",
            BACKTESTER_TEST_PYTHON=args.backtester_python or args.python,
            BACKTEST_BATCH_TEST_DATABASE_URL=f"postgresql+asyncpg://{user}:{password}@127.0.0.1:{db_port}/{database}",
        )
        config = output / "integration-config"
        config.mkdir()
        (config / ".env.shared").write_text(
            f"TIMESCALEDB_PUBLISHED_PORT={db_port}\nTIMESCALEDB_DB={database}\nTIMESCALEDB_USER={user}\n"
        )
        (config / ".env.secrets.db").write_text(f"TIMESCALEDB_PASSWORD={password}\n")
        environment["BACKTEST_INTEGRATION_ENV_DIR"] = str(config)
        # Bind before spawning to let the OS choose a loopback port; uvicorn inherits it.
        with socket.socket() as listener, (output / "accessor.log").open("w") as accessor_log:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            accessor_port = listener.getsockname()[1]
            accessor = subprocess.Popen(
                [args.python, "-m", "uvicorn", "main:app", "--fd", str(listener.fileno())],
                cwd=ROOT,
                env=service_env("database-accessor-api"),
                pass_fds=(listener.fileno(),),
                stdout=accessor_log,
                stderr=subprocess.STDOUT,
            )
            import httpx

            url = f"http://127.0.0.1:{accessor_port}"

            def ready():
                if accessor.poll() is not None:
                    raise RuntimeError("Accessor exited; see accessor.log")
                try:
                    return httpx.get(url + "/markets", timeout=1).json() == []
                except (httpx.HTTPError, ValueError):
                    return False

            wait_until(ready, "empty accessor")
            environment.update(
                RECOVERY_TEST_ACCESSOR_URL=url,
                RECOVERY_TEST_REDIS_URL=f"redis://127.0.0.1:{redis_port}/0",
                HISTORY_TEST_ACCESSOR_URL=url,
            )
            for name, area, directory, pattern in (
                (
                    "process",
                    "ingestion-service",
                    "ingestion-service/tests",
                    "test_recovery_process.py",
                ),
                (
                    "history",
                    "ingestion-service",
                    "ingestion-service/tests",
                    "test_history_integration.py",
                ),
                ("inactivity", "ingestion-service", "ingestion-service/tests", "test_recovery.py"),
                (
                    "storage",
                    "database-accessor-api",
                    "database-accessor-api/tests",
                    "test_*postgres.py",
                ),
                ("migrations", "", "timescaledb-init/tests", "test_run_migrations.py"),
            ):
                run(
                    f"test-{name}",
                    [
                        args.python,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        directory,
                        "-p",
                        pattern,
                        "-v",
                    ],
                    env=service_env(area),
                )
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
    finally:
        if accessor is not None:
            accessor.terminate()
            try:
                accessor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                accessor.kill()
                accessor.wait(timeout=5)
            report["accessor_exit"] = accessor.returncode
        for container in reversed(containers):
            result = subprocess.run(
                ["docker", "rm", "-fv", container], capture_output=True, text=True
            )
            report["cleanup"].append(
                dict(
                    container=container,
                    exit_code=result.returncode,
                    output=result.stdout + result.stderr,
                )
            )
            if result.returncode:
                report["status"] = "failed"
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{report['status']}: {output / 'report.json'}", flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
