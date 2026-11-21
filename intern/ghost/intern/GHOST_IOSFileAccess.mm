/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Native iOS file-location picker controls.
 */

#include "GHOST_IOSFileAccess.hh"

#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <os/log.h>

#include <cstring>

static NSString *const GHOST_IOSFileLocationDidGrantAccess =
    @"GHOST_IOSFileLocationDidGrantAccess";

static os_log_t GHOST_IOS_file_access_log()
{
  static os_log_t log = os_log_create("org.blenderfoundation.blender.ios", "FolderAccess");
  return log;
}

@interface GHOSTIOSFileAccessControls : NSObject <UIDocumentPickerDelegate>
{
  UIButton *button_;
  UIViewController *view_controller_;
  UIDocumentPickerViewController *picker_;
  BOOL picker_is_presented_;
}

- (instancetype)initWithInputView:(UIView *)input_view
                   viewController:(UIViewController *)view_controller
                      closeButton:(UIButton *)close_button;
- (BOOL)containsView:(UIView *)view;
- (void)invalidate;

@end

@implementation GHOSTIOSFileAccessControls

- (instancetype)initWithInputView:(UIView *)input_view
                   viewController:(UIViewController *)view_controller
                      closeButton:(UIButton *)close_button
{
  self = [super init];
  if (self == nil) {
    return nil;
  }

  view_controller_ = view_controller;
  picker_ = nil;
  picker_is_presented_ = NO;
  button_ = [[UIButton buttonWithType:UIButtonTypeSystem] retain];
  button_.translatesAutoresizingMaskIntoConstraints = NO;
  /* The picker only accepts folders, so name the button for what it adds. People who expected to
   * pick a file to import found everything greyed out. The gesture guide says the same. */
  button_.accessibilityLabel = @"Add Folder";
  button_.toolTip = @"Add Folder";
  button_.accessibilityHint = @"Choose a folder in the Files app so Blender can open and save "
                              @"files there";
  button_.accessibilityIdentifier = @"blender_file_browser_add_location";
  button_.tintColor = UIColor.whiteColor;

  UIImageSymbolConfiguration *symbol_configuration = [UIImageSymbolConfiguration
      configurationWithPointSize:14.0f
                          weight:UIImageSymbolWeightSemibold];
  UIImage *image = [UIImage systemImageNamed:@"folder.badge.plus"
                           withConfiguration:symbol_configuration];

  if (@available(iOS 26.0, *)) {
    UIButtonConfiguration *configuration = [UIButtonConfiguration glassButtonConfiguration];
    configuration.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
    configuration.baseForegroundColor = UIColor.whiteColor;
    configuration.image = image;
    button_.configuration = configuration;
  }
  else {
    button_.backgroundColor = [UIColor colorWithWhite:0.0f alpha:0.65f];
    button_.layer.cornerRadius = 22.0f;
    [button_ setImage:image forState:UIControlStateNormal];
  }

  [button_ addTarget:self
                action:@selector(showFolderPicker)
      forControlEvents:UIControlEventTouchUpInside];
  [input_view addSubview:button_];

  [NSLayoutConstraint activateConstraints:@[
    [button_.widthAnchor constraintEqualToConstant:44.0f],
    [button_.heightAnchor constraintEqualToConstant:44.0f],
    [button_.centerYAnchor constraintEqualToAnchor:close_button.centerYAnchor],
    [button_.trailingAnchor constraintEqualToAnchor:close_button.leadingAnchor constant:-8.0f],
  ]];

  return self;
}

