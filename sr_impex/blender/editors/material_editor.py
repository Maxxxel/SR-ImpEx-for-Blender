"""Artist-facing, type-specific DRS material controls and loss-aware serialization."""
from io import BytesIO
import json
import time
from pathlib import Path
from struct import pack, unpack

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras.io_utils import ImportHelper

from sr_impex.blender.material_preview import MARKER, TEXTURE_LABELS, build_material
from sr_impex.utilities.material_schema import (catalog, schema, parameter_name, signed16,
    signed32, DEFAULT_ID, COLOR_ID, PARAM_ID, NORMAL_ID, REF_ID, FLUID_ID, ENV_ID, FLOW_IDS, flow_timeline,FlowSequence,
    preview_texture_routes, scalar_in_range)
from sr_impex.definitions.mesh_definitions import (Material, Materials, Textures, Texture,
    Refraction, Flow, EmptyString, LevelOfDetail)

_BUSY=set()
_FLOW_CACHE={}
_FLOW_CLOCKS={}
_FLOW_RENDERING=set()


def _flow_clock(scene):
    from sr_impex.utilities.flow_playback import PreviewClock
    token=(scene.frame_current,scene.frame_subframe)
    seconds=max(0.,scene.frame_current+scene.frame_subframe-scene.frame_start)/(scene.render.fps/scene.render.fps_base)
    key=scene.as_pointer()
    if key not in _FLOW_CLOCKS:_FLOW_CLOCKS[key]=PreviewClock(seconds,token,time.monotonic())
    return _FLOW_CLOCKS[key],seconds,token


def flow_seconds(scene):
    clock,seconds,token=_flow_clock(scene)
    return clock.sample(seconds,token,time.monotonic(),
                        scene.as_pointer() in _FLOW_RENDERING or bpy.app.is_job_running('RENDER'))


@persistent
def _flow_play_start(scene,*_):
    clock,_,_=_flow_clock(scene);clock.start(time.monotonic())


@persistent
def _flow_play_stop(scene,*_):
    clock,_,token=_flow_clock(scene);clock.stop(time.monotonic(),token)


@persistent
def _flow_render_start(scene,*_):
    clock,_,_=_flow_clock(scene);clock.suspend(time.monotonic())
    _FLOW_RENDERING.add(scene.as_pointer())


@persistent
def _flow_render_end(scene,*_):
    clock,_,_=_flow_clock(scene);clock.resume(time.monotonic())
    _FLOW_RENDERING.discard(scene.as_pointer())


@persistent
def _flow_reset(*_):
    _FLOW_CLOCKS.clear();_FLOW_RENDERING.clear();_FLOW_CACHE.clear()


_FLOW_HANDLERS=(('animation_playback_pre',_flow_play_start),('animation_playback_post',_flow_play_stop),
    ('render_init',_flow_render_start),('render_complete',_flow_render_end),
    ('render_cancel',_flow_render_end),('load_post',_flow_reset))
ROUTING_VERSION=3
PAINT_WIND_STATE='_sr_paint_wind_viewport'
TYPE_ITEMS=[(m['name'],f"{m['name']} ({m['id']})",'BattleForge engine handler; preview coverage varies',
             int(m['id'],16)+(0x10000 if m['name']=='ReflectRefract' else 0)) for m in catalog()]
TYPE_ITEMS.append(('Unknown','Unknown / preserved ID','Keep an imported material ID not recovered in the engine catalog',0x7fffffff))
TYPE_ARTIST_ITEMS=[(identifier,label.split(' (0x')[0],description,value) for identifier,label,description,value in TYPE_ITEMS]


def material_type_items(settings,context):
    return TYPE_ITEMS if settings.technical_controls else TYPE_ARTIST_ITEMS


SCALAR_NAMES={0x63737431:'Smoothness',0x63737432:'Metalness',0x63737433:'Reflectivity',
    0x63737434:'Emissivity',0x63737435:'Refraction Scale',0x63737436:'Distortion Mesh Scale',
    0x73637468:'Scratch',0x63737437:'Specular Scale',0x63737438:'Wind Response',
    0x63737439:'Wind Height',0x73636477:'Depth Write Threshold',0x63737441:'Saturation'}
DEFAULT_FLOW=dict(zip(FLOW_IDS,((0,1,0,0),(0,.5,0,0),(0,.1,0,0),(1,1,1,0))))


def modern(material):
    return bool(material and material.get(MARKER)==2 and hasattr(material,'drs_settings'))


def owner_settings(row):
    material=row.id_data
    return material.drs_settings if isinstance(material,bpy.types.Material) else None


def update_row(self, context):
    material=self.id_data
    if isinstance(material,bpy.types.Material) and material.as_pointer() not in _BUSY:
        sync_material(material, context.object if context else None)


def type_changed(self, context):
    material=self.id_data
    if material.as_pointer() in _BUSY:return
    old=material.get('_drs_handler',self.material_type)
    if old!=self.material_type:
        # Switching schemas is intentional: only matching, equally named texture
        # roles survive. ParamMap and SpecularMap must not silently share content.
        previous={int(t.identifier,0):(t.name,t.image) for t in self.textures}
        profiles=json.loads(material.get('_drs_material_profiles','{}'))
        profiles[old]=profile_snapshot(self)
        material['_drs_material_profiles']=json.dumps(profiles)
        _BUSY.add(material.as_pointer())
        try:
            if self.material_type in profiles:
                restore_profile(self,profiles[self.material_type])
                flags=profiles[self.material_type]['flags']
            else:
                make_defaults(self,self.material_type)
                compatible_colors={'ColorMap','DiffuseMap','BaseColorTexture','ColorTexture','DecalTexture','Texture'}
                for t in self.textures:
                    prior=previous.get(int(t.identifier,0))
                    if prior and (prior[0]==t.name or (int(t.identifier,0)==COLOR_ID and
                                 prior[0] in compatible_colors and t.name in compatible_colors)):
                        t.image=prior[1];t.enabled=True
                flags=sum(1<<f['bit'] for f in schema(name=self.material_type)['flags'] if f.get('initial') and f.get('serialized_selectable',True))
            material['_drs_flags']=signed32(flags)
            owner=context.object if context and context.object and context.object.active_material==material else next(
                (obj for obj in bpy.data.objects if obj.type=='MESH' and obj.active_material==material),None)
            if owner:owner.drs_material.bool_parameter=signed32(flags)
        finally:_BUSY.discard(material.as_pointer())
    material['_drs_handler']=self.material_type
    if context and context.object and context.object.active_material==material:
        # Bit meanings are handler-specific. Keep unregistered bits until the
        # artist chooses Auto Features; no generic remapping across handlers.
        self.notice='Material type changed. Previous settings are retained when switching back.'
    sync_material(material,context.object if context else None)


class DRS_ParameterPG(PropertyGroup):
    enabled:BoolProperty(name='Export parameter',default=True,update=update_row)
    identifier:StringProperty(default='0x0')
    value:FloatProperty(name='Value',update=update_row)
    vector:FloatVectorProperty(name='Value',size=4,update=update_row)
    color:FloatVectorProperty(name='Color',size=3,subtype='COLOR',default=(1,1,1),update=update_row)
    integer:IntProperty(name='Value',update=update_row)
    text:StringProperty(name='Text',update=update_row)
    original_text:StringProperty(options={'HIDDEN'})
    raw_hex:StringProperty(options={'HIDDEN'})
    original_hex:StringProperty(options={'HIDDEN'})


# RNA bounds are defined per property, not per collection item. Bounded UI
# proxies share the lossless value field used by import/export. Only an edit
# through a proxy changes that value; drawing it never normalizes source data.
SCALAR_RANGE_FIELDS = {}


def _bounded_scalar_property(lower, upper):
    def get_value(row):
        return max(lower, min(upper, row.value))

    def set_value(row, value):
        row.value = max(lower, min(upper, value))

    return FloatProperty(name='Value', min=lower, max=upper,
                         get=get_value, set=set_value, precision=4)


for _range in sorted({(p['min'], p['max']) for m in catalog()
                      for p in m['parameters'].get('scalar', [])
                      if 'min' in p and 'max' in p}):
    _field = f'bounded_scalar_{len(SCALAR_RANGE_FIELDS)}'
    SCALAR_RANGE_FIELDS[_range] = _field
    DRS_ParameterPG.__annotations__[_field] = _bounded_scalar_property(*_range)


def scalar_value_property(entry):
    return SCALAR_RANGE_FIELDS.get((entry.get('min'), entry.get('max')), 'value')


class DRS_TexturePG(PropertyGroup):
    identifier:StringProperty(default='0x0')
    image:PointerProperty(type=bpy.types.Image,update=update_row)
    enabled:BoolProperty(name='Export slot',default=True,update=update_row)
    source_name:StringProperty(name='Source filename')
    source_path:StringProperty(options={'HIDDEN'})
    bias:FloatProperty(name='Stored texture bias',description='Preserved DRS load bias; Default overrides it in the traced engine path')
    raw_bias:IntProperty(options={'HIDDEN'})
    original_bias:FloatProperty(options={'HIDDEN'})


