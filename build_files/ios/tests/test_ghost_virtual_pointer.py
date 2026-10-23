#!/usr/bin/env python3

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
POINTER_HEADER = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSVirtualPointer.hh"
POINTER_STATE_HEADER = (
    REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSVirtualPointerState.hh"
)
POINTER_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSVirtualPointer.mm"
WINDOW_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_WindowIOS.mm"
SYSTEM_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_SystemIOS.mm"
GHOST_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "ghost_ios.cmake"
INPUT_TUNING = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSInputTuning.hh"


class GhostVirtualPointerStateTests(unittest.TestCase):
    def test_touch_release_does_not_release_a_held_hardware_button(self) -> None:
        harness = r'''
            #include "GHOST_IOSVirtualPointerState.hh"
            #include <cassert>
            int main() {
              GHOST_IOSVirtualPointerState state;
              state.setSource(GHOST_IOSPointerSource::Hardware);
              state.setButton(GHOST_IOSPointerButton::Left, true);
              state.setSource(GHOST_IOSPointerSource::Finger);
              state.setButton(GHOST_IOSPointerButton::Left, true);
              state.setButton(GHOST_IOSPointerButton::Left, false);
              assert(state.buttonDown(GHOST_IOSPointerButton::Left) &&
                     "touch release must preserve a mouse button still held on the device");
              state.setSource(GHOST_IOSPointerSource::Hardware);
              state.setButton(GHOST_IOSPointerButton::Left, false);
              assert(!state.buttonDown(GHOST_IOSPointerButton::Left));
              return 0;
            }
        '''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'button_ownership.cc'
            executable = Path(directory) / 'button_ownership'
            source.write_text(harness)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-I',
                            str(POINTER_STATE_HEADER.parent), str(source), '-o', str(executable)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pointer_state_supports_relative_absolute_and_warped_motion(self) -> None:
        harness = textwrap.dedent(
            r"""
            #include "GHOST_IOSVirtualPointerState.hh"

            #include <cassert>

            int main()
            {
              GHOST_IOSVirtualPointerState state;
              state.initialize(200.0, 100.0, 2.0);
              assert(state.x() == 100.0);
              assert(state.y() == 50.0);

              state.beginRelative(900.0, 700.0, 0.0);
              state.moveRelativeTo(908.0, 697.0, 0.5);
              assert(state.x() == 108.0);
              assert(state.y() == 47.0);
              state.endRelative();

              /* Repositioning a finger must not move or click the Blender cursor. */
              state.beginRelative(5.0, 5.0, 1.0);
              assert(state.x() == 108.0);
              assert(state.y() == 47.0);
              assert(!state.buttonDown(GHOST_IOSPointerButton::Left));
              state.moveRelativeTo(3.0, 9.0, 1.5);
              assert(state.x() == 106.0);
              assert(state.y() == 51.0);
              state.endRelative();

              state.moveAbsolute(25.0, 30.0, GHOST_IOSPointerSource::Pencil);
              assert(state.x() == 25.0);
              assert(state.y() == 30.0);
              assert(!state.visible());

              state.setSource(GHOST_IOSPointerSource::Finger);
              assert(state.visible());
              assert(state.x() == 25.0);
              assert(state.y() == 30.0);

              state.warp(10.0, 12.0);
              state.beginRelative(999.0, 999.0, 2.0);
              state.moveRelativeTo(1002.0, 1005.0, 2.5);
              assert(state.x() == 13.0);
              assert(state.y() == 18.0);

              state.moveAbsolute(77.0, 44.0, GHOST_IOSPointerSource::Hardware);
              assert(state.x() == 77.0);
              assert(state.y() == 44.0);
              assert(state.visible());

              state.setButton(GHOST_IOSPointerButton::Left, true);
              assert(state.buttonDown(GHOST_IOSPointerButton::Left));
              state.setButton(GHOST_IOSPointerButton::Left, false);
              assert(!state.buttonDown(GHOST_IOSPointerButton::Left));

              state.setBlenderVisibility(false);
              assert(!state.visible());
              state.setBlenderVisibility(true);
              assert(state.visible());
              return 0;
            }
            """
        )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "virtual_pointer_test.cc"
            executable = temporary / "virtual_pointer_test"
            source.write_text(harness)
            compile_result = subprocess.run(
                [
                    "xcrun",
                    "clang++",
                    "-std=c++17",
                    "-I",
                    str(POINTER_STATE_HEADER.parent),
                    str(source),
                    "-o",
                    str(executable),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            subprocess.run([str(executable)], check=True)

    def test_velocity_curve_preserves_precision_accelerates_and_is_bounded(self) -> None:
        harness = textwrap.dedent(
            r"""
            #include "GHOST_IOSVirtualPointerState.hh"

            #include <cassert>

            int main()
            {
              const double slow = GHOST_IOSPointerAcceleration::multiplier(2.0, 0.0, 0.02, 2.0);
              const double medium = GHOST_IOSPointerAcceleration::multiplier(20.0, 0.0, 0.02, 2.0);
              const double fast = GHOST_IOSPointerAcceleration::multiplier(80.0, 0.0, 0.02, 2.0);
              const double extreme =
                  GHOST_IOSPointerAcceleration::multiplier(10000.0, 0.0, 0.001, 2.0);

              assert(slow == GHOST_IOSInputTuning::pointer_min_multiplier);
              assert(medium > slow);
              assert(fast > medium);
              assert(fast <= GHOST_IOSInputTuning::pointer_max_multiplier);
              assert(extreme == GHOST_IOSInputTuning::pointer_max_multiplier);

              GHOST_IOSVirtualPointerState state;
              state.initialize(2000.0, 1000.0, 2.0);
              state.beginRelative(100.0, 100.0, 1.0);
              state.moveRelativeTo(180.0, 100.0, 1.02);
              assert(state.x() > 1000.0 + 80.0);
              assert(state.x() <=
                     1000.0 + 80.0 * GHOST_IOSInputTuning::pointer_max_multiplier);
              return 0;
            }
            """
        )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "virtual_pointer_acceleration_test.cc"
            executable = temporary / "virtual_pointer_acceleration_test"
            source.write_text(harness)
            compile_result = subprocess.run(
                [
                    "xcrun",
                    "clang++",
                    "-std=c++17",
                    "-I",
                    str(POINTER_STATE_HEADER.parent),
                    str(source),
                    "-o",
                    str(executable),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            subprocess.run([str(executable)], check=True)

    def test_pointer_bounds_wrap_on_both_axes_and_accumulate_modal_wraps(self) -> None:
        harness = textwrap.dedent(
            r"""
            #include "GHOST_IOSVirtualPointerState.hh"

            #include <cassert>

            int main()
            {
              GHOST_IOSVirtualPointerState state;
              state.initialize(200.0, 100.0, 2.0);

              state.warp(205.0, -3.0);
              state.wrapToBounds(0.0, 0.0, 200.0, 100.0, 2.0, true, true);
              assert(state.x() == 9.0);
              assert(state.y() == 93.0);

              state.warp(205.0, 105.0);
              const GHOST_IOSPointerWrapOffset wrap =
                  state.wrapToBounds(0.0, 0.0, 200.0, 100.0, 2.0, true, false);
              state.clampToBounds(0.0, 0.0, 200.0, 100.0);
              assert(state.x() == 9.0);
              assert(state.y() == 100.0);
              assert(wrap.x == 196.0);
              assert(wrap.y == 0.0);

              /* More than one screen of relative travel must still wrap correctly. */
              state.warp(610.0, 50.0);
              const GHOST_IOSPointerWrapOffset repeated_wrap =
                  state.wrapToBounds(0.0, 0.0, 200.0, 100.0, 2.0, true, false);
              assert(state.x() == 22.0);
              assert(repeated_wrap.x == 588.0);
              return 0;
            }
            """
        )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "virtual_pointer_bounds_test.cc"
            executable = temporary / "virtual_pointer_bounds_test"
            source.write_text(harness)
            compile_result = subprocess.run(
                [
                    "xcrun",
                    "clang++",
                    "-std=c++17",
                    "-I",
                    str(POINTER_STATE_HEADER.parent),
                    str(source),
                    "-o",
                    str(executable),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            subprocess.run([str(executable)], check=True)


class GhostVirtualPointerIntegrationTests(unittest.TestCase):
    def test_ios_build_owns_the_pointer_shim(self) -> None:
        cmake = GHOST_CMAKE.read_text()
        self.assertIn("intern/GHOST_IOSInputTuning.hh", cmake)
        self.assertIn("intern/GHOST_IOSVirtualPointer.hh", cmake)
        self.assertIn("intern/GHOST_IOSVirtualPointer.mm", cmake)

    def test_finger_motion_is_relative_and_does_not_hold_a_button(self) -> None:
        source = WINDOW_SOURCE.read_text()
        handler = source[source.rindex("- (void)handlePan:"): source.rindex("- (void)handlePan2f:")]
        self.assertIn("moveRelativeTo", handler)
        self.assertIn("getScaledTouchPoint", handler)
        self.assertNotIn("LEFT_BUTTON_DOWN", handler)
        self.assertNotIn("LEFT_BUTTON_UP", handler)

    def test_finger_tap_clicks_without_repositioning_the_cursor(self) -> None:
        source = WINDOW_SOURCE.read_text()
        handler = source[source.rindex("- (void)handleTap:"): source.rindex("- (void)handleTripleTap:")]
        direct_branch = handler[handler.index("else {"):]
        self.assertIn("virtual_pointer->click(GHOST_kButtonMaskLeft", handler)
        self.assertNotIn("getScaledTouchPoint", direct_branch)
        self.assertNotIn("moveAbsolute", direct_branch)

    def test_double_tap_hold_has_an_explicit_left_drag_lifetime(self) -> None:
        source = WINDOW_SOURCE.read_text()
        self.assertIn("double_tap_drag_gesture_recognizer.numberOfTapsRequired = 1;", source)
        handler = source[
            source.rindex("- (void)handleDoubleTapDrag:"): source.rindex("- (void)handleTwoFingerHold:")
        ]
        self.assertIn("button(GHOST_kButtonMaskLeft, true", handler)
        self.assertIn("moveRelativeTo", handler)
        self.assertIn("button(GHOST_kButtonMaskLeft, false", handler)

    def test_two_finger_hold_is_right_drag_at_virtual_cursor(self) -> None:
        source = WINDOW_SOURCE.read_text()
        handler = source[
            source.rindex("- (void)handleTwoFingerHold:"): source.rindex("- (void)handleTap2F:")
        ]
        self.assertIn("button(GHOST_kButtonMaskRight, true", handler)
        self.assertIn("moveRelativeTo", handler)
        self.assertIn("button(GHOST_kButtonMaskRight, false", handler)

    def test_pencil_and_hardware_pointer_feed_the_same_cursor(self) -> None:
        source = WINDOW_SOURCE.read_text()
        self.assertIn("handlePencilDrag:", source)
        self.assertIn("GHOST_IOSPointerSource::Pencil", source)
        self.assertIn("GHOST_IOSPointerSource::Hardware", source)
        self.assertIn("moveAbsolute", source)

    def test_system_cursor_polling_and_warp_use_the_pointer_shim(self) -> None:
        source = SYSTEM_SOURCE.read_text()
        self.assertIn("virtual_pointer_->getCursorPosition", source)
        self.assertIn("virtual_pointer_->warp", source)
        self.assertIn("virtual_pointer_->getButtons", source)

    def test_finger_pan_uses_touch_timestamps_and_processes_the_first_delta(self) -> None:
        source = WINDOW_SOURCE.read_text()
        recognizer = source[
            source.index("@interface GHOSTUIPanGestureRecognizer"):
            source.index("@interface GHOSTUIPinchGestureRecognizer")
        ]
        handler = source[
            source.rindex("- (void)handlePan:"): source.rindex("- (void)handlePencilDrag:")
        ]
        self.assertIn("getInitialTouchTimestamp", recognizer)
        self.assertIn("getTouchTimestamp", recognizer)
        self.assertIn("beginRelativeAtTime", handler)
        self.assertIn("moveRelativeToAtTime", handler)
        began = handler[handler.index("UIGestureRecognizerStateBegan"):
                        handler.index("UIGestureRecognizerStateChanged")]
        self.assertIn("getScaledInitialTouchPoint", began)
        self.assertIn("getScaledTouchPoint", began)
        self.assertIn("moveRelativeToAtTime", began)

    def test_relative_pointer_motion_is_constrained_or_wrapped_in_the_ios_shim(self) -> None:
        source = POINTER_SOURCE.read_text()
        constraint = source[
            source.index("void constrainCursorForEvent"):
            source.index("void sendButtonEvent")
        ]
        self.assertIn("grab_mode_ == GHOST_kGrabWrap", source)
        self.assertIn("grab_mode_ == GHOST_kGrabHide", source)
        self.assertIn("getCursorGrabBounds", source)
        self.assertIn("wrapToBounds", source)
        self.assertIn("clampToBounds", source)
        self.assertIn("setCursorGrabAccum", source)
        wrap_branch = constraint[:constraint.index("return;")]
        self.assertIn("clampToBounds", wrap_branch)

    def test_ordinary_pointer_motion_always_wraps_around_the_full_window(self) -> None:
        tuning = INPUT_TUNING.read_text()
        source = POINTER_SOURCE.read_text()
        constraint = source[
            source.index("void constrainCursorForEvent"):
            source.index("void sendButtonEvent")
        ]
        ordinary_branch = constraint[constraint.index("return;") + len("return;") :]

        self.assertIn("pointer_always_wrap = true", tuning)
        self.assertIn("pointer_always_wrap", ordinary_branch)
        self.assertIn("wrapToBounds", ordinary_branch)

    def test_virtual_pointer_advertises_real_cursor_warp_support(self) -> None:
        source = SYSTEM_SOURCE.read_text()
        capabilities = source[
            source.index("GHOST_TCapabilityFlag GHOST_SystemIOS::getCapabilities()"):
            source.index("#pragma mark Event handlers")
        ]
        self.assertIn("GHOST_kCapabilityCursorWarp", capabilities)

    def test_hidden_modal_grab_restores_the_virtual_cursor(self) -> None:
        source = WINDOW_SOURCE.read_text()
        grab = source[
            source.index("GHOST_TSuccess GHOST_WindowIOS::setWindowCursorGrab"):
            source.index("GHOST_TSuccess GHOST_WindowIOS::setWindowCursorShape")
        ]
        self.assertIn("cursor_grab_init_pos_", grab)
        self.assertIn("system_ios_->getCursorPosition", grab)
        self.assertIn("system_ios_->setCursorPosition", grab)
        self.assertIn("cursor_grab_ == GHOST_kGrabHide", grab)
        self.assertLess(
            grab.index("virtualPointer()->setGrabMode(mode)"),
            grab.index("system_ios_->setCursorPosition"),
        )

    def test_cursor_is_rendered_and_the_system_pointer_is_suppressed(self) -> None:
        source = POINTER_SOURCE.read_text()
        self.assertIn("CAShapeLayer", source)
        self.assertIn("addQuadCurveToPoint", source)
        self.assertIn("rasterizationScale", source)
        self.assertIn("hiddenPointerStyle", source)
        self.assertNotIn("node editor", source.lower())
        self.assertNotIn("space_node", source)


if __name__ == "__main__":
    unittest.main()
