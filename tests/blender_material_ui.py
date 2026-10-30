"""Exercise artist-visible controls with Blender RNA and material mode changes."""
import sys
from pathlib import Path
from types import SimpleNamespace
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sr_impex
sr_impex.register()
from sr_impex.blender.editors import material_editor as editor, material_flow_editor as legacy
from sr_impex.blender.drs_material import DRSMaterial
from sr_impex.utilities.material_schema import PARAM_ID, FLUID_ID
class Layout:
    def __init__(self,log): self.log=log;self.enabled=True
    def panel(self,key,**kwargs):self.log.append(('panel',key));return self,self
    def row(self,**kwargs):return Layout(self.log)
    column=box=row
    def label(self,**kwargs):pass
    def prop(self,data,key,**kwargs):
        assert hasattr(data,key),(data,key)
        self.log.append(('prop',getattr(data,'name',''),key,kwargs.get('index')))
    def operator(self,*args,**kwargs):
        self.log.append(('operator',args[0]));return SimpleNamespace()
def draw():
    log=[];editor.draw_settings(Layout(log),bpy.context);return log
obj=bpy.context.object
mat=DRSMaterial('UI context checks').material
obj.data.materials.clear();obj.data.materials.append(mat)
s=mat.drs_settings
s.parameter_source='PACKED';s.auto_features=True
param=next(r for r in s.textures if int(r.identifier,0)==PARAM_ID)
param.image=bpy.data.images.new('UI par',width=1,height=1);param.enabled=True
editor.sync_material(mat,obj)
before=[(r.identifier,r.value,r.enabled) for r in s.scalars]
log=draw()
assert ('panel','sr_material_preview') not in log
assert ('operator','drs.add_wind_modifier') not in log
assert ('operator','drs.screen_refraction_preview') not in log
assert not any(x[0]=='prop' and x[1]=='Smoothness' and x[2]!='enabled' for x in log)
assert before==[(r.identifier,r.value,r.enabled) for r in s.scalars]
assert ('panel','sr_material_flow') not in log
s.parameter_source='SCALARS';editor.sync_material(mat,obj)
assert any(x[0]=='prop' and x[1]=='Smoothness' and x[2]!='enabled' for x in draw())
fluid=next(r for r in s.textures if int(r.identifier,0)==FLUID_ID)
fluid.image=bpy.data.images.new('UI fluid',width=1,height=1);fluid.enabled=True
obj.drs_flow.use_flow=True
assert ('panel','sr_material_flow') in draw()
s.parameter_source='SEPARATE';editor.sync_material(mat,obj)
log=draw()
assert not any(x[:3]==('prop',param.name,'image') for x in log)
s.integers.add().name='Preserved integer'
s.strings.add().name='Preserved string'
s.technical_controls=True
log=draw()
assert any(x[0]=='prop' and x[1]=='Smoothness' and x[2]!='enabled' for x in log)
sections=[x[1] for x in log if x[0]=='panel']
order=['sr_material_flags','sr_material_textures','sr_material_color','sr_material_surface',
       'sr_material_integer','sr_material_text','sr_material_flow','sr_material_info','sr_material_preview']
assert sections==order,sections
assert not legacy.DRS_PT_MaterialFlags.poll(bpy.context)
assert not legacy.DRS_PT_Flow.poll(bpy.context)
assert not legacy.DRS_PT_Wind.poll(bpy.context)
assert not any(c.__name__=='DRS_PT_ArtistMaterial' for c in editor.CLASSES)
assert bpy.types.Panel.bl_rna_get_subclass_py('DRS_PT_ArtistMaterial') is None
print('ARTIST_CONTEXT_VISIBILITY_AND_DRS_SECTION_ORDER_OK')
