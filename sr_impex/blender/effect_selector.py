"""Shared modal resource browser; auditions never change model references."""
import json
from types import SimpleNamespace as NS
import bpy
from bpy.props import StringProperty,IntProperty,BoolProperty,FloatProperty,CollectionProperty,PointerProperty,EnumProperty
from sr_impex.utilities.effect_groups import GROUPS,groups,label

_suspended=[]


def state():return bpy.context.window_manager.drs_effect_selector


def _matches(item,value):
    text=(item.path+' '+item.category).lower()
    return (value.group=='ALL' or value.group in groups(item.path)) and all(word in text for word in value.query.lower().split())


def _filter_changed(value,context):
    visible=[i for i,item in enumerate(value.items) if _matches(item,value)]
    if value.index not in visible:value.index=visible[0] if visible else -1


class Resource(bpy.types.PropertyGroup):
    path:StringProperty()
    category:StringProperty()


class Browser(bpy.types.PropertyGroup):
    items:CollectionProperty(type=Resource)
    index:IntProperty(default=0)
    query:StringProperty(name='Search',update=_filter_changed)
    group:EnumProperty(items=GROUPS,default='ALL',update=_filter_changed)
    target:StringProperty()
    model_uid:StringProperty()
    locator_uid:StringProperty()
    entry_index:IntProperty()
    key_index:IntProperty()
    variant_index:IntProperty()
    proxy:StringProperty()
    playing:BoolProperty()
    frame:FloatProperty()
    notice:StringProperty()


class ResourceList(bpy.types.UIList):
    bl_idname='DRS_UL_EffectSelector'
    def filter_items(self,context,data,property):
        return [self.bitflag_filter_item if _matches(item,data) else 0 for item in data.items],[]
    def draw_item(self,context,layout,data,item,icon,active,active_property,index):
        row=layout.row();row.label(text=item.path.replace('\\','/').rsplit('/',1)[-1],icon='FILE')
        row.label(text=item.category)


def destination(context):
    from sr_impex.blender.editors import effect_set_editor as effects,locator_editor as loc
    value=state();model=effects._active_drs_collection(context)
    if not model or str(model.session_uid)!=value.model_uid:raise ValueError('Model selection changed; reopen Effect Selector')
    if value.target=='LOCATOR':
        model,item=loc.selected_fx_item(context)
        if item.uid!=value.locator_uid:raise ValueError('Locator selection changed; reopen Effect Selector')
        return model,item,None
    editor=effects._state()
    if not 0<=value.entry_index<len(editor.items):raise ValueError('Animation entry was removed')
    entry=editor.items[value.entry_index]
    if not 0<=value.key_index<len(entry.keyframes):raise ValueError('Effect event was removed')
    key=entry.keyframes[value.key_index]
    if not 0<=value.variant_index<len(key.variants):raise ValueError('Resource variant was removed')
    return model,key.variants[value.variant_index],key


def selected():
    value=state()
    if not 0<=value.index<len(value.items) or not _matches(value.items[value.index],value):raise ValueError('Select a resource')
    return value.items[value.index].path


def open_browser(context,target):
    from sr_impex.blender.editors import effect_set_editor as effects,locator_editor as loc
    value=state();close(context);value.items.clear();value.target=target
    model=effects._active_drs_collection(context)
    if not model:raise ValueError('Select a model')
    value.model_uid=str(model.session_uid);sound=False
    if target=='LOCATOR':_,item=loc.selected_fx_item(context);value.locator_uid=item.uid
    else:
        key,item=effects._selected_variant();editor=effects._state()
        value.entry_index=editor.active_index;value.key_index=editor.items[editor.active_index].active_keyframe
        value.variant_index=key.active_variant;sound=key.key_type=='0'
    for asset in effects._resource_choices(effects._library(context),sound):
        row=value.items.add();row.path=asset.name;row.category=label(asset.name)
    value.query='';value.group='ALL';value.index=0;value.notice=''
    value.playing=bool(context.screen and context.screen.is_animation_playing)
    value.frame=context.scene.frame_current+context.scene.frame_subframe
    _filter_changed(value,context)
    current=item.file.replace('\\','/').rsplit('/',1)[-1].casefold()
    match=next((i for i,row in enumerate(value.items) if row.path.replace('\\','/').rsplit('/',1)[-1].casefold()==current),None)
    if match is not None:value.index=match


def close(context):
    from sr_impex.blender import effect_preview as fx
    value=state();proxy=bpy.data.collections.get(value.proxy)
    if proxy:
        fx.clear(context.scene,proxy)
        bpy.data.collections.remove(proxy)
        if not value.playing and context.screen and context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        context.scene.frame_set(int(value.frame),subframe=value.frame-int(value.frame))
    value.proxy=''
    for session,enabled,mutes in _suspended:
        if any(current is session for current in fx.SESSIONS.values()):
            session.enabled=enabled;session.update()
            for strip in session.strips:
                if strip.name in mutes:strip.mute=mutes[strip.name]
    _suspended.clear()


