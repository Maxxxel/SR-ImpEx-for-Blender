"""Resolve the edited resource from a mesh, nested collection or preview scene."""
def find_model(context,kind=None):
    import bpy
    roots=[c for c in bpy.data.collections if c.name.startswith('DRSModel_')]
    if kind:roots=[c for c in roots if c.get('_sr_format','BMG' if 'sr_impex_meshgrid_blob' in c else 'DRS')==kind]
    active=context.view_layer.active_layer_collection.collection
    direct=[c for c in roots if active==c or active in c.children_recursive]
    if len(direct)==1:return direct[0]
    obj=context.object
    if obj:
        selected=[c for c in roots if obj.name in c.all_objects]
        if len(selected)==1:return selected[0]
    chosen=getattr(context.scene,'sr_resource_root',None)
    if chosen in roots:return chosen
    return roots[0] if len(roots)==1 else None
