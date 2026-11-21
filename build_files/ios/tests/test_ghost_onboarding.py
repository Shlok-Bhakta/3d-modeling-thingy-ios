#!/usr/bin/env python3

"""The first-launch gesture guide shows once for people and never for automated launches.

TestFlight testers asked for a guide to the iPad controls, because the gestures were only
discoverable by searching online. These tests compile the pure decision logic used by the
window and check that the guide stays inside the iOS GHOST shim.
"""

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
GHOST_INTERN = REPOSITORY / "intern" / "ghost" / "intern"
STATE_HEADER = GHOST_INTERN / "GHOST_IOSOnboardingState.hh"
GUIDE_SOURCE = GHOST_INTERN / "GHOST_IOSOnboarding.mm"
WINDOW_SOURCE = GHOST_INTERN / "GHOST_WindowIOS.mm"
GHOST_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "ghost_ios.cmake"
HARNESS = REPOSITORY / "build_files" / "ios" / "simulator_onboarding.py"


def run_state_harness(test: unittest.TestCase, body: str) -> None:
    harness = textwrap.dedent(
        """
        #include "GHOST_IOSOnboardingState.hh"

        #include <cstdio>
        #include <cstdlib>

        #define CHECK(expr) \\
          do { \\
            if (!(expr)) { \\
              std::fprintf(stderr, "%s:%d: CHECK(%s) failed\\n", __FILE__, __LINE__, #expr); \\
              std::exit(1); \\
            } \\
          } while (0)

        int main()
        {
        """
    ) + textwrap.indent(textwrap.dedent(body), "  ") + "\n  return 0;\n}\n"

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        source = temporary / "onboarding_state_test.cc"
        executable = temporary / "onboarding_state_test"
        source.write_text(harness)
        compile_result = subprocess.run(
            ["xcrun", "clang++", "-std=c++17", "-Wall", "-Werror", "-I", str(GHOST_INTERN),
             str(source), "-o", str(executable)],
            capture_output=True,
            text=True,
        )
        test.assertEqual(compile_result.returncode, 0, compile_result.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class OnboardingDecisionTests(unittest.TestCase):
    def test_home_screen_launch_shows_until_the_current_version_is_finished(self) -> None:
        run_state_harness(
            self,
            """
            CHECK(GHOST_IOSOnboarding_shouldPresent(0, false, false));
            CHECK(GHOST_IOSOnboarding_shouldPresent(GHOST_IOS_ONBOARDING_VERSION - 1, false, false));
            CHECK(!GHOST_IOSOnboarding_shouldPresent(GHOST_IOS_ONBOARDING_VERSION, false, false));
            CHECK(!GHOST_IOSOnboarding_shouldPresent(GHOST_IOS_ONBOARDING_VERSION + 1, false, false));
            """,
        )

    def test_automated_launches_skip_unless_forced(self) -> None:
        run_state_harness(
            self,
            """
            CHECK(!GHOST_IOSOnboarding_shouldPresent(0, true, false));
            CHECK(GHOST_IOSOnboarding_shouldPresent(0, true, true));
            CHECK(GHOST_IOSOnboarding_shouldPresent(GHOST_IOS_ONBOARDING_VERSION, true, true));
            CHECK(GHOST_IOSOnboarding_shouldPresent(GHOST_IOS_ONBOARDING_VERSION, false, true));
            """,
        )

    def test_back_and_next_stay_on_the_guide_pages(self) -> None:
        run_state_harness(
            self,
            """
            const int last = GHOST_IOS_ONBOARDING_PAGE_COUNT - 1;
            CHECK(GHOST_IOSOnboarding_stepPage(0, -1) == 0);
            CHECK(GHOST_IOSOnboarding_stepPage(0, 1) == 1);
            CHECK(GHOST_IOSOnboarding_stepPage(last, 1) == last);
            CHECK(GHOST_IOSOnboarding_stepPage(last, -1) == last - 1);
            """,
        )


class OnboardingIntegrationTests(unittest.TestCase):
    def test_guide_is_an_ios_ghost_shim_hooked_from_the_main_window(self) -> None:
        cmake = GHOST_CMAKE.read_text()
        for name in ("GHOST_IOSOnboarding.hh", "GHOST_IOSOnboarding.mm",
                     "GHOST_IOSOnboardingState.hh"):
            self.assertIn(f"intern/{name}", cmake)
        window = WINDOW_SOURCE.read_text()
        hook = window[window.index("- (void)registerOnboarding\n{"):]
        hook = hook[: hook.index("\n}\n")]
        self.assertIn("isMainWindow()", hook)
        self.assertIn("GHOST_IOSOnboarding_presentIfNeeded", hook)
        self.assertIn("[ghost_rootWindow registerOnboarding];", window)

    def test_guide_is_modal_and_returns_keys_to_the_window(self) -> None:
        source = GUIDE_SOURCE.read_text()
        self.assertIn("UIModalPresentationOverFullScreen", source)
        self.assertIn("process.arguments.count > 1", source)
        finish = source[source.index("- (void)finish") : source.index("- (BOOL)canBecomeFirstResponder")]
        self.assertIn("setInteger:GHOST_IOS_ONBOARDING_VERSION", finish)
        self.assertIn("becomeFirstResponder", finish)

    def test_simulator_harness_uses_the_guide_identifiers(self) -> None:
        source = GUIDE_SOURCE.read_text()
        harness = HARNESS.read_text()
        for suffix in ("", "_skip", "_back", "_next", "_done"):
            self.assertIn(f'@"blender_onboarding{suffix}"', source)
        self.assertIn("GUIDE_ID = 'blender_onboarding'", harness)
        for title in ("Your finger is the mouse", "Getting around", "Shortcuts",
                      "A few more things"):
            self.assertIn(f'@"{title}"', source)
            self.assertIn(f"'{title}'", harness)


if __name__ == "__main__":
    unittest.main()
