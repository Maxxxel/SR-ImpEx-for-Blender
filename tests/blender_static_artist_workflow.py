"""Fresh-scene setup, world-space preservation and actual static DRS export."""
from pathlib import Path
import sys
import numpy as np
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sr_impex
sr_impex.register()
from sr_impex.blender.editors import material_editor as editor
from sr_impex.utilities import drs_utility as du
from sr_impex.utilities.material_schema import COLOR_ID
from sr_impex.utilities.artist_context import find_model
du.logger.display=lambda:None
out=ROOT/'artifacts/static-artist-workflow';out.mkdir(exist_ok=True)
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2,location=(1,0,1));obj=bpy.context.object;obj.name='Crate'
obj.rotation_euler=(.2,.3,.6);obj.scale=(.7,1.4,2.)
bpy.context.view_layer.update()
before=np.array(obj.matrix_world)
libraries=len(bpy.context.preferences.filepaths.asset_libraries)
assert bpy.ops.scene.new_bf_scene(model_name='object_artist_test',use_selected=True)=={'FINISHED'}
root=find_model(bpy.context);assert root and obj.parent.name.startswith('GameOrientation')
np.testing.assert_allclose(obj.matrix_world,before,atol=1e-6)
assert len(bpy.context.preferences.filepaths.asset_libraries)==libraries
assert not hasattr(bpy.types,'DRS_PT_debug_tools')
assert bpy.ops.drs.setup_material()=={'FINISHED'}
image=bpy.data.images.new('object_artist_test_col',width=16,height=16)
image.generated_color=(.4,.25,.12,1);image.filepath_raw=str(out/'object_artist_test_col.png');image.file_format='PNG';image.save()
index=next(i for i,r in enumerate(obj.active_material.drs_settings.textures) if int(r.identifier,0)==COLOR_ID)
assert bpy.ops.drs.load_material_texture(filepath=image.filepath_raw,index=index)=={'FINISHED'}
# Select the nested mesh collection, not the root: exporter must resolve it.
branch=bpy.context.view_layer.active_layer_collection
bpy.context.view_layer.active_layer_collection=next(c for c in branch.children if c.name.startswith('Meshes_Collection'))
bpy.context.scene.cursor.location=(7,8,9)
result=bpy.ops.export_scene.drs(filepath=str(out/'object_artist_test.drs'),model_type='StaticObjectNoCollision',export_all_ska_actions=True)
assert result=={'FINISHED'},du.logger.messages
assert not list(out.glob('*.ska'))
assert (out/'object_artist_test.drs').is_file()
np.testing.assert_allclose(obj.matrix_world,before,atol=1e-6)
np.testing.assert_allclose(bpy.context.scene.cursor.location,(7,8,9))
from sr_impex.definitions.drs_definitions import DRS
drs=DRS().read(str(out/'object_artist_test.drs'))
assert drs.cdsp_mesh_file and drs.cgeo_obb_tree
assert (out/'object_artist_test_col.dds').is_file()
print('STATIC_ARTIST_SETUP_TEXTURE_EXPORT_AND_SOURCE_PRESERVATION_OK',flush=True)

# Reimport the actual exported files and compare visible world-space bounds.
from mathutils import Vector
original_points=np.array([obj.matrix_world @ Vector(v) for v in obj.bound_box])
existing=set(bpy.data.objects)
assert du.load_drs(bpy.context,filepath=str(out/'object_artist_test.drs'),import_animation=False)=={'FINISHED'}
loaded=[o for o in bpy.data.objects if o not in existing and o.type=='MESH']
assert loaded, 'No mesh reimported'
bpy.context.view_layer.update()
points=np.array([o.matrix_world @ Vector(v) for o in loaded for v in o.bound_box])
np.testing.assert_allclose(points.min(axis=0),original_points.min(axis=0),atol=1e-5)
np.testing.assert_allclose(points.max(axis=0),original_points.max(axis=0),atol=1e-5)
assert loaded[0].active_material and any(n.image for n in loaded[0].active_material.node_tree.nodes if n.type=='TEX_IMAGE')
print('STATIC_DRS_REIMPORT_WORLD_BOUNDS_AND_TEXTURE_OK',flush=True)

for source in bpy.context.selected_objects:source.select_set(False)
loaded[0].select_set(True);bpy.context.view_layer.objects.active=loaded[0]
assert bpy.ops.export_scene.drs(filepath=str(out/'object_artist_second.drs'),model_type='StaticObjectNoCollision')=={'FINISHED'}
second=DRS().read(str(out/'object_artist_second.drs'))
a=np.array([v.position for v in drs.cdsp_mesh_file.meshes[0].mesh_data[0].vertices])
b=np.array([v.position for v in second.cdsp_mesh_file.meshes[0].mesh_data[0].vertices])
np.testing.assert_allclose(a,b,atol=1e-5)
print('STATIC_IMPORTED_MODEL_REEXPORT_COORDINATES_STABLE_OK',flush=True)
