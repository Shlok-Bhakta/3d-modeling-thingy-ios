# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
SITE = REPOSITORY / "docs-site"
MEDIA = REPOSITORY / "docs-media"


class ReleaseDocsSiteTests(unittest.TestCase):
    def test_starlight_site_uses_bun_and_separate_media(self) -> None:
        package = (SITE / "package.json").read_text()
        config = (SITE / "astro.config.mjs").read_text()

        self.assertIn('"astro"', package)
        self.assertIn('"@astrojs/starlight"', package)
        self.assertTrue((SITE / "bun.lock").is_file())
        self.assertIn("starlight(", config)
        self.assertIn("base: '/3d-modeling-thingy-ios'", config)
        self.assertIn("publicDir: '../docs-media'", config)
        self.assertTrue(MEDIA.is_dir())

    def test_pages_deploy_runs_for_main_with_official_actions(self) -> None:
        workflow = (REPOSITORY / ".github" / "workflows" / "docs-pages.yml").read_text()

        self.assertIn("branches: [main]", workflow)
        self.assertIn("withastro/action@v6", workflow)
        self.assertIn("actions/deploy-pages@v5", workflow)
        self.assertIn("path: docs-site", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)

    def test_release_guide_covers_every_ios_control_group(self) -> None:
        docs = SITE / "src" / "content" / "docs"
        required_pages = (
            "index.md",
            "install.md",
            "controls/touch.md",
            "controls/keyboard-mouse-pencil.md",
            "workflow/files-and-windows.md",
            "workflow/rendering.md",
            "limitations.md",
        )
        for page in required_pages:
            self.assertTrue((docs / page).is_file(), page)

        touch = (docs / "controls" / "touch.md").read_text()
        for control in (
            "One-finger drag",
            "One-finger tap",
            "Tap, then hold and drag",
            "One-finger triple tap",
            "Two-finger tap",
            "Two-finger hold",
            "Two-finger drag",
            "Pinch",
            "Three-finger tap",
            "Three-finger drag",
            "Four-finger tap",
            "wraps",
        ):
            self.assertIn(control, touch)

        hardware = (docs / "controls" / "keyboard-mouse-pencil.md").read_text()
        for control in (
            "left, middle, and right buttons",
            "hardware keyboard",
            "Apple Pencil",
            "pressure",
            "tilt",
            "double tap",
        ):
            self.assertIn(control, hardware)

    def test_install_guide_describes_free_sidestore_path_and_expiry(self) -> None:
        install = (SITE / "src" / "content" / "docs" / "install.md").read_text()

        self.assertIn("SideStore", install)
        self.assertIn("LocalDevVPN", install)
        self.assertIn("Apple Account", install)
        self.assertIn("7 days", install)
        self.assertIn("iOS or iPadOS 18", install)
        self.assertIn("sidestore://install?url=", install)
        self.assertIn("releases/latest/download/Blender-iOS.ipa", install)

    def test_public_docs_never_load_planista_assets(self) -> None:
        offenders = []
        for root in (SITE, MEDIA):
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {
                    ".astro", ".css", ".html", ".js", ".json", ".md", ".mdx", ".mjs", ".ts", ".yaml", ".yml"
                }:
                    if "planista" in path.read_text(errors="ignore").lower():
                        offenders.append(path.relative_to(REPOSITORY).as_posix())
        self.assertEqual([], offenders)

    def test_documentation_media_stays_small(self) -> None:
        media_files = [path for path in MEDIA.rglob("*") if path.is_file()]
        self.assertTrue(media_files)
        self.assertLess(sum(path.stat().st_size for path in media_files), 50 * 1024 * 1024)
        for path in media_files:
            self.assertLess(path.stat().st_size, 10 * 1024 * 1024, path.name)


if __name__ == "__main__":
    unittest.main()
