#!/usr/bin/env python3

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
WINDOW_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_WindowIOS.mm"
POINTER_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSVirtualPointer.mm"


class GhostHardwareInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WINDOW_SOURCE.read_text()
        cls.pointer_source = POINTER_SOURCE.read_text()

    def test_mouse_buttons_are_not_delayed_by_tap_recognizers(self) -> None:
        # Wiring checks supplement simulator_hardware_input.py's real HID reproduction.
        self.assertNotIn("handleMouseButtonTap", self.source)
        self.assertIn("- (void)sendEvent:(UIEvent *)event", self.source)
        self.assertIn("event.buttonMask", self.source)
        for name in ("leftButton", "rightButton", "middleButton"):
            self.assertIn(f"input.{name}.pressedChangedHandler = button_changed", self.pointer_source)

    def test_mouse_drags_preserve_the_pressed_button(self) -> None:
        self.assertNotIn("handleHardwareDrag", self.source)
        self.assertIn("input.mouseMovedHandler", self.pointer_source)
        self.assertIn("GHOST_IOSPointerSource::Hardware", self.pointer_source)
        self.assertIn("pointerLockState.isLocked", self.pointer_source)
        self.assertIn("- (BOOL)prefersPointerLocked", self.source)

    def test_mouse_wheel_uses_native_wheel_events(self) -> None:
        handler = self.pointer_source.split('input.scroll.valueChangedHandler = ^', 1)[1]
        handler = handler.split('updatePointerLockPreference();', 1)[0]
        self.assertIn('GHOST_EventWheel', handler)
        self.assertIn('GHOST_kEventWheelAxisVertical', handler)
        self.assertIn('GHOST_kEventWheelAxisHorizontal', handler)
        self.assertNotIn('GHOST_EventTrackpad', handler)

    def test_pointer_scroll_generates_a_trackpad_scroll_event(self) -> None:
        self.assertIn("scroll_gesture_recognizer", self.source)
        self.assertIn("allowedScrollTypesMask = UIScrollTypeMaskAll", self.source)
        self.assertIn("POINTER_SCROLL", self.source)
        self.assertIn("GHOST_kTrackpadEventScroll", self.source)

    def test_hover_only_enables_tablet_data_for_pencil(self) -> None:
        self.assertIn("hover_touch_type", self.source)
        self.assertIn("[sender getTouchType] == UITouchTypePencil", self.source)

    def test_hardware_keyboard_focus_is_restored_after_text_entry(self) -> None:
        self.assertIn("- (BOOL)canBecomeFirstResponder", self.source)
        self.assertIn("[rootWindow becomeFirstResponder]", self.source)
        self.assertIn("[self becomeFirstResponder]", self.source)
        self.assertIn("UIKeyModifierCommand", self.source)


if __name__ == "__main__":
    unittest.main()
