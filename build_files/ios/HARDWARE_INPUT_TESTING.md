# iPad keyboard and mouse regression checks

The iOS PR preview runs the portable pointer-state and hardware-input checks.
Build the full simulator app to exercise UIKit, GameController, and Blender:

```sh
python3 build_files/ios/simulator_hardware_input.py \
  --app /path/to/simulator/Blender.app \
  --output /path/to/input-results \
  --restart-between-cases
```

The harness creates its own iPad simulator and deletes it on exit. Each fixture
uses factory startup. SimulatorKit sends real mouse, keyboard, and touch HID to
iOS. Test-only observers record platform input, native cursor coordinates,
display callbacks, process CPU time, and Blender events and results. They forward
input unchanged. A passive hover observer allows simultaneous recognition and
also sees the pointer over native window controls. Neither observer generates
Blender input or replaces the input backend.

The default cases cover:

- Turntable and trackball orbit; Object and Pose move gizmos with mouse and touch.
- Keyboard transforms and mode switching, right click, and Shift/Ctrl middle-button navigation.
- Three consecutive wheel reports that zoom without rotating, panning, or moving the pointer.
- Shift, Ctrl, Shift+Ctrl, and Alt scrolling, including the direction after iPad Shift-axis remapping. Native bindings pan the Graph Editor vertically with Shift, pan the timeline horizontally with Ctrl, and step frames with Alt.
- Scrolling a long sidebar without zooming the viewport.
- Three consecutive real Preferences checkbox clicks, each with one press and release and a persistent value change.
- Overlapping left/right holds and independent releases.
- The native Preferences close button without a second click reaching Blender, followed by fresh main-loop ticks.
- The custom app arrow, system tracking, and agreement between native pointer and Blender hit coordinates, both normally and during Cycles viewport startup.
- Reduced idle display callbacks, live timers, and restoration of the maximum display rate on input.

Use repeated `--case` options to select cases. `--wheel-delta -1`,
`--wheel-delta .25`, and `--wheel-delta -12` exercise reverse, fractional, and
large reports. Natural Scrolling can invert the physical delta; assertions use
the delivered OS direction. Missing OS input invalidates a fixture. The
`--wheel-reports 1` diagnostic does not replace the default repeated-report check.
`--case wheel-sweep` sends three reports for each of those four deltas in one
app launch. `--orientation landscape` requests a landscape scene and checks its
dimensions before input. The independent GameController observer's raw axes are
normalized to the scene orientation; UIKit already delivers view-oriented scroll.

Normal pointing follows UIKit's absolute coordinates and the iPad tracking and
acceleration settings. The system compositor draws the app's arrow path. A real
system pointer cannot be warped by Blender, so the harness moves the HID mouse
to each target and observes its actual position. Blender's captured tools use
relative GameController input. Finger and Pencil input keep their existing paths.
Raw motion callbacks are registered only for captured tools, avoiding a second
stream of unused callbacks on the UI thread during normal pointing.

UIKit's mouse button mask includes a button being released. Partial releases can
leave that mask unchanged, and an ended touch may have no view. Regression checks
therefore verify actual button edges and checkbox values, rather than treating a
nonzero mask as proof that a button remains held.

`--record` records each ready fixture to `demo.mp4`. SimulatorKit and `simctl` are
used because Maestro cannot inject physical mouse buttons or relative motion.
For an existing dedicated test device, use `--device UDID`; `--skip-install`
reuses the installed candidate. Do not use a simulator containing personal work.
The Alt-wheel fixture opens Simulator before connecting its mouse; a headless
accessory service can consume Alt-scroll without delivering either scroll API.
Use `--modifier-side right` to exercise the right modifier keys.

## Performance scope

The full device profile is a Release build with TBB, Cycles CPU, Cycles Metal,
Embree, and OpenSubdiv enabled. Blender and Cycles use automatic CPU concurrency;
there is no iOS-specific one-core limit. Cycles selects Metal by default when its
runtime finds a usable device, and keeps the CPU fallback. The simulator cannot
compile the required Metal kernels and intentionally uses that CPU fallback.

After 750 ms without input or a requested redraw, the iOS display callback rate
drops to 30 Hz. Input and redraws restore the display's maximum rate, including
animation and render updates. Render thread counts remain automatic. Timers
continue while idle.

Simulator measurements establish input routing, cursor coordinate agreement, and
callback pacing. They do not establish an iPad's CPU/GPU utilization, physical
mouse feel, power consumption, or battery life. Those require a device trace.
The test observer's file writes and sampling also add CPU work, so its CPU time
must not be presented as a production energy benchmark.
