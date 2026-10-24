#!/usr/bin/env python3

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
WINDOW_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_WindowIOS.mm"


class GhostTripleTapDoubleClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WINDOW_SOURCE.read_text()

    def test_one_finger_triple_tap_is_registered_without_a_context_click(self) -> None:
        self.assertIn("triple_tap_gesture_recognizer", self.source)
        self.assertIn("@selector(handleTripleTap:)", self.source)
        self.assertIn("triple_tap_gesture_recognizer.numberOfTapsRequired = 3;", self.source)
        self.assertIn("triple_tap_gesture_recognizer.numberOfTouchesRequired = 1;", self.source)
        self.assertIn(
            "requireGestureRecognizerToFail:triple_tap_gesture_recognizer",
            self.source,
        )
        self.assertIn(
            "[self releaseGestureRecognizer:triple_tap_gesture_recognizer fromView:input_view];",
            self.source,
        )

    def test_triple_tap_emits_two_left_clicks_at_the_virtual_cursor(self) -> None:
        handler = self.source[
            self.source.rindex("- (void)handleTripleTap:") :
            self.source.rindex("- (void)handleTwoFingerHold:")
        ]

        self.assertEqual(handler.count("virtual_pointer->click(GHOST_kButtonMaskLeft)"), 2)
        self.assertNotIn("getScaledFirstTapPoint", handler)
        self.assertNotIn("GHOST_kButtonMaskRight", handler)


if __name__ == "__main__":
    unittest.main()
