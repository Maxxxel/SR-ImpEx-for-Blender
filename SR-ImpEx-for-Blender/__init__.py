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
	"blender" : (4, 0, 0),
	"version" : (2, 4, 3),
	"location" : "File > Import",
	"warning" : "",
	"category" : "Import-Export",
	"tracker_url": ""
}

#################################################
# ALX MODULE AUTO-LOADER
import bpy
import os
import importlib

folder_blacklist = ["__pycache__", "alxoverhaul_updater"]
file_blacklist = ["__init__.py", "addon_updater_ops", "addon_updater.py", "Extras.py", ]

addon_folders = list([__path__[0]])
addon_folders.extend( [os.path.join(__path__[0], folder_name) for folder_name in os.listdir(__path__[0]) if ( os.path.isdir( os.path.join(__path__[0], folder_name) ) ) and (folder_name not in folder_blacklist) ] )

addon_files = [[folder_path, file_name[0:-3]] for folder_path in addon_folders for file_name in os.listdir(folder_path) if (file_name not in file_blacklist) and (file_name.endswith(".py"))]

for folder_file_batch in addon_files:
    if (os.path.basename(folder_file_batch[0]) == os.path.basename(__path__[0])):
        file = folder_file_batch[1]

        if (file not in locals()):
            import_line = f"from . import {file}"
            exec(import_line)
        else:
            reload_line = f"{file} = importlib.reload({file})"
            exec(reload_line)
    
    else:
        if (os.path.basename(folder_file_batch[0]) != os.path.basename(__path__[0])):
            file = folder_file_batch[1]

            if (file not in locals()):
                import_line = f"from . {os.path.basename(folder_file_batch[0])} import {file}"
                exec(import_line)
            else:
                reload_line = f"{file} = importlib.reload({file})"
                exec(reload_line)

import inspect

class_blacklist = ["PSA_UL_SequenceList"]

bpy_class_object_list = tuple(bpy_class[1] for bpy_class in inspect.getmembers(bpy.types, inspect.isclass) if (bpy_class not in class_blacklist))
alx_class_object_list = tuple(alx_class[1] for file_batch in addon_files for alx_class in inspect.getmembers(eval(file_batch[1]), inspect.isclass) if issubclass(alx_class[1], bpy_class_object_list) and (not issubclass(alx_class[1], bpy.types.WorkSpaceTool)))

AlxClassQueue = alx_class_object_list

#################################################

import os
from os.path import dirname, realpath
from bpy.props import StringProperty, BoolProperty
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper, ExportHelper, orientation_helper, axis_conversion
from .drs_importer import load_bmg, DRS
from .drs_exporter import save_drs
from .drs_utility import load_drs

#################################################
# ALX MODULE AUTO-LOADER
import bpy
import os
import importlib

folder_blacklist = ["__pycache__", "alxoverhaul_updater"]
file_blacklist = ["__init__.py", "addon_updater_ops", "addon_updater.py", "Extras.py", ]

addon_folders = list([__path__[0]])
addon_folders.extend( [os.path.join(__path__[0], folder_name) for folder_name in os.listdir(__path__[0]) if ( os.path.isdir( os.path.join(__path__[0], folder_name) ) ) and (folder_name not in folder_blacklist) ] )

addon_files = [[folder_path, file_name[0:-3]] for folder_path in addon_folders for file_name in os.listdir(folder_path) if (file_name not in file_blacklist) and (file_name.endswith(".py"))]

for folder_file_batch in addon_files:
    if (os.path.basename(folder_file_batch[0]) == os.path.basename(__path__[0])):
        file = folder_file_batch[1]

        if (file not in locals()):
            import_line = f"from . import {file}"
            exec(import_line)
        else:
            reload_line = f"{file} = importlib.reload({file})"
            exec(reload_line)
    
    else:
        if (os.path.basename(folder_file_batch[0]) != os.path.basename(__path__[0])):
            file = folder_file_batch[1]

            if (file not in locals()):
                import_line = f"from . {os.path.basename(folder_file_batch[0])} import {file}"
                exec(import_line)
            else:
                reload_line = f"{file} = importlib.reload({file})"
                exec(reload_line)

