"""Artist editor for standalone BMS state and transition references."""
from copy import deepcopy
from pathlib import Path
import bpy
from bpy.props import StringProperty,IntProperty,CollectionProperty,PointerProperty,BoolProperty
from bpy_extras.io_utils import ImportHelper,ExportHelper
from sr_impex.definitions.bmg_definitions import BMS
from sr_impex.definitions.grid_definitions import SMeshState,StateTransition,StateBasedMeshSet
from sr_impex.utilities.resource_container import snapshot,restore


class BMS_Row(bpy.types.PropertyGroup):
    state_id:StringProperty(name='State ID',default='0')
    version:IntProperty(name='Record revision',default=1,min=0,max=65535)
    fx:StringProperty(name='FX reference')
    resource:StringProperty(name='Resource DRS')
    original_index:IntProperty(default=-1,options={'HIDDEN'})


class BMS_Settings(bpy.types.PropertyGroup):
    source:StringProperty(options={'HIDDEN'})
    source_dir:StringProperty(name='Resource directory',subtype='DIR_PATH',description='Directory used to resolve DRS and FX references for local checks and previews')
    source_path:StringProperty(options={'HIDDEN'})
    mesh_set_type:StringProperty(name='Mesh-set Type',description='Stored BMS resource type; keep the source value unless creating a different supported resource kind',default='10')
    states:CollectionProperty(type=BMS_Row)
    transitions:CollectionProperty(type=BMS_Row)
    validation:StringProperty(options={'HIDDEN'})


def load_model(settings,filename):
    path=Path(filename);value=BMS().read(str(path));meshset=value.state_based_mesh_set
    settings.source=snapshot(path.read_bytes());settings.source_dir=str(path.resolve().parent)
    settings.source_path=str(path.resolve())
    settings.mesh_set_type=str(meshset.mesh_set_type)
    settings.states.clear();settings.transitions.clear()
    settings.validation=''
    for index,state in enumerate(meshset.mesh_states):
        row=settings.states.add();row.state_id=str(state.state_id);row.version=state.version
        row.fx=state.fx_file;row.resource=state.resource_file;row.original_index=index
    for index,transition in enumerate(meshset.transitions):
        row=settings.transitions.add();row.state_id=str(transition.target_state)
        row.fx=transition.fx_file;row.original_index=index


def build_model(settings):
    if not settings.source:raise ValueError('Open an existing BMS first')
    value=BMS().read_bytes(restore(settings.source));meshset=value.state_based_mesh_set
    previous_states=meshset.mesh_states;previous_transitions=meshset.transitions
    def parse_id(text):
        try:number=int(text,0)
        except ValueError:number=int(text,10)
        if not 0<=number<=0xffffffff:raise ValueError('State ID must fit uint32')
        return number
    def validate_ids(rows):
        ids=[parse_id(row.state_id) for row in rows]
        if len(set(ids))!=len(ids):raise ValueError('Each state or transition ID must be unique')
        return ids
    ids=validate_ids(settings.states);destinations=validate_ids(settings.transitions)
    states=[]
    for row,state_id in zip(settings.states,ids):
        item=deepcopy(previous_states[row.original_index]) if 0<=row.original_index<len(previous_states) else SMeshState()
        item.state_id=state_id;item.version=row.version
        if row.version==1:item.fx_file=row.fx;item.resource_file=row.resource
        states.append(item)
    transitions=[]
    for row,state_id in zip(settings.transitions,destinations):
        item=deepcopy(previous_transitions[row.original_index]) if 0<=row.original_index<len(previous_transitions) else StateTransition()
        item.target_state=state_id;item.fx_file=row.fx;transitions.append(item)
    meshset.mesh_set_type=parse_id(settings.mesh_set_type);meshset.mesh_states=states;meshset.transitions=transitions
    return value


