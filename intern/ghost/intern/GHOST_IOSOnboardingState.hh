/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Platform-neutral decisions for the iOS first-launch gesture guide.
 */

#pragma once

/** Raise this when the guide gains content that people who already finished it should see. */
constexpr int GHOST_IOS_ONBOARDING_VERSION = 1;

/**
 * Show the guide once per #GHOST_IOS_ONBOARDING_VERSION. A launch from the Home Screen has no
 * Blender arguments; launches with arguments are automated (tests, scripts) and skip the guide
 * unless it is \a forced.
 */
inline bool GHOST_IOSOnboarding_shouldPresent(const int completed_version,
                                              const bool has_launch_arguments,
                                              const bool forced)
{
  if (forced) {
    return true;
  }
  if (has_launch_arguments) {
    return false;
  }
  return completed_version < GHOST_IOS_ONBOARDING_VERSION;
}

/** Cursor, navigation, shortcuts, then input and files. */
constexpr int GHOST_IOS_ONBOARDING_PAGE_COUNT = 4;

/** Clamp a page index after a Back or Next step. */
inline int GHOST_IOSOnboarding_stepPage(const int page, const int step)
{
  const int next = page + step;
  if (next < 0) {
    return 0;
  }
  if (next >= GHOST_IOS_ONBOARDING_PAGE_COUNT) {
    return GHOST_IOS_ONBOARDING_PAGE_COUNT - 1;
  }
  return next;
}