class DRS_MaterialSettingsPG(PropertyGroup):
    technical_controls:BoolProperty(name='View Mode',description='Switch between Artist View and Debug View. Debug View reveals raw records and Blender-only diagnostics; switching views does not change exported values',default=False,update=update_row)
    material_type:EnumProperty(name='Material Type',items=material_type_items,default=DEFAULT_ID,update=type_changed)
    source_id:IntProperty(default=DEFAULT_ID,min=0,max=65535)
    initialized:BoolProperty(default=False,options={'HIDDEN'})
    auto_features:BoolProperty(name='Auto map flags',description='For Default, calculate map bits from enabled images; retain other bits',default=False,update=update_row)
    parameter_source:EnumProperty(name='Parameter Source',items=[('PACKED','Packed _par / _spec','Read the packed texture'),
        ('SEPARATE','Separate artist maps','Automatically pack Default RGBA at export'),
        ('SCALARS','Scalar values','Default: clear UseParameterMap and use scalar values')],default='PACKED',update=update_row)
    roughness_image:PointerProperty(type=bpy.types.Image,update=update_row)
    metalness_image:PointerProperty(type=bpy.types.Image,update=update_row)
    mask_image:PointerProperty(type=bpy.types.Image,update=update_row)
    emission_image:PointerProperty(type=bpy.types.Image,update=update_row)
    alpha_cutoff:FloatProperty(name='Preview alpha cutoff',default=.5,min=0,max=1,update=update_row)
    preview_refraction:BoolProperty(name='Refraction Preview',description='Ray-traced approximation; does not set the environment-map bit',default=True,update=update_row)
    preview_ior:FloatProperty(name='Preview IOR',description='Blender preview only; Default exports RefractionScale, not this IOR',default=1.03,min=1,max=2.5,update=update_row)
    flow_seed:IntProperty(name='Preview random seed',default=1,update=update_row)
    notice:StringProperty(options={'HIDDEN'})
    scalars:CollectionProperty(type=DRS_ParameterPG)
    colors:CollectionProperty(type=DRS_ParameterPG)
    vectors:CollectionProperty(type=DRS_ParameterPG)
    integers:CollectionProperty(type=DRS_ParameterPG)
    strings:CollectionProperty(type=DRS_ParameterPG)
    textures:CollectionProperty(type=DRS_TexturePG)


def handler_id(settings):
    return settings.source_id if settings.material_type=='Unknown' else int(schema(name=settings.material_type)['id'],16)


def make_defaults(settings, handler):
    definition=schema(name=handler)
    for attr in ('scalars','textures','colors','vectors','integers','strings'):getattr(settings,attr).clear()
    for category,attr in (('scalar','scalars'),('texture','textures'),('color','colors'),('vector','vectors')):
        seen=set()
        for item in definition['parameters'].get(category,[]):
            if item['id'] in seen:continue
            seen.add(item['id']);row=getattr(settings,attr).add()
            row.identifier=hex(item['id']);row.name=item['name']
            if category=='scalar':row.value=item.get('default',0.)
            elif category=='texture':row.enabled=False
            elif category=='vector':row.vector=(0,0,0,0)
    if handler=='Default':
        defaults=DEFAULT_FLOW
        for row in settings.vectors:
            if int(row.identifier,0) in defaults:row.vector=defaults[int(row.identifier,0)]
    settings.initialized=True


def profile_snapshot(settings):
    result={'flags':int(settings.id_data.get('_drs_flags',0)),'rows':{},'parameter_source':settings.parameter_source}
    for attr in ('scalars','colors','vectors','integers','strings','textures'):
        result['rows'][attr]=[]
        for row in getattr(settings,attr):
            fields=('name','identifier','enabled','source_name','source_path','bias','raw_bias','original_bias') if attr=='textures' else (
                'name','identifier','enabled','value','vector','color','integer','text','original_text','raw_hex','original_hex')
            data={}
            for field in fields:
                value=getattr(row,field)
                data[field]=list(value) if field in ('vector','color') else value
            if attr=='textures':data['image']=row.image.name if row.image else None
            result['rows'][attr].append(data)
    return result


def restore_profile(settings, profile):
    for attr,rows in profile['rows'].items():
        collection=getattr(settings,attr);collection.clear()
        for data in rows:
            row=collection.add()
            for field,value in data.items():
                setattr(row,field,bpy.data.images.get(value) if field=='image' and value else value)
    settings.parameter_source=profile.get('parameter_source','PACKED')


def append_missing_parameters(settings):
    """Expose available artist slots without adding bytes to an unchanged import."""
    definition=schema(name=settings.material_type)
    for category,attr in (('scalar','scalars'),('texture','textures'),('color','colors'),('vector','vectors')):
        rows=getattr(settings,attr);seen={int(row.identifier,0) for row in rows}
        for item in definition['parameters'].get(category,[]):
            if item['id'] in seen:continue
            seen.add(item['id']);row=rows.add();row.identifier=hex(item['id']);row.name=item['name']
            if category=='scalar':row.value=item.get('default',0.)
            elif category=='color':row.color=(1,1,1)
            row.enabled=False


def initialize_new(material):
    settings=material.drs_settings
    if settings.initialized:return
    _BUSY.add(material.as_pointer())
    try:make_defaults(settings,settings.material_type)
    finally:_BUSY.discard(material.as_pointer())
    material['_drs_handler']=settings.material_type


def load_image(path, role):
    if not path or not Path(path).is_file():return None
    try:
        image=bpy.data.images.load(str(path),check_existing=True)
        image.colorspace_settings.name='sRGB' if any(t in role.lower() for t in ('color','diffuse','fluid','decal')) else 'Non-Color'
        image.alpha_mode='CHANNEL_PACKED'
        return image
    except RuntimeError:return None


def import_settings(material, mesh, directory):
    if not hasattr(material,'drs_settings'):return
    settings=material.drs_settings
    definition=schema(material_id=mesh.material_id)
    matches=[m for m in catalog() if int(m['id'],16)==(mesh.material_id&0xffff)]
    if len(matches)>1:
        definition={'name':'Unknown','parameters':{}}
    _BUSY.add(material.as_pointer())
    try:
        settings.source_id=mesh.material_id&0xffff
        settings.material_type=definition['name']
        settings.notice=('This ID has multiple engine handlers; choose the intended handler explicitly.' if len(matches)>1 else '')
        material['_drs_handler']=settings.material_type
        for attr in ('scalars','textures','colors','vectors','integers','strings'):getattr(settings,attr).clear()
        for source in mesh.materials.materials:
            stream=BytesIO();source.write(stream);raw=stream.getvalue()
            row=settings.scalars.add();row.identifier=hex(source.identifier&0xffffffff)
            row.name=parameter_name(settings.material_type,'scalar',source.identifier)
            row.value=unpack('<f',raw[4:8])[0];row.original_hex=raw.hex()
        for source in mesh.textures.textures:
            row=settings.textures.add();row.identifier=hex(source.identifier&0xffffffff)
            row.name=parameter_name(settings.material_type,'texture',source.identifier)
            row.source_name=source.name
            path=Path(directory)/source.name
            if path.suffix.lower()!='.dds':path=path.with_suffix('.dds')
            row.source_path=str(path);row.image=load_image(path,row.name)
            row.enabled=bool(source.name);row.bias=source.texture_bias
            row.original_bias=source.texture_bias;row.raw_bias=source.spacer
        for identifier,values in mesh.refraction.entries or ([(mesh.refraction.identifier,mesh.refraction.rgb)] if mesh.refraction.length else []):
            row=settings.colors.add();row.identifier=hex(identifier&0xffffffff)
            row.name=parameter_name(settings.material_type,'color',identifier);row.color=values
        if mesh.material_parameters==-86061050:
            vectors=mesh.flow.entries
            if not vectors and mesh.flow.length==4:
                vectors=[(getattr(mesh.flow,attr+'_identifier'),getattr(mesh.flow,attr)) for attr in
                    ('max_flow_speed','min_flow_speed','flow_speed_change','flow_scale')]
            for identifier,values in vectors:
                row=settings.vectors.add();row.identifier=hex(identifier&0xffffffff)
                row.name=parameter_name(settings.material_type,'vector',identifier)
                row.vector=(values.x,values.y,values.z,values.w)
        if mesh.material_parameters!=-86061055:
            names=definition['parameters'].get('integer',[])
            values=mesh.level_of_detail.levels or ([mesh.level_of_detail.lod_level] if mesh.level_of_detail.length else [])
            for index,value in enumerate(values):
                row=settings.integers.add();row.integer=value
                row.name=names[index]['name'] if index<len(names) else f'Integer slot {index}'
        if mesh.material_parameters in (-86061053,-86061052,-86061051,-86061050):
            for index,raw in enumerate(mesh.empty_string.entries):
                row=settings.strings.add();row.name=f'String slot {index}'
                row.text=raw.decode('utf8',errors='replace');row.original_text=row.text;row.raw_hex=raw.hex()
        settings.initialized=True
        append_missing_parameters(settings)
        settings.preview_refraction=any(int(t.identifier,0)==REF_ID and t.enabled for t in settings.textures)
        values={int(r.identifier,0):list(r.vector) for r in settings.vectors if r.enabled}
        material['_drs_source_flow_controls']=json.dumps({hex(identifier):values.get(identifier,list(default)) for identifier,default in DEFAULT_FLOW.items()})
    finally:_BUSY.discard(material.as_pointer())
    sync_material(material)


def hydrate_object_flow(obj,mesh):
    if (mesh.material_id&0xffff)!=DEFAULT_ID:return
    values={identifier:vector for identifier,vector in mesh.flow.entries} if mesh.material_parameters==-86061050 else {}
    obj.drs_flow.use_flow=any(identifier in FLOW_IDS for identifier in values)
    for identifier,attr in zip(FLOW_IDS,('max_flow_speed','min_flow_speed','flow_speed_change','flow_scale')):
        value=values.get(identifier)
        setattr(obj.drs_flow,attr,(value.x,value.y,value.z,value.w) if value else DEFAULT_FLOW[identifier])