import inspect

class_blacklist = ["PSA_UL_SequenceList"]

bpy_class_object_list = tuple(bpy_class[1] for bpy_class in inspect.getmembers(bpy.types, inspect.isclass) if (bpy_class not in class_blacklist))
alx_class_object_list = tuple(alx_class[1] for file_batch in addon_files for alx_class in inspect.getmembers(eval(file_batch[1]), inspect.isclass) if issubclass(alx_class[1], bpy_class_object_list) and (not issubclass(alx_class[1], bpy.types.WorkSpaceTool)))

AlxClassQueue = alx_class_object_list

#################################################

import os
from os.path import dirname, realpath
from bpy.props import StringProperty, BoolProperty
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper, ExportHelper, orientation_helper, axis_conversion
from .drs_importer import load_bmg, DRS
from .drs_exporter import save_drs
from .drs_utility import load_drs

is_dev_version = True
resource_dir = dirname(realpath(__file__)) + "/resources"

@bpy.app.handlers.persistent
def do_stuff(dummy):
    load_drs(DRS.operator, DRS.context, **DRS.keywords)

@orientation_helper(axis_forward='X', axis_up='-Y')
class ImportBFModel(bpy.types.Operator, ImportHelper):
	"""Import a Battleforge drs/bmg file"""
	bl_idname = "import_scene.drs"
	bl_label = "Import DRS/BMG"
	filename_ext = ".drs;.bmg"

	def execute(self, context):
		keywords: list = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		global_matrix = axis_conversion(from_forward=self.axis_forward, from_up=self.axis_up).to_4x4()
		keywords["global_matrix"] = global_matrix

		# Check if the file is a DRS or a BMG file
		if self.filepath.endswith(".drs"):
			
			# if keywords["clear_scene"]:
			# 	load_drs(DRS.operator, DRS.context, **DRS.keywords)
			# 	DRS.operator = self
			# 	DRS.keywords = keywords
			# 	DRS.context = context
			# 	bpy.ops.wm.open_mainfile(filepath=resource_dir + "/default_scene.blend")
			# else:
			load_drs(context, filepath=self.filepath)

			return {'FINISHED'}
		elif self.filepath.endswith(".bmg"):
			return load_bmg(self, context, **keywords)
		else:
			self.report({'ERROR'}, "Unsupported file type")
			return {'CANCELLED'}

class ExportBFModel(bpy.types.Operator, ExportHelper):
	"""Export a Battleforge drs/bmg file"""
	bl_idname = "export_scene.drs"
	bl_label = "Export DRS"
	filename_ext = ".drs"
	filter_glob: StringProperty(default="*.drs;*.bmg", options={'HIDDEN'}, maxlen=255) # type: ignore # ignore
	use_apply_transform : BoolProperty(name="Apply Transform", description="Workaround for object transformations importing incorrectly", default=True) # type: ignore # ignore
	split_mesh_by_uv_islands : BoolProperty(name="Split Mesh by UV Islands", description="Split mesh by UV islands", default=False) # type: ignore # ignore
	keep_debug_collections : BoolProperty(name="Keep Debug Collection", description="Keep debug collection in the scene", default=False) # type: ignore # ignore

	def execute(self, context):
		keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing"))
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

def AlxRegisterClassQueue():
    for AlxClass in AlxClassQueue:
        try:
            bpy.utils.register_class(AlxClass)
        except:
            try:
                bpy.utils.unregister_class(AlxClass)
                bpy.utils.register_class(AlxClass)
            except:
                pass

def AlxUnregisterClassQueue():
    for AlxClass in AlxClassQueue:
        try:
            bpy.utils.unregister_class(AlxClass)
        except:
            print("Can't Unregister", AlxClass)

def register():
	AlxRegisterClassQueue()

	bpy.utils.register_class(ImportBFModel)
	bpy.utils.register_class(ExportBFModel)
	bpy.utils.register_class(NewBFScene)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
	AlxUnregisterClassQueue()

	bpy.utils.unregister_class(ImportBFModel)
	bpy.utils.unregister_class(ExportBFModel)
	bpy.utils.unregister_class(NewBFScene)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
	register()
