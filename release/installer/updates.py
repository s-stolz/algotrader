"""Find published releases and stage a checksum-verified installer bundle."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import io
import json
import re
import stat
import urllib.request
import zipfile
from pathlib import Path

from .model import VERSION, InstallationError, Release, version_key

API = "https://api.github.com/repos/s-stolz/algotrader/releases"
DOWNLOADS = "https://github.com/s-stolz/algotrader/releases/download"
MAX_DOWNLOAD = 8 * 1024 * 1024


def read_url(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "AlgoTrader-installer"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if not response.geturl().startswith("https://"):
                raise InstallationError("GitHub redirected the release download away from HTTPS.")
            content = response.read(limit + 1)
    except (OSError, http.client.HTTPException) as exc:
        raise InstallationError(f"Could not download {url}: {exc}") from exc
    if len(content) > limit:
        raise InstallationError("GitHub release response exceeds the installer size limit.")
    return content


def latest_version(prerelease: bool) -> str:
    if not prerelease:
        entry = json.loads(read_url(f"{API}/latest", MAX_DOWNLOAD))
        tag = entry.get("tag_name", "") if isinstance(entry, dict) else ""
        if (
            not isinstance(tag, str)
            or not VERSION.fullmatch(tag)
            or "-" in tag
            or entry.get("draft")
            or entry.get("prerelease")
        ):
            raise InstallationError("GitHub did not return a published stable AlgoTrader version.")
        return tag

    newest = None
    page = 1
    while True:
        entries = json.loads(read_url(f"{API}?per_page=100&page={page}", MAX_DOWNLOAD))
        if not isinstance(entries, list):
            raise InstallationError("Invalid GitHub release list.")
        for entry in entries:
            tag = entry.get("tag_name") if isinstance(entry, dict) else None
            if isinstance(tag, str) and VERSION.fullmatch(tag) and not entry.get("draft"):
                if newest is None or version_key(tag) > version_key(newest):
                    newest = tag
        if len(entries) < 100:
            break
        page += 1
    if newest is None:
        raise InstallationError("No published AlgoTrader releases were found.")
    return newest


def confirm_upgrade(current: str, target: str) -> bool:
    print(f"Installed version: {current}\nAvailable version: {target}", flush=True)
    if version_key(target) <= version_key(current):
        print("Your installation is already at or ahead of this version.")
        return False
    try:
        answer = input("Download and apply this upgrade? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() in {"y", "yes"}:
        return True
    print("Upgrade cancelled.")
    return False


def download_bundle(version: str, directory: Path) -> Release:
    if not VERSION.fullmatch(version):
        raise InstallationError("Invalid release tag.")
    filename = f"algotrader-{version}.zip"
    url = f"{DOWNLOADS}/{version}/{filename}"
    checksum = read_url(url + ".sha256", 1024).decode("ascii").rstrip("\r\n")
    match = re.fullmatch(r"([0-9a-fA-F]{64})  " + re.escape(filename), checksum)
    if not match:
        raise InstallationError("Invalid SHA-256 checksum file for the selected release.")
    content = read_url(url, MAX_DOWNLOAD)
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), match[1].lower()):
        raise InstallationError("Release ZIP checksum verification failed.")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 256 or sum(item.file_size for item in entries) > 2 * MAX_DOWNLOAD:
                raise InstallationError("Release ZIP exceeds the installer extraction limit.")
            for item in entries:
                parts = item.filename.rstrip("/").split("/")
                if (
                    any(part in {"", ".", ".."} for part in parts)
                    or "\\" in item.filename
                    or ":" in item.filename
                    or stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG, stat.S_IFDIR}
                ):
                    raise InstallationError("Unsafe path or file type in the release ZIP.")
                target = directory.joinpath(*parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as output:
                        output.write(archive.read(item))
    except (zipfile.BadZipFile, FileExistsError, RuntimeError) as exc:
        raise InstallationError(f"Invalid release ZIP: {exc}") from exc
    release = Release.read(directory / "release.json")
    installer = (directory / "installer-image.txt").read_text().strip()
    if (
        release.version != version
        or release.images["installer"] != installer
        or not installer.startswith("ghcr.io/")
        or not (directory / "compose.yaml").is_file()
    ):
        raise InstallationError(
            "Downloaded bundle does not match the selected release or installer."
        )
    return release
