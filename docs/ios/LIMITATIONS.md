# 3D Modelling Thingy iOS limitations

Simulator Workbench and EEVEE were proven on both iPhone and iPad before the branding change. Packet P530 installed the
earlier bundle (`UIDeviceFamily` 1 and 2) on an
iPhone 17 simulator and an iPad Pro 13-inch (M5) simulator, both on iOS 26.5.
The bundle declares a modern launch screen so current full-screen iPhones use
their complete native viewport instead of a legacy compatibility rectangle.
Splash and cube viewport screenshots exist for each simulator. iPad runs as
`UIUserInterfaceIdiomPad` (not an iPhone compatibility window). On iPadOS 26,
`UIRequiresFullScreen` no longer forces a full-screen scene; the iPad capture
is a native iPad windowed scene. Full-screen versus windowed placement on
iPadOS 26 is controlled by the user and operating system.
The window path now measures native pixels from `MTKView.drawableSize` instead
of `UIScreen.scale`, and the Metal view follows the scene window bounds. This
fixes the uniform top/right gray bands reported on a phone using a different
display configuration. iPhone 17e, iPhone 17 Pro Max, and iPad mini simulator
captures fill every edge. The originally reported physical phone still needs a
rerun with the new build, and external-display scaling remains a physical gate.
The release smoke gate also renders the factory cube to a validated 1920 by
1080 EEVEE PNG and holds a live rendered viewport for 30 seconds on each
simulator. A separate rendered-viewport soak uses a 60-second warmup and five
minutes of continuous scene changes. Its final iPhone run used 87.0-117.8 MiB
RSS with 1.1 MiB latter-half growth; iPad used 84.1-117.2 MiB with 11.1 MiB
latter-half growth and visible reclamation cycles. Both live `leaks` scans found
zero application-owned roots and zero leak growth. The stable 19,584-byte
`_MTLFunctionInternal` roots are owned by the Simulator Metal driver and are
reported separately rather than waived as application leaks. Physical-device
EEVEE performance, thermal behavior, jetsam behavior, and long-scene memory
pressure remain owner-signed acceptance work.

The arm64 iPhoneOS build, runtime bundle, and universal unsigned IPA are now
proven. The IPA targets iOS 18.0 or newer, declares iPhone and iPad device
families, and passes bundle, dependency ABI, executable ABI, archive integrity,
and embedded-signature audits. Physical iPhone and iPad launch remain unproven
because the artifact intentionally has no owner signing or provisioning.

CPython 3.13.13, NumPy 2.3.4, zstandard 0.25.0, and portable CPU Cycles are
enabled in both application lanes. Python native extensions are packaged as
signable frameworks. Simulator acceptance exercises Blender's Python API,
common standard-library modules, arrays, linear algebra, zstd
compression/decompression, and the Extensions background worker on iPhone and
iPad. Cycles acceptance discovers a CPU render device and produces a real
one-sample PNG through the registered desktop render engine on both form
factors. iOS does not permit Blender to create child processes, so the standard
Python `multiprocessing.Process` API is unavailable. The Extensions/remote
asset-library downloader preserves its asynchronous queue, cancellation, and
reporting behavior with a worker thread. The Cycles Metal render device now
compiles and links in both profiles and is exposed only on tier-2
argument-buffer GPUs. The iOS Simulator's tier-1 Metal device cannot compile
the roughly 303-resource Cycles bindless pipelines and is intentionally hidden;
the unsigned iPhoneOS app still needs an owner-signed physical-device Metal
render before that backend is accepted for daily work. CPU remains the proven
fallback. Embree, OSL, path guiding, USD, OpenVDB, and optional media services
remain separate hardening slices.

The current GHOST backend supports UIKit/Metal startup, rendering, touch,
Pencil, mouse/trackpad buttons and motion, hardware-keyboard HID translation,
modifier polling, activation events, sandbox paths, and security-scoped Blender
documents. It now uses a single `UIWindowScene`, scene-routed activation and
file-open callbacks, scene-relative geometry and scale, and MetalKit drawable
resize events. Screen/client coordinate conversion now routes through the
attached scene coordinate space, including its native-pixel scale, so pointer
state does not assume that an iPad window starts at the display origin. The
Metal overlay framebuffer follows the active view's native-pixel drawable and
preserves its last valid texture during a temporary zero-size transition;
offscreen contexts use a display-independent 1 by 1 backing. The
iPadOS 26 simulator renders the desktop UI inside the native OS-managed scene,
and both simulator form factors keep the full runtime and CPU Cycles gates
green. Swap requests are coalesced to one presentation per MetalKit delegate
frame, and the earlier process-global drawable identity heuristic has been
removed. iPhone and iPad simulator launch/render acceptance emits no duplicate
presentation diagnostics. Physical trackpad acceptance of nonzero window
origins remains pending.
The software-keyboard result and Cancel snapshot own their storage, input
objects detach during GHOST window teardown, and a failed first-responder
request reaches the caller as a failure. Blender UI text editing now opens the
native full keyboard for every field, preserves the initial selection, disables
UIKit text rewriting, and commits through Blender's normal validation path. An
iPad Simulator acceptance run entered `3+4` into Location X, committed `7 m`,
and moved the cube. Empty text, Unicode, Cancel, repeated open/close cycles,
keyboard avoidance for fields behind the overlay, and hardware-keyboard
interoperability still require signed-device acceptance.
Pencil tablet state now starts on contact, follows only the tracked stylus, and
keeps pressure and tilt bounded even if UIKit reports an unusable force range.
The simulator cannot synthesize physical Pencil pressure or tilt, so real
Pencil contact, motion, simultaneous finger input, cancellation, hover, and
double-tap remain owner-signed iPad acceptance gates.
Direct touch keeps one-finger selection and tool drags, two-finger orbit, and
pinch zoom; three-finger drag pans the viewport through Blender's standard
trackpad navigation path. One-finger drag no longer emits the scroll event that
caused a brief viewport rotation before selection, and a one-finger double tap
opens the right-click menu at the first tap location. The installed
Simulator/Maestro stack cannot synthesize three concurrent contacts, so final
gesture arbitration and feel remain a physical iPhone/iPad gate.
Multi-scene Blender sessions, physical rotation and resize acceptance,
safe-area transitions, external-display moves, physical memory-pressure
handling, and broader document workflows still require device hardening.

The unsigned device IPA cannot install or run on physical hardware before
owner-controlled signing and provisioning. This lane does not inspect
identities or profiles, and it never signs the `iphoneos` bundle.
