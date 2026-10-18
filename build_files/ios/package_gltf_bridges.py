#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Package glTF bridge dylibs as iOS frameworks for App Store distribution."""

from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import subprocess
import sys
from typing import Sequence


BRIDGE_NAMES = (
    "libbf_intern_draco_bridge.dylib",
    "libbf_intern_meshopt_bridge.dylib",
)
FRAMEWORK_NAMES = {
    "libbf_intern_draco_bridge.dylib": "draco",
    "libbf_intern_meshopt_bridge.dylib": "meshopt",
}


def package_bridges(
    app_bundle: Path,
    addon_directory: Path,
    *,
    platform: str = "iPhoneOS",
    minimum_os: str = "18.0",
) -> list[Path]:
    frameworks = app_bundle / "Frameworks"
    frameworks.mkdir(parents=True, exist_ok=True)
    relocated: list[Path] = []

    for name in BRIDGE_NAMES:
        source = addon_directory / name
        framework_name = FRAMEWORK_NAMES[name]
        destination = frameworks / f"{framework_name}.framework" / framework_name
        if source.is_symlink():
            source.unlink()
            if not destination.is_file():
                raise RuntimeError(f"missing relocated glTF bridge: {destination}")
            relocated.append(destination)
            continue
        if not source.is_file():
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        source.replace(destination)
        subprocess.run(
            ["install_name_tool", "-id", f"@rpath/{framework_name}.framework/{framework_name}", str(destination)],
            check=True,
        )
        info = {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleExecutable": framework_name,
            "CFBundleIdentifier": f"com.marginallybetterapps.modeling3d.{framework_name}",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundlePackageType": "FMWK",
            "CFBundleShortVersionString": "1.0",
            "CFBundleSupportedPlatforms": [platform],
            "CFBundleVersion": "1",
            "MinimumOSVersion": minimum_os,
        }
        with (destination.parent / "Info.plist").open("wb") as handle:
            plistlib.dump(info, handle)
        relocated.append(destination)

    return relocated


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-bundle", required=True, type=Path)
    parser.add_argument("--addon-directory", required=True, type=Path)
    parser.add_argument("--platform", choices=("iPhoneOS", "iPhoneSimulator"), default="iPhoneOS")
    parser.add_argument("--minimum-os", default="18.0")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    package_bridges(
        arguments.app_bundle,
        arguments.addon_directory,
        platform=arguments.platform,
        minimum_os=arguments.minimum_os,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
