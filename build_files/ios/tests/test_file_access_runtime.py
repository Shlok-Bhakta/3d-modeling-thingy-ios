#!/usr/bin/env python3
"""Compile and run the actual iOS Foundation shim, including provider stalls."""
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[3]


@unittest.skipUnless(platform.system() == 'Darwin', 'requires Apple Foundation')
class FileAccessRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='blender-file-access-runtime-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.executable = cls.root / 'file-access-runtime'
        fmt = Path(os.environ.get('FMT_INCLUDE_DIR', REPOSITORY / 'lib/macos_arm64/fmt/include'))
        if not (fmt / 'fmt/ranges.h').exists():
            raise RuntimeError('set FMT_INCLUDE_DIR to the dependency prefix containing fmt/ranges.h')
        includes = ['source/blender/blenlib', 'source/blender/makesdna',
                    'source/blender/editors/include', 'source/blender/blentranslation',
                    'source/blender/windowmanager', 'source/blender/blenkernel',
                    'source/blender/makesrna', 'intern/guardedalloc', 'intern/atomic']
        command = ['xcrun', '--sdk', 'macosx', 'clang++', '-std=c++20', '-funsigned-char',
                   '-DNDEBUG', '-framework', 'Foundation', '-I', str(fmt)]
        for include in includes:
            command.extend(['-I', str(REPOSITORY / include)])
        command.extend([str(Path(__file__).with_name('file_access_runtime.mm')),
                        '-o', str(cls.executable)])
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

    def test_slow_selection_keeps_main_thread_free_and_persists_repeated_grants(self):
        self.run_case('select')

    def test_slow_restore_keeps_main_thread_free_and_tolerates_bad_bookmarks(self):
        self.run_case('restore')

    def test_a_picked_file_is_not_added_as_a_folder(self):
        self.run_case('file')


if __name__ == '__main__':
    unittest.main()
