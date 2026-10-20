/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* GHOST's cross-platform C++ interfaces intentionally do not carry Objective-C
 * nullability qualifiers. UIKit makes Clang request them for every pointer. */
#pragma clang diagnostic ignored "-Wnullability-completeness"

#include "GHOST_IOSVirtualPointer.hh"

#include "GHOST_SystemIOS.hh"
#include "GHOST_WindowIOS.hh"

#include "GHOST_EventButton.hh"
#include "GHOST_EventCursor.hh"
#include "GHOST_EventTrackpad.hh"
#include "GHOST_Rect.hh"

#import <GameController/GameController.h>
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>

#include <cmath>

@interface GHOSTIOSPointerHider : NSObject <UIPointerInteractionDelegate>
@end

@implementation GHOSTIOSPointerHider

- (UIPointerStyle *)pointerInteraction:(UIPointerInteraction *)interaction
                        styleForRegion:(UIPointerRegion *)region
{
  (void)interaction;
  (void)region;
  return [UIPointerStyle hiddenPointerStyle];
}

@end

class GHOST_IOSVirtualPointer::Impl {
 public:
  explicit Impl(GHOST_SystemIOS *system) : system_(system)
  {
    mice_ = [[NSMutableSet alloc] init];
    const std::weak_ptr<int> lifetime = callback_lifetime_;
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    mouse_connect_observer_ = [[center
        addObserverForName:GCMouseDidConnectNotification object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) {
          if (!lifetime.expired()) {
            connectMouse((GCMouse *)note.object);
          }
        }] retain];
    mouse_disconnect_observer_ = [[center
        addObserverForName:GCMouseDidDisconnectNotification object:nil
        queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
          if (lifetime.expired()) {
            return;
          }
          disconnectMouse((GCMouse *)note.object);
          syncMouseButtons();
          updatePointerLockPreference();
        }] retain];
    pointer_lock_observer_ = [[center
        addObserverForName:UIPointerLockStateDidChangeNotification object:nil
        queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
          if (lifetime.expired()) {
            return;
          }
          if (window_ != nullptr && note.object == window_->rootWindow.windowScene.pointerLockState) {
            updateHardwareButtons(0);
          }
        }] retain];
    for (GCMouse *mouse in GCMouse.mice) {
      connectMouse(mouse);
    }
  }

  ~Impl()
  {
    callback_lifetime_.reset();
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    for (id observer in @[mouse_connect_observer_, mouse_disconnect_observer_, pointer_lock_observer_]) {
      [center removeObserver:observer];
      [observer release];
    }
    for (GCMouse *mouse in mice_.allObjects) {
      disconnectMouse(mouse);
    }
    [mice_ release];
    detachWindow(window_);
    [pointer_hider_ release];
  }

  bool usesHardwareMouse() const
  {
    return window_ != nullptr && mice_.count != 0 && window_->rootWindow.isKeyWindow &&
           window_->rootWindow.windowScene.activationState == UISceneActivationStateForegroundActive &&
           window_->rootWindow.windowScene.pointerLockState.isLocked &&
           !window_->getUITextField().isFirstResponder &&
           window_->rootWindow.rootViewController.presentedViewController == nil;
  }

  void updatePointerLockPreference()
  {
    if (window_ != nullptr) {
      [window_->rootWindow.rootViewController setNeedsUpdateOfPrefersPointerLocked];
    }
  }

  void updateHardwareButtons(const unsigned int mask)
  {
    constexpr GHOST_TButton buttons[] = {
        GHOST_kButtonMaskLeft, GHOST_kButtonMaskRight, GHOST_kButtonMaskMiddle};
    for (int i = 0; i < 3; i++) {
      GHOST_IOSPointerButton state_button;
      stateButton(buttons[i], state_button);
      const bool down = (mask & (1u << i)) != 0;
      if (state_.setButton(state_button, down, GHOST_IOSPointerSource::Hardware)) {
        /* Use the visible cursor's position before the press, never a drag recognizer's
         * later location. This also establishes hover for gizmo hit testing. */
        state_.setSource(GHOST_IOSPointerSource::Hardware);
        sendCursorEvent(GHOST_TABLET_DATA_NONE);
        sendButtonEvent(buttons[i], down, GHOST_TABLET_DATA_NONE);
      }
    }
  }

  void syncMouseButtons()
  {
    unsigned int mask = 0;
    if (usesHardwareMouse()) {
      for (GCMouse *mouse in mice_) {
        GCMouseInput *input = mouse.mouseInput;
        mask |= input.leftButton.isPressed ? 1u : 0u;
        mask |= input.rightButton.isPressed ? 2u : 0u;
        mask |= input.middleButton.isPressed ? 4u : 0u;
      }
    }
    updateHardwareButtons(mask);
  }

  void connectMouse(GCMouse *mouse)
  {
    if (mouse.mouseInput == nil || [mice_ containsObject:mouse]) {
      return;
    }
    [mice_ addObject:mouse];
    mouse.handlerQueue = dispatch_get_main_queue();
    GCMouseInput *input = mouse.mouseInput;
    const std::weak_ptr<int> lifetime = callback_lifetime_;
    input.mouseMovedHandler = ^(GCMouseInput *, float delta_x, float delta_y) {
      if (!lifetime.expired() && usesHardwareMouse()) {
        const double scale = window_->getWindowScaleFactor();
        state_.moveAbsolute(state_.x() + delta_x * scale,
                            state_.y() - delta_y * scale,
                            GHOST_IOSPointerSource::Hardware);
        sendCursorEvent(GHOST_TABLET_DATA_NONE);
      }
    };
    auto button_changed = ^(GCControllerButtonInput *, float, BOOL) {
      if (!lifetime.expired()) {
        syncMouseButtons();
      }
    };
    input.leftButton.pressedChangedHandler = button_changed;
    input.rightButton.pressedChangedHandler = button_changed;
    input.middleButton.pressedChangedHandler = button_changed;
    input.scroll.valueChangedHandler = ^(GCControllerDirectionPad *, float x, float y) {
      if (!lifetime.expired() && usesHardwareMouse() && (x != 0.0f || y != 0.0f)) {
        system_->pushEvent(std::make_unique<GHOST_EventTrackpad>(system_->getMilliSeconds(),
                                                               window_,
                                                               GHOST_kTrackpadEventScroll,
                                                               int32_t(state_.x()),
                                                               int32_t(state_.y()),
                                                               int32_t(std::lround(x)),
                                                               int32_t(std::lround(y)),
                                                               true));
      }
    };
    updatePointerLockPreference();
  }

  void disconnectMouse(GCMouse *mouse)
  {
    GCMouseInput *input = mouse.mouseInput;
    input.mouseMovedHandler = nil;
    input.leftButton.pressedChangedHandler = nil;
    input.rightButton.pressedChangedHandler = nil;
    input.middleButton.pressedChangedHandler = nil;
    input.scroll.valueChangedHandler = nil;
    [mice_ removeObject:mouse];
  }

  void attachWindow(GHOST_WindowIOS *window)
  {
    if (window_ == window && cursor_layer_ != nil) {
      state_.setBlenderVisibility(window_->getCursorVisibility());
      grab_mode_ = window_->getCursorGrabMode();
      updateCursorLayer();
      return;
    }

    detachWindow(window_);
    window_ = window;
    if (window_ == nullptr) {
      return;
    }

    const CGSize native_size = window_->getNativeWindowSize();
    state_.initialize(native_size.width, native_size.height, window_->getWindowScaleFactor());
    state_.setBlenderVisibility(window_->getCursorVisibility());
    grab_mode_ = window_->getCursorGrabMode();

    UIBezierPath *path = [UIBezierPath bezierPath];
    /* The outside edge of the stroke lands at (0, 0), making the visible tip the hotspot. */
    [path moveToPoint:CGPointMake(0.75, 0.75)];
    [path addQuadCurveToPoint:CGPointMake(2.8, 1.25) controlPoint:CGPointMake(1.45, 0.35)];
    [path addLineToPoint:CGPointMake(24.0, 17.0)];
    [path addQuadCurveToPoint:CGPointMake(21.5, 21.0) controlPoint:CGPointMake(25.2, 20.0)];
    [path addLineToPoint:CGPointMake(14.0, 21.0)];
    [path addLineToPoint:CGPointMake(9.8, 28.0)];
    [path addQuadCurveToPoint:CGPointMake(5.6, 27.1) controlPoint:CGPointMake(7.1, 30.1)];
    [path addLineToPoint:CGPointMake(0.5, 3.0)];
    [path addQuadCurveToPoint:CGPointMake(0.75, 0.75) controlPoint:CGPointMake(0.2, 1.4)];
    [path closePath];

    cursor_layer_ = [[CAShapeLayer layer] retain];
    cursor_layer_.path = path.CGPath;
    cursor_layer_.fillColor = [UIColor colorWithWhite:0.24 alpha:0.98].CGColor;
    cursor_layer_.strokeColor = [UIColor colorWithWhite:0.78 alpha:0.80].CGColor;
    cursor_layer_.lineWidth = 1.5;
    cursor_layer_.lineJoin = kCALineJoinRound;
    cursor_layer_.lineCap = kCALineCapRound;
    cursor_layer_.bounds = CGRectMake(0.0, 0.0, 30.0, 32.0);
    cursor_layer_.anchorPoint = CGPointMake(0.0, 0.0);
    cursor_layer_.contentsScale = UIScreen.mainScreen.scale;
    cursor_layer_.shouldRasterize = YES;
    cursor_layer_.rasterizationScale = UIScreen.mainScreen.scale;
    cursor_layer_.zPosition = 100000.0;
    [window_->getView().layer addSublayer:cursor_layer_];

    if (pointer_hider_ == nil) {
      pointer_hider_ = [[GHOSTIOSPointerHider alloc] init];
    }
    pointer_interaction_ = [[UIPointerInteraction alloc] initWithDelegate:pointer_hider_];
    [window_->getView() addInteraction:pointer_interaction_];
    updatePointerLockPreference();
    updateCursorLayer();
  }

  void detachWindow(GHOST_WindowIOS *window)
  {
    if (window == nullptr || window != window_) {
      return;
    }

    if (pointer_interaction_ != nil) {
      [window_->getView() removeInteraction:pointer_interaction_];
      [pointer_interaction_ release];
      pointer_interaction_ = nil;
    }
    [cursor_layer_ removeFromSuperlayer];
    [cursor_layer_ release];
    cursor_layer_ = nil;
    window_ = nullptr;
  }

  void sendCursorEvent(const GHOST_TabletData &tablet)
  {
    if (window_ == nullptr) {
      return;
    }
    int32_t x = int32_t(std::lround(state_.x()));
    int32_t y = int32_t(std::lround(state_.y()));
    constrainCursorForEvent(x, y);
    system_->pushEvent(std::make_unique<GHOST_EventCursor>(
        system_->getMilliSeconds(), GHOST_kEventCursorMove, window_, x, y, tablet));
    updateCursorLayer();
  }

  void constrainCursorForEvent(int32_t &event_x, int32_t &event_y)
  {
    GHOST_Rect bounds;
    if (grab_mode_ == GHOST_kGrabWrap || grab_mode_ == GHOST_kGrabHide) {
      if (window_->getCursorGrabBounds(bounds) == GHOST_kSuccess) {
        int32_t left;
        int32_t top;
        int32_t right;
        int32_t bottom;
        window_->screenToClient(bounds.l_, bounds.t_, left, top);
        window_->screenToClient(bounds.r_, bounds.b_, right, bottom);
        bounds.set(left, top, right, bottom);
      }
      else {
        window_->getClientBounds(bounds);
      }

      const double margin = grab_mode_ == GHOST_kGrabHide ?
                                double(bounds.getWidth()) / 10.0 :
                                2.0;
      const GHOST_TAxisFlag axis = window_->getCursorGrabAxis();
      const GHOST_IOSPointerWrapOffset offset = state_.wrapToBounds(bounds.l_,
                                                                    bounds.t_,
                                                                    bounds.r_,
                                                                    bounds.b_,
                                                                    margin,
                                                                    axis & GHOST_kAxisX,
                                                                    axis & GHOST_kAxisY);
      /* UIKit has no hardware cursor to constrain the axes Blender did not request to wrap. */
      state_.clampToBounds(bounds.l_, bounds.t_, bounds.r_, bounds.b_);
      int32_t accumulated_x;
      int32_t accumulated_y;
      window_->getCursorGrabAccum(accumulated_x, accumulated_y);
      accumulated_x += int32_t(std::lround(offset.x));
      accumulated_y += int32_t(std::lround(offset.y));
      window_->setCursorGrabAccum(accumulated_x, accumulated_y);
      event_x = int32_t(std::lround(state_.x())) + accumulated_x;
      event_y = int32_t(std::lround(state_.y())) + accumulated_y;
      return;
    }

    window_->getClientBounds(bounds);
    if constexpr (GHOST_IOSInputTuning::pointer_always_wrap) {
      state_.wrapToBounds(bounds.l_, bounds.t_, bounds.r_, bounds.b_, 2.0, true, true);
    }
    else {
      state_.clampToBounds(bounds.l_, bounds.t_, bounds.r_, bounds.b_);
    }
    event_x = int32_t(std::lround(state_.x()));
    event_y = int32_t(std::lround(state_.y()));
  }

  void sendButtonEvent(const GHOST_TButton button,
                       const bool down,
                       const GHOST_TabletData &tablet)
  {
    if (window_ == nullptr) {
      return;
    }
    system_->pushEvent(std::make_unique<GHOST_EventButton>(system_->getMilliSeconds(),
                                                           down ? GHOST_kEventButtonDown :
                                                                  GHOST_kEventButtonUp,
                                                           window_,
                                                           button,
                                                           tablet));
  }

  void updateCursorLayer()
  {
    if (cursor_layer_ == nil || window_ == nullptr) {
      return;
    }

    const CGFloat scale = window_->getWindowScaleFactor();
    [CATransaction begin];
    [CATransaction setDisableActions:YES];
    cursor_layer_.position = CGPointMake(state_.x() / scale, state_.y() / scale);
    cursor_layer_.hidden = !state_.visible() || grab_mode_ == GHOST_kGrabHide;
    [CATransaction commit];
  }

  static bool stateButton(const GHOST_TButton button, GHOST_IOSPointerButton &state_button)
  {
    switch (button) {
      case GHOST_kButtonMaskLeft:
        state_button = GHOST_IOSPointerButton::Left;
        return true;
      case GHOST_kButtonMaskMiddle:
        state_button = GHOST_IOSPointerButton::Middle;
        return true;
      case GHOST_kButtonMaskRight:
        state_button = GHOST_IOSPointerButton::Right;
        return true;
      default:
        return false;
    }
  }

  GHOST_SystemIOS *system_ = nullptr;
  GHOST_WindowIOS *window_ = nullptr;
  GHOST_IOSVirtualPointerState state_;
  GHOST_TGrabCursorMode grab_mode_ = GHOST_kGrabDisable;
  CAShapeLayer *cursor_layer_ = nil;
  GHOSTIOSPointerHider *pointer_hider_ = nil;
  UIPointerInteraction *pointer_interaction_ = nil;
  NSMutableSet<GCMouse *> *mice_ = nil;
  id mouse_connect_observer_ = nil;
  id mouse_disconnect_observer_ = nil;
  id pointer_lock_observer_ = nil;
  std::shared_ptr<int> callback_lifetime_ = std::make_shared<int>(0);
};

