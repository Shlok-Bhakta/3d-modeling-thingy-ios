# SPDX-FileCopyrightText: 2026 Blender Authors
# SPDX-License-Identifier: GPL-2.0-or-later
"""Load in Blender's Python Console on a dedicated documentation simulator.

Set DEMO_DIRECTORY to a writable path in the app container before executing.
This probe observes Blender state and leaves touch handling to production GHOST.
"""
import json
from pathlib import Path
import time
import bpy

folder = Path(DEMO_DIRECTORY)
folder.mkdir(parents=True, exist_ok=True)
marker = folder / 'state.json'
command = folder / 'command.py'
window = bpy.context.window_manager.windows[0]
# Build the default-Cube demonstration layout before attaching the observer.
screen = window.screen
if not any(a.type == 'NODE_EDITOR' for a in screen.areas):
    bpy.ops.screen.area_split(direction='HORIZONTAL', factor=.62)
    consoles = [a for a in screen.areas if a.type == 'CONSOLE']
    if len(consoles) != 2:
        raise RuntimeError('load the probe from the default viewport Python Console')
    node_area = min(consoles, key=lambda a: a.height)
    view_area = max(consoles, key=lambda a: a.height)
    node_area.type = 'NODE_EDITOR'
    node_area.ui_type = 'ShaderNodeTree'
    node_area.spaces.active.shader_type = 'OBJECT'
    view_area.type = 'VIEW_3D'
elif bpy.context.area.type == 'CONSOLE':
    bpy.context.area.type = 'VIEW_3D'
node_area = next(a for a in screen.areas if a.type == 'NODE_EDITOR')
node_area.ui_type = 'ShaderNodeTree'
node_area.spaces.active.shader_type = 'OBJECT'
node_area.spaces.active.show_region_ui = False
obj = bpy.data.objects['Cube']
if obj.active_material is None:
    obj.active_material = bpy.data.materials.new('Gesture demonstration')
obj.active_material.use_nodes = True
if not obj.active_material.node_tree.nodes.get('Noise Texture'):
    obj.active_material.node_tree.nodes.new('ShaderNodeTexNoise').location = (-450, 30)
view = next(a for a in screen.areas if a.type == 'VIEW_3D').spaces.active.region_3d
view.view_location = (0, 0, 0)
view.view_distance = 12
with bpy.context.temp_override(window=window, area=node_area,
                               region=next(r for r in node_area.regions if r.type == 'WINDOW')):
    bpy.ops.node.view_all()
pointer = None
last_event = None


class THINGY_OT_gesture_probe(bpy.types.Operator):
    bl_idname = 'wm.thingy_gesture_probe'
    bl_label = 'Documentation gesture probe'

    def modal(self, context, event):
        global pointer, last_event
        pointer = [event.mouse_x, event.mouse_y]
        last_event = event.type
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def sample():
    if command.exists():
        source = command.read_text()
        command.unlink()
        exec(source, globals())
    screen = window.screen
    area = next(a for a in screen.areas if a.type == 'VIEW_3D')
    region = area.spaces.active.region_3d
    nodes = next(a for a in screen.areas if a.type == 'NODE_EDITOR')
    node_region = next(r for r in nodes.regions if r.type == 'WINDOW')
    properties = next(a for a in screen.areas if a.type == 'PROPERTIES')
    property_region = next(r for r in properties.regions if r.type == 'WINDOW')
    obj = bpy.data.objects['Cube']
    material = obj.active_material
    data = dict(
        t=time.time(), width=window.width, height=window.height,
        pointer=pointer, event=last_event,
        view_location=list(region.view_location),
        view_rotation=list(region.view_rotation), view_distance=region.view_distance,
        location=list(obj.location), rotation=list(obj.rotation_euler), scale=list(obj.scale),
        selected=[o.name for o in window.view_layer.objects if o.select_get()],
        node_view=[node_region.view2d.region_to_view(0, 0),
                   node_region.view2d.region_to_view(node_region.width, node_region.height)],
        properties_view=[property_region.view2d.region_to_view(0, 0),
                         property_region.view2d.region_to_view(property_region.width, property_region.height)],
        node_locations={node.name: list(node.location) for node in material.node_tree.nodes},
        node_links=len(material.node_tree.links),
    )
    temporary = marker.with_suffix('.new')
    temporary.write_text(json.dumps(data))
    temporary.replace(marker)
    return .1


bpy.utils.register_class(THINGY_OT_gesture_probe)
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
with bpy.context.temp_override(window=window, area=area,
                               region=next(r for r in area.regions if r.type == 'WINDOW')):
    bpy.ops.wm.thingy_gesture_probe('INVOKE_DEFAULT')
def fit_nodes_after_layout():
    with bpy.context.temp_override(window=window, area=node_area,
                                   region=next(r for r in node_area.regions if r.type == 'WINDOW')):
        bpy.ops.node.view_all()
    return None


bpy.app.timers.register(fit_nodes_after_layout, first_interval=1.5)
bpy.app.timers.register(sample, first_interval=.1)
