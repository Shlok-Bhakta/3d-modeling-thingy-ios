#!/usr/bin/env python3

"""Unit coverage for the pure parts of the Extensions simulator harness."""

from pathlib import Path
import importlib.util
import sys
import unittest


IOS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("simulator_extensions", IOS / "simulator_extensions.py")
harness = importlib.util.module_from_spec(spec)
sys.modules["simulator_extensions"] = harness
spec.loader.exec_module(harness)


def passing_report() -> dict:
    return {
        "steps": {
            "sync": {"finished": True},
            "install": {"finished": True, "enabled": True, "pkg_id": "tiny_addon"},
            "uninstall": {"finished": True},
        },
        "errors": [],
        "locked_at_end": False,
    }


class ExtensionsHarnessTests(unittest.TestCase):
    def test_a_clean_run_passes(self) -> None:
        self.assertEqual(harness.validate(passing_report(), "Read prefs\n"), [])

    def test_issue_64_failure_is_reported(self) -> None:
        # What main produced before the fix: sync never finished and stayed locked.
        report = {"steps": {"sync": {"finished": False, "locked": True}}, "errors": []}
        logs = ("Traceback (most recent call last):\n"
                "OSError: [Errno 45] ios does not support processes.\n")
        failures = harness.validate(report, logs)
        self.assertEqual(len(failures), 5, failures)
        self.assertIn("sync did not finish (locked: True)", failures)

    def test_an_add_on_that_is_not_enabled_fails(self) -> None:
        report = passing_report()
        report["steps"]["install"]["enabled"] = False
        self.assertEqual(harness.validate(report, ""),
                         ["tiny_addon installed but was not enabled"])

    def test_a_lock_left_behind_or_harness_error_fails(self) -> None:
        report = passing_report()
        report["locked_at_end"] = True
        report["errors"] = ["Traceback ...\nRuntimeError: no repository\n"]
        self.assertEqual(len(harness.validate(report, "")), 2)

    def test_the_expression_compiles(self) -> None:
        compile(harness.EXTENSIONS_EXPR, "<extensions>", "exec")


if __name__ == "__main__":
    unittest.main()
