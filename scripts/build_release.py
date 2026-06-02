#!/usr/bin/env python3
"""Build a distributable GeiWorld desktop package with PyInstaller."""
import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _platform_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    return "linux"


def _safe_version(version: str) -> str:
    return "".join(char if char.isalnum() or char in ".-_" else "-" for char in version)


def _archive_package(package_source: Path, archive_base: Path) -> str:
    """Create a zip archive. Use ditto for macOS .app bundles to preserve bundle metadata."""
    if platform.system() == "Darwin" and package_source.suffix == ".app":
        subprocess.run(["xattr", "-cr", str(package_source)], check=False)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(package_source)], check=True)
        archive_path = Path(f"{archive_base}.zip")
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                package_source.name,
                str(archive_path),
            ],
            cwd=package_source.parent,
            check=True,
        )
        return str(archive_path)
    return shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=package_source.parent,
        base_dir=package_source.name,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GeiWorld release artifact")
    parser.add_argument("--version", default="dev", help="Version or git tag used in artifact name")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    app_name = "GeiWorld"
    build_dir = root / "build"
    dist_dir = root / "dist"
    artifact_dir = root / "release-artifacts"

    for directory in (build_dir, dist_dir, artifact_dir):
        if directory.exists():
            shutil.rmtree(directory)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--windowed",
        "--name",
        app_name,
        "--paths",
        str(root),
        str(root / "scripts" / "ui_game.py"),
    ]
    subprocess.run(command, cwd=root, check=True)

    app_bundle = dist_dir / f"{app_name}.app"
    app_dir = dist_dir / app_name
    package_source = app_bundle if app_bundle.exists() else app_dir
    if not package_source.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {package_source}")

    platform_label = _platform_name()
    version = _safe_version(args.version)
    archive_base = artifact_dir / f"{app_name}-{platform_label}-{version}"
    archive_path = _archive_package(package_source, archive_base)
    print(f"Built artifact: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
