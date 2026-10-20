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
iOS; a test-only observer reads the OS mouse state, while a Blender modal
observer passes events through and records the resulting transforms and view.
Neither observer generates Blender input or substitutes for the input backend.

The cases cover turntable and trackball orbit, Object and Pose move gizmos with
mouse and touch, keyboard transforms and mode switching, and Shift/Ctrl middle-button navigation. Results include
fresh Blender state, observed input events, OS button state, and application logs.
A missing OS mouse press is reported as an invalid injection setup rather than a
Blender failure.

Use `--case middle`, `--case gizmos`, `--case touch`, `--case keyboard`, `--case pan`, or `--case zoom` to narrow
a run. `--fixture pose` and `--orbit-method TRACKBALL` select individual fixtures.
`--record` opens Simulator and records each ready fixture to `demo.mp4` alongside
its result. Recordings use `simctl` because Maestro cannot inject physical mouse
buttons or relative mouse motion.

For an existing dedicated, booted test device, supply `--device UDID`.
`--skip-install` reuses an installed candidate; `--restart-between-cases` resets
SimulatorKit accessory services between fixtures. Do not point these factory
startup fixtures at a simulator containing work you want to preserve.
