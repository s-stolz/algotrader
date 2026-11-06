"""Install one monorepo service with shared dependency policy, or check its environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "broker-service",
    "indicator-api",
    "database-accessor-api",
    "ingestion-service",
    "realtime-service",
    "backtester",
)
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def require_supported_python() -> None:
    if not (3, 12) <= sys.version_info[:2] < (3, 16):
        raise ValueError("Use Python 3.12 through 3.15 for repository environments.")


def read_pins(path: Path, *, require_reason: bool = False) -> dict[str, str]:
    pins: dict[str, str] = {}
    reason = ""
    for number, line in enumerate(path.read_text().splitlines(), 1):
        value, _, comment = line.partition("#")
        value = value.strip()
        reason = comment.strip() or reason
        if not value:
            continue
        match = PIN.fullmatch(value)
        if not match:
            raise ValueError(f"{path}:{number}: expected a single package==version pin")
        name, version = match.groups()
        name = normalize_name(name)
        if name in pins:
            raise ValueError(f"{path}:{number}: duplicate pin for {name}")
        if require_reason and not reason:
            raise ValueError(f"{path}:{number}: explain the service override in a comment")
        pins[name] = version
        reason = ""
    return pins


def effective_pins(target: str, root: Path = ROOT) -> dict[str, str]:
    pins = read_pins(root / "constraints-shared.txt")
    override = root / target / "constraints.override.txt"
    if target != "root" and override.exists():
        replacements = read_pins(override, require_reason=True)
        unknown = replacements.keys() - pins.keys()
        if unknown:
            raise ValueError(f"Override has no shared pin: {', '.join(sorted(unknown))}")
        pins.update(replacements)
    return pins


def project(path: Path) -> dict:
    with (path / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]


def local_libraries(root: Path = ROOT) -> dict[str, Path]:
    return {
        normalize_name(project(path)["name"]): path
        for path in sorted((root / "libs").iterdir())
        if (path / "pyproject.toml").is_file()
    }


def dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
    if match is None:
        raise ValueError(f"Invalid package dependency: {requirement}")
    return normalize_name(match.group())


def service_install_arguments(
    target: str, *, dependencies_only: bool = False, root: Path = ROOT
) -> list[str]:
    libraries = local_libraries(root)
    dependencies = project(root / target)["dependencies"]
    selected: dict[str, Path] = {}
    pending = list(dependencies)
    while pending:
        name = dependency_name(pending.pop())
        if name in libraries and name not in selected:
            selected[name] = libraries[name]
            pending.extend(project(libraries[name]).get("dependencies", []))
    arguments = [argument for path in selected.values() for argument in ("-e", str(path))]
    if dependencies_only:
        arguments.extend(dependencies)
    else:
        arguments.extend(["-e", str(root / target)])
    return arguments


def install(target: str, *, dependencies_only: bool = False, dev: bool = False) -> None:
    pins = effective_pins(target)
    arguments = (
        ["-r", str(ROOT / "requirements.root.txt")]
        if target == "root"
        else service_install_arguments(target, dependencies_only=dependencies_only)
    )
    if dev and target != "root":
        arguments.extend(project(ROOT / target).get("optional-dependencies", {}).get("dev", []))
    with tempfile.TemporaryDirectory(prefix="algotrader-constraints-") as directory:
        constraints = Path(directory) / "constraints.txt"
        constraints.write_text("".join(f"{name}=={version}\n" for name, version in pins.items()))
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-c", str(constraints), *arguments],
            cwd=ROOT,
            check=True,
        )
    check(target, require_service=not dependencies_only)


def check(target: str, *, require_service: bool = True) -> None:
    mismatches = []
    for name, expected in effective_pins(target).items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        if actual != expected:
            mismatches.append(f"{name}: installed {actual}, expected {expected}")
    if target != "root" and require_service:
        name = project(ROOT / target)["name"]
        try:
            importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            mismatches.append(
                f"{name}: service package is not installed; run make venv SERVICE={target}"
            )
    if mismatches:
        raise ValueError("\n".join(mismatches))
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "check", "version"))
    parser.add_argument("target", nargs="?", choices=("root", *SERVICES))
    parser.add_argument("--dependencies-only", action="store_true")
    parser.add_argument("--dev", action="store_true", help="Install service development dependencies")
    args = parser.parse_args()
    require_supported_python()
    if args.command == "version":
        return
    if args.target is None:
        parser.error("install/check requires a target")
    if args.command == "install":
        install(args.target, dependencies_only=args.dependencies_only, dev=args.dev)
    else:
        check(args.target, require_service=not args.dependencies_only)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