class BMS_OT_Open(bpy.types.Operator,ImportHelper):
    bl_description = 'Open a BMS file to edit its state resources and effects'
    bl_idname='sr_bms.open';bl_label='Open BMS';filename_ext='.bms'
    filter_glob:StringProperty(default='*.bms',options={'HIDDEN'})
    def execute(self,context):
        try:load_model(context.scene.sr_bms,self.filepath)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class BMS_OT_New(bpy.types.Operator):
    bl_description = 'Create an empty mesh-state file; add the state resources it needs'
    bl_idname='sr_bms.new';bl_label='New BMS';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        settings=context.scene.sr_bms
        value=BMS(state_based_mesh_set=StateBasedMeshSet())
        settings.source=snapshot(value.to_bytes())
        settings.source_path='';settings.source_dir='';settings.validation=''
        settings.mesh_set_type=str(value.state_based_mesh_set.mesh_set_type)
        settings.states.clear();settings.transitions.clear()
        row=settings.states.add();row.state_id='0';row.version=1
        self.report({'INFO'},'New BMS created. Set the resource directory and state references.')
        return {'FINISHED'}


def inspect_references(settings):
    value=build_model(settings).state_based_mesh_set
    directory=Path(bpy.path.abspath(settings.source_dir)) if settings.source_dir else None
    references=[]
    for state in value.mesh_states:
        if state.version!=1:continue
        for kind,name in (('DRS',state.resource_file),('State FX',state.fx_file)):
            if name:references.append((kind,name))
    for transition in value.transitions:
        if transition.fx_file:references.append(('Transition FX',transition.fx_file))
    missing=[]
    for kind,name in references:
        path=Path(name.replace('\\','/'))
        if not path.is_absolute() and directory is not None:path=directory/path
        if (not path.is_absolute() and directory is None) or not path.is_file():
            missing.append(f'{kind}: {name}')
    return references,missing


class BMS_OT_Validate(bpy.types.Operator):
    bl_description = 'Check state IDs and resource references without changing them'
    bl_idname='sr_bms.validate';bl_label='Check State Resources'
    def execute(self,context):
        settings=context.scene.sr_bms
        try:references,missing=inspect_references(settings)
        except Exception as exc:
            settings.validation='Invalid records: '+str(exc)
            self.report({'ERROR'},settings.validation);return {'CANCELLED'}
        settings.validation=(f'{len(references)} references checked; {len(missing)} not found locally.'+
            ('\n'+'\n'.join(missing) if missing else ''))
        self.report({'INFO'},settings.validation.split('\n')[0])
        return {'FINISHED'}


class BMS_OT_Save(bpy.types.Operator,ExportHelper):
    bl_description = 'Write this mesh-state file to the selected export folder'
    bl_idname='sr_bms.save';bl_label='Export BMS';filename_ext='.bms'
    filter_glob:StringProperty(default='*.bms',options={'HIDDEN'})
    def execute(self,context):
        try:
            path=Path(self.filepath).with_suffix('.bms').resolve()
            if any(p.name.lower()=='unpack' for p in path.parents):raise ValueError('Export outside unpacked game assets')
            if context.scene.sr_bms.source_path and path==Path(context.scene.sr_bms.source_path).resolve():
                raise ValueError('Export to a copy; the imported BMS is read only')
            data=build_model(context.scene.sr_bms).to_bytes()
            BMS().read_bytes(data)
            path.write_bytes(data)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'BMS exported. Keep referenced DRS and FX files available.')
        return {'FINISHED'}


class BMS_OT_Row(bpy.types.Operator):
    bl_description = 'Add or remove a state or transition record in this file'
    bl_idname='sr_bms.row';bl_label='Add / Remove BMS Record';bl_options={'REGISTER','UNDO'}
    transition:BoolProperty(default=False)
    remove:BoolProperty(default=False)
    index:IntProperty(default=0)
    def execute(self,context):
        rows=context.scene.sr_bms.transitions if self.transition else context.scene.sr_bms.states
        if self.remove:rows.remove(self.index)
        else:
            # Offer an unused ID rather than making every new row a duplicate
            # of state 0. The artist may still enter any valid engine ID.
            used=set()
            for existing in rows:
                try:
                    try: value=int(existing.state_id,0)
                    except ValueError: value=int(existing.state_id,10)
                    if 0 <= value <= 0xffffffff: used.add(value)
                except ValueError: pass
            candidate=0
            while candidate in used:candidate+=1
            rows.add().state_id=str(candidate)
        return {'FINISHED'}