def group_node(material):
    return material.node_tree.nodes.get('DRS_Engine_Group') if material and material.use_nodes else None


def configure_image(image, color_space, packed_alpha=False):
    """Set data interpretation without losing generated or unsaved pixels.

    Blender can discard a generated/dirty image buffer when its color space is
    changed. File-backed clean images can be reloaded by Blender normally.
    """
    change_space=image.colorspace_settings.name!=color_space
    change_alpha=packed_alpha and image.alpha_mode!='CHANNEL_PACKED'
    if not (change_space or change_alpha):return
    pixels=None
    if image.has_data and (image.is_dirty or image.source=='GENERATED'):
        from array import array
        pixels=array('f',[0.0])*len(image.pixels)
        image.pixels.foreach_get(pixels)
    if change_space:image.colorspace_settings.name=color_space
    if change_alpha:image.alpha_mode='CHANNEL_PACKED'
    if pixels is not None:
        image.pixels.foreach_set(pixels)
        image.update()


def sync_object(obj):
    if obj and getattr(obj,'type',None)=='MESH' and modern(obj.active_material):
        sync_material(obj.active_material,obj)
        return True
    return False


def refraction_preview_enabled(settings):
    # Artist View always follows the material. Debug View may isolate the effect.
    return not settings.technical_controls or settings.preview_refraction


def sync_automatic_wind(material):
    """Derive Blender deformation from valid engine scalars; never edit export records."""
    from .material_flow_editor import _find_wind_modifier, _create_wind_modifier, _update_wind_nodes
    settings=material.drs_settings
    defaults={p['id']:p for p in schema(name='Default')['parameters']['scalar']
              if p['id'] in (0x63737438,0x63737439)}
    values={identifier:entry.get('default',0.) for identifier,entry in defaults.items()}
    if handler_id(settings)==DEFAULT_ID:
        for row in settings.scalars:
            identifier=int(row.identifier,0)
            if identifier not in defaults or not row.enabled:continue
            entry=defaults[identifier]
            if scalar_in_range(entry,row.value):values[identifier]=row.value
    enabled=handler_id(settings)==DEFAULT_ID and values[0x63737438]>0
    _BUSY.add(material.as_pointer())
    try:
        for obj in bpy.data.objects:
            if obj.type!='MESH' or obj.active_material!=material or obj.get('_drs_material_importing'):continue
            modifier=_find_wind_modifier(obj)
            if enabled and modifier is None:
                _create_wind_modifier(obj)
                modifier=_find_wind_modifier(obj)
                modifier.node_group['_sr_automatic_wind']=True
            if modifier:
                modifier.show_render=enabled
                if obj.mode=='TEXTURE_PAINT':
                    obj[PAINT_WIND_STATE]=enabled
                    modifier.show_viewport=False
                else:
                    if PAINT_WIND_STATE in obj:del obj[PAINT_WIND_STATE]
                    modifier.show_viewport=enabled
                if hasattr(obj,'drs_wind'):
                    for identifier,attr in ((0x63737438,'wind_response'),(0x63737439,'wind_height')):
                        value=values[identifier]
                        if getattr(obj.drs_wind,attr)!=value:setattr(obj.drs_wind,attr,value)
                    _update_wind_nodes(obj.drs_wind)
    finally:_BUSY.discard(material.as_pointer())


def sync_material(material,obj=None):
    if not modern(material) or material.as_pointer() in _BUSY:return
    initialize_new(material)
    settings=material.drs_settings
    if obj is not None and (getattr(obj,'type',None)!='MESH' or obj.active_material!=material):obj=None
    if obj is None:
        obj=next((o for o in bpy.data.objects if o.type=='MESH' and o.active_material==material),None)
    node=group_node(material)
    if not node:return
    if 'Use Vertex Color' not in node.inputs or 'Environment Color' not in node.inputs:
        # Swap only the shared group, retaining all links and input values on
        # the artist's material, including user-created links.
        from sr_impex.blender.material_preview import surface_group
        links=material.node_tree.links
        incoming=[(link.from_socket,link.to_socket.name) for link in links if link.to_node==node]
        outgoing=[(link.from_socket.name,link.to_socket) for link in links if link.from_node==node]
        values={sock.name:sock.default_value[:] if hasattr(sock.default_value,'__len__') else sock.default_value
                for sock in node.inputs if hasattr(sock,'default_value')}
        node.node_tree=surface_group()
        for name,value in values.items():
            if name in node.inputs:node.inputs[name].default_value=value
        for source,name in incoming:
            if name in node.inputs:links.new(source,node.inputs[name])
        for name,target in outgoing:
            if name in node.outputs:links.new(node.outputs[name],target)
    node.label='DRS Material - '+settings.material_type
    definition=schema(name=settings.material_type)
    textures={int(row.identifier,0):row for row in settings.textures}
    nodes=material.node_tree.nodes
    for row in settings.textures:
        identifier=int(row.identifier,0)
        tex=next((n for n in nodes if n.get('drs_texture_id')==identifier),None)
        if tex is None:
            tex=nodes.new('ShaderNodeTexImage');tex['drs_texture_id']=identifier
            tex.location=(-1100,-len(nodes)*30)
        tex.label=row.name;tex.image=row.image if row.enabled else None
        if row.image:
            space='Non-Color' if any(term in row.name.lower() for term in
                ('param','specular','normal','scratch','distortion','mask','blur')) else 'sRGB'
            configure_image(row.image,space,packed_alpha=True)
    routes=preview_texture_routes(settings.material_type)
    for input_name in ('Color Map','Color Alpha','Parameter Map','Parameter Alpha','Normal Map',
                       'Refraction Map','Refraction Alpha','Fluid Color','Fluid Alpha','Scratch Alpha','Environment Color'):
        identifier=routes.get(input_name)
        tex=next((n for n in nodes if n.get('drs_texture_id')==identifier),None)
        row=textures.get(identifier)
        for link in list(node.inputs[input_name].links):material.node_tree.links.remove(link)
        if tex and row and row.enabled and row.image:
            output='Alpha' if input_name.endswith('Alpha') else 'Color'
            material.node_tree.links.new(tex.outputs[output],node.inputs[input_name])
    flags=int(obj.drs_material.bool_parameter)&0xffffffff if obj and hasattr(obj,'drs_material') else int(material.get('_drs_flags',0))&0xffffffff
    is_default=handler_id(settings)==DEFAULT_ID
    present=lambda identifier:identifier in textures and textures[identifier].enabled and textures[identifier].image is not None
    if is_default and settings.auto_features:
        for bit,enabled in ((16,present(PARAM_ID) or settings.parameter_source=='SEPARATE'),(17,present(NORMAL_ID))):
            flags=(flags|1<<bit) if enabled else (flags&~(1<<bit))
    if is_default and settings.parameter_source=='SCALARS':flags&=~(1<<16)
    material['_drs_flags']=signed32(flags)
    if obj and hasattr(obj,'drs_material') and obj.drs_material.bool_parameter!=signed32(flags):
        _BUSY.add(material.as_pointer())
        try:obj.drs_material.bool_parameter=signed32(flags)
        finally:_BUSY.discard(material.as_pointer())
    def put(name,value):
        if name in node.inputs:node.inputs[name].default_value=value
    for key,value in (('Smoothness',0.),('Metalness',0.),('Reflectivity',0.),('Emissivity',0.),
                      ('Specular Scale',1.5),('Saturation',1.),('Scratch',0.),('Refraction Scale',1.)):
        put(key,value)
    family=0
    if settings.material_type in ('SingleColor','MonoColor','Textured','VertexColor','SimpleTextured','Billboard',
        'ParticleSystem','StatefulParticles','Trail','Emitter','Satellite','Glow','LightRay','UIBase','ActionButton','EATextFont','MiniMap'):family=2
    elif settings.material_type.startswith('DiffuseSpecular') or settings.material_type in ('Lava','Effect','Std'):family=1
    elif settings.material_type=='VolumetricFog':family=4
    put('Family',family)
    put('Use Parameter Map',float(is_default and bool(flags&(1<<16))))
    put('Use Environment Map',float(is_default and bool(flags&(1<<18))))
    put('Use Separate Maps',float(is_default and settings.parameter_source=='SEPARATE'))
    use_normal=routes.get('Normal Map')==NORMAL_ID and present(NORMAL_ID) and (bool(flags&(1<<17)) if is_default else True)
    put('Use Normal Map',float(use_normal))
    from sr_impex.blender.material_preview import ensure_environment_sampling
    env_row=textures.get(ENV_ID)
    ensure_environment_sampling(material,env_row.image if env_row and env_row.enabled else None,use_normal)
    names={f['name']:f for f in definition['flags']}
    put('Alpha Test',float('EnableAlphaTest' in names and bool(flags&(1<<names['EnableAlphaTest']['bit']))))
    put('Decal',float(settings.material_type in ('StaticDecal','DynamicDecal','StaticDecalPreview','SelectionDecal') or (is_default and flags&2!=0)))
    put('Alpha Cutoff',settings.alpha_cutoff)
    screen=bool(bpy.context.scene and (bpy.context.scene.get('_drs_screen_refraction') or
                (material.get('_sr_fx_refraction') and bpy.context.scene.get('_sr_fx_refraction_render'))))
    put('Use Refraction',float(not screen and refraction_preview_enabled(settings) and ((is_default and present(REF_ID)) or settings.material_type in ('Water','Fluid','ReflectRefract'))))
    put('Screen Refraction Enabled',float(is_default and refraction_preview_enabled(settings) and present(REF_ID)))
    put('Preview IOR',settings.preview_ior)
    put('Volume Density',0.);put('Volume Emission',0.)
    put('Use Masked Color',float(settings.material_type=='DiffuseSpecularMaskedColor'))
    put('Use Texture Alpha',float(settings.material_type in ('Textured','SimpleTextured')))
    put('Texture Alpha Factor',1.)
    from sr_impex.utilities.vertex_colors import COLOR_ATTRIBUTE
    vertex_color=(obj.data.color_attributes.get(COLOR_ATTRIBUTE) if obj else None)
    vertex_enabled=(settings.material_type in ('Textured','SimpleTextured') and
                    bool(flags & (1<<16)) and vertex_color is not None)
    put('Use Vertex Color',float(vertex_enabled))
    vertex_node=nodes.get('SR Color0 Attribute')
    if vertex_node is None:
        vertex_node=nodes.new('ShaderNodeVertexColor');vertex_node.name='SR Color0 Attribute'
        vertex_node.label='SR Color0 (editable vertex colors)'
    vertex_node.layer_name=COLOR_ATTRIBUTE
    for input_name,output_name in (('Vertex Color','Color'),('Vertex Alpha','Alpha')):
        if not node.inputs[input_name].is_linked:
            material.node_tree.links.new(vertex_node.outputs[output_name],node.inputs[input_name])
    put('Masked Color',(1,1,1,1))
    put('Tint Color',(1,1,1,1))
    if settings.material_type in ('Water','Fluid','ReflectRefract') and not present(REF_ID):put('Refraction Alpha',1.)
    ranges={entry['id']:entry for entry in definition['parameters'].get('scalar',[])}
    for row in settings.scalars:
        if not row.enabled:continue
        identifier=int(row.identifier,0)
        entry=ranges.get(identifier,{})
        if not scalar_in_range(entry,row.value):continue
        name=SCALAR_NAMES.get(identifier) if is_default else row.name
        if name:put(name,row.value)
        if (settings.material_type in ('Textured','SimpleTextured') and row.name=='Alpha'
                and not flags & (1<<16)):
            put('Texture Alpha Factor',row.value)
        if row.name=='RefractionScale':put('Refraction Scale',row.value)
        if settings.material_type=='VolumetricFog':
            if row.name=='ExtinctionCoefficient':put('Volume Density',max(0.,row.value))
            if row.name=='Emissivity':put('Volume Emission',max(0.,row.value))
    if is_default:
        put('Use Flow',float(present(FLUID_ID)))
    else:
        put('Use Flow',0.)
        # These families have different shader equations; their scalar labels are
        # retained without pretending their cst slots mean Default parameters.
    color=next((r for r in settings.colors if r.enabled and r.name=='RefractionColor'),None)
    if color:
        rgb=nodes.get('Refraction Color')
        if rgb:rgb.outputs[0].default_value=(*color.color,1.)
    tint=next((r for r in settings.colors if r.enabled and r.name in ('ColorDiffuse','Color','TintColor')),None)
    if tint and not (settings.material_type in ('Textured','SimpleTextured') and flags & (1<<16)):
        put('Tint Color',(*tint.color,1.))
        if not present(COLOR_ID):put('Color Map',(1,1,1,1))
    masked=next((r for r in settings.colors if r.enabled and r.name=='MaskedColor'),None)
    if masked:put('Masked Color',(*masked.color,1.))
    fog=next((r for r in settings.colors if r.enabled and r.name=='FogColor'),None)
    if fog:put('Volume Color',(*fog.color,1.))
    for item in node.inputs:item.hide=not item.is_linked
    for item in node.outputs:item.hide=item.name not in ('Surface','Volume')
    for item in nodes:
        internal=(item.get('drs_texture_id') is not None or item.name.startswith(('Separate ','SR Refraction','SR Flow'))
                  or item.name in ('DRS_Flow_Coordinates','Refraction Color','SR Color0 Attribute'))
        if internal:
            item.hide=not settings.technical_controls
            if item.type=='TEX_IMAGE':item.show_options=settings.technical_controls
    for name,image in (('Roughness',settings.roughness_image),('Metallic',settings.metalness_image),
                       ('Mask',settings.mask_image),('Emission',settings.emission_image)):
        tex=nodes.get('Separate '+name)
        if tex:tex.image=image
        if image:configure_image(image,'Non-Color')
        put('Separate '+name+' Present',float(image is not None))
    material.use_raytrace_refraction=refraction_preview_enabled(settings)
    if refraction_preview_enabled(settings) and (present(REF_ID) or settings.material_type in ('Water','Fluid','ReflectRefract')):
        for scene in bpy.data.scenes:
            if scene.render.engine.startswith('BLENDER_EEVEE') and any(o.type=='MESH' and o.active_material==material for o in scene.objects):
                if not scene.eevee.use_raytracing:scene.eevee.use_raytracing=True
    sync_automatic_wind(material)
    material['_drs_preview_routing_version']=ROUTING_VERSION
    _FLOW_CACHE.pop(material.as_pointer(),None)
    update_flow(bpy.context.scene,material,obj)


