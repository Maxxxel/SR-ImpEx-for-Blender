"""An isolated, repeatable artist look-development scene; not game calibration."""
import math
import bpy
from mathutils import Vector
from bpy.types import Operator, Panel


def configure_screen_refraction(scene):
    """Camera preview of the traced Default screen-sample displacement/addition.

    Screen capture and light/fog matching remain Blender approximations. The
    refraction map B-channel sampler mip bias is not emulated by Map UV.
    """
    from sr_impex.blender.editors.material_editor import modern, handler_id, refraction_preview_enabled
    from sr_impex.utilities.material_schema import DEFAULT_ID, REF_ID
    refractors=[]
    for obj in scene.objects:
        material=obj.active_material if obj.type=='MESH' else None
        if modern(material) and handler_id(material.drs_settings)==DEFAULT_ID and refraction_preview_enabled(material.drs_settings):
            if any(int(row.identifier,0)==REF_ID and row.enabled and row.image for row in material.drs_settings.textures):refractors.append(obj)
    if not refractors:return False
    collection=scene.collection.children.get('Screen Refraction Surfaces')
    if collection is None:
        collection=bpy.data.collections.new('Screen Refraction Surfaces');scene.collection.children.link(collection)
    models=scene.collection.children.get('Artist Models')
    for obj in refractors:
        if obj.name not in collection.objects:collection.objects.link(obj)
        if models and obj.name in models.objects:models.objects.unlink(obj)
    surface=scene.view_layers[0]
    for name in ('SR Refraction UV','SR Refraction Contribution'):
        if name not in surface.aovs:
            aov=surface.aovs.add();aov.name=name;aov.type='COLOR'
    background=scene.view_layers.get('SR Refraction Background') or scene.view_layers.new('SR Refraction Background')
    background.layer_collection.children[collection.name].exclude=True
    if bpy.app.version >= (5,0,0):
        tree=bpy.data.node_groups.new(scene.name+' Screen Refraction','CompositorNodeTree')
        tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
        scene.compositing_node_group=tree
    else:
        scene.use_nodes=True
        tree=scene.node_tree
        tree.nodes.clear()
    scene.render.use_compositing=True
    nodes,links=tree.nodes,tree.links
    front=nodes.new('CompositorNodeRLayers');front.scene=scene;front.layer=surface.name;front.location=(-700,200)
    back=nodes.new('CompositorNodeRLayers');back.scene=scene;back.layer=background.name;back.location=(-700,-200)
    lookup=nodes.new('CompositorNodeMapUV');lookup.location=(-400,-150)
    links.new(back.outputs['Image'],lookup.inputs['Image']);links.new(front.outputs['SR Refraction UV'],lookup.inputs['UV'])
    tint=nodes.new('ShaderNodeMix');tint.data_type='RGBA';tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1.;tint.location=(-150,-150)
    links.new(lookup.outputs['Image'],tint.inputs[6]);links.new(front.outputs['SR Refraction Contribution'],tint.inputs[7])
    add=nodes.new('ShaderNodeMix');add.data_type='RGBA';add.blend_type='ADD';add.inputs[0].default_value=1.;add.location=(100,100)
    links.new(front.outputs['Image'],add.inputs[6]);links.new(tint.outputs[2],add.inputs[7])
    out=nodes.new('NodeGroupOutput' if bpy.app.version>=(5,0,0) else 'CompositorNodeComposite');out.location=(350,100);links.new(add.outputs[2],out.inputs['Image'])
    scene['_drs_screen_refraction']=True
    from sr_impex.blender.editors.material_editor import sync_material
    for obj in refractors:sync_material(obj.active_material,obj)
    return True


