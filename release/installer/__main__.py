"""Run local lifecycle commands inside the transient installer container."""

from __future__ import annotations

import argparse
import fcntl
import os
import sys

from .docker import Docker
from .lifecycle import Lifecycle
from .model import InstallationError, Locations, Release, require_installed_controller


def restore_ownership(locations: Locations) -> None:
    uid = os.environ.get("ALGOTRADER_HOST_UID")
    gid = os.environ.get("ALGOTRADER_HOST_GID")
    if not uid or not gid or not uid.isdigit() or not gid.isdigit():
        return
    for root in (locations.config, locations.data, locations.state):
        for path in (root, *root.rglob("*")):
            if not path.is_symlink():
                os.chown(path, int(uid), int(gid))


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and manage local AlgoTrader releases.")
    parser.add_argument(
        "command", choices=("setup", "start", "stop", "status", "reconnect", "upgrade")
    )
    args = parser.parse_args()
    locations = Locations()
    for path in (locations.config, locations.data, locations.state):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    try:
        with (locations.state / ".controller.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise InstallationError("Another installation command is already running.") from exc
            if args.command not in {"setup", "upgrade"}:
                require_installed_controller(
                    locations, os.environ.get("ALGOTRADER_INSTALLER_IMAGE", "")
                )
            docker = Docker(locations)
            docker.discover_mounts()
            lifecycle = Lifecycle(locations, docker)
            if args.command in {"setup", "upgrade"}:
                release = Release.read(locations.bundle / "release.json")
                if release.images["installer"] != os.environ.get("ALGOTRADER_INSTALLER_IMAGE"):
                    raise InstallationError("Installer image does not match the release manifest.")
                getattr(lifecycle, args.command)(release)
            else:
                getattr(lifecycle, args.command)()
        return 0
    except (InstallationError, OSError, ValueError, KeyError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Saved configuration and data have been retained.", file=sys.stderr)
        return 130
    finally:
        restore_ownership(locations)


if __name__ == "__main__":
    raise SystemExit(main())
