"""Start, reconnect and upgrade a single local installation."""

from __future__ import annotations

import hashlib
import json
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import generate_env

from .configuration import (
    authorize,
    choose_port,
    prepare_release,
    render_configuration,
    require_callback_port,
)
from .docker import Docker, bind_mount
from .model import InstallationError, Locations, Release, protected_write, version_key, write_json

APPLICATION_SERVICES = [
    "frontend",
    "backtester-api",
    "backtester-worker",
    "ingestion-service",
    "realtime-service",
    "indicator-api",
    "broker-service",
    "database-accessor-api",
]
INTERNAL_SERVICES = [
    "database-accessor-api",
    "broker-service",
    "ingestion-service",
    "realtime-service",
    "indicator-api",
]
ADMISSION_SERVICES = ["backtester-api", "backtester-worker", "frontend"]
BUSY_QUERY = """SELECT EXISTS (
    SELECT 1 FROM backtest_runs WHERE status IN ('queued', 'running', 'cancelling')
) OR EXISTS (
    SELECT 1 FROM backtest_execution_slot
    WHERE owner_token IS NOT NULL OR run_id IS NOT NULL OR fault_code IS NOT NULL
);"""


def file_checksum(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class Lifecycle:
    def __init__(self, locations: Locations, docker: Docker):
        self.locations = locations
        self.docker = docker

    def current(
        self, *, allow_pending: bool = False, allow_reconnect: bool = False
    ) -> dict[str, Any]:
        record = self.locations.installed()
        if record.get("pending_upgrade") and not allow_pending:
            raise InstallationError(
                "An upgrade did not finish. Services remain stopped; follow "
                f"{record['pending_upgrade']['backup']}/RECOVERY.md before restarting."
            )
        if record.get("pending_reconnect") and not (allow_pending or allow_reconnect):
            raise InstallationError(
                "Broker reconnection did not finish. Run reconnect again before starting services."
            )
        return record

    def check_ready(self, record: dict[str, Any], *, announce: bool = True) -> None:
        response = self.docker.compose(
            record,
            [
                "exec",
                "-T",
                "broker-service",
                "python",
                "-c",
                "import urllib.request; print(urllib.request.urlopen("
                "'http://localhost:8080/connection', timeout=30).read().decode())",
            ],
            capture=True,
        )
        connection = json.loads(response)
        if (
            str(connection.get("account_id")) != record["account_id"]
            or connection.get("environment") != record["environment"]
        ):
            raise InstallationError("The running broker did not authenticate the selected account.")
        if announce:
            print(f"AlgoTrader is ready at http://localhost:{record['ui_port']}")
            print("Add a broker market to collect live candles or request history.")

    def setup(self, release: Release) -> None:
        if self.locations.record.exists():
            raise InstallationError(
                "This installation already exists. Use start, reconnect, or upgrade."
            )
        self.docker.pull(release)
        prepare_release(self.locations, release)
        port = choose_port(self.docker, release)
        require_callback_port(self.docker, release)
        authorize(self.locations, self.docker, release)
        credentials = generate_env.read_env(self.locations.config / ".env.secrets.local")
        record = {
            "account_id": credentials["ACCOUNT_ID"],
            "environment": credentials["CTRADER_HOST_TYPE"],
            "schema_version": 1,
            "project": "algotrader-" + uuid.uuid4().hex[:12],
            "version": release.version,
            "ui_port": port,
            "stopped": False,
        }
        render_configuration(self.locations, record)
        # Record identity before startup so a failed startup is safely resumable with start.
        write_json(self.locations.record, record)
        self.docker.compose(record, ["up", "--detach", "--wait", "--wait-timeout", "360"])
        self.check_ready(record)

    def start(self) -> None:
        record = self.current()
        render_configuration(self.locations, record)
        self.docker.compose(record, ["up", "--detach", "--wait", "--wait-timeout", "360"])
        record["stopped"] = False
        write_json(self.locations.record, record)
        self.check_ready(record)

    def stop(self) -> None:
        record = self.current(allow_pending=True)
        self.docker.compose(record, ["stop", "--timeout", "60"])
        record["stopped"] = True
        write_json(self.locations.record, record)
        print("Stopped. Configuration, candles and download progress are preserved.")

    def status(self) -> None:
        record = self.current(allow_pending=True)
        print(f"Installation: {record['project']}")
        print(f"Installed version: {record['version']}")
        print(f"Application: http://localhost:{record['ui_port']}")
        print("Services: " + ("explicitly stopped" if record.get("stopped") else "enabled"))
        if record.get("pending_upgrade"):
            print(f"Upgrade needs recovery: {record['pending_upgrade']['backup']}/RECOVERY.md")
        if record.get("pending_reconnect"):
            print("Broker remains stopped after an incomplete reconnect. Run reconnect again.")
        self.docker.compose(record, ["ps", "--all"])

    def reconnect(self) -> None:
        record = self.current(allow_reconnect=True)
        release = Release.read(self.locations.release_dir(record["version"]) / "release.json")
        require_callback_port(self.docker, release)
        self.docker.compose(record, ["up", "--detach", "--wait", "redis"])
        self.docker.compose(record, ["stop", "--timeout", "60", "broker-service"])
        record["pending_reconnect"] = True
        write_json(self.locations.record, record)
        # A failed Redis replacement may have an unknown outcome: never restart an
        # old broker or promote the private intermediate file after a nonzero exit.
        authorize(self.locations, self.docker, release, record)
        render_configuration(self.locations, record)
        record.pop("pending_reconnect")
        write_json(self.locations.record, record)
        if not record.get("stopped"):
            self.docker.compose(record, ["up", "--detach", "--wait", "broker-service"])
            self.check_ready(record)
        else:
            self.docker.compose(record, ["stop", "redis"])

    def backup(self, record: dict[str, Any], release: Release) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder = self.locations.state / "backups" / f"{stamp}-{uuid.uuid4().hex[:6]}"
        folder.mkdir(parents=True, mode=0o700)
        settings = generate_env.read_env(self.locations.config / ".env.shared")
        dump = folder / "database.dump"
        with dump.open("wb") as output:
            self.docker.compose(
                record,
                [
                    "exec",
                    "-T",
                    "timescaledb",
                    "pg_dump",
                    "-U",
                    settings["POSTGRES_USER"],
                    "-d",
                    settings["POSTGRES_DB"],
                    "--format=custom",
                ],
                stdout=output,
            )
        with dump.open("rb") as source:
            self.docker.compose(
                record,
                ["exec", "-T", "timescaledb", "pg_restore", "--list"],
                stdin=source,
                capture=True,
            )
        self.docker.run(
            [
                "run",
                "--rm",
                "--mount",
                f"type=volume,source={record['project']}_redis_data,target=/source,readonly",
                "--mount",
                bind_mount(self.docker.host_path(folder), "/backup"),
                "--entrypoint",
                "tar",
                release.images["installer"],
                "-czf",
                "/backup/redis.tar.gz",
                "-C",
                "/source",
                ".",
            ]
        )
        with tarfile.open(folder / "redis.tar.gz", "r:gz") as archive:
            if not archive.getmembers():
                raise InstallationError("Redis backup is empty; upgrade was not started.")
        with tarfile.open(folder / "configuration.tar.gz", "w:gz") as archive:
            archive.add(self.locations.config, arcname="config")
            archive.add(self.locations.release_dir(record["version"]), arcname="release")
            archive.add(self.locations.record, arcname="installation.json")
        self.write_recovery(folder, record, release, settings)
        files = [path for path in folder.iterdir() if path.is_file()]
        for path in files:
            path.chmod(0o600)
        write_json(
            folder / "backup.json",
            {
                "version": record["version"],
                "project": record["project"],
                "sha256": {path.name: file_checksum(path) for path in files},
            },
        )
        return folder

    def write_recovery(
        self, folder: Path, record: dict[str, Any], release: Release, settings: dict[str, str]
    ) -> None:
        recovery = (Path(__file__).resolve().parents[1] / "docs/recovery.md").read_text()
        instructions = (
            f"# Recover {record['version']}\n\n"
            "Application writers are stopped. "
            "Preserve the failed volumes and this private backup.\n"
            f"Archived project: `{record['project']}`; "
            f"PostgreSQL major: {release.database_major}.\n"
            f"Database: `{settings['POSTGRES_DB']}`; user: `{settings['POSTGRES_USER']}`.\n\n"
            + recovery
        )
        protected_write(folder / "RECOVERY.md", instructions)

    def upgrade(self, target: Release) -> None:
        record = self.current()
        old_release = Release.read(self.locations.release_dir(record["version"]) / "release.json")
        if version_key(target.version) <= version_key(old_release.version):
            raise InstallationError(
                "Upgrade requires a newer explicit release; downgrades are unsupported."
            )
        if target.database_major != old_release.database_major:
            raise InstallationError(
                "PostgreSQL major upgrades need a separate migration procedure."
            )
        self.docker.pull(target)
        prepare_release(self.locations, target)
        self.docker.compose(record, ["up", "--detach", "--wait", "timescaledb", "redis"])
        self.docker.compose(record, ["stop", "--timeout", "60", "frontend", "backtester-api"])
        backup: Path | None = None
        try:
            if self.docker.sql(record, BUSY_QUERY).strip() != "f":
                raise InstallationError(
                    "Finish or cancel queued/running backtests and resolve held "
                    "execution slots before upgrading."
                )
            self.docker.compose(record, ["stop", "--timeout", "60", *APPLICATION_SERVICES, "redis"])
            backup = self.backup(record, old_release)
        except BaseException:
            if not record.get("stopped"):
                self.docker.compose(record, ["up", "--detach", "--wait", "--wait-timeout", "360"])
            else:
                self.docker.compose(record, ["stop", "--timeout", "60"])
            raise
        record["pending_upgrade"] = {"version": target.version, "backup": str(backup)}
        write_json(self.locations.record, record)
        candidate = {**record, "version": target.version}
        # Every following failure leaves a durable recovery marker and writers stopped.
        self.docker.compose(record, ["stop", "--timeout", "60", "timescaledb"])
        render_configuration(self.locations, candidate)
        self.docker.compose(candidate, ["up", "--detach", "--wait", "timescaledb", "redis"])
        self.docker.compose(
            candidate,
            [
                "exec",
                "-T",
                "timescaledb",
                "python3",
                "/usr/local/lib/algotrader/migrate_db.py",
                "--in-container",
                "--migrations-dir",
                "/docker-entrypoint-initdb.d/migrations",
            ],
        )
        try:
            self.docker.compose(
                candidate,
                [
                    "up",
                    "--detach",
                    "--wait",
                    "--wait-timeout",
                    "360",
                    *INTERNAL_SERVICES,
                ],
            )
            self.check_ready(candidate, announce=False)
            candidate.pop("pending_upgrade")
            if record.get("stopped"):
                self.docker.compose(candidate, ["stop", "--timeout", "60"])
            write_json(self.locations.record, candidate)
        except BaseException:
            self.docker.compose(candidate, ["stop", "--timeout", "60", *INTERNAL_SERVICES])
            raise
        # New work is admitted only after the candidate is durably accepted. A
        # later startup failure must never stop workers that may have accepted it.
        if not record.get("stopped"):
            self.docker.compose(
                candidate,
                [
                    "up",
                    "--detach",
                    "--wait",
                    "--wait-timeout",
                    "360",
                    *ADMISSION_SERVICES,
                ],
            )
            print(f"AlgoTrader is ready at http://localhost:{candidate['ui_port']}")
        print(f"Upgraded to {target.version}. Backup: {backup}")
