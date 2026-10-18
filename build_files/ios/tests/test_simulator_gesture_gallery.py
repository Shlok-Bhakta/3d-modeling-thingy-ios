# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'gesture_gallery', Path(__file__).resolve().parents[1] / 'simulator_gesture_gallery.py')
gallery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gallery)


class GestureGalleryTests(unittest.TestCase):
    def test_replay_preserves_three_contacts_and_releases_them(self):
        points = [[.2, .4], [.3, .4], [.4, .4]]
        events = gallery.replay_events([
            dict(t=.6, phase=1, points=points),
            dict(t=.9, phase=6, points=points),
            dict(t=1.1, phase=2, points=points),
        ])
        self.assertEqual([3, 3, 3], [len(e['points']) for e in events])
        self.assertEqual(2, events[-1]['phase'])
        self.assertAlmostEqual(1.1, sum(e['wait'] for e in events))

    def test_invalid_sequences_fail_before_sending_input(self):
        for events in (
            [dict(t=.4, phase=1, points=[[.2, .2]]), dict(t=.3, phase=2, points=[[.2, .2]])],
            [dict(t=.4, phase=1, points=[])],
            [dict(t=.4, phase=1, points=[[1.1, .2]])],
            [dict(t=.4, phase=3, points=[[.2, .2]])],
            [dict(t=.4, phase=1, points=[[.2, .2]])],
            [dict(t=.4, phase=2, points=[[.2, .2]])],
            [dict(t=float('nan'), phase=1, points=[[.2, .2]])],
        ):
            with self.subTest(events=events), self.assertRaises(ValueError):
                gallery.replay_events(events)

    def test_pan_requires_view_movement_without_object_movement(self):
        before = dict(t=1, view_location=[0, 0, 0], location=[0, 0, 0])
        expected = dict(changed=['view_location'], unchanged=['location'])
        with self.assertRaises(AssertionError):
            gallery.assert_outcome(before, dict(before, t=2), expected)
        with self.assertRaises(AssertionError):
            gallery.assert_outcome(before, dict(t=2, view_location=[1, 0, 0], location=[1, 0, 0]), expected)
        gallery.assert_outcome(before, dict(t=2, view_location=[1, 0, 0], location=[0, 0, 0]), expected)

    def test_stale_main_loop_cannot_pass(self):
        with self.assertRaises(AssertionError):
            gallery.assert_outcome(dict(t=1), dict(t=1), {})

    def test_wrap_requires_reaching_the_opposite_edge(self):
        before = dict(t=1, pointer=[980, 400], width=1000, height=800)
        after = dict(before, t=2, pointer=[100, 400])
        gallery.assert_outcome(before, after, dict(wrap='x'))
        with self.assertRaises(AssertionError):
            gallery.assert_outcome(before, dict(after, pointer=[900, 400]), dict(wrap='x'))


if __name__ == '__main__':
    unittest.main()
