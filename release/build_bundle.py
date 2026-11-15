"""Validate release tags and assemble a small digest-pinned installation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from release.installer.model import IMAGE_NAMES, VERSION, InstallationError, Release

ROOT = Path(__file__).resolve().parents[1]


def validate_tag(tag: str) -> None:
    if not VERSION.fullmatch(tag):
        raise InstallationError("Release tags must use vMAJOR.MINOR.PATCH[-prerelease].")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", f"refs/tags/{tag}^{{commit}}", "origin/main"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InstallationError("Release tag commit is not contained in origin/main.") from exc


def assemble(version: str, digests: Path, output: Path) -> Path:
    if not VERSION.fullmatch(version):
        raise InstallationError("Invalid release version.")
    images: dict[str, str] = {}
    for path in sorted(digests.glob("*.json")):
        value = json.loads(path.read_text())
        if value["name"] in images:
            raise InstallationError("Duplicate image digest: " + value["name"])
        images[value["name"]] = value["image"]
    if set(images) != IMAGE_NAMES:
        raise InstallationError("Release image inventory is incomplete.")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "version": version,
        "database_major": 18,
        "images": images,
    }
    manifest_path = output / "release.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    Release.read(manifest_path)
    files = {
        "release.json": manifest_path.read_bytes(),
        "installer-image.txt": (images["installer"] + "\n").encode(),
        "compose.yaml": (ROOT / "release/compose.yaml").read_bytes(),
        "algotrader.sh": (ROOT / "release/algotrader.sh").read_bytes(),
        "algotrader.ps1": (ROOT / "release/algotrader.ps1").read_bytes(),
        "README.md": (ROOT / "release/README.md").read_bytes(),
    }
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in sorted(files.items())
    ).encode()
    archive_path = output / f"algotrader-{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    (output / (archive_path.name + ".sha256")).write_text(
        hashlib.sha256(archive_path.read_bytes()).hexdigest() + "  " + archive_path.name + "\n"
    )
    return archive_path


def verify_public(images: dict[str, str]) -> None:
    # A new temporary Docker config ensures the check cannot use the publishing token.
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as config:
        env = {**os.environ, "DOCKER_CONFIG": config}
        for name, image in images.items():
            result = subprocess.run(
                ["docker", "manifest", "inspect", image], env=env, capture_output=True
            )
            if result.returncode:
                raise InstallationError(
                    f"{name} is not anonymously readable. Set its GitHub package visibility "
                    "to Public, then rerun this workflow. No downloadable release was published."
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    tag = commands.add_parser("validate-tag")
    tag.add_argument("version")
    bundle = commands.add_parser("assemble")
    bundle.add_argument("version")
    bundle.add_argument("--digests", type=Path, required=True)
    bundle.add_argument("--output", type=Path, required=True)
    public = commands.add_parser("verify-public")
    public.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.command == "validate-tag":
        validate_tag(args.version)
    elif args.command == "assemble":
        print(assemble(args.version, args.digests, args.output))
    else:
        verify_public(Release.read(args.manifest).images)


if __name__ == "__main__":
    main()
