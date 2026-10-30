"""OBB leaf coverage and scaled-box containment on separated mesh islands."""
from pathlib import Path
import sys,io
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sr_impex
sr_impex.register()
from sr_impex.utilities.drs_utility import create_cgeo_obb_tree
from sr_impex.definitions.obb_definitions import CGeoOBBTree
from mathutils import Matrix
vertices=[];faces=[]
for x in (-12,-6,0,6,12):
 bpy.ops.mesh.primitive_cube_add(size=2,location=(x,0,0))
 obj=bpy.context.object
 offset=len(vertices);vertices.extend([tuple(obj.matrix_world@v.co) for v in obj.data.vertices])
 faces.extend([tuple(offset+i for i in f.vertices) for f in obj.data.polygons])
mesh=bpy.data.meshes.new('Separated test boxes');mesh.from_pydata(vertices,[],faces)
tree=create_cgeo_obb_tree(mesh)
assert len(tree.obb_nodes)>1
buf=io.BytesIO();tree.write(buf);buf.seek(0);tree=CGeoOBBTree().read(buf)
covered=[]
for node in tree.obb_nodes:
 if node.first_child_index:continue
 ids=range(node.triangle_offset,node.triangle_offset+node.total_triangles)
 covered.extend(ids)
 axes=np.array(node.oriented_bounding_box.matrix.matrix).reshape((3,3)).T
 center=np.array(tuple(getattr(node.oriented_bounding_box.position,k) for k in ('x','y','z')))
 points=np.array([vertices[i] for f in [tree.faces[j] for j in ids] for i in f.indices])
 local=(points-center)@np.linalg.inv(axes).T
 assert np.abs(local).max()<1.001,(node.triangle_offset,node.total_triangles,local)
assert sorted(covered)==list(range(tree.triangle_count))
# Stackless full traversal using the links consumed by native IntersectRay.
visited=[];index=0
while True:
 node=tree.obb_nodes[index];visited.append(index)
 index=node.first_child_index or node.skip_pointer
 if index==0:break
 assert len(visited)<=len(tree.obb_nodes)
assert set(visited)==set(range(len(tree.obb_nodes)))
assert sorted(tuple(f.indices) for f in tree.faces)==sorted(tuple(t.vertices) for t in mesh.loop_triangles)
print('OBB_SERIALIZED_LEAF_SPANS_BOX_CONTAINMENT_AND_SKIP_TRAVERSAL_OK',flush=True)
