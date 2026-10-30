"""Scene-timeline previews of existing FX resources; never an FXB authoring tool.

All IO and object construction happen in build(). The frame handler evaluates
cached tracks/geometry only. Preview collections are siblings of model exports.
"""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import math
import random
import uuid
import wave

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector, Quaternion, Euler

from sr_impex.definitions.fxb_definitions import _element_type_map
from sr_impex.utilities.effect_inspection import read_effect
from sr_impex.utilities.effect_tracks import TrackSet, choose_variant, fade_value, node_active
from sr_impex.utilities.effect_audio import load_audio,pitch_wave
from sr_impex.utilities.effect_particles import SfpRamps

OWNER='_sr_fx_preview'
SESSIONS={}


class NoPreviewResources(ValueError):
    def __init__(self,message,expected=False):
        super().__init__(message);self.expected=expected


def _rotation(tracks,time,duration,kind):
    from bisect import bisect_right
    from sr_impex.utilities.effect_tracks import address_time,components
    # 10DF0790 is shared by these quaternion consumers. SFP/trail nodes
    # instead receive vector rotation data and must keep vector interpolation.
    if kind not in ('AnimatedMesh','AnimatedMeshMaterial','Emitter','Light','Effect',
                    'EffectMesh','MeshMaterial','Satellite','WaterDecal'):
        return Euler(tracks.value(1,time,(0.,0.,0.),duration),'XYZ').to_quaternion()
    result=Quaternion()
    for track in tracks.groups.get(1,[]):
        keys=track.entries
        if not keys:continue
        at=address_time(track,time,duration) if len(keys)>1 else keys[0].frame
        index=bisect_right([key.frame for key in keys],at)-1
        low=max(0,min(len(keys)-1,index));high=min(len(keys)-1,low+1)
        a,b=keys[low],keys[high]
        qa=Euler(components(a.data),'XYZ').to_quaternion()
        qb=Euler(components(b.data),'XYZ').to_quaternion()
        weight=max(0.,min(1.,(at-a.frame)/max(b.frame-a.frame,1e-8)))
        # CFxTrackQuaternion::UpdateData (10E23F10) interpolates stored
        # quaternions, rather than interpolating the serialized Euler angles.
        result=result@qa.slerp(qb,weight)
    # 10DF0790 writes the conventional quaternion matrix as three consecutive
    # basis vectors. 1000DCD0 then combines those vectors as COLUMNS. Blender
    # needs the transpose of the stored rows: inverse/conjugate for rotations.
    # Converting Euler to a matching quaternion alone misses this final step.
    return result.conjugated()

# Explicit limits, not invented equivalence with the game's renderer.
CAPABILITIES={
 'Light':'Animated point light; Blender energy calibration is approximate',
 'Billboard':'Textured camera-facing quad, alpha/color/scale and atlas; blend/shader approximation',
 'Effect':'Nested resources and graph transforms; advanced source/target links incomplete',
 'EffectMesh':'DRS mesh/material preview and transform tracks',
 'MeshMaterial':'Whole-resource MAT override and supported DRS shader parameter curves',
 'AnimatedMesh':'Skinned DRS geometry driven by SKA and the FX normalized Anim curve',
 'AnimatedMeshMaterial':'SKA playback and supported DRS shader parameter curves',
 'Sound':'Independent overlapping audio, sound-set loops/pitch variants and volume curves; spatial falloff/pitch automation pending',
 'Emitter':'Native static particle field, local force/direction/phase and color/size curves; scene trails/fog/shader parity incomplete',
 'Satellite':'Approximate particle sprites; satellite-specific motion pending',
 'SfpSystem':'128-sample render ramps: color, emissive color, alpha, size, rotation and atlas; shader approximation',
 'SfpEmitter':'Deterministic particle sprites with render ramps; emission/forces approximation',
 'SfpForceField':'Cached point attraction, inner/outer sphere, distortion, uniform drift and vortex; approximate integration/RNG',
 'StaticDecal':'Projected onto cached scene surfaces; engine terrain/shader approximation',
 'Decal':'Dynamic projection onto cached scene surfaces; engine terrain/shader approximation',
 'WaterDecal':'3D texture animation and alpha-squared color on a flat water level; wave/fog/shadow approximation',
 'Trail':'Cached motion ribbon with width, lifetime and fade; spline/ramp/distortion approximation',
 'PhysicGroup':'Terrain offset and within-group debris collision control',
 'Physic':'Cached gravity, force, mass, torque and collision preview; proxy inertia/contact solver',
 'Force':'Not simulated; retained as a graph node',
 'ForcePoint':'Cached CPhy point attraction/repulsion with animated range and power',
 'CameraShake':'Not applied; the artist camera remains under artist control',
}

USED_TRACKS={
 'Light':{0,1,4,9,40},'Billboard':{0,1,2,4,5,8,24,52,53,59},
 'SfpSystem':{0,1,5,6,8,51,59,97,98,*range(113,125)},
 'SfpEmitter':{0,1,24,41,42,99,100,101,102,103,104,105,106,108,109,111,112,
               129,130,131,132,133,134,135,137,145,146,147,148},
 'Emitter':{0,1,2,4,5,10,11,12,13,16,17,18,21,22,24,25,26,27,28,29,30,31,32,33,34,35,36,39,51,63},'Satellite':{0,1,2,4,5,10,11,12,13,16,17,25,36,51},
 'Sound':{77},'EffectMesh':{0,1,2,5},'MeshMaterial':{0,1,2,5},'Physic':{5,72,76,189},
 'PhysicGroup':{75,167},'ForcePoint':{73,74},
 'AnimatedMesh':{0,1,2,3,5},'AnimatedMeshMaterial':{0,1,2,3,5},
 'StaticDecal':{0,1,89,90},'Decal':{0,1,4,5,6,8},'WaterDecal':{0,1,4,5,6,7},
 'Trail':{0,1,4,5,8,59,169,170,171,172,173,174},
 'SfpForceField':{0,1,110,125,126,127,128,153,155,156,157,158,159},
}


def _new_object(collection,name,data=None,parent=None):
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    obj[OWNER]=True
    obj.hide_select=True
    obj.parent=parent
    if data is None:obj.empty_display_size=.001
    return obj


def _quad(collection,name,parent):
    mesh=bpy.data.meshes.new(name)
    mesh[OWNER]=True
    mesh.from_pydata([(-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0)],[],[(0,1,2,3)])
    uv=mesh.uv_layers.new()
    for item,co in zip(uv.data,((0,0),(1,0),(1,1),(0,1))):item.uv=co
    return _new_object(collection,name,mesh,parent)


@dataclass
class Visual:
    element: object
    obj: object
    tracks: object
    start: float
    duration: float
    geometry: object=None
    shader: object=None
    alpha: object=None
    texture: object=None
    kind: str=''
    particle_data: object=None
    legacy_samples: object=None
    fades: list=field(default_factory=list)
    bone_target: object=None
    animation: object=None
    material_bindings: list=field(default_factory=list)
    system: object=None
    force_cache: object=None
    blend: object=None
    birth_state: object=None
    audio_strips: list=field(default_factory=list)
    world_matrix: object=None
    slot_target: object=None
    graph_parent: object=None
    physics_cache: object=None
    decal_grid: object=None
    water_volume: object=None
    glow_uniform: object=None
    physics_no_piece_collision: bool=False
    physics_inverse_inertia: object=None
    active_window: tuple=(-1.,-1.,-1.)


