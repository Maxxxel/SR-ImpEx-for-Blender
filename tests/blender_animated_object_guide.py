"""Exercise the new animated prop guide without touching game or live Blender data."""
from pathlib import Path
import sys,math
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sr_impex
sr_impex.register()
from sr_impex.utilities import drs_utility as du
from sr_impex.utilities.artist_context import find_model
from sr_impex.blender.editors import animation_set_editor as editor
du.logger.display=lambda:None
out=ROOT/'artifacts/animated-object-guide';out.mkdir(exist_ok=True)
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2,location=(1.5,0,1));mesh=bpy.context.object;mesh.name='Gate'
mesh.scale=(1.5,.15,1);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bpy.ops.scene.new_bf_scene(scene_type='animated_object',model_name='object_gate',use_selected=True)
root=find_model(bpy.context);go=mesh.parent
armcol=bpy.data.collections.new('Armature_Collection');root.children.link(armcol)
bpy.ops.object.armature_add(location=(0,0,0));rig=bpy.context.object;rig.name='Gate Rig'
for col in list(rig.users_collection):col.objects.unlink(rig)
armcol.objects.link(rig)
rig.data.bones[0].name='gate_root'
rig.parent=go;rig.matrix_parent_inverse=Matrix.Identity(4);rig.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
world=mesh.matrix_world.copy();mesh.parent=rig;mesh.matrix_world=world
mod=mesh.modifiers.new('Armature','ARMATURE');mod.object=rig
vg=mesh.vertex_groups.new(name='gate_root');vg.add(list(range(len(mesh.data.vertices))),1.,'REPLACE')
rig.pose.bones['gate_root'].rotation_mode='QUATERNION'
for frame,angle in [(1,0),(31,math.pi/3),(61,0)]:
 bone=rig.pose.bones['gate_root'];bone.rotation_quaternion=Quaternion((0,0,1),angle);bone.keyframe_insert('rotation_quaternion',frame=frame)
clip=rig.animation_data.action;clip.name='gate_idle'
bpy.ops.sr_ska.clip_settings(action_name=clip.name,fps=30,start=1,length=60,repeat='1')
for o in bpy.context.selected_objects:o.select_set(False)
mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
bpy.ops.drs.setup_material()
from sr_impex.utilities.material_schema import COLOR_ID
image=bpy.data.images.new('object_gate_col',width=16,height=16);image.generated_color=(.15,.35,.55,1);image.filepath_raw=str(out/'object_gate_col.png');image.file_format='PNG';image.save()
index=next(i for i,r in enumerate(mesh.active_material.drs_settings.textures) if int(r.identifier,0)==COLOR_ID)
bpy.ops.drs.load_material_texture(filepath=image.filepath_raw,index=index)
bpy.ops.drs.animset_reinit(profile='ANIMATED_OBJECT',replace_existing=True)
st=editor._state();st.mode_keys[0].variants[0].file=clip.name
bpy.ops.drs.animset_save()
def evaluated_points(obj,frame):
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
 return np.array([ev.matrix_world@v.co for v in ev.data.vertices])
expected={f:evaluated_points(mesh,f) for f in (1,31)}
result=bpy.ops.export_scene.drs(filepath=str(out/'object_gate.drs'),model_type='AnimatedObjectNoCollision',export_all_ska_actions=True)
assert result=={'FINISHED'},du.logger.messages
assert (out/'gate_idle.ska').is_file()
from sr_impex.definitions.drs_definitions import DRS
file=DRS().read(str(out/'object_gate.drs'))
assert [(k.vis_job,k.special_mode) for k in file.animation_set.mode_animation_keys]==[(0,0)]
assert file.csk_skeleton and file.csk_skin_info
existing=set(bpy.data.objects)
assert du.load_drs(bpy.context,filepath=str(out/'object_gate.drs'),import_animation=True)=={'FINISHED'}
loaded=[o for o in bpy.data.objects if o not in existing and o.type=='MESH' and o.name.startswith('CDspMeshFile')][0]
newrig=next(o for o in bpy.data.objects if o not in existing and o.type=='ARMATURE')
assert newrig.animation_data and newrig.animation_data.action
for f in (1,31):
 a=expected[f]
 imported_frame=f-float(clip.get('ska_start_frame',1))+float(newrig.animation_data.action.get('ska_start_frame',0))
 b=evaluated_points(loaded,int(imported_frame))
 # UV seams can duplicate vertices. Compare point sets independently of ordering.
 for point in a:assert np.min(np.linalg.norm(b-point,axis=1))<2e-3,(f,point,b)
print('ANIMATED_OBJECT_GUIDE_EXPORT_REIMPORT_POSE_AND_TEXTURE_OK',flush=True)