def ensure_flow_object_uniforms(material,node):
    """Read per-object uniforms without invalidating the material/shader cache."""
    if node.get('_sr_flow_object_uniforms')==1:return True
    from sr_impex.utilities.ska_utility import _iter_action_fcurves
    tree=material.node_tree;socket=node.inputs['Offset'];old_path=socket.path_from_id('default_value')
    owned=bool(node.get('_sr_flow_uniform_drivers') or node.get('_sr_flow_animation_cache'))
    if socket.is_linked and socket.links[0].from_node.name!='SR Flow Offset':return False
    animation=tree.animation_data
    if animation:
        drivers=[fc for fc in animation.drivers if fc.data_path==old_path]
        if drivers and not owned:return False
        for curve in drivers:animation.drivers.remove(curve)
        action=animation.action
        if action and owned:
            # Remove only generated channels; preserve other node animation.
            for curve in list(_iter_action_fcurves(action)):
                if curve.data_path!=old_path and not curve.data_path.startswith('nodes["SR Flow Offset'):continue
                if hasattr(action,'fcurves'):action.fcurves.remove(curve)
                else:
                    for layer in action.layers:
                        for strip in layer.strips:
                            for bag in strip.channelbags:
                                if curve in list(bag.fcurves):bag.fcurves.remove(curve)
            if action.get('_sr_flow_preview') and not list(_iter_action_fcurves(action)):
                animation.action=None
                if action.users==0:bpy.data.actions.remove(action)
    for name,prop in (('Offset','_sr_flow_offset'),('Scale','_sr_flow_scale')):
        attr=tree.nodes.new('ShaderNodeAttribute');attr.name='SR Flow Object '+name
        attr.attribute_type='OBJECT';attr.attribute_name=prop;attr.hide=True
        tree.links.new(attr.outputs['Vector'],node.inputs[name])
    node['_sr_flow_object_uniforms']=1
    return True


def update_flow(scene,material,obj=None):
    if not modern(material):return
    settings=material.drs_settings
    if handler_id(settings)!=DEFAULT_ID:return
    surface=group_node(material)
    explicit_flow=bool(obj and hasattr(obj,'drs_flow') and obj.drs_flow.use_flow)
    if surface and not surface.inputs['Use Flow'].default_value and not explicit_flow:return
    if obj and not obj.add_rest_position_attribute:obj.add_rest_position_attribute=True
    vectors={int(r.identifier,0):tuple(r.vector) for r in settings.vectors if r.enabled}
    # Existing flow controls remain editable and are the public import/export API.
    if obj and hasattr(obj,'drs_flow') and obj.drs_flow.use_flow:
        flow=obj.drs_flow
        vectors.update(zip(FLOW_IDS,(tuple(flow.max_flow_speed),tuple(flow.min_flow_speed),
                                     tuple(flow.flow_speed_change),tuple(flow.flow_scale))))
    maximum=vectors.get(FLOW_IDS[0],(0,1,0,0));minimum=vectors.get(FLOW_IDS[1],(0,.5,0,0))
    change=vectors.get(FLOW_IDS[2],(0,.1,0,0));scale=vectors.get(FLOW_IDS[3],(1,1,1,0))
    seconds=flow_seconds(scene)
    key=(maximum,minimum,change,scale,settings.flow_seed)
    cache_id=(material.as_pointer(),obj.as_pointer() if obj else 0)
    cached=_FLOW_CACHE.get(cache_id)
    if cached is None or cached[0]!=key:
        cached=(key,FlowSequence(minimum,maximum,change,scale,settings.flow_seed))
        _FLOW_CACHE[cache_id]=cached
    node=material.node_tree.nodes.get('DRS_Flow_Coordinates')
    if node:
        from sr_impex.blender.material_preview import ensure_flow_image
        ensure_flow_image()
        if not node.node_tree or not node.node_tree.get('_sr_flow_rest_position'):
            from sr_impex.blender.material_preview import flow_group
            incoming={name:node.inputs[name].links[0].from_socket for name in ('Scale','Offset') if node.inputs[name].is_linked}
            node.node_tree=flow_group()
            for name,sock in incoming.items():material.node_tree.links.new(sock,node.inputs[name])
            fluid=next((n for n in material.node_tree.nodes if n.get('drs_texture_id')==FLUID_ID),None)
            if fluid and not fluid.inputs['Vector'].is_linked:
                material.node_tree.links.new(node.outputs['Lookup UV'],fluid.inputs['Vector'])
        offset=cached[1].sample(seconds)[:3]
        uniform=bool(obj and ensure_flow_object_uniforms(material,node))
        if tuple(material.get('_sr_flow_offset',()))!=tuple(offset):material['_sr_flow_offset']=list(offset)
        if uniform:
            changed=False
            for name,value in (('_sr_flow_offset',offset),('_sr_flow_scale',scale[:3])):
                if tuple(obj.get(name,()))!=tuple(value):obj[name]=list(value);changed=True
            if changed:obj.update_tag(refresh={'OBJECT'})
        else:
            if tuple(node.inputs['Offset'].default_value)!=tuple(offset):node.inputs['Offset'].default_value=offset
            if tuple(node.inputs['Scale'].default_value)!=tuple(scale[:3]):node.inputs['Scale'].default_value=scale[:3]



