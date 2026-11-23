#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce TestFlight file reports against a real simulator build.

Each check drives the path a person uses and records what actually happens:

import-picker:  open the FBX import browser. The native add-location button must be
                named "Add Folder", because the Files picker it opens only accepts folders
                and greys out the files Blender imports. Choosing a .blend there must not
                register the file as a folder.
blend-compat:   save factory and modified scenes in the app, report each file's header,
                and load every file with each --host-blender in background mode.
save:           File > Save on an untitled, modified scene through Blender's file browser
                into an external Files folder, then save in place and over a document
                opened from Files. The main loop must keep ticking.
render:         F12 with EEVEE and Cycles, then close the render window with its native
                button. The main loop must not stall and the window must close.
open-document:  open a .blend from Files by tapping it in the Files app, and through
                `simctl openurl` with the app cold and warm. The app must stay alive and
                load the document.

A startup script inside the app's user config exposes a small command channel, so the
app keeps its normal preferences. The script removes that probe when it finishes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import time


CHECKS = ("import-picker", "blend-compat", "save", "render", "open-document")
ADD_LOCATION_BUTTON_ID = "blender_file_browser_add_location"
ADD_LOCATION_TITLE = "Add Folder"
CLOSE_BUTTON_ID = "blender_child_window_close"
PROBE_NAME = "ios_feedback_probe.py"
EXTERNAL_FOLDER = "BlenderFeedback"
SHARED_DOCUMENT = "shared-from-discord.blend"
FIXTURE_SOURCE = Path(__file__).with_name("file_access_provider_fixture.mm")
# A healthy main loop ticks every 0.2 s. Longer gaps read as a frozen app.
STALL_LIMIT = 2.0
SAVE_LIMIT = 5.0
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
GZIP_MAGIC = b"\x1f\x8b"
# Files picker grid on iPad portrait with the sidebar visible: first row, by column.
PICKER_GRID = ("51%,36%", "66%,36%", "80%,36%")
# The picker's Open button, which grants the folder it shows. The remote view hides
# it from XCTest's tree and ignores synthesized taps on its close button.
PICKER_OPEN = "84%,29%"
# Files app "On My iPad" grid: first row, by column.
FILES_GRID = ("9%,10%", "23%,10%", "37%,10%")

PROBE_SOURCE = '''\
import bpy, json, os, time, traceback

_tmp = os.path.expanduser("~/tmp")
_state = {"ticks": 0, "pid": os.getpid(), "started": time.time()}
_ns = {"bpy": bpy, "os": os, "json": json, "time": time, "state": _state}


def _write(name, data):
    path = os.path.join(_tmp, name)
    with open(path + ".part", "w") as handle:
        json.dump(data, handle, default=str)
    os.replace(path + ".part", path)


def _tick():
    _state["ticks"] += 1
    _state["time"] = time.time()
    _state["filepath"] = bpy.data.filepath
    _state["dirty"] = bpy.data.is_dirty
    _state["objects"] = sorted(o.name for o in bpy.data.objects)
    _state["windows"] = [w.screen.areas[0].type if w.screen.areas else ""
                         for w in bpy.context.window_manager.windows]
    _write("feedback-state.json", _state)
    command = os.path.join(_tmp, "feedback-command.py")
    if os.path.exists(command):
        with open(command) as handle:
            source = handle.read()
        os.remove(command)
        result = {"started": time.time()}
        try:
            _ns["result"] = result
            exec(source, _ns)
            result["ok"] = True
        except Exception:
            result["ok"] = False
            result["error"] = traceback.format_exc()
        result["finished"] = time.time()
        _write("feedback-result.json", result)
    return 0.2


def register():
    bpy.app.timers.register(_tick, first_interval=0.2, persistent=True)


def unregister():
    pass
'''

VIEW3D_CONTEXT = '''\
win = bpy.context.window_manager.windows[0]
area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
region = next(r for r in area.regions if r.type == "WINDOW")
'''

FILE_BROWSER_CONTEXT = '''\
win = next(w for w in bpy.context.window_manager.windows
           if w.screen.areas and w.screen.areas[0].type == "FILE_BROWSER")
area = win.screen.areas[0]
params = area.spaces.active.params
region = next(r for r in area.regions if r.type == "WINDOW")
'''


class FeedbackFailure(RuntimeError):
    pass


