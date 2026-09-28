# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import plistlib
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
PRODUCT_INFO_PLIST = REPOSITORY / "release" / "ios" / "Blender.app" / "Info.plist"

IPHONE_FAMILY = 1
IPAD_FAMILY = 2
IPAD_ORIENTATIONS = {
    "UIInterfaceOrientationLandscapeLeft",
    "UIInterfaceOrientationLandscapeRight",
    "UIInterfaceOrientationPortrait",
    "UIInterfaceOrientationPortraitUpsideDown",
}


class UniversalBundlePlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with PRODUCT_INFO_PLIST.open("rb") as handle:
            cls.plist = plistlib.load(handle)

    def test_bundle_id_is_the_single_ios_product(self) -> None:
        self.assertEqual(
            self.plist["CFBundleIdentifier"],
            "com.marginallybetterapps.modeling3d",
        )

    def test_declares_iphone_and_ipad_device_families(self) -> None:
        families = {int(value) for value in self.plist["UIDeviceFamily"]}
        self.assertEqual(families, {IPHONE_FAMILY, IPAD_FAMILY})

    def test_ipad_orientations_include_portrait_and_landscape(self) -> None:
        orientations = set(self.plist["UISupportedInterfaceOrientations~ipad"])
        self.assertEqual(orientations, IPAD_ORIENTATIONS)

    def test_iphone_orientations_remain_landscape_only(self) -> None:
        orientations = set(self.plist["UISupportedInterfaceOrientations"])
        self.assertEqual(
            orientations,
            {
                "UIInterfaceOrientationLandscapeLeft",
                "UIInterfaceOrientationLandscapeRight",
            },
        )

    def test_declares_modern_launch_screen_for_full_device_viewport(self) -> None:
        self.assertIn("UILaunchScreen", self.plist)
        self.assertIsInstance(self.plist["UILaunchScreen"], dict)

    def test_registers_blend_documents_for_in_place_editing(self) -> None:
        self.assertTrue(self.plist["LSSupportsOpeningDocumentsInPlace"])
        self.assertIn(
            "com.marginallybetterapps.modeling3d.project",
            self.plist["CFBundleDocumentTypes"][0]["LSItemContentTypes"],
        )
        self.assertEqual(
            self.plist["UTExportedTypeDeclarations"][0]["UTTypeTagSpecification"]
            ["public.filename-extension"],
            ["blend"],
        )

    def test_declares_single_window_scene_lifecycle(self) -> None:
        manifest = self.plist["UIApplicationSceneManifest"]
        self.assertFalse(manifest["UIApplicationSupportsMultipleScenes"])
        configurations = manifest["UISceneConfigurations"]
        application = configurations["UIWindowSceneSessionRoleApplication"]
        self.assertEqual(len(application), 1)
        self.assertEqual(application[0]["UISceneClassName"], "UIWindowScene")
        self.assertEqual(application[0]["UISceneDelegateClassName"], "IOSSceneDelegate")