GHOST_IOSVirtualPointer::GHOST_IOSVirtualPointer(GHOST_SystemIOS *system)
    : impl_(std::make_unique<Impl>(system))
{
}

GHOST_IOSVirtualPointer::~GHOST_IOSVirtualPointer() = default;

void GHOST_IOSVirtualPointer::attachWindow(GHOST_WindowIOS *window)
{
  impl_->attachWindow(window);
}

void GHOST_IOSVirtualPointer::detachWindow(GHOST_WindowIOS *window)
{
  impl_->detachWindow(window);
}

void GHOST_IOSVirtualPointer::beginRelative(const double finger_x, const double finger_y)
{
  beginRelativeAtTime(finger_x, finger_y, CACurrentMediaTime());
}

void GHOST_IOSVirtualPointer::beginRelativeAtTime(const double finger_x,
                                                  const double finger_y,
                                                  const double timestamp_seconds)
{
  impl_->state_.beginRelative(finger_x, finger_y, timestamp_seconds);
  impl_->updateCursorLayer();
}

void GHOST_IOSVirtualPointer::moveRelativeTo(const double finger_x,
                                             const double finger_y,
                                             const GHOST_TabletData &tablet)
{
  moveRelativeToAtTime(finger_x, finger_y, CACurrentMediaTime(), tablet);
}

