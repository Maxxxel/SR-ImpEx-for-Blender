"""Blender shader graphs for editable DRS materials.

The Default flow lookup/channel math and turbulence volume are traced from
the engine. BSDF lighting and ray-traced refraction remain approximations.
"""
import bpy
from pathlib import Path

VERSION = 2
MARKER = '_drs_preview_version'


class Graph:
    def __init__(self, tree):
        self.tree, self.nodes, self.links = tree, tree.nodes, tree.links
        self.count = 0

    def node(self, kind, name):
        node = self.nodes.new(kind); node.name = name; node.label = name
        node.location = ((self.count % 7)*235, -(self.count//7)*230)
        self.count += 1
        return node

    def plug(self, value, socket):
        if hasattr(value, 'is_output'): self.links.new(value, socket)
        else:
            if isinstance(value,(int,float)) and socket.type=='RGBA':value=(value,value,value,1.)
            socket.default_value = value

    def math(self, op, a, b=0., name=None):
        n = self.node('ShaderNodeMath', name or op); n.operation = op
        self.plug(a,n.inputs[0]); self.plug(b,n.inputs[1]); return n.outputs[0]

    def vector(self, op, a, b, name=None):
        n = self.node('ShaderNodeVectorMath',name or op); n.operation = op
        self.plug(a,n.inputs[0]); self.plug(b,n.inputs[1]); return n.outputs[0]

    def mix(self, factor, a, b, name):
        n = self.node('ShaderNodeMixRGB',name)
        self.plug(factor,n.inputs[0]); self.plug(a,n.inputs[1]); self.plug(b,n.inputs[2])
        return n.outputs[0]


def socket(tree, name, kind='NodeSocketFloat', value=None, output=False):
    result = tree.interface.new_socket(name=name,in_out='OUTPUT' if output else 'INPUT',socket_type=kind)
    if value is not None: result.default_value = value
    return result


def cube_strip_uv_group():
    name='SR DirectX Cube Strip UV v1'
    tree=bpy.data.node_groups.get(name)
    if tree:return tree
    tree=bpy.data.node_groups.new(name,'ShaderNodeTree')
    socket(tree,'Direction','NodeSocketVector',(1,0,0))
    socket(tree,'Horizontal',value=0.)
    socket(tree,'Half Texel',value=0.)
    socket(tree,'UV','NodeSocketVector',output=True)
    g=Graph(tree);inp=g.node('NodeGroupInput','Direction');out=g.node('NodeGroupOutput','Atlas UV')
    separate=g.node('ShaderNodeSeparateXYZ','Cube Direction');g.plug(inp.outputs['Direction'],separate.inputs[0])
    x,y,z=[separate.outputs[k] for k in ('X','Y','Z')]
    ax,ay,az=[g.math('MAXIMUM',g.math('ABSOLUTE',v),1e-8) for v in (x,y,z)]
    nx,ny,nz=[g.math('LESS_THAN',v,0.) for v in (x,y,z)]
    neg=lambda v:g.math('MULTIPLY',v,-1.)
    div=lambda a,b:g.math('DIVIDE',a,b)
    choose=lambda f,a,b,name:g.mix(f,a,b,name)
    ux=choose(nx,div(neg(z),ax),div(z,ax),'X face U')
    tx=div(neg(y),ax)
    uy=div(x,ay);ty=choose(ny,div(z,ay),div(neg(z),ay),'Y face T')
    uz=choose(nz,div(x,az),div(neg(x),az),'Z face U');tz=div(neg(y),az)
    use_x=g.math('MULTIPLY',g.math('SUBTRACT',1.,g.math('LESS_THAN',ax,ay)),g.math('SUBTRACT',1.,g.math('LESS_THAN',ax,az)))
    use_y=g.math('SUBTRACT',1.,g.math('LESS_THAN',ay,az))
    u=choose(use_x,choose(use_y,uz,uy,'YZ U'),ux,'Major-axis U')
    t=choose(use_x,choose(use_y,tz,ty,'YZ T'),tx,'Major-axis T')
    face=choose(use_x,choose(use_y,g.math('ADD',4.,nz),g.math('ADD',2.,ny),'YZ face'),nx,'Major-axis face')
    # Math nodes accept the grayscale outputs of the selection nodes.
    u=g.math('MULTIPLY',g.math('ADD',u,1.),.5)
    v=g.math('MULTIPLY',g.math('SUBTRACT',1.,t),.5)
    high=g.math('SUBTRACT',1.,inp.outputs['Half Texel'])
    u=g.math('MINIMUM',g.math('MAXIMUM',u,inp.outputs['Half Texel']),high)
    v=g.math('MINIMUM',g.math('MAXIMUM',v,inp.outputs['Half Texel']),high)
    horizontal_u=div(g.math('ADD',face,u),6.)
    vertical_v=div(g.math('ADD',g.math('SUBTRACT',5.,face),v),6.)
    uv=g.node('ShaderNodeCombineXYZ','Strip UV')
    g.plug(choose(inp.outputs['Horizontal'],u,horizontal_u,'Atlas U'),uv.inputs['X'])
    g.plug(choose(inp.outputs['Horizontal'],vertical_v,v,'Atlas V'),uv.inputs['Y'])
    g.plug(uv.outputs[0],out.inputs['UV'])
    return tree


def ensure_environment_sampling(material,image,use_normal):
    nodes=material.node_tree.nodes;links=material.node_tree.links
    tex=next((n for n in nodes if n.get('drs_texture_id')==0x656e7674),None)
    if tex is None:return
    def get(kind,name):return nodes.get(name) or nodes.new(kind)
    geometry=get('ShaderNodeNewGeometry','SR Environment Geometry');geometry.name='SR Environment Geometry'
    incoming=get('ShaderNodeVectorMath','SR Environment Incident');incoming.name='SR Environment Incident';incoming.operation='SCALE';incoming.inputs['Scale'].default_value=-1.
    links.new(geometry.outputs['Incoming'],incoming.inputs[0])
    normal=get('ShaderNodeNormalMap','SR Environment Normal');normal.name='SR Environment Normal';normal.inputs['Strength'].default_value=float(use_normal)
    normal_tex=next((n for n in nodes if n.get('drs_texture_id')==0x6e726d73),None)
    if normal_tex:links.new(normal_tex.outputs['Color'],normal.inputs['Color'])
    reflect=get('ShaderNodeVectorMath','SR Environment Reflection');reflect.name='SR Environment Reflection';reflect.operation='REFLECT'
    links.new(incoming.outputs[0],reflect.inputs[0]);links.new(normal.outputs['Normal'],reflect.inputs[1])
    uv=get('ShaderNodeGroup','SR Environment Cube UV');uv.name='SR Environment Cube UV';uv.node_tree=cube_strip_uv_group()
    links.new(reflect.outputs[0],uv.inputs['Direction'])
    width,height=image.size[:] if image else (1,6)
    uv.inputs['Horizontal'].default_value=float(width>=height)
    uv.inputs['Half Texel'].default_value=.5/max(1,min(width,height))
    links.new(uv.outputs['UV'],tex.inputs['Vector']);tex.extension='EXTEND'
    for n in (geometry,incoming,normal,reflect,uv):n.hide=not material.drs_settings.technical_controls


def surface_group():
    name = 'SR DRS Material Switch v8'
    tree = bpy.data.node_groups.get(name)
    if tree is not None: return tree
    tree = bpy.data.node_groups.new(name,'ShaderNodeTree'); tree[MARKER] = VERSION
    colors = {'Color Map':(.8,.8,.8,1.), 'Parameter Map':(0.,0.,0.,0.),
        'Normal Map':(.5,.5,1.,1.), 'Fluid Color':(0.,0.,0.,1.),
        'Refraction Map':(.5,.5,0.,0.), 'Refraction Color':(1.,1.,1.,1.),
        'Separate Metallic':(0.,0.,0.,1.), 'Separate Roughness':(1.,1.,1.,1.),
        'Separate Mask':(0.,0.,0.,1.), 'Separate Emission':(0.,0.,0.,1.)}
    colors['Environment Color']=(0.,0.,0.,1.)
    colors['Tint Color']=(1.,1.,1.,1.)
    colors['Masked Color']=(1.,1.,1.,1.)
    colors['Vertex Color']=(1.,1.,1.,1.)
    colors['Volume Color']=(.6,.7,.8,1.)
    for key,value in colors.items(): socket(tree,key,'NodeSocketColor',value)
    values = {'Color Alpha':1., 'Parameter Alpha':0., 'Fluid Alpha':1., 'Refraction Alpha':0.,
        'Use Parameter Map':0., 'Use Separate Maps':0., 'Use Normal Map':0., 'Use Flow':0.,
        'Use Environment Map':0.,
        'Use Refraction':0., 'Alpha Test':0., 'Alpha Cutoff':.5, 'Decal':0.,
        'Family':0., 'Smoothness':0., 'Metalness':0., 'Reflectivity':0., 'Emissivity':0.,
        'Specular Scale':1.5, 'Saturation':1., 'Scratch':0., 'Scratch Alpha':1.,
        'Refraction Scale':1., 'Preview IOR':1.03, 'Separate Mode':0.}
    values['Volume Density']=0.
    values['Volume Emission']=0.
    values['Use Masked Color']=0.
    values['Use Texture Alpha']=0.
    values['Texture Alpha Factor']=1.
    values['Use Vertex Color']=0.
    values['Vertex Alpha']=1.
    for key in ('Roughness','Metallic','Mask','Emission'):
        values['Separate '+key+' Present']=0.
    for key,value in values.items(): socket(tree,key,value=value)
    for key in ('Surface',): socket(tree,key,'NodeSocketShader',output=True)
    socket(tree,'Volume','NodeSocketShader',output=True)
    socket(tree,'Screen Refraction UV','NodeSocketVector',output=True)
    socket(tree,'Screen Refraction Contribution','NodeSocketColor',output=True)
    socket(tree,'Screen Refraction Enabled',value=0.)
    for key in ('Metallic','Roughness','Emission','Flu Mask'):
        socket(tree,key,output=True)
    g = Graph(tree); inp=g.node('NodeGroupInput','Engine Inputs'); out=g.node('NodeGroupOutput','Engine Outputs')
    p=inp.outputs
    split=g.node('ShaderNodeSeparateColor','Engine Parameter RGBA'); g.plug(p['Parameter Map'],split.inputs[0])
    rough_split=g.node('ShaderNodeSeparateColor','Separate Roughness R');g.plug(p['Separate Roughness'],rough_split.inputs[0])
    metal_split=g.node('ShaderNodeSeparateColor','Separate Metalness R');g.plug(p['Separate Metallic'],metal_split.inputs[0])
    mask_split=g.node('ShaderNodeSeparateColor','Separate Blue Mask R');g.plug(p['Separate Mask'],mask_split.inputs[0])
    emit_split=g.node('ShaderNodeSeparateColor','Separate Emissivity R');g.plug(p['Separate Emission'],emit_split.inputs[0])
    channels=[split.outputs['Red'],split.outputs['Green'],split.outputs['Blue'],p['Parameter Alpha']]
    separate=[g.math('SUBTRACT',1.,rough_split.outputs['Red']),metal_split.outputs['Red'],mask_split.outputs['Red'],emit_split.outputs['Red']]
    selected=[]
    for i,(key,source) in enumerate(zip(('Smoothness','Metalness','Reflectivity','Emissivity'),('Roughness','Metallic','Mask','Emission'))):
        use_separate=g.math('MULTIPLY',p['Use Separate Maps'],p['Separate '+source+' Present'])
        packed=g.mix(use_separate,channels[i],separate[i],key+' map source')
        selected.append(g.mix(p['Use Parameter Map'],p[key],packed,key+' scalar or map'))
    smooth,metal,blue,emission=selected
    mask=g.math('MULTIPLY',blue,p['Use Flow'],'Blue is flow mask in fluid permutation')
    color=g.mix(mask,p['Color Map'],p['Fluid Color'],'Engine fluid RGB blend')
    env_tint=g.node('ShaderNodeMixRGB','Engine environment metal tint');env_tint.blend_type='MULTIPLY'
    g.plug(1.,env_tint.inputs[0]);g.plug(color,env_tint.inputs[1]);g.plug(p['Environment Color'],env_tint.inputs[2])
    environment=g.mix(metal,p['Environment Color'],env_tint.outputs[0],'Engine environment metalness')
    reflection=g.math('MULTIPLY',g.math('MULTIPLY',blue,smooth),p['Use Environment Map'])
    color=g.mix(reflection,color,environment,'Engine environment RGB blend')
    tint=g.node('ShaderNodeMixRGB','Material tint preview');tint.blend_type='MULTIPLY'
    color_tint=g.mix(p['Use Vertex Color'],p['Tint Color'],p['Vertex Color'],'Material or vertex color')
    g.plug(1.,tint.inputs[0]);g.plug(color,tint.inputs[1]);g.plug(color_tint,tint.inputs[2]);color=tint.outputs[0]
    emission=g.mix(mask,emission,p['Fluid Alpha'],'Engine fluid emissivity blend')
    scratch=g.math('ADD',1.,g.math('MULTIPLY',p['Scratch'],g.math('SUBTRACT',p['Scratch Alpha'],1.)))
    multiply=g.node('ShaderNodeMixRGB','Scratch RGB factor');multiply.blend_type='MULTIPLY'
    g.plug(1.,multiply.inputs[0]);g.plug(color,multiply.inputs[1]);g.plug(scratch,multiply.inputs[2])
    saturation=g.node('ShaderNodeHueSaturation','Engine saturation control (Blender HSV preview)')
    g.plug(multiply.outputs[0],saturation.inputs['Color']);g.plug(p['Saturation'],saturation.inputs['Saturation'])
    normal=g.node('ShaderNodeNormalMap','Tangent Normal');g.plug(p['Normal Map'],normal.inputs['Color'])
    g.plug(p['Use Normal Map'],normal.inputs['Strength'])
    rough=g.math('SUBTRACT',1.,smooth,'Smoothness to Blender roughness approximation')
    bsdf=g.node('ShaderNodeBsdfPrincipled','DRS Shader')
    for key,value in (('Base Color',saturation.outputs[0]),('Metallic',metal),('Roughness',rough),
                      ('Normal',normal.outputs[0]),('Emission Color',color),('Emission Strength',emission)):
        g.plug(value,bsdf.inputs[key])
    spec=g.math('MULTIPLY',p['Specular Scale'],.3333333333)
    g.plug(spec,bsdf.inputs['Specular IOR Level'])
    reflection=g.math('MULTIPLY',g.math('MULTIPLY',blue,smooth),p['Use Environment Map'])
    bsdf.inputs['Coat Weight'].default_value=0.
    g.plug(rough,bsdf.inputs['Coat Roughness'])
    # MaskedColor PS0 computes specular alpha + (1-alpha)*MaskedColor.rgb.
    # The same factor colors diffuse once and specular twice.
    legacy_tint=g.mix(g.math('MULTIPLY',p['Use Masked Color'],g.math('SUBTRACT',1.,p['Parameter Alpha'])),
                      (1.,1.,1.,1.),p['Masked Color'],'Legacy specular alpha tint')
    tint_diff=g.node('ShaderNodeMixRGB','Legacy tinted diffuse');tint_diff.blend_type='MULTIPLY'
    g.plug(1.,tint_diff.inputs[0]);g.plug(color,tint_diff.inputs[1]);g.plug(legacy_tint,tint_diff.inputs[2])
    tint_spec=g.node('ShaderNodeMixRGB','Legacy tint squared');tint_spec.blend_type='MULTIPLY'
    g.plug(1.,tint_spec.inputs[0]);g.plug(legacy_tint,tint_spec.inputs[1]);g.plug(legacy_tint,tint_spec.inputs[2])
    spec_color=g.node('ShaderNodeMixRGB','Legacy tinted specular');spec_color.blend_type='MULTIPLY'
    g.plug(1.,spec_color.inputs[0]);g.plug(p['Parameter Map'],spec_color.inputs[1]);g.plug(tint_spec.outputs[0],spec_color.inputs[2])
    diffuse=g.node('ShaderNodeBsdfDiffuse','Legacy diffuse preview')
    g.plug(tint_diff.outputs[0],diffuse.inputs['Color']);g.plug(normal.outputs[0],diffuse.inputs['Normal'])
    glossy=g.node('ShaderNodeBsdfGlossy','Legacy colored specular preview')
    g.plug(spec_color.outputs[0],glossy.inputs['Color']);glossy.inputs['Roughness'].default_value=.4
    g.plug(normal.outputs[0],glossy.inputs['Normal'])
    legacy=g.node('ShaderNodeAddShader','Legacy diffuse plus RGB specular')
    g.plug(diffuse.outputs[0],legacy.inputs[0]);g.plug(glossy.outputs[0],legacy.inputs[1])
    family=g.node('ShaderNodeMixShader','Default or legacy specular family')
    g.plug(g.math('COMPARE',p['Family'],1.),family.inputs[0])
    g.plug(bsdf.outputs[0],family.inputs[1]);g.plug(legacy.outputs[0],family.inputs[2])
    unlit=g.node('ShaderNodeEmission','Unlit / sprite preview');g.plug(color,unlit.inputs['Color'])
    choose=g.node('ShaderNodeMixShader','Material family switch')
    g.plug(g.math('COMPARE',p['Family'],2.),choose.inputs[0])
    g.plug(family.outputs[0],choose.inputs[1]);g.plug(unlit.outputs[0],choose.inputs[2])
    # A real screen-color lookup cannot be implemented by a surface BSDF. Decode
    # the RG offsets, but route them through refraction normals for live preview.
    ref=g.node('ShaderNodeSeparateColor','Refraction RG displacement');g.plug(p['Refraction Map'],ref.inputs[0])
    combine=g.node('ShaderNodeCombineXYZ','Centered refraction vector')
    screen=g.node('ShaderNodeTexCoord','Screen refraction coordinates')
    screen_components=g.node('ShaderNodeSeparateXYZ','Screen UV');g.plug(screen.outputs['Window'],screen_components.inputs[0])
    screen_uv=g.node('ShaderNodeCombineXYZ','Engine screen lookup UV')
    screen_uv.inputs['Z'].default_value=1.  # Compositor Map UV uses B as coverage.
    for index,key in enumerate(('Red','Green')):
        offset=g.math('MULTIPLY',g.math('SUBTRACT',ref.outputs[key],.5),g.math('DIVIDE',p['Refraction Scale'],256.))
        g.plug(offset,combine.inputs[index])
        # D3D screen coordinates have downward Y; Blender compositor UV has upward Y.
        displacement=offset if index==0 else g.math('MULTIPLY',offset,-1.)
        g.plug(g.math('ADD',screen_components.outputs[index],displacement),screen_uv.inputs[index])
    combine.inputs['Z'].default_value=0.
    geometry=g.node('ShaderNodeNewGeometry','Refraction geometric normal')
    bump=g.node('ShaderNodeVectorMath','Refraction normal approximation');bump.operation='ADD'
    g.plug(geometry.outputs['Normal'],bump.inputs[0]);g.plug(combine.outputs[0],bump.inputs[1])
    glass=g.node('ShaderNodeBsdfRefraction','Ray-traced refraction preview')
    g.plug(p['Refraction Color'],glass.inputs['Color']);g.plug(p['Preview IOR'],glass.inputs['IOR'])
    g.plug(rough,glass.inputs['Roughness']);g.plug(bump.outputs[0],glass.inputs['Normal'])
    refract=g.node('ShaderNodeMixShader','Refraction path')
    g.plug(g.math('MULTIPLY',p['Use Refraction'],p['Refraction Alpha']),refract.inputs[0])
    g.plug(choose.outputs[0],refract.inputs[1]);g.plug(glass.outputs[0],refract.inputs[2])
    alpha_cut=g.math('GREATER_THAN',p['Color Alpha'],p['Alpha Cutoff'])
    alpha=g.mix(p['Alpha Test'],1.,alpha_cut,'Optional alpha test')
    alpha_factor=g.mix(p['Use Vertex Color'],p['Texture Alpha Factor'],p['Vertex Alpha'],'Material or vertex alpha')
    texture_alpha=g.math('MULTIPLY',p['Color Alpha'],alpha_factor)
    alpha=g.math('MULTIPLY',alpha,g.mix(p['Use Texture Alpha'],1.,texture_alpha,
                                      'Textured material alpha'),'Textured opacity')
    alpha=g.mix(p['Decal'],alpha,p['Color Alpha'],'Optional decal alpha')
    transparent=g.node('ShaderNodeBsdfTransparent','Cutout transparent')
    final=g.node('ShaderNodeMixShader','Alpha output');g.plug(alpha,final.inputs[0])
    g.plug(transparent.outputs[0],final.inputs[1]);g.plug(refract.outputs[0],final.inputs[2])
    volume_surface=g.node('ShaderNodeMixShader','Surface or volume material')
    g.plug(g.math('COMPARE',p['Family'],4.),volume_surface.inputs[0])
    g.plug(final.outputs[0],volume_surface.inputs[1]);g.plug(transparent.outputs[0],volume_surface.inputs[2])
    g.plug(volume_surface.outputs[0],out.inputs['Surface'])
    volume=g.node('ShaderNodeVolumePrincipled','Volumetric fog approximation')
    g.plug(p['Volume Color'],volume.inputs['Color']);g.plug(p['Volume Density'],volume.inputs['Density'])
    g.plug(p['Volume Color'],volume.inputs['Emission Color']);g.plug(p['Volume Emission'],volume.inputs['Emission Strength'])
    g.plug(volume.outputs[0],out.inputs['Volume'])
    contribution=g.mix(1.,(0,0,0,1),p['Refraction Color'],'Refraction filter')
    filter_node=g.node('ShaderNodeMixRGB','Refraction additive contribution');filter_node.blend_type='MULTIPLY'
    g.plug(1.,filter_node.inputs[0]);g.plug(contribution,filter_node.inputs[1])
    g.plug(g.math('MULTIPLY',p['Refraction Alpha'],p['Screen Refraction Enabled']),filter_node.inputs[2])
    g.plug(screen_uv.outputs[0],out.inputs['Screen Refraction UV'])
    g.plug(filter_node.outputs[0],out.inputs['Screen Refraction Contribution'])
    for name,value in (('Metallic',metal),('Roughness',rough),('Emission',emission),('Flu Mask',mask)):
        g.plug(value,out.inputs[name])
    return tree


def ensure_flow_image():
    name='SR Engine Flow Turbulence 32'
    image=bpy.data.images.get(name)
    # Packed images can have a lazily unloaded pixel buffer. The packed bytes
    # are sufficient; reloading them on every frame invalidates GPU resources.
    if image is not None and image.packed_file:
        if image.colorspace_settings.name!='Non-Color':image.colorspace_settings.name='Non-Color'
        return image
    path=Path(__file__).resolve().parents[1]/'resources'/'flow_turbulence.png'
    if image is None:
        image=bpy.data.images.load(str(path),check_existing=False)
        image.name=name
    elif not image.has_data:
        image.filepath=str(path)
        image.reload()
    if image.colorspace_settings.name!='Non-Color':image.colorspace_settings.name='Non-Color'
    if not image.packed_file:image.pack()
    return image


def flow_group():
    name='SR Default Fluid Coordinates v5'
    tree=bpy.data.node_groups.get(name)
    if tree:return tree
    tree=bpy.data.node_groups.new(name,'ShaderNodeTree');tree[MARKER]=VERSION
    tree['_sr_flow_rest_position']=True
    socket(tree,'Scale','NodeSocketVector',(1.,1.,1.));socket(tree,'Offset','NodeSocketVector',(0.,0.,0.))
    socket(tree,'Lookup UV','NodeSocketVector',output=True)
    g=Graph(tree);inp=g.node('NodeGroupInput','Flow controls');out=g.node('NodeGroupOutput','Fluid strip UV')
    # Skinned VS40 forwards v0.xyz for fluid lookup, while r2 contains the
    # skinned position used for geometry. Armature deformation must not advect
    # the fluid volume through the surface.
    coord=g.node('ShaderNodeAttribute','Unnormalized rest position');coord.attribute_name='rest_position'
    split=g.node('ShaderNodeSeparateXYZ','Position components');g.plug(coord.outputs['Vector'],split.inputs[0])
    combine=g.node('ShaderNodeCombineXYZ','Engine position shear')
    axes=('X','Y','Z')
    for i,axis in enumerate(axes):
        shear=g.math('DIVIDE',g.math('ADD',split.outputs[axes[(i+1)%3]],split.outputs[axes[(i+2)%3]]),32.)
        g.plug(g.math('ADD',split.outputs[axis],shear),combine.inputs[axis])
    position=g.vector('MULTIPLY',combine.outputs[0],inp.outputs['Scale'])
    position=g.vector('ADD',position,inp.outputs['Offset'])
    # Flat atlas UVs jump at every Z slice. Blender's linear image sampler
    # always enables mipmaps/anisotropy, so those artificial derivatives bleed
    # unrelated slices into each other. Fetch texel centers without mipmaps
    # and perform the engine's wrapped trilinear interpolation explicitly.
    image=ensure_flow_image();octaves=[]
    for scale in (1.,2.,4.):
        scaled=g.vector('MULTIPLY',position,(scale,scale,scale))
        split=g.node('ShaderNodeSeparateXYZ',f'Volume coordinates {scale:g}');g.plug(scaled,split.inputs[0])
        indices=[];weights=[]
        for axis in ('X','Y','Z'):
            coordinate=g.math('SUBTRACT',g.math('MULTIPLY',g.math('FRACT',split.outputs[axis]),32.),.5)
            indices.append(g.math('FLOOR',coordinate));weights.append(g.math('FRACT',coordinate))
        slices=[]
        for dz in (0.,1.):
            layer=g.math('FLOORED_MODULO',g.math('ADD',indices[2],dz),32.)
            rows=[]
            for dy in (0.,1.):
                iy=g.math('FLOORED_MODULO',g.math('ADD',indices[1],dy),32.)
                samples=[]
                for dx in (0.,1.):
                    ix=g.math('FLOORED_MODULO',g.math('ADD',indices[0],dx),32.)
                    uv=g.node('ShaderNodeCombineXYZ',f'Volume texel {scale:g} / {dx:g}{dy:g}{dz:g}')
                    g.plug(g.math('DIVIDE',g.math('ADD',g.math('MULTIPLY',layer,34.),g.math('ADD',ix,1.5)),1088.),uv.inputs['X'])
                    g.plug(g.math('DIVIDE',g.math('ADD',iy,1.5),34.),uv.inputs['Y'])
                    tex=g.node('ShaderNodeTexImage',f'Engine volume texel {scale:g} / {dx:g}{dy:g}{dz:g}')
                    tex.image=image;tex.interpolation='Closest';tex.extension='EXTEND';g.plug(uv.outputs[0],tex.inputs['Vector'])
                    samples.append(tex.outputs['Color'])
                rows.append(g.mix(weights[0],samples[0],samples[1],f'Volume X interpolation {scale:g} / {dy:g}{dz:g}'))
            slices.append(g.mix(weights[1],rows[0],rows[1],f'Volume Y interpolation {scale:g} / {dz:g}'))
        octaves.append(g.mix(weights[2],slices[0],slices[1],f'Volume Z interpolation {scale:g}'))
    value=g.math('ADD',octaves[0],g.math('MULTIPLY',octaves[1],.5))
    value=g.math('ADD',value,g.math('MULTIPLY',octaves[2],.25))
    value=g.math('MULTIPLY',value,4./7.,'Engine weights 1 + 1/2 + 1/4')
    uv=g.node('ShaderNodeCombineXYZ','Fluid lookup (u, 0.5)');g.plug(value,uv.inputs['X']);uv.inputs['Y'].default_value=.5
    g.plug(uv.outputs[0],out.inputs['Lookup UV'])
    return tree


TEXTURE_LABELS={0x64666673:'Color Map (_col)',0x7370636c:'Parameter Map (_par)',
    0x6e726d73:'Normal Map (_nor)',0x7263636f:'Refraction Map (_ref)',
    0x63737432:'Flu Map Layer 1',0x63737431:'Scratch Map (_scr)',0x656e7674:'Environment Map (_env)'}


def build_material(material):
    """Build a versioned graph without deleting any shared old group datablock."""
    material.use_nodes=True;material[MARKER]=VERSION
    material.node_tree.nodes.clear();g=Graph(material.node_tree)
    # Ordinary group nodes survive opening a blend without the add-on. The
    # material enum is shown in both the DRS sidebar and Shader Editor sidebar.
    group=g.node('ShaderNodeGroup','DRS_Engine_Group');group.label='AIO DRS Engine'
    group.node_tree=surface_group();group.width=290;group.location=(0,300)
    flow=g.node('ShaderNodeGroup','DRS_Flow_Coordinates');flow.node_tree=flow_group();flow.location=(-900,-500)
    mapping={0x64666673:('Color Map','Color Alpha'),0x7370636c:('Parameter Map','Parameter Alpha'),
        0x6e726d73:('Normal Map',None),0x7263636f:('Refraction Map','Refraction Alpha'),
        0x63737432:('Fluid Color','Fluid Alpha'),0x63737431:(None,'Scratch Alpha')}
    textures={}
    for index,(identifier,label) in enumerate(TEXTURE_LABELS.items()):
        n=g.node('ShaderNodeTexImage',label);n.label=label;n['drs_texture_id']=identifier
        n.location=(-620,(3-index)*260);n.extension='REPEAT';textures[identifier]=n
        if identifier in mapping:
            color,alpha=mapping[identifier]
            if color:g.plug(n.outputs['Color'],group.inputs[color])
            if alpha:g.plug(n.outputs['Alpha'],group.inputs[alpha])
        if identifier==0x63737432:g.plug(flow.outputs['Lookup UV'],n.inputs['Vector'])
    for index,key in enumerate(('Metallic','Roughness','Mask','Emission')):
        n=g.node('ShaderNodeTexImage','Separate '+key);n.label='Separate '+key
        n.location=(-620,-2100-index*260);g.plug(n.outputs['Color'],group.inputs['Separate '+key])
    ref=g.node('ShaderNodeRGB','Refraction Color');ref.outputs[0].default_value=(1.,1.,1.,1.)
    g.plug(ref.outputs[0],group.inputs['Refraction Color']);ref.location=(-300,-1500)
    out=g.node('ShaderNodeOutputMaterial','Material Output');out.location=(500,300)
    g.plug(group.outputs['Surface'],out.inputs['Surface'])
    g.plug(group.outputs['Volume'],out.inputs['Volume'])
    for name,output in (('SR Refraction UV','Screen Refraction UV'),('SR Refraction Contribution','Screen Refraction Contribution')):
        aov=g.node('ShaderNodeOutputAOV',name);aov.aov_name=name
        g.plug(group.outputs[output],aov.inputs['Color'])
    material.surface_render_method='DITHERED'
    material.use_backface_culling=True
    return group,textures
