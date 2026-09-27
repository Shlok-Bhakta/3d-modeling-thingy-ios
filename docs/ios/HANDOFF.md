# 3D Modelling Thingy iOS port handoff

This independent fork ports Blender onto the immutable Blender `v5.2.0`
release. The simulator product reaches a responsive Workbench frame on
iPhone and iPad, embeds CPython and its accepted native packages, and renders
with portable CPU Cycles. The device product builds as arm64 iPhoneOS and is
handed off as one universal unsigned IPA; owner signing, provisioning, and
physical-device launch remain outside this repository.

## Ten-minute resume

1. Read `STATUS.json`, the newest entry in `DECISIONS.md`, and
   `overnight/MORNING.md` when it exists.
2. Confirm the worktree is clean and pinned correctly:

   ```sh
   git status --short --branch
   git rev-parse HEAD v5.2.0 a1de44dd54af75a4c8c4a29a5fed2a1334a87446
   ```

3. Run the environment doctor before any build:

   ```sh
   python3 build_files/ios/doctor.py --output /Volumes/BlenderBuild/blender-ios/artifacts/manual-doctor/env.json
   ```

4. Inspect the last-green artifact named by `STATUS.json`, then re-run the
   active packet's narrow test before editing.
5. Claim only a packet in `next_safe_packets`. Update the ledger before code if
   recorded state and the checkout disagree.

Before handing off a Metal or EEVEE change, run the production app through the
render gate on one booted iPhone and iPad simulator:

```sh
build_files/ios/simulator_render_smoke.py \
  --app /path/to/ios-simulator-build/bin/Blender.app
```

The command requires a nonblank factory-cube EEVEE PNG and a live rendered
viewport on both form factors. The narrow source tests identify the three iOS
Metal compatibility seams, so a forward port should adapt those seams before
changing shader behavior globally.

For a long-running memory gate, run each booted form factor explicitly:

```sh
python3 build_files/ios/simulator_memory_soak.py \
  --app /path/to/ios-simulator-build/bin/Blender.app \
  --udid DEVICE_UDID --warmup-seconds 60 --duration-seconds 300
```

The command must finish with zero application-owned leak roots and zero leak
growth. Treat stable Simulator Metal-driver roots as a separate diagnostic,
and do not replace the physical-device jetsam and thermal gate with simulator
RSS evidence.

The generated dependency graph is `DEPENDENCY_DAG.json`. Its bootstrap queue is
dependency-free and ordered for bounded `-j2` packets; do not replace it with the
global `install` target.

## Scene backing-scale boundary

Treat `MTKView.drawableSize` as the only authority for Blender client pixels.
Do not multiply UIKit bounds by `UIScreen.scale` or assign that screen-global
value to the Metal view. Display Zoom can give the logical coordinate space and
native Metal backing different scales. Derive input and overlay placement from
the current drawable-to-bounds ratio, and keep the Metal view pinned to the
scene window bounds.

## Touch and software-keyboard boundary

One-finger drag is Blender left-button input only. Do not reintroduce a
single-finger `GHOST_EventTrackpad`: it races selection with viewport
navigation. Two-finger drag remains orbit, pinch remains zoom, and three-finger
drag selects Blender's Shift+trackpad-pan mapping. Direct double tap is right
click and must use the first tap position.

Blender's `textedit_begin`/`textedit_end` pair owns the native keyboard bridge.
Keep the full keyboard for numeric fields so expressions and drivers remain
possible. The final string is captured during hide and must not be overwritten
by rereading the cleared UIKit field. Run
`build_files/ios/maestro/input_polish.yaml` after changing either side; its
`3+4` acceptance must end at `7 m` and its double tap must open the Object
context menu.

## Immutable anchors

- Production baseline: `v5.2.0` / `fbe6228777e7d9afefcd61a413844e790ae75db7`
- Read-only donor: `a1de44dd54af75a4c8c4a29a5fed2a1334a87446`
- Donor comparison: `v5.1.2..a1de44dd54af75a4c8c4a29a5fed2a1334a87446`
- Integration branch: `port/ios-5.2-simulator`

Do not merge the donor branch. Adapt one subsystem at a time and record donor
paths in each packet handoff.

## Storage contract

Source, Git metadata, control scripts, documentation, and small fixtures remain
on the internal SSD. All downloads, dependency builds/installs, Blender build
trees, large logs, artifacts, and task temporary directories belong below
`/Volumes/BlenderBuild/blender-ios`. A missing or changed bulk volume is a hard
stop; never fall back to an internal path.

## Safety boundary

Administrative or host-wide changes require explicit operator authorization;
that authorization was granted for this dedicated build Mac. The N100/N111
bootstrap installed `autoconf`, `automake`, `bison`, `dos2unix`, `flex`,
`libtool`, `meson`, `pkgconf`, and `yasm` with Homebrew, without `sudo`.
Credentials must never be written to source, logs, or artifacts.

No build packet may inspect signing identities or profiles, sign a device
bundle, rewrite history, or broaden its allowed files. Stop after two
unsuccessful architectural approaches and preserve the evidence.

## Unsigned device IPA

The production device lane uses `blender_ios_device.cmake`, an `iphoneos`
sysroot, an arm64-only dependency prefix, and a build directory separate from
the simulator. The `_minimal` profile remains a narrow diagnostic lane and is
not the release handoff. After `ninja install`, create the artifact with:

```sh
python3 build_files/ios/package_unsigned_ipa.py \
  /path/to/bin/Blender.app \
  /path/to/Blender-5.2.0-iPhone-iPad-unsigned.ipa
```

The packager rejects simulator binaries, the wrong bundle id or device-family
metadata, provisioning/signing files, signing plist keys, and embedded Mach-O
signatures. The owner must sign and provision the IPA before installing it.

## Recommended next order

1. Sign the current IPA and run a physical iPhone/iPad smoke test for launch,
   precise one-finger selection drags, first-position double-tap right click,
   one/two/three-finger navigation, keyboard expressions and Cancel, rotation,
   background/foreground, save/open, thermal behavior, jetsam, and memory
   pressure.
2. Finish GHOST/UIKit hardening: run physical rotation, resize, safe-area, and
   external-display acceptance against the scene-owned window, including exact
   `MTKView.drawableSize` framebuffer dimensions before and after each
   transition. Verify the new scene-space pointer mapping with a physical
   trackpad in a nonzero-origin iPad window. Exercise software-keyboard empty
   text, Unicode, Cancel, and repeated open/close cycles. Validate Pencil
   pressure, tilt, simultaneous finger input, cancellation, hover, and
   double-tap, then close memory-pressure and file-workflow gaps.
3. Owner-sign the P540-capable device IPA and run
   `BLENDER_IOS_CYCLES_SMOKE=METAL` on tier-2 iPhone and iPad hardware. Keep
   portable CPU Cycles as the accepted fallback until both renders pass.
4. Add optional dependency families individually under simulator, device ABI,
   and physical-device smoke tests. Prioritize Apple Accelerate for NumPy,
   then Embree, OSL, USD, OpenVDB, and media integrations.
5. Keep `makesrna.features` synchronized with each target profile when a
   feature changes generated RNA. Rebuild host tools before diagnosing target
   code when the manifest rejects a configure.
