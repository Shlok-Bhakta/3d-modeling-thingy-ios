/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

#pragma once

#include "GHOST_Buttons.hh"
#include "GHOST_IOSVirtualPointerState.hh"
#include "GHOST_Types.hh"

#include <memory>

class GHOST_SystemIOS;
class GHOST_WindowIOS;

/** UIKit/GHOST adapter for the shared virtual pointer state. */
class GHOST_IOSVirtualPointer {
 public:
  explicit GHOST_IOSVirtualPointer(GHOST_SystemIOS *system);
  ~GHOST_IOSVirtualPointer();

  void attachWindow(GHOST_WindowIOS *window);
  void detachWindow(GHOST_WindowIOS *window);

  void beginRelative(double finger_x, double finger_y);
  void beginRelativeAtTime(double finger_x, double finger_y, double timestamp_seconds);
  void moveRelativeTo(double finger_x,
                      double finger_y,
                      const GHOST_TabletData &tablet = GHOST_TABLET_DATA_NONE);
  void moveRelativeToAtTime(double finger_x,
                            double finger_y,
                            double timestamp_seconds,
                            const GHOST_TabletData &tablet = GHOST_TABLET_DATA_NONE);
  void endRelative();

  void moveAbsolute(double x,
                    double y,
                    GHOST_IOSPointerSource source,
                    const GHOST_TabletData &tablet = GHOST_TABLET_DATA_NONE);
  void warp(double x, double y);
  void setSource(GHOST_IOSPointerSource source);

  void button(GHOST_TButton button,
              bool down,
              const GHOST_TabletData &tablet = GHOST_TABLET_DATA_NONE);
  void click(GHOST_TButton button,
             const GHOST_TabletData &tablet = GHOST_TABLET_DATA_NONE);
  void clearButtons();
  void getButtons(GHOST_Buttons &buttons) const;
  /** UIKit's primary/secondary/middle bits, independent of touch and Pencil holds. */
  void hardwareButtons(unsigned int mask);
  bool hasHardwareMouse() const;
  bool usesHardwareMouse() const;
  bool usesRelativeMouse() const;
  bool wantsPointerLock() const;

  void getClientPosition(double &x, double &y) const;
  GHOST_TSuccess getCursorPosition(int32_t &screen_x, int32_t &screen_y) const;
  void setBlenderVisibility(bool visible);
  void setGrabMode(GHOST_TGrabCursorMode mode);

 private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};
