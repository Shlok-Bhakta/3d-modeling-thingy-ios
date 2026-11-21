/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * First-launch guide to the iPad gestures, Pencil and on-screen keys.
 *
 * The guide is a modal sheet over the main window, so touches, the pointer and hardware keys go
 * to it instead of Blender until it is finished or skipped. Which launches show it is decided in
 * #GHOST_IOSOnboarding_shouldPresent; this file is only the view.
 */

#import <UIKit/UIKit.h>

#include "GHOST_IOSOnboarding.hh"
#include "GHOST_IOSOnboardingState.hh"

static NSString *const GHOST_IOSOnboardingCompletedVersion = @"GHOST_IOSOnboardingCompletedVersion";

/** How long to keep waiting for the main window to be on screen with nothing presented. */
static constexpr int present_attempts = 60;
static constexpr double present_retry_seconds = 0.5;
static constexpr CGFloat card_max_width = 560.0f;
static constexpr CGFloat card_padding = 28.0f;

struct GHOST_IOSOnboardingRow {
  NSString *symbol;
  NSString *gesture;
  NSString *action;
};

struct GHOST_IOSOnboardingPageInfo {
  NSString *title;
  /** Optional, nil hides it. */
  NSString *subtitle;
  GHOST_IOSOnboardingRow rows[5];
  int row_count;
};

static const GHOST_IOSOnboardingPageInfo GHOST_IOS_ONBOARDING_PAGES[GHOST_IOS_ONBOARDING_PAGE_COUNT] =
    {
        {@"Cursor",
         @"Drag anywhere to move the cursor, tap to click.",
         {
             {@"hand.point.up.left", @"One-finger drag", @"Move cursor"},
             {@"hand.tap", @"Tap", @"Left-click"},
             {@"hand.draw", @"Double-tap and drag", @"Click and drag (box select, gizmos, sliders)"},
             {@"hand.tap.fill", @"Triple-tap", @"Double-click"},
             {@"contextualmenu.and.cursorarrow", @"Two-finger hold", @"Right-click"},
         },
         5},
        {@"Navigation",
         @"Acts on whichever editor the cursor is over.",
         {
             {@"rotate.3d", @"Two-finger drag", @"Orbit view / scroll lists"},
             {@"hand.pinch", @"Pinch", @"Zoom"},
             {@"arrow.up.and.down.and.arrow.left.and.right", @"Three-finger drag", @"Pan"},
         },
         3},
        {@"Shortcuts",
         nil,
         {
             {@"arrow.uturn.backward", @"Two-finger tap", @"Undo"},
             {@"arrow.uturn.forward", @"Three-finger tap", @"Redo"},
             {@"magnifyingglass", @"Four-finger tap", @"Search (F3)"},
         },
         3},
        {@"Input & Files",
         nil,
         {
             {@"keyboard", @"Modifier keys",
              @"Tap the keyboard button in the corner for Shift, Ctrl, Alt, and Cmd. Tap once for "
              @"one click, twice to lock."},
             {@"applepencil", @"Apple Pencil",
              @"Draws, sculpts, and paints directly under the tip with pressure."},
             {@"computermouse", @"Keyboard, mouse, trackpad", @"Works the same as desktop Blender."},
             {@"folder.badge.plus", @"Files",
              @"Tap the folder button in a file browser to add a folder from the Files app."},
         },
         4},
};

static UIColor *GHOST_IOSOnboardingAccent()
{
  /* Blender's orange. */
  return [UIColor colorWithRed:0.91f green:0.49f blue:0.05f alpha:1.0f];
}

static UIImage *GHOST_IOSOnboardingSymbol(NSString *name)
{
  UIImageSymbolConfiguration *config = [UIImageSymbolConfiguration
      configurationWithPointSize:22.0f
                          weight:UIImageSymbolWeightMedium];
  UIImage *image = [UIImage systemImageNamed:name withConfiguration:config];
  return image != nil ? image : [UIImage systemImageNamed:@"hand.tap" withConfiguration:config];
}

static UILabel *GHOST_IOSOnboardingLabel(UIFontTextStyle style, UIColor *color)
{
  UILabel *label = [[[UILabel alloc] init] autorelease];
  label.font = [UIFont preferredFontForTextStyle:style];
  label.adjustsFontForContentSizeCategory = YES;
  label.textColor = color;
  label.numberOfLines = 0;
  [label setContentCompressionResistancePriority:UILayoutPriorityRequired
                                         forAxis:UILayoutConstraintAxisVertical];
  return label;
}