DIAGNOSTIC_REPORTS = Path.home() / "Library" / "Logs" / "DiagnosticReports"


def springboard_reports() -> set[str]:
    return {path.name for path in DIAGNOSTIC_REPORTS.glob("SpringBoard-*.ips")}


def run(*args: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True, timeout=timeout)


def version_dir(short_version: str) -> str:
    """Blender keeps user config per major.minor version."""
    major, minor = short_version.split(".")[:2]
    return f"{major}.{minor}"


def parse_blend_header(data: bytes) -> dict:
    """Describe the start of a .blend file: compression, header format and version."""
    if data.startswith(ZSTD_MAGIC):
        return {"compression": "zstd"}
    if data.startswith(GZIP_MAGIC):
        return {"compression": "gzip"}
    if not data.startswith(b"BLENDER"):
        raise ValueError("not a Blender file")
    # Blender 5.0 and later: BLENDER17-01v0503 (header size, format, endian, version).
    modern = re.match(rb"BLENDER(\d\d)-(\d\d)([vV])(\d{4})", data)
    if modern:
        return {"compression": "none", "format": int(modern.group(2)),
                "header_size": int(modern.group(1)), "pointer_size": 8,
                "endian": "little" if modern.group(3) == b"v" else "big",
                "version": int(modern.group(4))}
    # Earlier files: BLENDER-v405 (pointer size, endian, version).
    legacy = re.match(rb"BLENDER([_-])([vV])(\d{3})", data)
    if legacy:
        return {"compression": "none", "format": 0, "header_size": 12,
                "pointer_size": 4 if legacy.group(1) == b"_" else 8,
                "endian": "little" if legacy.group(2) == b"v" else "big",
                "version": int(legacy.group(3))}
    raise ValueError("unknown Blender header")


def host_version(output: str) -> tuple[int, int, int] | None:
    match = re.search(r"Blender (\d+)\.(\d+)\.(\d+)", output)
    return tuple(int(part) for part in match.groups()) if match else None


def classify_host_load(output: str) -> str:
    if "FEEDBACK-LOADED" in output:
        return "loaded"
    if "incomplete header, may be from a newer version" in output:
        return "newer-header-unsupported"
    return "failed"


def longest_gap(times: list[float]) -> tuple[float, float]:
    """Longest interval between distinct main-loop ticks, and when it began."""
    ordered = sorted(set(times))
    gaps = [(later - earlier, earlier) for earlier, later in zip(ordered, ordered[1:])]
    return max(gaps) if gaps else (0.0, ordered[0] if ordered else 0.0)


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def files_open_flow(folder_point: str, document_point: str) -> str:
    """Files app: Browse > On My iPad > folder > document."""
    return f'''- launchApp:
    stopApp: true
- tapOn: Browse
- waitForAnimationToEnd
- tapOn: "On My iPad"
- waitForAnimationToEnd
- tapOn:
    point: {folder_point}
- waitForAnimationToEnd
- takeScreenshot: files-folder
- tapOn:
    point: {document_point}
- waitForAnimationToEnd
'''


def close_flow() -> str:
    return f'''- tapOn:
    id: {CLOSE_BUTTON_ID}
- extendedWaitUntil:
    notVisible:
      id: {CLOSE_BUTTON_ID}
    timeout: 30000
'''


def picker_flow(item_point: str, screenshot: str) -> str:
    """Open the native Files picker from Blender's file browser and tap one grid item."""
    return f'''- extendedWaitUntil:
    visible:
      id: {ADD_LOCATION_BUTTON_ID}
    timeout: 30000
- tapOn:
    id: {ADD_LOCATION_BUTTON_ID}
- extendedWaitUntil:
    visible: Cancel
    timeout: 30000
- waitForAnimationToEnd
- takeScreenshot: {screenshot}
- tapOn:
    point: {item_point}
- waitForAnimationToEnd
- takeScreenshot: {screenshot}-after-tap
'''


def label_flow() -> str:
    """The add-location button must be named for what it adds."""
    return f'''- extendedWaitUntil:
    visible:
      id: {ADD_LOCATION_BUTTON_ID}
    timeout: 30000
- assertVisible:
    id: {ADD_LOCATION_BUTTON_ID}
    text: {ADD_LOCATION_TITLE}
- takeScreenshot: add-folder-button
'''


