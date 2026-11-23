/* SPDX-FileCopyrightText: 2026 Blender Authors
 * SPDX-License-Identifier: GPL-2.0-or-later */

/* Runs the production drop loader against Foundation on macOS with real item providers and
 * files. The simulator test covers the UIKit drop interaction and Blender's import. */
#include "../../../intern/ghost/intern/GHOST_IOSFileDropLoad.mm"

#include <cstdio>
#include <cstring>

static void require(bool condition, const char *message)
{
  if (!condition) {
    fprintf(stderr, "FAIL: %s\n", message);
    _Exit(1);
  }
}

static NSItemProvider *file_provider(NSURL *url, NSString *type, BOOL in_place)
{
  NSItemProvider *provider = [[[NSItemProvider alloc] init] autorelease];
  [provider registerFileRepresentationForTypeIdentifier:type
                                            fileOptions:in_place ?
                                                            NSItemProviderFileOptionOpenInPlace :
                                                            0
                                             visibility:NSItemProviderRepresentationVisibilityAll
                                            loadHandler:^NSProgress *(
                                                void (^completion)(NSURL *, BOOL, NSError *)) {
                                              completion(url, in_place, nil);
                                              return nil;
                                            }];
  return provider;
}

static NSArray<NSString *> *load(NSArray<NSItemProvider *> *providers, NSURL *inbox)
{
  __block NSArray<NSString *> *result = nil;
  __block bool finished = false;
  GHOST_IOSFileDrop_loadFiles(providers, inbox, ^(NSArray<NSString *> *paths) {
    require(NSThread.isMainThread, "drop completion ran off the main thread");
    result = [paths retain];
    finished = true;
  });
  const NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:10];
  while (!finished && [deadline timeIntervalSinceNow] > 0) {
    [NSRunLoop.mainRunLoop runMode:NSDefaultRunLoopMode
                        beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
  }
  require(finished, "drop loading never finished");
  return [result autorelease];
}

static NSURL *write_file(NSURL *folder, NSString *name, NSString *contents)
{
  NSURL *url = [folder URLByAppendingPathComponent:name];
  require([contents writeToURL:url atomically:YES encoding:NSUTF8StringEncoding error:nil],
          "could not write a fixture");
  return url;
}

static NSArray<NSString *> *inbox_names(NSURL *inbox)
{
  NSArray *names = [NSFileManager.defaultManager contentsOfDirectoryAtPath:inbox.path error:nil];
  return [names ?: @[] sortedArrayUsingSelector:@selector(compare:)];
}

static NSString *contents(NSString *path)
{
  return [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:nil];
}

int main(int argc, char **argv)
{
  @autoreleasepool {
    require(argc == 3, "usage: file-drop-runtime <case> <folder>");
    const char *test = argv[1];
    NSURL *folder = [NSURL fileURLWithPath:@(argv[2]) isDirectory:YES];
    NSURL *source = [folder URLByAppendingPathComponent:@"source" isDirectory:YES];
    NSURL *inbox = [folder URLByAppendingPathComponent:@"Dropped Files" isDirectory:YES];
    [NSFileManager.defaultManager createDirectoryAtURL:source
                           withIntermediateDirectories:YES
                                            attributes:nil
                                                 error:nil];
    NSString *obj = [UTType typeWithFilenameExtension:@"obj"].identifier;

    if (strcmp(test, "in-place") == 0) {
      NSURL *url = write_file(source, @"scene.obj", @"o InPlace\n");
      NSArray<NSString *> *paths = load(@[ file_provider(url, obj, YES) ], inbox);
      require(paths.count == 1, "a file offered in place was not loaded");
      require([paths[0] isEqualToString:url.path], "a file offered in place did not keep its path");
      require(inbox_names(inbox).count == 0, "a file offered in place was copied");
    }
    else if (strcmp(test, "copy") == 0) {
      NSURL *url = write_file(source, @"scene.obj", @"o Copied\n");
      NSArray<NSString *> *first = load(@[ file_provider(url, obj, NO) ], inbox);
      NSArray<NSString *> *second = load(@[ file_provider(url, obj, NO) ], inbox);
      require(first.count == 1 && second.count == 1, "a copied file was not loaded");
      require([first[0] isEqualToString:[inbox URLByAppendingPathComponent:@"scene.obj"].path],
              "a copied file was not kept in the inbox under its own name");
      require([second[0] isEqualToString:[inbox URLByAppendingPathComponent:@"scene 2.obj"].path],
              "a second copy with the same name replaced the first");
      require([contents(first[0]) isEqualToString:@"o Copied\n"] &&
                  [contents(second[0]) isEqualToString:@"o Copied\n"],
              "a kept copy lost its contents after UIKit's temporary file went away");
    }
    else if (strcmp(test, "mixed") == 0) {
      NSURL *texture = write_file(source, @"texture.png", @"png");
      NSURL *model = write_file(source, @"model.obj", @"o Model\n");
      NSURL *directory = [source URLByAppendingPathComponent:@"Folder" isDirectory:YES];
      [NSFileManager.defaultManager createDirectoryAtURL:directory
                             withIntermediateDirectories:YES
                                              attributes:nil
                                                   error:nil];
      NSArray<NSString *> *paths = load(@[ file_provider(texture, UTTypePNG.identifier, NO),
                                            file_provider(directory, UTTypeFolder.identifier, YES),
                                            file_provider(model, obj, YES) ],
                                         inbox);
      NSArray *expected = @[ [inbox URLByAppendingPathComponent:@"texture.png"].path, model.path ];
      require([paths isEqualToArray:expected], "dropped files lost their order or kept a folder");
    }
    else if (strcmp(test, "slow") == 0) {
      /* A provider that is still downloading must not hold up Blender's main thread. */
      NSURL *url = write_file(source, @"slow.obj", @"o Slow\n");
      dispatch_semaphore_t release = dispatch_semaphore_create(0);
      __block bool loaded_on_main = false;
      NSItemProvider *provider = [[[NSItemProvider alloc] init] autorelease];
      [provider
          registerFileRepresentationForTypeIdentifier:obj
                                          fileOptions:0
                                           visibility:NSItemProviderRepresentationVisibilityAll
                                          loadHandler:^NSProgress *(
                                              void (^completion)(NSURL *, BOOL, NSError *)) {
                                            loaded_on_main = NSThread.isMainThread;
                                            dispatch_semaphore_wait(release,
                                                                    DISPATCH_TIME_FOREVER);
                                            completion(url, NO, nil);
                                            return nil;
                                          }];
      __block bool finished = false;
      GHOST_IOSFileDrop_loadFiles(@[ provider ], inbox, ^(NSArray<NSString *> *paths) {
        require(paths.count == 1, "a slow provider was not loaded");
        finished = true;
      });
      require(!finished, "loading waited for a slow provider on the main thread");
      dispatch_after(dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC / 4),
                     dispatch_get_global_queue(QOS_CLASS_DEFAULT, 0),
                     ^{ dispatch_semaphore_signal(release); });
      const NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:10];
      while (!finished && [deadline timeIntervalSinceNow] > 0) {
        [NSRunLoop.mainRunLoop runMode:NSDefaultRunLoopMode
                            beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
      }
      require(finished, "a slow provider never finished");
      require(!loaded_on_main, "a provider loaded on the main thread");
    }
    else {
      require(false, "unknown case");
    }
    printf("PASS: %s\n", test);
  }
  return 0;
}