static UIButton *GHOST_IOSOnboardingButton(NSString *title,
                                           NSString *identifier,
                                           const bool filled,
                                           id target,
                                           SEL action)
{
  UIButtonConfiguration *config = filled ? [UIButtonConfiguration filledButtonConfiguration] :
                                           [UIButtonConfiguration plainButtonConfiguration];
  config.title = title;
  config.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
  config.baseBackgroundColor = GHOST_IOSOnboardingAccent();
  config.baseForegroundColor = filled ? UIColor.whiteColor : UIColor.secondaryLabelColor;
  UIButton *button = [UIButton buttonWithConfiguration:config primaryAction:nil];
  button.accessibilityIdentifier = identifier;
  [button addTarget:target action:action forControlEvents:UIControlEventTouchUpInside];
  return button;
}

/**
 * Stack views lose track of an arranged subview when `hidden` is set to its current value,
 * especially inside an animation. The button then keeps a stale frame outside the card.
 */
static void GHOST_IOSOnboardingSetHidden(UIView *view, const bool hidden)
{
  if (bool(view.hidden) != hidden) {
    view.hidden = hidden;
  }
}

/* -------------------------------------------------------------------- */
/** \name Guide
 * \{ */

@interface GHOSTIOSOnboardingViewController : UIViewController {
  int page_;
  UIView *card_;
  /** A fixed width, so multi-line labels wrap instead of truncating to one line. */
  NSLayoutConstraint *card_width_;
  UILabel *title_;
  UILabel *subtitle_;
  UIStackView *content_;
  UIStackView *rows_;
  UIPageControl *dots_;
  UIButton *skip_;
  UIButton *back_;
  UIButton *next_;
  UIButton *done_;
}
@end

@implementation GHOSTIOSOnboardingViewController

- (instancetype)init
{
  self = [super initWithNibName:nil bundle:nil];
  if (self == nil) {
    return nil;
  }
  page_ = 0;
  self.modalPresentationStyle = UIModalPresentationOverFullScreen;
  self.modalTransitionStyle = UIModalTransitionStyleCrossDissolve;
  self.overrideUserInterfaceStyle = UIUserInterfaceStyleDark;
  return self;
}

- (void)dealloc
{
  [card_ release];
  [card_width_ release];
  [title_ release];
  [subtitle_ release];
  [content_ release];
  [rows_ release];
  [dots_ release];
  [skip_ release];
  [back_ release];
  [next_ release];
  [done_ release];
  [super dealloc];
}

