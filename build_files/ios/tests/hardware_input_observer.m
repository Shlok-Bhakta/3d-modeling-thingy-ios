/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Test-only Simulator observer. Record real wheel callbacks and forward their
 * arguments to the app's original handler unchanged. Never synthesize input. */
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <sys/resource.h>

static NSMutableArray *uikit_scroll_events;
static NSArray *native_pointer;
static NSMutableArray *pointer_events;
static NSUInteger frame_count;
static __weak UIView *frame_view;
static BOOL geometry_requested;
static NSString *geometry_error;

static void observe_frame(id renderer, SEL selector, UIView *view)
{
  frame_count++;
  frame_view = view;
  ((void (*)(id, SEL, id))objc_msgSend)(renderer, @selector(observeInputFrame:), view);
}

@interface HardwareHoverObserver : NSObject <UIGestureRecognizerDelegate>
- (void)hover:(UIHoverGestureRecognizer *)recognizer;
@end

@implementation HardwareHoverObserver
- (void)hover:(UIHoverGestureRecognizer *)recognizer
{
  CGPoint point = [recognizer locationInView:recognizer.view];
  CGFloat scale = ((UIWindow *)recognizer.view).rootViewController.view.contentScaleFactor;
  native_pointer = @[@(point.x * scale), @(point.y * scale)];
}
- (BOOL)gestureRecognizer:(UIGestureRecognizer *)recognizer
    shouldRecognizeSimultaneouslyWithGestureRecognizer:(UIGestureRecognizer *)other
{
  return YES;
}
@end

static void observe_scroll(id window, SEL selector, UIPanGestureRecognizer *sender)
{
  CGPoint translation = [sender translationInView:sender.view];
  [uikit_scroll_events addObject:@{@"time": @(NSDate.date.timeIntervalSince1970),
                                  @"x": @(translation.x), @"y": @(translation.y),
                                  @"state": @(sender.state), @"modifiers": @(sender.modifierFlags)}];
  if (uikit_scroll_events.count > 500) {
    [uikit_scroll_events removeObjectAtIndex:0];
  }
  /* Swizzling installs the original implementation under this observer selector. */
  ((void (*)(id, SEL, id))objc_msgSend)(window, @selector(observeInputScroll:), sender);
}

static void observe_pointer_event(id window, SEL selector, UIEvent *event)
{
  for (UITouch *touch in event.allTouches) {
    if (touch.type == UITouchTypeIndirectPointer) {
      [pointer_events addObject:@{@"time": @(NSDate.date.timeIntervalSince1970),
                                  @"phase": @(touch.phase), @"mask": @(event.buttonMask),
                                  @"view": NSStringFromClass(touch.view.class) ?: @"None"}];
      if (pointer_events.count > 500) {
        [pointer_events removeObjectAtIndex:0];
      }
    }
  }
  ((void (*)(id, SEL, id))objc_msgSend)(window, @selector(observePointerEvent:), event);
}

