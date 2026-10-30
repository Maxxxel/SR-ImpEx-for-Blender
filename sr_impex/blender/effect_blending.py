"""Surface-closure substitutes for traced DX blend presets.

100510A0 indexes 10FC05B8 in 12-byte records. 1006A230/1006A2D0
convert factors/operations; this establishes 303 additive, 304 alpha-add,
305 screen, 308 multiply, 30B alpha-over and 30C premultiplied-over.
Fogged variants and destination-dependent min/max/subtraction need the scene
framebuffer and cannot be reproduced by an individual Blender surface alone.
"""


def prepare(visual):
    material=visual.geometry.data.materials[0];tree=material.node_tree
    n=tree.nodes;l=tree.links
    output=next(node for node in n if node.type=='OUTPUT_MATERIAL')
    original=output.inputs['Surface'].links[0].from_socket
    source=next(node for node in n if node.type=='EMISSION').inputs['Color'].links[0].from_socket
    emission=n.new('ShaderNodeEmission');emission.name='FX Blend Emission'
    l.new(source,emission.inputs['Color']);l.new(visual.alpha.outputs[0],emission.inputs['Strength'])
    transparent=n.new('ShaderNodeBsdfTransparent');transparent.name='FX Blend Transmission'
    add=n.new('ShaderNodeAddShader');add.name='FX Additive'
    l.new(transparent.outputs[0],add.inputs[0]);l.new(emission.outputs[0],add.inputs[1])
    weighted=n.new('ShaderNodeMixRGB');weighted.blend_type='MULTIPLY';weighted.inputs[0].default_value=1
    l.new(source,weighted.inputs[1]);l.new(visual.alpha.outputs[0],weighted.inputs[2])
    inverse=n.new('ShaderNodeMixRGB');inverse.name='FX Screen Transmission';inverse.blend_type='SUBTRACT'
    inverse.inputs[0].default_value=1;inverse.inputs[1].default_value=(1,1,1,1)
    l.new(weighted.outputs[0],inverse.inputs[2])
    multiply=n.new('ShaderNodeMixRGB');multiply.name='FX Multiply Transmission'
    multiply.inputs[1].default_value=(1,1,1,1)
    l.new(visual.alpha.outputs[0],multiply.inputs[0]);l.new(source,multiply.inputs[2])
    return (material,output,original,add,transparent,inverse,multiply)


def update(binding,preset,warn):
    material,output,original,add,transparent,inverse,multiply=binding
    preset=int(round(preset))
    if material.get('_sr_fx_blendmode')==preset:return
    material['_sr_fx_blendmode']=preset
    tree=material.node_tree;l=tree.links
    for link in list(transparent.inputs['Color'].links):l.remove(link)
    transparent.inputs['Color'].default_value=(1,1,1,1)
    route=original
    if preset in (0x303,0x304):route=add.outputs[0]
    elif preset==0x305:
        l.new(inverse.outputs[0],transparent.inputs['Color']);route=add.outputs[0]
    elif preset==0x308:
        l.new(multiply.outputs[0],transparent.inputs['Color']);route=transparent.outputs[0]
    elif preset==0x30c:
        warn('Premultiplied-over FX uses an alpha-over surface approximation')
    elif preset not in (0x302,0x30b):
        warn(f'FX blend preset {preset:#x} needs framebuffer compositing; preview uses alpha-over')
    if preset==0x303:warn('Additive FX preview weights texture alpha; exact shader premultiplication is not established')
    l.new(route,output.inputs['Surface'])