@persistent
def migrate_loaded_materials(_=None):
    """Upgrade older surface graphs after opening a blend or enabling the add-on."""
    for material in bpy.data.materials:
        if not modern(material):continue
        node=group_node(material)
        if node and ('Use Vertex Color' not in node.inputs or 'Environment Color' not in node.inputs or
                     material.get('_drs_preview_routing_version')!=ROUTING_VERSION):
            try:sync_material(material)
            except Exception as exc:
                print(f'SR material migration failed for {material.name}: {exc}')


@persistent
def guard_texture_paint_geometry(scene,*_):
    """Keep the plugin's animated evaluated mesh out of projection painting.

    Blender 5.0.1 crashed reading corner_verts_eval during a rendered paint
    stroke. A paused wind preview reduces evaluated-mesh invalidation while
    painting; this is a workaround, not a fix for Blender's native lifetime.
    """
    for obj in scene.objects:
        if obj.type!='MESH':continue
        modifier=next((m for m in obj.modifiers if m.type=='NODES' and m.node_group
                       and m.node_group.get('_sr_engine_wind_version')),None)
        if not modifier:continue
        if obj.mode=='TEXTURE_PAINT':
            if PAINT_WIND_STATE not in obj:
                obj[PAINT_WIND_STATE]=modifier.show_viewport
            if modifier.show_viewport:modifier.show_viewport=False
        elif PAINT_WIND_STATE in obj:
            enabled=bool(obj[PAINT_WIND_STATE])
            del obj[PAINT_WIND_STATE]
            if modifier.show_viewport!=enabled:modifier.show_viewport=enabled


@persistent
def frame_update(scene,*_):
    owners={}
    rendering=bpy.app.is_job_running('RENDER')
    layer=bpy.context.view_layer if bpy.context.scene==scene else scene.view_layers[0]
    for obj in scene.objects:
        if (obj.type=='MESH' and obj.active_material and
                (not obj.hide_render if rendering else obj.visible_get(view_layer=layer))):
            owners.setdefault(obj.active_material,[]).append(obj)
    for material,objects in owners.items():
        if modern(material):
            for obj in objects:update_flow(scene,material,obj)
            obj=objects[0]
            if obj:
                node=group_node(material)
                if node:
                    settings=material.drs_settings
                    has_ref=any(int(r.identifier,0)==REF_ID and r.enabled and r.image for r in settings.textures)
                    screen=scene.get('_drs_screen_refraction') or (material.get('_sr_fx_refraction') and scene.get('_sr_fx_refraction_render'))
                    use=not screen and refraction_preview_enabled(settings) and (
                        (settings.material_type=='Default' and has_ref) or settings.material_type in ('Water','Fluid','ReflectRefract'))
                    value=float(bool(use))
                    if node.inputs['Use Refraction'].default_value!=value:
                        node.inputs['Use Refraction'].default_value=value


def apply_parameter_blocks(obj,mesh):
    """Serialize exactly the artist's type-specific lists, including unknown IDs."""
    material=obj.active_material;settings=material.drs_settings
    mesh.material_id=signed16(handler_id(settings));mesh.material_parameters=-86061050
    mesh.bool_parameter=signed32(material.get('_drs_flags',getattr(obj.drs_material,'bool_parameter',0)))
    scalars=[r for r in settings.scalars if r.enabled]
    raw=pack('<I',len(scalars))
    for row in scalars:
        encoded=pack('<If',int(row.identifier,0),row.value)
        # Retain source NaN payloads / original bits where a value was unedited.
        if row.original_hex:
            old=bytes.fromhex(row.original_hex)
            if old[:4]==encoded[:4] and unpack('<f',old[4:8])[0]==row.value:encoded=old
        raw+=encoded
    mesh.materials=Materials().read(BytesIO(raw))
    colors=[r for r in settings.colors if r.enabled]
    raw=pack('<I',len(colors))+b''.join(pack('<I3f',int(r.identifier,0),*r.color) for r in colors)
    mesh.refraction=Refraction().read(BytesIO(raw))
    vectors=[r for r in settings.vectors if r.enabled]
    raw=pack('<I',len(vectors))+b''.join(pack('<I4f',int(r.identifier,0),*r.vector) for r in vectors)
    mesh.flow=Flow().read(BytesIO(raw))
    integers=[r for r in settings.integers if r.enabled]
    mesh.level_of_detail=LevelOfDetail().read(BytesIO(pack('<I',len(integers))+b''.join(pack('<i',r.integer) for r in integers)))
    mesh.empty_string=EmptyString(entries=[bytes.fromhex(r.raw_hex) if r.raw_hex and r.text==r.original_text else r.text.encode('utf8') for r in settings.strings if r.enabled])
    if handler_id(settings)==DEFAULT_ID and hasattr(obj,'drs_flow'):
        baseline=json.loads(material.get('_drs_source_flow_controls','{}'))
        fp=obj.drs_flow
        wanted=dict(zip(FLOW_IDS,(tuple(fp.max_flow_speed),tuple(fp.min_flow_speed),tuple(fp.flow_speed_change),tuple(fp.flow_scale))))
        existing={identifier:vector for identifier,vector in mesh.flow.entries}
        for identifier,value in wanted.items():
            previous=baseline.get(hex(identifier))
            if fp.use_flow and (previous is None or pack('<4f',*previous)!=pack('<4f',*value)):
                if identifier not in existing:
                    from sr_impex.definitions.base_types import Vector4
                    vector=Vector4();mesh.flow.entries.append((identifier,vector));existing[identifier]=vector
                vector=existing[identifier]
                vector.x,vector.y,vector.z,vector.w=value
                for attr,key in zip(('max_flow_speed','min_flow_speed','flow_speed_change','flow_scale'),FLOW_IDS):
                    if key==identifier:setattr(mesh.flow,attr,vector)
        if not fp.use_flow:
            mesh.flow.entries=[entry for entry in mesh.flow.entries if entry[0] not in FLOW_IDS]
        mesh.flow.length=len(mesh.flow.entries)
    return mesh


def sync_wind(obj):
    if not obj or not modern(obj.active_material) or obj.get('_drs_material_importing'):return
    material=obj.active_material
    if material.drs_settings.material_type!='Default' or material.as_pointer() in _BUSY:return
    _BUSY.add(material.as_pointer())
    try:
        for row in material.drs_settings.scalars:
            attr={0x63737438:'wind_response',0x63737439:'wind_height'}.get(int(row.identifier,0))
            if attr:row.value=getattr(obj.drs_wind,attr);row.enabled=True
    finally:_BUSY.discard(material.as_pointer())


def pack_artist_map(settings, material):
    """R=1-roughness, G=metalness, B=mask/reflectivity, A=emissivity.

    Separate grayscale maps use red, including emission. Packed-map fallbacks
    retain their own RGBA channel. Mixed fallback/separate sources are supported.
    """
    import numpy as np
    packed=next((r.image for r in settings.textures if int(r.identifier,0)==PARAM_ID and r.enabled),None)
    images=(settings.roughness_image,settings.metalness_image,settings.mask_image,settings.emission_image)
    source=next((image for image in images if image is not None),packed)
    if source is None:raise ValueError('Separate parameter maps need at least one image')
    width,height=source.size[:]
    def pixels(image):
        if tuple(image.size[:])!=(width,height):
            raise ValueError('Parameter maps must have identical image dimensions')
        array=np.empty(width*height*4,dtype=np.float32);image.pixels.foreach_get(array)
        return array.reshape((-1,4))
    result=pixels(packed).copy() if packed else np.zeros((width*height,4),dtype=np.float32)
    for index,image in enumerate(images):
        if image is not None:
            values=pixels(image)[:,0]
            result[:,index]=1.-values if index==0 else values
    image=bpy.data.images.new(material.name+' packed _par',width=width,height=height,alpha=True,float_buffer=True)
    image.colorspace_settings.name='Non-Color';image.alpha_mode='CHANNEL_PACKED'
    image.pixels.foreach_set(result.ravel());image.update()
    return image


