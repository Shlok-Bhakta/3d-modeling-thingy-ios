# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile


IOS_DIR = Path(__file__).resolve().parents[1]
PACKAGER = IOS_DIR / "package_unsigned_ipa.py"
DEVICE_PROFILE = (
    IOS_DIR.parent / "cmake" / "config" / "blender_ios_device_minimal.cmake"
)


class UnsignedIpaTests(unittest.TestCase):
    def make_bundle(self, root: Path, sdk: str = "iphoneos") -> Path:
        bundle = root / "Blender.app"
        bundle.mkdir()
        with (bundle / "Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleExecutable": "Blender",
                    "CFBundleIdentifier": "com.marginallybetterapps.modeling3d",
                    "CFBundlePackageType": "APPL",
                    "UIDeviceFamily": [1, 2],
                },
                handle,
            )
        source = root / "fixture.c"
        source.write_text("int main(void) { return 0; }\n")
        command = ["xcrun", "--sdk", sdk, "clang", "-arch", "arm64"]
        if sdk == "iphonesimulator":
            command.extend(["-target", "arm64-apple-ios18.0-simulator"])
        else:
            command.extend(["-target", "arm64-apple-ios18.0"])
        command.extend([os.fspath(source), "-o", os.fspath(bundle / "Blender")])
        subprocess.run(command, check=True, capture_output=True, text=True)
        (bundle / "Assets").mkdir()
        (bundle / "Assets" / "startup.blend").write_bytes(b"fixture")
        return bundle

    def run_packager(self, bundle: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, os.fspath(PACKAGER), os.fspath(bundle), os.fspath(output)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_device_profile_selects_physical_ios(self) -> None:
        profile = DEVICE_PROFILE.read_text()
        self.assertIn('set(APPLE_TARGET_DEVICE      ios ', profile)
        self.assertNotIn('set(APPLE_TARGET_DEVICE      ios-simulator', profile)

    def test_packages_unsigned_universal_device_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            output = root / "Blender-unsigned.ipa"

            result = self.run_packager(bundle, output)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("Payload/Blender.app/Info.plist", names)
                self.assertIn("Payload/Blender.app/Blender", names)
                packaged_plist = plistlib.loads(
                    archive.read("Payload/Blender.app/Info.plist")
                )
                executable_mode = (
                    archive.getinfo("Payload/Blender.app/Blender").external_attr >> 16
                )
            self.assertEqual(set(packaged_plist["UIDeviceFamily"]), {1, 2})
            self.assertNotEqual(executable_mode & 0o111, 0)

    def test_rejects_simulator_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root, sdk="iphonesimulator")
            result = self.run_packager(bundle, root / "Blender-unsigned.ipa")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("IOS", result.stdout + result.stderr)

    def test_rejects_signing_contamination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            (bundle / "embedded.mobileprovision").write_bytes(b"fixture")
            result = self.run_packager(bundle, root / "Blender-unsigned.ipa")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SIGN-CONTAMINATION", result.stdout + result.stderr)

    def test_rejects_ad_hoc_signed_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            signed_executable = root / "signed-Blender"
            signed_executable.write_bytes((bundle / "Blender").read_bytes())
            signed_executable.chmod(0o755)
            subprocess.run(
                ["codesign", "--force", "--sign", "-", os.fspath(signed_executable)],
                check=True,
                capture_output=True,
                text=True,
            )
            (bundle / "Blender").write_bytes(signed_executable.read_bytes())
            (bundle / "Blender").chmod(0o755)

            result = self.run_packager(bundle, root / "Blender-unsigned.ipa")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SIGN-BINARY", result.stdout + result.stderr)

    def test_rejects_simulator_binary_nested_in_framework(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            framework = bundle / "Frameworks/Python.framework"
            framework.mkdir(parents=True)
            simulator_root = root / "simulator"
            simulator_root.mkdir()
            simulator_bundle = self.make_bundle(simulator_root, sdk="iphonesimulator")
            (framework / "Python").write_bytes((simulator_bundle / "Blender").read_bytes())
            (framework / "Python").chmod(0o755)

            result = self.run_packager(bundle, root / "Blender-unsigned.ipa")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ABI-PLATFORM", result.stdout + result.stderr)
            self.assertIn("Python.framework/Python", result.stdout + result.stderr)

    def test_rejects_loose_macho_in_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            loose_binary = bundle / "Assets/extension.so"
            loose_binary.write_bytes((bundle / "Blender").read_bytes())
            loose_binary.chmod(0o755)

            result = self.run_packager(bundle, root / "Blender-unsigned.ipa")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("IPA-MACHO-LOCATION", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
