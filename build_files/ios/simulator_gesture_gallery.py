#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Replay a captured gesture recipe through SimulatorKit and record its outcome."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

PHASES = {1, 2, 6}
TRANSFORMS = ('location', 'rotation', 'scale')


def replay_events(touches: list[dict]) -> list[dict]:
    """Convert recording-relative timestamps into serialized HID delays."""
    result = []
    previous = 0.0
    contacts = None
    for touch in touches:
        stamp = float(touch['t'])
        if not math.isfinite(stamp) or stamp < previous:
            raise ValueError('touch timestamps must be monotonic')
        phase = touch['phase']
        if 'key' in touch:
            if phase not in {1, 2}:
                raise ValueError('invalid key phase')
            event = {'key': touch['key'], 'phase': phase}
        else:
            points = touch['points']
            if phase not in PHASES or not 1 <= len(points) <= 4:
                raise ValueError('invalid touch phase or contact count')
            if any(len(p) != 2 or any(not 0 <= c <= 1 for c in p) for p in points):
                raise ValueError('touch coordinates must be normalized')
            if phase == 1:
                if contacts is not None:
                    raise ValueError('touch down before previous contacts were released')
                contacts = len(points)
            elif contacts != len(points):
                raise ValueError('touch move/up must match the active contacts')
            if phase == 2:
                contacts = None
            event = {'points': points, 'phase': phase}
        result.append(dict(event, wait=stamp - previous))
        previous = stamp
    if contacts is not None:
        raise ValueError('recipe ends with contacts still down')
    return result


def assert_outcome(before: dict, after: dict, expectations: dict) -> None:
    for field in expectations.get('changed', []):
        if before[field] == after[field]:
            raise AssertionError(f'{field} did not change')
    for field in expectations.get('unchanged', []):
        if before[field] != after[field]:
            raise AssertionError(f'{field} changed unexpectedly')
    if 'selected' in expectations and expectations['selected'] not in after['selected']:
        raise AssertionError('target object was not selected')
    wrap = expectations.get('wrap')
    if wrap:
        axis, size = (0, after['width']) if wrap == 'x' else (1, after['height'])
        if not before['pointer'][axis] > size * .9 or not after['pointer'][axis] < size * .5:
            raise AssertionError(f'cursor did not wrap across the {wrap} edge')
    if after['t'] <= before['t']:
        raise AssertionError('the main loop did not produce a fresh state sample')


def read_state(path: Path) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            state = json.loads(path.read_text())
            if time.time() - state['t'] < 2 and all(key in state for key in ('pointer','width','height')):
                return state
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(.05)
    raise RuntimeError('missing or stale probe state; load simulator_gesture_probe.py first')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True)
    parser.add_argument('--recipe', required=True, type=Path)
    parser.add_argument('--state-file', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text())
    events = replay_events(recipe['touches'])
    before = read_state(args.state_file)
    if (before['width'], before['height']) != (recipe['before']['width'], recipe['before']['height']):
        raise RuntimeError('simulator display dimensions do not match the recipe')
    expected_pointer = recipe['before']['pointer']
    if any(abs(a - b) > 25 for a, b in zip(before['pointer'], expected_pointer)):
        raise RuntimeError('aim the cursor at the recipe starting position before replaying')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    developer = subprocess.check_output(['xcode-select', '-p'], text=True).strip()
    environment = dict(os.environ, DEVELOPER_DIR=developer)
    with tempfile.TemporaryDirectory(prefix='gesture-gallery-') as tmp:
        helper = Path(tmp) / 'hid'
        subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-framework', 'Foundation',
                        '-framework', 'AppKit', str(Path(__file__).with_name('simulator_gesture_hid.m')),
                        '-o', str(helper)], check=True, env=environment)
        with args.output.with_suffix('.log').open('w') as log:
            capture = subprocess.Popen(['xcrun', 'simctl', 'io', args.device, 'recordVideo',
                                        '--codec=h264', '--force', str(args.output)],
                                       stdout=log, stderr=subprocess.PIPE, text=True)
            try:
                for line in capture.stderr:
                    log.write(line)
                    if 'Recording started' in line:
                        break
                else:
                    raise RuntimeError('simctl did not start recording')
                subprocess.run([str(helper), args.device], input=json.dumps(events), text=True,
                               env=environment, check=True)
                deadline = time.monotonic() + 5
                while True:
                    after = read_state(args.state_file)
                    try:
                        assert_outcome(before, after, recipe['expectations'])
                        break
                    except AssertionError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(.1)
                time.sleep(1)
            finally:
                if capture.poll() is None:
                    capture.send_signal(signal.SIGINT)
                capture.communicate(timeout=30)
        if not args.output.is_file() or args.output.stat().st_size == 0:
            raise RuntimeError('recording missing')
        result = dict(recipe=recipe['slug'], before=before, after=after, result='PASS')
        args.output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS: {args.output.resolve()}')


if __name__ == '__main__':
    main()
