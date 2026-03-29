#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from pathlib import Path


VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
PYTHON_VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$')


def read_version(version_file: Path) -> str:
    version = version_file.read_text(encoding="utf-8").strip()
    if not VERSION_RE.fullmatch(version):
        raise SystemExit(f"Invalid version in {version_file}: {version!r}")
    return version


def read_python_version(target: Path) -> str:
    match = PYTHON_VERSION_RE.fullmatch(target.read_text(encoding="utf-8").strip())
    if match is None:
        raise SystemExit(f"Unsupported Python version file format: {target}")
    return match.group(1)


def write_python_version(target: Path, version: str) -> None:
    target.write_text(f'__version__ = "{version}"\n', encoding="utf-8")


def read_package_json_version(target: Path) -> str:
    package = json.loads(target.read_text(encoding="utf-8"))
    version = package.get("version")
    if not isinstance(version, str):
        raise SystemExit(f"Missing or invalid version in {target}")
    return version


def write_package_json_version(target: Path, version: str) -> None:
    package = json.loads(target.read_text(encoding="utf-8"))
    package["version"] = version
    target.write_text(f"{json.dumps(package, indent=2)}\n", encoding="utf-8")


def version_targets(
    repo_root: Path,
) -> list[
    tuple[
        str,
        Path,
        Callable[[Path], str],
        Callable[[Path, str], None],
    ]
]:
    return [
        (
            "mitmproxy_addon",
            repo_root / "mitmproxy_addon/src/proxylens_mitmproxy/_version.py",
            read_python_version,
            write_python_version,
        ),
        (
            "server",
            repo_root / "server/src/proxylens_server/_version.py",
            read_python_version,
            write_python_version,
        ),
        (
            "ui",
            repo_root / "ui/package.json",
            read_package_json_version,
            write_package_json_version,
        ),
    ]


def check_versions(repo_root: Path, version: str) -> None:
    mismatches: list[str] = []
    for name, target, reader, _writer in version_targets(repo_root):
        current = reader(target)
        if current != version:
            mismatches.append(f"{name}: expected {version}, found {current} in {target}")

    if mismatches:
        raise SystemExit("Version mismatch detected:\n" + "\n".join(mismatches))

    print(f"All package versions match {version}")


def update_versions(repo_root: Path, version: str) -> None:
    for _name, target, _reader, writer in version_targets(repo_root):
        writer(target, version)

    print(f"Synchronized package versions to {version}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or sync package versions from VERSION.txt.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify package versions match VERSION.txt without changing files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    version = read_version(repo_root / "VERSION.txt")
    if args.check:
        check_versions(repo_root, version)
        return
    update_versions(repo_root, version)


if __name__ == "__main__":
    main()
