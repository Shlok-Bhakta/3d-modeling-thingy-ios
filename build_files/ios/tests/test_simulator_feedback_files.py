#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Unit coverage for the pure parts of the TestFlight file-report harness."""

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "simulator_feedback_files.py"
SPEC = importlib.util.spec_from_file_location("simulator_feedback_files", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BlendHeaderTests(unittest.TestCase):
    def test_compressed_files_report_their_codec(self):
        self.assertEqual(MODULE.parse_blend_header(b"\x28\xb5\x2f\xfd\xa0\x41"), {"compression": "zstd"})
        self.assertEqual(MODULE.parse_blend_header(b"\x1f\x8b\x08\x00"), {"compression": "gzip"})

    def test_blender_5_header_reports_format_and_version(self):
        header = MODULE.parse_blend_header(b"BLENDER17-01v0503REND")
        self.assertEqual(header["format"], 1)
        self.assertEqual(header["version"], 503)
        self.assertEqual(header["endian"], "little")
        self.assertEqual(header["header_size"], 17)

    def test_legacy_header_reports_pointer_size(self):
        header = MODULE.parse_blend_header(b"BLENDER-v405REND")
        self.assertEqual((header["format"], header["pointer_size"], header["version"]), (0, 8, 405))
        self.assertEqual(MODULE.parse_blend_header(b"BLENDER_V279")["pointer_size"], 4)
        self.assertEqual(MODULE.parse_blend_header(b"BLENDER_V279")["endian"], "big")

    def test_non_blend_data_is_rejected(self):
        for data in (b"PK\x03\x04", b"BLENDERXYZ"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                MODULE.parse_blend_header(data)


class HostLoadTests(unittest.TestCase):
    OLD_HOST = ("Blender 4.4.3 (hash 802179c51ccc built 2025-04-29 14:25:11)\n"
                "Error: Cannot read blend file '/x.blend', incomplete header, "
                "may be from a newer version of Blender\n")

    def test_pre_5_reader_failure_is_classified_as_header_format(self):
        self.assertEqual(MODULE.classify_host_load(self.OLD_HOST), "newer-header-unsupported")
        self.assertEqual(MODULE.host_version(self.OLD_HOST), (4, 4, 3))

    def test_successful_load_requires_the_loader_marker(self):
        loaded = "Warning: File written by newer Blender binary\nFEEDBACK-LOADED 5.2.4 LTS ['Cube']\n"
        self.assertEqual(MODULE.classify_host_load(loaded), "loaded")
        self.assertEqual(MODULE.classify_host_load("Blender 5.2.4\nTraceback ..."), "failed")

    def test_version_is_absent_when_output_has_none(self):
        self.assertIsNone(MODULE.host_version("FEEDBACK-LOADED"))


class MainLoopTests(unittest.TestCase):
    def test_longest_gap_ignores_repeated_samples(self):
        times = [10.0, 10.0, 10.2, 10.4, 20.6, 20.6, 20.8]
        self.assertEqual(MODULE.longest_gap(times), (20.6 - 10.4, 10.4))

    def test_longest_gap_of_too_few_ticks_is_zero(self):
        self.assertEqual(MODULE.longest_gap([]), (0.0, 0.0))
        self.assertEqual(MODULE.longest_gap([3.0, 3.0]), (0.0, 3.0))

    def test_render_stall_and_stuck_window_are_both_reported(self):
        self.assertEqual(MODULE.evaluate_render("CYCLES", 0.4, True), [])
        problems = MODULE.evaluate_render("BLENDER_EEVEE", 10.2, False)
        self.assertEqual(len(problems), 2)
        self.assertIn("stalled 10.2 s", problems[0])
        self.assertIn("did not close", problems[1])


class FakeStateSession(MODULE.Session):
    """Session whose state comes from a scripted sequence instead of the simulator."""

    def __init__(self, states):
        self.states = list(states)
        self.springboard_before = MODULE.springboard_reports()

    def state(self):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


class TickWaitTests(unittest.TestCase):
    def test_leftover_state_from_terminated_process_is_ignored(self):
        old = {"pid": 1, "ticks": 600}
        states = [{}, old, old, {"pid": 2, "ticks": 4}, {"pid": 2, "ticks": 10}]
        self.assertEqual(FakeStateSession(states).wait_ticks(10, timeout=5, stale_pid=1)["pid"], 2)

    def test_stalled_process_times_out(self):
        stalled = {"pid": 2, "ticks": 50}
        with self.assertRaisesRegex(MODULE.FeedbackFailure, "did not tick"):
            FakeStateSession([stalled]).wait_ticks(5, timeout=0.5)


class DocumentOpenTests(unittest.TestCase):
    EXPECTED = Path("/files/BlenderFeedback/shared-from-discord.blend")

    def test_open_in_place_and_inbox_copies_pass(self):
        for path in ("/files/BlenderFeedback/shared-from-discord.blend",
                     "/app/Documents/Inbox/shared-from-discord-1.blend"):
            with self.subTest(path=path):
                self.assertEqual(MODULE.evaluate_document_open(
                    {"pid": 7}, {"pid": 7, "filepath": path}, self.EXPECTED, "warm"), [])

    def test_crash_relaunch_or_missing_document_fails(self):
        self.assertIn("never reported", MODULE.evaluate_document_open({}, {}, self.EXPECTED, "cold")[0])
        relaunched = MODULE.evaluate_document_open(
            {"pid": 7}, {"pid": 9, "filepath": str(self.EXPECTED)}, self.EXPECTED, "warm")
        self.assertIn("process changed", relaunched[0])
        untitled = MODULE.evaluate_document_open({"pid": 7}, {"pid": 7, "filepath": ""},
                                                 self.EXPECTED, "warm")
        self.assertIn("expected shared-from-discord.blend", untitled[0])


class PickerTests(unittest.TestCase):
    BLEND = Path("/files/BlenderFeedback/shared-from-discord.blend")
    FBX = Path("/files/BlenderFeedback/cube.fbx")

    def test_grayed_import_type_and_file_as_folder_are_reported(self):
        problems = MODULE.evaluate_picker(["/app/Documents/"],
                                          ["/app/Documents/", str(self.BLEND) + "/"],
                                          self.FBX, self.BLEND)
        self.assertEqual(len(problems), 2)
        self.assertIn(".fbx", problems[0])
        self.assertIn("listed it as a folder", problems[1])

    def test_selectable_import_type_and_folder_only_bookmarks_pass(self):
        self.assertEqual(MODULE.evaluate_picker([str(self.FBX)], ["/files/BlenderFeedback/"],
                                                self.FBX, self.BLEND), [])

    def test_picker_flow_taps_the_native_button_then_one_item(self):
        flow = MODULE.picker_flow("66%,36%", "picker")
        self.assertLess(flow.index(MODULE.ADD_LOCATION_BUTTON_ID), flow.index("66%,36%"))
        self.assertIn("visible: Cancel", flow)
        self.assertIn("takeScreenshot: picker-after-tap", flow)


class FlowAndProbeTests(unittest.TestCase):
    def test_files_flow_browses_to_folder_before_document(self):
        flow = MODULE.files_open_flow("23%,10%", "37%,10%")
        self.assertLess(flow.index("Browse"), flow.index("On My iPad"))
        self.assertLess(flow.index("23%,10%"), flow.index("37%,10%"))

    def test_close_flow_waits_for_native_button_to_disappear(self):
        flow = MODULE.close_flow()
        self.assertIn(f"id: {MODULE.CLOSE_BUTTON_ID}", flow)
        self.assertIn("notVisible", flow)

    def test_probe_and_context_snippets_are_valid_python(self):
        compile(MODULE.PROBE_SOURCE, "probe", "exec")
        compile(MODULE.VIEW3D_CONTEXT, "view3d", "exec")
        compile(MODULE.FILE_BROWSER_CONTEXT, "file_browser", "exec")

    def test_probe_survives_file_loads(self):
        self.assertIn("persistent=True", MODULE.PROBE_SOURCE)

    def test_version_dir_and_file_url(self):
        self.assertEqual(MODULE.version_dir("5.3.0"), "5.3")
        self.assertEqual(MODULE.file_url(Path("/tmp/a b.blend")).split(":", 1)[0], "file")
        self.assertIn("a%20b.blend", MODULE.file_url(Path("/tmp/a b.blend")))


if __name__ == "__main__":
    unittest.main()