def make_preview_scene(objects, name='BattleForge Artist Preview',target_scene=None,stage_parent=None):
    objects=[o for o in objects if not o.name.startswith('_CS_')]
    meshes=[o for o in objects if o.type=='MESH']
    if not meshes:raise ValueError('Select at least one model mesh')
    scene=target_scene or bpy.data.scenes.new(name)
    scene['_drs_artist_preview']=True
    scene['preview_scope']='Approximate lighting/BSDF preview. Check final shading in Skylords Map Editor.'
    scene.render.engine='BLENDER_EEVEE' if bpy.app.version>=(5,0,0) else 'BLENDER_EEVEE_NEXT'
    scene.eevee.use_raytracing=True
    scene.render.resolution_x=1200;scene.render.resolution_y=850;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    if target_scene is None:
        scene.render.fps=30;scene.frame_start=1;scene.frame_end=240
    scene.view_settings.view_transform='Standard'
    scene.view_settings.look='None'
    scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    model=None
    if target_scene is None:
        model=bpy.data.collections.new('Artist Models');scene.collection.children.link(model)
    # Link the actual editable models; leave the source scene's lights, world,
    # camera, collections and rendering settings untouched.
    related=set(objects)
    for obj in objects:
        parent=obj.parent
        while parent:
            related.add(parent);parent=parent.parent
        for modifier in obj.modifiers:
            if modifier.type=='ARMATURE' and modifier.object:related.add(modifier.object)
    if model:
        for obj in related:model.objects.link(obj)
    stage=bpy.data.collections.new('Render' if stage_parent else 'Preview Stage (not exported)')
    (stage_parent or scene.collection).children.link(stage)
    stage['_sr_render_stage']=True
    points=[obj.matrix_world@Vector(corner) for obj in meshes for corner in obj.bound_box]
    lower=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    upper=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center=(lower+upper)*.5
    span=max((upper-lower).length,1.)
    def link_object(name,data,location):
        obj=bpy.data.objects.new(name,data);stage.objects.link(obj);obj.location=location;return obj
    mesh=bpy.data.meshes.new('Preview ground')
    r=span*4.
    mesh.from_pydata([(-r,-r,0),(r,-r,0),(r,r,0),(-r,r,0)],[],[(0,1,2,3)])
    ground=link_object('Preview ground',mesh,(center.x,center.y,lower.z-.025*span))
    material=bpy.data.materials.new('Preview terrain');material.use_nodes=True
    n=material.node_tree.nodes;p=next(n for n in n if n.type=='BSDF_PRINCIPLED')
    noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.8/span
    ramp=n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color=(.11,.14,.045,1.)
    ramp.color_ramp.elements[1].color=(.27,.25,.12,1.)
    material.node_tree.links.new(noise.outputs['Fac'],ramp.inputs['Fac'])
    material.node_tree.links.new(ramp.outputs['Color'],p.inputs['Base Color']);p.inputs['Roughness'].default_value=.9
    ground.data.materials.append(material)
    world=bpy.data.worlds.new('BattleForge Preview Sky');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.30,.42,.62,1.)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45
    scene.world=world
    sun_data=bpy.data.lights.new('Warm daylight','SUN');sun_data.energy=2.2
    sun_data.angle=math.radians(8);sun_data.color=(1.,.88,.72)
    sun=link_object('Warm daylight',sun_data,center+Vector((span,-span,span*2)))
    sun.rotation_euler=(math.radians(28),math.radians(-20),math.radians(-35))
    fill_data=bpy.data.lights.new('Preview sky fill','AREA');fill_data.energy=span*span*25.
    fill_data.shape='DISK';fill_data.size=span*2.;fill_data.color=(.64,.78,1.)
    fill=link_object('Preview sky fill',fill_data,center+Vector((-span,span,span*1.5)))
    fill.rotation_euler=(center-fill.location).to_track_quat('-Z','Y').to_euler()
    camera_data=bpy.data.cameras.new('BattleForge Preview Camera');camera_data.type='ORTHO';camera_data.ortho_scale=span*1.7
    camera=link_object('BattleForge Preview Camera',camera_data,center+Vector((1.3,-1.8,1.35))*span)
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.clip_end=span*30.;scene.camera=camera
    if target_scene is None:
        scene.frame_set(1)
        configure_screen_refraction(scene)
    return scene


