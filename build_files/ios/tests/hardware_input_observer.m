/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Test-only Simulator observer. Record real wheel callbacks and forward their
 * arguments to the app's original handler unchanged. Never synthesize input. */
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#import <UIKit/UIKit.h>

__attribute__((constructor)) static void observe_hardware(void)
{
  dispatch_async(dispatch_get_main_queue(), ^{
    NSHashTable *observed = [NSHashTable weakObjectsHashTable];
    NSMutableArray *scroll_events = [NSMutableArray array];
    __block NSUInteger sequence = 0;
    NSTimer *timer = [NSTimer scheduledTimerWithTimeInterval:0.05 repeats:YES block:^(NSTimer *t) {
      NSMutableArray *mice = [NSMutableArray array];
      for (GCMouse *mouse in GCMouse.mice) {
        GCMouseInput *input = mouse.mouseInput;
        if (![observed containsObject:input] && input.scroll.valueChangedHandler != nil) {
          [observed addObject:input];
          void (^original)(GCControllerDirectionPad *, float, float) = input.scroll.valueChangedHandler;
          input.scroll.valueChangedHandler = ^(GCControllerDirectionPad *scroll, float x, float y) {
            [scroll_events addObject:@{@"time": @(NSDate.date.timeIntervalSince1970),
                                       @"sequence": @(++sequence), @"x": @(x), @"y": @(y)}];
            if (scroll_events.count > 500) {
              [scroll_events removeObjectAtIndex:0];
            }
            original(scroll, x, y);
          };
        }
        [mice addObject:@{@"left": @(input.leftButton.isPressed),
                          @"middle": @(input.middleButton.isPressed),
                          @"right": @(input.rightButton.isPressed),
                          @"scroll_x": @(input.scroll.xAxis.value),
                          @"scroll_y": @(input.scroll.yAxis.value)}];
      }
      UIWindowScene *scene = (UIWindowScene *)UIApplication.sharedApplication.connectedScenes.anyObject;
      NSDictionary *state = @{@"mice": mice, @"time": @(NSDate.date.timeIntervalSince1970),
                              @"scroll_events": scroll_events,
                              @"pid": @(NSProcessInfo.processInfo.processIdentifier),
                              @"locked": @(scene.pointerLockState.isLocked)};
      NSData *data = [NSJSONSerialization dataWithJSONObject:state options:0 error:nil];
      [data writeToFile:[NSTemporaryDirectory() stringByAppendingPathComponent:@"hardware-os.json"]
               options:NSDataWritingAtomic error:nil];
    }];
    (void)timer;
  });
}
