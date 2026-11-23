#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import simulator_file_drop as drop  # noqa: E402


class SimulatorFileDropTests(unittest.TestCase):
    def test_each_mode_imports_an_object_named_after_it(self) -> None:
        self.assertEqual(drop.object_name('in-place'), 'DroppedInPlace')
        self.assertEqual(drop.object_name('copy'), 'DroppedCopy')
        self.assertTrue(drop.fixture('copy').startswith('o DroppedCopy\n'))

    def test_viewport_target_flips_blender_window_coordinates(self) -> None:
        state = dict(width=2000, height=1000, viewport=[0, 200, 1000, 600])
        self.assertEqual(drop.viewport_target(state), [0.3, 0.5])

    def test_drag_holds_long_enough_to_lift_and_ends_on_the_target(self) -> None:
        events = drop.drag_events([.1, .7], [.5, .5])
        self.assertEqual(events[0]['phase'], 1)
        held = 0
        for event in events[1:]:
            if event['points'] != [[.1, .7]]:
                break
            held += event['wait']
        self.assertGreaterEqual(held, 1.0)
        self.assertEqual(events[-1], dict(points=[[.5, .5]], phase=2, wait=.1))

    def test_a_cancelled_drop_fails_even_without_other_problems(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'in-place.obj'
            source.write_text('o DroppedInPlace\n')
            self.assertEqual(drop.evaluate('in-place', 'copy', ['DroppedInPlace'], source, []), [])
            problems = drop.evaluate('in-place', '0', ['Cube'], source, [])
            self.assertEqual(len(problems), 2)
            self.assertIn('operation 0', problems[0])

    def test_in_place_must_not_copy_and_copy_must_keep_exactly_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'copy.obj'
            source.write_text(drop.fixture('copy'))
            kept = folder / 'kept.obj'
            kept.write_text(drop.fixture('copy'))
            self.assertEqual(drop.evaluate('copy', 'copy', ['DroppedCopy'], source, [kept]), [])
            self.assertTrue(drop.evaluate('copy', 'copy', ['DroppedCopy'], source, []))
            kept.write_text('changed')
            self.assertTrue(drop.evaluate('copy', 'copy', ['DroppedCopy'], source, [kept]))
            self.assertTrue(drop.evaluate('in-place', 'copy', ['DroppedInPlace'], source, [kept]))


if __name__ == '__main__':
    unittest.main()
