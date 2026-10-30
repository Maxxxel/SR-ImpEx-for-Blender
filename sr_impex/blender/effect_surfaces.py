"""Read-only build-time snapshot of visible scene surfaces for FX previews."""
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def snapshot(context,warn,limit=250000,exclude=(),static_only=False):
    vertices=[];triangles=[];graph=context.evaluated_depsgraph_get()
    excluded={obj.as_pointer() for obj in exclude}
    for obj in context.scene.objects:
        if (obj.as_pointer() in excluded or obj.type!='MESH' or obj.get('_sr_fx_preview') or obj.get('_cdrw_uid') or
            obj.hide_render or not obj.visible_get(view_layer=context.view_layer)):continue
        # A static decal cannot retain a character's pose as a frozen surface.
        # In spawn clips that pose may be far above ground, stretching the
        # projection grid between the airborne body and the fallback floor.
        if static_only and (obj.find_armature() is not None or
                (obj.animation_data and (obj.animation_data.action or obj.animation_data.nla_tracks))):continue
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            if len(triangles)+len(mesh.loop_triangles)>limit:
                warn('FX collision/projection surfaces capped at 250,000 scene triangles');continue
            start=len(vertices)
            vertices.extend(evaluated.matrix_world@v.co for v in mesh.vertices)
            triangles.extend(tuple(start+i for i in tri.vertices) for tri in mesh.loop_triangles)
        finally:evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices,triangles,all_triangles=True) if triangles else None


def project(tree,point,up,origin,distance=100.):
    """Project down to scene surfaces; absent surfaces use the model-origin plane."""
    if tree:
        hit,normal,_,_=tree.ray_cast(point+up*distance,-up,2*distance)
        if hit is not None:return hit,normal if normal.dot(up)>=0 else -normal
    return point-up*((point-origin).dot(up)),up
