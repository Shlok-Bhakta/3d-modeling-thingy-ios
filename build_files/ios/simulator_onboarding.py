#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the first-launch gesture guide on a dedicated iPad simulator.

A launch from the Home Screen has no Blender arguments, so it must show the guide once.
Dismissing it must persist across launches. While it is visible, touches must not reach
Blender, and after it closes the canvas must receive input again. Automated launches pass
Blender arguments and skip the guide, so `BLENDER_IOS_ONBOARDING=1` forces it for the probe.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import time


HERE = Path(__file__).resolve().parent
GUIDE_ID = 'blender_onboarding'
PAGES = ('Your finger is the mouse', 'Getting around', 'Shortcuts', 'A few more things')


def run(*args, check=True, **kwargs):
    result = subprocess.run(list(map(str, args)), text=True, capture_output=True, **kwargs)
    if check and result.returncode:
        raise RuntimeError(f'{args[:3]} failed ({result.returncode}):\n' +
                           result.stdout + result.stderr)
    return result


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


def wait_for(predicate, description, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError(f'timed out waiting for {description}')


def step_through_flow():
    """Page forward and back through the guide by its buttons, then finish it."""
    lines = ['- extendedWaitUntil:', '    visible:', f'      id: {GUIDE_ID}', '    timeout: 90000',
             f'- assertVisible: "{PAGES[0]}"',
             # A tap on the dimmed backdrop must neither close the guide nor reach Blender.
             '- tapOn:', '    point: 50%,4%',
             f'- assertVisible: "{PAGES[0]}"']
    lines += ['- takeScreenshot: guide-page-1']
    for index, title in enumerate(PAGES[1:], 2):
        lines += ['- tapOn:', f'    id: {GUIDE_ID}_next', f'- assertVisible: "{title}"',
                  '- waitForAnimationToEnd', f'- takeScreenshot: guide-page-{index}']
    lines += ['- tapOn:', f'    id: {GUIDE_ID}_back', f'- assertVisible: "{PAGES[-2]}"',
              '- tapOn:', f'    id: {GUIDE_ID}_next',
              '- tapOn:', f'    id: {GUIDE_ID}_done',
              '- extendedWaitUntil:', '    notVisible:', f'      id: {GUIDE_ID}', '    timeout: 10000']
    return '\n'.join(lines) + '\n'


def skip_flow():
    return '\n'.join(['- extendedWaitUntil:', '    visible:', f'      id: {GUIDE_ID}',
                      '    timeout: 90000',
                      '- tapOn:', f'    id: {GUIDE_ID}_skip',
                      '- extendedWaitUntil:', '    notVisible:', f'      id: {GUIDE_ID}',
                      '    timeout: 10000']) + '\n'


def absent_flow(appear_timeout_ms):
    # Give the guide at least as long to appear as it took on the first launch.
    return '\n'.join(['- extendedWaitUntil:', '    visible:', f'      id: {GUIDE_ID}',
                      f'    timeout: {appear_timeout_ms}', '    optional: true',
                      '- assertNotVisible:', f'    id: {GUIDE_ID}']) + '\n'


def canvas_tap_flow():
    return '- tapOn:\n    point: 30%,50%\n'


def left_presses(state):
    return [e for e in state['events'] if e['type'] == 'LEFTMOUSE' and e['value'] == 'PRESS']


class Simulator:
    def __init__(self, app: Path, device: str, output: Path):
        self.app = app
        self.device = device
        self.output = output
        self.bundle = plistlib.loads((app / 'Info.plist').read_bytes())['CFBundleIdentifier']

    def maestro(self, name, body):
        flow = self.output / f'{name}.yaml'
        flow.write_text(f'appId: {self.bundle}\n---\n{body}')
        started = time.monotonic()
        result = run('maestro', '--device', self.device, 'test', '--test-output-dir',
                     self.output / name, flow, check=False)
        (self.output / f'{name}.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise AssertionError(f'{name} failed, see {self.output / f"{name}.log"}')
        print(f'PASS: {name}', flush=True)
        return time.monotonic() - started

    def launch(self, *arguments, environment=None):
        run('xcrun', 'simctl', 'terminate', self.device, self.bundle, check=False)
        return run('xcrun', 'simctl', 'launch', '--terminate-running-process', self.device,
                   self.bundle, *arguments, env=dict(os.environ, **(environment or {})), timeout=90)

    def container(self):
        return Path(run('xcrun', 'simctl', 'get_app_container', self.device, self.bundle,
                        'data').stdout.strip())


def exercise(simulator: Simulator):
    run('xcrun', 'simctl', 'uninstall', simulator.device, simulator.bundle, check=False)
    run('xcrun', 'simctl', 'install', simulator.device, simulator.app)

    # A Home Screen launch of a fresh install shows the guide, and Skip dismisses it.
    simulator.launch()
    appeared = simulator.maestro('first-launch-skip', skip_flow())

    # Skipping is remembered: the next ordinary launch shows Blender without the guide.
    simulator.launch()
    simulator.maestro('second-launch-absent', absent_flow(int(max(appeared, 30) * 1000)))

    # Forced under the input probe: the guide blocks Blender input until it is finished.
    folder = simulator.container() / 'tmp' / 'onboarding-regression'
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('state.json', 'error.txt', 'command.json'):
        (folder / name).unlink(missing_ok=True)
    source = f'PROBE_DIRECTORY={str(folder)!r}\n' + (HERE / 'hardware_input_probe.py').read_text()
    launch = simulator.launch('--factory-startup', '--python-exit-code', '7',
                              '--python-expr', f'exec({source!r})',
                              environment={'SIMCTL_CHILD_BLENDER_IOS_ONBOARDING': '1'})
    pid = int(launch.stdout.strip().rsplit(':', 1)[1])
    state_file = folder / 'state.json'

    def probe():
        if (folder / 'error.txt').exists():
            raise RuntimeError((folder / 'error.txt').read_text())
        state = read_json(state_file)
        return state if state and state.get('pid') == pid else None

    wait_for(lambda: (s := probe()) and s['ticks'] > 8, 'the Blender input probe', 120)
    simulator.maestro('forced-guide-steps', step_through_flow())
    during = probe()
    assert not left_presses(during), 'a tap on the guide reached Blender'
    ticks = during['ticks']
    wait_for(lambda: probe()['ticks'] > ticks + 8, 'Blender main-loop ticks after the guide closed')

    simulator.maestro('canvas-tap-after-guide', canvas_tap_flow())
    wait_for(lambda: left_presses(probe()), 'a canvas tap reaching Blender after the guide closed', 15)
    print('PASS: Blender receives touch input after the guide closes', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--device', help='Use an existing booted test simulator')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    owned = args.device is None
    device = args.device
    if owned:
        devices = json.loads(run('xcrun', 'simctl', 'list', 'devicetypes', '--json').stdout)
        kind = next(d['identifier'] for d in devices['devicetypes'] if 'iPad Pro 13' in d['name'])
        runtimes = json.loads(run('xcrun', 'simctl', 'list', 'runtimes', '--json').stdout)
        runtime = next(r['identifier'] for r in reversed(runtimes['runtimes'])
                       if r['isAvailable'] and r['name'].startswith('iOS'))
        device = run('xcrun', 'simctl', 'create', 'Blender onboarding regression', kind,
                     runtime).stdout.strip()
    output = args.output or Path(tempfile.mkdtemp(prefix='blender-onboarding-'))
    output.mkdir(parents=True, exist_ok=True)
    try:
        if owned:
            run('xcrun', 'simctl', 'boot', device)
            run('xcrun', 'simctl', 'bootstatus', device, '-b')
        exercise(Simulator(args.app.resolve(), device, output.resolve()))
    finally:
        if owned and device:
            run('xcrun', 'simctl', 'shutdown', device, check=False)
            run('xcrun', 'simctl', 'delete', device, check=False)


if __name__ == '__main__':
    main()
