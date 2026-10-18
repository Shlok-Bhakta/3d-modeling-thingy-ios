# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
WORKFLOW = REPOSITORY / ".github" / "workflows" / "ios-pr-preview.yml"
HOST_PROFILE = (
    REPOSITORY / "build_files" / "cmake" / "config" / "blender_ios_host_tools.cmake"
)
DEPENDENCY_DOWNLOADS = (
    REPOSITORY
    / "build_files"
    / "ios"
    / "build_environment"
    / "cmake"
    / "download.cmake"
)
OPENCOLORIO_RECIPE = (
    REPOSITORY
    / "build_files"
    / "ios"
    / "build_environment"
    / "cmake"
    / "opencolorio.cmake"
)


class PrPreviewWorkflowTests(unittest.TestCase):
    def test_cancels_obsolete_preview_builds(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertNotIn("cancel-in-progress: false", workflow)

    def test_uses_github_hosted_arm_runner_and_content_addressed_caches(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("runs-on: xcode-27", workflow)
        self.assertIn("XCODE_PATH: /Applications/Xcode_27.app/Contents/Developer", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertIn("actions/cache", workflow)
        self.assertIn("dependency-cache-key", workflow)
        self.assertIn("host-tool-cache-key", workflow)
        self.assertIn("host-tool-cache-key=ios-host-tools-v2-", workflow)
        self.assertNotIn("github.workspace }}/../", workflow)

    def test_hydrates_required_lfs_files_from_public_blender_upstream(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("lfs: false", workflow)
        self.assertNotIn("lfs: true", workflow)
        self.assertIn("https://projects.blender.org/blender/blender.git/info/lfs", workflow)
        self.assertIn("release/datafiles/**", workflow)
        self.assertIn("scripts/**", workflow)

    def test_downloads_only_the_cached_ios_dependency_closure(self) -> None:
        workflow = WORKFLOW.read_text()
        downloads = DEPENDENCY_DOWNLOADS.read_text()
        self.assertIn("-DPACKAGE_USE_UPSTREAM_SOURCES=OFF", workflow)
        self.assertIn("-DBLENDER_DEPENDENCY_DOWNLOADS=", workflow)
        self.assertIn("BLENDER_DEPENDENCY_DOWNLOADS", downloads)
        self.assertIn("IN_LIST BLENDER_DEPENDENCY_DOWNLOADS", downloads)

    def test_dependency_cache_preserves_every_static_link_input(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("dependency-cache-key=ios-device-deps-v5-", workflow)
        self.assertGreaterEqual(
            workflow.count("${{ env.DEPS_BUILD }}/Release"),
            2,
        )
        self.assertIn('test -s "$DEPS_INSTALL/opencolorio/lib/libpystring.a"', workflow)
        self.assertIn('test -s "$DEPS_BUILD/Release/png/lib/libpng.a"', workflow)
        self.assertIn('test -s "$DEPS_BUILD/Release/zlib/lib/libz.a"', workflow)
        self.assertIn('test -s "$DEPS_BUILD/Release/ffmpeg/lib/libavcodec.a"', workflow)
        self.assertIn('test -s "$DEPS_BUILD/Release/usd/lib/libusd_m.a"', workflow)

    def test_cached_dependencies_skip_the_redundant_full_abi_scan(self) -> None:
        workflow = WORKFLOW.read_text()
        audit_step = workflow.split("- name: Audit cached dependency prefix", 1)[1].split(
            "- name: Save iOS dependency prefix", 1
        )[0]
        self.assertIn("DEPENDENCY_CACHE_HIT", audit_step)
        self.assertIn("build_files/ios/audit.py abi", audit_step)
        self.assertIn('if [[ "$DEPENDENCY_CACHE_HIT" != "true" ]]', audit_step)

    def test_full_app_build_reuses_a_bounded_compiler_cache(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("CCACHE_DIR:", workflow)
        self.assertIn("CCACHE_MAXSIZE: 4G", workflow)
        self.assertIn("Restore full-app compiler cache", workflow)
        self.assertIn("Save full-app compiler cache", workflow)
        self.assertIn("ios-device-ccache-v1-", workflow)
        self.assertIn("restore-keys:", workflow)
        self.assertIn("-DCMAKE_C_COMPILER_LAUNCHER=ccache", workflow)
        self.assertIn("-DCMAKE_CXX_COMPILER_LAUNCHER=ccache", workflow)
        self.assertIn("ccache --show-stats", workflow)

    def test_build_parallelism_tracks_the_runner_instead_of_a_magic_number(self) -> None:
        workflow = WORKFLOW.read_text()
        app_step = workflow.split("- name: Configure and build unsigned device app", 1)[1].split(
            "- name: Save full-app compiler cache", 1
        )[0]
        self.assertIn('build_jobs="$(sysctl -n hw.logicalcpu)"', app_step)
        self.assertIn('--parallel "$build_jobs"', app_step)
        self.assertNotIn("--parallel 3", app_step)

    def test_opencolorio_finishes_static_library_copies_before_harvesting(self) -> None:
        recipe = OPENCOLORIO_RECIPE.read_text()
        harvest_step = recipe.split(
            "ExternalProject_Add_Step(external_opencolorio harvest_ios", 1
        )[1]
        self.assertIn("DEPENDEES after_install", harvest_step)

    def test_publishes_exact_pr_release_contract(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("gh release delete", workflow)
        self.assertIn("--cleanup-tag", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("--prerelease", workflow)
        self.assertIn("3D-Modeling-Thingy-Preview-unsigned.ipa", workflow)
        self.assertIn("application/octet-stream", workflow)
        self.assertIn("gh pr comment", workflow)
        self.assertIn("marginally-better-apps.github.io/Autoloader", workflow)
        self.assertNotIn("planista.shloklab.us", workflow.lower())

    def test_write_lane_excludes_forks(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", workflow)
        self.assertIn("startsWith(github.head_ref, 'story/')", workflow)
        self.assertIn("startsWith(github.head_ref, 'feat/')", workflow)
        self.assertIn("startsWith(github.head_ref, 'refactor/')", workflow)

    def test_host_tools_match_the_device_generator_features(self) -> None:
        profile = HOST_PROFILE.read_text()
        workflow = WORKFLOW.read_text()
        self.assertIn("include(\"${CMAKE_CURRENT_LIST_DIR}/blender_full.cmake\")", profile)
        self.assertIn(
            "include(\"${CMAKE_CURRENT_LIST_DIR}/blender_ios_features.cmake\")",
            profile,
        )
        self.assertNotIn("blender_lite.cmake", profile)
        for feature in ("WITH_CYCLES", "WITH_METAL_BACKEND", "WITH_PYTHON", "WITH_TBB"):
            self.assertIn(f"set({feature}", profile)
            self.assertIn("ON CACHE BOOL", profile)
        self.assertIn("makesdna makesrna datatoc msgfmt shader_tool", workflow)
        self.assertIn('cp "$HOST_BUILD/bin/msgfmt"', workflow)

    def test_host_tool_cache_includes_the_recursive_dylib_closure(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("build_files/ios/bundle_host_tool_runtime.py", workflow)
        self.assertIn('--destination "$HOST_INSTALL/lib"', workflow)
        self.assertIn('find "$HOST_INSTALL/lib"', workflow)
        self.assertIn('export DYLD_LIBRARY_PATH="$HOST_INSTALL/lib', workflow)

    def test_host_library_checkout_overrides_the_disabled_submodule_policy(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("submodule.lib/macos_arm64.update=checkout", workflow)

    def test_runs_portable_file_access_regressions_before_building(self) -> None:
        workflow = WORKFLOW.read_text()
        regression_step = workflow.split(
            "- name: Run portable iOS file-access regression tests", 1
        )[1].split("- name: Build revision-matched native tools on cache miss", 1)[0]

        for test_file in (
            "test_ghost_file_access.py",
            "test_simulator_file_access.py",
            "test_file_access_runtime.py",
            "test_pr_preview_workflow.py",
        ):
            self.assertIn(test_file, regression_step)
        self.assertNotIn("test_*.py", regression_step)


if __name__ == "__main__":
    unittest.main()
