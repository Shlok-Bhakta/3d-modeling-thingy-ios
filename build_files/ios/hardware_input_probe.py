# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Observe real Blender input and tool outcomes on a dedicated test simulator.

The launcher supplies PROBE_DIRECTORY in this script's globals. Input enters
through SimulatorKit HID, never through Blender's operator or event simulation.
"""
import json
import os
from pathlib import Path
import time
import traceback

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Quaternion, Vector

folder = Path(PROBE_DIRECTORY)
folder.mkdir(parents=True, exist_ok=True)
window = bpy.context.window_manager.windows[0]
events = []
ticks = 0
pointer = None
case = 'cube'
bpy.context.preferences.view.show_splash = False


def view_context():
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return area, region


def setup(kind):
    global case, events
    case = kind
    events = []
    area, region = view_context()
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    if kind == 'pose':
        obj = bpy.data.objects.get('Input test armature')
        if obj is None:
            bpy.ops.object.armature_add()
            obj = bpy.context.object
            obj.name = 'Input test armature'
        obj.select_set(True)
        obj.show_in_front = True
        window.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='POSE')
        bone = obj.data.bones[0]
        obj.pose.bones[0].select = True
        obj.data.bones.active = bone
        obj.pose.bones[0].location = (0, 0, 0)
    else:
        obj = bpy.data.objects['Cube']
        obj.select_set(True)
        window.view_layer.objects.active = obj
        obj.location = (0, 0, 0)
        obj.rotation_euler = (0, 0, 0)
        obj.scale = (1, 1, 1)
    bpy.data.objects['Cube'].hide_set(kind == 'pose')
    armature = bpy.data.objects.get('Input test armature')
    if armature:
        armature.hide_set(kind != 'pose')
    space = area.spaces.active
    space.shading.type = 'SOLID'
    space.show_region_ui = False
    space.region_3d.view_perspective = 'ORTHO'
    space.region_3d.view_rotation = Quaternion((1, 0, 0, 0))
    space.region_3d.view_location = (0, 0, 0)
    space.region_3d.view_distance = 10
    space.show_gizmo = True
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.tool_set_by_id(name='builtin.move')
    area.tag_redraw()


class INPUT_OT_probe(bpy.types.Operator):
    bl_idname = 'wm.ios_input_probe'
    bl_label = 'iOS input regression observer'

    def modal(self, context, event):
        global pointer
        pointer = [event.mouse_x, event.mouse_y]
        if event.type not in {'TIMER', 'TIMER_REPORT'}:
            events.append(dict(type=event.type, value=event.value, x=event.mouse_x,
                               y=event.mouse_y, shift=event.shift, ctrl=event.ctrl,
                               alt=event.alt, oskey=event.oskey))
            del events[:-150]
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def sample_impl():
    global ticks
    ticks += 1
    command = folder / 'command.json'
    if command.exists():
        options = json.loads(command.read_text())
        command.unlink()
        if 'setup' in options:
            setup(options['setup'])
        if 'orbit_method' in options:
            bpy.context.preferences.inputs.view_rotate_method = options['orbit_method']
        if 'warp' in options:
            window.cursor_warp(*options['warp'])
        if options.get('clear'):
            events.clear()
    area, region = view_context()
    view = area.spaces.active.region_3d
    origin = location_3d_to_region_2d(region, view, Vector((0, 0, 0)))
    obj = window.view_layer.objects.active
    location = list(obj.pose.bones[0].location if obj.mode == 'POSE' else obj.location)
    state = dict(t=time.time(), pid=os.getpid(), ticks=ticks, case=case,
                 width=window.width, height=window.height,
                 pointer=pointer, events=events, location=location, mode=obj.mode,
                 object_rotation=list(obj.rotation_euler), object_scale=list(obj.scale),
                 rotation=list(view.view_rotation), distance=view.view_distance,
                 view_location=list(view.view_location),
                 origin=[region.x + origin.x, region.y + origin.y],
                 region=[region.x, region.y, region.width, region.height])
    temporary = folder / 'state.new'
    temporary.write_text(json.dumps(state))
    temporary.replace(folder / 'state.json')
    return .05


def sample():
    try:
        return sample_impl()
    except Exception:
        (folder / 'error.txt').write_text(traceback.format_exc())
        return None


def start():
    setup('cube')
    bpy.utils.register_class(INPUT_OT_probe)
    area, region = view_context()
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.wm.ios_input_probe('INVOKE_DEFAULT')
    bpy.app.timers.register(sample)


bpy.app.timers.register(start, first_interval=1)
