# iPad keyboard and mouse regression checks

The iOS PR preview runs the portable pointer-state and hardware-input regression
checks alongside the existing iOS tests. To exercise the platform input path,
first build the full simulator app, then run:

```sh
python3 build_files/ios/simulator_hardware_input.py \
  --app /path/to/simulator/Blender.app \
  --output /path/to/input-results
```

The harness owns an iPad simulator and deletes it on exit. It uses factory
startup for each fixture. SimulatorKit sends mouse, keyboard, and touch HID to
iOS. A test-only observer samples OS mouse state and records scroll callbacks
before forwarding their arguments unchanged to the app's original handler.
A Blender modal observer passes events through and records the resulting
transforms and view. Neither observer generates Blender input or substitutes
for the input backend.

The cases cover turntable and trackball orbit, Object and Pose move gizmos with
mouse and touch, keyboard transforms and mode switching, Shift/Ctrl middle-button
navigation, and plain mouse-wheel zoom. The wheel fixture repeats three reports.
Use `--wheel-delta -1`, `--wheel-delta .25`, or `--wheel-delta -12` to check the
reverse direction and fractional or large reports. It requires one native wheel
event per report, zoom in the delivered direction, and no view rotation or cursor
movement. Results include fresh Blender state, observed input events, OS button
state, and application logs.
A missing OS mouse press or wheel report is reported as an invalid injection
setup rather than a Blender failure.

Some SimulatorKit mouse services drop repeated scroll packets before they reach
GameController. `--wheel-reports 1` isolates a single report in a fresh app launch;
this does not validate repeated scrolling. Keep the default three-report check
for repeat coverage on a simulator that delivers all reports or use a physical
iPad for that check.

Use `--case middle`, `--case gizmos`, `--case touch`, `--case keyboard`, `--case pan`,
`--case zoom`, or `--case wheel` to narrow
a run. `--fixture pose` and `--orbit-method TRACKBALL` select individual fixtures.
`--record` opens Simulator and records each ready fixture to `demo.mp4` alongside
its result. Recordings use `simctl` because Maestro cannot inject physical mouse
buttons or relative mouse motion.

For an existing dedicated, booted test device, supply `--device UDID`.
`--skip-install` reuses an installed candidate; `--restart-between-cases` resets
SimulatorKit accessory services between fixtures. Do not point these factory
startup fixtures at a simulator containing work you want to preserve.