- (void)viewDidLoad
{
  [super viewDidLoad];
  UIView *root = self.view;
  /* The backdrop takes every touch so nothing reaches Blender behind the guide. */
  root.backgroundColor = [UIColor colorWithWhite:0.0f alpha:0.6f];
  root.accessibilityViewIsModal = YES;

  card_ = [[UIView alloc] init];
  card_.translatesAutoresizingMaskIntoConstraints = NO;
  card_.backgroundColor = [UIColor colorWithWhite:0.13f alpha:0.98f];
  card_.layer.cornerRadius = 24.0f;
  card_.layer.cornerCurve = kCACornerCurveContinuous;
  card_.accessibilityIdentifier = @"blender_onboarding";
  [root addSubview:card_];

  title_ = [GHOST_IOSOnboardingLabel(UIFontTextStyleTitle1, UIColor.labelColor) retain];
  title_.font = [UIFont systemFontOfSize:title_.font.pointSize weight:UIFontWeightBold];
  title_.accessibilityTraits = UIAccessibilityTraitHeader;
  subtitle_ = [GHOST_IOSOnboardingLabel(UIFontTextStyleBody, UIColor.secondaryLabelColor) retain];

  rows_ = [[UIStackView alloc] init];
  rows_.axis = UILayoutConstraintAxisVertical;
  rows_.spacing = 18.0f;

  dots_ = [[UIPageControl alloc] init];
  dots_.numberOfPages = GHOST_IOS_ONBOARDING_PAGE_COUNT;
  dots_.userInteractionEnabled = NO;
  dots_.currentPageIndicatorTintColor = GHOST_IOSOnboardingAccent();
  dots_.pageIndicatorTintColor = UIColor.tertiaryLabelColor;

  skip_ = [GHOST_IOSOnboardingButton(
      @"Skip", @"blender_onboarding_skip", false, self, @selector(finish)) retain];
  back_ = [GHOST_IOSOnboardingButton(
      @"Back", @"blender_onboarding_back", false, self, @selector(back)) retain];
  next_ = [GHOST_IOSOnboardingButton(
      @"Next", @"blender_onboarding_next", true, self, @selector(next)) retain];
  done_ = [GHOST_IOSOnboardingButton(
      @"Done", @"blender_onboarding_done", true, self, @selector(finish)) retain];

  UIView *spacer = [[[UIView alloc] init] autorelease];
  UIStackView *buttons = [[[UIStackView alloc]
      initWithArrangedSubviews:@[ skip_, spacer, back_, next_, done_ ]] autorelease];
  buttons.axis = UILayoutConstraintAxisHorizontal;
  buttons.alignment = UIStackViewAlignmentCenter;
  buttons.spacing = 8.0f;

  content_ = [[UIStackView alloc]
      initWithArrangedSubviews:@[ title_, subtitle_, rows_, dots_, buttons ]];
  content_.translatesAutoresizingMaskIntoConstraints = NO;
  content_.axis = UILayoutConstraintAxisVertical;
  content_.spacing = 12.0f;
  [content_ setCustomSpacing:28.0f afterView:subtitle_];
  [content_ setCustomSpacing:24.0f afterView:rows_];
  [card_ addSubview:content_];

  UILayoutGuide *safe_area = root.safeAreaLayoutGuide;
  card_width_ = [[card_.widthAnchor constraintEqualToConstant:card_max_width] retain];
  [NSLayoutConstraint activateConstraints:@[
    [card_.centerXAnchor constraintEqualToAnchor:safe_area.centerXAnchor],
    [card_.centerYAnchor constraintEqualToAnchor:safe_area.centerYAnchor],
    card_width_,
    [card_.topAnchor constraintGreaterThanOrEqualToAnchor:safe_area.topAnchor constant:16.0f],
    [card_.bottomAnchor constraintLessThanOrEqualToAnchor:safe_area.bottomAnchor
                                                 constant:-16.0f],
    [content_.topAnchor constraintEqualToAnchor:card_.topAnchor constant:card_padding],
    [content_.bottomAnchor constraintEqualToAnchor:card_.bottomAnchor constant:-card_padding],
    [content_.leadingAnchor constraintEqualToAnchor:card_.leadingAnchor constant:card_padding],
    [content_.trailingAnchor constraintEqualToAnchor:card_.trailingAnchor
                                            constant:-card_padding],
  ]];

  [self showPage];
}

- (void)viewWillLayoutSubviews
{
  [super viewWillLayoutSubviews];
  const CGFloat available = CGRectGetWidth(self.view.safeAreaLayoutGuide.layoutFrame) - 32.0f;
  card_width_.constant = MIN(card_max_width, MAX(available, 0.0f));
}

- (UIView *)rowView:(const GHOST_IOSOnboardingRow &)row
{
  UIImageView *icon = [[[UIImageView alloc]
      initWithImage:GHOST_IOSOnboardingSymbol(row.symbol)] autorelease];
  icon.translatesAutoresizingMaskIntoConstraints = NO;
  icon.contentMode = UIViewContentModeCenter;
  icon.tintColor = GHOST_IOSOnboardingAccent();
  [icon.widthAnchor constraintEqualToConstant:36.0f].active = YES;

  UILabel *gesture = GHOST_IOSOnboardingLabel(UIFontTextStyleHeadline, UIColor.labelColor);
  gesture.text = row.gesture;
  UILabel *action = GHOST_IOSOnboardingLabel(UIFontTextStyleSubheadline,
                                             UIColor.secondaryLabelColor);
  action.text = row.action;
  UIStackView *text = [[[UIStackView alloc] initWithArrangedSubviews:@[ gesture, action ]]
      autorelease];
  text.axis = UILayoutConstraintAxisVertical;
  text.spacing = 2.0f;

  UIStackView *line = [[[UIStackView alloc] initWithArrangedSubviews:@[ icon, text ]]
      autorelease];
  line.axis = UILayoutConstraintAxisHorizontal;
  line.alignment = UIStackViewAlignmentTop;
  line.spacing = 14.0f;
  line.isAccessibilityElement = YES;
  line.accessibilityLabel = [NSString stringWithFormat:@"%@: %@", row.gesture, row.action];
  return line;
}