def export_material(obj, mesh, mesh_index, model_name, folder_path, mip_maps, converter):
    """Populate a mesh's full material block without the legacy Default-only path."""
    import shutil
    material=obj.active_material;settings=material.drs_settings
    sync_material(material,obj);apply_parameter_blocks(obj,mesh)
    mesh.textures=Textures()
    temporary=None
    if handler_id(settings)==DEFAULT_ID and settings.parameter_source=='SEPARATE':
        temporary=pack_artist_map(settings,material)
    try:
        rows=list(settings.textures)
        if temporary and not any(int(r.identifier,0)==PARAM_ID for r in rows):
            raise ValueError('Default material has no parameter texture slot')
        for index,row in enumerate(rows):
            identifier=int(row.identifier,0)
            generated=temporary is not None and identifier==PARAM_ID
            if not row.enabled and not generated:continue
            texture=Texture(identifier=signed32(identifier))
            image=temporary if generated else row.image
            suffix={'ColorMap':'_col','DiffuseMap':'_col','TintMap':'_col','BaseColorTexture':'_col',
                    'Texture':'_col','ParamMap':'_par','ParameterMap':'_par','SpecularMap':'_spec',
                    'NormalMap':'_nor','BaseNormalTexture':'_nor','FluidNormal':'_nor',
                    'RefractionParamMap':'_ref','ScratchMap':'_scr','EnvironmentMap':'_env',
                    'DistortionParamMap':'_dis'}.get(row.name,f'_slot_{identifier:08x}_{index}')
            if handler_id(settings)==DEFAULT_ID and identifier==FLUID_ID:suffix='_flu'
            untouched=(not generated and row.source_path and Path(row.source_path).is_file() and image is not None
                       and not image.is_dirty and Path(bpy.path.abspath(image.filepath)).resolve()==Path(row.source_path).resolve()
                       and mip_maps=='auto')
            if untouched:
                name=f'{model_name}_{mesh_index}{suffix}'
                destination=Path(folder_path)/(name+'.dds')
                if Path(row.source_path).resolve()!=destination.resolve():shutil.copy2(row.source_path,destination)
                texture.name=name
            elif image is not None:
                texture.name=converter(image,model_name,mesh_index,folder_path,
                    file_ending=suffix,dxt_format='DXT5',mip_maps=mip_maps,
                    extra_args=['-bc','u','-sepalpha'] if image.colorspace_settings.name=='Non-Color' else None)
                if not texture.name:raise ValueError(f'Failed to export {row.name}')
            elif row.source_path and Path(row.source_path).is_file():
                # Some source DDS formats cannot be sampled by Blender. Preserve
                # their bytes as a copied resource instead of silently dropping it.
                name=f'{model_name}_{mesh_index}{suffix}.dds'
                destination=Path(folder_path)/name
                if Path(row.source_path).resolve()!=destination.resolve():shutil.copy2(row.source_path,destination)
                texture.name=name
            else:
                raise ValueError(f'Enabled texture {row.name} has no image or readable source file')
            texture.spacer=row.raw_bias if row.bias==row.original_bias else unpack('<i',pack('<f',row.bias))[0]
            mesh.textures.textures.append(texture)
        mesh.textures.length=len(mesh.textures.textures)
        return mesh
    finally:
        if temporary:bpy.data.images.remove(temporary)


def draw_flags(layout,obj):
    """Show the recovered flag schema; unregistered set bits remain explicit."""
    material=obj.active_material;definition=schema(name=material.drs_settings.material_type)
    flags=obj.drs_material;raw=int(flags.bool_parameter)&0xffffffff
    technical=material.drs_settings.technical_controls
    if technical:
        layout.label(text=f'Raw mask: 0x{raw:08X}')
    seen=set()
    for flag in definition['flags']:
        if not technical and flag.get('consumer_status')=='registered_no_consumer_found':continue
        bit=flag['bit']
        if bit in seen:continue
        seen.add(bit);line=layout.row()
        label=flag['name']+(' (effect unverified)' if flag.get('consumer_status')=='registered_no_consumer_found' else '')
        line.prop(flags,f'bit_{bit}',text=label)
    for bit in range(32):
        if technical and bit not in seen and raw&(1<<bit):layout.prop(flags,f'bit_{bit}',text=f'Unregistered bit {bit} (preserved)')
    if not definition['flags']:layout.label(text='No DRS boolean inputs registered for this handler.')


class DRS_OT_LoadMaterialTexture(Operator,ImportHelper):
    bl_idname='drs.load_material_texture';bl_label='Load Texture'
    bl_description='Load an image into this texture slot; the exporter converts supported images to DDS'
    bl_options={'REGISTER','UNDO'}
    index:IntProperty(options={'HIDDEN'})
    filter_glob:StringProperty(default='*.dds;*.png;*.tga;*.tif;*.tiff;*.jpg;*.jpeg;*.bmp',options={'HIDDEN'})
    def execute(self,context):
        obj=context.object;material=obj.active_material if obj and obj.type=='MESH' else None
        if not modern(material) or not 0<=self.index<len(material.drs_settings.textures):return {'CANCELLED'}
        try:image=bpy.data.images.load(self.filepath,check_existing=True)
        except (RuntimeError,OSError) as exc:
            self.report({'ERROR'},'Could not load texture: '+str(exc));return {'CANCELLED'}
        row=material.drs_settings.textures[self.index];row.image=image;row.enabled=True
        sync_material(material,obj)
        return {'FINISHED'}


class DRS_OT_MaterialSetup(Operator):
    bl_idname='drs.setup_material';bl_label='Create / Upgrade DRS Material';bl_options={'REGISTER','UNDO'}
    bl_description='Create a game-ready material on the selected mesh; keep its previous material as a separate datablock'
    def execute(self,context):
        obj=context.object
        if not obj or obj.type!='MESH':return {'CANCELLED'}
        # Upgrade into a new datablock: keep the original graph available.
        old=obj.active_material
        material=bpy.data.materials.new((old.name if old else obj.name)+' DRS')
        build_material(material);initialize_new(material)
        from sr_impex.utilities.drs_material_metadata import METADATA_KEY,_decode
        if METADATA_KEY in obj:
            data=json.loads(obj[METADATA_KEY])
            from sr_impex.definitions.mesh_definitions import BattleforgeMesh
            source=BattleforgeMesh(material_id=signed16(data.get('material_id',DEFAULT_ID)),material_parameters=-86061050,
                                  flow=Flow(length=0),level_of_detail=LevelOfDetail(length=0))
            source.bool_parameter=int(obj.drs_material.bool_parameter)
            for key,cls in (('materials',Materials),('refraction',Refraction),('flow',Flow),
                            ('level_of_detail',LevelOfDetail),('strings',EmptyString)):
                if data.get(key) is not None:setattr(source,'empty_string' if key=='strings' else key,_decode(data[key],cls))
            source.textures=Textures(textures=[Texture(identifier=t['identifier'],name=t['name']) for t in data.get('textures',[])])
            directory=''
            if old and old.use_nodes:
                image=next((n.image for n in old.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.filepath),None)
                if image:directory=str(Path(bpy.path.abspath(image.filepath)).parent)
            import_settings(material,source,directory)
        if old and old.use_nodes:
            for n in old.node_tree.nodes:
                if n.type=='TEX_IMAGE' and n.image:
                    row=next((r for r in material.drs_settings.textures if r.name.lower() in n.label.lower() or TEXTURE_LABELS.get(int(r.identifier,0))==n.label),None)
                    if row:row.image=n.image;row.enabled=True
        if obj.material_slots:obj.active_material=material
        else:obj.data.materials.append(material)
        material.drs_settings.auto_features=True
        sync_material(material,obj)
        return {'FINISHED'}


def prepare_texture_paint(context, index):
    """Paint editable pixels, not a DDS compressed GPU image or an internal atlas."""
    from array import array
    obj=context.object
    if not obj or obj.type!='MESH' or not obj.data.uv_layers.active:
        raise ValueError('Select a mesh with a UV map')
    material=obj.active_material
    if not modern(material):raise ValueError('Select a mesh with a DRS material')
    rows=material.drs_settings.textures
    if not 0<=index<len(rows):raise ValueError('Texture slot no longer exists')
    row=rows[index];source=row.image
    if not row.enabled or source is None:raise ValueError('Assign and enable the texture first')
    if source.source not in ('FILE','GENERATED') or source.size[0]<=0 or not source.has_data:
        raise ValueError('Painting requires a loaded, single 2D image')
    if not source.get('_sr_editable_texture'):
        # Image.copy() does not copy unsaved painted pixels. Copy the actual
        # buffer, including alpha, so existing strokes survive preparation.
        pixels=array('f',[0.0])*len(source.pixels)
        source.pixels.foreach_get(pixels)
        image=bpy.data.images.new(Path(source.name).stem+'_paint',
            width=source.size[0],height=source.size[1],alpha=True,float_buffer=source.is_float)
        image.colorspace_settings.name=source.colorspace_settings.name
        image.alpha_mode=source.alpha_mode;image.file_format='PNG'
        image.pixels.foreach_set(pixels);image.update()
        image['_sr_editable_texture']=True
        image['_sr_paint_source']=source.filepath
        image.pack()
        row.image=image
    else:image=source
    node=next((n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image==image),None)
    if node:material.node_tree.nodes.active=node
    # Single-image mode keeps shared internal turbulence textures out of the
    # paint target, regardless of Blender's recursively generated paint slots.
    paint=context.scene.tool_settings.image_paint
    paint.mode='IMAGE';paint.canvas=image
    for area in context.screen.areas if context.screen else ():
        if area.type=='IMAGE_EDITOR':
            space=area.spaces.active;space.image=image;space.mode='PAINT'
            # Repeated display fills the editor with tiles when the next map
            # has a different size/zoom. It is not needed for shader wrapping.
            space.show_repeat=False
    if obj.mode!='TEXTURE_PAINT':bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
    guard_texture_paint_geometry(context.scene)
    return image


