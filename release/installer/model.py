"""Versioned release metadata and protected installation records."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION = re.compile(
    r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
IMAGE = re.compile(r"^[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}$")
IMAGE_NAMES = frozenset(
    {
        "database-accessor-api",
        "backtester",
        "indicator-api",
        "timescaledb",
        "broker-service",
        "ingestion-service",
        "realtime-service",
        "frontend",
        "redis",
        "installer",
    }
)


class InstallationError(RuntimeError):
    """An actionable failure that does not expose credentials."""


def protected_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(content.encode() if isinstance(content, str) else content)
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    protected_write(path, json.dumps(value, indent=2) + "\n")


@dataclass(frozen=True)
class Release:
    version: str
    images: dict[str, str]
    database_major: int

    @classmethod
    def read(cls, path: Path) -> Release:
        try:
            value = json.loads(path.read_text())
            if value["schema_version"] != 1 or not VERSION.fullmatch(value["version"]):
                raise ValueError("unsupported release format")
            images = value["images"]
            if set(images) != IMAGE_NAMES or any(not IMAGE.fullmatch(v) for v in images.values()):
                raise ValueError("every release image must be pinned by digest")
            if value["database_major"] != 18:
                raise ValueError("unsupported PostgreSQL major version")
            return cls(value["version"], images, value["database_major"])
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise InstallationError(f"Invalid release manifest: {path.name}: {exc}") from exc

    def environment(self) -> dict[str, str]:
        return {
            "IMAGE_" + key.upper().replace("-", "_"): value for key, value in self.images.items()
        }


def version_key(version: str) -> tuple[int, int, int, tuple[tuple[int, Any], ...]]:
    match = VERSION.fullmatch(version)
    if not match:
        raise InstallationError("Version must use vMAJOR.MINOR.PATCH[-prerelease].")
    major, minor, patch, prerelease = match.groups()
    suffix = (
        ((2, ""),)
        if prerelease is None
        else tuple(
            (0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split(".")
        )
    )
    return int(major), int(minor), int(patch), suffix


@dataclass(frozen=True)
class Locations:
    config: Path = Path("/config")
    data: Path = Path("/data")
    state: Path = Path("/state")
    bundle: Path = Path("/bundle")

    @property
    def record(self) -> Path:
        return self.state / "installation.json"

    def installed(self) -> dict[str, Any]:
        if not self.record.exists():
            raise InstallationError("No installation found. Run setup first.")
        value = json.loads(self.record.read_text())
        if not re.fullmatch(r"algotrader-[0-9a-f]{12}", value.get("project", "")):
            raise InstallationError("Installation record has an invalid project name.")
        if not VERSION.fullmatch(value.get("version", "")):
            raise InstallationError("Installation record has an invalid version.")
        return value

    def release_dir(self, version: str) -> Path:
        if not VERSION.fullmatch(version):
            raise InstallationError("Invalid release version.")
        return self.data / "releases" / version
