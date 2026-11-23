#!/usr/bin/env python3

"""Apple Pencil strokes must start where the tip landed and end where it left the screen.

A TestFlight tester reported that strokes start a little after the tip touches the screen. The
drag recognizer only begins once the tip has moved past UIKit's drag threshold, so pressing at
its location loses the first part of every stroke. The window records the touch-down point and
presses there instead.

Stroke ends are issue #61.

On iPads with Pencil hover, UIKit can report a hover location while the tip is
down or as it lifts. That location is the last hover point, which is where the
stroke started. Delivering it before the stroke's button release drags the
stroke back to its start. These tests replay that ordering against the pure
contact state used by the window.
"""

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
GHOST_INTERN = REPOSITORY / "intern" / "ghost" / "intern"
CONTACT_HEADER = GHOST_INTERN / "GHOST_IOSPencilContact.hh"
WINDOW_SOURCE = GHOST_INTERN / "GHOST_WindowIOS.mm"
GHOST_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "ghost_ios.cmake"


def run_contact_harness(test: unittest.TestCase, body: str) -> None:
    harness = textwrap.dedent(
        """
        #include "GHOST_IOSPencilContact.hh"

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
        source = temporary / "pencil_contact_test.cc"
        executable = temporary / "pencil_contact_test"
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


class GhostPencilContactTests(unittest.TestCase):
    def test_stale_hover_during_a_stroke_is_ignored_and_release_uses_the_tip(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            CHECK(contact.acceptsHover());

            /* Hover reaches the start point, then the tip lands there. */
            contact.touchBegan(100.0, 200.0);
            CHECK(!contact.acceptsHover());
            contact.strokeBegan();
            contact.touchMoved(300.0, 260.0);
            contact.touchMoved(500.0, 320.0);
            CHECK(!contact.acceptsHover());

            /* The touch ends before the drag recognizer reports its end. A hover
             * update still carrying the start point must not move the cursor. */
            contact.touchEnded(520.0, 330.0);
            CHECK(!contact.acceptsHover());
            CHECK(contact.hasPoint());
            CHECK(contact.x() == 520.0 && contact.y() == 330.0);

            contact.strokeEnded();
            CHECK(contact.acceptsHover());
            CHECK(contact.x() == 520.0 && contact.y() == 330.0);
            """,
        )

    def test_recognizer_updates_keep_the_tip_current_without_window_touches(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            contact.strokeMoved(1.0, 1.0);
            CHECK(!contact.hasPoint());

            contact.strokeBegan();
            contact.strokeMoved(100.0, 200.0);
            contact.strokeMoved(400.0, 220.0);
            CHECK(!contact.acceptsHover());
            CHECK(contact.x() == 400.0 && contact.y() == 220.0);
            contact.strokeEnded();
            CHECK(contact.acceptsHover());
            CHECK(contact.x() == 400.0 && contact.y() == 220.0);
            """,
        )

    def test_stroke_can_end_before_the_touch_does(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            contact.touchBegan(10.0, 10.0);
            contact.strokeBegan();
            contact.touchMoved(40.0, 50.0);
            contact.strokeEnded();
            CHECK(!contact.acceptsHover());
            contact.touchEnded(42.0, 51.0);
            CHECK(contact.acceptsHover());
            """,
        )

    def test_stroke_starts_where_the_tip_landed(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            CHECK(!contact.hasStrokeStart());

            /* The tip lands, then moves past the drag threshold before the recognizer begins. */
            contact.touchBegan(100.0, 200.0);
            contact.touchMoved(104.0, 203.0);
            contact.touchMoved(112.0, 208.0);
            contact.strokeBegan();
            CHECK(contact.hasStrokeStart());
            CHECK(contact.strokeStartX() == 100.0 && contact.strokeStartY() == 200.0);
            contact.strokeMoved(112.0, 208.0);
            CHECK(contact.x() == 112.0 && contact.y() == 208.0);
            CHECK(contact.strokeStartX() == 100.0 && contact.strokeStartY() == 200.0);
            """,
        )

    def test_a_stroke_without_a_new_touch_has_no_stale_start(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            contact.touchBegan(10.0, 20.0);
            contact.touchEnded(10.0, 20.0);
            contact.strokeBegan();
            CHECK(!contact.hasStrokeStart());
            contact.strokeEnded();

            contact.touchBegan(30.0, 40.0);
            contact.reset();
            contact.strokeBegan();
            CHECK(!contact.hasStrokeStart());
            """,
        )

    def test_taps_and_cancelled_touches_restore_hover(self) -> None:
        run_contact_harness(
            self,
            """
            GHOST_IOSPencilContact contact;
            CHECK(!contact.hasPoint());
            contact.touchBegan(5.0, 6.0);
            contact.touchEnded(5.0, 6.0);
            CHECK(contact.acceptsHover());

            contact.touchBegan(7.0, 8.0);
            contact.strokeBegan();
            contact.reset();
            CHECK(contact.acceptsHover());
            CHECK(!contact.hasPoint());
            """,
        )


class GhostPencilContactWiringTests(unittest.TestCase):
    @staticmethod
    def method(source: str, signature: str) -> str:
        body = source[source.index(signature) :]
        return body[: body.index("\n}\n")]

    def test_contact_state_is_part_of_the_ghost_shim(self) -> None:
        self.assertIn("intern/GHOST_IOSPencilContact.hh", GHOST_CMAKE.read_text())
        self.assertIn("GHOST_IOSPencilContact.hh", WINDOW_SOURCE.read_text())

    def test_hover_is_ignored_while_the_pencil_is_down(self) -> None:
        source = WINDOW_SOURCE.read_text()
        hover = self.method(source, "- (void)handleHover:(GHOSTUIHoverGestureRecognizer *)sender\n{")
        guard = hover.index("pencil_contact.acceptsHover()")
        self.assertLess(guard, hover.index("moveAbsolute"))
        self.assertLess(guard, hover.index("tablet_data = GHOST_TABLET_DATA_NONE"))

    def test_pencil_drag_uses_the_tracked_tip_and_brackets_the_stroke(self) -> None:
        source = WINDOW_SOURCE.read_text()
        drag = self.method(source, "- (void)handlePencilDrag:(GHOSTUIPanGestureRecognizer *)sender\n{")
        self.assertIn("pencil_contact.strokeBegan()", drag)
        self.assertIn("pencil_contact.strokeEnded()", drag)
        self.assertIn("pencil_contact.strokeMoved(", drag)
        self.assertIn("pencil_contact.x()", drag)
        press = drag.index("button(GHOST_kButtonMaskLeft, true")
        start = drag.index("pencil_contact.strokeStartX()")
        self.assertLess(start, press)
        release = drag.index("button(GHOST_kButtonMaskLeft, false")
        self.assertLess(release, drag.index("pencil_contact.strokeEnded()"))

    def test_window_tracks_the_pencil_touch_location(self) -> None:
        source = WINDOW_SOURCE.read_text()
        window = source[source.index("@implementation GHOSTUIWindow") :]
        for signature, call in (
            ("- (void)touchesBegan:", "pencil_contact.touchBegan("),
            ("- (void)touchesMoved:", "pencil_contact.touchMoved("),
            ("- (void)touchesEnded:", "pencil_contact.touchEnded("),
            ("- (void)touchesCancelled:", "pencil_contact.touchEnded("),
        ):
            self.assertIn(call, self.method(window, signature))


if __name__ == "__main__":
    unittest.main()
