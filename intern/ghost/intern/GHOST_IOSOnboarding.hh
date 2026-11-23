/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * First-launch guide to the iPad gestures, Pencil and on-screen keys.
 */

#pragma once

#ifdef __OBJC__

@class UIViewController;

/**
 * Present the guide over \a root once, as soon as \a root is on screen with nothing else
 * presented. Finishing or skipping it is remembered in user defaults. Launches with Blender
 * arguments are automated and skip it, unless the `BLENDER_IOS_ONBOARDING=1` environment
 * variable forces it.
 */
void GHOST_IOSOnboarding_presentIfNeeded(UIViewController *root);

#endif
