"""Owned camera-render passes for Default FX mesh screen-color lookup.

Opaque data proxies carry UV/filter/fade without stochastic transparency.
Color geometry stays smoothly blended; the viewport retains its BSDF fallback.
The frontmost data surface wins; sequential overlapping refractions and the
engine's B-channel sampler mip bias are not reproduced by this compositor.
"""
import json
import bpy
from bpy.app.handlers import persistent

TAG='_sr_fx_refraction'
OWNER='_sr_fx_preview'
RENDER='_sr_fx_refraction_render'
UV='SR FX Refraction UV'
FILTER='SR FX Refraction Filter'
STATES={}


def _collection(parent,name):
    collection=bpy.data.collections.new(name);collection[OWNER]=True
    parent.children.link(collection)
    return collection


def _mapped_socket(socket,tree):
    node=tree.nodes[socket.node.name]
    sockets=node.outputs if socket.is_output else node.inputs
    original=socket.node.outputs if socket.is_output else socket.node.inputs
    return sockets[list(original).index(socket)]


def prepare(session,visual):
    from sr_impex.blender.editors.material_editor import handler_id,refraction_preview_enabled
    from sr_impex.utilities.material_schema import DEFAULT_ID,REF_ID
    meshes=[obj for obj in visual.obj.children if obj.type=='MESH']
    for obj in meshes:
        candidates=[]
        for material in obj.data.materials:
            if not material or handler_id(material.drs_settings)!=DEFAULT_ID:continue
            settings=material.drs_settings
            if not refraction_preview_enabled(settings):continue
            if not any(int(row.identifier,0)==REF_ID and row.enabled and row.image for row in settings.textures):continue
            group=material.node_tree.nodes.get('DRS_Engine_Group')
            if group and group.outputs.get('Screen Refraction UV'):candidates.append(material)
        if not candidates:continue
        # A per-object proxy can retain separate material slots and deformation.
        if not hasattr(session,'refraction_originals'):
            session.refraction_originals=_collection(session.collection,'FX Refraction Color')
            session.refraction_proxies=_collection(session.collection,'FX Refraction Data')
            session.refraction_records=[]
        for parent in list(obj.users_collection):parent.objects.unlink(obj)
        session.refraction_originals.objects.link(obj)
        proxy=obj.copy();proxy.name='FX Refraction Data '+obj.name;proxy[OWNER]=True;proxy['_sr_fx_refraction_data']=True
        proxy.hide_viewport=True;proxy.hide_render=False;proxy.hide_select=True
        session.refraction_proxies.objects.link(proxy)
        for index,material in enumerate(obj.data.materials):
            if material is None:continue
            proxy.material_slots[index].link='OBJECT'
            data=material.copy();data.name='FX Refraction Data '+material.name;data[OWNER]=True
            proxy.material_slots[index].material=data
            tree=data.node_tree;n=tree.nodes;l=tree.links
            output=next(node for node in n if node.type=='OUTPUT_MATERIAL' and node.is_active_output)
            for socket in output.inputs:
                for link in list(socket.links):l.remove(link)
            emission=n.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(0,0,0,1)
            l.new(emission.outputs[0],output.inputs['Surface'])
            data.surface_render_method='DITHERED'
            if material not in candidates:continue  # Opaque zero-data occluder.
            material[TAG]=True
            group=n['DRS_Engine_Group']
            aov=n.new('ShaderNodeOutputAOV');aov.aov_name=UV
            l.new(group.outputs['Screen Refraction UV'],aov.inputs['Color'])
            weight=n.new('ShaderNodeMixRGB');weight.blend_type='MULTIPLY';weight.inputs[0].default_value=1.
            l.new(group.outputs['Screen Refraction Contribution'],weight.inputs[1])
            # A copied FX fade socket has no output. Give it a uniform node;
            # append it to the existing material-curve binding update below.
            opacity=n.new('ShaderNodeValue');opacity.name='FX Refraction Fade';opacity.outputs[0].default_value=1.
            l.new(opacity.outputs[0],weight.inputs[2])
            aov=n.new('ShaderNodeOutputAOV');aov.aov_name=FILTER;l.new(weight.outputs[0],aov.inputs['Color'])
            for alpha,curves in list(visual.material_bindings):
                if alpha.id_data!=material.node_tree:continue
                visual.material_bindings.append((opacity.outputs[0],
                    [(_mapped_socket(socket,tree),tracks) for socket,tracks in curves]))
            # Cutout coverage remains binary and independent of the FX fade.
            less=n.new('ShaderNodeMath');less.operation='GREATER_THAN'
            if group.inputs['Color Alpha'].is_linked:l.new(group.inputs['Color Alpha'].links[0].from_socket,less.inputs[0])
            else:less.inputs[0].default_value=group.inputs['Color Alpha'].default_value
            less.inputs[1].default_value=group.inputs['Alpha Cutoff'].default_value
            coverage=n.new('ShaderNodeMixRGB');coverage.inputs[1].default_value=(1,1,1,1)
            coverage.inputs[0].default_value=group.inputs['Alpha Test'].default_value;l.new(less.outputs[0],coverage.inputs[2])
            present=n.new('ShaderNodeMath');present.operation='GREATER_THAN';present.inputs[1].default_value=1e-6
            l.new(opacity.outputs[0],present.inputs[0])
            visible=n.new('ShaderNodeMath');visible.operation='MULTIPLY'
            l.new(present.outputs[0],visible.inputs[0]);l.new(coverage.outputs[0],visible.inputs[1])
            transparent=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader')
            l.new(visible.outputs[0],mix.inputs[0]);l.new(transparent.outputs[0],mix.inputs[1]);l.new(emission.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],output.inputs['Surface'])
            session.refraction_records.append((obj,proxy,material,data))
        visual.refraction_proxies=getattr(visual,'refraction_proxies',[])+[proxy]


