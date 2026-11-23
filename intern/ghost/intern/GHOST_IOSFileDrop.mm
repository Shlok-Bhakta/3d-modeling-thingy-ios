/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Accept files dragged onto a Blender window from other apps.
 */

#include "GHOST_IOSFileDrop.hh"

#include "GHOST_IOSVirtualPointer.hh"
#include "GHOST_SystemIOS.hh"
#include "GHOST_WindowIOS.hh"

#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

@interface GHOSTIOSFileDrop : NSObject <UIDropInteractionDelegate>
{
  UIView *view_;
  UIDropInteraction *interaction_;
  GHOST_SystemIOS *system_;
  GHOST_WindowIOS *window_;
}

- (instancetype)initWithView:(UIView *)view
                      system:(GHOST_SystemIOS *)system
                      window:(GHOST_WindowIOS *)window;
- (void)invalidate;
@end

@implementation GHOSTIOSFileDrop

- (instancetype)initWithView:(UIView *)view
                      system:(GHOST_SystemIOS *)system
                      window:(GHOST_WindowIOS *)window
{
  self = [super init];
  if (self) {
    view_ = [view retain];
    system_ = system;
    window_ = window;
    interaction_ = [[UIDropInteraction alloc] initWithDelegate:self];
    [view_ addInteraction:interaction_];
  }
  return self;
}

- (void)invalidate
{
  [view_ removeInteraction:interaction_];
  [interaction_ release];
  interaction_ = nil;
  [view_ release];
  view_ = nil;
  system_ = nullptr;
  window_ = nullptr;
}

/** The drop location in window pixels. Moving Blender's cursor there lets the editor under it
 * highlight and receive the drop. */
- (CGPoint)pointerToSession:(id<UIDropSession>)session
{
  CGPoint point = [session locationInView:view_];
  const CGPoint pixel = window_->scalePointToWindow(point);
  system_->virtualPointer()->warp(pixel.x, pixel.y);
  return pixel;
}

- (BOOL)dropInteraction:(UIDropInteraction *)interaction canHandleSession:(id<UIDropSession>)session
{
  return window_ != nullptr && [session hasItemsConformingToTypeIdentifiers:@[ UTTypeData.identifier ]];
}

- (UIDropProposal *)dropInteraction:(UIDropInteraction *)interaction
                   sessionDidUpdate:(id<UIDropSession>)session
{
  if (window_ == nullptr) {
    return [[[UIDropProposal alloc] initWithDropOperation:UIDropOperationCancel] autorelease];
  }
  [self pointerToSession:session];
  return [[[UIDropProposal alloc] initWithDropOperation:UIDropOperationCopy] autorelease];
}

- (void)dropInteraction:(UIDropInteraction *)interaction performDrop:(id<UIDropSession>)session
{
  if (window_ == nullptr) {
    return;
  }
  const CGPoint pixel = [self pointerToSession:session];
  NSMutableArray<NSItemProvider *> *providers = [NSMutableArray array];
  for (UIDragItem *item in session.items) {
    [providers addObject:item.itemProvider];
  }
  /* The block keeps this object alive while files load; the window may close meanwhile. */
  GHOST_IOSFileDrop_loadFiles(providers, GHOST_IOSFileDrop_inbox(), ^(NSArray<NSString *> *paths) {
    if (window_ == nullptr || paths.count == 0) {
      return;
    }
    system_->handleDraggingEvent(GHOST_kEventDraggingDropDone,
                                 GHOST_kDragnDropTypeFilenames,
                                 window_,
                                 int(pixel.x),
                                 int(pixel.y),
                                 paths);
  });
}

@end

NSObject *GHOST_IOSFileDrop_install(UIView *view, GHOST_SystemIOS *system, GHOST_WindowIOS *window)
{
  if (view == nil || system == nullptr || window == nullptr) {
    return nil;
  }
  return [[GHOSTIOSFileDrop alloc] initWithView:view system:system window:window];
}

void GHOST_IOSFileDrop_uninstall(NSObject *drop)
{
  if (drop == nil) {
    return;
  }
  [(GHOSTIOSFileDrop *)drop invalidate];
  [drop release];
}
