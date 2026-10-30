"""Artist SKA controls: clip settings, markers, shared tracks and playback."""
import json
import math
import bpy
from bpy.props import BoolProperty,EnumProperty,FloatProperty,IntProperty,StringProperty,PointerProperty
from sr_impex.utilities.ska_artist import action_tail,marker_rows,edit_markers,RAW_TRACKS,ALPHA_ID,ALPHA_PATH
from sr_impex.utilities.ska_utility import _iter_action_fcurves
from sr_impex.blender.animation_utils import assign_action_compat,ensure_fcurve_compat,configure_clip_playback


def armature(context):
    obj=context.object
    if obj:
        if obj.type=='ARMATURE' and 'Control_Rig' not in obj.name:return obj
        if obj.type=='MESH':return obj.find_armature()
    return next((o for o in context.collection.all_objects if o.type=='ARMATURE' and 'Control_Rig' not in o.name),None)


def action(context):
    rig=armature(context)
    return rig.animation_data.action if rig and rig.animation_data else None


def operator_action(operator, context):
    """An explicit clip never falls back to an unrelated playing action."""
    name = operator.action_name
    return bpy.data.actions.get(name) if name else action(context)


def notify_clip_changed(clip):
    from . import animation_set_editor as anim
    anim._recompute_all_timing_values(anim._state())
    anim._redraw_ui()


def _clip_action_poll(scene,clip):
    return clip is None or not clip.get('_sr_flow_preview',False)


def _action_changed(scene,context):
    rig=armature(context)
    if rig and scene.sr_ska_action:
        assign_action_compat(rig,scene.sr_ska_action)
        clip=scene.sr_ska_action
        configure_clip_playback(scene,clip)
        if not scene.frame_start<=scene.frame_current<=scene.frame_end:scene.frame_set(scene.frame_start)


def sync_markers(clip):
    for marker in list(clip.pose_markers):
        if marker.name.startswith('SKA:'):clip.pose_markers.remove(marker)
    for index,row in enumerate(marker_rows(action_tail(clip))):
        marker=clip.pose_markers.new(f'SKA:{index:03d} {row["text"]}')
        marker.frame=round(float(clip.get('ska_start_frame',0))+row['time']*clip.get('frame_length',1))


def keyed_clip_range(clip):
    from sr_impex.blender.ska_loop import authored_points
    times = [point.co.x for curve in _iter_action_fcurves(clip) for point in authored_points(clip,curve)]
    if not times:
        return None
    first,last=float(min(times)),float(max(times))
    padding=clip.get('ska_fit_padding')
    if padding is not None:
        first-=float(padding[0]);last+=float(padding[1])
    elif clip.get('ska_import_signature'):
        # Older saved imports lack padding metadata. Preserve their declared
        # window, extending it only if keys have been moved outside it.
        stored=float(clip.get('ska_start_frame',0))
        first=min(first,stored);last=max(last,stored+float(clip.get('frame_length',1)))
    span=last-first
    if abs(span-round(span))<1e-5:span=round(span)
    return first,max(1,math.ceil(span))


