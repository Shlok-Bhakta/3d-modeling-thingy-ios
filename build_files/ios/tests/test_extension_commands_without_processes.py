#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Extension repository commands run without child processes on iOS (issue #64).

The tests run the real ``blender_ext`` commands against a local repository, once with the
desktop child-process transport and once as iOS does, and compare what callers receive.
"""

from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock
import errno
import importlib
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
BL_PKG = REPOSITORY / "scripts" / "addons_core" / "bl_pkg"
PACKAGE = "bl_pkg_under_test"


def load_bl_pkg():
    """Import the add-on's modules without its ``__init__``, which needs ``bpy``."""
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(BL_PKG)]
        sys.modules[PACKAGE] = package
    return importlib.import_module(f"{PACKAGE}.bl_extension_utils")


utils = load_bl_pkg()


def popen_unsupported(*_args, **_kwargs):
    # What iOS CPython's `subprocess.Popen` raises.
    raise OSError(errno.ENOTSUP, "ios does not support processes.")


@contextmanager
def as_ios():
    """Behave like iOS CPython: report the platform and refuse to start processes."""
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(sys, "platform", "ios"))
        stack.enter_context(mock.patch.object(platform, "system", lambda: "iOS"))
        stack.enter_context(mock.patch.object(platform, "machine", lambda: "arm64"))
        stack.enter_context(mock.patch.object(subprocess, "Popen", popen_unsupported))
        yield


def drain(generator, request_exit_after=None):
    """Read a command's messages the way ``CommandBatch.exec_blocking`` does."""
    messages = []
    send = None
    started = time.monotonic()
    while True:
        try:
            messages.extend(generator.send(send))
        except StopIteration:
            return messages
        send = False
        if request_exit_after is not None and time.monotonic() - started > request_exit_after:
            send = True
        if time.monotonic() - started > 60.0:
            raise AssertionError("the command did not finish")


def comparable(messages):
    # Paths to the temporary directories differ between the two runs.
    return [(ty, data) for ty, data in messages if ty not in {"PATH", "PROGRESS"}]


class ExtensionCommandsWithoutProcessesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.remote = self.temp / "remote"
        # Build the repository once with the desktop transport.
        messages = drain(utils.command_output_from_json_0(
            ["dummy-repo", "--repo-dir", str(self.remote), "--package-names", "addon_a,addon_b"],
            use_idle=True, python_args=()))
        self.assertNotIn("FATAL_ERROR", [ty for ty, _ in messages])

    def run_commands(self, local: Path, *, ios: bool):
        remote_url = (self.remote / "index.json").as_uri()
        commands = [
            utils.repo_sync(directory=str(local), remote_name="test", remote_url=remote_url,
                            online_user_agent="", access_token="", timeout=10.0, use_idle=True,
                            force_exit_ok=True, python_args=()),
            utils.pkg_install(directory=str(local), remote_url=remote_url,
                              pkg_id_sequence=["addon_a"], online_user_agent="",
                              blender_version=(5, 2, 0), python_version=(3, 13, 0),
                              access_token="", timeout=10.0, use_cache=False, use_idle=True,
                              python_args=()),
            utils.pkg_uninstall(directory=str(local), pkg_id_sequence=["addon_a"],
                                user_directory="", use_idle=True, python_args=()),
        ]
        with as_ios() if ios else ExitStack():
            return [drain(command) for command in commands]

    def test_ios_runs_sync_install_and_uninstall_like_a_child_process(self) -> None:
        desktop = self.run_commands(self.temp / "desktop", ios=False)
        hook = sys.unraisablehook
        ios = self.run_commands(self.temp / "ios", ios=True)

        self.assertEqual([comparable(m) for m in ios], [comparable(m) for m in desktop])
        for messages in ios:
            self.assertNotIn("FATAL_ERROR", [ty for ty, _ in messages])
        self.assertFalse((self.temp / "ios" / "addon_a").exists())
        self.assertTrue((self.temp / "ios" / ".blender_ext" / "index.json").is_file())
        # `--force-exit-ok` is for child processes, it must not change Blender's own hook.
        self.assertIs(sys.unraisablehook, hook)

    def test_ios_installs_the_package_files(self) -> None:
        local = self.temp / "ios"
        remote_url = (self.remote / "index.json").as_uri()
        with as_ios():
            drain(utils.repo_sync(directory=str(local), remote_name="test", remote_url=remote_url,
                                  online_user_agent="", access_token="", timeout=10.0,
                                  use_idle=False, python_args=()))
            messages = drain(utils.pkg_install(
                directory=str(local), remote_url=remote_url, pkg_id_sequence=["addon_b"],
                online_user_agent="", blender_version=(5, 2, 0), python_version=(3, 13, 0),
                access_token="", timeout=10.0, use_cache=False, use_idle=False, python_args=()))
        self.assertNotIn("FATAL_ERROR", [ty for ty, _ in messages], messages)
        self.assertTrue((local / "addon_b" / "blender_manifest.toml").is_file())
        self.assertTrue((local / "addon_b" / "docs" / "readme.txt").is_file())


class ThreadTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        stack = ExitStack()
        stack.enter_context(as_ios())
        self.addCleanup(stack.close)

    def test_request_exit_stops_a_running_command(self) -> None:
        started = time.monotonic()
        messages = drain(utils.command_output_from_json_0(
            ["dummy-progress", "--time-duration", "30", "--time-delay", "0.01"],
            use_idle=True, python_args=()), request_exit_after=0.3)
        self.assertLess(time.monotonic() - started, 10.0)
        self.assertEqual(messages[-1], ("DONE", ""))
        progress = [data for ty, data in messages if ty == "PROGRESS"]
        self.assertTrue(progress)
        # Messages arrive as JSON would decode them: lists, not tuples.
        self.assertEqual(progress[0], ["Demo", "BYTE", 0, 100])

    def test_a_crashing_command_reports_a_fatal_error_and_ends(self) -> None:
        messages = drain(utils.command_output_from_json_0(
            ["no-such-command"], use_idle=False, python_args=()))
        self.assertEqual([ty for ty, _ in messages], ["FATAL_ERROR"])
        self.assertIn("SystemExit", messages[0][1])

    def test_commands_run_concurrently(self) -> None:
        # The Preferences refresh every repository at once, each command on its own thread.
        generators = [utils.command_output_from_json_0(
            ["dummy-progress", "--time-duration", "0", "--time-delay", "0.01",
             "--steps-limit", "20"], use_idle=False, python_args=()) for _ in range(3)]
        done = [False] * len(generators)
        started = [False] * len(generators)
        deadline = time.monotonic() + 30.0
        while not all(done):
            self.assertLess(time.monotonic(), deadline)
            for index, generator in enumerate(generators):
                if done[index]:
                    continue
                try:
                    generator.send(False if started[index] else None)
                    started[index] = True
                except StopIteration:
                    done[index] = True
            time.sleep(0.005)


if __name__ == "__main__":
    unittest.main()
