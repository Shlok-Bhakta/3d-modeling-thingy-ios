/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Test-only Simulator drag source. Adds a small view to Blender's window that offers one
 * file through a real UIDragInteraction, so a HID touch drag reaches Blender's drop target
 * the way a drag from the Files app does. It never calls into Blender.
 *
 * BLENDER_DROP_SOURCE_FILE: the file to offer.
 * BLENDER_DROP_SOURCE_MODE: "in-place" offers the file itself, "copy" makes UIKit hand
 *                           the receiver a temporary copy, like a drag from Photos.
 * BLENDER_DROP_SOURCE_REPORT: where to write the view's center, normalized to the screen,
 *                             and whether a drag session began and how it ended. */
#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

@interface FileDropSource : NSObject <UIDragInteractionDelegate>
@property(nonatomic, copy) NSURL *url;
@property(nonatomic) BOOL inPlace;
@property(nonatomic, strong) NSMutableDictionary *state;
- (void)report:(NSDictionary *)values;
@end

@implementation FileDropSource
- (NSArray<UIDragItem *> *)dragInteraction:(UIDragInteraction *)interaction
                  itemsForBeginningSession:(id<UIDragSession>)session
{
  NSURL *url = self.url;
  const BOOL in_place = self.inPlace;
  FileDropSource *source = self;
  UTType *type = [UTType typeWithFilenameExtension:url.pathExtension] ?: UTTypeData;
  NSItemProvider *provider = [[NSItemProvider alloc] init];
  provider.suggestedName = url.lastPathComponent.stringByDeletingPathExtension;
  [provider registerFileRepresentationForTypeIdentifier:type.identifier
                                            fileOptions:in_place ?
                                                            NSItemProviderFileOptionOpenInPlace :
                                                            0
                                             visibility:NSItemProviderRepresentationVisibilityAll
                                            loadHandler:^NSProgress *(
                                                void (^completion)(NSURL *, BOOL, NSError *)) {
                                              dispatch_async(dispatch_get_main_queue(), ^{
                                                [source report:@{@"loaded" : @YES}];
                                              });
                                              completion(url, in_place, nil);
                                              return nil;
                                            }];
  return @[ [[UIDragItem alloc] initWithItemProvider:provider] ];
}

- (void)dragInteraction:(UIDragInteraction *)interaction sessionWillBegin:(id<UIDragSession>)session
{
  [self report:@{@"began" : @YES}];
}

- (void)dragInteraction:(UIDragInteraction *)interaction
                session:(id<UIDragSession>)session
    didEndWithOperation:(UIDropOperation)operation
{
  [self report:@{@"ended" : operation == UIDropOperationCopy ? @"copy" : @(operation).stringValue}];
}

- (void)report:(NSDictionary *)values
{
  [self.state addEntriesFromDictionary:values];
  NSData *data = [NSJSONSerialization dataWithJSONObject:self.state options:0 error:nil];
  [data writeToFile:NSProcessInfo.processInfo.environment[@"BLENDER_DROP_SOURCE_REPORT"]
         atomically:YES];
}
@end

static FileDropSource *drop_source;

static void install_source(void)
{
  NSDictionary *environment = NSProcessInfo.processInfo.environment;
  UIWindow *window = nil;
  for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
    if (![scene isKindOfClass:UIWindowScene.class]) {
      continue;
    }
    for (UIWindow *candidate in ((UIWindowScene *)scene).windows) {
      if ([NSStringFromClass(candidate.class) isEqualToString:@"GHOSTUIWindow"]) {
        window = candidate;
      }
    }
  }
  if (window == nil || window.bounds.size.width < 1) {
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC / 2),
                   dispatch_get_main_queue(),
                   ^{ install_source(); });
    return;
  }

  drop_source = [[FileDropSource alloc] init];
  drop_source.url = [NSURL fileURLWithPath:environment[@"BLENDER_DROP_SOURCE_FILE"]];
  drop_source.inPlace = [environment[@"BLENDER_DROP_SOURCE_MODE"] isEqualToString:@"in-place"];

  const CGSize size = window.bounds.size;
  UIView *chip = [[UIView alloc]
      initWithFrame:CGRectMake(size.width * 0.06, size.height * 0.62, 120.0, 120.0)];
  chip.backgroundColor = UIColor.systemOrangeColor;
  chip.layer.cornerRadius = 16.0;
  chip.accessibilityIdentifier = @"blender_test_drop_source";
  UIDragInteraction *interaction = [[UIDragInteraction alloc] initWithDelegate:drop_source];
  interaction.enabled = YES;
  [chip addInteraction:interaction];
  [window addSubview:chip];

  const CGRect frame = [window convertRect:chip.frame toCoordinateSpace:window.screen.coordinateSpace];
  const CGSize screen = window.screen.bounds.size;
  drop_source.state = [NSMutableDictionary dictionary];
  [drop_source report:@{
    @"pid" : @(NSProcessInfo.processInfo.processIdentifier),
    @"center" : @[ @(CGRectGetMidX(frame) / screen.width), @(CGRectGetMidY(frame) / screen.height) ],
  }];
}

__attribute__((constructor)) static void start_drop_source(void)
{
  dispatch_async(dispatch_get_main_queue(), ^{ install_source(); });
}
