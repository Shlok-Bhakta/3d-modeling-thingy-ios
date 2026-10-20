#!/usr/bin/env python3

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
WINDOW_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_WindowIOS.mm"


class GhostTouchPolishTests(unittest.TestCase):
    def test_one_finger_pan_only_moves_the_virtual_cursor(self) -> None:
        source = WINDOW_SOURCE.read_text()
        handler = source[
            source.rindex("- (void)handlePan:") : source.rindex("- (void)handlePencilDrag:")
        ]

        self.assertIn("virtual_pointer->moveRelative", handler)
        self.assertIn("getScaledInitialTouchPoint", handler)
        self.assertNotIn("virtual_pointer->button", handler)

    def test_only_two_finger_pan_can_run_with_pinch(self) -> None:
        source = WINDOW_SOURCE.read_text()
        delegate = source[
            source.rindex("shouldRecognizeSimultaneouslyWithGestureRecognizer:") : source.rindex(
                "- (void)updateTabletDataFromTouch:"
            )
        ]

        self.assertIn("gestureRecognizer == pan2f_gesture_recognizer", delegate)
        self.assertNotIn("gestureRecognizer == pan_gesture_recognizer", delegate)

    def test_double_tap_hold_is_an_explicit_relative_left_drag(self) -> None:
        source = WINDOW_SOURCE.read_text()

        self.assertIn("double_tap_drag_gesture_recognizer.numberOfTapsRequired = 1;", source)
        self.assertIn(
            "[tap_gesture_recognizer requireGestureRecognizerToFail:double_tap_drag_gesture_recognizer];",
            source,
        )

        handler = source[
            source.rindex("- (void)handleDoubleTapDrag:") : source.rindex("- (void)handleTwoFingerHold:")
        ]
        self.assertIn("virtual_pointer->beginRelative", handler)
        self.assertIn("virtual_pointer->moveRelative", handler)
        self.assertIn("virtual_pointer->button(GHOST_kButtonMaskLeft, true)", handler)
        self.assertIn("virtual_pointer->button(GHOST_kButtonMaskLeft, false)", handler)

    def test_double_tap_drag_recognizer_is_direct_touch_only_and_released(self) -> None:
        source = WINDOW_SOURCE.read_text()

        self.assertIn("double_tap_drag_gesture_recognizer.allowedTouchTypes = @[@(UITouchTypeDirect)];", source)
        self.assertIn(
            "[self releaseGestureRecognizer:double_tap_drag_gesture_recognizer fromView:input_view];",
            source,
        )


if __name__ == "__main__":
    unittest.main()