class Session:
    def __init__(self,scene,model,library,frame_start,frame_end,seed=0,audio=True):
        self.scene=scene;self.model=model;self.library=library
        obj=bpy.context.active_object;layer=bpy.context.view_layer.active_layer_collection
        self.selection_context=(obj.as_pointer() if obj else 0,layer.collection.as_pointer())
        self.frame_start=frame_start;self.frame_end=frame_end
        self.fps=scene.render.fps/scene.render.fps_base
        if '_sr_fx_previous_render_lock' not in scene:
            scene['_sr_fx_previous_render_lock']=scene.render.use_lock_interface
        scene.render.use_lock_interface=True
        self.seed=seed;self.audio=audio
        self.cache=Path(bpy.utils.user_resource('DATAFILES',path='sr_impex/effect_preview',create=True))
        self.collection=bpy.data.collections.new('Effect Preview â€” '+model.name)
        self.collection[OWNER]=True
        self.collection['_sr_fx_model']=model.name
        scene.collection.children.link(self.collection)
        self.items=[];self.events=[];self.strips=[];self.images={};self.masters={}
        self.persistent={}
        self.baking=False;self.motion_times=None;self.motion={}
        self.sprite_budget=8192
        self.surface=None
        self.terrain_surface=None
        self.static_surface=None
        self.volumes={};self.volume_budget=16_777_216
        self.has_glow=False
        self.requested_resources=[]
        self.locator_blob=None
        self.enabled=True;self.time_offset=0.;self._last_enabled=None
        self.warnings=set();self.counts={};self.created=0
        self.anchor=next((o for o in model.all_objects if o.name.startswith('GameOrientation')),None)
        self.base_matrix=self.anchor.matrix_world.copy() if self.anchor else Matrix.Identity(4)
        self.report_name='Effect Preview Report â€” '+model.name

    def view_matrix(self):
        if not bpy.app.is_job_running('RENDER') and bpy.context.screen:
            for area in bpy.context.screen.areas:
                if area.type=='VIEW_3D':
                    region=area.spaces.active.region_3d
                    if region and region.view_perspective!='CAMERA':return region.view_matrix.inverted()
        return self.scene.camera.matrix_world if self.scene.camera else Matrix.Identity(4)

    def warn(self,text):self.warnings.add(str(text))

    def source_slot(self,name):
        # SetSrcSlot (10DFA970) explicitly recognizes these attachment names.
        class_id={'Health Bar':0,'Projectile Spawn':29}.get(name)
        if class_id is None:return None
        records=json.loads(self.model.get('CDrwLocatorListJSON','{}')).get('locators',[])
        records=[record for record in records if record.get('class_id')==class_id]
        if not records:
            self.warn(f'FX source slot {name}: no locator; preview uses model origin')
            return None
        if len(records)>1:self.warn(f'FX source slot {name}: preview uses the first matching locator')
        record=records[0]
        target=next((obj for obj in self.model.all_objects if record.get('uid') and
                     obj.get('_cdrw_uid')==record['uid']),None)
        if target:return target,None,Matrix.Identity(4)
        values=record.get('rot3x3',[1,0,0,0,1,0,0,0,1])
        local=Matrix((values[:3],values[3:6],values[6:9])).to_4x4()
        local.translation=Vector(record.get('pos',(0.,0.,0.)))
        rig=next((obj for obj in self.model.all_objects if obj.type=='ARMATURE'),None)
        if rig and record.get('bone_id',-1)>=0:
            from sr_impex.blender.editors.locator_editor import _bone_name_from_index
            bone=_bone_name_from_index(rig,int(record['bone_id']))
            if bone:return rig,bone,local
        return (self.anchor,None,local) if self.anchor else (None,None,self.base_matrix@local)

    def resolve(self,name,source,folder=''):
        if folder=='textures' and name and not Path(name).suffix:
            try:return self.resolve(name+'.dds',source,folder)
            except FileNotFoundError:pass
        try:return self.library.resolve(name,source)
        except (FileNotFoundError,ValueError):
            # The shipped effect library has meshes/ and textures/ namespaces.
            # Prefer that explicit context over choosing an arbitrary duplicate.
            if folder and '/' not in name.replace('\\','/'):
                return self.library.resolve(folder+'/'+name,source)
            raise

    def texture_image(self,name,source):
        if not name:return None
        asset=self.resolve(name,source,'textures')
        key=(str(asset.source),asset.name)
        if key not in self.images:
            from sr_impex.utilities.legacy_particles import alpha_only_dds
            raw=asset.read();alpha=alpha_only_dds(raw)
            if alpha is not None:
                import numpy as np
                width,height,mask=alpha
                label='FX A8 '+hashlib.sha256(raw).hexdigest()
                image=bpy.data.images.get(label)
                if image is None:
                    image=bpy.data.images.new(label,width,height,alpha=True)
                    image[OWNER]=True;image.colorspace_settings.name='Non-Color'
                    rgba=np.ones((height,width,4),dtype='float32')
                    rgba[:,:,3]=np.frombuffer(mask,dtype='uint8').reshape(height,width)[::-1]/255.
                    image.pixels.foreach_set(rgba.ravel());image.pack()
                self.images[key]=image
            else:self.images[key]=bpy.data.images.load(str(asset.materialize(self.cache)),check_existing=True)
        return self.images[key]

    def material(self,obj,name,source):
        material=bpy.data.materials.new('FX Preview '+obj.name)
        material[OWNER]=True;material.use_nodes=True
        nodes=material.node_tree.nodes;nodes.clear();links=material.node_tree.links
        out=nodes.new('ShaderNodeOutputMaterial');mix=nodes.new('ShaderNodeMixShader')
        transparent=nodes.new('ShaderNodeBsdfTransparent');emission=nodes.new('ShaderNodeEmission')
        color=nodes.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1
        color.inputs[1].default_value=(1,1,1,1);color.inputs[2].default_value=(1,1,1,1)
        alpha=nodes.new('ShaderNodeMath');alpha.operation='MULTIPLY'
        alpha.inputs[0].default_value=1;alpha.inputs[1].default_value=1
        links.new(color.outputs[0],emission.inputs['Color'])
        links.new(alpha.outputs[0],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1])
        links.new(emission.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],out.inputs['Surface'])
        try:
            image=self.texture_image(name,source)
            if image:
                tex=nodes.new('ShaderNodeTexImage');tex.image=image
                links.new(tex.outputs['Color'],color.inputs[1]);links.new(tex.outputs['Alpha'],alpha.inputs[0])
        except (OSError,ValueError) as exc:self.warn(exc)
        if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
        obj.data.materials.append(material)
        return color,alpha

    def master(self,asset):
        key=(str(asset.source),asset.name)
        if key not in self.masters:
            if Path(asset.name).suffix.lower()=='.xml':
                from sr_impex.utilities.effect_xml import read_building_effect
                self.masters[key]=read_building_effect(asset.read(),self.warn)
            else:self.masters[key]=read_effect(asset.read())
        return self.masters[key]

    def elapsed(self):
        return (self.scene.frame_current+self.scene.frame_subframe-self.frame_start)/self.fps-self.time_offset

    def sound(self,name,start,source=None,volume=1.,seed=0,pitch_shift=None):
        if name:self.requested_resources.append(('audio',name))
        if not self.audio:return
        try:
            cue=load_audio(self.library,name,self.cache,source,seed)
            if cue is None:return
            path=cue.path
            rng=random.Random(seed)
            pitch=rng.uniform(cue.pitch_min,cue.pitch_max)
            if pitch_shift is not None:
                # CPssAudioEvent::generatePlayInfo: 1 + uniform(min,max).
                # getPitchShift multiplies the event and per-file factors.
                pitch*=1.+rng.uniform(*pitch_shift)
            if not math.isfinite(pitch) or pitch<=0:
                raise ValueError('Pitch shift produces a nonpositive playback rate; choose shifts above -1')
            if abs(pitch-1)>1e-6:
                try:path=pitch_wave(path,pitch,self.cache)
                except (OSError,ValueError,wave.Error) as exc:self.warn(exc)
            editor=self.scene.sequence_editor_create()
            strips=editor.strips
            frame=int(round(self.frame_start+start*self.fps))
            # Use a free channel; existing user strips and other cues survive.
            channel=next((i for i in range(1,129) if not any(s.channel==i for s in strips)),None)
            if channel is None:raise ValueError('Audio preview reached Blender\'s 128 timeline-channel limit')
            prior_sounds=set(bpy.data.sounds)
            strip=strips.new_sound('FX Preview '+name,str(path),channel,frame)
            strip[OWNER]=True
            if strip.sound not in prior_sounds:strip.sound[OWNER]=True
            strip['_sr_fx_model']=self.model.name
            strip.volume=max(0.,volume*cue.volume)
            strip['_sr_fx_base_volume']=strip.volume
            self.strips.append(strip)
            created=[strip]
            if cue.looped:
                while strip.frame_final_end<self.frame_end and len(created)<256:
                    next_frame=strip.frame_final_end
                    strip=strips.new_sound('FX Preview '+name,str(path),channel,next_frame)
                    strip[OWNER]=True;strip['_sr_fx_model']=self.model.name
                    if strip.sound not in prior_sounds:strip.sound[OWNER]=True
                    strip.volume=max(0.,volume*cue.volume);strip['_sr_fx_base_volume']=strip.volume
                    self.strips.append(strip);created.append(strip)
                if strip.frame_final_end>self.frame_end:strip.frame_final_end=math.ceil(self.frame_end)
                if len(created)>=256:self.warn('Looped audio preview capped at 256 repeats per cue')
            return created
        except Exception as exc:self.warn(f'Audio {name}: {exc}')

    def add_effect(self,name,start,parent=None,offset=(0,0,0),linked=False,source=None,stack=()):
        self.requested_resources.append(('effect',name))
        asset=self.library.resolve(name,source)
        key=asset.name.casefold()
        if key in stack or len(stack)>=16:raise ValueError(f'Nested FX cycle/depth limit: {name}')
        master=self.master(asset)
        root=_new_object(self.collection,'FX '+name,parent=parent)
        if parent is None:root.matrix_world=self.base_matrix@Matrix.Translation(Vector(offset))
        else:root.location=offset
        root['_sr_fx_offset']=list(offset)
        duration=max(float(master.play_length),float(master.length))
        if duration<=0:
            # Open-ended ambient resources need a bounded artist preview,
            # rather than being discarded after a single scene frame.
            duration=max(1/self.fps,(self.frame_end-self.frame_start)/self.fps-start)
        self.events.append((root,start,duration,linked and parent is None))
        for element in master.special_effect.children:
            self.add_element(element,root,asset,start,duration,stack+(key,))
        return root

    def add_persistent(self):
        blob=self.locator_blob if self.locator_blob is not None else json.loads(self.model.get('CDrwLocatorListJSON','{}'))
        for locator in blob.get('locators',[]):
            if locator.get('class_id') not in (6,8) or not locator.get('file','').lower().endswith('.fxb'):continue
            target=next((o for o in self.model.all_objects if locator.get('uid') and o.get('_cdrw_uid')==locator['uid']),None)
            if target is None:
                # BMG import can preserve locator records without creating their
                # viewport helpers. Build a preview-owned anchor from the record.
                target=_new_object(self.collection,'FX locator anchor')
                values=locator.get('rot3x3',[1,0,0,0,1,0,0,0,1])
                matrix=Matrix((values[0:3],values[3:6],values[6:9])).to_4x4()
                matrix.translation=Vector(locator.get('pos',(0,0,0)))
                bone_id=int(locator.get('bone_id',-1))
                rig=next((o for o in self.model.all_objects if o.type=='ARMATURE'),None)
                if rig and bone_id>=0:
                    from sr_impex.blender.editors.locator_editor import _bone_name_from_index
                    bone=_bone_name_from_index(rig,bone_id)
                    if bone:
                        target.parent=rig;target.parent_type='BONE';target.parent_bone=bone
                        target.matrix_basis=matrix
                    else:target.matrix_world=self.base_matrix@matrix
                else:target.matrix_world=self.base_matrix@matrix
            first=len(self.items)
            try:
                root=self.add_effect(locator['file'],0.)
                constraint=root.constraints.new('COPY_TRANSFORMS');constraint.target=target
                fades=[]
                self.persistent.setdefault(Path(locator['file']).name.casefold(),[]).append(fades)
                for item in self.items[first:]:item.fades=fades
            except (ValueError,OSError) as exc:self.warn(exc)

    def add_element(self,element,parent,asset,start,duration,stack,system=None):
        self.created+=1
        if self.created>2048:raise ValueError('Effect preview exceeds the 2048-node safety budget')
        kind=_element_type_map[element.element_type_header].__name__
        self.counts[kind]=self.counts.get(kind,0)+1
        obj=_new_object(self.collection,element.name,parent=parent)
        obj['fx_component']=kind;obj['fx_status']=CAPABILITIES[kind]
        tracks=TrackSet(element,self.warn)
        visual=Visual(element,obj,tracks,start,duration,kind=kind)
        statics={s.track_type:s.data.value for s in element.static_tracks}
        visual.active_window=tuple(float(statics.get(key,-1.)) for key in (8,9,18))
        visual.graph_parent=parent
        self.items.append(visual)
        payload=getattr(element,kind.lower())
        link=element.node_link
        if link.parent=='Source' and link.slot not in ('','None'):
            if link.slot in ('Origin','Health Bar','Projectile Spawn'):
                visual.slot_target=self.source_slot(link.slot)
                if visual.slot_target:obj.parent=None
            else:
                from sr_impex.utilities.skeleton_metadata import SOURCE_NAME
                for rig in (o for o in self.model.all_objects if o.type=='ARMATURE'):
                    bone=rig.pose.bones.get(link.slot) or next((b for b in rig.pose.bones
                        if b.bone.get(SOURCE_NAME)==link.slot),None)
                    if bone:
                        visual.bone_target=(rig,bone.name);obj.parent=None;break
                if not visual.bone_target:self.warn(f'FX source bone not found: {link.slot}')
        if link.destination_slot not in ('','None') or link.floor or link.aim or link.span or link.locator or link.world:
            self.warn('Some FX source/target, floor, aim, span or locator links are not reproduced')
        if kind=='Light':
            light=bpy.data.lights.new('FX '+element.name,'POINT');light[OWNER]=True
            visual.geometry=_new_object(self.collection,'Light '+element.name,light,obj)
        elif kind in ('Billboard','StaticDecal','Decal','WaterDecal'):
            visual.geometry=_quad(self.collection,kind+' '+element.name,obj)
            if kind!='Billboard':visual.geometry.rotation_euler[0]=-math.pi/2
            texture=(getattr(payload,'texture_one',None) or getattr(payload,'color_texture',None)
                     or getattr(payload,'texture',None) or getattr(payload,'decal_file',None))
            visual.shader,visual.alpha=self.material(visual.geometry,None if kind=='WaterDecal' else texture,asset)
            if kind in ('StaticDecal','Decal','WaterDecal'):
                from sr_impex.blender.effect_decals import prepare
                prepare(visual)
            if kind=='WaterDecal':
                from sr_impex.blender.effect_water import prepare
                try:visual.water_volume=prepare(self,visual,texture,asset)
                except Exception as exc:
                    self.warn(f'WaterDecal volume: {exc}; trying static 2D texture')
                    try:
                        image=self.texture_image(texture,asset)
                        node=visual.geometry.data.materials[0].node_tree.nodes.new('ShaderNodeTexImage');node.image=image
                        links=visual.geometry.data.materials[0].node_tree.links
                        links.new(node.outputs['Color'],visual.shader.inputs[1]);links.new(node.outputs['Alpha'],visual.alpha.inputs[0])
                    except Exception as fallback:
                        self.warn(f'WaterDecal texture: {fallback}');visual.alpha.inputs[0].default_value=0.
            if kind!='Billboard':self.warn(CAPABILITIES[kind])
            if getattr(payload,'texture_two',''):self.warn('Secondary billboard texture composition is not reproduced')
        elif kind=='Sound':
            visual.audio_strips=self.sound(payload.sound_file,start,asset,1.,self.seed+self.created) or []
        elif kind=='Effect':
            if not payload.embedded and payload.effect_file:
                try:self.add_effect(payload.effect_file,start,obj,source=asset,stack=stack)
                except (OSError,ValueError) as exc:self.warn(exc)
        elif kind=='SfpSystem':
            system=(payload.system_file,tracks,asset,SfpRamps(element,self.warn))
        elif kind=='SfpForceField':
            self.warn(CAPABILITIES[kind])
        elif kind in ('SfpEmitter','Emitter','Satellite'):
            texture=system[0] if kind=='SfpEmitter' and system else getattr(payload,'emitter_file','')
            visual.geometry=_quad(self.collection,'Particles '+element.name,obj)
            visual.shader,visual.alpha=self.material(visual.geometry,texture,system[2] if system else asset)
            self.prepare_particles(visual,system)
            self.warn(CAPABILITIES[kind])
        elif kind=='Trail':
            from sr_impex.blender.effect_trails import prepare
            visual.geometry=_quad(self.collection,'Trail '+element.name,obj)
            visual.geometry.parent=None  # Historical vertices are in world space.
            visual.shader,visual.alpha=self.material(visual.geometry,payload.trail_file,asset)
            prepare(visual)
            self.particle_shader(visual)
            self.warn(CAPABILITIES[kind])
        elif kind in ('EffectMesh','MeshMaterial','AnimatedMesh','AnimatedMeshMaterial','Physic'):
            try:self.mesh(visual,payload,asset)
            except Exception as exc:self.warn(f'{kind}: {exc}')
            if kind!='EffectMesh':self.warn(CAPABILITIES[kind])
        elif kind not in ('SfpSystem','Effect'):
            self.warn(kind+': '+CAPABILITIES[kind])
        visual.system=system
        if visual.shader:
            from sr_impex.blender.effect_blending import prepare
            visual.blend=prepare(visual)
            from sr_impex.blender.effect_glow import prepare_visual
            prepare_visual(self,visual)
        for child in element.children:
            self.add_element(child,obj,asset,start,duration,stack,system)

    def mesh(self,visual,payload,source):
        from sr_impex.definitions.drs_definitions import DRS
        from sr_impex.utilities.drs_utility import create_mesh_object,setup_material_parameters,setup_armature
        from sr_impex.utilities.effect_assets import virtual_path
        name=(getattr(payload,'mesh_file','') or getattr(payload,'mesh_material_file','')
              or getattr(payload,'physic_file',''))
        asset=self.resolve(name,source,'meshes')
        raw=asset.read();drs=DRS().read(raw)
        if visual.kind=='Physic':
            from sr_impex.utilities.resource_container import container_nodes
            names={entry[0] for entry in container_nodes(raw)[-1].values()}
            if 'PhysicInertia' not in names:
                # ConstructData leaves +7C null; CPhyObject::Init constructs
                # CPhyInertia, whose inverse inertia defaults to (1,1,1).
                visual.physics_inverse_inertia=(1.,1.,1.)
            else:self.warn('Explicit PhysicInertia payload is not evaluated by the preview yet')
        folder=self.cache/'meshes'/hashlib.sha256(raw).hexdigest()
        folder.mkdir(parents=True,exist_ok=True)
        for mesh in drs.cdsp_mesh_file.meshes:
            for texture in mesh.textures.textures:
                if not texture.name:continue
                try:
                    try:tex=self.library.resolve(texture.name,asset)
                    except (FileNotFoundError,ValueError):tex=self.resolve(texture.name,source,'textures')
                    filename=texture.name if Path(texture.name).suffix else texture.name+'.dds'
                    target=folder/virtual_path(filename)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.is_file():target.write_bytes(tex.read())
                except (OSError,ValueError) as exc:self.warn(exc)
        rig=None
        animation_name=getattr(payload,'animation_file','')
        if animation_name:
            from sr_impex.definitions.ska_definitions import SKA
            from sr_impex.blender.animation_utils import import_ska_animation
            rig,bones=setup_armature(self.collection,drs,locator_prefix='FX Preview ')
            if rig is None:raise ValueError('Animated effect mesh has no skeleton')
            rig[OWNER]=True;rig.data[OWNER]=True;rig.parent=visual.obj;rig.hide_select=True
            for collection in rig.users_collection:collection[OWNER]=True
            ska_asset=self.library.resolve(animation_name,source)
            ska=SKA().read(str(ska_asset.materialize(self.cache)))
            # The import name is unique to this generated rig. Never reuse or
            # delete an artist's identically named Action.
            import_ska_animation(ska,rig,bones,'FX Preview '+uuid.uuid4().hex)
            action=rig.animation_data.action;action[OWNER]=True
            slot=rig.animation_data.action_slot
            rig.animation_data.action=None
            nla=rig.animation_data.nla_tracks.new()
            strip=nla.strips.new('FX animation',math.floor(self.frame_start+visual.start*self.fps),action)
            if slot:strip.action_slot=slot
            strip.action_frame_start=0;strip.action_frame_end=ska.frame_length
            strip.frame_end=max(strip.frame_start+1,self.frame_start+(visual.start+visual.duration)*self.fps)
            strip.use_animated_time=True
            strip.use_animated_time_cyclic=bool(ska.repeat==1)
            strip.extrapolation='HOLD'
            visual.animation=(rig,strip,ska)
        for index in range(drs.cdsp_mesh_file.mesh_count):
            obj,_=create_mesh_object(drs,index,str(folder),'FX Preview',rig)
            self.collection.objects.link(obj);obj.parent=visual.obj
            obj[OWNER]=True;obj.data[OWNER]=True;obj.hide_select=True
            for material in obj.data.materials:material[OWNER]=True
            setup_material_parameters(obj,drs,index)
        from sr_impex.blender.effect_materials import prepare
        visual.material_bindings=prepare(visual,self.warn)
        from sr_impex.blender.effect_refraction import prepare as prepare_refraction
        prepare_refraction(self,visual)

    def update_animation(self):
        # Set NLA time before Blender evaluates the armature, including seeks.
        if not self.enabled and not self.baking:return
        time=self.elapsed()
        for item in self.items:
            if item.animation:
                rig,strip,ska=item.animation
                t=time-item.start
                # OnAttached creates a frozen expression; only Anim (3) moves
                # its normalized time. Missing curves therefore stay at zero.
                value=float(item.tracks.value(3,t,0.,item.duration))
                if item.kind=='AnimatedMesh':value=max(0.,min(1.,value))
                strip.strip_time=value*ska.frame_length

    def bake_motion(self):
        """Snapshot history once; timeline playback never evaluates past frames."""
        import numpy as np
        needed=[item for item in self.items if item.kind=='Trail' or
                item.kind in ('Physic','ForcePoint') or
                (item.system and item.kind in ('SfpForceField','SfpEmitter'))]
        if not needed:return
        seconds=(self.frame_end-self.frame_start)/self.fps
        requested=max(2,math.ceil(seconds*30)+1)
        count=min(1801,requested,max(2,1_000_000//len(needed)))
        if count<requested:self.warn('FX attachment history uses reduced sampling to bound memory')
        self.motion_times=np.linspace(0,seconds,count)
        self.motion={id(item):np.empty((count,4,4),dtype='float32') for item in needed}
        old=self.scene.frame_current+self.scene.frame_subframe
        self.baking=True
        try:
            for index,time in enumerate(self.motion_times):
                frame=self.frame_start+time*self.fps
                self.scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame))
                self.update()
                bpy.context.view_layer.update()
                for item in needed:self.motion[id(item)][index]=np.array(item.obj.matrix_world)
        finally:
            self.baking=False
            self.scene.frame_set(math.floor(old),subframe=old-math.floor(old))
        from sr_impex.utilities.effect_forces import bake
        budget=2_000_000
        emitters=sum(item.kind=='SfpEmitter' for item in needed)
        for item in needed:
            if item.kind!='SfpEmitter':continue
            emitters-=1
            minimum=2*len(item.particle_data[1]) if item.particle_data else 0
            if not item.particle_data or minimum>budget:
                self.warn('Force-cache memory budget reached; remaining emitters use analytic motion')
                continue
            fields=[field for field in needed if field.kind=='SfpForceField' and field.system is item.system]
            item.force_cache=bake(item,fields,self.motion_times,self.motion,
                self.base_matrix.to_3x3()@Vector((0,1,0)),self.warn,self.seed,max(minimum,budget//(emitters+1)))
            if item.force_cache:budget-=item.force_cache[0].shape[0]*item.force_cache[0].shape[1]

    def prepare_particles(self,visual,system):
        # Deliberately approximate: a bounded deterministic sprite field. No
        # claim that this replaces SFP's forces, ramp sources or collision code.
        import numpy as np
        if self.sprite_budget<=0:
            visual.geometry.data.clear_geometry()
            self.warn('Effect preview capped at 8,192 particle sprites per model')
            return
        if visual.kind=='Emitter':
            from sr_impex.utilities.legacy_particles import samples
            # Legacy GPU particles blend each textured sprite continuously.
            # EEVEE DITHERED produces a visible stipple pattern during playback
            # because changing frames cannot accumulate transparency samples.
            # This path has no glow AOV (which needs a separate render policy).
            material=visual.geometry.data.materials[0]
            if hasattr(material,'surface_render_method'):
                material.surface_render_method='BLENDED'
                material.use_transparency_overlap=True
            tr=visual.tracks
            requested=max(0,max(int(round(tr.value(36,t,250,visual.duration)))
                                for t in np.linspace(0,visual.duration,301)))
            count=min(256,self.sprite_budget,requested)
            if count<requested:self.warn('Legacy particle field exceeds the preview sprite budget')
            self.sprite_budget-=count
            visual.legacy_samples=samples(count)
            visual.particle_data=(float('inf'),np.zeros(count),np.zeros((count,3)),None,count)
            self.prepare_particle_mesh(visual,count)
            return
        tr=visual.tracks;sfp=visual.kind=='SfpEmitter'
        life=max(.01,float(tr.value(104 if sfp else 29,0,1.,visual.duration)))
        # Integrate the emission curve once. Replaying/rewinding never resimulates
        # prior frames, and a rate starting at zero can emit later in the clip.
        step=1/30.;births=[];total=0.;maximum=0.
        for tick in range(min(18000,math.ceil(visual.duration/step))):
            now=tick*step
            if visual.kind=='Emitter':life=max(life,float(tr.value(29,now,1.,visual.duration)))
            rate=max(0.,float(tr.value(106 if sfp else 36,now,5.,visual.duration)))
            maximum=max(maximum,rate)
            previous=total;total+=rate*step
            for birth in range(math.floor(previous)+1,math.floor(total)+1):
                births.append(now+(birth-previous)/max(rate,1e-8))
                if len(births)>=20000:break
            if len(births)>=20000:
                self.warn('Particle preview capped at 20,000 scheduled births per emitter');break
        count=min(256,max(1,math.ceil(maximum*life)))
        if maximum*life>256:self.warn('Particle preview capped at 256 visible sprites per emitter')
        rng=np.random.default_rng(self.seed+self.created)
        directions=rng.normal(size=(len(births),3));directions[:,1]=abs(directions[:,1])+1
        directions/=np.maximum(np.linalg.norm(directions,axis=1)[:,None],1e-8)
        if sfp:
            def values(key,default):return np.array([tr.value(key,b,default,visual.duration) for b in births])
            n=len(births)
            horizontal=np.radians(values(100,360.))*rng.random(n)
            vertical=np.radians(values(101,0.))*rng.uniform(-1,1,n)
            directions=np.stack((np.sin(horizontal)*np.sin(vertical),np.cos(vertical),
                                 np.cos(horizontal)*np.sin(vertical)),axis=-1)
            # Emit 10DC6680: shape 0 uses a signed random box, scaled by
            # the extent vector at data +14 / runtime +F4 (track 99).
            shape=np.rint(values(145,0.)).astype('int32')
            extent=values(99,(0.,0.,0.)).reshape((n,3))
            offset=rng.uniform(-1,1,(n,3))*extent
            h=np.radians(values(147,360.))*rng.random(n)
            v=np.radians(values(148,180.))*rng.uniform(-1,1,n)
            spherical=np.stack((np.sin(h)*np.sin(v),np.cos(v),np.cos(h)*np.sin(v)),axis=-1)
            radius=np.where(shape==1,rng.random(n),1.)
            shell=(shape==1)|(shape==2)
            offset[shell]=(spherical*radius[:,None]*extent)[shell]
            # Shape 3: the engine rotates a Z offset around Y, then adds a
            # radial Y offset rotated around X and Y, scaled by extent.
            ring=rng.uniform(-2*math.pi,2*math.pi,n)
            r=rng.random(n)*values(146,0.)
            radial=np.stack((np.sin(h)*np.sin(ring),np.cos(ring),np.cos(h)*np.sin(ring)),axis=-1)
            axis=np.stack((np.sin(h),np.zeros(n),np.cos(h)),axis=-1)
            cylinder=shape==3
            offset[cylinder]=((axis+radial*r[:,None])*extent)[cylinder]
            if np.any((shape<0)|(shape>3)):self.warn('Unknown SFP emission shape uses a box approximation')
            lifetimes=np.maximum(.01,values(104,1.)*(1+values(105,0.)*rng.uniform(-1,1,n)))
            life=max(life,float(lifetimes.max()) if n else life)
            texture_indices=np.stack([values(key,0.) for key in (24,41,42)],axis=-1)
            weights=np.maximum(0.,values(137,(1.,0.,0.))).reshape((n,3))
            pick=rng.random(n)*weights.sum(axis=1)
            slots=np.minimum(2,(pick[:,None]>=np.cumsum(weights,axis=1)).sum(axis=1))
            # Emit (10DC6680): speed/mass variation uses GetUFloat; lifetime
            # uses signed GetFloat. Mass controls per-step system damping.
            visual.birth_state={'life':lifetimes,'speed':values(102,1.)*(1+values(103,0.)*rng.random(n)),
                'mass':values(108,1.)*(1+values(109,0.)*rng.random(n)),
                'size':np.maximum(0.,values(111,.2)*(1+values(112,0.)*rng.random(n))),
                'rotation':np.radians(values(133,0.))*rng.uniform(-1,1,n),
                'angular':np.radians(values(134,0.)+(values(135,0.)-values(134,0.))*rng.random(n)),
                'color':values(129,(1.,1.,1.)).reshape((n,3)),
                'emissive':values(131,(0.,0.,0.)).reshape((n,3)),
                'alpha':values(130,1.),'glow':values(132,0.),
                'offset':offset,
                'atlas':texture_indices[np.arange(n),slots].astype('int32')%256}
            if np.any(visual.birth_state['glow']):self.warn('Particle glow uses a separate Blender AOV approximation when system glow is enabled')
            # No glow AOV is needed when neither births nor ramps produce glow.
            # Smooth alpha avoids stochastic dots in moving low-opacity flames.
            glow_ramp=any(int(system[1].value(key,t,0.,visual.duration))==2
                          for key in (117,118) for t in np.linspace(0,visual.duration,31)) if system else False
            visual._smooth_particles=not np.any(visual.birth_state['glow']) and not glow_ramp
            if visual._smooth_particles:
                material=visual.geometry.data.materials[0]
                if hasattr(material,'surface_render_method'):
                    material.surface_render_method='BLENDED';material.use_transparency_overlap=True
            count=min(256,max(1,math.ceil(maximum*life)))
        if count>self.sprite_budget:self.warn('Effect preview capped at 8,192 particle sprites per model')
        count=min(count,self.sprite_budget);self.sprite_budget-=count
        visual.particle_data=(life,np.array(births),directions,system,count)
        self.prepare_particle_mesh(visual,count)

    def prepare_particle_mesh(self,visual,count):
        mesh=visual.geometry.data
        mesh.clear_geometry()
        for layer in list(mesh.uv_layers):mesh.uv_layers.remove(layer)
        mesh.from_pydata([(0,0,0)]*(count*4),[],[(4*i,4*i+1,4*i+2,4*i+3) for i in range(count)])
        uv=mesh.uv_layers.new()
        for i,item in enumerate(uv.data):item.uv=((0,0),(1,0),(1,1),(0,1))[i%4]
        for name in ('FX Color','FX Emissive'):
            mesh.color_attributes.new(name=name,type='FLOAT_COLOR',domain='POINT')
        self.particle_shader(visual)

    def particle_shader(self,visual):
        material=visual.geometry.data.materials[0];tree=material.node_tree
        nodes=tree.nodes;links=tree.links
        color=nodes.new('ShaderNodeAttribute');color.attribute_name='FX Color'
        emissive=nodes.new('ShaderNodeAttribute');emissive.attribute_name='FX Emissive'
        multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
        links.new(visual.shader.outputs[0],multiply.inputs[1]);links.new(color.outputs['Color'],multiply.inputs[2])
        glow=nodes.new('ShaderNodeMixRGB');glow.blend_type='MULTIPLY';glow.inputs[0].default_value=1
        base=visual.shader.inputs[1]
        if base.is_linked:links.new(base.links[0].from_socket,glow.inputs[1])
        else:glow.inputs[1].default_value=base.default_value
        links.new(emissive.outputs['Color'],glow.inputs[2])
        add=nodes.new('ShaderNodeMixRGB');add.blend_type='ADD';add.inputs[0].default_value=1
        links.new(multiply.outputs[0],add.inputs[1]);links.new(glow.outputs[0],add.inputs[2])
        emission=next(n for n in nodes if n.type=='EMISSION')
        links.new(add.outputs[0],emission.inputs['Color'])
        alpha=nodes.new('ShaderNodeMath');alpha.operation='MULTIPLY'
        if visual.alpha.inputs[0].is_linked:links.new(visual.alpha.inputs[0].links[0].from_socket,alpha.inputs[0])
        else:alpha.inputs[0].default_value=1
        links.new(color.outputs['Alpha'],alpha.inputs[1]);links.new(alpha.outputs[0],visual.alpha.inputs[0])

    def update_particles(self,visual,time):
        import numpy as np
        life,births,directions,system,count=visual.particle_data
        if visual.legacy_samples is not None:
            from sr_impex.utilities.legacy_particles import evaluate
            positions,state=evaluate(visual.tracks,time,visual.duration,visual.legacy_samples,self.warn)
            self._write_particles(visual,positions,state,count,time,system)
            return
        low=np.searchsorted(births,time-life,side='right')
        high=np.searchsorted(births,time,side='right')
        low=max(low,high-count)
        indices=np.arange(low,high)
        if visual.birth_state is not None:
            indices=indices[time-births[indices]<visual.birth_state['life'][indices]]
        age=time-births[indices]
        sfp=visual.kind=='SfpEmitter';tr=visual.tracks
        speed=float(tr.value(102 if sfp else 25,time,1.,visual.duration))
        size=max(0.,float(tr.value(111 if sfp else 16,time,.2,visual.duration)))
        positions=directions[indices]*age[:,None]*speed
        if system:
            # 10E1B4D6 divides by a double 100.0 (10FC9E30), not 1000.
            gravity=float(system[1].value(97,time,0.,visual.duration))/100.
            positions[:,1]-=.5*gravity*age*age
        world_matrix=visual.world_matrix if visual.world_matrix is not None else visual.obj.matrix_world
        n=len(age);velocity=directions[indices]*speed
        state={'color':np.ones((n,3)),'emissive':np.zeros((n,3)),'alpha':np.ones(n),
               'glow':np.ones(n),'size':np.full(n,size),'rotation':np.zeros(n),
               'atlas':np.full(n,int(tr.value(24,time,0.,visual.duration)),dtype='int32')}
        lifetime=np.full(n,life);angular=np.zeros(n)
        if visual.birth_state is not None:
            state.update({key:visual.birth_state[key][indices].copy() for key in
                          ('color','emissive','alpha','glow','size','rotation','atlas')})
            lifetime=visual.birth_state['life'][indices];angular=visual.birth_state['angular'][indices]
            state['rotation']+=angular*age
            velocity=directions[indices]*visual.birth_state['speed'][indices,None]
            positions=visual.birth_state['offset'][indices]+velocity*age[:,None]
            if system:positions[:,1]-=.5*gravity*age*age
        survivors=np.ones(n,dtype=bool)
        if visual.force_cache:
            from sr_impex.utilities.effect_forces import evaluate
            world,survivors,world_velocity=evaluate(visual.force_cache,indices,age)
            # The cache already contains world positions. Keep them there;
            # reparenting to the current emitter would drag old particles along
            # and a singular scale must never manufacture an epsilon inverse.
            if not getattr(visual,'_cached_world_geometry',False):
                visual.geometry.parent=None;visual.geometry.matrix_world=Matrix.Identity(4)
                visual._cached_world_geometry=True
            world_matrix=Matrix.Identity(4)
            positions=world;velocity=world_velocity
        if system and sfp:
            state=system[3].apply(system[1],time,visual.duration,age,lifetime,velocity,
                                  state['rotation'],angular,state)
            visual.alpha.inputs[1].default_value*=max(0.,system[1].value(5,time,1.,visual.duration))
        elif not sfp:
            weight=np.clip(age/life,0,1)
            start_color=np.array(tr.value(10,time,(1.,1.,1.),visual.duration))
            end_color=np.array(tr.value(11,time,tuple(start_color),visual.duration))
            state['color']=start_color[None,:]+(end_color-start_color)[None,:]*weight[:,None]
            state['alpha']=tr.value(12,time,1.,visual.duration)*(1-weight)+tr.value(13,time,0.,visual.duration)*weight
            if visual.kind=='Emitter':
                from sr_impex.utilities.legacy_particles import colors
                state['color'],state['alpha']=colors(start_color,end_color,
                    tr.value(12,time,1.,visual.duration),tr.value(13,time,0.,visual.duration),age,lifetime)
            state['size']=size*(1-weight)+tr.value(17,time,size,visual.duration)*weight
        state['alpha']=state['alpha']*survivors
        self._write_particles(visual,positions,state,count,time,system,world_matrix)

    def _write_particles(self,visual,positions,state,count,time,system,world_matrix=None):
        import numpy as np
        tr=visual.tracks;n=len(positions)
        if world_matrix is None:
            world_matrix=visual.world_matrix if visual.world_matrix is not None else visual.obj.matrix_world
        # Native emitter VS transforms the center with ObjectToView, THEN adds
        # its billboard corner in view XY. Zero emitter scale is valid. An
        # epsilon inverse manufactures enormous quads for a collapsed matrix.
        if not getattr(visual,'_particle_world_space',False):
            try:inverse=world_matrix.inverted()
            except ValueError:
                visual._particle_world_space=True
                visual.geometry.parent=None
                visual.geometry.matrix_world=Matrix.Identity(4)
        if getattr(visual,'_particle_world_space',False):
            world=np.array(world_matrix)
            positions=positions@world[:3,:3].T+world[:3,3]
            basis=np.array(self.view_matrix().to_3x3())
        else:
            basis=np.array(inverse.to_3x3()@self.view_matrix().to_3x3())
        corners=np.array(((-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0)))
        ca=np.cos(state['rotation']);sa=np.sin(state['rotation'])
        rotated=np.broadcast_to(corners,(n,4,3)).copy()
        rotated[:,:,0]=corners[:,0]*ca[:,None]-corners[:,1]*sa[:,None]
        rotated[:,:,1]=corners[:,0]*sa[:,None]+corners[:,1]*ca[:,None]
        offsets=(rotated@basis.T)*np.maximum(state['size'],0)[:,None,None]
        vertices=np.zeros((count,4,3),dtype='float32')
        vertices[:n]=positions[:,None,:]+offsets
        visual.geometry.data.vertices.foreach_set('co',vertices.ravel())
        colors=np.zeros((count,4),dtype='float32');glow=np.zeros((count,4),dtype='float32')
        colors[:n,:3]=state['color'];colors[:n,3]=np.clip(state['alpha'],0,1)
        glow[:n,:3]=state['emissive'];glow[:n,3]=state['glow']
        visual.geometry.data.color_attributes['FX Color'].data.foreach_set('color',np.repeat(colors,4,axis=0).ravel())
        if not np.array_equal(getattr(visual,'_last_emissive',None),glow):
            visual.geometry.data.color_attributes['FX Emissive'].data.foreach_set('color',np.repeat(glow,4,axis=0).ravel())
            visual._last_emissive=glow.copy()
        tiles=1<<max(0,min(8,int(system[1].value(51,time,0.,visual.duration) if system else tr.value(51,time,0.,visual.duration))))
        cells=np.zeros(count,dtype='int32')
        cells[:n]=state.get('atlas',np.zeros(n))%(tiles*tiles)
        uv_key=(tiles,cells.tobytes())
        if getattr(visual,'_last_particle_uv',None)!=uv_key:
            uv=np.tile(np.array(((0,0),(1,0),(1,1),(0,1)),dtype='float32'),(count,1))
            uv[:,0]=(uv[:,0]+np.repeat(cells%tiles,4))/tiles
            uv[:,1]=(uv[:,1]+np.repeat(tiles-1-cells//tiles,4))/tiles
            visual.geometry.data.uv_layers.active.data.foreach_set('uv',uv.ravel())
            visual._last_particle_uv=uv_key
        visual.geometry.data.update()

    def update(self):
        # Hidden preloaded building stages need one update to hide their data,
        # then can sleep until selected. Do not animate all destruction stages.
        if not self.baking:
            if not self.enabled and self._last_enabled is False:return
            self._last_enabled=self.enabled
        frame=self.scene.frame_current+self.scene.frame_subframe
        time=self.elapsed()
        for root,start,duration,linked in self.events:
            if linked and self.anchor:
                root.matrix_world=self.anchor.matrix_world@Matrix.Translation(Vector(root['_sr_fx_offset']))
        worlds={}
        for item in self.items:
            t=time-item.start;tr=item.tracks
            opacity=fade_value(item.fades,time)
            active=(self.enabled or self.baking) and 0<=t<=item.duration and opacity>1e-6 and node_active(item.active_window,t)
            if item.kind=='Emitter' and int(tr.value(63,t,0.,item.duration))==2:
                # +30-adjusted setter 10BC1B10 -> +12C; OnUpdateParameters
                # passes it to SetParticleMode. Mode 2 sorts into distortion
                # group 2800, not the ordinary colored-particle pass 2100.
                # Until its framebuffer pass exists, do not invent fire RGB.
                active=False
                self.warn(f'Emitter {item.element.name}: distortion-only particles have no color preview; screen-space heat distortion is not yet reproduced')
            location=tr.value(0,t,(0.,0.,0.),item.duration)
            rotation=_rotation(tr,t,item.duration,item.kind)
            if item.kind in ('Physic','ForcePoint'):
                from sr_impex.utilities.effect_tracks import components
                statics={s.track_type:components(s.data.value) for s in item.element.static_tracks}
                location=statics.get(6,(0.,0.,0.))
                rotation=Euler(tuple(math.radians(v) for v in statics.get(12,(0.,0.,0.))),'XYZ').to_quaternion()
            if item.kind in ('Decal','StaticDecal'):
                rotation=Euler((0,tr.value(1,t,(0.,0.,0.),item.duration)[1],0),'XYZ').to_quaternion()
            scale=(1.,1.,1.) if item.kind in ('Billboard','Physic','ForcePoint','Decal','StaticDecal') else tr.value(2,t,(1.,1.,1.),item.duration)
            if item.kind=='SfpSystem':
                size=max(0.,float(tr.value(6,t,1.,item.duration)));scale=(size,size,size)
            local_matrix=Matrix.LocRotScale(Vector(location),rotation,Vector(scale))
            if item.bone_target:
                rig,bone=item.bone_target
                world=rig.matrix_world@rig.pose.bones[bone].matrix@local_matrix
            elif item.slot_target:
                target,bone,local=item.slot_target
                world=local.copy() if target is None else target.matrix_world@(
                    target.pose.bones[bone].matrix@local if bone else local)
                world=world@local_matrix
            elif item.obj.parent:
                parent=worlds.get(item.obj.parent.as_pointer(),item.obj.parent.matrix_world)
                world=parent@local_matrix
            else:world=local_matrix
            if item.physics_cache is not None and not self.baking:
                from sr_impex.blender.effect_physics import evaluate
                world=evaluate(item.physics_cache,time)
            item.world_matrix=world;worlds[item.obj.as_pointer()]=world
            if item.obj.matrix_world!=world:item.obj.matrix_world=world
            if self.baking:continue
            for strip in item.audio_strips:
                volume=max(0.,strip['_sr_fx_base_volume']*tr.value(77,t,1.,item.duration)*opacity)
                if strip.volume!=volume:strip.volume=volume
                if strip.mute==active:strip.mute=not active
            geo=item.geometry
            if geo:
                if geo.hide_render==active:geo.hide_render=not active
                if geo.hide_viewport==active:geo.hide_viewport=not active
            if item.kind=='Light' and geo:
                geo.data.color=tr.value(4,t,(1.,1.,1.),item.duration)
                geo.data.use_custom_distance=True
                geo.data.cutoff_distance=max(0.,tr.value(9,t,item.element.light.range,item.duration))
                geo.data.energy=max(0.,tr.value(40,t,1.,item.duration))*100.*opacity
            elif item.kind=='Billboard' and geo:
                scale=tr.value(2,t,(1.,1.,1.),item.duration)
                scale=Vector((scale[0],scale[1],1.))
                if geo.scale!=scale:geo.scale=scale
                matrix=world.inverted_safe()@self.view_matrix()
                if geo.rotation_mode!='QUATERNION':geo.rotation_mode='QUATERNION'
                rotation=matrix.to_quaternion()
                if geo.rotation_quaternion!=rotation:geo.rotation_quaternion=rotation
                cols=1<<max(0,min(8,int(tr.value(52,t,0.,item.duration))))
                rows=1<<max(0,min(8,int(tr.value(53,t,0.,item.duration))))
                cell=int(tr.value(24,t,0.,item.duration))%(cols*rows)
                uv_key=(cols,rows,cell)
                if getattr(item,'_last_billboard_uv',None)!=uv_key:
                    for loop,uv in enumerate(((0,0),(1,0),(1,1),(0,1))):
                        geo.data.uv_layers.active.data[loop].uv=((uv[0]+cell%cols)/cols,(uv[1]+rows-1-cell//cols)/rows)
                    item._last_billboard_uv=uv_key
            if item.shader:
                color=tr.value(4,t,(1.,1.,1.),item.duration)
                value=(*color[:3],1.)
                if tuple(item.shader.inputs[2].default_value)!=value:item.shader.inputs[2].default_value=value
                alpha_track=90 if item.kind=='StaticDecal' else 5
                value=max(0.,tr.value(alpha_track,t,1.,item.duration))*opacity if active else 0.
                if item.alpha.inputs[1].default_value!=value:item.alpha.inputs[1].default_value=value
            if item.decal_grid is not None and active:
                from sr_impex.blender.effect_decals import update
                up=(self.base_matrix.to_3x3()@Vector((0,1,0))).normalized()
                target=self.terrain_surface if item.kind=='Decal' else self.static_surface if item.kind=='StaticDecal' else None
                update(item,time,target,
                       up,self.base_matrix.translation)
            if item.water_volume is not None and active:
                from sr_impex.blender.effect_water import update
                update(item,t)
            if item.blend:
                from sr_impex.blender.effect_blending import update
                source=item.system[1] if item.kind=='SfpEmitter' and item.system else tr
                preset=source.value(8,t,0x30b,item.duration)
                if item.kind=='Emitter':
                    from sr_impex.utilities.legacy_particles import SURFACE_ROUTES
                    mode=int(round(tr.value(22,t,5.,item.duration)))
                    if mode in SURFACE_ROUTES:preset=SURFACE_ROUTES[mode]
                    else:self.warn(f'Legacy emitter blend mode {mode} is not reproduced; requires its engine shader/compositor route')
                update(item.blend,preset,self.warn)
            if item.glow_uniform is not None:
                source=item.system[1] if item.kind=='SfpEmitter' and item.system else tr
                value=max(0.,source.value(59,t,0.,item.duration)) if active else 0.
                if item.glow_uniform.default_value!=value:item.glow_uniform.default_value=value
            if item.particle_data and active:self.update_particles(item,t)
            if item.kind=='Trail' and active and id(item) in self.motion:
                from sr_impex.blender.effect_trails import update
                update(item,time,self.motion_times,self.motion[id(item)])
            if item.kind in ('EffectMesh','MeshMaterial','AnimatedMesh','AnimatedMeshMaterial','Physic'):
                for child in item.obj.children:
                    visible=active and (not child.get('_sr_fx_refraction_data') or getattr(self,'screen_refraction',False))
                    if child.hide_render==visible:child.hide_render=not visible
                    hidden=not active or bool(child.get('_sr_fx_refraction_data'))
                    if child.hide_viewport!=hidden:child.hide_viewport=hidden
                from sr_impex.blender.effect_materials import update
                update(item.material_bindings,t,item.duration,
                       tr.value(5,t,1.,item.duration)*opacity if active else 0.,self.warn)

    def report(self):
        unhandled={}
        for item in self.items:
            ids=set(item.tracks.groups)-USED_TRACKS.get(item.kind,{0,1,2})
            if ids:unhandled.setdefault(item.kind,set()).update(ids)
        data={'components':self.counts,'capabilities':{k:CAPABILITIES[k] for k in self.counts},
              'warnings':sorted(self.warnings),'audio_sources':len(self.strips),
              'unhandled_dynamic_tracks':{k:sorted(v) for k,v in unhandled.items()},
              'frame_range':[self.frame_start,self.frame_end],
              'status':'Blender approximation; validate the exported model in the Map Editor'}
        text=bpy.data.texts.get(self.report_name) or bpy.data.texts.new(self.report_name)
        text.clear();text.write(json.dumps(data,indent=2))
        self.collection['status']=f'{len(self.items)} components, {len(self.strips)} audio cues, {len(self.warnings)} limitations'
        return data


def stop_changed_model_audio(context):
    """React to viewport-object and Outliner-collection model changes.

    Compare with the selection at preview creation: a stale object left selected
    while choosing a collection must not instantly silence a newly built preview.
    """
    scene=context.scene
    sessions=[s for s in SESSIONS.values() if s.scene==scene and s.strips]
    if not sessions:return
    obj=context.active_object;col=context.view_layer.active_layer_collection.collection
    current=(obj.as_pointer() if obj else 0,col.as_pointer())
    roots=None
    for session in sessions:
        try:
            previous=session.selection_context
            if previous==current:continue
            if roots is None:roots=[c for c in scene.collection.children_recursive if c.name.startswith('DRSModel_')]
            if current[1]!=previous[1]:
                owners=[root for root in roots if col==root or col in root.children_recursive]
                if len(owners)==1 and owners[0]!=session.model:
                    stop_other_audio(scene,owners[0]);return
            if obj and obj.select_get() and current[0]!=previous[0]:
                owners=[root for root in roots if obj.name in root.all_objects]
                if len(owners)==1 and owners[0]!=session.model:
                    stop_other_audio(scene,owners[0]);return
        except ReferenceError:
            stop_other_audio(scene);return


def stop_other_audio(scene,model=None):
    """Stop preview-owned audio outside the newly selected/imported model."""
    if not scene.sequence_editor:return
    removed=False
    for strip in list(scene.sequence_editor.strips):
        if strip.get(OWNER) and (model is None or strip.get('_sr_fx_model')!=model.name):
            scene.sequence_editor.strips.remove(strip);removed=True
    if removed:
        for session in SESSIONS.values():
            try:inactive=session.scene==scene and (model is None or session.model!=model)
            except ReferenceError:inactive=True
            if inactive:
                session.strips.clear()
                for item in session.items:item.audio_strips.clear()
        for sound in list(bpy.data.sounds):
            if sound.get(OWNER) and sound.users==0:bpy.data.sounds.remove(sound)


def clear(scene,model=None):
    from sr_impex.blender import effect_refraction
    effect_refraction.clear(scene)
    from sr_impex.blender.building_damage_preview import restore
    restore(scene,model)
    def remove_tree(collection):
        for child in list(collection.children):
            if child.get(OWNER):remove_tree(child)
        for obj in list(collection.objects):
            if obj.get(OWNER):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(collection)
    for key,session in list(SESSIONS.items()):
        if session.scene==scene and (model is None or session.model==model):
            if scene.sequence_editor:
                for strip in session.strips:
                    try:scene.sequence_editor.strips.remove(strip)
                    except ReferenceError:pass
            SESSIONS.pop(key)
            try:
                remove_tree(session.collection)
            except ReferenceError:pass
    # Saved previews can outlive the Python session after opening a .blend.
    # Remove only generated data belonging to this scene/model.
    if scene.sequence_editor:
        for strip in list(scene.sequence_editor.strips):
            if strip.get(OWNER) and (model is None or strip.get('_sr_fx_model')==model.name):
                scene.sequence_editor.strips.remove(strip)
    for collection in list(scene.collection.children):
        if collection.get(OWNER) and (model is None or collection.get('_sr_fx_model')==model.name):
            remove_tree(collection)
    for collection in (bpy.data.meshes,bpy.data.armatures,bpy.data.actions,bpy.data.materials,bpy.data.lights,bpy.data.sounds,bpy.data.images):
        for data in list(collection):
            if data.get(OWNER) and data.users==0:collection.remove(data)
    if not any(s.scene==scene for s in SESSIONS.values()) and '_sr_fx_previous_render_lock' in scene:
        scene.render.use_lock_interface=bool(scene['_sr_fx_previous_render_lock'])
        del scene['_sr_fx_previous_render_lock']
    if not any(s.scene==scene for s in SESSIONS.values()):
        from sr_impex.blender.effect_render import restore
        restore(scene)
    if not any(s.scene==scene and s.has_glow for s in SESSIONS.values()):
        from sr_impex.blender.effect_glow import clear as clear_glow
        clear_glow(scene)
    effect_refraction.enable(scene,list(SESSIONS.values()))


def build(context,model,entry,library,seed=0,audio=True,variant_override=None,locator_blob=None,action_override=None,allow_scene_events=False):
    if context.mode!='OBJECT':raise ValueError('Switch to Object Mode to rebuild the effect preview')
    if bpy.app.is_job_running('RENDER'):raise ValueError('Wait for the current render to finish before rebuilding effects')
    scene=context.scene
    action=action_override if action_override is not None else bpy.data.actions.get(entry.action) if entry else None
    has_events=bool(entry and any(v.file for key in entry.keyframes for v in key.variants))
    if has_events and action is None and not allow_scene_events:raise ValueError('Import or assign an Action to preview this clipâ€™s timed effect events')
    from sr_impex.blender.animation_utils import clip_frame_range,configure_clip_playback
    f0,f1=clip_frame_range(action) if action else (float(scene.frame_start),float(scene.frame_end))
    if f1<=f0:raise ValueError('The selected Action has no usable frame range')
    clear(scene,model)
    if action:configure_clip_playback(scene,action)
    session=Session(scene,model,library,f0,f1,seed,audio)
    session.locator_blob=locator_blob
    SESSIONS[(scene.as_pointer(),model.as_pointer())]=session
    previous_selection=list(context.selected_objects);active=context.view_layer.objects.active
    try:
        from sr_impex.blender.animation_utils import assign_action_compat
        rig=next((o for o in model.all_objects if o.type=='ARMATURE'),None)
        if rig and action:assign_action_compat(rig,action)
        session.add_persistent()
        skipped_variants=0
        for index,key in enumerate(entry.keyframes if entry else []):
            if variant_override and index==variant_override[0] and 0<=variant_override[1]<len(key.variants):
                selected=key.variants[variant_override[1]].to_dict()
            else:selected=choose_variant([v.to_dict() for v in key.variants],seed+index)
            if not selected or not selected.get('name'):
                if any(v.file for v in key.variants):skipped_variants+=1
                continue
            start=key.time*(f1-f0)/session.fps
            if key.key_type=='0':session.sound(selected['name'],start,volume=key.volume,seed=seed+index,
                                              pitch_shift=(key.pitch_min,key.pitch_max))
            elif key.key_type in ('1','2'):
                try:session.add_effect(selected['name'],start,offset=key.offset,linked=key.key_type=='2')
                except (OSError,ValueError) as exc:session.warn(exc)
            else:
                fades=session.persistent.get(selected['name'].replace('\\','/').rsplit('/',1)[-1].casefold(),[])
                if not fades:session.warn('Fade event has no matching persistent locator FX')
                for curve in fades:curve.append((start,0. if key.key_type=='3' else 1.,float(key.offset[0])))
        if any(item.kind in ('Physic','Decal','StaticDecal') for item in session.items):
            from sr_impex.blender.effect_surfaces import snapshot
            session.surface=snapshot(context,session.warn,exclude=model.all_objects)
            session.terrain_surface=session.surface
            if any(item.kind=='StaticDecal' for item in session.items):
                session.static_surface=snapshot(context,session.warn,static_only=True)
            if session.surface is None:
                session.warn('No scene terrain surface: physics and terrain decals use the model-origin ground plane')
        session.bake_motion()
        from sr_impex.blender.effect_physics import bake
        bake(session)
        from sr_impex.blender.effect_glow import enable
        enable(session)
        from sr_impex.blender.effect_refraction import enable as enable_refraction
        enable_refraction(scene,list(SESSIONS.values()))
        from sr_impex.blender.effect_render import configure
        configure(scene,list(SESSIONS.values()))
        session.update_animation()
        context.view_layer.update()
        session.update();session.report()
        if not session.items and not session.strips:
            if session.warnings:
                detail='; '.join(sorted(session.warnings)[:2])
                raise NoPreviewResources('Effect preview could not load: '+detail+'. See '+session.report_name+' in the Text Editor.')
            if session.requested_resources and all(kind=='audio' for kind,name in session.requested_resources) and not audio:
                raise NoPreviewResources('This clip only has sound cues. Enable Audio to hear them.',expected=True)
            if skipped_variants:
                raise NoPreviewResources('No variant was chosen by the saved chances. Check the chances or use Selected Variant to preview a specific resource.',expected=True)
            if session.requested_resources:
                names=', '.join(dict.fromkeys(name for kind,name in session.requested_resources))
                raise NoPreviewResources(f'The referenced effects contain no preview components: {names}')
            raise NoPreviewResources('No effect events or persistent FX are assigned to this model/clip.',expected=True)
        return session
    except Exception:
        clear(scene,model)
        raise
    finally:
        for obj in context.selected_objects:obj.select_set(False)
        for obj in previous_selection:
            if obj.name in context.view_layer.objects:obj.select_set(True)
        context.view_layer.objects.active=active


@persistent
def _frame_pre(scene,*args):
    for session in list(SESSIONS.values()):
        if session.scene==scene:
            try:session.update_animation()
            except (ReferenceError,RuntimeError,ValueError) as exc:session.warn(exc)


@persistent
def _frame(scene,*args):
    for session in list(SESSIONS.values()):
        if session.scene==scene:
            try:session.update()
            except (ReferenceError,RuntimeError,ValueError) as exc:session.warn(exc)


@persistent
def _load(*args):
    SESSIONS.clear()
    from sr_impex.blender import building_damage_preview
    building_damage_preview.SESSIONS.clear()


def register():
    from sr_impex.blender import effect_refraction
    effect_refraction.register()
    if _frame_pre not in bpy.app.handlers.frame_change_pre:bpy.app.handlers.frame_change_pre.append(_frame_pre)
    if _frame not in bpy.app.handlers.frame_change_post:bpy.app.handlers.frame_change_post.append(_frame)
    if _load not in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.append(_load)


def unregister():
    for scene in bpy.data.scenes:clear(scene)
    from sr_impex.blender import effect_refraction
    effect_refraction.unregister()
    for handlers,callback in ((bpy.app.handlers.frame_change_pre,_frame_pre),(bpy.app.handlers.frame_change_post,_frame),(bpy.app.handlers.load_pre,_load)):
        if callback in handlers:handlers.remove(callback)