- (void)showFolderPicker
{
  if (picker_is_presented_ || view_controller_ == nil ||
      view_controller_.presentedViewController != nil)
  {
    os_log(GHOST_IOS_file_access_log(),
           "Picker presentation skipped: active=%{public}d host=%{public}d presented=%{public}d",
           picker_is_presented_,
           view_controller_ != nil,
           view_controller_.presentedViewController != nil);
    return;
  }

  /* The system dismisses a completed document picker after its delegate returns.
   * Retain that host until the next presentation so its remote Files view can
   * finish the handoff before we clear the weak delegate. */
  if (picker_ != nil) {
    picker_.delegate = nil;
    [picker_ release];
    picker_ = nil;
  }

  picker_ = [[UIDocumentPickerViewController alloc] initForOpeningContentTypes:@[ UTTypeFolder ]
                                                                        asCopy:NO];
  picker_.delegate = self;
  picker_.allowsMultipleSelection = NO;
  picker_.modalPresentationStyle = UIModalPresentationFormSheet;
  picker_is_presented_ = YES;
  os_log(GHOST_IOS_file_access_log(), "Presenting folder picker");
  [view_controller_ presentViewController:picker_
                                 animated:YES
                               completion:^{
                                 os_log(GHOST_IOS_file_access_log(),
                                        "Folder picker presentation completed");
                               }];
}

- (void)documentPicker:(UIDocumentPickerViewController *)controller
    didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls
{
  os_log(GHOST_IOS_file_access_log(),
         "Folder picker delegate entered: count=%{public}lu matches=%{public}d main=%{public}d",
         (unsigned long)urls.count,
         controller == picker_,
         NSThread.isMainThread);
  NSUInteger granted_count = 0;
  for (NSURL *url in urls) {
    if (url.isFileURL) {
      [[NSNotificationCenter defaultCenter]
          postNotificationName:GHOST_IOSFileLocationDidGrantAccess
                        object:url];
      granted_count++;
    }
  }

  if (controller == picker_) {
    picker_is_presented_ = NO;
  }
  os_log(GHOST_IOS_file_access_log(),
         "Folder picker delegate returning: grants=%{public}lu",
         (unsigned long)granted_count);
}

- (void)documentPickerWasCancelled:(UIDocumentPickerViewController *)controller
{
  os_log(GHOST_IOS_file_access_log(),
         "Folder picker cancelled: matches=%{public}d",
         controller == picker_);
  if (controller == picker_) {
    picker_is_presented_ = NO;
  }
}

- (BOOL)containsView:(UIView *)view
{
  return button_ != nil && (view == button_ || [view isDescendantOfView:button_]);
}

- (void)invalidate
{
  if (picker_is_presented_) {
    os_log(GHOST_IOS_file_access_log(), "Folder picker owner invalidated while active");
  }
  if (picker_ != nil) {
    UIDocumentPickerViewController *picker = picker_;
    picker_ = nil;
    picker_is_presented_ = NO;
    picker.delegate = nil;
    if (picker.presentingViewController != nil) {
      [picker dismissViewControllerAnimated:NO
                                 completion:^{
                                   [picker release];
                                 }];
    }
    else {
      [picker release];
    }
  }

  if (button_ != nil) {
    [button_ removeTarget:self
                   action:@selector(showFolderPicker)
         forControlEvents:UIControlEventTouchUpInside];
    [button_ removeFromSuperview];
    [button_ release];
    button_ = nil;
  }
  view_controller_ = nil;
}

- (void)dealloc
{
  [self invalidate];
  [super dealloc];
}

@end

NSObject *GHOST_IOSFileAccess_createControls(UIView *input_view,
                                             UIViewController *view_controller,
                                             UIButton *close_button,
                                             const char *window_title)
{
  const bool is_file_browser = window_title != nullptr &&
                               (strcmp(window_title, "Blender File View") == 0 ||
                                strcmp(window_title, "File Browser") == 0);
  if (input_view == nil || view_controller == nil || close_button == nil || !is_file_browser) {
    return nil;
  }

  return [[GHOSTIOSFileAccessControls alloc] initWithInputView:input_view
                                                viewController:view_controller
                                                   closeButton:close_button];
}

void GHOST_IOSFileAccess_destroyControls(NSObject *controls)
{
  if (controls == nil) {
    return;
  }
  GHOSTIOSFileAccessControls *file_controls = (GHOSTIOSFileAccessControls *)controls;
  [file_controls invalidate];
  [file_controls release];
}

bool GHOST_IOSFileAccess_containsView(NSObject *controls, UIView *view)
{
  if (controls == nil || view == nil) {
    return false;
  }
  return [(GHOSTIOSFileAccessControls *)controls containsView:view] == YES;
}
