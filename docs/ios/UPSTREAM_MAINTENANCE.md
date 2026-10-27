# iOS upstream-maintenance audit

## Baselines and method

The repository originally diverged from Blender 5.2.0 at
`fbe6228777e7d9afefcd61a413844e790ae75db7`. The port later merged Blender
5.2.1, so measuring the current port against the original divergence would
incorrectly count Blender's own 5.2.1 changes as port changes. The actionable
comparison therefore uses the merged Blender 5.2.1 tree at
`9e2066aef7ef7e20c142ad7bd3303138a4304c93`.

The pre-refactor port tip is
`5281baa65182263fa0b8c0894f4186cb98159fd6`. A file is considered upstream-owned
when that path exists in the 5.2.1 baseline. LOC is additions plus deletions
reported by `git diff --numstat`; it is an approximation of rebase surface, not
a claim about semantic complexity.

Run the repeatable audit with:

```sh
python3 build_files/ios/audit_upstream_seams.py \
  --base 9e2066aef7ef7e20c142ad7bd3303138a4304c93
```

## Result

| Measurement | Before | After |
| --- | ---: | ---: |
| Upstream Blender files modified | 129 | 68 |
| Upstream additions | 3,227 | 917 |
| Upstream deletions | 423 | 196 |
| Approximate upstream LOC churn | 3,650 | 1,113 |

The largest reduction came from returning all 58 shared dependency recipes to
their upstream form. The iOS recipes and patches now live under
`build_files/ios/build_environment`. The Apple, Xcode, GHOST, creator,
window-manager startup, Python startup, and Metal platform policies similarly
live in new iOS-owned files. Existing CMake and C++ files retain small generic
dispatch or capability seams.

The remaining upstream delta contains no direct
`WITH_APPLE_CROSSPLATFORM`, `BLENDER_IOS_*`, `TARGET_OS_IPHONE`, or
`TARGET_OS_SIMULATOR` policy branch. Platform-specific implementations still
use those facilities inside iOS-owned files.

## Remaining upstream files

Every remaining upstream file was inspected. They fall into the following
groups.

### Stable dispatch and platform contracts

These files contain small generic hooks or capabilities needed to reach an
iOS-owned implementation. Removing them would require duplicating a larger
Blender subsystem.

```text
CMakeLists.txt
build_files/cmake/platform/dependency_targets.cmake
build_files/cmake/platform/platform_apple.cmake
intern/ghost/CMakeLists.txt
intern/ghost/GHOST_ISystem.hh
intern/ghost/GHOST_Types.hh
intern/ghost/intern/GHOST_EventTrackpad.hh
intern/ghost/intern/GHOST_ISystem.cc
source/blender/blenkernel/intern/appdir.cc
source/blender/blenkernel/intern/blendfile.cc
source/blender/blentranslation/msgfmt/CMakeLists.txt
source/blender/datatoc/CMakeLists.txt
source/blender/editors/space_file/CMakeLists.txt
source/blender/gpu/shader_tool/CMakeLists.txt
source/blender/io/usd/CMakeLists.txt
source/blender/makesdna/intern/CMakeLists.txt
source/blender/makesrna/intern/CMakeLists.txt
source/blender/python/intern/bpy_interface.cc
source/blender/windowmanager/CMakeLists.txt
source/blender/windowmanager/WM_api.hh
source/blender/windowmanager/intern/wm_init_exit.cc
source/creator/CMakeLists.txt
source/creator/creator.cc
```

The GHOST API additions are platform-neutral: touch events, event-local
modifiers, and an opt-in on-screen-keyboard capability. UIKit state and gesture
recognizers do not cross this boundary. Creator and window-manager hooks allow
UIKit to own the process loop while normal desktop builds retain `WM_main`.

### Shared Metal backend compatibility

These are real Metal backend changes, not UIKit code. iOS uses the shared Metal
renderer, but its compiler, attachment rules, framebuffer-fetch behavior,
resource limits, and Objective-C object lifetime expose assumptions that macOS
does not. Platform capability values are centralized in the new
`mtl_platform_ios.hh`; the shared code consumes generic `MTL_BACKEND_*`
capabilities.

```text
source/blender/gpu/metal/mtl_backend.mm
source/blender/gpu/metal/mtl_capabilities.hh
source/blender/gpu/metal/mtl_command_buffer.mm
source/blender/gpu/metal/mtl_common.hh
source/blender/gpu/metal/mtl_context.hh
source/blender/gpu/metal/mtl_context.mm
source/blender/gpu/metal/mtl_framebuffer.hh
source/blender/gpu/metal/mtl_framebuffer.mm
source/blender/gpu/metal/mtl_immediate.hh
source/blender/gpu/metal/mtl_index_buffer.hh
source/blender/gpu/metal/mtl_index_buffer.mm
source/blender/gpu/metal/mtl_memory.hh
source/blender/gpu/metal/mtl_memory.mm
source/blender/gpu/metal/mtl_query.mm
source/blender/gpu/metal/mtl_shader.mm
source/blender/gpu/metal/mtl_shader_generate.cc
source/blender/gpu/metal/mtl_shader_interface.mm
source/blender/gpu/metal/mtl_storage_buffer.mm
source/blender/gpu/metal/mtl_texture.hh
source/blender/gpu/metal/mtl_texture.mm
source/blender/gpu/metal/mtl_texture_util.mm
source/blender/gpu/metal/mtl_vertex_buffer.hh
source/blender/gpu/metal/mtl_vertex_buffer.mm
```