class SKA_OT_ClipSettings(bpy.types.Operator):
    bl_description = 'Edit the selected animation clip duration and loop settings'
    action_name:StringProperty(options={'HIDDEN'})
    bl_idname='sr_ska.clip_settings';bl_label='SKA Clip Settings';bl_options={'REGISTER','UNDO'}
    fps:FloatProperty(name='Frames per second',default=30,min=.001,max=1000)
    start:FloatProperty(name='First frame',default=0)
    length:IntProperty(name='Duration in frames',default=30,min=1)
    version:EnumProperty(name='SKA version',items=[('6','6','Completeness is implicitly 2'),('7','7','Stores an explicit completeness word')],default='7')
    repeat:EnumProperty(name='Time addressing',items=[('0','Clamp','Hold the endpoint outside the clip'),('1','Loop','Wrap clip time')],default='0')
    interpolation:EnumProperty(name='Interpolation',items=[('0','Hold','Constant values'),('1','Linear','Linear interpolation'),('2','Cubic Hermite','Edit Bézier handles; export Hermite tangents')],default='2')
    completeness:IntProperty(name='Completeness (advanced)',description='Preserved engine word; no reliable artist-facing effect established',default=2)

    def invoke(self,context,event):
        clip=operator_action(self,context)
        if not clip:self.report({'ERROR'},'Select a deform armature and an action');return {'CANCELLED'}
        self.fps=float(clip.get('original_fps',context.scene.render.fps/context.scene.render.fps_base))
        self.start=float(clip.get('ska_start_frame',0));self.length=int(clip.get('frame_length',max(1,clip.frame_range[1]-clip.frame_range[0])))
        keyed = keyed_clip_range(clip)
        if keyed:self.start,self.length = keyed
        self.version=str(clip.get('ska_version',7));self.repeat=str(clip.get('repeat',0))
        self.interpolation=str(clip.get('stutter_mode',2));self.completeness=int(clip.get('unused1',2))
        return context.window_manager.invoke_props_dialog(self,width=420)

    def draw(self,context):
        col=self.layout
        col.prop(self,'fps')
        bounds=col.column()
        clip=operator_action(self,context)
        bounds.enabled = clip is None or keyed_clip_range(clip) is None
        bounds.prop(self,'start');bounds.prop(self,'length')
        for key in ('repeat','interpolation'):col.prop(self,key)
        if context.scene.sr_ska_debug_view:col.prop(self,'version')
        col.label(text=f'Export duration: {self.length/self.fps:.3f} seconds')
        if context.scene.sr_ska_debug_view and self.version=='7':col.prop(self,'completeness')
        col.label(text='OK fits edited keys and keeps the imported clip padding.',icon='INFO')
        col.label(text='Keyframes stay unchanged; without keys the stored range is kept.')

    def execute(self,context):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        keyed = keyed_clip_range(clip)
        if keyed:self.start,self.length = keyed
        old=int(clip.get('stutter_mode',2))
        old_repeat=int(clip.get('repeat',0))
        if old!=int(self.interpolation):
            from sr_impex.blender.ska_loop import strip
            strip(clip)
        clip['original_fps']=self.fps;clip['ska_start_frame']=self.start;clip['frame_length']=self.length
        clip['original_duration']=self.length/self.fps;clip['ska_version']=int(self.version)
        clip['repeat']=int(self.repeat);clip['stutter_mode']=int(self.interpolation);clip['unused1']=self.completeness
        if hasattr(clip,'use_cyclic'):clip.use_cyclic=self.repeat=='1'
        for curve in _iter_action_fcurves(clip):
            if old!=int(self.interpolation):
                for point in curve.keyframe_points:
                    point.interpolation={'0':'CONSTANT','1':'LINEAR','2':'BEZIER'}[self.interpolation]
                    if self.interpolation=='2':point.handle_left_type=point.handle_right_type='AUTO_CLAMPED'
            if old_repeat != int(self.repeat):
                for modifier in list(curve.modifiers):
                    if modifier.type=='CYCLES':curve.modifiers.remove(modifier)
        from sr_impex.blender.ska_loop import sync
        sync(clip)
        sync_markers(clip)
        notify_clip_changed(clip)
        if action(context)==clip:configure_clip_playback(context.scene,clip)
        return {'FINISHED'}


