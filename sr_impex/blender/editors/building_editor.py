"""Artist-facing building setup, state authoring and validated BMG export."""
import json
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty
from sr_impex.utilities.building_export import (
    find_building, create_grid, state_collections, child,
    CELL_ID, STATE_ID, STATE_FX, TRANSITIONS,
)
from sr_impex.utilities.building_layout import grid_from_blob
from sr_impex.utilities.resource_container import payload_bytes
from sr_impex.blender.editors.bmg_state_editor import MESHGRID_BLOB_KEY, switch_meshset_state


def _new_collection(parent, name):
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    return col


def add_state(root, index, state_id, objects):
    grid = create_grid(root)
    if not 0 <= index < len(grid.mesh_modules):
        raise ValueError("Cell index is outside the building grid")
    if (index, state_id) in state_collections(root):
        raise ValueError(f"Cell {index} already has state S{state_id}")
    anchor = child(root, 'MeshSetGrid_') or _new_collection(root, 'MeshSetGrid_0')
    module = next((c for c in anchor.children if c.get(CELL_ID) == index), None)
    if module is None:
        module = _new_collection(anchor, f'MeshSet_{index}')
        module[CELL_ID] = index
        module[TRANSITIONS] = '[]'
        marker = bpy.data.objects.new(f'Active_State_MeshSet_{index}', None)
        marker.empty_display_type = 'CUBE'
        marker.empty_display_size = .5
        marker.hide_viewport = True  # State bookkeeping only, not a viewport control.
        marker.hide_render = True
        marker['active_state'], marker['mesh_set_index'] = f'S{state_id}', index
        module.objects.link(marker)
    states = child(module, 'States_Collection') or _new_collection(module, f'States_Collection_{index}')
    state = _new_collection(states, f'S{state_id}_Undamaged' if state_id == 0 else f'S{state_id}_Damaged')
    state[CELL_ID] = state['mesh_set_index'] = index
    state[STATE_ID] = state_id
    state['state_type'] = f'S{state_id}'
    state[STATE_FX] = ''
    meshes = _new_collection(state, 'Meshes_Collection')
    go = next((o for o in root.objects if o.name.startswith('GameOrientation')), None)
    for obj in objects:
        world = obj.matrix_world.copy()
        if go:
            obj.parent = go
            obj.matrix_parent_inverse.identity()
            obj.matrix_world = world
        meshes.objects.link(obj)
    raw = json.loads(root[MESHGRID_BLOB_KEY])
    cells = raw.setdefault('cells', [])
    cell = next((c for c in cells if int(c['index']) == index), None)
    if cell is None:
        cell = {'index': index, 'rotation': 0}
        cells.append(cell)
    cell['has_mesh_set'] = 1
    cell['mesh_object_name'] = objects[0].name if objects else ''
    root[MESHGRID_BLOB_KEY] = json.dumps(raw)
    switch_meshset_state(module, f'S{state_id}')
    return state


class BMG_OT_NewBuilding(bpy.types.Operator):
    bl_idname = 'bmg.new_building'
    bl_label = 'Building from Selected Meshes'
    bl_description = 'Move selected meshes into a new building with an undamaged S0 state'
    bl_options = {'REGISTER', 'UNDO'}
    building_name: StringProperty(name='Building name', default='NewBuilding')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, 'Select at least one mesh')
            return {'CANCELLED'}
        if any(m.type == 'ARMATURE' for obj in meshes for m in obj.modifiers):
            self.report({'ERROR'}, 'For skinned buildings, import an animated BMG and add/edit its states with the existing game skeleton.')
            return {'CANCELLED'}
        root = _new_collection(context.scene.collection, 'DRSModel_' + (self.building_name.strip() or 'NewBuilding'))
        root[MESHGRID_BLOB_KEY] = json.dumps({'name': self.building_name, 'rows': 1, 'columns': 1,
            'orientation': 0, 'module_distance': 2., 'is_center_pivoted': 1, 'cells': []})
        from sr_impex.blender.transform_utils import create_empty
        create_empty(root)
        # Starting a new asset makes the current visible placement its geometry
        # basis; do not inherit display compensation from another BMG model.
        for obj in meshes:
            for key in ('_bmg_display_yaw', '_bmg_import_basis', '_bmg_import_transform'):
                if key in obj:
                    del obj[key]
        add_state(root, 4, 0, meshes)
        for obj in meshes:
            for col in list(obj.users_collection):
                if col not in root.children_recursive:
                    col.objects.unlink(obj)
            if not obj.data.materials:
                from sr_impex.blender.drs_material import DRSMaterial
                obj.data.materials.append(DRSMaterial(self.building_name + '_Default').material)
        self.report({'INFO'}, 'Building created. Edit materials and add damaged states in the BMG Editor tab.')
        return {'FINISHED'}