This is the largest remaining conflict area. Forking the complete Metal backend
would isolate diffs but make correctness fixes and upstream GPU improvements
substantially harder to inherit, so that trade was intentionally rejected.

### Generic portability and behavior fixes

These changes cannot be cleanly implemented behind GHOST or CMake alone. Most
are generic fixes: cross-compile host tools, backend-neutral OpenSubdiv, safe
Metal ownership, lack of subprocess support, or shader/compiler portability.

```text
extern/quadriflow/src/hierarchy.cpp
extern/quadriflow/src/localsat.cpp
intern/cycles/CMakeLists.txt
intern/cycles/device/metal/bvh.mm
intern/cycles/device/metal/device_impl.mm
intern/cycles/device/metal/kernel.mm
intern/cycles/device/metal/queue.mm
intern/cycles/device/metal/util.mm
intern/cycles/util/half.h
intern/opensubdiv/CMakeLists.txt
intern/opensubdiv/internal/evaluator/eval_output_gpu.h
intern/opensubdiv/internal/evaluator/gpu_compute_evaluator.cc
source/blender/asset_system/intern/disk_file_hash_service.cc
source/blender/blentranslation/intern/messages_apple.mm
source/blender/draw/engines/eevee/shaders/eevee_light_iter.bsl.hh
source/blender/editors/interface/interface_handlers.cc
source/blender/editors/screen/screen_ops.cc
source/blender/windowmanager/intern/wm.cc
source/blender/windowmanager/intern/wm_event_system.cc
```

The on-screen keyboard needs the live Blender edit buffer, selection range, and
commit path, so the generic capability bridge in `interface_handlers.cc` cannot
reasonably live in Python. The window-manager loop split is required because
UIKit owns the outer application loop. Trackpad event-local modifiers let GHOST
translate a touch gesture into Blender's existing Shift+trackpad-pan behavior
without an iOS branch in the editor or keymap.

### Python and add-on integration

```text
intern/cycles/blender/addon/properties.py
scripts/addons_core/bl_pkg/bl_extension_utils.py
scripts/addons_core/bl_pkg/cli/blender_ext.py
scripts/addons_core/io_scene_gltf2/io/com/library.py
scripts/modules/_bpy_internal/http/downloader.py
```

Cycles' GPU default must be selected while its RNA properties and preferences
are registered; a later startup script would only update the current scene and
would regress new scenes. glTF must resolve signed native bridges from the app's
Frameworks directory. The downloader now contains only a generic import and
worker invocation; iOS thread selection is isolated in the new
`worker_context.py` and `thread_context.py` modules. The Extensions command
runner hands its arguments to `bl_pkg/bl_extension_thread.py` on iOS, and
`blender_ext.msglog_from_args` accepts that module's message callback.

## Intentionally retained risk

- The shared Metal changes remain broad. Replacing them with an iOS Metal fork
  would be a larger long-term maintenance liability.
- The native keyboard currently commits its final UIKit string through
  Blender's normal text-edit completion path. Replacing this with synthetic
  per-character events would risk IME, selection, expression, and undo behavior.
- `WM_main` remains split into entry and one-iteration functions so UIKit can
  drive frames. A separate duplicated event loop would drift from upstream.
- QuadriFlow's optional aggressive SAT repair remains disabled through a
  generic subprocess capability. iOS cannot launch its external `minisat` and
  `timeout` commands; normal remeshing remains available.
- The glTF bridge lookup stays in the add-on until Blender exposes a generic
  signed-extension resolver for application frameworks.
- The Cycles add-on retains a small iOS default-device policy because moving it
  to a startup handler would not preserve defaults for every newly created
  scene.

## Expected rebase hotspots

1. The shared Metal backend, especially framebuffer, shader-generation, and
   command-buffer ownership code.
2. Creator and top-level CMake dispatch points if Blender reorganizes platform
   configuration or packaging.
3. GHOST public event and keyboard contracts if upstream adds native touch or
   virtual-keyboard APIs.
4. `interface_handlers.cc` if Blender changes text-edit ownership.
5. Cycles device registration and the add-on's device-default properties.

The iOS dependency graph itself is now a low-conflict area: upstream recipes
can update normally, and the port can reconcile only the owned iOS recipe copy.