def _layers(collection):
    yield collection
    for child in collection.children:yield from _layers(child)


def _exclude(layer,collection,changes):
    for branch in _layers(layer.layer_collection):
        if branch.collection==collection and not branch.exclude:
            changes.append((layer.name,collection.name,False));branch.exclude=True


def enable(scene,sessions):
    clear(scene)
    sessions=[s for s in sessions if s.scene==scene and getattr(s,'refraction_records',None)]
    if not sessions:return
    if bpy.app.version<(5,0,0):
        for s in sessions:s.warn('FX screen refraction camera renders require Blender 5')
        return
    previous=scene.compositing_node_group
    tree=previous.copy() if previous else bpy.data.node_groups.new(scene.name+' FX Refraction','CompositorNodeTree')
    tree[TAG]=True;tree['_previous_group']=previous.name if previous else ''
    tree['_scene_name']=scene.name;tree['_previous_compositing']=scene.render.use_compositing
    state={'tree':tree,'layers':[],'changes':[],'sessions':sessions,'render_values':[]}
    STATES[scene.as_pointer()]=state
    try:
        main=scene.view_layers[0]
        background=scene.view_layers.new('FX Refraction Background');state['layers'].append(background.name)
        data=scene.view_layers.new('FX Refraction Data');state['layers'].append(data.name)
        for name in (UV,FILTER):aov=data.aovs.add();aov.name=name;aov.type='COLOR'
        for session in sessions:
            _exclude(background,session.refraction_originals,state['changes'])
            _exclude(data,session.refraction_originals,state['changes'])
            for layer in scene.view_layers:
                if layer!=data:_exclude(layer,session.refraction_proxies,state['changes'])
        n=tree.nodes;l=tree.links
        if previous:
            reference=n.new('CompositorNodeGroup');reference.node_tree=previous
            reference.name='Preserved compositor before FX refraction';reference.hide=True
        if previous is None:
            tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
            output=n.new('NodeGroupOutput');front=n.new('CompositorNodeRLayers');front.scene=scene;front.layer=main.name
            l.new(front.outputs['Image'],output.inputs['Image'])
        sources=[node for node in n if node.type=='R_LAYERS' and
                 (node.scene is None or node.scene==scene) and node.layer in ('',main.name) and node.outputs['Image'].is_linked]
        if not sources:raise ValueError('The artist compositor has no main scene Image input to extend')
        back=n.new('CompositorNodeRLayers');back.scene=scene;back.layer=background.name;back.name='FX Refraction Background'
        vectors=n.new('CompositorNodeRLayers');vectors.scene=scene;vectors.layer=data.name;vectors.name='FX Refraction Data'
        lookup=n.new('CompositorNodeMapUV');lookup.name='FX Screen Color Lookup'
        l.new(back.outputs['Image'],lookup.inputs['Image']);l.new(vectors.outputs[UV],lookup.inputs['UV'])
        contribution=n.new('ShaderNodeMix');contribution.data_type='RGBA';contribution.blend_type='MULTIPLY';contribution.inputs[0].default_value=1.
        l.new(lookup.outputs['Image'],contribution.inputs[6]);l.new(vectors.outputs[FILTER],contribution.inputs[7])
        for source in sources:
            targets=[link.to_socket for link in source.outputs['Image'].links]
            add=n.new('ShaderNodeMix');add.data_type='RGBA';add.blend_type='ADD';add.inputs[0].default_value=1.
            l.new(source.outputs['Image'],add.inputs[6]);l.new(contribution.outputs[2],add.inputs[7])
            alpha=n.new('CompositorNodeSetAlpha')
            alpha.inputs['Type'].default_value='Replace Alpha'
            l.new(add.outputs[2],alpha.inputs['Image']);l.new(source.outputs['Alpha'],alpha.inputs['Alpha'])
            for target in targets:l.new(alpha.outputs['Image'],target)
        tree['_layers']=json.dumps(state['layers']);tree['_changes']=json.dumps(state['changes'])
        scene.compositing_node_group=tree;scene.render.use_compositing=True
        for session in sessions:
            session.screen_refraction=True
            for obj,proxy,_,_ in session.refraction_records:proxy.hide_render=obj.hide_render
            session.warn('FX mesh screen refraction is composited in camera renders; viewport uses BSDF fallback. Frontmost distortion only; sampler mip bias and engine lighting differ')
    except Exception as exc:
        clear(scene)
        for session in sessions:session.warn(f'FX screen refraction setup failed; compositor preserved: {exc}')


