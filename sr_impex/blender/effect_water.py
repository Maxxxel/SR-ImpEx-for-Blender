"""Water-decal volume texture playback, using original CSC shader evidence.

WaterDecal_SM4 VS emits TimeLevel.z as volume Z; PS samples a texture3d,
then weights RGB by alpha squared. Scene water waves/fog/shadows remain
separate work. A flat water level and diffuse BSDF substitute their lighting.
"""
import hashlib
import struct
import bpy
from sr_impex.utilities.effect_volume import split_volume,volume_coordinate


def prepare(session,item,name,source):
    asset=session.resolve(name,source,'textures');raw=asset.read()
    key=hashlib.sha256(raw).hexdigest()
    if key in session.volumes:images,indices,depth=session.volumes[key]
    else:
        slices,indices,depth=split_volume(raw,max_texels=session.volume_budget)
        folder=session.cache/'volumes'/key;folder.mkdir(parents=True,exist_ok=True)
        images=[]
        for index,data in zip(indices,slices):
            path=folder/f'{index:04}.dds'
            if not path.is_file():path.write_bytes(data)
            image=bpy.data.images.load(str(path),check_existing=True)
            image['_sr_fx_preview']=True
            image.pixels[0]  # Decode now, rather than during the timeline handler.
            images.append(image)
        height,width=struct.unpack_from('<II',raw,12)
        session.volume_budget-=len(indices)*width*height
        session.volumes[key]=(images,indices,depth)
        if len(indices)<depth:session.warn('Water volume slices are subsampled to bound preview memory')
    material=item.geometry.data.materials[0];tree=material.node_tree;n=tree.nodes;l=tree.links
    a=n.new('ShaderNodeTexImage');b=n.new('ShaderNodeTexImage')
    for tex in (a,b):tex.extension='EXTEND';tex.interpolation='Linear'
    color=n.new('ShaderNodeMixRGB');color.inputs[0].default_value=0.
    l.new(a.outputs['Color'],color.inputs[1]);l.new(b.outputs['Color'],color.inputs[2])
    inverse=n.new('ShaderNodeMath');inverse.operation='SUBTRACT';inverse.inputs[0].default_value=1.
    left=n.new('ShaderNodeMath');left.operation='MULTIPLY'
    right=n.new('ShaderNodeMath');right.operation='MULTIPLY'
    alpha=n.new('ShaderNodeMath');alpha.operation='ADD'
    l.new(a.outputs['Alpha'],left.inputs[0]);l.new(inverse.outputs[0],left.inputs[1])
    l.new(b.outputs['Alpha'],right.inputs[0])
    l.new(left.outputs[0],alpha.inputs[0]);l.new(right.outputs[0],alpha.inputs[1])
    l.new(color.outputs[0],item.shader.inputs[1]);l.new(alpha.outputs[0],item.alpha.inputs[0])
    weighted=n.new('ShaderNodeMixRGB');weighted.blend_type='MULTIPLY';weighted.inputs[0].default_value=1.
    l.new(item.shader.outputs[0],weighted.inputs[1]);l.new(item.alpha.outputs[0],weighted.inputs[2])
    # With the existing over closure, this extra alpha multiplication yields
    # RGB*alpha^2 while preserving background transmission of 1-alpha.
    emission=next(node for node in n if node.type=='EMISSION')
    l.new(weighted.outputs[0],emission.inputs['Color'])
    bsdf=n.new('ShaderNodeBsdfPrincipled');bsdf.inputs['Roughness'].default_value=1.
    bsdf.inputs['Specular IOR Level'].default_value=0.
    l.new(weighted.outputs[0],bsdf.inputs['Base Color'])
    for link in list(emission.outputs[0].links):l.new(bsdf.outputs[0],link.to_socket)
    return images,indices,depth,a,b,color.inputs[0],inverse.inputs[1],left,right


def update(item,time):
    images,indices,depth,a,b,mix,inverse,left,right=item.water_volume
    low,high,weight=volume_coordinate(float(item.tracks.value(7,time,0.,item.duration)),indices,depth)
    if a.image!=images[low]:a.image=images[low]
    if b.image!=images[high]:b.image=images[high]
    mix.default_value=weight;inverse.default_value=weight
    right.inputs[1].default_value=weight
