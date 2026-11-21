/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Runs the production iOS menu shim against Foundation on macOS. Only Blender's
 * menu/notifier boundary is substituted; URLs, bookmarks and defaults are real.
 * The simulator test covers that boundary with the full app and UIKit. */
#include "../../../source/blender/editors/space_file/fsmenu_system_ios.mm"

#include <atomic>
#include <cstdio>
#import <objc/runtime.h>
#include <set>
#include <string>

static std::set<std::string> menu_paths;
static int notifications = 0;
static std::atomic<bool> provider_entered{false};
static dispatch_semaphore_t provider_release;
static bool hold_access = false;
static bool hold_resolution = false;
static IMP original_creation;
static IMP original_resolution;
static IMP original_start_access;
static std::atomic<bool> scope_started{false};
static std::atomic<bool> scope_started_on_main{false};
static NSUserDefaults *test_defaults;

static void require(bool condition, const char *message)
{
  if (!condition) {
    fprintf(stderr, "FAIL: %s\n", message);
    _Exit(1);
  }
}

namespace blender {
struct FSMenu {};
FSMenu *ED_fsmenu_get()
{
  require(NSThread.isMainThread, "menu accessed off the main thread");
  static FSMenu menu;
  return &menu;
}
void fsmenu_insert_entry(
    FSMenu *, FSMenuCategory, const char *path, const char *, int, FSMenuInsert)
{
  require(NSThread.isMainThread, "menu modified off the main thread");
  menu_paths.insert(path);
}
void WM_main_add_notifier(uint, void *)
{
  require(NSThread.isMainThread, "notifier added off the main thread");
  notifications++;
}
size_t BLI_snprintf(char *dst, size_t size, const char *format, ...)
{
  va_list args;
  va_start(args, format);
  int result = vsnprintf(dst, size, format, args);
  va_end(args);
  return result;
}
}  // namespace blender

static id create_bookmark(id url,
                          SEL selector,
                          NSURLBookmarkCreationOptions options,
                          NSArray *keys,
                          NSURL *relative,
                          NSError **error)
{
  require(!NSThread.isMainThread, "bookmark creation blocked the main thread");
  using Fn = id (*)(id, SEL, NSURLBookmarkCreationOptions, NSArray *, NSURL *, NSError **);
  return reinterpret_cast<Fn>(original_creation)(url, selector, options, keys, relative, error);
}

static id resolve_bookmark(id cls,
                           SEL selector,
                           NSData *data,
                           NSURLBookmarkResolutionOptions options,
                           NSURL *relative,
                           BOOL *stale,
                           NSError **error)
{
  require(!NSThread.isMainThread, "bookmark restoration blocked the main thread");
  if (hold_resolution) {
    provider_entered = true;
    dispatch_semaphore_wait(provider_release, DISPATCH_TIME_FOREVER);
  }
  using Fn = id (*)(
      id, SEL, NSData *, NSURLBookmarkResolutionOptions, NSURL *, BOOL *, NSError **);
  return reinterpret_cast<Fn>(original_resolution)(
      cls, selector, data, options, relative, stale, error);
}

static BOOL start_access(id url, SEL selector)
{
  scope_started_on_main = NSThread.isMainThread;
  scope_started = true;
  require(!NSThread.isMainThread, "security-scope access blocked the picker callback");
  if (hold_access) {
    provider_entered = true;
    dispatch_semaphore_wait(provider_release, DISPATCH_TIME_FOREVER);
  }
  using Fn = BOOL (*)(id, SEL);
  (void)reinterpret_cast<Fn>(original_start_access)(url, selector);
  /* The temporary-directory fixture has no sandbox extension on macOS. Treat
   * the observed call as a successful claim so production retains the URL. */
  return YES;
}

static void spin_until(const std::function<bool()> &predicate)
{
  NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:10];
  while (!predicate() && deadline.timeIntervalSinceNow > 0) {
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
  }
  require(predicate(), "asynchronous operation did not finish");
}

static void grant(NSURL *url)
{
  [[NSNotificationCenter defaultCenter] postNotificationName:GHOST_IOSFileLocationDidGrantAccess
                                                      object:url];
}