__attribute__((constructor)) static void observe_hardware(void)
{
  dispatch_async(dispatch_get_main_queue(), ^{
    uikit_scroll_events = [NSMutableArray array];
    pointer_events = [NSMutableArray array];
    Class window_class = NSClassFromString(@"GHOSTUIWindow");
    Method original_scroll = class_getInstanceMethod(window_class, @selector(handlePointerScroll:));
    class_addMethod(window_class, @selector(observeInputScroll:), (IMP)observe_scroll,
                    method_getTypeEncoding(original_scroll));
    method_exchangeImplementations(original_scroll,
        class_getInstanceMethod(window_class, @selector(observeInputScroll:)));
    Method send_event = class_getInstanceMethod(window_class, @selector(sendEvent:));
    class_addMethod(window_class, @selector(observePointerEvent:), (IMP)observe_pointer_event,
                    method_getTypeEncoding(send_event));
    method_exchangeImplementations(send_event,
        class_getInstanceMethod(window_class, @selector(observePointerEvent:)));
    Class renderer_class = NSClassFromString(@"GHOST_IOSMetalRenderer");
    Method draw = class_getInstanceMethod(renderer_class, @selector(drawInMTKView:));
    class_addMethod(renderer_class, @selector(observeInputFrame:), (IMP)observe_frame,
                    method_getTypeEncoding(draw));
    method_exchangeImplementations(draw,
        class_getInstanceMethod(renderer_class, @selector(observeInputFrame:)));
    NSHashTable *observed = [NSHashTable weakObjectsHashTable];
    NSHashTable *observed_motion = [NSHashTable weakObjectsHashTable];
    NSHashTable *observed_windows = [NSHashTable weakObjectsHashTable];
    HardwareHoverObserver *hover_observer = [HardwareHoverObserver new];
    NSMutableArray *scroll_events = [NSMutableArray array];
    __block NSUInteger sequence = 0;
    __block NSUInteger raw_motion_callbacks = 0;
    NSTimer *timer = [NSTimer scheduledTimerWithTimeInterval:0.05 repeats:YES block:^(NSTimer *t) {
      NSMutableArray *mice = [NSMutableArray array];
      for (GCMouse *mouse in GCMouse.mice) {
        GCMouseInput *input = mouse.mouseInput;
        if (![observed_motion containsObject:input] && input.mouseMovedHandler != nil) {
          [observed_motion addObject:input];
          GCMouseMoved original_motion = input.mouseMovedHandler;
          input.mouseMovedHandler = ^(GCMouseInput *source, float x, float y) {
            raw_motion_callbacks++;
            original_motion(source, x, y);
          };
        }
        if (![observed containsObject:input]) {
          [observed addObject:input];
          void (^original)(GCControllerDirectionPad *, float, float) = input.scroll.valueChangedHandler;
          input.scroll.valueChangedHandler = ^(GCControllerDirectionPad *scroll, float x, float y) {
            [scroll_events addObject:@{@"time": @(NSDate.date.timeIntervalSince1970),
                                       @"sequence": @(++sequence), @"x": @(x), @"y": @(y)}];
            if (scroll_events.count > 500) {
              [scroll_events removeObjectAtIndex:0];
            }
            if (original) {
              original(scroll, x, y);
            }
          };
        }
        [mice addObject:@{@"left": @(input.leftButton.isPressed),
                          @"middle": @(input.middleButton.isPressed),
                          @"right": @(input.rightButton.isPressed),
                          @"scroll_x": @(input.scroll.xAxis.value),
                          @"scroll_y": @(input.scroll.yAxis.value)}];
      }
      UIWindowScene *scene = (UIWindowScene *)UIApplication.sharedApplication.connectedScenes.anyObject;
      if (!geometry_requested && scene.keyWindow != nil &&
          [NSProcessInfo.processInfo.environment[@"BLENDER_INPUT_LANDSCAPE"] boolValue]) {
        geometry_requested = YES;
        [scene.keyWindow.rootViewController setNeedsUpdateOfSupportedInterfaceOrientations];
        UIWindowSceneGeometryPreferencesIOS *preferences = [[UIWindowSceneGeometryPreferencesIOS alloc]
            initWithInterfaceOrientations:UIInterfaceOrientationMaskLandscapeLeft];
        [scene requestGeometryUpdateWithPreferences:preferences errorHandler:^(NSError *error) {
          geometry_error = error.localizedDescription;
        }];
      }
      BOOL custom_arrow = NO;
      for (UIWindow *window in scene.windows) {
        if (window.isKeyWindow) {
          for (id interaction in window.rootViewController.view.interactions) {
            if ([interaction isKindOfClass:UIPointerInteraction.class]) {
              id delegate = ((UIPointerInteraction *)interaction).delegate;
              if ([delegate isKindOfClass:NSClassFromString(@"GHOSTIOSPointerHider")] &&
                  [delegate respondsToSelector:@selector(hidden)]) {
                custom_arrow = ![[delegate valueForKey:@"hidden"] boolValue] &&
                               [delegate valueForKey:@"path"] != nil;
              }
            }
          }
        }
        if (![observed_windows containsObject:window]) {
          [observed_windows addObject:window];
          UIHoverGestureRecognizer *hover = [[UIHoverGestureRecognizer alloc]
              initWithTarget:hover_observer action:@selector(hover:)];
          hover.allowedTouchTypes = @[@(UITouchTypeIndirectPointer)];
          hover.cancelsTouchesInView = NO;
          hover.delegate = hover_observer;
          [window addGestureRecognizer:hover];
        }
      }
      struct rusage usage;
      getrusage(RUSAGE_SELF, &usage);
      double cpu_seconds = usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6 +
                           usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1e6;
      NSDictionary *state = @{@"mice": mice, @"time": @(NSDate.date.timeIntervalSince1970),
                              @"scroll_events": scroll_events,
                              @"uikit_scroll_events": uikit_scroll_events,
                              @"pointer_events": pointer_events,
                              @"pid": @(NSProcessInfo.processInfo.processIdentifier),
                              @"cpu_seconds": @(cpu_seconds),
                              @"active_cores": @(NSProcessInfo.processInfo.activeProcessorCount),
                              @"native_pointer": native_pointer ?: (id)NSNull.null,
                              @"custom_arrow": @(custom_arrow),
                              @"raw_motion_callbacks": @(raw_motion_callbacks),
                              @"frames": @(frame_count),
                              @"preferred_fps": frame_view ? [frame_view valueForKey:@"preferredFramesPerSecond"] : @0,
                              @"maximum_fps": @(scene.screen.maximumFramesPerSecond),
                              @"interface_orientation": @(scene.interfaceOrientation),
                              @"geometry_error": geometry_error ?: @"",
                              @"locked": @(scene.pointerLockState.isLocked)};
      NSData *data = [NSJSONSerialization dataWithJSONObject:state options:0 error:nil];
      [data writeToFile:[NSTemporaryDirectory() stringByAppendingPathComponent:@"hardware-os.json"]
               options:NSDataWritingAtomic error:nil];
    }];
    (void)timer;
  });
}
