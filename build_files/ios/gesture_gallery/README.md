# Gesture recording evidence

The public video guide contains 17 captures from the linked iPad simulator app.
The gesture recognizers and Blender editors run normally. No app code was changed
for recording. Teal touch markers and captions are added after capture using the
injected contact coordinates and recording-relative timestamps.

Each recipe contains the actual contacts, before/after Blender state, and explicit
outcome checks. `media-validation.json` records codec, frame count, duration, and
file size. The context-menu and Search outcomes also received visual review of the
final captured frames. Their state checks alone do not prove that a popup appeared.

## Reproduce a clip

Use Xcode 26.5, the arm64 simulator app, and the iPad Pro 13-inch M5 simulator.
Keep that simulator visible and pass its exact UDID. Install the app with
`xcrun simctl install UDID /absolute/path/Blender.app` and launch its bundle ID.
These recordings used `org.blenderfoundation.blender.ios`; newer builds may use
a different identifier.

1. Start with the default Cube scene on a dedicated simulator. Move the cursor into
   the viewport and press Shift-F4 to open Blender's Python Console.
2. Copy `build_files/ios/simulator_gesture_probe.py` into the app's writable container.
   In the console, execute this with your actual container paths:

   ```python
   DEMO_DIRECTORY = '/absolute/app/container/tmp/gesture-gallery'
   exec(open('/absolute/app/container/tmp/simulator_gesture_probe.py').read())
   ```

   The fixture creates the viewport/node layout and samples live editor state.
   It never intercepts or replaces GHOST gestures. Its modal observer returns
   `PASS_THROUGH` for every event. State writes are atomic.
3. Match the recipe's starting editor, tool, object state, and cursor position.
   The recipes use a 2064 by 2752 display in portrait. Pointer coordinates use
   Blender's bottom-left origin; touch coordinates use the top-left origin.
   For `three-finger-pan`, place the cursor at roughly 40% across and 60% down.
4. Replay and record:

   ```sh
   python3 build_files/ios/simulator_gesture_gallery.py \
     --device UDID \
     --recipe build_files/ios/gesture_gallery/recipes/three-finger-pan.json \
     --state-file /absolute/app/container/tmp/gesture-gallery/state.json \
     --output /absolute/output/three-finger-pan.mp4
   ```

The recorder compiles the host-only Objective-C helper, sends real one- through
four-contact SimulatorKit events, checks the resulting state, and finalizes H.264
capture with SIGINT. A failed check leaves the raw recording and log for diagnosis
but does not write a PASS result. Review the final frame before publishing a clip.

`command.py` in the probe directory can contain fixture setup between recordings.
The probe executes it once on Blender's main-loop timer and deletes it. Keep that
setup outside the recording boundary.

## Validation commands

```sh
python3 -m unittest discover -s build_files/ios/tests -p test_simulator_gesture_gallery.py
clang -fobjc-arc -framework Foundation -framework AppKit \
  build_files/ios/simulator_gesture_hid.m -o /tmp/simulator-gesture-hid
ffmpeg -v error -i docs-media/touch/three-finger-pan.mp4 -f null -
```

The gallery videos use H.264, yuv420p, 15 fps, silent audio, and fast-start MP4.
Most clips are two to six seconds. The editor-targeting comparison takes about
15 seconds because it includes moving the cursor to both editors.