void GHOST_IOSVirtualPointer::moveRelativeToAtTime(const double finger_x,
                                                   const double finger_y,
                                                   const double timestamp_seconds,
                                                   const GHOST_TabletData &tablet)
{
  impl_->state_.moveRelativeTo(finger_x, finger_y, timestamp_seconds);
  impl_->sendCursorEvent(tablet);
}

void GHOST_IOSVirtualPointer::endRelative()
{
  impl_->state_.endRelative();
}

void GHOST_IOSVirtualPointer::moveAbsolute(const double x,
                                           const double y,
                                           const GHOST_IOSPointerSource source,
                                           const GHOST_TabletData &tablet)
{
  impl_->state_.moveAbsolute(x, y, source);
  impl_->sendCursorEvent(tablet);
}

void GHOST_IOSVirtualPointer::warp(const double x, const double y)
{
  impl_->state_.warp(x, y);
  impl_->sendCursorEvent(GHOST_TABLET_DATA_NONE);
}

void GHOST_IOSVirtualPointer::setSource(const GHOST_IOSPointerSource source)
{
  impl_->state_.setSource(source);
  impl_->updateCursorLayer();
}

void GHOST_IOSVirtualPointer::button(const GHOST_TButton button,
                                     const bool down,
                                     const GHOST_TabletData &tablet)
{
  GHOST_IOSPointerButton state_button;
  if (Impl::stateButton(button, state_button) && !impl_->state_.setButton(state_button, down)) {
    return;
  }
  impl_->sendButtonEvent(button, down, tablet);
}

