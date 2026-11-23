#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Drag a file onto Blender with a real UIKit drag in a simulator build.

A test-only dylib (tests/file_drop_source.m) adds a small view to Blender's window that
offers an OBJ file through UIDragInteraction. SimulatorKit HID touches long-press that
view and drag it over the 3D viewport, so the drop reaches Blender through UIKit the way
a drag from the Files app does. Return then confirms Blender's import dialog.

in-place: the source offers the file itself. Blender must import it from where it is
          and must not copy it.
copy:     the source only offers a temporary copy, like a drag from Photos. Blender must
          keep its own copy in Documents/Dropped Files and import that.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import time


HERE = Path(__file__).resolve().parent
MODES = ('in-place', 'copy')
DROP_FOLDER = 'Dropped Files'
RETURN_KEY = 0x28

PROBE_SOURCE = '''\
import json, os, time
import bpy

folder = PROBE_DIRECTORY
window = bpy.context.window_manager.windows[0]
bpy.context.preferences.view.show_splash = False
ticks = 0


def tick():
    global ticks
    ticks += 1
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    state = dict(pid=os.getpid(), ticks=ticks, width=window.width, height=window.height,
                 viewport=[region.x, region.y, region.width, region.height],
                 objects=sorted(o.name for o in bpy.data.objects if o.type == 'MESH'))
    temporary = os.path.join(folder, 'state.new')
    with open(temporary, 'w') as handle:
        json.dump(state, handle)
    os.replace(temporary, os.path.join(folder, 'state.json'))
    return 0.2


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
'''


def run(*args, **kwargs):
    result = subprocess.run(list(map(str, args)), text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{args[:3]} failed ({result.returncode}):\n' +
                           result.stdout + result.stderr)
    return result


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


