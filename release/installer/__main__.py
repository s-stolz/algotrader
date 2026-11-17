"""Run local lifecycle commands inside the transient installer container."""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from .docker import Docker
from .lifecycle import Lifecycle
from .model import InstallationError, Locations, Release, require_installed_controller
from .updates import confirm_upgrade, download_bundle, latest_version


def restore_ownership(locations: Locations) -> None:
    uid = os.environ.get("ALGOTRADER_HOST_UID")
    gid = os.environ.get("ALGOTRADER_HOST_GID")
    if not uid or not gid or not uid.isdigit() or not gid.isdigit():
        return
    for root in (locations.config, locations.data, locations.state):
        for path in (root, *root.rglob("*")):
            if not path.is_symlink():
                os.chown(path, int(uid), int(gid))


@contextmanager
def installation_lock(locations: Locations, command: str) -> Iterator[None]:
    with (locations.state / ".controller.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InstallationError("Another installation command is already running.") from exc
        try:
            yield
        finally:
            # Discovery only stages temporary files; the target owns all persistent writes.
            if command != "update":
                restore_ownership(locations)


def apply_bundle(lifecycle: Lifecycle, command: str, image: str) -> None:
    release = Release.read(lifecycle.locations.bundle / "release.json")
    if release.images["installer"] != image:
        raise InstallationError("Installer image does not match the release manifest.")
    if command == "setup":
        lifecycle.setup(release)
        return
    installed = lifecycle.current()["version"]
    if os.environ.get("ALGOTRADER_UPGRADE_FROM", installed) != installed:
        raise InstallationError("Installed version changed. Run upgrade again.")
    if command == "upgrade" or confirm_upgrade(installed, release.version):
        lifecycle.upgrade(release)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and manage local AlgoTrader releases.")
    parser.add_argument(
        "command",
        choices=(
            "setup",
            "start",
            "stop",
            "status",
            "reconnect",
            "upgrade",
            "apply-bundle",
            "update",
        ),
    )
    parser.add_argument("--prerelease", action="store_true")
    args = parser.parse_args()
    if args.prerelease and args.command != "update":
        parser.error("--prerelease requires an update check")
    locations = Locations()
    for path in (locations.config, locations.data, locations.state):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    try:
        with ExitStack() as staging:
            with installation_lock(locations, args.command):
                image = os.environ.get("ALGOTRADER_INSTALLER_IMAGE", "")
                if args.command not in {"setup", "upgrade", "apply-bundle", "update"}:
                    require_installed_controller(locations, image)
                docker = Docker(locations)
                docker.discover_mounts()
                lifecycle = Lifecycle(locations, docker)
                if args.command == "update":
                    installed = lifecycle.current()["version"]
                    target = latest_version(args.prerelease)
                    if not confirm_upgrade(installed, target):
                        return 0
                    directory = Path(staging.enter_context(TemporaryDirectory(dir=locations.data)))
                    release = download_bundle(target, directory)
                elif args.command in {"setup", "upgrade", "apply-bundle"}:
                    apply_bundle(lifecycle, args.command, image)
                    return 0
                else:
                    getattr(lifecycle, args.command)()
                    return 0
            # The verified target controller takes the installation lock itself.
            docker.apply_upgrade(directory, release, installed)
        return 0
    except (InstallationError, OSError, ValueError, KeyError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Saved configuration and data have been retained.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
