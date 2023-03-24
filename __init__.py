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

bl_info = {
	"name" : "Battleforge Tools",
	"author" : "Maxxxel",
	"description" : "Addon for importing and exporting Battleforge drs/bmg files",
	"blender" : (3, 4, 0),
	"version" : (0, 0, 1),
	"location" : "File > Import",
	"warning" : "",
	"category" : "Import-Export",
	"tracker_url": ""
}

if "bpy" in locals():
	import importlib

	if "DRSImporter" in locals():
		importlib.reload(ImportBFModel)

import bpy

from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, orientation_helper, axis_conversion

@orientation_helper(axis_forward='-X', axis_up='Y')
class ImportBFModel(bpy.types.Operator, ImportHelper):
	"""Import a Battleforge drs/bmg file"""
	bl_idname = "import_scene.drs"
	bl_label = "Import DRS/BMG"
	filename_ext = ".drs;.bmg"
	filter_glob: StringProperty(default="*.drs;*.bmg", options={'HIDDEN'}, maxlen=255)
	UseApplyTransform : BoolProperty(name="Apply Transform", description="Workaround for object transformations importing incorrectly", default=True)
	ClearScene : BoolProperty(name="Clear Scene", description="Clear the scene before importing", default=True)
	EditModel : BoolProperty(name="Only Edit Model", description="Only edit the model and preserve the DRS Data", default=False)

	def execute(self, context):
		from . import DRSImporter
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		global_matrix = axis_conversion(from_forward=self.axis_forward, from_up=self.axis_up).to_4x4()
		keywords["GlobalMatrix"] = global_matrix

		# Check if the file is a DRS or a BMG file
		if self.filepath.endswith(".drs"):
			return DRSImporter.LoadDRS(self, context, **keywords)
		elif self.filepath.endswith(".bmg"):
			return DRSImporter.LoadBMG(self, context, **keywords)
		else:
			self.report({'ERROR'}, "Unsupported file type")
			return {'CANCELLED'}

class ErrorMessage(bpy.types.Operator):
	bl_idname = 'ui.error_message'
	bl_label = "Test error"
	bl_description = "Some useless text"

	def execute(self, context):
		self.report({'INFO'}, message="ERROR: SOME STUPID  MESSAGE")
		return {'CANCELLED'}

def menu_func_import(self, context):
	self.layout.operator(ImportBFModel.bl_idname, text="Battleforge (.drs)")

def register():
	bpy.utils.register_class(ImportBFModel)
	bpy.utils.register_class(ErrorMessage)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
	bpy.utils.unregister_class(ImportBFModel)
	bpy.utils.unregister_class(ErrorMessage)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
	register()
