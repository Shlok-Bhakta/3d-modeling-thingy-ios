#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Audit and package a universal unsigned Blender device bundle as an IPA."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
from typing import Sequence
import zipfile

from audit import Finding, audit_abi, audit_bundle, macho_candidates


EXPECTED_BUNDLE_ID = "com.marginallybetterapps.modeling3d"
EXPECTED_DEVICE_FAMILIES = {1, 2}
IPA_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def metadata_findings(bundle: Path) -> list[Finding]:
    plist_path = bundle / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as ex:
        return [Finding("IPA-PLIST", f"cannot load Info.plist: {ex}", str(plist_path))]

    findings: list[Finding] = []
    if plist.get("CFBundleIdentifier") != EXPECTED_BUNDLE_ID:
        findings.append(
            Finding(
                "IPA-BUNDLE-ID",
                f"expected {EXPECTED_BUNDLE_ID}",
                str(plist_path),
            )
        )
    try:
        families = {int(value) for value in plist.get("UIDeviceFamily", [])}
    except (TypeError, ValueError):
        families = set()
    if families != EXPECTED_DEVICE_FAMILIES:
        findings.append(
            Finding(
                "IPA-DEVICE-FAMILY",
                f"expected iPhone and iPad families; found {sorted(families)}",
                str(plist_path),
            )
        )
    return findings


def signature_findings(executable: Path) -> list[Finding]:
    result = subprocess.run(
        ["codesign", "--display", "--verbose=2", os.fspath(executable)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return [
            Finding(
                "SIGN-BINARY",
                "unsigned lane executable contains an embedded code signature",
                str(executable),
            )
        ]
    return []


def embedded_binary_findings(bundle: Path, main_executable: Path) -> list[Finding]:
    """Audit every executable image, not only the app's primary executable."""
    findings = audit_abi(bundle, "ios-device", "arm64")
    frameworks = bundle / "Frameworks"
    for binary in macho_candidates(bundle):
        if binary != main_executable and frameworks not in binary.parents:
            findings.append(
                Finding(
                    "IPA-MACHO-LOCATION",
                    f"embedded Mach-O binary must be contained in "
                    f"Blender.app/Frameworks: {binary}",
                    str(binary),
                )
            )
        findings.extend(signature_findings(binary))
    return findings


def archive_bundle(bundle: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(
            temporary_output,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in sorted(bundle.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = Path("Payload") / bundle.name / path.relative_to(bundle)
                info = zipfile.ZipInfo(relative.as_posix(), date_time=IPA_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) << 16
                with path.open("rb") as handle:
                    archive.writestr(info, handle.read(), compresslevel=9)
        os.replace(temporary_output, output)
    finally:
        temporary_output.unlink(missing_ok=True)


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    bundle = arguments.bundle.resolve()
    output = arguments.output.resolve()
    findings = audit_bundle(bundle, "device-unsigned", ())
    findings.extend(metadata_findings(bundle))

    plist_path = bundle / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            executable_name = plistlib.load(handle).get("CFBundleExecutable", "")
    except (OSError, plistlib.InvalidFileException):
        executable_name = ""
    if executable_name:
        executable = bundle / str(executable_name)
        findings.extend(embedded_binary_findings(bundle, executable))

    if findings:
        print(
            json.dumps(
                {
                    "ok": False,
                    "findings": [asdict(finding) for finding in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    archive_bundle(bundle, output)
    print(
        json.dumps(
            {
                "ok": True,
                "bundle": str(bundle),
                "ipa": str(output),
                "device_families": sorted(EXPECTED_DEVICE_FAMILIES),
                "signing": "unsigned",
                "target": "ios-device-arm64",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