def add_model_render(context):
    from sr_impex.utilities.artist_context import find_model
    root=find_model(context)
    if root is None:raise ValueError('Select a model mesh or its DRSModel collection')
    stage=next((c for c in root.children if c.get('_sr_render_stage')),None)
    if stage:
        camera=next((o for o in stage.objects if o.type=='CAMERA'),None)
        if camera:
            context.scene.camera=camera
            return stage
        raise ValueError('The model Render collection has no camera; undo its removal first')
    meshes=set()
    for collection in root.children_recursive:
        if collection.name.startswith(('Meshes_Collection','GroundDecal_Collection')):
            meshes.update(o for o in collection.all_objects if o.type=='MESH' and
                          not o.hide_render and o.visible_get(view_layer=context.view_layer))
    if not meshes:raise ValueError('The model has no visible render meshes')
    context.view_layer.update()
    make_preview_scene(list(meshes),target_scene=context.scene,stage_parent=root)
    return next(c for c in root.children if c.get('_sr_render_stage'))


class DRS_OT_AddRender(Operator):
    bl_idname='drs.add_render';bl_label='Add Render';bl_options={'REGISTER','UNDO'}
    bl_description='Add a camera, lights and ground for this whole model; reuse its render setup if one already exists'
    def execute(self,context):
        try:add_model_render(context)
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        if context.area and context.area.type=='VIEW_3D':
            space=context.area.spaces.active;space.shading.type='RENDERED'
            if space.region_3d:space.region_3d.view_perspective='CAMERA'
        return {'FINISHED'}


class DRS_OT_PreviewScene(Operator):
    bl_idname='drs.create_preview_scene';bl_label='Create BattleForge Preview Scene';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:
            scene=make_preview_scene([o for o in context.selected_objects if o.type in ('MESH','ARMATURE')])
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        if context.window:context.window.scene=scene
        return {'FINISHED'}


class DRS_OT_CurrentRenderedView(Operator):
    bl_idname='drs.current_rendered_view';bl_label='Rendered View (Current Scene)'
    bl_description='Use the current scene lights and world to inspect the model in rendered shading'
    def execute(self,context):
        area=context.area
        if not area or area.type!='VIEW_3D':
            self.report({'ERROR'},'Use this control in a 3D Viewport');return {'CANCELLED'}
        area.spaces.active.shading.type='RENDERED'
        return {'FINISHED'}


class DRS_PT_PreviewScene(Panel):
    bl_label='Render Setup';bl_category='DRS Editor';bl_order=10000;bl_space_type='VIEW_3D';bl_region_type='UI'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout
        layout.operator('drs.add_render',icon='RENDER_STILL')
        layout.label(text='Camera, lights and ground for the whole model.')
        layout.label(text='The game renderer remains the final visual check.')
        if context.scene.get('_drs_artist_preview'):
            material=getattr(context.object,'active_material',None) if context.object else None
            if material and hasattr(material,'drs_settings') and material.drs_settings.technical_controls:
                layout.operator('drs.screen_refraction_preview',text='Rebuild Refraction Diagnostic',icon='SHADING_RENDERED')
            layout.prop(context.scene.render,'engine')
            layout.prop(context.scene.view_settings,'exposure')


class DRS_OT_ScreenRefraction(Operator):
    bl_idname='drs.screen_refraction_preview';bl_label='Refresh Screen Refraction Preview';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        if not context.scene.get('_drs_artist_preview'):
            self.report({'ERROR'},'Create a BattleForge preview scene first');return {'CANCELLED'}
        if not configure_screen_refraction(context.scene):
            self.report({'WARNING'},'No Default material with an enabled refraction image was found');return {'CANCELLED'}
        return {'FINISHED'}


def register():
    for cls in (DRS_OT_PreviewScene,DRS_OT_ScreenRefraction,DRS_OT_CurrentRenderedView,DRS_OT_AddRender,DRS_PT_PreviewScene):bpy.utils.register_class(cls)


def unregister():
    for cls in (DRS_PT_PreviewScene,DRS_OT_AddRender,DRS_OT_CurrentRenderedView,DRS_OT_ScreenRefraction,DRS_OT_PreviewScene):bpy.utils.unregister_class(cls)
