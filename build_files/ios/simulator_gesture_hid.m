// SPDX-FileCopyrightText: 2026 Blender Authors
// SPDX-License-Identifier: GPL-2.0-or-later
// Host-only SimulatorKit input. This file is never linked into the iOS app.
#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <mach/mach_time.h>
#import <malloc/malloc.h>
#import <objc/message.h>
@interface NSObject (PrivateSimulator)
+ (id)sharedServiceContextForDeveloperDir:(NSString *)dir error:(NSError **)error;
- (id)defaultDeviceSetWithError:(NSError **)error;
- (NSArray *)availableDevices;
- (NSUUID *)UDID;
- (id)initWithDevice:(id)device error:(NSError **)error;
- (void)sendWithMessage:(void *)message
           freeWhenDone:(BOOL)free
        completionQueue:(id)queue
             completion:(id)completion;
@end
int main(int argc, char **argv)
{
  @autoreleasepool {
    if (argc != 2) {
      fprintf(stderr, "usage: simulator_gesture_hid UDID < events.json\n");
      return 1;
    }
    NSString *dev = NSProcessInfo.processInfo.environment[@"DEVELOPER_DIR"];
    if (!dev) {
      fprintf(stderr, "DEVELOPER_DIR is required\n");
      return 1;
    }
    dlopen(
        [[dev stringByAppendingString:
                  @"/Library/PrivateFrameworks/CoreSimulator.framework/CoreSimulator"] UTF8String],
        RTLD_NOW);
    void *sk = dlopen(
        [[dev stringByAppendingString:
                  @"/Library/PrivateFrameworks/SimulatorKit.framework/SimulatorKit"] UTF8String],
        RTLD_NOW);
    NSError *err = nil;
    id ctx = [NSClassFromString(@"SimServiceContext") sharedServiceContextForDeveloperDir:dev
                                                                                    error:&err];
    id set = [ctx defaultDeviceSetWithError:&err];
    id device = nil;
    for (id d in [set availableDevices])
      if ([[[d UDID] UUIDString] isEqualToString:@(argv[1])])
        device = d;
    if (!device || !sk) {
      NSLog(@"Simulator device or framework missing");
      return 1;
    }
    id client = [[NSClassFromString(@"_TtC12SimulatorKit24SimDeviceLegacyHIDClient") alloc]
        initWithDevice:device
                 error:&err];
    if (!client) {
      NSLog(@"client error %@", err);
      return 1;
    }
    void *(*mouse)(CGPoint *, CGPoint *, unsigned long, unsigned long, CGSize, unsigned long) =
        dlsym(sk, "IndigoHIDMessageForMouseNSEvent");

    void *io = dlopen("/System/Library/Frameworks/IOKit.framework/IOKit", RTLD_NOW);
    CFTypeRef (*parent)(CFAllocatorRef,
                        uint64_t,
                        uint32_t,
                        uint32_t,
                        uint32_t,
                        uint32_t,
                        uint32_t,
                        double,
                        double,
                        double,
                        double,
                        double,
                        uint32_t,
                        uint32_t,
                        uint32_t) = dlsym(io, "IOHIDEventCreateDigitizerEvent");
    CFTypeRef (*finger)(CFAllocatorRef,
                        uint64_t,
                        uint32_t,
                        uint32_t,
                        uint32_t,
                        double,
                        double,
                        double,
                        double,
                        double,
                        uint32_t,
                        uint32_t,
                        uint32_t) = dlsym(io, "IOHIDEventCreateDigitizerFingerEvent");
    void (*append)(CFTypeRef, CFTypeRef, uint32_t) = dlsym(io, "IOHIDEventAppendEvent");
    void *(*wrap)(CFTypeRef) = dlsym(sk, "IndigoHIDMessageForTrackpadEventFromHIDEventRef");
    NSData *data = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
    if (!mouse || !parent || !finger || !append || !wrap) {
      NSLog(@"required SimulatorKit/IOKit symbols missing");
      return 1;
    }
    NSArray *events = [NSJSONSerialization JSONObjectWithData:data options:0 error:&err];
    if (![events isKindOfClass:NSArray.class]) {
      NSLog(@"invalid input: %@", err);
      return 1;
    }
    void *(*key)(uint32_t, uint32_t) = dlsym(sk, "IndigoHIDMessageForKeyboardArbitrary");
    for (NSDictionary *e in events) {
      usleep([e[@"wait"] doubleValue] * 1000000);
      if (e[@"key"]) {
        void *msg = key([e[@"key"] unsignedIntValue], [e[@"phase"] unsignedIntValue]);
        [client sendWithMessage:msg freeWhenDone:YES completionQueue:nil completion:nil];
        continue;
      }
      NSArray *points = e[@"points"];
      int phase = [e[@"phase"] intValue];
      if (points.count < 1 || points.count > 4 || !(phase == 1 || phase == 2 || phase == 6)) {
        NSLog(@"invalid contact count or phase");
        return 1;
      }
      for (NSArray *point in points) {
        if (point.count != 2 || [point[0] doubleValue] < 0 || [point[0] doubleValue] > 1 ||
            [point[1] doubleValue] < 0 || [point[1] doubleValue] > 1)
        {
          NSLog(@"invalid normalized point");
          return 1;
        }
      }
      void *msg = NULL;
      if ([points count] <= 2) {
        CGPoint p = {[points[0][0] doubleValue], [points[0][1] doubleValue]};
        CGPoint q = CGPointZero;
        if (points.count == 2)
          q = CGPointMake([points[1][0] doubleValue], [points[1][1] doubleValue]);
        msg = mouse(&p, points.count == 2 ? &q : NULL, 0x32, phase, CGSizeMake(1, 1), 0);
      }
      else {
        uint64_t ts = mach_absolute_time();
        uint32_t active = phase == 2 ? 0 : 1, mask = phase == 2 ? 6 : 7;
        CFTypeRef group = parent(NULL, ts, 2, 0, 1, mask, 0, 0, 0, 0, 0, 0, active, active, 0);
        for (NSUInteger i = 0; i < points.count; i++) {
          CFTypeRef f = finger(NULL,
                               ts,
                               (uint32_t)i,
                               (uint32_t)i + 1,
                               mask,
                               [points[i][0] doubleValue],
                               [points[i][1] doubleValue],
                               0,
                               0,
                               0,
                               active,
                               active,
                               0);
          append(group, f, 0);
          CFRelease(f);
        }
        msg = wrap(group);
        CFRelease(group);
        if (msg && malloc_size(msg) >= 0x70) {
          *(uint32_t *)((char *)msg + 0x6c) = 0x32;
        }
        else {
          NSLog(@"invalid digitizer message");
          return 2;
        }
      }
      if (!msg) {
        NSLog(@"no message");
        return 2;
      }
      [client sendWithMessage:msg freeWhenDone:YES completionQueue:nil completion:nil];
    }
    usleep(200000);
  }
}