class BMG_OT_BuildingSettings(bpy.types.Operator):
    bl_description = 'Edit the building grid dimensions and ground resource'
    bl_idname = 'bmg.building_settings'
    bl_label = 'Building Grid Settings'
    bl_options = {'REGISTER', 'UNDO'}
    name_value: StringProperty(name='Resource name')
    half_extent: IntProperty(name='Grid half extent', min=0, max=127, default=1)
    spacing: FloatProperty(name='Cell spacing', min=.001, default=2.)
    yaw: IntProperty(name='Rotation (degrees)', min=-32768, max=32767)
    shared_origin: BoolProperty(name='Shared origin for all modules', default=True)
    ground_decal: StringProperty(name='Ground resource', description='Optional ground decal DRS reference')
    debris_effect: StringProperty(name='Cell hit effect')
    destruction_effect: StringProperty(name='Building crush effect')

    def invoke(self, context, event):
        try:
            grid = create_grid(find_building(context))
            self.name_value, self.half_extent = grid.name, grid.grid_width
            self.spacing, self.yaw = grid.module_distance, grid.grid_rotation
            self.shared_origin = bool(grid.is_center_pivoted)
            self.ground_decal, self.debris_effect = grid.ground_decal, grid.debris_effect
            self.destruction_effect = grid.destruction_effect
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=440)

    def execute(self, context):
        try:
            root = find_building(context)
            old = create_grid(root)
            blob = json.loads(root[MESHGRID_BLOB_KEY])
            # Reconstruct from the current complete grid; grid_from_blob handles
            # resizing around the origin and rejects discarding occupied cells.
            blob.update(source_grid_payload_hex=payload_bytes(old).hex(), cells=[],
                rows=self.half_extent, columns=self.half_extent,
                grid_width=self.half_extent, grid_height=self.half_extent,
                name=self.name_value, module_distance=self.spacing,
                orientation=self.yaw, grid_rotation=self.yaw,
                is_center_pivoted=int(self.shared_origin), ground_decal=self.ground_decal,
                debris_effect=self.debris_effect, destruction_effect=self.destruction_effect)
            new = grid_from_blob(blob)
            old_side, new_side = old.expanded_width, new.expanded_width
            for col in root.children_recursive:
                if CELL_ID in col or 'mesh_set_index' in col:
                    i = int(col.get(CELL_ID, col.get('mesh_set_index')))
                    x, z = i // old_side - old.grid_width, i % old_side - old.grid_height
                    col[CELL_ID] = col['mesh_set_index'] = (x + self.half_extent) * new_side + z + self.half_extent
            blob['source_grid_payload_hex'] = payload_bytes(new).hex()
            blob['cells'] = [{'index': i, 'rotation': m.rotation, 'has_mesh_set': m.has_mesh_set}
                             for i, m in enumerate(new.mesh_modules)]
            root[MESHGRID_BLOB_KEY] = json.dumps(blob)
            from sr_impex.blender.editors.bmg_state_editor import _set_model_rotation
            _set_model_rotation(root, self.yaw, rebuild_grid=True)
        except (ValueError, KeyError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_AddBuildingState(bpy.types.Operator):
    bl_idname = 'bmg.add_building_state'
    bl_label = 'State from Selected Meshes'
    bl_description = 'Copy selected render meshes into a new building cell/state'
    bl_options = {'REGISTER', 'UNDO'}
    cell_index: IntProperty(name='Cell index', min=0, default=4)
    state_id: IntProperty(name='State ID (0 intact, 2 damaged)', min=0, default=2)

    def invoke(self, context, event):
        try:
            grid = create_grid(find_building(context))
            self.cell_index = len(grid.mesh_modules) // 2
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        copies = []
        try:
            root = find_building(context)
            selected = [o for o in context.selected_objects if o.type == 'MESH']
            if not selected:
                raise ValueError('Select render meshes to copy into the new state')
            if (self.cell_index, self.state_id) in state_collections(root):
                raise ValueError('That cell/state already exists')
            if not 0 <= self.cell_index < len(create_grid(root).mesh_modules):
                raise ValueError('Cell index is outside the building grid')
            for obj in selected:
                dupe = obj.copy(); dupe.data = obj.data.copy()
                dupe.matrix_world = obj.matrix_world.copy()
                copies.append(dupe)
            add_state(root, self.cell_index, self.state_id, copies)
        except ValueError as exc:
            for obj in copies:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh.users == 0: bpy.data.meshes.remove(mesh)
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_StateEffects(bpy.types.Operator):
    bl_description = 'Edit the persistent and transition effect references for this building state'
    bl_idname = 'bmg.building_state_effects'
    bl_label = 'State Effects'
    bl_options = {'REGISTER', 'UNDO'}
    cell_index: IntProperty(name='Cell index', min=0)
    state_id: IntProperty(name='State ID', min=0)
    state_fx: StringProperty(name='Persistent state FX')
    transition_fx: StringProperty(name='Effect on entering this state')

    def invoke(self, context, event):
        try:
            root = find_building(context)
            state = state_collections(root)[(self.cell_index, self.state_id)]
            self.state_fx = state.get(STATE_FX, '')
            module = create_grid(root).mesh_modules[self.cell_index].state_based_mesh_set
            self.transition_fx = next((s.fx_file for s in module.transitions if s.target_state == self.state_id), '')
        except (ValueError, KeyError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=480)

    def execute(self, context):
        try:
            root = find_building(context)
            state = state_collections(root)[(self.cell_index, self.state_id)]
            state[STATE_FX] = self.state_fx
            module_col = next(c for c in root.children_recursive if c.get(CELL_ID) == self.cell_index and TRANSITIONS in c)
            transitions = json.loads(module_col[TRANSITIONS])
            transitions = [s for s in transitions if s['state_id'] != self.state_id]
            if self.transition_fx:
                transitions.append({'state_id': self.state_id, 'fx_file': self.transition_fx})
            module_col[TRANSITIONS] = json.dumps(transitions)
        except (ValueError, KeyError, StopIteration) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_ShowBuildingState(bpy.types.Operator):
    bl_description = 'Display this building state in the viewport'
    bl_idname = 'bmg.show_building_state'
    bl_label = 'Show State'
    bl_options = {'REGISTER', 'UNDO'}
    cell_index: IntProperty(min=0)
    state_id: IntProperty(min=0)

    def execute(self, context):
        try:
            root = find_building(context)
            from sr_impex.blender.editors.bmg_state_editor import stop_damage_preview
            stop_damage_preview(context,root)
            module = next(c for c in root.children_recursive
                if c.get(CELL_ID) == self.cell_index and child(c, 'States_Collection'))
            switch_meshset_state(module, f'S{self.state_id}')
        except (ValueError, StopIteration) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_RemoveBuildingState(bpy.types.Operator):
    bl_idname='bmg.remove_building_state'
    bl_label='Remove Building State'
    bl_description='Remove this state from the grid; its mesh objects are unlinked from this building'
    bl_options={'REGISTER','UNDO'}
    cell_index:IntProperty(min=0)
    state_id:IntProperty(min=0)
    def execute(self,context):
        try:
            root=find_building(context)
            state=state_collections(root)[(self.cell_index,self.state_id)]
            parent=next(c for c in root.children_recursive if state.name in c.children)
            grid=create_grid(root);module=grid.mesh_modules[self.cell_index]
            module.state_based_mesh_set.mesh_states=[s for s in module.state_based_mesh_set.mesh_states if s.state_id!=self.state_id]
            blob=json.loads(root[MESHGRID_BLOB_KEY]);blob['source_grid_payload_hex']=payload_bytes(grid).hex()
            for cell in blob.get('cells',[]):
                if int(cell['index'])==self.cell_index and self.state_id==0:cell['mesh_object_name']=''
            root[MESHGRID_BLOB_KEY]=json.dumps(blob)
            parent.children.unlink(state)
            remaining=state_collections(root)
            other=next((key[1] for key in sorted(remaining) if key[0]==self.cell_index),None)
            if other is not None:
                owner=next(c for c in root.children_recursive if c.get(CELL_ID)==self.cell_index and child(c,'States_Collection'))
                switch_meshset_state(owner,f'S{other}')
        except (ValueError,KeyError,StopIteration) as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


def _damage_model(context=None):
    return find_building(context or bpy.context)


def _damage_get(_self):
    from sr_impex.blender.building_damage_preview import DAMAGE
    try:return float(_damage_model().get(DAMAGE,0.))
    except (ValueError,ReferenceError):return 0.


def _damage_set(_self,value):
    from sr_impex.blender.building_damage_preview import DAMAGE,SESSIONS,key
    try:
        model=_damage_model();scene=bpy.context.scene
        if bpy.app.is_job_running('RENDER'):return
        model[DAMAGE]=max(0.,min(1.,value))
        preview=SESSIONS.get(key(scene,model))
        if preview:preview.apply(model[DAMAGE]);preview.report()
    except (ValueError,ReferenceError):return


class BMG_OT_DamagePreview(bpy.types.Operator):
    bl_idname='bmg.damage_preview'
    bl_label='Build Damage Preview'
    bl_description='Cache building state effects and destruction debris; preview only, not exported'

    def execute(self,context):
        from sr_impex.blender.building_damage_preview import build
        from sr_impex.blender.editors.effect_set_editor import _library
        try:
            result=build(context,_damage_model(context),_library(context))
            self.report({'INFO'},f'Damage preview ready for {len(result.cells)} cells. Space plays debris and FX.')
        except (ValueError,OSError) as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_ReplayDamage(bpy.types.Operator):
    bl_idname='bmg.replay_damage'
    bl_label='Replay Transition'
    bl_description='Restart cached destruction and effects at the current frame; Space plays the timeline'

    def execute(self,context):
        from sr_impex.blender.building_damage_preview import DAMAGE,SESSIONS,key
        try:
            model=_damage_model(context);preview=SESSIONS.get(key(context.scene,model))
            if preview is None:raise ValueError('Build the damage preview first')
            preview.apply(float(model.get(DAMAGE,0.)),restart=True)
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class BMG_OT_ClearDamage(bpy.types.Operator):
    bl_idname='bmg.clear_damage'
    bl_label='Clear Damage Preview'
    bl_description='Remove generated FX and restore building visibility and original materials'

    def execute(self,context):
        from sr_impex.blender.effect_preview import clear
        try:clear(context.scene,_damage_model(context))
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class BMG_PT_BuildingExport(bpy.types.Panel):
    bl_label = 'Building Editor'
    bl_idname = 'BMG_PT_building_export'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BMG Editor'
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        layout.operator('bmg.new_building', icon='OUTLINER_COLLECTION')
        try:
            root = find_building(context)
            grid = create_grid(root)
            states = state_collections(root)
        except (ValueError, KeyError) as exc:
            layout.label(text=str(exc), icon='INFO')
            return
        layout.label(text=root.name, icon='HOME')
        layout.label(text=f'{grid.expanded_width} × {grid.expanded_height} cells · {len(states)} editable states')
        from sr_impex.blender.building_damage_preview import SESSIONS,key,TAG
        preview=SESSIONS.get(key(context.scene,root))
        box=layout.box();box.label(text='Damage Preview',icon='MOD_EXPLODE')
        box.operator('bmg.damage_preview',text='Update Damage Preview' if preview else 'Build Damage Preview',icon='FILE_REFRESH')
        if preview:
            box.prop(context.window_manager,'bmg_damage',text='Damage',slider=True)
            row=box.row(align=True);row.operator('bmg.replay_damage',icon='FILE_REFRESH')
            row.operator('bmg.clear_damage',text='',icon='X')
            box.label(text='Preview only. Space plays debris and FX.',icon='INFO')
        elif any(TAG+'_visibility' in col for col in root.children_recursive):
            box.label(text='Rebuild the saved preview to use Damage.',icon='INFO')
            box.operator('bmg.clear_damage')
        layout.operator('bmg.building_settings', icon='PREFERENCES')
        layout.operator('bmg.add_building_state', icon='ADD')
        layout.operator('drs.setup_material', text='Create / Upgrade Selected Material', icon='MATERIAL')
        for (cell, state_id), state in sorted(states.items()):
            row = layout.row(align=True)
            row.label(text=f'Cell {cell} / S{state_id}')
            op = row.operator('bmg.show_building_state', text='Show')
            op.cell_index, op.state_id = cell, state_id
            op = row.operator('bmg.building_state_effects', text='Effects')
            op.cell_index, op.state_id = cell, state_id
            op = row.operator('bmg.remove_building_state', text='', icon='X')
            op.cell_index, op.state_id = cell, state_id
        layout.separator()
        layout.label(text='Exports all states, including hidden stages.', icon='INFO')
        layout.operator('export_scene.bmg', text='Export Building Package', icon='EXPORT')


classes = (BMG_OT_NewBuilding, BMG_OT_BuildingSettings, BMG_OT_AddBuildingState,
           BMG_OT_StateEffects, BMG_OT_ShowBuildingState, BMG_OT_RemoveBuildingState,
           BMG_OT_DamagePreview,BMG_OT_ReplayDamage,BMG_OT_ClearDamage,BMG_PT_BuildingExport)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.bmg_damage=FloatProperty(name='Damage',min=0.,max=1.,subtype='FACTOR',
        description='Preview cell damage, destruction effects and scratch without editing export settings',
        get=_damage_get,set=_damage_set)


def unregister():
    from sr_impex.blender import building_damage_preview as damage
    from sr_impex.blender.effect_preview import clear
    for preview in list(damage.SESSIONS.values()):clear(preview.scene,preview.model)
    del bpy.types.WindowManager.bmg_damage
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
