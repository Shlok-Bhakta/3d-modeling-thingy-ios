---
title: Files and windows
description: Open projects, allow access to folders, and close extra windows.
---

## Where your files live

Look under **On My iPhone** or **On My iPad** in Files for the app's
local documents. Files kept inside the app can be lost when you delete it.
Keep another copy of important projects before replacing a sideloaded build.

## Settings, add-ons, and extensions

Your preferences live in the **Settings** folder inside the app's folder in
Files. There's one folder for each Blender version, laid out the same way as
desktop Blender:

| Folder | Contents |
| --- | --- |
| `5.2/config` | Preferences (`userpref.blend`), the startup file, bookmarks, and recent files |
| `5.2/scripts` | Add-ons, presets, and startup scripts |
| `5.2/extensions` | Extensions |
| `5.2/datafiles` | Extra data files, such as fonts |

The preferences file appears after you tap **Continue** in Quick Setup or
change a preference.

To bring your settings from a computer:

1. Close the app from the app switcher, so it can't save over the files.
2. Copy the version folder from your computer into **Settings**. On a Mac it's
   in `~/Library/Application Support/Blender/`. On Windows it's in
   `%APPDATA%\Blender Foundation\Blender\`, and on Linux in `~/.config/blender/`.
3. If it's the same version as the app, replace the app's folder. If it's an
   older version, delete or rename the app's own version folder first. Then
   open the app and choose **Load 5.1 Settings** on the splash screen, with
   your folder's version number.

Desktop preferences use desktop interface sizes. If everything looks too small,
raise **Resolution Scale** in **Edit > Preferences > Interface**.

When the app updates to a newer Blender version, it creates a new version
folder and offers to load your previous settings. Delete old version folders
when you no longer need them. See [Add-ons and extensions](/3d-modeling-thingy-ios/limitations/#add-ons-and-extensions)
for what can run on iPhone and iPad.

## Open a project

In Files, select a `.blend` file and choose **3D Modeling Thingy** from the share
or Open In menu. You can also use **File > Open** inside the app.

## Add an external folder

The app needs your permission before it can use a folder outside its own
storage.

1. Open the app's file browser.
2. Tap the folder-plus button beside the close button.
3. Choose a folder in Files and tap **Open**.
4. Look under **System** in the app's file browser for that folder.

The app remembers the folder after you close the app. Adding it again shouldn't
create a duplicate. Cloud providers can take a moment to respond, so wait for
the Files picker to finish.

![The folder access button beside the close button in the app's file browser](/3d-modeling-thingy-ios/files/external-folder.webp)

### Open a project from a network share

This walkthrough starts in the app, grants access to a Samba share through
Files, and opens a project from that folder.

<video controls playsinline preload="metadata" poster="/3d-modeling-thingy-ios/files/external-folder.webp">
  <source src="/3d-modeling-thingy-ios/files/network-share.mp4" type="video/mp4" />
</video>

If a folder stops opening, add it again. This can happen after moving it,
changing its permissions, or signing the app with a different account.

## Close a window

The file browser, render display, and Preferences can open in separate
windows. Close one with the round button at the top right, or press
`Command-W` on a keyboard.