class DRS_OT_PaintTexture(Operator):
    bl_idname='drs.paint_texture';bl_label='Paint Texture';bl_options={'REGISTER','UNDO'}
    bl_description='Paint an editable copy, preserving existing strokes and the original source file'
    index:IntProperty(default=-1,options={'HIDDEN'})

    def execute(self,context):
        try:prepare_texture_paint(context,self.index)
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class DRS_OT_MaterialAutoFlags(Operator):
    bl_description = 'Enable the material map features matching its assigned textures; keep other flags'
    bl_idname='drs.material_auto_flags';bl_label='Calculate Map Flags';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        material=context.object.active_material
        material.drs_settings.auto_features=True;sync_material(material,context.object)
        return {'FINISHED'}


class DRS_OT_EnableVertexColors(Operator):
    bl_idname='drs.enable_vertex_colors';bl_label='Create SR Vertex Colors'
    bl_description='Create editable point colors and enable the compatible static color stream'
    bl_options={'REGISTER','UNDO'}
    remove:BoolProperty(default=False,options={'HIDDEN'})
    def execute(self,context):
        obj=context.object
        if not obj or obj.type!='MESH' or obj.mode!='OBJECT' or not modern(obj.active_material):
            self.report({'ERROR'},'Select a mesh with a DRS material in Object Mode');return {'CANCELLED'}
        if obj.active_material.drs_settings.material_type not in ('Textured','SimpleTextured'):
            self.report({'ERROR'},'Choose Textured or SimpleTextured first');return {'CANCELLED'}
        if obj.find_armature():
            self.report({'ERROR'},'Skinned color-stream export is not verified');return {'CANCELLED'}
        from sr_impex.utilities.vertex_colors import COLOR_ATTRIBUTE,COLOR_STREAM_KEY
        if self.remove:
            attr=obj.data.color_attributes.get(COLOR_ATTRIBUTE)
            if attr:obj.data.color_attributes.remove(attr)
            for key in (COLOR_STREAM_KEY,'_sr_color_stream_count'):
                if key in obj.data:del obj.data[key]
            obj.drs_material.bit_16=False
            sync_material(obj.active_material,obj)
            self.report({'INFO'},'SR Color0 removed; export will use the normal mesh layout')
            return {'FINISHED'}
        if obj.data.get(COLOR_STREAM_KEY) and obj.data.get('_sr_color_stream_count',1)!=1:
            self.report({'ERROR'},'Multi-stream vertex color export is not verified');return {'CANCELLED'}
        attr=obj.data.color_attributes.get(COLOR_ATTRIBUTE)
        if attr and attr.domain!='POINT':
            self.report({'ERROR'},'SR Color0 must use the Point domain');return {'CANCELLED'}
        if not attr:
            attr=obj.data.color_attributes.new(name=COLOR_ATTRIBUTE,type='FLOAT_COLOR',domain='POINT')
            for value in attr.data:value.color=(1,1,1,1)
        obj.data.color_attributes.active_color=attr
        obj.data[COLOR_STREAM_KEY]=True
        obj.data['_sr_color_stream_count']=1
        obj.drs_material.bit_16=True
        sync_material(obj.active_material,obj)
        self.report({'INFO'},'SR Color0 created; use Vertex Paint and validate the exported model in the editor')
        return {'FINISHED'}