class BMS_OT_Preview(bpy.types.Operator):
    bl_description = 'Import the referenced state model into the scene for inspection'
    bl_idname='sr_bms.preview_state';bl_label='Import State DRS Preview';bl_options={'REGISTER','UNDO'}
    index:IntProperty(default=0)
    def execute(self,context):
        settings=context.scene.sr_bms
        if not 0<=self.index<len(settings.states):return {'CANCELLED'}
        row=settings.states[self.index]
        path=Path(row.resource.replace('\\','/'))
        if not path.is_absolute():
            if not settings.source_dir:
                self.report({'ERROR'},'Set the resource directory first');return {'CANCELLED'}
            path=Path(bpy.path.abspath(settings.source_dir))/path
        if row.version!=1 or not row.resource or not path.is_file():
            self.report({'ERROR'},'This state needs an existing revision-1 DRS reference');return {'CANCELLED'}
        from sr_impex.utilities.drs_utility import load_drs
        return load_drs(context,str(path),import_animation=False,import_modules=False)


class BMS_PT_Artist(bpy.types.Panel):
    bl_label='BMS Editor';bl_idname='BMS_PT_artist';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='BMG Editor'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout;settings=context.scene.sr_bms
        row=layout.row(align=True);row.operator('sr_bms.new',icon='ADD');row.operator('sr_bms.open',icon='FILE_FOLDER')
        if not settings.source:return
        header,advanced=layout.panel('sr_bms_advanced',default_closed=True)
        header.label(text='Advanced File Settings')
        if advanced:advanced.prop(settings,'mesh_set_type')
        layout.prop(settings,'source_dir')
        layout.operator('sr_bms.validate',icon='CHECKMARK')
        if settings.validation:
            for message in settings.validation.split('\n'):
                layout.label(text=message)
            layout.label(text='Check again after editing references.',icon='INFO')
        box=layout.box();box.label(text='State resources and persistent FX')
        for index,row in enumerate(settings.states):
            col=box.column(align=True);line=col.row(align=True);line.prop(row,'state_id')
            op=line.operator('sr_bms.row',text='',icon='X');op.remove=True;op.index=index
            if row.version==1:
                col.prop(row,'resource');col.prop(row,'fx')
                col.operator('sr_bms.preview_state',text='Import DRS Preview',icon='MESH_DATA').index=index
            else:col.label(text='This stored state format cannot be edited here.',icon='INFO')
        box.operator('sr_bms.row',text='Add State',icon='ADD')
        box=layout.box();box.label(text='Effects when entering a state')
        for index,row in enumerate(settings.transitions):
            line=box.row(align=True);line.prop(row,'state_id');line.prop(row,'fx')
            op=line.operator('sr_bms.row',text='',icon='X');op.transition=True;op.remove=True;op.index=index
        op=box.operator('sr_bms.row',text='Add Transition',icon='ADD');op.transition=True
        layout.label(text='FX playback needs the Map Editor.',icon='INFO')
        layout.label(text='DRS/FX references must accompany the export.')
        layout.operator('sr_bms.save',icon='EXPORT')


classes=(BMS_Row,BMS_Settings,BMS_OT_Open,BMS_OT_New,BMS_OT_Validate,BMS_OT_Save,BMS_OT_Row,BMS_OT_Preview,BMS_PT_Artist)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.sr_bms=PointerProperty(type=BMS_Settings)
def unregister():
    del bpy.types.Scene.sr_bms
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
