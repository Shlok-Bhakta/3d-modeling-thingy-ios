#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Preferences > Input > Touchpad > Scroll Direction must change the iPad trackpad direction.

A TestFlight tester reported that trackpad orbit feels backwards. UIKit does not tell apps
whether the iPad uses natural scrolling, so GHOST cannot detect it the way macOS does. Blender
already shows the Scroll Direction preference when GHOST cannot detect the direction, but the
window manager skipped it on every Apple platform. Touchscreen gestures follow the fingers, so
they must keep their direction whatever the preference says.
"""

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
GHOST = REPOSITORY / "intern" / "ghost"
GHOST_INTERN = GHOST / "intern"
WINDOW_SOURCE = GHOST_INTERN / "GHOST_WindowIOS.mm"
SYSTEM_SOURCE = GHOST_INTERN / "GHOST_SystemIOS.mm"
COCOA_SOURCE = GHOST_INTERN / "GHOST_SystemCocoa.mm"
EVENT_SYSTEM = REPOSITORY / "source" / "blender" / "windowmanager" / "intern" / "wm_event_system.cc"


def run_event_harness(test: unittest.TestCase, body: str) -> None:
    harness = textwrap.dedent(
        """
        #include "GHOST_EventTrackpad.hh"

        #include <cstdio>
        #include <cstdlib>

        namespace mem_guarded::internal {
        void (*mem_freeN_ex)(void *, DestructorType) = nullptr;
        }

        #define CHECK(expr) \\
          do { \\
            if (!(expr)) { \\
              std::fprintf(stderr, "%s:%d: CHECK(%s) failed\\n", __FILE__, __LINE__, #expr); \\
              std::exit(1); \\
            } \\
          } while (0)

        static const GHOST_TEventTrackpadData &data(const GHOST_EventTrackpad &event)
        {
          return *static_cast<const GHOST_TEventTrackpadData *>(event.getData());
        }

        int main()
        {
        """
    ) + textwrap.indent(textwrap.dedent(body), "  ") + "\n  return 0;\n}\n"

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        source = temporary / "trackpad_direction_test.cc"
        executable = temporary / "trackpad_direction_test"
        source.write_text(harness)
        compile_result = subprocess.run(
            ["xcrun", "clang++", "-std=c++17", "-Wall", "-Werror", "-I", str(GHOST),
             "-I", str(GHOST_INTERN), "-I", str(REPOSITORY / "intern" / "guardedalloc"),
             str(source), "-o", str(executable)],
            capture_output=True,
            text=True,
        )
        test.assertEqual(compile_result.returncode, 0, compile_result.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def method(source: str, signature: str) -> str:
    body = source[source.index(signature) :]
    return body[: body.index("\n}\n")]


class TrackpadEventTests(unittest.TestCase):
    def test_trackpad_events_follow_the_preference_unless_marked_fixed(self) -> None:
        run_event_harness(
            self,
            """
            const GHOST_EventTrackpad scroll(
                0, nullptr, GHOST_kTrackpadEventScroll, 1, 2, 3, 4, true);
            CHECK(!data(scroll).hasFixedDirection);
            CHECK(data(scroll).isDirectionInverted);

            const GHOST_EventTrackpad touch(0, nullptr, GHOST_kTrackpadEventScroll, 1, 2, 3, 4,
                                            true, 2, GHOST_kModifierKeyNum, true);
            CHECK(data(touch).hasFixedDirection);
            CHECK(data(touch).numFingers == 2);
            """,
        )


class TrackpadDirectionWiringTests(unittest.TestCase):
    def test_window_manager_applies_the_preference_on_ios(self) -> None:
        source = EVENT_SYSTEM.read_text()
        block = source[source.index("/* Ensure \"auto\" is used when supported. */") - 200 :]
        block = block[: block.index("wm_event_add_trackpad")]
        guard = block[block.index("#if") : block.index("\n", block.index("#if"))]
        self.assertNotIn("__APPLE__", guard)
        self.assertIn("!pd->hasFixedDirection", block)

    def test_macos_still_detects_the_direction_itself(self) -> None:
        # The preference only applies without this capability, so dropping the Apple guard
        # leaves macOS on the system's natural scrolling setting.
        cocoa = method(COCOA_SOURCE.read_text(), "GHOST_SystemCocoa::getCapabilities() const")
        self.assertIn("GHOST_CAPABILITY_FLAG_ALL", cocoa)
        self.assertNotIn("GHOST_kCapabilityTrackpadPhysicalDirection", cocoa)

    def test_ios_cannot_detect_the_direction_so_the_preference_shows(self) -> None:
        ios = method(SYSTEM_SOURCE.read_text(), "GHOST_SystemIOS::getCapabilities() const")
        self.assertNotIn("GHOST_kCapabilityTrackpadPhysicalDirection", ios)

    def test_touchscreen_gestures_keep_their_direction(self) -> None:
        source = WINDOW_SOURCE.read_text()
        dispatch = method(source, "- (void)generateUserInputEvents:(const UserInputEvent &)event_info\n{")

        def case(name: str) -> str:
            body = dispatch[dispatch.index(f"case UserInputEvent::EventTypes::{name}:") :]
            return body[: body.index("break;")]

        for name in ("PAN_GESTURE_TWO_FINGERS", "PAN_GESTURE_THREE_FINGERS", "PINCH_GESTURE"):
            self.assertRegex(case(name), r"GHOST_kModifierKey\w+,\s*true\)\);", name)
        # A hardware trackpad or mouse scroll uses the preference.
        self.assertNotIn("GHOST_kModifierKey", case("POINTER_SCROLL"))


if __name__ == "__main__":
    unittest.main()
