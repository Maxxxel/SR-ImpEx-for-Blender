"""Reversible BMG damage preview: states, scratch and cached destruction FX.

Build does resource IO once. Damage updates only select cached state sessions
and set preview material sockets. Exported state tables/scalars are untouched.
"""
from pathlib import Path
import json
import math
import bpy
from mathutils import Matrix,Vector
from sr_impex.utilities.building_damage import damage_states,scratch_factor

SESSIONS={}
TAG='_sr_building_damage'
DAMAGE='_sr_building_damage_value'
BASE_CRUSH='bf1/gfx/effects/effect_code_building_Crush.fxb'
BASE_HIT='bf1/gfx/buildings/frost/generic_debris/Effect_frost_gen_destruction.xml'
BASE_DAMAGE='bf1/gfx/effects/effect_code_building_Damage.fxb'


def key(scene,model):return scene.as_pointer(),model.as_pointer()


class Preview:
    def __init__(self,context,model,library):
        from sr_impex.utilities.building_export import create_grid,state_collections,STATE_ID
        self.scene=context.scene;self.model=model;self.grid=create_grid(model)
        self.states=state_collections(model);self.library=library
        self.cells=[i for i,m in enumerate(self.grid.mesh_modules) if m.has_mesh_set]
        if not self.cells:raise ValueError('This building has no occupied cells')
        self.fx={};self.active={};self.materials={};self.slots=[];self.warnings=set()
        self.visibility=[];self.markers=[];self.groups={}
        self.start=float(self.scene.frame_current)+self.scene.frame_subframe
        self.fps=self.scene.render.fps/self.scene.render.fps_base
        self.source=Path(model.get('_bmg_source_path','') or 'new-building.bmg')
        # Persist restoration metadata too: saved previews must be clearable
        # after reopening Blender, when this Python object no longer exists.
        from sr_impex.utilities.building_export import child,CELL_ID
        for col in model.children_recursive:
            if col.get(CELL_ID) in self.cells and child(col,'States_Collection'):
                self.groups[int(col[CELL_ID])]=col
        affected={c for group in self.groups.values() for c in (group,*group.children_recursive)}
        for col in affected:
            self.visibility.append((col,col.hide_viewport,col.hide_render))
            col[TAG+'_visibility']=[col.hide_viewport,col.hide_render]
        for obj in model.all_objects:
            if obj.type=='EMPTY' and 'active_state' in obj:
                self.markers.append((obj,obj['active_state']))
                obj[TAG+'_active']=obj['active_state']
        for state in self.states.values():
            for obj in state.all_objects:
                if obj.type!='MESH' or 'Collision' in obj.name:continue
                saved=[]
                for index,slot in enumerate(obj.material_slots):
                    original=slot.material
                    if original is None or not original.use_nodes:continue
                    group=original.node_tree.nodes.get('DRS_Engine_Group')
                    if group is None or 'Scratch' not in group.inputs:continue
                    if original not in self.materials:
                        copy=original.copy();copy.name=original.name+' Damage Preview'
                        copy.use_fake_user=False
                        copy[TAG]=True
                        # Preserve the original Material ID across save/reload.
                        copy[TAG+'_original']=original.name
                        copy[TAG+'_original_id']=original
                        if TAG+'_fake_user' not in original:
                            original[TAG+'_fake_user']=original.use_fake_user
                        original.use_fake_user=True
                        self.materials[original]=copy
                    copy=self.materials[original]
                    saved.append({'index':index,'link':slot.link,'original':original.name,'copy':copy.name})
                    # Isolate the override even if another model shares Mesh data.
                    slot.link='OBJECT';slot.material=copy
                if saved:obj[TAG+'_slots']=json.dumps(saved)

    def warn(self,message):self.warnings.add(str(message))

    def add_session(self,context,label,resources=(),persistent=False):
        from sr_impex.blender import effect_preview as fx
        from sr_impex.blender.effect_surfaces import snapshot
        from sr_impex.blender.effect_physics import bake
        from sr_impex.blender.effect_glow import enable
        session=fx.Session(self.scene,self.model,self.library,self.start,self.start+20*self.fps,audio=False)
        session.base_matrix=session.base_matrix@Matrix.Rotation(math.radians(self.grid.grid_rotation),4,'Y')
        session.report_name='Building Damage Preview — '+self.model.name+' / '+str(label)
        session.collection[TAG]=True
        self.fx[label]=session
        fx.SESSIONS[(*key(self.scene,self.model),str(label))]=session
        if persistent:session.add_persistent()
        for name,placement,*transition in resources:
            if not name:continue
            anchor=fx._new_object(session.collection,'Building FX anchor')
            anchor.matrix_world=session.base_matrix@placement
            try:
                first=len(session.items)
                session.add_effect(name,0.,parent=anchor,source=self.source)
                if transition and transition[0]:
                    # CVisDamageCell transition consumer 10080FA0 explicitly
                    # disables both within-group and out-of-group collisions.
                    for item in session.items[first:]:
                        if item.kind=='Physic':item.physics_no_piece_collision=True
            except (OSError,ValueError) as exc:session.warn(f'Building effect {name}: {exc}')
        session.surface=snapshot(context,session.warn,exclude=self.model.all_objects)
        session.terrain_surface=session.surface
        if any(item.kind=='StaticDecal' for item in session.items):
            session.static_surface=snapshot(context,session.warn)
        # Keep the cache bounded while covering the longest loaded resource.
        duration=max([5.]+[event[2] for event in session.events])
        session.frame_end=self.start+min(100.,duration)*self.fps
        if duration>100:session.warn('Building destruction cache capped at 100 seconds')
        session.bake_motion();bake(session);enable(session)
        session.enabled=False;session.update();session.report()
        return session

    def build(self,context):
        self.add_session(context,'ambient',persistent=True)
        for cell in self.cells:
            meshset=self.grid.mesh_modules[cell].state_based_mesh_set
            if meshset is None:continue
            place=self.grid.cell_placement(cell)
            transform=Matrix.Translation(Vector(place['translation']))@Matrix.Rotation(math.radians(place['rotation_degrees']),4,'Y')
            hit=transform@Matrix.Translation(Vector(place['effect_offset']))
            for state in (0,2,3):
                record=next((s for s in meshset.mesh_states if s.state_id==state),None)
                transition=next((t.fx_file for t in meshset.transitions if t.target_state==state),'')
                resources=[(record.fx_file if record else '',transform)]
                # Initialization selects S0; restoration should not invent a
                # destruction transition on entering the intact preview.
                if state!=0:resources.append((transition,transform,True))
                if state==2:
                    resources.extend(((self.grid.debris_effect or BASE_HIT,hit),(BASE_DAMAGE,hit)))
                self.add_session(context,(cell,state),resources)
        self.add_session(context,'crush',[(self.grid.destruction_effect or BASE_CRUSH,Matrix.Identity(4))])
        from sr_impex.blender.effect_render import configure
        from sr_impex.blender import effect_preview
        configure(self.scene,list(effect_preview.SESSIONS.values()))
        self.warn('Damage visits cells in ascending index order. In game, the hit position selects the starting cell.')
        self.warn('Debris uses proxy collision/inertia; engine-generated hit/crush impulses and FX budgets differ. Building preview audio is disabled.')
        for session in self.fx.values():self.warnings.update(session.warnings)
        self.apply(float(self.model.get(DAMAGE,0.)),restart=True)
        self.report()

    def apply(self,value,restart=False):
        from sr_impex.blender.editors.bmg_state_editor import switch_meshset_state
        value=max(0.,min(1.,float(value)));self.model[DAMAGE]=value
        states=damage_states(self.cells,value)
        now=(self.scene.frame_current+self.scene.frame_subframe-self.start)/self.fps
        active={('crush' if value>=1. else 'ambient'),*states.items()}
        for label,session in self.fx.items():
            enabled=label in active
            if enabled and (restart or not session.enabled):session.time_offset=now
            session.enabled=enabled
        for cell,state in states.items():
            if restart or self.active.get(cell)!=state:
                group=self.groups.get(cell)
                if group:switch_meshset_state(group,f'S{state}')
        self.active=states
        for copy in self.materials.values():
            node=copy.node_tree.nodes.get('DRS_Engine_Group')
            if node:node.inputs['Scratch'].default_value=scratch_factor(value)
        for session in self.fx.values():
            session.update_animation();session.update()

    def report(self):
        report={'damage':float(self.model.get(DAMAGE,0.)),'states':self.active,
                'scratch_factor':scratch_factor(self.model.get(DAMAGE,0.)),
                'warnings':sorted(self.warnings),'preview_only':True}
        text=bpy.data.texts.get('Building Damage Preview Report') or bpy.data.texts.new('Building Damage Preview Report')
        text.clear();text.write(json.dumps(report,indent=2))
        return report