class DRS_OT_ParameterRecord(Operator):
    bl_description = 'Add or remove an advanced material record'
    bl_idname='drs.parameter_record';bl_label='Material Parameter Record';bl_options={'REGISTER','UNDO'}
    category:EnumProperty(name='Record type',items=[(v,v.title(),'Engine parameter list') for v in ('scalars','colors','vectors','integers','strings','textures')],default='scalars')
    index:IntProperty(default=-1)
    remove:BoolProperty(default=False,options={'HIDDEN'})
    identifier:StringProperty(name='Engine identifier (uint32 / hex)',default='0x0')
    def invoke(self,context,event):
        if self.remove:return self.execute(context)
        obj=context.object
        if not obj or not modern(obj.active_material):return {'CANCELLED'}
        if self.index>=0:self.identifier=getattr(obj.active_material.drs_settings,self.category)[self.index].identifier
        return context.window_manager.invoke_props_dialog(self,width=420)
    def draw(self,context):
        self.layout.prop(self,'category')
        if self.category not in ('integers','strings'):self.layout.prop(self,'identifier')
        self.layout.label(text='Unknown IDs are preserved; no visual meaning is guessed.',icon='INFO')
    def execute(self,context):
        obj=context.object
        if not obj or not modern(obj.active_material):return {'CANCELLED'}
        material=obj.active_material;settings=material.drs_settings;rows=getattr(settings,self.category)
        try:
            if self.remove:rows.remove(self.index)
            else:
                value=int(self.identifier,0)
                if not 0<=value<=0xffffffff:raise ValueError('Identifier must fit uint32')
                if self.index<0 and self.category not in ('integers','strings') and any(int(r.identifier,0)==value for r in rows):
                    raise ValueError('This ID already exists; enable/edit its existing row')
                row=rows.add() if self.index<0 else rows[self.index]
                row.identifier=hex(value);row.enabled=True
                entry=next((p for p in schema(name=settings.material_type)['parameters'].get(
                    {'scalars':'scalar','colors':'color','vectors':'vector','textures':'texture'}.get(self.category,''),[]) if p['id']==value),None)
                row.name=entry['name'] if entry else f'Raw {self.category} {hex(value)}'
                if entry and self.category=='scalars':row.value=entry.get('default',0.)
            sync_material(material,obj)
        except (ValueError,IndexError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


def material_section(layout,key,title,closed=True):
    header,body=layout.panel('sr_material_'+key,default_closed=closed)
    header.label(text=title)
    return body


def scalar_override_reason(material, row, obj=None):
    """Only hide controls with an established replacement path, never guessed dependencies."""
    s=material.drs_settings
    flags=int(obj.drs_material.bool_parameter if obj and hasattr(obj,'drs_material')
              else material.get('_drs_flags',0)) & 0xffffffff
    if handler_id(s)==DEFAULT_ID and s.parameter_source!='SCALARS' and flags & (1<<16):
        if int(row.identifier,0) in range(0x63737431,0x63737435):return 'Supplied by the parameter map'
    if handler_id(s)==DEFAULT_ID:
        textures={int(r.identifier,0) for r in s.textures if r.enabled and r.image is not None}
        if int(row.identifier,0)==0x63737435 and REF_ID not in textures:return 'Requires a refraction map'
        if int(row.identifier,0)==0x73637468 and 0x63737431 not in textures:return 'Requires a scratch map'
    if s.material_type in ('Textured','SimpleTextured') and row.name=='Alpha' and flags & (1<<16):
        return 'Supplied by vertex colors'
    return ''


def draw_parameter_sections(layout,settings,collections):
    s=settings
    definition=schema(name=s.material_type)
    has_ref=any(int(r.identifier,0)==REF_ID and r.enabled and r.image for r in s.textures)
    for collection,field,title in collections:
        if not s.technical_controls and field in ('integer','text'):continue
        known={p['id'] for p in definition['parameters'].get({'color':'color','vector':'vector'}.get(field,''),[])}
        visible=[]
        for index,row in enumerate(collection):
            if field=='vector' and handler_id(s)==DEFAULT_ID and int(row.identifier,0) in FLOW_IDS:continue
            if not s.technical_controls:
                if field in ('color','vector') and int(row.identifier,0) not in known:continue
                if field=='color' and handler_id(s)==DEFAULT_ID and not has_ref:continue
            visible.append((index,row))
        if not visible:continue
        box=material_section(layout,field,title if s.technical_controls else title.split(' (')[0])
        if box is None:continue
        for index,row in visible:
            line=box.row();line.prop(row,'enabled',text='')
            value=line.row();value.enabled=row.enabled;value.prop(row,field,text=row.name)
            category={'color':'colors','vector':'vectors','integer':'integers','text':'strings'}[field]
            if s.technical_controls:
                op=line.operator('drs.parameter_record',text='',icon='X');op.category=category;op.index=index;op.remove=True


def draw_settings(layout,context):
    obj=context.object
    if not obj or obj.type!='MESH' or not obj.select_get():layout.label(text='Select a mesh to edit its DRS material.');return
    material=obj.active_material
    if material is None:
        layout.label(text='Select or create a material on this mesh.',icon='MATERIAL')
        layout.operator('drs.setup_material',text='Create DRS Material',icon='ADD');return
    if not modern(material):layout.operator('drs.setup_material',icon='MATERIAL');return
    s=material.drs_settings;definition=schema(name=s.material_type)
    layout.prop(s,'material_type')
    layout.prop(s,'technical_controls',text='Debug View' if s.technical_controls else 'Artist View',
                icon='CONSOLE' if s.technical_controls else 'BRUSH_DATA',toggle=True)
    if s.material_type=='Unknown' and s.technical_controls:layout.prop(s,'source_id')
    flags=material_section(layout,'flags','Material Flags (BooleanParameters)' if s.technical_controls else 'Material Flags')
    if flags is not None:draw_flags(flags,obj)
    if s.material_type in ('Textured','SimpleTextured'):
        box=material_section(layout,'vertex_colors','Vertex Colors')
        if box:
            if s.material_type in ('Textured','SimpleTextured') and int(material.get('_drs_flags',0)) & (1<<16):
                from sr_impex.utilities.vertex_colors import COLOR_ATTRIBUTE
                if COLOR_ATTRIBUTE not in obj.data.color_attributes:
                    box.label(text='UseVertexColor needs an SR Color0 attribute.',icon='ERROR')
            if s.material_type in ('Textured','SimpleTextured'):
                from sr_impex.utilities.vertex_colors import COLOR_STREAM_KEY
                if obj.data.get(COLOR_STREAM_KEY):
                    box.operator('drs.enable_vertex_colors',text='Remove SR Vertex Colors',icon='X').remove=True
                else:box.operator('drs.enable_vertex_colors',icon='GROUP_VCOL')
                box.label(text='Static 0x28001 stream; check in Map Editor.',icon='INFO')
    box=material_section(layout,'textures','Textures',closed=False)
    if box:
        if handler_id(s)==DEFAULT_ID:
            setup=box.column()
            setup.prop(s,'parameter_source');setup.prop(s,'auto_features')
            if not s.auto_features:setup.operator('drs.material_auto_flags',icon='FILE_REFRESH')
            if s.parameter_source=='SEPARATE':
                setup.prop(s,'roughness_image');setup.prop(s,'metalness_image')
                setup.prop(s,'mask_image',text='Blue flow mask / reflectivity');setup.prop(s,'emission_image')
        previewed_ids=set(preview_texture_routes(s.material_type).values())
        for index,row in enumerate(s.textures):
            if not s.technical_controls:
                if int(row.identifier,0) not in {p['id'] for p in definition['parameters'].get('texture',[])}:continue
                if handler_id(s)==DEFAULT_ID and int(row.identifier,0)==PARAM_ID and s.parameter_source!='PACKED':continue
            label=row.name+(' (export only)' if int(row.identifier,0) not in previewed_ids else '')
            line=box.row(align=True);line.prop(row,'enabled',text='');line.label(text=label);line.prop(row,'image',text='')
            line.operator('drs.load_material_texture',text='',icon='FILE_FOLDER').index=index
            if row.enabled and row.image and int(row.identifier,0) in previewed_ids and int(row.identifier,0)!=ENV_ID:
                line.operator('drs.paint_texture',text='',icon='BRUSH_DATA').index=index
            if s.technical_controls:
                op=line.operator('drs.parameter_record',text='',icon='X');op.category='textures';op.index=index;op.remove=True
            if row.enabled and row.image is None and row.source_name:box.label(text='Missing image: '+row.source_name,icon='ERROR')
        from .environment_cubemap_editor import draw_environment_settings
        draw_environment_settings(box,context)
    draw_parameter_sections(layout,s,((s.colors,'color','Color Parameters (Refraction)'),))
    texture_driven=handler_id(s)==DEFAULT_ID and s.parameter_source!='SCALARS' and bool(int(material.get('_drs_flags',0)) & (1<<16))
    box=material_section(layout,'surface','Scalar Parameters (Materials)' if s.technical_controls else 'Material Parameters')
    if box:
        if texture_driven:box.label(text='Surface values come from the parameter map.',icon='IMAGE_DATA')
        registered={p['id']:p for p in definition['parameters'].get('scalar',[])}
        for index,row in enumerate(s.scalars):
            if not s.technical_controls and int(row.identifier,0) not in registered:continue
            identifier=int(row.identifier,0)
            export_only=handler_id(s)==DEFAULT_ID and identifier in (0x63737436,0x73636477)
            if export_only and not s.technical_controls:continue
            overridden=scalar_override_reason(material,row,obj)
            if overridden and not s.technical_controls:continue
            line=box.row()
            line.prop(row,'enabled',text='')
            value=line.row()
            value.enabled=row.enabled and not overridden
            label=row.name+(' (export only)' if export_only else '')
            if handler_id(s)==DEFAULT_ID and identifier==0x63737437:label+=' (approx.)'
            entry=registered.get(identifier,{})
            value.prop(row,scalar_value_property(entry),text=label)
            if s.technical_controls:
                op=line.operator('drs.parameter_record',text='',icon='X');op.category='scalars';op.index=index;op.remove=True
                if overridden:box.label(text=overridden,icon='INFO')
                if not scalar_in_range(entry,row.value):
                    box.label(text=f'Stored source value: {row.value:g} (preserved)')
    draw_parameter_sections(layout,s,((s.integers,'integer','Integer Parameters (LevelOfDetail)'),
                                      (s.strings,'text','String Parameters (EmptyString)')))
    has_flow=any(int(r.identifier,0)==FLUID_ID and r.enabled and r.image is not None for r in s.textures)
    has_refraction=any(int(r.identifier,0)==REF_ID and r.enabled and r.image is not None for r in s.textures)
    if handler_id(s)==DEFAULT_ID and hasattr(obj,'drs_flow') and (has_flow or s.technical_controls):
        body=material_section(layout,'flow','Flow — Speed and Direction',closed=False)
        if body:
            flow=obj.drs_flow
            if not has_flow:body.label(text='Assign a FluidMap for visible flow.',icon='INFO')
            body.prop(flow,'use_flow',text='Custom Flow Settings')
            controls=body.column();controls.enabled=flow.use_flow
            for attr,title in (('min_flow_speed','Minimum Speed'),('max_flow_speed','Maximum Speed'),
                               ('flow_speed_change','Speed Variation'),('flow_scale','Pattern Scale')):
                controls.label(text=title)
                row=controls.row(align=True)
                for axis,label in enumerate(('X','Y','Z')):row.prop(flow,attr,index=axis,text=label)
                if s.technical_controls:controls.prop(flow,attr,index=3,text='W (advanced)')
    draw_parameter_sections(layout,s,((s.vectors,'vector','Other Flow Vectors'),))
    if s.technical_controls:layout.operator('drs.parameter_record',text='Add Material Record',icon='ADD')
    box=material_section(layout,'info','Info')
    if box:
        box.label(text='Validate final shading in the editor.',icon='INFO')
        if s.material_type not in ('Default',):box.label(text='This handler uses an approximate surface preview.')
        if s.notice:box.label(text=s.notice)
        triangles=sum(max(0,len(face.vertices)-2) for face in obj.data.polygons)
        box.label(text=f'{len(obj.data.vertices):,} vertices / {triangles:,} triangles')
        box.label(text='Counts, texture lengths and export bounds are calculated.')
    if s.technical_controls:
        preview=material_section(layout,'preview','Debug Rendering')
        if preview:
            preview.label(text='Display diagnostics; not exported.',icon='INFO')
            if has_refraction and handler_id(s)==DEFAULT_ID:
                preview.operator('drs.screen_refraction_preview',text='Rebuild Screen Refraction Diagnostic')
            preview.prop(s,'preview_refraction');preview.prop(s,'preview_ior')
            preview.prop(s,'alpha_cutoff');preview.prop(s,'flow_seed')



class DRS_PT_ShaderMaterial(Panel):
    bl_label='Material Editor';bl_category='DRS Editor';bl_space_type='NODE_EDITOR';bl_region_type='UI'
    @classmethod
    def poll(cls,context):return context.space_data.tree_type=='ShaderNodeTree'
    def draw(self,context):draw_settings(self.layout,context)


CLASSES=(DRS_ParameterPG,DRS_TexturePG,DRS_MaterialSettingsPG,DRS_OT_MaterialSetup,DRS_OT_LoadMaterialTexture,
         DRS_OT_PaintTexture,DRS_OT_MaterialAutoFlags,DRS_OT_EnableVertexColors,DRS_OT_ParameterRecord,DRS_PT_ShaderMaterial)


def register():
    for name,handler in _FLOW_HANDLERS:
        handlers=getattr(bpy.app.handlers,name)
        if handler not in handlers:handlers.append(handler)
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Material.drs_settings=PointerProperty(type=DRS_MaterialSettingsPG)
    if guard_texture_paint_geometry not in bpy.app.handlers.depsgraph_update_pre:
        bpy.app.handlers.depsgraph_update_pre.append(guard_texture_paint_geometry)
    if frame_update not in bpy.app.handlers.frame_change_pre:bpy.app.handlers.frame_change_pre.append(frame_update)
    if frame_update not in bpy.app.handlers.render_pre:bpy.app.handlers.render_pre.append(frame_update)
    if migrate_loaded_materials not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(migrate_loaded_materials)
    # Blender restricts bpy.data during add-on registration. Migrate the
    # currently open file on the next event-loop tick, after that restriction.
    if not bpy.app.timers.is_registered(migrate_loaded_materials):
        bpy.app.timers.register(migrate_loaded_materials,first_interval=0.0)


def unregister():
    for name,handler in _FLOW_HANDLERS:
        handlers=getattr(bpy.app.handlers,name)
        if handler in handlers:handlers.remove(handler)
    _flow_reset()
    if guard_texture_paint_geometry in bpy.app.handlers.depsgraph_update_pre:
        bpy.app.handlers.depsgraph_update_pre.remove(guard_texture_paint_geometry)
    # Do not leave the viewport preview paused when disabling the add-on.
    for obj in bpy.data.objects:
        if PAINT_WIND_STATE in obj:
            modifier=next((m for m in obj.modifiers if m.type=='NODES' and m.node_group
                           and m.node_group.get('_sr_engine_wind_version')),None)
            if modifier:modifier.show_viewport=bool(obj[PAINT_WIND_STATE])
            del obj[PAINT_WIND_STATE]
    if frame_update in bpy.app.handlers.frame_change_pre:bpy.app.handlers.frame_change_pre.remove(frame_update)
    if frame_update in bpy.app.handlers.render_pre:bpy.app.handlers.render_pre.remove(frame_update)
    if migrate_loaded_materials in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(migrate_loaded_materials)
    if bpy.app.timers.is_registered(migrate_loaded_materials):bpy.app.timers.unregister(migrate_loaded_materials)
    del bpy.types.Material.drs_settings
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
    _FLOW_CACHE.clear()