def wait_for(predicate, description, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError(f'timed out waiting for {description}')


def fixture(mode):
    """An OBJ triangle whose object name says which drop produced it."""
    return (f'o {object_name(mode)}\n'
            'v 0 0 0\nv 1 0 0\nv 0 1 0\n'
            'f 1 2 3\n')


def object_name(mode):
    return 'Dropped' + ''.join(part.title() for part in mode.split('-'))


def viewport_target(state):
    """The 3D viewport center as a normalized touch point (window origin bottom left)."""
    x, y, width, height = state['viewport']
    return [(x + width * .6) / state['width'], 1 - (y + height * .5) / state['height']]


def drag_events(source, target, steps=24):
    """Long-press the source until UIKit lifts the drag, carry it to target and drop."""
    events = [dict(points=[source], phase=1, wait=.1)]
    events += [dict(points=[source], phase=6, wait=.15) for _ in range(8)]
    for step in range(1, steps + 1):
        point = [source[i] + (target[i] - source[i]) * step / steps for i in range(2)]
        events.append(dict(points=[point], phase=6, wait=.05))
    events += [dict(points=[target], phase=6, wait=.15) for _ in range(5)]
    events.append(dict(points=[target], phase=2, wait=.1))
    return events


def return_key():
    return [dict(key=RETURN_KEY, phase=1, wait=.1), dict(key=RETURN_KEY, phase=2, wait=.1)]


def evaluate(mode, operation, objects, source, dropped):
    """Return the problems with a finished drop, or an empty list."""
    problems = []
    if operation != 'copy':
        problems.append(f'Blender did not accept the drop; UIKit ended it with operation {operation}')
    name = object_name(mode)
    if name not in objects:
        problems.append(f'the dropped OBJ was not imported; mesh objects are {objects}')
    if mode == 'in-place' and dropped:
        problems.append(f'a file offered in place was copied to {dropped}')
    if mode == 'copy':
        if len(dropped) != 1:
            problems.append(f'expected one kept copy in {DROP_FOLDER}, found {dropped}')
        elif dropped[0].read_bytes() != source.read_bytes():
            problems.append(f'the kept copy {dropped[0]} does not match the dropped file')
    return problems


def exercise(app, device, output, mode, skip_install):
    output.mkdir(parents=True, exist_ok=True)
    bundle = plistlib.loads((app / 'Info.plist').read_bytes())['CFBundleIdentifier']
    if not skip_install:
        run('xcrun', 'simctl', 'install', device, app)
    subprocess.run(['xcrun', 'simctl', 'terminate', device, bundle], capture_output=True)
    container = Path(run('xcrun', 'simctl', 'get_app_container', device, bundle, 'data')
                     .stdout.strip())
    folder = container / 'tmp' / 'file-drop'
    folder.mkdir(parents=True, exist_ok=True)
    for stale in ('state.json', 'source.json'):
        (folder / stale).unlink(missing_ok=True)
    inbox = container / 'Documents' / DROP_FOLDER
    for stale in inbox.glob('*') if inbox.exists() else ():
        stale.unlink()
    # Documents is a Files location, like the folders people drag from.
    source_folder = container / 'Documents' / 'Drop Source'
    source_folder.mkdir(parents=True, exist_ok=True)
    source = source_folder / f'{mode}.obj'
    source.write_text(fixture(mode))

    library = folder / 'file-drop-source.dylib'
    run('xcrun', '--sdk', 'iphonesimulator', 'clang', '-target', 'arm64-apple-ios18.0-simulator',
        '-fobjc-arc', '-dynamiclib', '-framework', 'Foundation', '-framework', 'UIKit',
        '-framework', 'CoreGraphics', '-framework', 'UniformTypeIdentifiers',
        HERE / 'tests' / 'file_drop_source.m', '-o', library)
    helper = output / 'hardware-hid'
    run('xcrun', 'clang', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'AppKit',
        HERE / 'simulator_gesture_hid.m', '-o', helper)

    environment = dict(os.environ,
                       SIMCTL_CHILD_DYLD_INSERT_LIBRARIES=str(library),
                       SIMCTL_CHILD_BLENDER_DROP_SOURCE_FILE=str(source),
                       SIMCTL_CHILD_BLENDER_DROP_SOURCE_MODE=mode,
                       SIMCTL_CHILD_BLENDER_DROP_SOURCE_REPORT=str(folder / 'source.json'))
    probe = f'PROBE_DIRECTORY={str(folder)!r}\n' + PROBE_SOURCE
    launch = run('xcrun', 'simctl', 'launch', '--terminate-running-process',
                 f'--stdout={output / "app-stdout.log"}', f'--stderr={output / "app-stderr.log"}',
                 device, bundle, '--factory-startup', '--python-expr', f'exec({probe!r})',
                 env=environment, timeout=90)
    pid = int(launch.stdout.strip().rsplit(':', 1)[1])

    def state():
        current = read_json(folder / 'state.json')
        return current if current and current['pid'] == pid else None

    ready = wait_for(lambda: (s := state()) and s['ticks'] > 8 and s, 'the Blender probe', 90)
    chip = wait_for(lambda: (s := read_json(folder / 'source.json')) and s['pid'] == pid and s,
                    'the test drag source', 30)

    hid_environment = dict(os.environ, DEVELOPER_DIR=run('xcode-select', '-p').stdout.strip())

    def send(events):
        run(helper, device, input=json.dumps(events), env=hid_environment, timeout=60)

    send(drag_events(chip['center'], viewport_target(ready)))
    drag = wait_for(lambda: (s := read_json(folder / 'source.json')) and 'ended' in s and s,
                    'the drag session to end', 10)
    if not drag.get('began'):
        raise RuntimeError('the HID long press did not start a UIKit drag session')
    time.sleep(2)
    run('xcrun', 'simctl', 'io', device, 'screenshot', output / 'after-drop.png')
    send(return_key())
    name = object_name(mode)
    try:
        wait_for(lambda: (s := state()) and name in s['objects'], 'the imported object', 15)
    except RuntimeError:
        pass
    run('xcrun', 'simctl', 'io', device, 'screenshot', output / 'after-confirm.png')

    final = state() or {}
    dropped = sorted(inbox.glob('*')) if inbox.exists() else []
    problems = evaluate(mode, drag['ended'], final.get('objects', []), source, dropped)
    report = dict(mode=mode, drop_operation=drag['ended'], objects=final.get('objects'),
                  dropped=[str(p) for p in dropped],
                  problems=problems, result='FAIL' if problems else 'PASS')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for problem in problems:
        print(f'FAIL: {mode}: {problem}', flush=True)
    if not problems:
        print(f'PASS: {mode}', flush=True)
    return not problems


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--device', required=True, help='A booted test simulator')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', action='append', choices=MODES)
    parser.add_argument('--skip-install', action='store_true')
    args = parser.parse_args()
    passed = True
    for index, mode in enumerate(args.mode or MODES):
        passed &= exercise(args.app.resolve(), args.device, args.output.resolve() / mode, mode,
                           args.skip_install or index > 0)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