@persistent
def render_pre(scene,*args):
    state=STATES.get(scene.as_pointer())
    if not state or scene.compositing_node_group!=state['tree'] or not scene.render.use_compositing:return
    scene[RENDER]=True
    for session in state['sessions']:
        for _,_,material,_ in session.refraction_records:
            if any(row[0]==material for row in state['render_values']):continue
            group=material.node_tree.nodes.get('DRS_Engine_Group')
            state['render_values'].append((material,group.inputs['Use Refraction'].default_value,
                material.surface_render_method,material.use_transparency_overlap))
            group.inputs['Use Refraction'].default_value=0.
            material.surface_render_method='BLENDED';material.use_transparency_overlap=True


@persistent
def render_post(scene,*args):
    state=STATES.get(scene.as_pointer())
    if RENDER in scene:del scene[RENDER]
    if not state:return
    for material,value,method,overlap in state['render_values']:
        try:
            group=material.node_tree.nodes.get('DRS_Engine_Group');group.inputs['Use Refraction'].default_value=value
            material.surface_render_method=method;material.use_transparency_overlap=overlap
        except ReferenceError:pass
    state['render_values'].clear()


def clear(scene):
    render_post(scene)
    state=STATES.pop(scene.as_pointer(),None)
    for obj in scene.objects:
        if obj.get('_sr_fx_refraction_data'):obj.hide_render=True
    if state:
        for session in state['sessions']:
            session.screen_refraction=False
            for _,proxy,_,_ in session.refraction_records:
                try:proxy.hide_render=True
                except ReferenceError:pass
    trees=[tree for tree in bpy.data.node_groups if tree.get(TAG) and tree.get('_scene_name')==scene.name]
    if state and state['tree'] not in trees:trees.append(state['tree'])
    for tree in trees:
        if scene.compositing_node_group==tree:
            scene.compositing_node_group=bpy.data.node_groups.get(tree.get('_previous_group',''))
            scene.render.use_compositing=bool(tree.get('_previous_compositing',True))
        for layer_name,collection_name,value in json.loads(tree.get('_changes','[]')):
            layer=scene.view_layers.get(layer_name)
            if layer:
                for branch in _layers(layer.layer_collection):
                    if branch.collection.name==collection_name:branch.exclude=value
        for name in json.loads(tree.get('_layers','[]')):
            layer=scene.view_layers.get(name)
            if layer:scene.view_layers.remove(layer)
        if tree.users==0:bpy.data.node_groups.remove(tree)
    if state: # Also cover a partially failed setup before metadata was saved.
        for layer_name,collection_name,value in state['changes']:
            layer=scene.view_layers.get(layer_name)
            if layer:
                for branch in _layers(layer.layer_collection):
                    if branch.collection.name==collection_name:branch.exclude=value
        for name in state['layers']:
            layer=scene.view_layers.get(name)
            if layer:scene.view_layers.remove(layer)


def register():
    for handlers,callback in ((bpy.app.handlers.render_pre,render_pre),
                              (bpy.app.handlers.render_post,render_post),
                              (bpy.app.handlers.render_cancel,render_post),
                              (bpy.app.handlers.load_post,load_post)):
        if callback not in handlers:handlers.append(callback)


def unregister():
    for scene in bpy.data.scenes:clear(scene)
    for handlers,callback in ((bpy.app.handlers.render_pre,render_pre),
                              (bpy.app.handlers.render_post,render_post),
                              (bpy.app.handlers.render_cancel,render_post),
                              (bpy.app.handlers.load_post,load_post)):
        if callback in handlers:handlers.remove(callback)


@persistent
def load_post(*args):
    STATES.clear()
    for scene in bpy.data.scenes:clear(scene)