def evaluate_picker(labeled: bool, after_fbx_tap: list[str], after_blend_tap: list[str],
                    fbx_path: Path, blend_path: Path) -> list[str]:
    """Judge the button label and each picker tap by what reached Blender's System locations."""
    problems = []
    if not labeled:
        problems.append(f"the add-location button is not named {ADD_LOCATION_TITLE!r}, so people "
                        "expect to pick the file they want to import")
    if any(Path(entry) == fbx_path for entry in after_fbx_tap):
        problems.append(f"the folder picker accepted a file and listed it as a folder: {fbx_path}")
    if any(Path(entry) == blend_path for entry in after_blend_tap):
        problems.append(f"the folder picker accepted a .blend and listed it as a folder: {blend_path}")
    return problems


def evaluate_document_open(before: dict, after: dict, expected: Path, label: str) -> list[str]:
    problems = []
    if not after:
        return [f"{label}: the app never reported a running main loop (crash or no launch)"]
    if before and after.get("pid") != before.get("pid"):
        problems.append(f"{label}: the app process changed from {before.get('pid')} to {after.get('pid')}")
    # Files hands over a copy in Documents/Inbox, renamed "-1", "-2" when one exists.
    if not Path(after.get("filepath") or "/").stem.startswith(expected.stem):
        problems.append(f"{label}: expected {expected.name} loaded, found {after.get('filepath')!r}")
    return problems


def evaluate_render(engine: str, gap: float, closed: bool) -> list[str]:
    problems = []
    if gap > STALL_LIMIT:
        problems.append(f"{engine}: main loop stalled {gap:.1f} s during F12 render")
    if not closed:
        problems.append(f"{engine}: native close button did not close the render window")
    return problems


