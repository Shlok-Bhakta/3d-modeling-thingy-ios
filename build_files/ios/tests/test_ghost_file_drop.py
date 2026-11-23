#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Files dragged onto a Blender window from other apps reach Blender as dropped paths.

These source checks support the runtime tests: test_file_drop_runtime.py runs the loader with
real item providers, and simulator_file_drop.py drags a file onto the full app through UIKit.
"""

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
GHOST_INTERN = REPOSITORY / "intern" / "ghost" / "intern"
WINDOW_SOURCE = GHOST_INTERN / "GHOST_WindowIOS.mm"
SYSTEM_SOURCE = GHOST_INTERN / "GHOST_SystemIOS.mm"
DROP_SOURCE = GHOST_INTERN / "GHOST_IOSFileDrop.mm"
LOAD_SOURCE = GHOST_INTERN / "GHOST_IOSFileDropLoad.mm"
GHOST_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "ghost_ios.cmake"
IO_UTILS = REPOSITORY / "source" / "blender" / "editors" / "io" / "io_utils.cc"


class GhostFileDropTests(unittest.TestCase):
    def test_drop_handling_lives_in_an_ios_ghost_shim(self) -> None:
        window = WINDOW_SOURCE.read_text()
        cmake = GHOST_CMAKE.read_text()

        self.assertIn("GHOST_IOSFileDrop_install(window->getView(), system, window)", window)
        self.assertIn("GHOST_IOSFileDrop_uninstall(file_drop)", window)
        self.assertIn("[ghost_rootWindow registerFileDrop];", window)
        self.assertNotIn("UIDropInteraction", window)
        for name in ("GHOST_IOSFileDrop.hh", "GHOST_IOSFileDrop.mm", "GHOST_IOSFileDropLoad.mm"):
            self.assertIn(f"intern/{name}", cmake)

    def test_window_close_removes_the_drop_target(self) -> None:
        window = WINDOW_SOURCE.read_text()
        invalidate = window[window.index("- (void)invalidateInput\n{") :]
        invalidate = invalidate[: invalidate.index("\n}\n")]
        self.assertIn("GHOST_IOSFileDrop_uninstall(file_drop);", invalidate)

    def test_any_file_is_accepted_and_delivered_as_dropped_paths(self) -> None:
        drop = DROP_SOURCE.read_text()
        self.assertIn("[[UIDropInteraction alloc] initWithDelegate:self]", drop)
        self.assertIn("hasItemsConformingToTypeIdentifiers:@[ UTTypeData.identifier ]", drop)
        self.assertIn("UIDropOperationCopy", drop)
        self.assertIn("GHOST_kEventDraggingDropDone", drop)
        self.assertIn("GHOST_kDragnDropTypeFilenames", drop)
        # Blender's cursor follows the drag so the editor under it receives the drop.
        self.assertIn("virtualPointer()->warp", drop)

    def test_drop_point_reaches_blender_in_screen_coordinates(self) -> None:
        source = SYSTEM_SOURCE.read_text()
        handler = source[source.index("GHOST_TSuccess GHOST_SystemIOS::handleDraggingEvent") :]
        drop_done = handler[handler.index("case GHOST_kEventDraggingDropDone:") :]
        drop_done = drop_done[: drop_done.index("pushEvent")]
        self.assertIn("clientToScreenIntern(mouseX, mouseY, mouseX, mouseY)", drop_done)

    def test_drop_import_dialog_names_the_file_so_it_fits_the_window(self) -> None:
        # Dropping an OBJ titled its import dialog with the full container path, which made the
        # dialog wider than an iPad and pushed its confirm button off screen.
        source = IO_UTILS.read_text()
        invoke = source[source.index("wmOperatorStatus filesel_drop_import_invoke") :]
        invoke = invoke[: invoke.index("WM_operator_props_dialog_popup")]
        self.assertIn("title = BLI_path_basename(files[0].c_str());", invoke)
        self.assertIn("title = BLI_path_basename(filepath);", invoke)

    def test_files_open_in_place_or_are_kept_in_documents(self) -> None:
        load = LOAD_SOURCE.read_text()
        self.assertIn("loadInPlaceFileRepresentationForTypeIdentifier", load)
        self.assertIn("startAccessingSecurityScopedResource", load)
        self.assertIn('@"Dropped Files"', load)
        self.assertIn("NSDocumentDirectory", load)


if __name__ == "__main__":
    unittest.main()
