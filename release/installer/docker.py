"""Docker invocation and host-path translation without shell evaluation."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from scripts import generate_env

from .model import InstallationError, Locations, Release


def bind_mount(source: str, target: str, *, readonly: bool = False) -> str:
    output = io.StringIO()
    values = ["type=bind", "source=" + source, "target=" + target]
    if readonly:
        values.append("readonly")
    csv.writer(output, lineterminator="").writerow(values)
    return output.getvalue()


class Docker:
    def __init__(self, locations: Locations):
        self.locations = locations
        self.controller = os.environ.get("ALGOTRADER_CONTROLLER_NAME", "")
        self.sources: dict[str, str] = {}

    def run(
        self,
        args: list[str],
        *,
        capture: bool = False,
        stdin: Any = None,
        stdout: Any = None,
        env: dict[str, str] | None = None,
    ) -> str:
        result = subprocess.run(
            ["docker", *args],
            check=False,
            stdin=stdin,
            stdout=subprocess.PIPE if capture else stdout,
            stderr=subprocess.PIPE,
            env=env,
        )
        if result.returncode:
            message = result.stderr.decode(errors="replace").strip()
            raise InstallationError(f"Docker command failed: {message[-3000:]}")
        return result.stdout.decode().strip() if capture else ""

    def discover_mounts(self) -> None:
        if not self.controller:
            raise InstallationError("Run this command through algotrader.sh or algotrader.ps1.")
        value = json.loads(self.run(["inspect", self.controller], capture=True))[0]
        self.sources = {
            mount["Destination"]: mount["Source"]
            for mount in value["Mounts"]
            if mount["Type"] == "bind"
        }
        for target in ("/config", "/data", "/state"):
            if target not in self.sources:
                raise InstallationError(f"Controller is missing its {target} directory mount.")

    def host_path(self, path: Path) -> str:
        # Inspect returns the daemon's translated path, including Docker Desktop mounts.
        for mount in sorted(self.sources, key=len, reverse=True):
            try:
                relative = path.relative_to(mount)
            except ValueError:
                continue
            return str(Path(self.sources[mount]) / relative)
        raise InstallationError(f"Path is outside the installation mounts: {path}")

    def compose(
        self,
        record: dict[str, Any],
        args: list[str],
        *,
        capture: bool = False,
        stdin: Any = None,
        stdout: BinaryIO | None = None,
    ) -> str:
        folder = self.locations.release_dir(record["version"])
        release = Release.read(folder / "release.json")
        environment = {
            **os.environ,
            **release.environment(),
            "ALGOTRADER_UI_PORT": str(record["ui_port"]),
        }
        return self.run(
            [
                "compose",
                "--project-name",
                record["project"],
                "--env-file",
                str(self.locations.config / ".env.shared"),
                "--file",
                str(folder / "compose.yaml"),
                *args,
            ],
            capture=capture,
            stdin=stdin,
            stdout=stdout,
            env=environment,
        )

    def pull(self, release: Release) -> None:
        for name, image in release.images.items():
            print(f"Downloading {name}…", flush=True)
            self.run(["pull", image])

    def apply_upgrade(self, bundle: Path, release: Release, installed_version: str) -> None:
        name = "algotrader-upgrade-" + uuid.uuid4().hex
        image = release.images["installer"]
        args = ["run", "--rm", "--name", name]
        for mount in ("/config", "/data", "/state", "/var/run/docker.sock"):
            args.extend(["--mount", bind_mount(self.sources[mount], mount)])
        args.extend(["--mount", bind_mount(self.host_path(bundle), "/bundle", readonly=True)])
        args.extend(["--env", "ALGOTRADER_CONTROLLER_NAME=" + name])
        args.extend(["--env", "ALGOTRADER_INSTALLER_IMAGE=" + image])
        args.extend(["--env", "ALGOTRADER_UPGRADE_FROM=" + installed_version])
        for variable in ("ALGOTRADER_HOST_UID", "ALGOTRADER_HOST_GID"):
            if variable in os.environ:
                args.extend(["--env", variable])
        self.run([*args, image, "upgrade"])

    def sql(self, record: dict[str, Any], query: str) -> str:
        settings = generate_env.read_env(self.locations.config / ".env.shared")
        return self.compose(
            record,
            [
                "exec",
                "-T",
                "timescaledb",
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                settings["POSTGRES_USER"],
                "-d",
                settings["POSTGRES_DB"],
                "-tAc",
                query,
            ],
            capture=True,
        )