void GHOST_IOSVirtualPointer::click(const GHOST_TButton button,
                                    const GHOST_TabletData &tablet)
{
  this->button(button, true, tablet);
  this->button(button, false, tablet);
}

void GHOST_IOSVirtualPointer::clearButtons()
{
  for (GHOST_TButton button : {GHOST_kButtonMaskLeft, GHOST_kButtonMaskMiddle, GHOST_kButtonMaskRight}) {
    GHOST_IOSPointerButton state_button;
    Impl::stateButton(button, state_button);
    if (impl_->state_.buttonDown(state_button)) {
      impl_->sendButtonEvent(button, false, GHOST_TABLET_DATA_NONE);
    }
  }
  impl_->state_.clearButtons();
}

void GHOST_IOSVirtualPointer::hardwareButtons(const unsigned int mask)
{
  impl_->updateHardwareButtons(mask);
}

bool GHOST_IOSVirtualPointer::hasHardwareMouse() const
{
  return impl_->mice_.count != 0;
}

bool GHOST_IOSVirtualPointer::usesHardwareMouse() const
{
  return impl_->usesHardwareMouse();
}

void GHOST_IOSVirtualPointer::getButtons(GHOST_Buttons &buttons) const
{
  buttons.clear();
  buttons.set(GHOST_kButtonMaskLeft,
              impl_->state_.buttonDown(GHOST_IOSPointerButton::Left));
  buttons.set(GHOST_kButtonMaskMiddle,
              impl_->state_.buttonDown(GHOST_IOSPointerButton::Middle));
  buttons.set(GHOST_kButtonMaskRight,
              impl_->state_.buttonDown(GHOST_IOSPointerButton::Right));
}

void GHOST_IOSVirtualPointer::getClientPosition(double &x, double &y) const
{
  x = impl_->state_.x();
  y = impl_->state_.y();
}

GHOST_TSuccess GHOST_IOSVirtualPointer::getCursorPosition(int32_t &screen_x,
                                                          int32_t &screen_y) const
{
  if (impl_->window_ == nullptr) {
    return GHOST_kFailure;
  }
  impl_->window_->clientToScreen(int32_t(std::lround(impl_->state_.x())),
                                int32_t(std::lround(impl_->state_.y())),
                                screen_x,
                                screen_y);
  return GHOST_kSuccess;
}

void GHOST_IOSVirtualPointer::setBlenderVisibility(const bool visible)
{
  impl_->state_.setBlenderVisibility(visible);
  impl_->updateCursorLayer();
}

void GHOST_IOSVirtualPointer::setGrabMode(const GHOST_TGrabCursorMode mode)
{
  impl_->grab_mode_ = mode;
  impl_->updateCursorLayer();
}
