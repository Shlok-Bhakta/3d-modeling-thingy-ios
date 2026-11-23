#!/usr/bin/env python3

from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
WINDOW_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_WindowIOS.mm"
ACCESS_HEADER = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSFileAccess.hh"
ACCESS_SOURCE = REPOSITORY / "intern" / "ghost" / "intern" / "GHOST_IOSFileAccess.mm"
FILE_MENU_SOURCE = (
    REPOSITORY / "source" / "blender" / "editors" / "space_file" / "fsmenu_system_ios.mm"
)
GHOST_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "ghost_ios.cmake"
PLATFORM_CMAKE = REPOSITORY / "build_files" / "ios" / "cmake" / "platform_ios.cmake"


class GhostFileAccessTests(unittest.TestCase):
    def test_file_access_ui_lives_in_an_ios_ghost_shim(self) -> None:
        window_source = WINDOW_SOURCE.read_text()
        access_source = ACCESS_SOURCE.read_text()
        cmake = GHOST_CMAKE.read_text()

        self.assertIn("GHOST_IOSFileAccess_createControls", window_source)
        self.assertIn("GHOST_IOSFileAccess_destroyControls", window_source)
        self.assertNotIn("UIDocumentPickerViewController", window_source)
        self.assertNotIn("startAccessingSecurityScopedResource", window_source)
        self.assertIn("intern/GHOST_IOSFileAccess.hh", cmake)
        self.assertIn("intern/GHOST_IOSFileAccess.mm", cmake)
        self.assertIn("UIDocumentPickerViewController", access_source)
        self.assertIn("-framework UniformTypeIdentifiers", PLATFORM_CMAKE.read_text())

    def test_control_only_appears_on_the_file_browser_window(self) -> None:
        window_source = WINDOW_SOURCE.read_text()
        access_source = ACCESS_SOURCE.read_text()

        self.assertIn('strcmp(window_title, "Blender File View")', access_source)
        self.assertIn('strcmp(window_title, "File Browser")', access_source)
        self.assertIn('accessibilityIdentifier = @"blender_file_browser_add_location";', access_source)
        self.assertIn('systemImageNamed:@"folder.badge.plus"', access_source)

    def test_window_title_refresh_does_not_destroy_an_open_picker(self) -> None:
        window_source = WINDOW_SOURCE.read_text()
        set_title = window_source[
            window_source.index("void GHOST_WindowIOS::setTitle") : window_source.index(
                "std::string GHOST_WindowIOS::getTitle"
            )
        ]

        self.assertNotIn("updateFileAccessControls", set_title)

    def test_control_is_a_small_circle_immediately_left_of_close(self) -> None:
        access_source = ACCESS_SOURCE.read_text()

        self.assertIn("glassButtonConfiguration", access_source)
        self.assertIn("constraintEqualToConstant:44.0f", access_source)
        # A wider, titled button covers the file browser's search and display controls.
        self.assertNotIn("configuration.title", access_source)
        self.assertIn('accessibilityLabel = @"Add Folder"', access_source)
        self.assertIn("constraintEqualToAnchor:close_button.leadingAnchor", access_source)
        self.assertIn("constraintEqualToAnchor:close_button.centerYAnchor", access_source)

    def test_control_uses_an_explicit_single_directory_access_picker(self) -> None:
        access_source = ACCESS_SOURCE.read_text()

        self.assertIn("initForOpeningContentTypes:@[ UTTypeFolder ]", access_source)
        self.assertIn("asCopy:NO", access_source)
        self.assertIn("allowsMultipleSelection = NO", access_source)

    def test_selection_callback_keeps_the_remote_picker_host_alive(self) -> None:
        access_source = ACCESS_SOURCE.read_text()
        selection = access_source[
            access_source.index("didPickDocumentsAtURLs") : access_source.index(
                "documentPickerWasCancelled"
            )
        ]

        self.assertNotIn("delegate = nil", selection)
        self.assertNotIn("dismissViewControllerAnimated", selection)
        self.assertNotIn("[picker_ release]", selection)

    def test_selection_callback_defers_security_scope_and_bookmark_work(self) -> None:
        file_menu_source = FILE_MENU_SOURCE.read_text()
        observer = file_menu_source[
            file_menu_source.index("didGrantFileLocationAccess") : file_menu_source.index(
                "IOS_ensure_file_location_observer"
            )
        ]

        dispatch = observer.index("dispatch_async(g_file_location_queue")
        self.assertNotIn("IOS_begin_accessing_file_location", observer[:dispatch])
        self.assertIn("IOS_begin_accessing_file_location", observer[dispatch:])

    def test_control_touches_do_not_leak_into_blender(self) -> None:
        window_source = WINDOW_SOURCE.read_text()

        self.assertIn("GHOST_IOSFileAccess_containsView", window_source)

    def test_selected_directories_are_persisted_as_ios_bookmarks(self) -> None:
        file_menu_source = FILE_MENU_SOURCE.read_text()

        self.assertIn("NSURLBookmarkCreationMinimalBookmark", file_menu_source)
        self.assertIn("URLByResolvingBookmarkData", file_menu_source)
        self.assertIn("startAccessingSecurityScopedResource", file_menu_source)
        self.assertIn("stopAccessingSecurityScopedResource", file_menu_source)
        self.assertIn("NSUserDefaults", file_menu_source)

    def test_selected_directories_appear_as_blender_system_bookmarks(self) -> None:
        file_menu_source = FILE_MENU_SOURCE.read_text()

        self.assertIn("FS_CATEGORY_SYSTEM_BOOKMARKS", file_menu_source)
        self.assertIn("GHOST_IOSFileLocationDidGrantAccess", file_menu_source)
        self.assertIn("WM_main_add_notifier", file_menu_source)

    def test_folder_handoff_has_device_diagnostics_without_logging_paths(self) -> None:
        access_source = ACCESS_SOURCE.read_text()
        file_menu_source = FILE_MENU_SOURCE.read_text()

        self.assertIn('"Folder picker delegate entered:', access_source)
        self.assertIn('"Folder picker delegate returning:', access_source)
        self.assertIn('"Folder grant worker started"', file_menu_source)
        self.assertIn('"Security scope request completed:', file_menu_source)
        self.assertIn('"Folder publication completed"', file_menu_source)
        self.assertNotIn("url.path", access_source)
        self.assertNotIn("%{public}@\", url", access_source)


if __name__ == "__main__":
    unittest.main()
