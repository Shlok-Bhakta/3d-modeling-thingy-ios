#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check that the wheel acceptance assertion rejects incorrect observations."""
import copy
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'simulator_hardware_input.py'
SPEC = importlib.util.spec_from_file_location('simulator_hardware_input', SCRIPT)
HARDWARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARDWARE)


class WheelAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(t=0, distance=10, rotation=[1, 0, 0, 0], pointer=[300, 400],
                           view_location=[0, 0, 0])
        self.after = dict(self.before, distance=8,
                          events=[dict(type='WHEELUPMOUSE') for _ in range(3)])
        self.samples = [dict(platform=dict(scroll_events=[
            dict(time=i, sequence=i, x=0, y=1) for i in (1, 2, 3)]))]

    def test_accepts_zoom_in_and_zoom_out(self):
        HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)
        self.after.update(distance=12, events=[dict(type='WHEELDOWNMOUSE') for _ in range(3)])
        for report in self.samples[0]['platform']['scroll_events']:
            report['y'] = -1
        HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)
        self.after['events'] = self.after['events'][:1]
        self.samples[0]['platform']['scroll_events'] = self.samples[0]['platform']['scroll_events'][:1]
        HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples, expected_reports=1)

    def test_rejects_orbit_without_zoom(self):
        self.after.update(distance=10, rotation=[.99, .1, 0, 0],
                          events=[dict(type='TRACKPADPAN') for _ in range(3)])
        with self.assertRaisesRegex(AssertionError, 'did not zoom'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_normalizes_raw_scroll_axes_for_each_orientation(self):
        for orientation, axis, sign in ((1, 'y', 1), (2, 'y', -1),
                                         (3, 'x', -1), (4, 'x', 1)):
            with self.subTest(orientation=orientation):
                platform = self.samples[0]['platform']
                platform['interface_orientation'] = orientation
                platform['scroll_events'] = [dict(time=i, sequence=i, x=0, y=0)
                                              for i in (1, 2, 3)]
                for report in platform['scroll_events']:
                    report[axis] = sign
                HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_rejects_rotation_even_when_zoom_changes(self):
        self.after['rotation'] = [.99, .1, 0, 0]
        with self.assertRaisesRegex(AssertionError, 'rotated'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_rejects_sideways_movement_even_when_zoom_changes(self):
        self.after['view_location'] = [1, 0, 0]
        with self.assertRaisesRegex(AssertionError, 'panned'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_rejects_wrong_direction(self):
        self.after['distance'] = 12
        with self.assertRaisesRegex(AssertionError, 'expected direction'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_rejects_missing_and_duplicate_events(self):
        for count in (0, 2, 4, 6):
            with self.subTest(count=count):
                after = copy.deepcopy(self.after)
                after['events'] = [dict(type='WHEELUPMOUSE') for _ in range(count)]
                with self.assertRaisesRegex(AssertionError, 'arrive once'):
                    HARDWARE.assert_wheel_zoom(self.before, after, self.samples)

    def test_rejects_cursor_movement(self):
        self.after['pointer'] = [301, 400]
        with self.assertRaisesRegex(AssertionError, 'moved the cursor'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_missing_os_input_is_an_invalid_fixture(self):
        self.samples[0]['platform']['scroll_events'] = []
        with self.assertRaisesRegex(RuntimeError, 'invalid HID setup'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)

    def test_dropped_os_report_is_an_invalid_fixture(self):
        self.samples[0]['platform']['scroll_events'] = self.samples[0]['platform']['scroll_events'][:1]
        with self.assertRaisesRegex(RuntimeError, '1 of 3 wheel reports'):
            HARDWARE.assert_wheel_zoom(self.before, self.after, self.samples)


class FeedbackFixtureGeometryTests(unittest.TestCase):
    AREAS = [['VIEW_3D', 0, 300, 1500, 1600], ['OUTLINER', 1502, 1300, 548, 600],
             ['PROPERTIES', 1502, 300, 548, 998], ['DOPESHEET_EDITOR', 0, 0, 2050, 298]]

    def test_touch_points_flip_blender_window_y(self):
        self.assertEqual(HARDWARE.window_to_touch((500, 0), 1000, 2000), [.5, 1])
        self.assertEqual(HARDWARE.window_to_touch((0, 2000), 1000, 2000), [0, 0])

    def test_two_finger_drag_keeps_both_contacts_parallel(self):
        events = HARDWARE.two_finger_drag((500, 1000), 1000, 2000, -200, steps=4, spread=100)
        self.assertEqual([e['phase'] for e in events], [1, 6, 6, 6, 6, 2])
        self.assertEqual(events[0]['points'], [[.45, .5], [.55, .5]])
        self.assertEqual(events[-1]['points'], [[.45, .6], [.55, .6]])
        for event in events:
            self.assertEqual(event['points'][0][1], event['points'][1][1])

    def test_border_is_between_viewport_and_tallest_right_neighbor(self):
        self.assertEqual(HARDWARE.vertical_border(self.AREAS), [1501, 799])

    def test_border_requires_a_right_neighbor(self):
        with self.assertRaisesRegex(RuntimeError, 'no area touches'):
            HARDWARE.vertical_border([['VIEW_3D', 0, 0, 100, 100]])


class ModifiedWheelAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(t=0)
        self.event = dict(type='WHEELUPMOUSE', shift=True, ctrl=False, alt=False, oskey=False)
        self.after = dict(events=[self.event])
        self.samples = [dict(platform=dict(scroll_events=[dict(time=1, sequence=1, x=0, y=1)]))]

    def test_accepts_all_modifier_combinations(self):
        for flags in (['shift'], ['ctrl'], ['shift', 'ctrl'], ['alt'], ['oskey']):
            with self.subTest(flags=flags):
                for key in ('shift', 'ctrl', 'alt', 'oskey'):
                    self.event[key] = key in flags
                HARDWARE.assert_modified_wheel(self.before, self.after, self.samples, flags)

    def test_rejects_wrong_axis_and_direction(self):
        for event_type in ('WHEELLEFTMOUSE', 'WHEELRIGHTMOUSE', 'WHEELDOWNMOUSE'):
            self.event['type'] = event_type
            with self.subTest(event_type=event_type), self.assertRaisesRegex(AssertionError, 'axis or direction'):
                HARDWARE.assert_modified_wheel(self.before, self.after, self.samples, ['shift'])

    def test_rejects_missing_or_stuck_modifier(self):
        for flag in ('shift', 'ctrl', 'alt', 'oskey'):
            with self.subTest(flag=flag):
                self.event[flag] = not self.event[flag]
                with self.assertRaisesRegex(AssertionError, flag):
                    HARDWARE.assert_modified_wheel(self.before, self.after, self.samples, ['shift'])
                self.event[flag] = not self.event[flag]

    def test_missing_os_report_is_invalid_setup(self):
        self.samples[0]['platform']['scroll_events'] = []
        with self.assertRaisesRegex(RuntimeError, 'invalid HID setup'):
            HARDWARE.assert_modified_wheel(self.before, self.after, self.samples, ['shift'])



if __name__ == '__main__':
    unittest.main()
