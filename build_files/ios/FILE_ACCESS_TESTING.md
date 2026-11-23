# File location regression tests

The folder button must return control to Blender after a selection, even when a
Files provider stalls during permission access or bookmark restoration. Repeated
grants must produce one System entry, and saved locations must return after relaunch.
The picker callback must return while the provider is stalled, and the remote
picker host and its weak delegate must remain alive until Files dismisses itself.
The native picker explicitly requests access to one original directory. The
simulator reproduction separately times out if tapping Open never enters or
returns from the delegate, so later bookmark work cannot hide a stuck Files sheet.

Run the host suite on macOS:

```sh
python3 -m unittest discover -s build_files/ios/tests -p 'test_*.py'
```

`test_file_access_runtime.py` compiles the production `fsmenu_system_ios.mm` shim
against Foundation. It uses real temporary folders, NSURL bookmarks and isolated
NSUserDefaults suites. It pauses permission access or bookmark resolution,
requires a responsive main queue, refreshes the menu while paused, then checks
persistence, duplicate grants and malformed saved data. Blender's menu and
notifier functions are test substitutes that reject calls from a worker thread.

Set `FMT_INCLUDE_DIR` if the fmt headers are outside
`lib/macos_arm64/fmt/include`. CI uses its harvested iOS dependency prefix and
runs these tests before the full app build.

For the full app, boot an iPhone or iPad simulator, build the simulator app, then:

```sh
python3 build_files/ios/simulator_file_access.py \
  --app /path/to/Blender.app \
  --output /tmp/blender-file-access \
  --slow-provider
```

Use `--device <UDID>` to select one booted device. Without that argument, the
script runs each booted iPhone and iPad sequentially. Omit `--slow-provider` to
exercise ordinary provider timing.

The script starts from a clean app container and creates a folder with 90
top-level items and nested directories in Files' local storage outside Blender's
sandbox. Its test-only dylib sets the native picker's starting directory and
holds the real security-scope call until the host releases it. While that call is
blocked, the test requires the picker delegate to return, Files to dismiss, the
picker host to remain retained, and Blender's main loop to keep ticking. Nothing
in the production app loads this dylib. Maestro selects the folder three times,
then closes the file browser and verifies one System entry. The script also
verifies restoration after terminating and relaunching the app. Failed runs
preserve logs and state.

The iOS 26.5 remote Files view does not expose its Open button reliably to XCTest.
The flow uses a coordinate fallback for that button on iPhone landscape and iPad
portrait; Blender's controls use accessibility identifiers. The generated flow
requires the script's fixture and should not be run alone.

Live iCloud and network-provider access still needs an account configured on a
real device. The controlled stall covers responsiveness independently of provider
latency; it does not claim to authenticate or exercise those services.

## Dropping files onto Blender

```sh
python3 build_files/ios/simulator_file_drop.py \
  --app /path/to/Blender.app --device <booted-simulator-udid> --output /tmp/file-drop
```

A test-only dylib adds a small orange view to Blender's window that offers an OBJ
file through `UIDragInteraction`. HID touches long-press it, carry the drag over
the 3D viewport and drop it, and a hardware Return confirms Blender's import
dialog. The run fails when UIKit does not start the drag, when Blender does not
accept the drop, or when the object is missing afterwards. `in-place` offers a
file from Documents and requires Blender to read it where it is; `copy` offers
only a temporary copy and requires exactly one kept copy in
`Documents/Dropped Files`. Nothing in the production app loads this dylib.

A drag from the Files app or Photos runs in another process, which the simulator
check does not cover. Check those on a device.