class Preview(bpy.types.Operator):
    bl_idname='drs.effect_selector_preview';bl_label='Preview'
    def execute(self,context):
        from sr_impex.blender.editors import effect_set_editor as effects,locator_editor as loc
        from sr_impex.blender import effect_preview as fx
        try:
            model,item,key=destination(context);name=selected();value=state()
            current=fx.SESSIONS.get((context.scene.as_pointer(),model.as_pointer()))
            if current and not any(row[0] is current for row in _suspended):
                _suspended.append((current,current.enabled,{strip.name:strip.mute for strip in current.strips}))
                current.enabled=False;current.update()
                for strip in current.strips:strip.mute=True
            proxy=bpy.data.collections.get(value.proxy)
            if proxy is None:
                proxy=bpy.data.collections.new('FX Resource Audition');context.scene.collection.children.link(proxy)
                for obj in model.all_objects:proxy.objects.link(obj)
                value.proxy=proxy.name
            proxy[loc.BLOB_KEY]=json.dumps({'locators':[]})
            entry=None
            if value.target=='LOCATOR':
                blob=loc._read_blob(model)
                row=next(r for r in blob['locators'] if r.get('uid')==item.uid).copy()
                row.update(file=name,class_id=8)
                proxy[loc.BLOB_KEY]=json.dumps({'locators':[row]})
            else:
                variant=NS(file=name,to_dict=lambda:{'name':name,'weight':100})
                cue=NS(time=0.,key_type='0' if key.key_type=='0' else '2',variants=[variant],
                       volume=key.volume,pitch_min=key.pitch_min,pitch_max=key.pitch_max,
                       offset=key.offset if key.key_type in ('1','2') else (0.,0.,0.))
                entry=NS(action='NONE',keyframes=[cue])
            fx.build(context,proxy,entry,effects._library(context),effects._state().preview_seed,
                     effects._state().preview_audio,allow_scene_events=True)
            context.scene.frame_set(context.scene.frame_start)
            if context.screen and not context.screen.is_animation_playing:bpy.ops.screen.animation_play()
            value.notice='Audition only; the model reference is unchanged.'
        except Exception as exc:
            close(context)
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class Inspect(bpy.types.Operator):
    bl_idname='drs.effect_selector_inspect';bl_label='Inspect'
    def execute(self,context):
        from sr_impex.blender.editors import effect_set_editor as effects
        from sr_impex.utilities.effect_inspection import read_effect,inspect_effect
        try:
            asset=effects._library(context).resolve(selected())
            if asset.name.lower().endswith('.fxb'):
                report=inspect_effect(read_effect(asset.read()))
                state().notice=' · '.join(f'{count} {kind}' for kind,count in report['element_counts'].items())
                text=bpy.data.texts.get('Effect Resource Report') or bpy.data.texts.new('Effect Resource Report')
                text.clear();text.write(json.dumps(dict(report,resource=asset.name,source=str(asset.source)),indent=2))
            else:state().notice='Audio resource: '+asset.name
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class Selector(bpy.types.Operator):
    bl_idname='drs.effect_selector';bl_label='Effect Selector'
    target:EnumProperty(items=[('EFFECT','EffectSet',''),('LOCATOR','Locator','')],default='EFFECT',options={'HIDDEN'})

    def invoke(self,context,event):
        try:
            context.window.cursor_set('WAIT')
            open_browser(context,self.target)
            return context.window_manager.invoke_props_dialog(self,width=900,confirm_text='Use Resource')
        except (ValueError,OSError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        finally:context.window.cursor_set('DEFAULT')

    def draw(self,context):
        value=state();layout=self.layout
        layout.prop(value,'query',text='',icon='VIEWZOOM')
        split=layout.split(factor=.23);categories=split.column(align=True)
        for key,title,_ in GROUPS:categories.prop_enum(value,'group',key,text=title)
        right=split.column();right.template_list('DRS_UL_EffectSelector','',value,'items',value,'index',rows=12)
        if 0<=value.index<len(value.items):right.label(text=value.items[value.index].path)
        row=right.row(align=True);row.operator('drs.effect_selector_preview',icon='PLAY')
        from sr_impex.blender.editors import effect_set_editor as effects
        row.prop(effects._state(),'preview_audio')
        if value.notice:right.label(text=value.notice,icon='INFO')

    def execute(self,context):
        try:
            _,item,_=destination(context);item.file=selected().replace('\\','/').rsplit('/',1)[-1]
            return {'FINISHED'}
        except ValueError as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        finally:close(context)

    def cancel(self,context):close(context)


CLASSES=(Resource,Browser,ResourceList,Preview,Inspect,Selector)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.WindowManager.drs_effect_selector=PointerProperty(type=Browser)
def unregister():
    close(bpy.context)
    del bpy.types.WindowManager.drs_effect_selector
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
