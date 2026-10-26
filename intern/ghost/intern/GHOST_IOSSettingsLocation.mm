/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Location of Blender's user settings inside the app's Files-visible documents.
 */

#import <Foundation/Foundation.h>
#import <os/log.h>

#include "GHOST_IOSSettingsLocation.hh"

static NSString *const IOS_settings_folder_name = @"Settings";
static NSString *const IOS_settings_readme_name = @"README.txt";

static NSString *const IOS_settings_readme =
    @"3D Modeling Thingy settings\n"
     "\n"
     "This folder holds the app's Blender preferences, add-ons and other user files, with one\n"
     "folder for each Blender version, such as 5.2:\n"
     "\n"
     "  5.2/config       Preferences (userpref.blend), the startup file, bookmarks and recent files\n"
     "  5.2/scripts      Add-ons, presets and startup scripts\n"
     "  5.2/extensions   Extensions\n"
     "  5.2/datafiles    Extra data files such as fonts\n"
     "\n"
     "Bring settings from Blender on a computer\n"
     "\n"
     "1. Close the app from the app switcher, so it can't save over the files you copy.\n"
     "2. Copy the version folder from the computer into this folder:\n"
     "     Mac:      ~/Library/Application Support/Blender/\n"
     "     Windows:  %APPDATA%\\Blender Foundation\\Blender\\\n"
     "     Linux:    ~/.config/blender/\n"
     "3. If the folder has the same version as the app, replace the existing one.\n"
     "   If it's an older version, rename or remove the app's own version folder,\n"
     "   then open the app and choose Load <version> Settings on the splash screen.\n"
     "\n"
     "Preferences from a computer use desktop interface sizes. If everything looks\n"
     "too small, raise Resolution Scale in Edit > Preferences > Interface.\n"
     "\n"
     "Updates\n"
     "\n"
     "When the app moves to a newer Blender version it creates a new version folder\n"
     "and offers to Load your previous settings on the splash screen. Older version\n"
     "folders stay here until you delete them.\n";

static os_log_t IOS_settings_log()
{
  static os_log_t log = os_log_create("org.blender.ios", "settings");
  return log;
}

static bool IOS_is_directory(NSFileManager *file_manager, NSURL *url)
{
  BOOL is_directory = NO;
  return [file_manager fileExistsAtPath:url.path isDirectory:&is_directory] && is_directory;
}

static void IOS_write_readme(NSFileManager *file_manager, NSURL *root_url)
{
  NSURL *readme_url = [root_url URLByAppendingPathComponent:IOS_settings_readme_name
                                                isDirectory:NO];
  if ([file_manager fileExistsAtPath:readme_url.path]) {
    return;
  }
  NSError *error = nil;
  if (![IOS_settings_readme writeToURL:readme_url
                            atomically:YES
                              encoding:NSUTF8StringEncoding
                                 error:&error])
  {
    os_log_error(IOS_settings_log(),
                 "Could not write the settings README: %{public}@",
                 error.localizedDescription);
  }
}

NSURL *GHOST_IOSSettings_prepareRoot(NSURL *documents_url, NSURL *legacy_root_url)
{
  if (documents_url == nil) {
    return legacy_root_url;
  }

  NSFileManager *file_manager = [NSFileManager defaultManager];
  NSURL *settings_url = [documents_url URLByAppendingPathComponent:IOS_settings_folder_name
                                                       isDirectory:YES];

  if (!IOS_is_directory(file_manager, settings_url) && legacy_root_url != nil &&
      IOS_is_directory(file_manager, legacy_root_url))
  {
    /* Both folders are in the app container, so this is a rename rather than a copy. */
    NSError *error = nil;
    if (![file_manager moveItemAtURL:legacy_root_url toURL:settings_url error:&error]) {
      os_log_error(IOS_settings_log(),
                   "Keeping settings in Application Support, the move failed: %{public}@",
                   error.localizedDescription);
      return legacy_root_url;
    }
    os_log_info(IOS_settings_log(), "Moved settings into Documents/Settings");
  }

  NSError *error = nil;
  if (![file_manager createDirectoryAtURL:settings_url
              withIntermediateDirectories:YES
                               attributes:nil
                                    error:&error])
  {
    os_log_error(IOS_settings_log(),
                 "Could not create Documents/Settings: %{public}@",
                 error.localizedDescription);
    return IOS_is_directory(file_manager, legacy_root_url) ? legacy_root_url : settings_url;
  }

  IOS_write_readme(file_manager, settings_url);
  return settings_url;
}