int main(int argc, char **argv)
{
  @autoreleasepool {
    require(argc == 3, "expected mode and temporary directory");
    NSString *suite = [@"org.blender.tests.file-access."
        stringByAppendingString:NSUUID.UUID.UUIDString];
    test_defaults = [[NSUserDefaults alloc] initWithSuiteName:suite];
    Method defaults_method = class_getClassMethod(NSUserDefaults.class,
                                                  @selector(standardUserDefaults));
    method_setImplementation(defaults_method, imp_implementationWithBlock(^id(id) {
                               return test_defaults;
                             }));
    NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[2]] isDirectory:YES];
    url = url.URLByResolvingSymlinksInPath;
    NSData *bookmark = [url bookmarkDataWithOptions:NSURLBookmarkCreationMinimalBookmark
                     includingResourceValuesForKeys:nil
                                      relativeToURL:nil
                                              error:nil];
    require(bookmark != nil, "real fixture bookmark could not be created");
    /* Foundation can resolve /var to /private/var on macOS. Use the same URL
     * spelling for restored and newly granted locations in this fixture. */
    url = [NSURL URLByResolvingBookmarkData:bookmark
                                    options:0
                              relativeToURL:nil
                        bookmarkDataIsStale:nil
                                      error:nil];
    require(url != nil, "real fixture bookmark could not be resolved");
    const bool restore = strcmp(argv[1], "restore") == 0;
    if (restore) {
      [test_defaults setObject:@[ bookmark, @"invalid", [NSData data] ]
                        forKey:IOSFileLocationBookmarksKey];
    }
    provider_release = dispatch_semaphore_create(0);
    Method creation = class_getInstanceMethod(
        NSURL.class,
        @selector(bookmarkDataWithOptions:includingResourceValuesForKeys:relativeToURL:error:));
    original_creation = method_setImplementation(creation, reinterpret_cast<IMP>(create_bookmark));
    Method resolution = class_getClassMethod(
        NSURL.class,
        @selector(URLByResolvingBookmarkData:options:relativeToURL:bookmarkDataIsStale:error:));
    original_resolution = method_setImplementation(resolution,
                                                   reinterpret_cast<IMP>(resolve_bookmark));
    Method start_access_method = class_getInstanceMethod(
        NSURL.class, @selector(startAccessingSecurityScopedResource));
    original_start_access = method_setImplementation(start_access_method,
                                                     reinterpret_cast<IMP>(start_access));
    if (strcmp(argv[1], "file") == 0) {
      /* TestFlight: a .blend chosen in the folder picker was listed as a folder. */
      NSURL *file = [url URLByAppendingPathComponent:@"picked.blend" isDirectory:NO];
      require([[NSData data] writeToURL:file atomically:YES], "fixture file was not written");
      blender::fsmenu_read_system(blender::ED_fsmenu_get(), true);
      grant(file);
      grant(url);
      spin_until([&] { return menu_paths.count(url.path.UTF8String) == 1; });
      /* Grants run in order on one queue, so the file's grant has finished as well. */
      auto persisted = std::make_shared<bool>(false);
      dispatch_async(g_file_location_queue, ^{
        dispatch_async(dispatch_get_main_queue(), ^{
          *persisted = true;
        });
      });
      spin_until([&] { return *persisted; });
      require(menu_paths.count(file.path.UTF8String) == 0, "a picked file was listed as a folder");
      require([test_defaults arrayForKey:IOSFileLocationBookmarksKey].count == 1,
              "a picked file was saved as a folder");
      [test_defaults removePersistentDomainForName:suite];
      fprintf(stdout, "PASS: file, only the folder was added\n");
      return 0;
    }
    hold_access = !restore;
    hold_resolution = restore;
    blender::fsmenu_read_system(blender::ED_fsmenu_get(), true);
    if (!restore) {
      /* Hold the provider queue to prove the picker handoff only enqueues work. */
      dispatch_sync(g_file_location_queue,
                    ^{
                    });
      dispatch_suspend(g_file_location_queue);
      grant(url);
      require(!scope_started.load(),
              "folder grant performed provider work in the picker callback");
      dispatch_resume(g_file_location_queue);
    }
    spin_until([] { return provider_entered.load(); });
    auto main_responsive = std::make_shared<bool>(false);
    dispatch_async(dispatch_get_main_queue(), ^{
      *main_responsive = true;
    });
    spin_until([&] { return *main_responsive; });
    /* Refresh and close/reopen must not synchronously resolve saved grants. */
    menu_paths.clear();
    blender::fsmenu_read_system(blender::ED_fsmenu_get(), true);
    require(!menu_paths.empty(), "Documents disappeared while provider was blocked");
    hold_access = false;
    hold_resolution = false;
    dispatch_semaphore_signal(provider_release);
    spin_until([&] { return notifications > 0 && menu_paths.count(url.path.UTF8String) == 1; });
    require(scope_started.load(), "folder grant never claimed its security scope");
    require(!scope_started_on_main.load(), "folder grant claimed its security scope on main");
    grant(url);
    grant(url);
    spin_until([] { return notifications >= 3; });
    /* A queue barrier waits for persistence without blocking the main queue. */
    auto persisted = std::make_shared<bool>(false);
    dispatch_async(g_file_location_queue, ^{
      dispatch_async(dispatch_get_main_queue(), ^{
        *persisted = true;
      });
    });
    spin_until([&] { return *persisted; });
    NSArray *saved = [test_defaults arrayForKey:IOSFileLocationBookmarksKey];
    require(saved.count == (restore ? 3 : 1), "duplicate grants changed bookmark count");
    require(menu_paths.count(url.path.UTF8String) == 1, "folder missing from System");
    [test_defaults removePersistentDomainForName:suite];
    fprintf(stdout,
            "PASS: %s, provider blocked on worker, main responsive, real bookmarks persisted\n",
            argv[1]);
  }
  return 0;
}