def build(context,model,library):
    if context.mode!='OBJECT':raise ValueError('Switch to Object Mode before building the damage preview')
    if bpy.app.is_job_running('RENDER'):raise ValueError('Wait for the current render to finish')
    from sr_impex.blender import effect_preview as fx
    fx.clear(context.scene,model)
    old_selection=list(context.selected_objects);active=context.view_layer.objects.active
    preview=None
    try:
        preview=Preview(context,model,library)
        SESSIONS[key(context.scene,model)]=preview
        preview.build(context)
        return preview
    except Exception:
        fx.clear(context.scene,model)
        raise
    finally:
        for obj in context.selected_objects:obj.select_set(False)
        for obj in old_selection:
            if obj.name in context.view_layer.objects:obj.select_set(True)
        context.view_layer.objects.active=active


def restore(scene,model=None):
    """Restore live and saved previews; retain intentional material replacement."""
    models=[model] if model else [c for c in scene.collection.children_recursive if any(TAG+'_visibility' in child for child in c.children)]
    for index,preview in list(SESSIONS.items()):
        if preview.scene==scene and (model is None or preview.model==model):
            if preview.model not in models:models.append(preview.model)
            SESSIONS.pop(index)
    for root in models:
        for obj in root.all_objects:
            if TAG+'_active' in obj:
                obj['active_state']=obj[TAG+'_active'];del obj[TAG+'_active']
            if obj.type!='MESH':continue
            if TAG+'_slots' in obj:
                for row in json.loads(obj[TAG+'_slots']):
                    if row['index']>=len(obj.material_slots):continue
                    slot=obj.material_slots[row['index']];copy=slot.material
                    original=(copy.get(TAG+'_original_id') or bpy.data.materials.get(row['original'])) if copy and copy.get(TAG) else None
                    if original and copy and copy.name==row['copy'] and copy.get(TAG):
                        slot.material=original;slot.link=row['link']
                del obj[TAG+'_slots']
        for col in root.children_recursive:
            if TAG+'_visibility' in col:
                col.hide_viewport,col.hide_render=col[TAG+'_visibility'];del col[TAG+'_visibility']
    # Include orphan copies if an artist changed the material slot themselves.
    for copy in list(bpy.data.materials):
        if copy.get(TAG) and copy.users==0:
            bpy.data.materials.remove(copy)
    referenced={copy[TAG+'_original_id'].name if copy.get(TAG+'_original_id') else copy.get(TAG+'_original')
                for copy in bpy.data.materials if copy.get(TAG)}
    for original in bpy.data.materials:
        if TAG+'_fake_user' in original and original.name not in referenced:
            original.use_fake_user=bool(original[TAG+'_fake_user']);del original[TAG+'_fake_user']
