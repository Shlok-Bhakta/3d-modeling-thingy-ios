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
        self.before = dict(t=0, distance=10, rotation=[1, 0, 0, 0], pointer=[300, 400])
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

    def test_rejects_rotation_even_when_zoom_changes(self):
        self.after['rotation'] = [.99, .1, 0, 0]
        with self.assertRaisesRegex(AssertionError, 'rotated'):
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


if __name__ == '__main__':
    unittest.main()
