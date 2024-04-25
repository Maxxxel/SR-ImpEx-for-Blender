# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import os
from os.path import dirname, realpath
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper, orientation_helper, axis_conversion
from .drs_importer import load_drs, load_bmg
from .drs_exporter import save_drs

bl_info = {
	"name" : "Battleforge Tools",
	"author" : "Maxxxel",
	"description" : "Addon for importing and exporting Battleforge drs/bmg files",
	"blender" : (4, 0, 0),
	"version" : (2, 2, 2),
	"location" : "File > Import",
	"warning" : "",
	"category" : "Import-Export",
	"tracker_url": ""
}

is_dev_version = True
resource_dir = dirname(realpath(__file__)) + "/resources"

@orientation_helper(axis_forward='X', axis_up='-Y')
class ImportBFModel(bpy.types.Operator, ImportHelper):
	"""Import a Battleforge drs/bmg file"""
	bl_idname = "import_scene.drs"
	bl_label = "Import DRS/BMG"
	filename_ext = ".drs;.bmg"
	filter_glob: StringProperty(default="*.drs;*.bmg", options={'HIDDEN'}, maxlen=255) # type: ignore # ignore
	use_apply_transform : BoolProperty(name="Apply Transform", description="Workaround for object transformations importing incorrectly", default=True) # type: ignore # ignore
	clear_scene : BoolProperty(name="Clear Scene", description="Clear the scene before importing", default=True) # type: ignore # ignore

	def execute(self, context):
		keywords: list = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		global_matrix = axis_conversion(from_forward=self.axis_forward, from_up=self.axis_up).to_4x4()
		keywords["global_matrix"] = global_matrix

		# Check if the file is a DRS or a BMG file
		if self.filepath.endswith(".drs"):
			load_drs(self, context, **keywords)
			return {'FINISHED'}
		elif self.filepath.endswith(".bmg"):
			return load_bmg(self, context, **keywords)
		else:
			self.report({'ERROR'}, "Unsupported file type")
			return {'CANCELLED'}

@orientation_helper(axis_forward='-X', axis_up='Y')
class ExportBFModel(bpy.types.Operator, ExportHelper):
	"""Export a Battleforge drs/bmg file"""
	bl_idname = "export_scene.drs"
	bl_label = "Export DRS"
	filename_ext = ".drs"
	filter_glob: StringProperty(default="*.drs;*.bmg", options={'HIDDEN'}, maxlen=255) # type: ignore # ignore
	use_apply_transform : BoolProperty(name="Apply Transform", description="Workaround for object transformations importing incorrectly", default=True) # type: ignore # ignore

	def execute(self, context):
		keywords: list = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob", "check_existing"))
		global_matrix = axis_conversion(from_forward=self.axis_forward, from_up=self.axis_up).to_4x4()
		keywords["global_matrix"] = global_matrix
		return save_drs(self, context, **keywords)

class NewBFScene(bpy.types.Operator):
	'''Create a new Battleforge scene'''
	bl_idname = "scene.new_bf_scene"
	bl_label = "New Battleforge Scene"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		# Load the default scene from resources
		bpy.ops.wm.open_mainfile(filepath=resource_dir + "/default_scene.blend")
		return {'FINISHED'}

def menu_func_import(self, context=None):
	self.layout.operator(ImportBFModel.bl_idname, text="Battleforge (.drs) - "+(is_dev_version and "DEV" or "")+" v" + str(bl_info["version"][0]) + "." + str(bl_info["version"][1]) + "." + str(bl_info["version"][2]))
	self.layout.operator(NewBFScene.bl_idname, text="New Battleforge Scene - "+(is_dev_version and "DEV" or "")+" v" + str(bl_info["version"][0]) + "." + str(bl_info["version"][1]) + "." + str(bl_info["version"][2]))

def menu_func_export(self, context=None):
	self.layout.operator(ExportBFModel.bl_idname, text="Battleforge (.drs) - "+(is_dev_version and "DEV" or "")+" v" + str(bl_info["version"][0]) + "." + str(bl_info["version"][1]) + "." + str(bl_info["version"][2]))

def register():
	bpy.utils.register_class(ImportBFModel)
	bpy.utils.register_class(ExportBFModel)
	bpy.utils.register_class(NewBFScene)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
	bpy.utils.unregister_class(ImportBFModel)
	bpy.utils.unregister_class(ExportBFModel)
	bpy.utils.unregister_class(NewBFScene)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
	register()
