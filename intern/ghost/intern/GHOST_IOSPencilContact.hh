/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Platform-neutral Apple Pencil contact state.
 */

#pragma once

/**
 * Tracks where the Pencil tip is while it touches the screen.
 *
 * On iPads with Pencil hover, UIKit can report a hover location while the tip is down or as it
 * lifts. That location is the last hover point, which is where the stroke started. Hover must not
 * move the cursor until both the touch and the stroke have ended, and the stroke must end at the
 * tip's last real location.
 */
class GHOST_IOSPencilContact {
 public:
  void touchBegan(const double x, const double y)
  {
    touching_ = true;
    setPoint(x, y);
  }

  void touchMoved(const double x, const double y)
  {
    if (touching_) {
      setPoint(x, y);
    }
  }

  void touchEnded(const double x, const double y)
  {
    if (touching_) {
      setPoint(x, y);
    }
    touching_ = false;
  }

  void strokeBegan()
  {
    stroking_ = true;
  }

  /** The drag recognizer's current location, which is as fresh as the last touch update. */
  void strokeMoved(const double x, const double y)
  {
    if (stroking_) {
      setPoint(x, y);
    }
  }

  void strokeEnded()
  {
    stroking_ = false;
  }

  void reset()
  {
    touching_ = false;
    stroking_ = false;
    has_point_ = false;
  }

  bool acceptsHover() const
  {
    return !touching_ && !stroking_;
  }

  bool hasPoint() const
  {
    return has_point_;
  }

  double x() const
  {
    return x_;
  }

  double y() const
  {
    return y_;
  }

 private:
  void setPoint(const double x, const double y)
  {
    x_ = x;
    y_ = y;
    has_point_ = true;
  }

  double x_ = 0.0;
  double y_ = 0.0;
  bool has_point_ = false;
  bool touching_ = false;
  bool stroking_ = false;
};
