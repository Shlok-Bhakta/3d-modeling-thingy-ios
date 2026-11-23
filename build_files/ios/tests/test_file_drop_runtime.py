#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile and run the actual iOS drop loader with real item providers and files."""
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[3]


@unittest.skipUnless(platform.system() == 'Darwin', 'requires Apple Foundation')
class FileDropRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='blender-file-drop-runtime-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.executable = cls.root / 'file-drop-runtime'
        command = ['xcrun', '--sdk', 'macosx', 'clang++', '-std=c++17', '-Wall', '-Werror',
                   '-framework', 'Foundation', '-framework', 'UniformTypeIdentifiers',
                   '-I', str(REPOSITORY / 'intern' / 'ghost' / 'intern'),
                   str(Path(__file__).with_name('file_drop_runtime.mm')),
                   '-o', str(cls.executable)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def run_case(self, case):
        folder = self.root / case
        folder.mkdir()
        result = subprocess.run([str(self.executable), case, str(folder)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS:', result.stdout)

    def test_a_file_offered_in_place_keeps_its_path(self):
        self.run_case('in-place')

    def test_a_temporary_copy_is_kept_under_an_unused_name(self):
        self.run_case('copy')

    def test_files_keep_drop_order_and_folders_are_skipped(self):
        self.run_case('mixed')

    def test_a_slow_provider_does_not_block_the_main_thread(self):
        self.run_case('slow')


if __name__ == '__main__':
    unittest.main()
