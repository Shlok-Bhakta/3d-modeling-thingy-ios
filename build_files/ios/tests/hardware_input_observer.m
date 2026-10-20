/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Test-only Simulator injection. Observe OS accessory state without installing
 * input handlers or changing the application's event delivery. */
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#import <UIKit/UIKit.h>

__attribute__((constructor)) static void observe_hardware(void)
{
  dispatch_async(dispatch_get_main_queue(), ^{
    NSTimer *timer = [NSTimer scheduledTimerWithTimeInterval:0.05 repeats:YES block:^(NSTimer *t) {
      NSMutableArray *mice = [NSMutableArray array];
      for (GCMouse *mouse in GCMouse.mice) {
        GCMouseInput *input = mouse.mouseInput;
        [mice addObject:@{@"left": @(input.leftButton.isPressed),
                          @"middle": @(input.middleButton.isPressed),
                          @"right": @(input.rightButton.isPressed)}];
      }
      UIWindowScene *scene = (UIWindowScene *)UIApplication.sharedApplication.connectedScenes.anyObject;
      NSDictionary *state = @{@"mice": mice, @"time": @(NSDate.date.timeIntervalSince1970),
                              @"pid": @(NSProcessInfo.processInfo.processIdentifier),
                              @"locked": @(scene.pointerLockState.isLocked)};
      NSData *data = [NSJSONSerialization dataWithJSONObject:state options:0 error:nil];
      [data writeToFile:[NSTemporaryDirectory() stringByAppendingPathComponent:@"hardware-os.json"]
               options:NSDataWritingAtomic error:nil];
    }];
    (void)timer;
  });
}
