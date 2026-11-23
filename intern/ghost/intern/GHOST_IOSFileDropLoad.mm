/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup GHOST
 * Load dropped items as local files. Foundation only, so it also runs in macOS tests.
 */

#include "GHOST_IOSFileDrop.hh"

#import <Foundation/Foundation.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <os/log.h>

static os_log_t GHOST_IOS_file_drop_log()
{
  static os_log_t log = os_log_create("org.blenderfoundation.blender.ios", "FileDrop");
  return log;
}

/** Blender may read a dropped file again later, such as a texture or a linked library, so
 * access to files opened in place lasts for the session. */
static NSMutableArray<NSURL *> *IOS_file_drop_scoped_urls()
{
  static NSMutableArray<NSURL *> *urls = [[NSMutableArray alloc] init];
  return urls;
}

static NSString *IOS_file_drop_type(NSItemProvider *provider)
{
  for (NSString *identifier in provider.registeredTypeIdentifiers) {
    UTType *type = [UTType typeWithIdentifier:identifier];
    if (type != nil && [type conformsToType:UTTypeData]) {
      return identifier;
    }
  }
  return nil;
}

/** "name.obj", then "name 2.obj" and so on, like Finder. */
static NSURL *IOS_file_drop_unused_url(NSURL *inbox, NSString *name)
{
  NSFileManager *files = NSFileManager.defaultManager;
  NSString *stem = name.stringByDeletingPathExtension;
  NSString *extension = name.pathExtension;
  NSURL *url = [inbox URLByAppendingPathComponent:name];
  for (int number = 2; [files fileExistsAtPath:url.path]; number++) {
    NSString *numbered = [NSString stringWithFormat:@"%@ %d", stem, number];
    if (extension.length > 0) {
      numbered = [numbered stringByAppendingPathExtension:extension];
    }
    url = [inbox URLByAppendingPathComponent:numbered];
  }
  return url;
}

static NSString *IOS_file_drop_keep_copy(NSURL *url, NSURL *inbox)
{
  /* Completion handlers run concurrently, and two copies must not claim the same name. */
  static NSObject *lock = [[NSObject alloc] init];
  @synchronized(lock) {
    NSFileManager *files = NSFileManager.defaultManager;
    NSError *error = nil;
    if (![files createDirectoryAtURL:inbox
            withIntermediateDirectories:YES
                             attributes:nil
                                  error:&error])
    {
      os_log_error(GHOST_IOS_file_drop_log(),
                   "Could not create the dropped files folder: %{public}@",
                   error.localizedDescription);
      return nil;
    }
    NSURL *destination = IOS_file_drop_unused_url(inbox, url.lastPathComponent);
    if (![files copyItemAtURL:url toURL:destination error:&error]) {
      os_log_error(GHOST_IOS_file_drop_log(),
                   "Could not keep a dropped file: %{public}@",
                   error.localizedDescription);
      return nil;
    }
    return destination.path;
  }
}

static NSString *IOS_file_drop_open(NSURL *url, BOOL is_in_place, NSURL *inbox)
{
  if (url == nil) {
    return nil;
  }
  if (!is_in_place) {
    return IOS_file_drop_keep_copy(url, inbox);
  }
  if ([url startAccessingSecurityScopedResource]) {
    NSMutableArray<NSURL *> *urls = IOS_file_drop_scoped_urls();
    @synchronized(urls) {
      [urls addObject:url];
    }
  }
  return url.path;
}

void GHOST_IOSFileDrop_loadFiles(NSArray<NSItemProvider *> *providers,
                                 NSURL *inbox,
                                 void (^completion)(NSArray<NSString *> *paths))
{
  NSMutableArray *results = [NSMutableArray arrayWithCapacity:providers.count];
  dispatch_group_t group = dispatch_group_create();
  for (NSItemProvider *provider in providers) {
    const NSUInteger index = results.count;
    [results addObject:NSNull.null];
    NSString *type = IOS_file_drop_type(provider);
    if (type == nil) {
      continue;
    }
    dispatch_group_enter(group);
    /* A provider in this process can run its load handler on the calling thread. */
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
      [provider
          loadInPlaceFileRepresentationForTypeIdentifier:type
                                       completionHandler:^(
                                           NSURL *url, BOOL is_in_place, NSError *error) {
                                         NSString *path = IOS_file_drop_open(
                                             url, is_in_place, inbox);
                                         if (path == nil) {
                                           os_log_error(GHOST_IOS_file_drop_log(),
                                                        "Could not load a dropped item: "
                                                        "%{public}@",
                                                        error.localizedDescription);
                                         }
                                         @synchronized(results) {
                                           if (path != nil) {
                                             results[index] = path;
                                           }
                                         }
                                         dispatch_group_leave(group);
                                       }];
    });
  }
  dispatch_group_notify(group, dispatch_get_main_queue(), ^{
    NSMutableArray<NSString *> *paths = [NSMutableArray arrayWithCapacity:results.count];
    for (id path in results) {
      if (path != NSNull.null) {
        [paths addObject:path];
      }
    }
    completion(paths);
  });
  dispatch_release(group);
}

NSURL *GHOST_IOSFileDrop_inbox()
{
  NSURL *documents = [NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory
                                                          inDomains:NSUserDomainMask]
                         .firstObject;
  return [documents URLByAppendingPathComponent:@"Dropped Files" isDirectory:YES];
}