class SKA_OT_Marker(bpy.types.Operator):
    bl_description = 'Edit a stored SKA text marker; its gameplay use needs testing in the Map Editor'
    action_name:StringProperty(options={'HIDDEN'})
    bl_idname='sr_ska.marker';bl_label='SKA Marker';bl_options={'REGISTER','UNDO'}
    index:IntProperty(default=-1)
    remove:BoolProperty(default=False,options={'HIDDEN'})
    text:StringProperty(name='Marker text',default='<blink>')
    frame:FloatProperty(name='Frame',default=0)
    def invoke(self,context,event):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        if self.remove:return self.execute(context)
        if self.index>=0:
            row=marker_rows(action_tail(clip))[self.index];self.text=row['text']
            self.frame=clip.get('ska_start_frame',0)+row['time']*clip.get('frame_length',1)
        else:self.frame=context.scene.frame_current
        return context.window_manager.invoke_props_dialog(self,width=420)
    def execute(self,context):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        try:
            metadata=action_tail(clip);rows=marker_rows(metadata)
            if self.remove:rows.pop(self.index)
            else:
                row={'time':(self.frame-clip.get('ska_start_frame',0))/clip.get('frame_length',1),'text':self.text}
                if self.index<0:rows.append(row)
                else:rows[self.index].update(row)
            clip['ska_tail_metadata']=json.dumps(edit_markers(metadata,rows,metadata.get('target_ids',[])))
            sync_markers(clip)
        except (ValueError,IndexError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class SKA_OT_Target(bpy.types.Operator):
    bl_description = 'Edit a stored SKA target ID; its artist workflow is not yet established'
    action_name:StringProperty(options={'HIDDEN'})
    bl_idname='sr_ska.target';bl_label='SKA Target ID';bl_options={'REGISTER','UNDO'}
    index:IntProperty(default=-1)
    remove:BoolProperty(default=False,options={'HIDDEN'})
    value:StringProperty(name='Target ID (uint32 / hex)',default='0x0')
    def invoke(self,context,event):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        if self.remove:return self.execute(context)
        if self.index>=0:self.value=hex(action_tail(clip)['target_ids'][self.index])
        return context.window_manager.invoke_props_dialog(self)
    def execute(self,context):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        try:
            metadata=action_tail(clip);ids=list(metadata.get('target_ids',[]))
            if self.remove:ids.pop(self.index)
            elif self.index<0:ids.append(int(self.value,0))
            else:ids[self.index]=int(self.value,0)
            if any(not 0<=v<=0xffffffff for v in ids):raise ValueError('Target ID must fit uint32')
            metadata['target_ids']=ids;clip['ska_tail_metadata']=json.dumps(metadata)
        except (ValueError,IndexError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class SKA_OT_RawTrack(bpy.types.Operator):
    bl_description = 'Remove the selected preserved animation track from export'
    action_name:StringProperty(options={'HIDDEN'})
    bl_idname='sr_ska.remove_preserved_track';bl_label='Remove Preserved Track';bl_options={'REGISTER','UNDO'}
    index:IntProperty(default=0)
    def execute(self,context):
        clip=operator_action(self,context)
        if not clip:return {'CANCELLED'}
        rows=json.loads(clip.get(RAW_TRACKS,'[]'));row=rows.pop(self.index)
        if row['bone_id']==ALPHA_ID:clip['ska_write_alpha']=False
        clip[RAW_TRACKS]=json.dumps(rows)
        return {'FINISHED'}


class SKA_OT_InspectSkin(bpy.types.Operator):
    bl_idname='sr_ska.inspect_skin';bl_label='Inspect Selected Mesh Weights'
    bl_description='Check selected skinned meshes without changing their vertex groups'
    def execute(self,context):
        meshes=[obj for obj in context.selected_objects if obj.type=='MESH']
        if not meshes:
            self.report({'ERROR'},'Select one or more skinned meshes in Object Mode');return {'CANCELLED'}
        if any(obj.mode!='OBJECT' for obj in meshes):
            self.report({'ERROR'},'Switch to Object Mode before inspecting weights');return {'CANCELLED'}
        totals={'meshes':0,'unweighted':0,'over_four':0,'unnormalized':0,'nonbone':0,'missing_rig':0}
        for obj in meshes:
            rig=obj.find_armature()
            if not rig:
                totals['missing_rig']+=1;continue
            totals['meshes']+=1
            names={group.index:group.name for group in obj.vertex_groups}
            bones=set(rig.data.bones.keys())
            for vertex in obj.data.vertices:
                weights=[membership.weight for membership in vertex.groups
                         if membership.weight>0 and names.get(membership.group) in bones]
                if any(membership.weight>0 and names.get(membership.group) not in bones
                       for membership in vertex.groups):totals['nonbone']+=1
                if not weights:totals['unweighted']+=1;continue
                if len(weights)>4:totals['over_four']+=1
                if abs(sum(weights)-1.0)>1e-4:totals['unnormalized']+=1
        context.scene.sr_skin_audit=(f"{totals['meshes']} skinned meshes; {totals['unweighted']} unweighted; "
            f"{totals['over_four']} over four; {totals['unnormalized']} unnormalized; "
            f"{totals['nonbone']} with non-bone groups; {totals['missing_rig']} without armature")
        self.report({'INFO'},context.scene.sr_skin_audit)
        return {'FINISHED'}


class SKA_OT_SelectSkinProblems(bpy.types.Operator):
    bl_idname='sr_ska.select_skin_problems';bl_label='Select Skin Weight Problems'
    bl_description='Select matching vertices on the active skinned mesh and enter Edit Mode'
    bl_options={'REGISTER','UNDO'}
    kind:EnumProperty(items=[('UNWEIGHTED','Unweighted','Vertices without a positive skeleton weight'),
        ('OVER_FOUR','Over four','Vertices with more than four positive skeleton weights'),
        ('UNNORMALIZED','Unnormalized','Vertices whose skeleton weights do not sum to one')])
    def execute(self,context):
        obj=context.object
        if not obj or obj.type!='MESH' or obj.mode!='OBJECT':
            self.report({'ERROR'},'Make a skinned mesh active in Object Mode');return {'CANCELLED'}
        rig=obj.find_armature()
        if not rig:
            self.report({'ERROR'},'The active mesh has no armature');return {'CANCELLED'}
        names={group.index:group.name for group in obj.vertex_groups}
        bones=set(rig.data.bones.keys())
        matching=[]
        for vertex in obj.data.vertices:
            weights=[g.weight for g in vertex.groups if g.weight>0 and names.get(g.group) in bones]
            if ((self.kind=='UNWEIGHTED' and not weights) or
                (self.kind=='OVER_FOUR' and len(weights)>4) or
                (self.kind=='UNNORMALIZED' and weights and abs(sum(weights)-1.0)>1e-4)):
                matching.append(vertex.index)
        if not matching:
            self.report({'INFO'},'No matching vertices on the active mesh');return {'FINISHED'}
        selected=set(matching)
        for face in obj.data.polygons:face.select=False
        for edge in obj.data.edges:edge.select=False
        for vertex in obj.data.vertices:vertex.select=vertex.index in selected
        context.tool_settings.mesh_select_mode=(True,False,False)
        # Blender enters multi-object Edit Mode based on actual selection, not
        # just the context override. Keep the selection operation on this mesh.
        for other in context.selected_objects:
            if other!=obj and other.type=='MESH':other.select_set(False)
        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'},f'Selected {len(matching)} vertices on {obj.name}')
        return {'FINISHED'}


def ska_section(layout,key,title):
    header,body=layout.panel('sr_ska_'+key,default_closed=True)
    header.label(text=title)
    return body


def _clip_foldout(layout, variant, key, title):
    # Variants are drawn in nested boxes; UILayout.panel requires full-width layout.
    box = layout.box()
    opened = getattr(variant, key)
    header = box.row()
    header.use_property_split = False
    header.prop(variant, key, text=title, emboss=False,
                icon='TRIA_DOWN' if opened else 'TRIA_RIGHT')
    return box.column() if opened else None


def draw_clip_settings(layout, context, clip, variant):
    """One clip editor, embedded under the AnimationSet's selected variant."""
    debug = context.scene.sr_ska_debug_view
    length = clip.get('frame_length', max(1, clip.frame_range[1]-clip.frame_range[0]))
    fps = max(float(clip.get('original_fps', context.scene.render.fps/context.scene.render.fps_base)), .001)
    body = _clip_foldout(layout, variant, 'show_clip_settings', 'Clip Settings')
    if body:
        body.label(text=f'{length:g} frames / {length/fps:.3f} s / {fps:g} fps')
        row = body.row(align=True)
        row.operator('sr_ska.clip_settings', text='Edit Settings', icon='PREFERENCES').action_name = clip.name
    extra = _clip_foldout(layout, variant, 'show_ska_advanced', 'Advanced SKA Data')
    if extra:
        extra.label(text='Events and Target IDs: usage is not fully verified.', icon='INFO')
        extra.label(text='Preserved on export; no Blender playback effect.')
        try:
            metadata = action_tail(clip)
            extra.label(text='Events')
            extra.operator('sr_ska.marker', text='Add Event', icon='ADD').action_name = clip.name
            for i, marker in enumerate(marker_rows(metadata)):
                frame = clip.get('ska_start_frame', 0)+marker['time']*length
                row = extra.row(align=True)
                row.label(text=f'{marker["text"]} @ {frame:.2f}')
                op = row.operator('sr_ska.marker', text='', icon='GREASEPENCIL'); op.index=i; op.action_name=clip.name
                op = row.operator('sr_ska.marker', text='', icon='X'); op.index=i; op.remove=True; op.action_name=clip.name
            extra.label(text='Target IDs')
            extra.operator('sr_ska.target', text='Add Target ID', icon='ADD').action_name = clip.name
            for i, value in enumerate(metadata.get('target_ids', [])):
                row = extra.row(align=True); row.label(text=f'0x{value:08X}')
                op = row.operator('sr_ska.target', text='', icon='GREASEPENCIL'); op.index=i; op.action_name=clip.name
                op = row.operator('sr_ska.target', text='', icon='X'); op.index=i; op.remove=True; op.action_name=clip.name
        except (ValueError, TypeError, KeyError) as exc:
            extra.label(text=str(exc), icon='ERROR')
        if debug:
            try:
                for i, track in enumerate(json.loads(clip.get(RAW_TRACKS, '[]'))):
                    row = extra.row(align=True); row.label(text=f'0x{track["bone_id"]:08X} type {track["type"]}')
                    op = row.operator('sr_ska.remove_preserved_track', text='', icon='X'); op.index=i; op.action_name=clip.name
                if any(fc.data_path == ALPHA_PATH for fc in _iter_action_fcurves(clip)):
                    extra.label(text='Alpha: edit the curve in the Graph Editor.', icon='INFO')
            except (ValueError, TypeError, KeyError) as exc:
                extra.label(text=str(exc), icon='ERROR')


def draw_skin_tools(layout, context):
    if not any(o.type=='MESH' and o.find_armature() for o in context.selected_objects):
        return
    skin = ska_section(layout, 'skinning', 'Skinning')
    if skin:
        skin.operator('sr_ska.inspect_skin', text='Check Skin Weights', icon='MOD_VERTEX_WEIGHT')
        if context.scene.sr_skin_audit:
            for entry in context.scene.sr_skin_audit.split('; '):skin.label(text=entry)
            row=skin.row(align=True)
            for kind,label in (('UNWEIGHTED','Unweighted'),('OVER_FOUR','Over 4'),('UNNORMALIZED','Unnormalized')):
                row.operator('sr_ska.select_skin_problems',text=label).kind=kind


classes=(SKA_OT_ClipSettings,SKA_OT_Marker,SKA_OT_Target,SKA_OT_RawTrack,SKA_OT_InspectSkin,SKA_OT_SelectSkinProblems)
def register():
    from sr_impex.blender import ska_loop
    ska_loop.register()
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.sr_ska_action=PointerProperty(type=bpy.types.Action,update=_action_changed,poll=_clip_action_poll)
    bpy.types.Scene.sr_ska_debug_view=BoolProperty(name='View Mode',description='Switch between Artist View and Debug View; debug reveals preserved engine records',default=False)
    bpy.types.Scene.sr_skin_audit=StringProperty(options={'HIDDEN'})
def unregister():
    from sr_impex.blender import ska_loop
    ska_loop.unregister()
    del bpy.types.Scene.sr_ska_action
    del bpy.types.Scene.sr_skin_audit
    del bpy.types.Scene.sr_ska_debug_view
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