class Session:
    def __init__(self, app: Path, udid: str, output: Path):
        self.app = app
        self.udid = udid
        self.output = output
        with (app / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        self.bundle_id = info["CFBundleIdentifier"]
        self.version = version_dir(info["CFBundleShortVersionString"])
        self.container = Path(run("xcrun", "simctl", "get_app_container", udid,
                                  self.bundle_id, "data").stdout.strip())
        self.tmp = self.container / "tmp"
        groups = run("xcrun", "simctl", "get_app_container", udid,
                     "com.apple.DocumentsApp", "groups").stdout
        storage = next(Path(line.split("\t", 1)[1]) for line in groups.splitlines()
                       if line.startswith("group.com.apple.FileProvider.LocalStorage\t"))
        self.external = storage / "File Provider Storage" / EXTERNAL_FOLDER
        self.springboard_before = springboard_reports()
        self.probe = (self.container / "Documents" / "Settings" / self.version /
                      "scripts" / "startup" / PROBE_NAME)

    def install_probe(self) -> None:
        self.probe.parent.mkdir(parents=True, exist_ok=True)
        self.probe.write_text(PROBE_SOURCE)

    def remove_probe(self) -> None:
        self.probe.unlink(missing_ok=True)

    def state(self) -> dict:
        try:
            return json.loads((self.tmp / "feedback-state.json").read_text())
        except (OSError, ValueError):
            return {}

    def wait_ticks(self, minimum: int = 5, timeout: float = 120.0, stale_pid: int | None = None) -> dict:
        """Wait for fresh ticks. A new process counts from zero; a stale one never counts."""
        deadline = time.monotonic() + timeout
        initial = self.state()
        while time.monotonic() < deadline:
            state = self.state()
            pid = state.get("pid")
            start = initial.get("ticks", 0) if pid == initial.get("pid") else 0
            if pid is not None and pid != stale_pid and state.get("ticks", 0) >= start + minimum:
                return state
            time.sleep(0.2)
        # The report can land seconds after the flow that triggered it returned.
        crashed = sorted(springboard_reports() - self.springboard_before)
        cause = f" after SpringBoard crashed {crashed}; rerun" if crashed else ""
        raise FeedbackFailure(f"main loop did not tick within {timeout:.0f} s{cause}: {self.state()}")

    def wait_document(self, expected: Path, timeout: float = 60.0) -> dict:
        """Wait for a document to load; return the last state either way."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state()
            if Path(state.get("filepath") or "/").stem.startswith(expected.stem):
                break
            time.sleep(0.2)
        return self.state()

    def launch(self) -> dict:
        # The previous process may write its state once more while it is terminated.
        stale_pid = self.state().get("pid")
        (self.tmp / "feedback-state.json").unlink(missing_ok=True)
        run("xcrun", "simctl", "launch", "--terminate-running-process", self.udid, self.bundle_id)
        return self.wait_ticks(10, stale_pid=stale_pid)

    def terminate(self) -> None:
        run("xcrun", "simctl", "terminate", self.udid, self.bundle_id, check=False)

    def command(self, source: str, timeout: float = 60.0) -> dict:
        result = self.tmp / "feedback-result.json"
        result.unlink(missing_ok=True)
        part = self.tmp / "feedback-command.part"
        part.write_text(source)
        part.replace(self.tmp / "feedback-command.py")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if result.exists():
                data = json.loads(result.read_text())
                if not data.get("ok"):
                    raise FeedbackFailure(f"command failed:\n{data.get('error')}")
                return data
            time.sleep(0.1)
        raise FeedbackFailure(f"command did not run within {timeout:.0f} s (main loop stalled?)")

    def maestro(self, name: str, flow: str, app_id: str | None = None) -> bool:
        path = self.output / f"{name}.yaml"
        path.write_text(f"appId: {app_id or self.bundle_id}\n---\n{flow}")
        before = springboard_reports()
        result = run("maestro", "--device", self.udid, "test", "--test-output-dir",
                     str(self.output / name), str(path), check=False)
        (self.output / f"{name}.log").write_text(result.stdout + result.stderr)
        # XCTest automation can crash the simulator's SpringBoard, which suspends the
        # app. That is a harness failure, not a frozen Blender.
        crashed = sorted(springboard_reports() - before)
        if crashed:
            raise FeedbackFailure(f"SpringBoard crashed during Maestro flow {name}: {crashed}; rerun")
        return result.returncode == 0

    def screenshot(self, name: str) -> Path:
        path = self.output / f"{name}.png"
        run("xcrun", "simctl", "io", self.udid, "screenshot", str(path), check=False)
        return path

    def sample_ticks(self, until, timeout: float) -> list[float]:
        times = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not until():
            stamp = self.state().get("time")
            if stamp:
                times.append(stamp)
            time.sleep(0.1)
        return times


def stage_external_folder(session: Session, blend: Path, assets: list[Path]) -> None:
    shutil.rmtree(session.external, ignore_errors=True)
    session.external.mkdir(parents=True)
    shutil.copy(blend, session.external / SHARED_DOCUMENT)
    for asset in assets:
        shutil.copy(asset, session.external / asset.name)


def check_import_picker(session: Session) -> dict:
    fixture = session.tmp / "feedback-picker.dylib"
    run("xcrun", "--sdk", "iphonesimulator", "clang++", "-std=c++17", "-dynamiclib",
        "-target", "arm64-apple-ios18.0-simulator", "-framework", "Foundation",
        "-framework", "UIKit", str(FIXTURE_SOURCE), "-o", str(fixture))
    run("codesign", "-s", "-", str(fixture))
    names = sorted(p.name for p in session.external.iterdir())
    session.launch()
    session.command(f'''import ctypes
fixture = ctypes.CDLL({str(fixture)!r})
fixture.blender_test_set_picker_directory.argtypes = [ctypes.c_char_p]
fixture.blender_test_set_picker_directory({str(session.external).encode()!r})
''' + VIEW3D_CONTEXT + '''with bpy.context.temp_override(window=win, area=area):
    result["invoke"] = sorted(bpy.ops.import_scene.fbx("INVOKE_DEFAULT"))
''')
    fbx_point = PICKER_GRID[names.index("cube.fbx")]
    # When the tapped item could not be chosen, leave by granting the shown folder.
    close = f'''- runFlow:
    when:
      visible: Cancel
    commands:
      - tapOn:
          point: {PICKER_OPEN}
      - waitForAnimationToEnd
'''
    bookmarks_query = FILE_BROWSER_CONTEXT + \
        'result["bookmarks"] = [e.path for e in area.spaces.active.system_bookmarks]\n'
    labeled = session.maestro("add-folder-label", label_flow())
    session.maestro("picker-fbx", picker_flow(fbx_point, "picker-fbx") + close)
    session.wait_ticks(5)
    after_fbx = session.command(bookmarks_query)["bookmarks"]
    blend_point = PICKER_GRID[names.index(SHARED_DOCUMENT)]
    session.maestro("picker-blend", picker_flow(blend_point, "picker-blend") + close)
    session.wait_ticks(5)
    bookmarks = session.command(bookmarks_query)["bookmarks"]
    problems = evaluate_picker(labeled, after_fbx, bookmarks, session.external / "cube.fbx",
                               session.external / SHARED_DOCUMENT)
    # Blender's own browser is the working route once the folder itself is granted.
    imported = session.command(FILE_BROWSER_CONTEXT + f'''params.directory = {str(session.external).encode() + b"/"!r}
params.filename = "cube.fbx"
state["objects_before"] = len(bpy.data.objects)
with bpy.context.temp_override(window=win, area=area, region=region):
    result["execute"] = sorted(bpy.ops.file.execute())
''')
    session.wait_ticks(5)
    after = session.command('result["added"] = len(bpy.data.objects) - state["objects_before"]\n')
    session.terminate()
    return {"listing": names, "labeled": labeled, "after_fbx_tap": after_fbx, "after_blend_tap": bookmarks,
            "browser_import": imported["execute"], "objects_added": after["added"],
            "problems": problems}


def check_blend_compat(session: Session, hosts: list[Path]) -> dict:
    session.launch()
    folder = session.container / "Documents" / "feedback-compat"
    shutil.rmtree(folder, ignore_errors=True)
    session.command(f'''folder = {str(folder)!r}
os.makedirs(folder, exist_ok=True)
bpy.ops.wm.read_homefile(use_factory_startup=True)
result["compress_pref"] = bpy.context.preferences.filepaths.use_file_compression
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, "factory.blend"), copy=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, "modified.blend"))
''' + VIEW3D_CONTEXT + '''with bpy.context.temp_override(window=win, area=area, region=region):
    bpy.ops.mesh.primitive_monkey_add(location=(2, 0, 0))
bpy.data.objects["Cube"].data.materials.append(bpy.data.materials.new("FeedbackMaterial"))
bpy.ops.wm.save_mainfile()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, "uncompressed.blend"), copy=True, compress=False)
''')
    session.terminate()
    local = session.output / "compat"
    shutil.rmtree(local, ignore_errors=True)
    shutil.copytree(folder, local, ignore=shutil.ignore_patterns("*.blend1"))
    files = {path.name: parse_blend_header(path.read_bytes()[:32]) for path in sorted(local.glob("*.blend"))}
    loader = session.output / "host_load.py"
    loader.write_text('''import bpy, sys
path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
print("FEEDBACK-LOADED", bpy.app.version_string, sorted(o.name for o in bpy.data.objects))
''')
    loads, problems = [], []
    for host in hosts:
        binary = host / "Contents" / "MacOS" / "Blender" if host.suffix == ".app" else host
        for name in files:
            result = run(str(binary), "--background", "--factory-startup", "--python", str(loader),
                         "--", str(local / name), check=False, timeout=900)
            output = result.stdout + result.stderr
            version = host_version(output)
            outcome = classify_host_load(output)
            loads.append({"host": str(host), "version": version, "file": name, "outcome": outcome,
                          "detail": next((line for line in output.splitlines()
                                          if "FEEDBACK-LOADED" in line or "Cannot read" in line), "")})
            if outcome != "loaded" and version and version >= (4, 5, 0):
                problems.append(f"Blender {'.'.join(map(str, version))} could not load iOS {name}")
    return {"files": files, "loads": loads, "problems": problems}


def check_save(session: Session) -> dict:
    session.launch()
    steps, problems = {}, []
    session.command('bpy.ops.wm.read_homefile()\n')
    session.command(VIEW3D_CONTEXT + '''with bpy.context.temp_override(window=win, area=area, region=region):
    bpy.ops.transform.translate(value=(0, 0, 1))
    result["invoke"] = sorted(bpy.ops.wm.save_mainfile("INVOKE_DEFAULT"))
''')
    session.wait_ticks(5)
    if "FILE_BROWSER" not in session.state().get("windows", []):
        problems.append("File > Save on an untitled file did not open the file browser")
        return {"steps": steps, "problems": problems}
    target = session.external / "saved-from-ios.blend"
    steps["save_as"] = session.command(FILE_BROWSER_CONTEXT + f'''params.directory = {str(session.external).encode() + b"/"!r}
params.filename = {target.name!r}
start = time.time()
with bpy.context.temp_override(window=win, area=area, region=region):
    result["execute"] = sorted(bpy.ops.file.execute())
result["seconds"] = time.time() - start
''')
    session.wait_ticks(5)
    steps["resave"] = session.command(VIEW3D_CONTEXT + '''with bpy.context.temp_override(window=win, area=area, region=region):
    bpy.ops.transform.translate(value=(0, 1, 0))
    start = time.time()
    result["save"] = sorted(bpy.ops.wm.save_mainfile("INVOKE_DEFAULT"))
    result["seconds"] = time.time() - start
''')
    session.command(f'bpy.ops.wm.open_mainfile(filepath={str(session.external / SHARED_DOCUMENT)!r})\n')
    session.wait_ticks(5)
    steps["save_opened_document"] = session.command(VIEW3D_CONTEXT + '''with bpy.context.temp_override(window=win, area=area, region=region):
    bpy.ops.mesh.primitive_cylinder_add(location=(-3, 0, 0))
    start = time.time()
    result["save"] = sorted(bpy.ops.wm.save_mainfile("INVOKE_DEFAULT"))
    result["seconds"] = time.time() - start
result["filepath"] = bpy.data.filepath
''')
    final = session.wait_ticks(5)
    session.terminate()
    for name, step in steps.items():
        if step.get("seconds", 0) > SAVE_LIMIT:
            problems.append(f"{name} took {step['seconds']:.1f} s")
    if not target.exists():
        problems.append(f"Save As did not write {target}")
    if not (session.external / (SHARED_DOCUMENT + "1")).exists():
        problems.append("saving over the opened document did not keep a .blend1 backup")
    if final.get("dirty"):
        problems.append("the document is still dirty after saving")
    return {"steps": steps, "files": sorted(p.name for p in session.external.iterdir()),
            "problems": problems}


def check_render(session: Session, cycles: int) -> dict:
    session.launch()
    session.command('bpy.ops.wm.read_homefile()\n')
    renders, problems = [], []
    for engine in ("BLENDER_EEVEE", "CYCLES"):
        for cycle in range(cycles):
            done = session.tmp / "feedback-render-done.txt"
            done.unlink(missing_ok=True)
            session.command(VIEW3D_CONTEXT + f'''scene = bpy.context.scene
scene.render.engine = {engine!r}
scene.eevee.taa_render_samples = 64
scene.cycles.samples = 32
bpy.app.handlers.render_complete.clear()
bpy.app.handlers.render_cancel.clear()
def _done(*_args):
    with open(os.path.expanduser("~/tmp/feedback-render-done.txt"), "w") as handle:
        handle.write(str(time.time()))
bpy.app.handlers.render_complete.append(_done)
bpy.app.handlers.render_cancel.append(_done)
state["render_started"] = time.time()
with bpy.context.temp_override(window=win, area=area):
    result["render"] = sorted(bpy.ops.render.render("INVOKE_DEFAULT"))
''')
            started = time.time()
            times = session.sample_ticks(done.exists, 600)
            seconds = time.time() - started
            times += session.sample_ticks(lambda: False, 2)
            gap, _ = longest_gap(times)
            session.screenshot(f"render-{engine.lower()}-{cycle}")
            closed = session.maestro(f"render-close-{engine.lower()}-{cycle}", close_flow())
            if closed:
                closed = len(session.wait_ticks(5).get("windows", [])) == 1
            renders.append({"engine": engine, "cycle": cycle, "seconds": round(seconds, 2),
                            "longest_stall": round(gap, 2), "closed": closed})
            problems += evaluate_render(engine, gap, closed)
            if not closed:
                session.maestro(f"render-close-retry-{engine.lower()}-{cycle}", close_flow())
    session.terminate()
    return {"renders": renders, "problems": problems}


def check_open_document(session: Session) -> dict:
    document = session.external / SHARED_DOCUMENT
    results, problems = {}, []
    crash_reports = DIAGNOSTIC_REPORTS
    before_crashes = {p.name for p in crash_reports.glob("Blender*")}

    session.terminate()
    (session.tmp / "feedback-state.json").unlink(missing_ok=True)
    run("xcrun", "simctl", "openurl", session.udid, file_url(document))
    results["openurl_cold"] = session.wait_document(document)
    problems += evaluate_document_open({}, results["openurl_cold"], document, "openurl cold")

    before = session.command('bpy.ops.wm.read_homefile()\n') and session.wait_ticks(5)
    run("xcrun", "simctl", "openurl", session.udid, file_url(document))
    results["openurl_warm"] = session.wait_document(document)
    problems += evaluate_document_open(before, results["openurl_warm"], document, "openurl warm")

    before = session.command('bpy.ops.wm.read_homefile()\n') and session.wait_ticks(5)
    names = sorted(p.name for p in session.external.iterdir())
    session.maestro("files-open", files_open_flow(FILES_GRID[1], FILES_GRID[names.index(SHARED_DOCUMENT)]),
                    app_id="com.apple.DocumentsApp")
    results["files_tap_warm"] = session.wait_document(document)
    problems += evaluate_document_open(before, results["files_tap_warm"], document, "Files tap warm")

    session.terminate()
    (session.tmp / "feedback-state.json").unlink(missing_ok=True)
    session.maestro("files-open-cold", files_open_flow(FILES_GRID[1], FILES_GRID[names.index(SHARED_DOCUMENT)]),
                    app_id="com.apple.DocumentsApp")
    results["files_tap_cold"] = session.wait_document(document)
    problems += evaluate_document_open({}, results["files_tap_cold"], document, "Files tap cold")
    session.terminate()
    new_crashes = sorted({p.name for p in crash_reports.glob("Blender*")} - before_crashes)
    if new_crashes:
        problems.append(f"new crash reports: {new_crashes}")
    return {"results": results, "crash_reports": new_crashes, "problems": problems}


def create_assets(session: Session) -> tuple[Path, list[Path]]:
    """Make the shared document and importable assets with the app itself."""
    folder = session.container / "Documents" / "feedback-assets"
    shutil.rmtree(folder, ignore_errors=True)
    session.launch()
    session.command(f'''folder = {str(folder)!r}
os.makedirs(folder, exist_ok=True)
bpy.ops.wm.read_homefile(use_factory_startup=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(folder, "cube.fbx"))
image = bpy.data.images.new("texture", 32, 32)
image.filepath_raw = os.path.join(folder, "texture.png")
image.file_format = "PNG"
image.save()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, {SHARED_DOCUMENT!r}), copy=True)
''', timeout=180)
    session.terminate()
    return folder / SHARED_DOCUMENT, [folder / "cube.fbx", folder / "texture.png"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--device", required=True, help="UDID of one booted iPad simulator")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="append", choices=CHECKS)
    parser.add_argument("--host-blender", action="append", default=[], type=Path,
                        help="macOS Blender.app or binary used to load the iOS files")
    parser.add_argument("--render-cycles", type=int, default=2)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    app = args.app.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.skip_install:
        with (app / "Info.plist").open("rb") as handle:
            bundle_id = plistlib.load(handle)["CFBundleIdentifier"]
        # Start clean: saved Files locations live in the app's preferences.
        run("xcrun", "simctl", "terminate", args.device, bundle_id, check=False)
        run("xcrun", "simctl", "uninstall", args.device, bundle_id, check=False)
        run("xcrun", "simctl", "install", args.device, str(app))
    session = Session(app, args.device, output)
    session.install_probe()
    report: dict = {}
    try:
        blend, assets = create_assets(session)
        for check in args.check or CHECKS:
            stage_external_folder(session, blend, assets)
            if check == "import-picker":
                report[check] = check_import_picker(session)
            elif check == "blend-compat":
                report[check] = check_blend_compat(session, args.host_blender)
            elif check == "save":
                report[check] = check_save(session)
            elif check == "render":
                report[check] = check_render(session, args.render_cycles)
            else:
                report[check] = check_open_document(session)
            status = "FAIL" if report[check]["problems"] else "PASS"
            print(f"[{check}] {status}")
            for problem in report[check]["problems"]:
                print(f"  - {problem}")
    finally:
        session.terminate()
        session.remove_probe()
        (output / "feedback-report.json").write_text(json.dumps(report, indent=2, default=str))
    return 1 if any(entry["problems"] for entry in report.values()) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FeedbackFailure, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}")
        raise SystemExit(2)