- (void)showPage
{
  const GHOST_IOSOnboardingPageInfo &info = GHOST_IOS_ONBOARDING_PAGES[page_];
  title_.text = info.title;
  subtitle_.text = info.subtitle;
  GHOST_IOSOnboardingSetHidden(subtitle_, info.subtitle == nil);
  /* Without a subtitle, keep the gap that would have followed it under the title. */
  [content_ setCustomSpacing:info.subtitle == nil ? 28.0f : 12.0f afterView:title_];
  for (UIView *view in [[rows_.arrangedSubviews copy] autorelease]) {
    [rows_ removeArrangedSubview:view];
    [view removeFromSuperview];
  }
  for (int i = 0; i < info.row_count; i++) {
    [rows_ addArrangedSubview:[self rowView:info.rows[i]]];
  }
  const bool last = page_ == GHOST_IOS_ONBOARDING_PAGE_COUNT - 1;
  dots_.currentPage = page_;
  GHOST_IOSOnboardingSetHidden(skip_, last);
  GHOST_IOSOnboardingSetHidden(back_, page_ == 0);
  GHOST_IOSOnboardingSetHidden(next_, last);
  GHOST_IOSOnboardingSetHidden(done_, !last);
  [card_ layoutIfNeeded];
  UIAccessibilityPostNotification(UIAccessibilityScreenChangedNotification, title_);
}

- (void)step:(const int)step
{
  const int page = GHOST_IOSOnboarding_stepPage(page_, step);
  if (page == page_) {
    return;
  }
  /* Swap pages without an animation. A transition blocks taps on the card while it runs and
   * lays out the stack views from a snapshot. */
  page_ = page;
  [self showPage];
}

- (void)next
{
  [self step:1];
}

- (void)back
{
  [self step:-1];
}

- (void)finish
{
  [NSUserDefaults.standardUserDefaults setInteger:GHOST_IOS_ONBOARDING_VERSION
                                           forKey:GHOST_IOSOnboardingCompletedVersion];
  UIWindow *window = self.presentingViewController.view.window;
  [self dismissViewControllerAnimated:YES
                           completion:^{
                             /* Hardware keys go to the window again. */
                             [window becomeFirstResponder];
                           }];
}

/* Take hardware keys from Blender while the guide is open. */
- (BOOL)canBecomeFirstResponder
{
  return YES;
}

- (void)viewDidAppear:(BOOL)animated
{
  [super viewDidAppear:animated];
  [self becomeFirstResponder];
}

- (NSArray<UIKeyCommand *> *)keyCommands
{
  const bool last = page_ == GHOST_IOS_ONBOARDING_PAGE_COUNT - 1;
  return @[
    [UIKeyCommand keyCommandWithInput:@"\r" modifierFlags:0 action:last ? @selector(finish) :
                                                                          @selector(next)],
    [UIKeyCommand keyCommandWithInput:UIKeyInputRightArrow modifierFlags:0 action:@selector(next)],
    [UIKeyCommand keyCommandWithInput:UIKeyInputLeftArrow modifierFlags:0 action:@selector(back)],
    [UIKeyCommand keyCommandWithInput:UIKeyInputEscape modifierFlags:0 action:@selector(finish)],
  ];
}

/* Unmatched keys stop here instead of reaching Blender. */
- (void)pressesBegan:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event
{
  (void)presses;
  (void)event;
}

- (void)pressesEnded:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event
{
  (void)presses;
  (void)event;
}

@end

/** \} */

static void GHOST_IOSOnboarding_presentWhenReady(UIViewController *root, const int attempts)
{
  dispatch_after(
      dispatch_time(DISPATCH_TIME_NOW, int64_t(present_retry_seconds * NSEC_PER_SEC)),
      dispatch_get_main_queue(),
      ^{
        /* Wait until the window is on screen and nothing else, such as a file picker, is up. */
        if (root.view.window == nil || root.presentedViewController != nil) {
          if (attempts > 1) {
            GHOST_IOSOnboarding_presentWhenReady(root, attempts - 1);
          }
          return;
        }
        GHOSTIOSOnboardingViewController *guide = [[GHOSTIOSOnboardingViewController alloc] init];
        [root presentViewController:guide animated:YES completion:nil];
        [guide release];
      });
}

void GHOST_IOSOnboarding_presentIfNeeded(UIViewController *root)
{
  if (root == nil) {
    return;
  }
  NSProcessInfo *process = NSProcessInfo.processInfo;
  const bool forced = [process.environment[@"BLENDER_IOS_ONBOARDING"] isEqualToString:@"1"];
  const int completed = int(
      [NSUserDefaults.standardUserDefaults integerForKey:GHOST_IOSOnboardingCompletedVersion]);
  if (!GHOST_IOSOnboarding_shouldPresent(completed, process.arguments.count > 1, forced)) {
    return;
  }
  GHOST_IOSOnboarding_presentWhenReady(root, present_attempts);
}
