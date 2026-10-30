"""Separate FX glow AOV and nondestructive Blender 5 compositor preview.

Track 59 and SFP particle glow feed a dedicated pass. Fog Glow is an explicit
kernel/calibration substitute; it is not the game's glow implementation.
"""
import json
import bpy
from sr_impex.utilities.effect_tracks import components

TAG='_sr_fx_glow';AOV='SR FX Glow'


def prepare_visual(session,item):
    if item.kind not in ('Billboard','Trail','SfpEmitter'):return
    if getattr(item,'_smooth_particles',False):return  # This emitter produces no particle glow.
    source=item.system[1] if item.kind=='SfpEmitter' and item.system else item.tracks
    if not any(abs(float(components(key.data)))>1e-6 for track in source.groups.get(59,[]) for key in track.entries):return
    tree=item.geometry.data.materials[0].node_tree;n=tree.nodes;l=tree.links
    out=n.new('ShaderNodeOutputAOV');out.aov_name=AOV
    color=n.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1.
    l.new(item.shader.outputs[0],color.inputs[1])
    strength=n.new('ShaderNodeMath');strength.operation='MULTIPLY';strength.inputs[1].default_value=0.
    l.new(item.alpha.outputs[0],strength.inputs[0])
    if item.kind=='SfpEmitter':
        attr=n.new('ShaderNodeAttribute');attr.attribute_name='FX Emissive'
        particle=n.new('ShaderNodeMath');particle.operation='MULTIPLY'
        l.new(strength.outputs[0],particle.inputs[0]);l.new(attr.outputs['Alpha'],particle.inputs[1])
        l.new(particle.outputs[0],color.inputs[2])
    else:l.new(strength.outputs[0],color.inputs[2])
    l.new(color.outputs[0],out.inputs['Color'])
    item.glow_uniform=strength.inputs[1]
    session.has_glow=True


def enable(session):
    if bpy.app.version<(5,0,0):return _enable(session)
    scene=session.scene;previous=scene.compositing_node_group
    compositing=scene.render.use_compositing;groups=set(bpy.data.node_groups)
    aovs={layer.name:{a.name for a in layer.aovs} for layer in scene.view_layers}
    try:_enable(session)
    except Exception as exc:
        scene.compositing_node_group=previous;scene.render.use_compositing=compositing
        for tree in list(bpy.data.node_groups):
            if tree not in groups and tree.get(TAG) and tree.users==0:bpy.data.node_groups.remove(tree)
        for layer in scene.view_layers:
            if AOV in layer.aovs and AOV not in aovs.get(layer.name,set()):layer.aovs.remove(layer.aovs[AOV])
        session.warn(f'Glow compositor setup failed; original compositor preserved: {exc}')


def _enable(session):
    scene=session.scene
    if not session.has_glow:return
    if bpy.app.version<(5,0,0):
        session.warn('Automatic FX glow compositing requires Blender 5');return
    previous=scene.compositing_node_group
    if previous and previous.get(TAG):return
    tree=previous.copy() if previous else bpy.data.node_groups.new(scene.name+' FX Glow','CompositorNodeTree')
    tree[TAG]=True;tree['_previous_group']=previous.name if previous else ''
    tree['_scene_name']=scene.name
    tree['_previous_compositing']=scene.render.use_compositing
    if previous:
        reference=tree.nodes.new('CompositorNodeGroup');reference.node_tree=previous
        reference.name='Preserved original compositor';reference.hide=True
    else:tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    n=tree.nodes;l=tree.links
    output=next((node for node in n if node.type=='GROUP_OUTPUT' and node.is_active_output),None) or n.new('NodeGroupOutput')
    socket=output.inputs.get('Image')
    if socket is None:
        bpy.data.node_groups.remove(tree);session.warn('FX glow could not locate the compositor Image output');return
    created=[]
    for layer in scene.view_layers:
        if AOV not in layer.aovs:
            aov=layer.aovs.add();aov.name=AOV;aov.type='COLOR';created.append(layer.name)
    tree['_created_aovs']=json.dumps(created)
    render=n.new('CompositorNodeRLayers');render.scene=scene;render.layer=scene.view_layers[0].name
    original=socket.links[0].from_socket if socket.is_linked else render.outputs['Image']
    glow=n.new('CompositorNodeGlare');glow.inputs['Type'].default_value='Fog Glow'
    glow.inputs['Threshold'].default_value=0.;glow.inputs['Strength'].default_value=.25
    l.new(render.outputs[AOV],glow.inputs['Image'])
    add=n.new('ShaderNodeMix');add.data_type='RGBA';add.blend_type='ADD';add.inputs[0].default_value=1.
    l.new(original,add.inputs[6]);l.new(glow.outputs['Glare'],add.inputs[7]);l.new(add.outputs[2],socket)
    scene.compositing_node_group=tree;scene.render.use_compositing=True
    session.warn('Glow uses a separate AOV and Blender Fog Glow; engine kernel/lighting calibration differs')


def clear(scene):
    if bpy.app.version<(5,0,0):return
    active=scene.compositing_node_group
    def uses_aov(tree,seen=None):
        if tree is None:return False
        seen=set() if seen is None else seen
        if tree.as_pointer() in seen:return False
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type=='R_LAYERS' and AOV in node.outputs and node.outputs[AOV].is_linked:return True
            if node.type=='GROUP' and uses_aov(node.node_tree,seen):return True
        return False
    for tree in list(bpy.data.node_groups):
        if not tree.get(TAG) or (tree!=active and tree.get('_scene_name')!=scene.name):continue
        if tree==active:
            scene.compositing_node_group=bpy.data.node_groups.get(tree.get('_previous_group',''))
            if scene.render.use_compositing:scene.render.use_compositing=bool(tree.get('_previous_compositing',True))
        if tree==active or not uses_aov(scene.compositing_node_group):
            for name in json.loads(tree.get('_created_aovs','[]')):
                layer=scene.view_layers.get(name)
                if layer and AOV in layer.aovs:layer.aovs.remove(layer.aovs[AOV])
        if tree.users==0:bpy.data.node_groups.remove(tree)
