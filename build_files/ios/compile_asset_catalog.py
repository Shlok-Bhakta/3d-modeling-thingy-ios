#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Compile the iOS app icon package into an installed bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import subprocess
import tempfile
from typing import Mapping, Sequence


def merge_plist(destination: Path, additions: Mapping[str, object]) -> None:
    with destination.open("rb") as handle:
        document = plistlib.load(handle)
    document.update(additions)
    with destination.open("wb") as handle:
        plistlib.dump(document, handle, sort_keys=False)


def compile_catalog(
    *,
    app_bundle: Path,
    icon_package: Path,
    platform: str,
    minimum_os: str,
) -> None:
    info_plist = app_bundle / "Info.plist"
    if not info_plist.is_file():
        raise FileNotFoundError(f"installed app Info.plist is missing: {info_plist}")
    if not icon_package.is_dir():
        raise FileNotFoundError(f"iOS icon package is missing: {icon_package}")

    # Keep generated data beside the install tree; canonical builds live on the
    # external build volume and must not spill large intermediates onto the host.
    with tempfile.TemporaryDirectory(
        prefix="blender-ios-assets-", dir=app_bundle.parent
    ) as temporary:
        partial_plist = Path(temporary) / "asset-info.plist"
        subprocess.run(
            [
                "xcrun",
                "actool",
                "--compile",
                str(app_bundle),
                "--platform",
                platform,
                "--minimum-deployment-target",
                minimum_os,
                "--target-device",
                "iphone",
                "--target-device",
                "ipad",
                "--app-icon",
                "modeling3d",
                "--compress-pngs",
                "--output-partial-info-plist",
                str(partial_plist),
                str(icon_package),
            ],
            check=True,
        )
        with partial_plist.open("rb") as handle:
            additions = plistlib.load(handle)
        merge_plist(info_plist, additions)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-bundle", required=True, type=Path)
    parser.add_argument("--icon-package", required=True, type=Path)
    parser.add_argument("--platform", choices=("iphoneos", "iphonesimulator"), required=True)
    parser.add_argument("--minimum-os", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    compile_catalog(
        app_bundle=arguments.app_bundle.resolve(),
        icon_package=arguments.icon_package.resolve(),
        platform=arguments.platform,
        minimum_os=arguments.minimum_os,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
