# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest

from build_files.ios.package_python_frameworks import package_tree


class PackagePythonFrameworksTests(unittest.TestCase):
    def make_dylib(self, path: Path, install_name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        source = path.parent / f"{path.name}.c"
        source.write_text("void blender_python_extension_fixture(void) {}\n")
        subprocess.run(
            [
                "xcrun",
                "clang",
                "-dynamiclib",
                "-headerpad_max_install_names",
                "-install_name",
                install_name,
                "-o",
                str(path),
                str(source),
            ],
            check=True,
        )

    def install_name(self, path: Path) -> str:
        result = subprocess.run(
            ["xcrun", "otool", "-D", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.splitlines()[-1].strip()

    def test_extension_becomes_framework_with_bidirectional_markers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "Assets/5.2/python/lib/python3.13"
            extension = import_root / "lib-dynload/_ssl.cpython-313-iphonesimulator.so"
            self.make_dylib(extension, "Modules/_ssl.cpython-313-iphonesimulator.so")

            results = package_tree(
                app_bundle=app,
                import_root=import_root,
                bundle_identifier="com.shlokbhakta.modeling3d",
                platform="iPhoneSimulator",
                minimum_os="18.0",
            )

            framework = (app / "Frameworks/_ssl.framework").resolve()
            marker = import_root / "lib-dynload/_ssl.cpython-313-iphonesimulator.fwork"
            self.assertEqual(results, [framework])
            self.assertFalse(extension.exists())
            self.assertTrue(os.access(framework / "_ssl", os.X_OK))
            self.assertEqual(
                self.install_name(framework / "_ssl"),
                "@rpath/_ssl.framework/_ssl",
            )
            self.assertEqual(marker.read_text(), "Frameworks/_ssl.framework/_ssl\n")
            self.assertEqual(
                (framework / "_ssl.origin").read_text(),
                "Assets/5.2/python/lib/python3.13/lib-dynload/"
                "_ssl.cpython-313-iphonesimulator.fwork\n",
            )
            with (framework / "Info.plist").open("rb") as handle:
                metadata = plistlib.load(handle)
            self.assertEqual(metadata["CFBundlePackageType"], "FMWK")
            self.assertEqual(metadata["CFBundleExecutable"], "_ssl")
            self.assertEqual(metadata["CFBundleSupportedPlatforms"], ["iPhoneSimulator"])
            self.assertEqual(metadata["MinimumOSVersion"], "18.0")
            self.assertEqual(
                metadata["CFBundleIdentifier"], "com.shlokbhakta.modeling3d.-ssl"
            )

    def test_nested_extension_uses_fully_qualified_module_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "python"
            extension = import_root / "numpy/core/_multiarray_umath.abi3.so"
            self.make_dylib(extension, "Modules/_multiarray_umath.abi3.so")

            package_tree(
                app_bundle=app,
                import_root=import_root,
                bundle_identifier="com.shlokbhakta.modeling3d",
                platform="iPhoneOS",
                minimum_os="18.0",
            )

            framework = app / "Frameworks/numpy.core._multiarray_umath.framework"
            self.assertTrue((framework / "numpy.core._multiarray_umath").is_file())
            self.assertEqual(
                (import_root / "numpy/core/_multiarray_umath.abi3.fwork").read_text(),
                "Frameworks/numpy.core._multiarray_umath.framework/numpy.core._multiarray_umath\n",
            )

    def test_packaging_is_repeatable_after_install_repopulates_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "python"
            extension = import_root / "_ssl.cpython-313-iphonesimulator.so"
            self.make_dylib(extension, "Modules/_ssl.cpython-313-iphonesimulator.so")
            original = Path(directory) / "original.so"
            shutil.copy2(extension, original)

            arguments = {
                "app_bundle": app,
                "import_root": import_root,
                "bundle_identifier": "com.shlokbhakta.modeling3d",
                "platform": "iPhoneSimulator",
                "minimum_os": "18.0",
            }
            package_tree(**arguments)
            shutil.copy2(original, extension)
            package_tree(**arguments)

            binary = app / "Frameworks/_ssl.framework/_ssl"
            self.assertEqual(self.install_name(binary), "@rpath/_ssl.framework/_ssl")

    def test_duplicate_module_names_fail_before_mutating_import_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "python"
            first = import_root / "example.abi3.so"
            second = import_root / "example.cpython-313-iphonesimulator.so"
            self.make_dylib(first, "Modules/example.abi3.so")
            self.make_dylib(second, "Modules/example.cpython-313-iphonesimulator.so")

            with self.assertRaisesRegex(ValueError, "duplicate Python extension module"):
                package_tree(
                    app_bundle=app,
                    import_root=import_root,
                    bundle_identifier="com.shlokbhakta.modeling3d",
                    platform="iPhoneSimulator",
                    minimum_os="18.0",
                )

            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())

    def test_stale_generated_frameworks_are_removed_without_touching_other_frameworks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "python"
            extension = import_root / "example.abi3.so"
            self.make_dylib(extension, "Modules/example.abi3.so")

            stale = app / "Frameworks/old-name.framework"
            stale.mkdir(parents=True)
            (stale / "old-name.origin").write_text("python/example.abi3.fwork\n")
            unrelated = app / "Frameworks/Unrelated.framework"
            unrelated.mkdir()
            (unrelated / "Unrelated").write_bytes(b"not managed by the Python packager")

            package_tree(
                app_bundle=app,
                import_root=import_root,
                bundle_identifier="com.shlokbhakta.modeling3d",
                platform="iPhoneSimulator",
                minimum_os="18.0",
            )

            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.is_dir())

    def test_static_development_libraries_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Blender.app"
            import_root = app / "python"
            archive = import_root / "numpy/_core/lib/libnpymath.a"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"development-only archive")

            package_tree(
                app_bundle=app,
                import_root=import_root,
                bundle_identifier="com.shlokbhakta.modeling3d",
                platform="iPhoneOS",
                minimum_os="18.0",
            )

            self.assertFalse(archive.exists())


if __name__ == "__main__":
    unittest.main()
