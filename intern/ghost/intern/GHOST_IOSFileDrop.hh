/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Accept files dragged onto a Blender window from other apps.
 */

#pragma once

#ifdef __OBJC__

@class NSArray<ObjectType>;
@class NSItemProvider;
@class NSObject;
@class NSString;
@class NSURL;
@class UIView;

class GHOST_SystemIOS;
class GHOST_WindowIOS;

/** Make `view` accept file drops and deliver them to Blender as dropped file paths. */
NSObject *GHOST_IOSFileDrop_install(UIView *view, GHOST_SystemIOS *system, GHOST_WindowIOS *window);
void GHOST_IOSFileDrop_uninstall(NSObject *drop);

/** Where copies of dropped files are kept: "Dropped Files" in the app's Documents. */
NSURL *GHOST_IOSFileDrop_inbox();

/**
 * Turn dropped items into local paths Blender can read, in drop order.
 *
 * A file the source offers in place keeps its location, so paths relative to it still resolve.
 * Anything else is copied into `inbox` first, because UIKit deletes its temporary copy as soon
 * as the load returns. Items that are not files are skipped. Provider I/O stays off the main
 * thread; `completion` runs on the main queue.
 */
void GHOST_IOSFileDrop_loadFiles(NSArray<NSItemProvider *> *providers,
                                 NSURL *inbox,
                                 void (^completion)(NSArray<NSString *> *paths));

#endif
