"""Animated-object restrictions in actual Blender operators and picker rows."""
from pathlib import Path
from types import SimpleNamespace
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sr_impex
sr_impex.register()
from sr_impex.blender.editors import animation_set_editor as editor
root=bpy.data.collections.new('DRSModel_object_picker_policy')
bpy.context.scene.collection.children.link(root)
bpy.context.view_layer.active_layer_collection=bpy.context.view_layer.layer_collection.children[root.name]
bpy.ops.object.armature_add();rig=bpy.context.object
if rig.name not in root.objects:root.objects.link(rig)
root['_sr_model_type']='animated_object'
assert editor._model_profile(root)=='ANIMATED_OBJECT'
assert bpy.ops.drs.animset_reinit(profile='ANIMATED_OBJECT',replace_existing=True)=={'FINISHED'}
st=editor._state()
assert [int(m.vis_job) for m in st.mode_keys]==[0]
action=bpy.data.actions.new('Gate opening scripted clip')
bpy.types.Scene.sr_test_ability_items=bpy.props.CollectionProperty(type=editor.AbilityPickItemPG)
items=bpy.context.scene.sr_test_ability_items
editor._fill_picker_items(items,0)
attack=next(i for i in items if i.name=='Attack')
assert not attack.available and 'Base mode' in attack.description
assert not any(i.available for i in items)
assert bpy.ops.drs.modekey_add_ability(ability='Attack',mode=0)=={'CANCELLED'}
assert bpy.ops.drs.modekey_add_ability(ability='Idle',mode=1)=={'CANCELLED'}
assert len(st.mode_keys)==1
# A disabled active row must not get added by Enter, even with a stale checked value.
messages=[]
fake=SimpleNamespace(items=items,active_index=next(i for i,x in enumerate(items) if x.name=='Attack'),
                     mode=0,report=lambda *v:messages.append(v),_rebuild_items=lambda ctx:None)
assert editor.DRS_OT_OpenAbilityPicker.execute(fake,bpy.context)=={'CANCELLED'}
attack.selected=True
assert editor.DRS_OT_OpenAbilityPicker.execute(fake,bpy.context)=={'CANCELLED'}
# A missing Base Idle stays selectable; Idle in another mode does not.
st.mode_keys.clear();editor._fill_picker_items(items,0)
assert [i.name for i in items if i.available]==['Idle']
editor._fill_picker_items(items,1)
assert not any(i.available for i in items)
assert bpy.ops.drs.modekey_add_ability(ability='Idle',mode=0)=={'FINISHED'}
# Draw the actual UIList row and check that its checkbox inherits disabled state.
class Layout:
 def __init__(self,log,parent=None):self.log=log;self.parent=parent;self.enabled=True
 def row(self,**kw):return Layout(self.log,self)
 column=box=row
 def active(self):return self.enabled and (self.parent is None or self.parent.active())
 def prop(self,data,name,**kw):self.log.append(('prop',name,self.active()))
 def label(self,**kw):self.log.append(('label',kw.get('text'),self.active()))
editor._fill_picker_items(items,0);attack=next(i for i in items if i.name=='Attack')
log=[]
editor.DRS_UL_AbilityPicker.draw_item(SimpleNamespace(),bpy.context,Layout(log),None,attack,0,None,0)
assert ('prop','selected',False) in log
# Explain scripts on demand, without adding another gameplay mapping.
assert not st.show_scripted_help
log=[];editor._draw_object_animation_help(Layout(log),root)
assert not any(x[0]=='label' and 'filename' in x[1] for x in log)
st.show_scripted_help=True
log=[];editor._draw_object_animation_help(Layout(log),root)
assert any(x[0]=='label' and 'filename' in x[1] for x in log)
# Switching model type must apply the NEW policy before populating starters.
assert bpy.ops.drs.animset_reinit(profile='STATIC',replace_existing=True)=={'FINISHED'}
assert bpy.ops.drs.modekey_add_ability(ability='Idle',mode=0)=={'CANCELLED'}
assert bpy.ops.drs.animset_reinit(profile='UNIT',replace_existing=True)=={'FINISHED'}
assert [int(m.vis_job) for m in st.mode_keys]==[0,1,2,3,12]
editor._fill_picker_items(items,0)
assert next(i for i in items if i.name=='Attack').available
assert bpy.ops.drs.modekey_add_ability(ability='Attack',mode=0)=={'FINISHED'}
before=[int(m.vis_job) for m in st.mode_keys]
assert bpy.ops.drs.animset_reinit(profile='ANIMATED_OBJECT',replace_existing=False)=={'FINISHED'}
assert [int(m.vis_job) for m in st.mode_keys]==before
assert bpy.data.actions.get(action.name)==action
assert bpy.ops.drs.modekey_add_ability(ability='Cheer',mode=0)=={'CANCELLED'}
del bpy.types.Scene.sr_test_ability_items
print('OBJECT_GREY_PICKER_ENTER_GUARD_PROFILE_SWITCH_AND_SCRIPT_HELP_OK',flush=True)
