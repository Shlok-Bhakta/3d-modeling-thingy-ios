# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import plistlib
import tempfile
import unittest

from build_files.ios.compile_asset_catalog import merge_plist


class CompileAssetCatalogTests(unittest.TestCase):
    def test_partial_asset_metadata_is_merged_without_losing_bundle_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            info_plist = Path(directory) / "Info.plist"
            with info_plist.open("wb") as handle:
                plistlib.dump(
                    {
                        "CFBundleIdentifier": "com.marginallybetterapps.modeling3d",
                        "UIDeviceFamily": [1, 2],
                    },
                    handle,
                )

            merge_plist(
                info_plist,
                {
                    "CFBundleIcons": {
                        "CFBundlePrimaryIcon": {
                            "CFBundleIconName": "modeling3d"
                        }
                    }
                },
            )

            with info_plist.open("rb") as handle:
                merged = plistlib.load(handle)
            self.assertEqual(
                merged["CFBundleIdentifier"], "com.marginallybetterapps.modeling3d"
            )
            self.assertEqual(merged["UIDeviceFamily"], [1, 2])
            self.assertEqual(
                merged["CFBundleIcons"]["CFBundlePrimaryIcon"]["CFBundleIconName"],
                "modeling3d",
            )


if __name__ == "__main__":
    unittest.main()
