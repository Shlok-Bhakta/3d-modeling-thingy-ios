---
title: What doesn't work
description: Missing features, add-on limits, and things we haven't tested on iPhone and iPad.
---

3D Modeling Thingy includes most Blender features, but some desktop workflows
need features that iOS does not support.
These are the limits to check before you bring a project or buy an add-on.

## Missing features

| Feature | What that means for your project |
| --- | --- |
| Open Shading Language, or OSL | Custom OSL shaders and OSL Script nodes won't work. Use Blender's other shader nodes instead. |
| Hydra rendering | Blender's Hydra render integration is disabled. This is separate from USD file import and export. |
| VR through OpenXR | You can't use Blender's VR session features in this app. |
| SpaceMouse and other NDOF controllers | Blender's dedicated support for these controllers is disabled. Ordinary mouse and keyboard input is available. |
| Separate Python processes | Scripts can't launch command-line tools, helper apps, or background Blender processes. Add-ons that use `subprocess` or `multiprocessing.Process` need changes. |

## USD and OpenVDB are included

The current release includes USD import and export, OpenVDB, Embree, and Cycles
path guiding.

Hydra is the part of the USD-related tooling that is disabled. You don't need
Hydra to import or export a USD file.

Included doesn't mean every workflow has been checked on a device. We haven't
tested every USD round trip, volume setup, or simulation. Keep your original
project and check a copy before relying on the result.

## Add-ons and extensions

Add-on support depends on what the add-on needs and how it's packaged.
We don't yet have a tested list of third-party add-ons.

### Python-only legacy add-ons

An add-on written entirely in Python is the best candidate, provided it supports
Blender 5.2 and only needs features available in this app. The legacy
installer copies Python files into its add-ons folder without launching another
program. That path is present, but we haven't verified a third-party add-on
through installation, use, and relaunch on a device.

To try a legacy add-on:

1. Save its `.py` or `.zip` file somewhere the app can read.
   If needed, [add its folder](/3d-modeling-thingy-ios/workflow/files-and-windows/#add-an-external-folder)
   in the app's file browser.
2. Open **Edit > Preferences > Add-ons**.
3. Open the menu at the top right and choose **Install from Disk**.
4. Select the file, then enable the add-on if it isn't enabled automatically.
5. Try its tools on a copy of your project and check that it still works after
   restarting the app.

Keep ZIP packages zipped. An extension ZIP and a legacy add-on ZIP are different
formats; changing the filename won't convert one into the other.
Blender's [add-on installation guide](https://docs.blender.org/manual/en/5.0/editors/preferences/addons.html)
explains the legacy format.

### The Extensions installer is unsupported

The current Extensions installer calls a separate Python process for package
operations. iOS doesn't support that path. This affects packages installed
through **Get Extensions** and extension-format ZIP files installed from disk.

Some background download work has been adapted for iOS, but that doesn't fix
the package installer. Treat extension installation and updates as unsupported
in this release, even if the package itself contains only Python.

### Add-ons with desktop dependencies

These won't work unchanged:

- Add-ons that load Windows, Linux, or macOS binaries. A macOS build for
  Apple silicon is still a macOS build, not an iOS build.
- Add-ons that download compiled Python libraries and try to load them.
  Native libraries need to be built for iOS, bundled with the app, and signed.
- Add-ons that run an external renderer, converter, helper service, or another
  copy of Blender.
- Add-ons that require OSL, Hydra, or another missing feature.

The app already includes Python 3.13, NumPy, and zstandard. That helps add-ons
that use those libraries, but it doesn't make their other dependencies available.

## Rendering and large scenes

Cycles CPU rendering is available, but long renders can be slow and heat up
the device. Cycles Metal needs compatible GPU hardware; it won't be available
on every device.

iOS can close the app when a scene uses too much memory. Large textures,
dense meshes, simulations, and rendered viewport shading all add to that load.
Save before starting a long render and keep a backup outside the app.

## Files and app installation

The app can use its own storage and files or folders you've granted access to.
It can't freely browse the whole device like a desktop file system. A moved
folder or a change in cloud-provider access may need
[a new folder grant](/3d-modeling-thingy-ios/workflow/files-and-windows/#add-an-external-folder).

Deleting the app can delete projects stored inside it. Signing it with a
different account or tool can also change where its data lives.
Copy important files elsewhere before replacing an installation.

Free Apple Account signing expires after seven days unless the app is refreshed.
We still haven't verified a complete free-account SideStore install and refresh
on a physical device.

## What still needs device testing

We don't have broad coverage of third-party add-ons, external displays,
cloud file providers, or every iPad window arrangement. There also isn't
support for restoring several independent app sessions.

If something fails, [report it](https://github.com/Shlok-Bhakta/3d-modeling-thingy-ios/issues)
with your device, iOS version, and the steps that caused it. For an add-on,
include its name and version too.

The feature list above comes from the release's
[iOS build settings](https://github.com/Shlok-Bhakta/3d-modeling-thingy-ios/blob/ios-v5.2.1/build_files/cmake/config/blender_ios_features.cmake).
The extension installer limitation comes from its
[package command runner](https://github.com/Shlok-Bhakta/3d-modeling-thingy-ios/blob/ios-v5.2.1/scripts/addons_core/bl_pkg/bl_extension_utils.py).
