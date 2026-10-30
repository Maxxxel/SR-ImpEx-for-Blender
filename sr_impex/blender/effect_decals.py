"""Scene-surface projection for terrain decals; never modifies target meshes.

The terrain heightfield is substituted by the scene's cached triangle surfaces.
Dynamic size: 10DF6800 case 6. Static scale/alphas: 10E1FA20, 10E20210.
"""
import numpy as np
from mathutils import Matrix,Vector
from sr_impex.blender.effect_surfaces import project

GRID=16


def prepare(item):
    mesh=item.geometry.data;mesh.clear_geometry()
    for layer in list(mesh.uv_layers):mesh.uv_layers.remove(layer)
    vertices=[(x/GRID-.5,0,z/GRID-.5) for z in range(GRID+1) for x in range(GRID+1)]
    faces=[]
    for z in range(GRID):
        for x in range(GRID):
            a=z*(GRID+1)+x;faces.append((a,a+GRID+1,a+GRID+2,a+1))
    mesh.from_pydata(vertices,[],faces);uv=mesh.uv_layers.new()
    for loop in mesh.loops:
        p=vertices[loop.vertex_index];uv.data[loop.index].uv=(p[0]+.5,p[2]+.5)
    item.geometry.parent=None;item.geometry.matrix_world=Matrix.Identity(4)
    item.geometry.rotation_euler=(0,0,0)
    item.decal_grid=np.array(vertices,dtype='float32')


def update(item,time,tree,up,origin):
    t=time-item.start;tr=item.tracks
    # Both terrain decal consumers use only the Y component of vector rotation.
    # The node's yaw-only world transform is supplied by the session.
    size=max(.0001,float(tr.value(89 if item.kind=='StaticDecal' else 6,t,1.,item.duration)))
    matrix=item.world_matrix
    signature=(tuple(value for row in matrix for value in row),size,id(tree),tuple(up),tuple(origin))
    if getattr(item,'decal_signature',None)==signature:return
    item.decal_signature=signature
    positions=[]
    for point in item.decal_grid:
        p=matrix@Vector(point*size)
        hit,normal=project(tree,p,up,origin)
        positions.append(hit+normal*.002)
    item.geometry.data.vertices.foreach_set('co',np.array(positions,dtype='float32').ravel())
    item.geometry.data.update()
