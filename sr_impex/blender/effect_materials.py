"""Animate owned FX materials through the existing DRS preview shader.

CFxMaterial::UpdateMaterial (10DE22C0) multiplies curves of the same
semantic. SetMaterial (10E0E990) overrides the whole mesh resource,
copying its first material when the MAT handler is zero.
"""
from sr_impex.utilities.effect_tracks import sample, multiply
from sr_impex.utilities.material_schema import schema, parameter_name


def prepare(visual,warn):
    from sr_impex.blender.editors.material_editor import SCALAR_NAMES
    meshes=[obj for obj in visual.obj.children if obj.type=='MESH']
    if not meshes:return []
    materials=list(dict.fromkeys(mat for obj in meshes for mat in obj.data.materials if mat))
    blocks=visual.element.materials
    if blocks:
        if len(blocks)>1:warn('Multiple MAT blocks: the final material override is previewed')
        block=blocks[-1]
        material=materials[0]
        if block.material_id:
            handler=schema(material_id=block.material_id)['name']
            if handler=='Unknown':warn(f'Unregistered FX MAT handler {block.material_id:#x}')
            else:
                # SetFxMaterial allocates a new CDspMaterial for nonzero IDs.
                # It does not carry the source mesh's texture bindings across.
                import bpy
                material=bpy.data.materials.new('FX MAT Override '+visual.obj.name)
                material['_sr_fx_preview']=True;material.use_nodes=True
                material.drs_settings.material_type=handler
        for obj in meshes:
            obj.data.materials.clear();obj.data.materials.append(material)
        materials=[material]
    result=[]
    for material in materials:
        tree=material.node_tree
        output=next((n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
        if not output or not output.inputs['Surface'].is_linked:continue
        original=output.inputs['Surface'].links[0].from_socket
        mix=tree.nodes.new('ShaderNodeMixShader');mix.name='FX Opacity'
        transparent=tree.nodes.new('ShaderNodeBsdfTransparent')
        tree.links.new(transparent.outputs[0],mix.inputs[1])
        tree.links.new(original,mix.inputs[2]);tree.links.new(mix.outputs[0],output.inputs['Surface'])
        mix.inputs[0].default_value=1.
        if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
        group=tree.nodes.get('DRS_Engine_Group');bindings=[]
        handler=material.drs_settings.material_type
        curves={}
        for track in (blocks[-1].tracks if blocks else []):
            curves.setdefault((track.parameter_type,track.semantic),[]).append(track)
        for (kind,semantic),tracks in curves.items():
            category=('scalar','vector','color')[kind]
            name=parameter_name(handler,category,semantic)
            target=None
            if group:
                if kind==0:
                    label=SCALAR_NAMES.get(semantic,name) if handler=='Default' else name
                    label={'RefractionScale':'Refraction Scale','Alpha':'Texture Alpha Factor',
                           'ExtinctionCoefficient':'Volume Density'}.get(label,label)
                    target=group.inputs.get(label)
                elif kind==2:
                    label={'ColorDiffuse':'Tint Color','Color':'Tint Color','TintColor':'Tint Color',
                           'MaskedColor':'Masked Color','FogColor':'Volume Color'}.get(name,name)
                    target=group.inputs.get(label)
                    if name=='RefractionColor' and tree.nodes.get('Refraction Color'):
                        target=tree.nodes['Refraction Color'].outputs[0]
            if target is None:
                warn(f'FX MAT {handler}: {name} has no Blender animation route')
                continue
            if target.is_linked and not target.is_output:
                warn(f'FX MAT {handler}: {name} is driven by a map; scalar animation cannot override it')
                continue
            bindings.append((target,tracks))
        result.append((mix.inputs[0],bindings))
    return result


def update(bindings,time,duration,opacity,warn):
    for alpha,curves in bindings:
        value=max(0.,min(1.,opacity))
        if alpha.default_value!=value:alpha.default_value=value
        for socket,tracks in curves:
            try:
                value=None
                for track in tracks:
                    current=sample(track,time,duration)
                    value=current if value is None else multiply(value,current)
                if isinstance(value,(tuple,list)) and len(value)==3:value=(*value,1.)
                current=socket.default_value
                if hasattr(current,'__len__'):current=tuple(current)
                if isinstance(value,list):value=tuple(value)
                if current!=value:socket.default_value=value
            except (ValueError,TypeError) as exc:warn(f'FX material curve: {exc}')
