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
import os
from os.path import dirname, realpath
import importlib  # pylint: disable=unused-import
import inspect
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .drs_utility import load_drs, save_drs, load_bmg, create_new_bf_scene
from .ska_utility import export_ska, get_actions

bl_info = {
    "name": "Battleforge Tools",
    "author": "Maxxxel",
    "description": "Addon for importing and exporting Battleforge drs/bmg files",
    "blender": (4, 3, 0),
    "version": (2, 6, 0),
    "location": "File > Import",
    "warning": "",
    "category": "Import-Export",
    "tracker_url": "",
}

#################################################
# ALX MODULE AUTO-LOADER
folder_blacklist = ["__pycache__", "alxoverhaul_updater"]
file_blacklist = [
    "__init__.py",
    "addon_updater_ops",
    "addon_updater.py",
    "Extras.py",
]

addon_folders = list([__path__[0]])
addon_folders.extend(
    [
        os.path.join(__path__[0], folder_name)
        for folder_name in os.listdir(__path__[0])
        if (os.path.isdir(os.path.join(__path__[0], folder_name)))
        and (folder_name not in folder_blacklist)
    ]
)

addon_files = [
    [folder_path, file_name[0:-3]]
    for folder_path in addon_folders
    for file_name in os.listdir(folder_path)
    if (file_name not in file_blacklist) and (file_name.endswith(".py"))
]

for folder_file_batch in addon_files:
    if os.path.basename(folder_file_batch[0]) == os.path.basename(__path__[0]):
        file = folder_file_batch[1]

        if file not in locals():
            IMPORT_LINE = f"from . import {file}"
            exec(IMPORT_LINE)
        else:
            RELOAD_LINE = f"{file} = importlib.reload({file})"
            exec(RELOAD_LINE)

    else:
        if os.path.basename(folder_file_batch[0]) != os.path.basename(__path__[0]):
            file = folder_file_batch[1]

            if file not in locals():
                IMPORT_LINE = (
                    f"from . {os.path.basename(folder_file_batch[0])} import {file}"
                )
                exec(IMPORT_LINE)
            else:
                RELOAD_LINE = f"{file} = importlib.reload({file})"
                exec(RELOAD_LINE)

class_blacklist = ["PSA_UL_SequenceList"]

bpy_class_object_list = tuple(
    bpy_class[1]
    for bpy_class in inspect.getmembers(bpy.types, inspect.isclass)
    if bpy_class not in class_blacklist
)
alx_class_object_list = tuple(
    alx_class[1]
    for file_batch in addon_files
    for alx_class in inspect.getmembers(eval(file_batch[1]), inspect.isclass)
    if issubclass(alx_class[1], bpy_class_object_list)
    and (not issubclass(alx_class[1], bpy.types.WorkSpaceTool))
)

AlxClassQueue = alx_class_object_list
#################################################

is_dev_version = False
resource_dir = dirname(realpath(__file__)) + "/resources"
temporary_file_path = ""


class ImportBFModel(bpy.types.Operator, ImportHelper):
    """Import a Battleforge drs/bmg file"""

    bl_idname = "import_scene.drs"
    bl_label = "Import DRS/BMG"
    filename_ext = ".drs;.bmg"
    filter_glob: StringProperty(
        default="*.drs;*.bmg", options={"HIDDEN"}, maxlen=255
    )  # type: ignore
    apply_transform: BoolProperty(
        name="Apply Transform",
        description="Workaround for object transformations importing incorrectly",
        default=True,
    )  # type: ignore
    clear_scene: BoolProperty(
        name="Clear Scene", description="Clear the scene before importing", default=True
    )  # type: ignore
    create_size_reference: BoolProperty(
        name="Create Size References",
        description="Creates multiple size references in the scene",
        default=False,
    )  # type: ignore
    import_collision_shape: BoolProperty(
        name="Import Collision Shape",
        description="Import collision shapes",
        default=True,
    )  # type: ignore
    # use_animation_smoothing: BoolProperty(name="Use Animation Smoothing", description="Use animation smoothing", default=True) # type: ignore
    import_animation: BoolProperty(
        name="Import Animation", description="Import animation", default=True
    )  # type: ignore
    import_debris: BoolProperty(
        name="Import Debris", description="Import debris for bmg files", default=True
    )  # type: ignore
    import_modules: BoolProperty(
        name="Import Modules", description="Import modules for drs files", default=True
    )  # type: ignore
    import_construction: BoolProperty(
        name="Import Construction",
        description="Import construction for bmg files",
        default=True,
    )  # type: ignore

    def execute(self, context):
        global temporary_file_path  # pylint: disable=global-statement
        temporary_file_path = self.filepath
        keywords: list = self.as_keywords(
            ignore=("filter_glob", "clear_scene", "create_size_reference")
        )
        keywords["import_collision_shape"] = self.import_collision_shape
        keywords["import_animation"] = self.import_animation
        keywords["import_modules"] = self.import_modules
        keywords["import_construction"] = self.import_construction
        keywords["import_debris"] = self.import_debris

        if self.clear_scene:
            # Delete all collections
            for collection in bpy.data.collections:
                bpy.data.collections.remove(collection)
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete(use_global=False)

        # Check if the file is a DRS or a BMG file
        if self.filepath.endswith(".drs"):
            keywords.pop("import_debris", None)
            keywords.pop("import_construction", None)
            load_drs(context, **keywords)
            return {"FINISHED"}
        elif self.filepath.endswith(".bmg"):
            keywords.pop("import_modules", None)
            load_bmg(context, **keywords)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "Unsupported file type")
            return {"CANCELLED"}


class ExportBFModel(bpy.types.Operator, ExportHelper):
    """Export a Battleforge drs/bmg file"""

    bl_idname = "export_scene.drs"
    bl_label = "Export DRS"
    filename_ext = ".drs"

    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.drs;*.bmg",
        options={"HIDDEN"},
        maxlen=255,
    )
    use_apply_transform: BoolProperty(
        # type: ignore # ignore
        name="Apply Transform",
        description="Workaround for object transformations importing incorrectly",
        default=True,
    )
    split_mesh_by_uv_islands: BoolProperty(
        # type: ignore # ignore
        name="Split Mesh by UV Islands",
        description="Split mesh by UV islands",
        default=True,
    )
    flip_normals: BoolProperty(
        # type: ignore # ignore
        name="Flip Normals",
        description="Flip normals if you see them 'blue' in Blender",
        default=True,
    )
    keep_debug_collections: BoolProperty(
        # type: ignore # ignore
        name="Keep Debug Collection",
        description="Keep debug collection in the scene",
        default=False,
    )
    export_animation: BoolProperty(
        # type: ignore # ignore
        name="Export Animation",
        description="Export animation",
        default=False,
    )
    automatic_naming: BoolProperty(
        name="Automatic Naming",
        description="Names the exported file automatically based on the selection and model name, else the name from the save-path is taken.",
        default=True,
    )  # type: ignore # ignore
    model_type: EnumProperty(
        name="Model Type",
        description="Select the model type",
        items=[
            ("AnimatedUnit", "Animated Unit", ""),
            ("building", "Building", ""),
            (
                # type: ignore # ignore
                "StaticObjectNoCollision",
                "Static Object (no collision)",
                "",
            ),
            ("StaticObjectCollision", "Static Object (with collision)", ""),
        ],
        default="StaticObjectNoCollision",
    )

    def execute(self, context):
        keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing"))
        keywords["use_apply_transform"] = self.use_apply_transform
        keywords["split_mesh_by_uv_islands"] = self.split_mesh_by_uv_islands
        keywords["flip_normals"] = self.flip_normals
        keywords["keep_debug_collections"] = self.keep_debug_collections
        keywords["export_animation"] = self.export_animation
        keywords["automatic_naming"] = self.automatic_naming
        save_drs(context, **keywords)
        # test_export(context, **keywords)
        return {"FINISHED"}


def update_filename(self, context):
    if self.action and self.action != "None":
        # Ensure we are currently in FILE_BROWSER space
        if context.space_data and context.space_data.type == "FILE_BROWSER":
            params = context.space_data.params
            if params:
                params.filename = bpy.path.ensure_ext(self.action, ".ska")


def available_actions(self, context):
    actions = get_actions()  # Your function that returns a list of action names

    # If no actions are available, provide a default fallback
    if not actions:
        print("No actions available")
        return [("None", "No actions available", "")]

    # Otherwise, dynamically construct the EnumProperty items
    return [(act, act, "") for act in actions]


class ExportSKAFile(bpy.types.Operator, ExportHelper):
    """Export a Battleforge ska animation file"""

    bl_idname = "export_animation.ska"
    bl_label = "Export SKA"
    filename_ext = ".ska"

    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.ska",
        options={"HIDDEN"},
        maxlen=255,
    )

    # Create an enum with all the actions for the selected object
    action: EnumProperty(
        name="Action",
        description="Select the action to export",
        items=available_actions,  # Note: Pass the function, not the call result!
        update=update_filename,
    )

    def invoke(self, context, event):
        actions = get_actions()
        if actions:
            self.action = actions[0]
            self.filepath = bpy.path.ensure_ext(self.action, ".ska")
        else:
            self.filepath = "untitled.ska"

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing"))

        export_ska(context, **keywords)
        return {"FINISHED"}


class NewBFScene(bpy.types.Operator, ImportHelper):
    """Create a new Battleforge scene with selectable type and collision support"""

    bl_idname = "scene.new_bf_scene"
    bl_label = "New Battleforge Scene"
    bl_options = {"REGISTER", "UNDO"}

    scene_type: EnumProperty(  # type: ignore
        name="Scene Type",
        description="Select the type of scene to create",
        items=[
            ("object", "Static Object", "Create a static object scene"),
            ("object", "Animated Object", "Create an animated object scene"),
        ],
        default="object",
    )

    collision_support: BoolProperty(  # type: ignore
        name="Collision Support",
        description="Include collision shape collections",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scene_type")
        layout.prop(self, "collision_support")

    def execute(self, context):
        create_new_bf_scene(self.scene_type, self.collision_support)
        self.report({"INFO"}, "New Battleforge scene created.")
        return {"FINISHED"}


class ShowMessagesOperator(bpy.types.Operator):
    """Display collected messages in a popup dialog."""

    bl_idname = "my_category.show_messages"
    bl_label = "Messages"
    bl_options = {"REGISTER", "INTERNAL"}

    messages: StringProperty()  # type: ignore

    def execute(self, context):
        # Optional actions upon confirmation
        return {"FINISHED"}

    def invoke(self, context, event):
        width = 800
        return context.window_manager.invoke_popup(self, width=width)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        for message in self.messages.split("\n"):
            col.label(text=message)


def menu_func_import(self, _context):
    self.layout.operator(
        ImportBFModel.bl_idname,
        text="Battleforge (.drs) - "
        + (is_dev_version and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )
    self.layout.operator(
        NewBFScene.bl_idname,
        text="New Battleforge Scene - "
        + (is_dev_version and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )


def menu_func_export(self, _context):
    self.layout.operator(
        ExportBFModel.bl_idname,
        text="Battleforge (.drs) - "
        + (is_dev_version and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )
    self.layout.operator(
        ExportSKAFile.bl_idname,
        text="Battleforge Animation (.ska) - "
        + (is_dev_version and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )


def alx_register_class_queue():
    for alx_class in AlxClassQueue:
        try:
            bpy.utils.register_class(alx_class)
        except Exception as e:  # pylint: disable=broad-except
            print("[ERROR #1] Can't Register", alx_class, e, "Type:", type(e))
            try:
                bpy.utils.unregister_class(alx_class)
                bpy.utils.register_class(alx_class)
            except Exception as e2:  # pylint: disable=broad-except
                print("[ERROR #2] Can't Re-Register", alx_class, e2, "Type:", type(e2))


def alx_unregister_class_queue():
    for alx_class in AlxClassQueue:
        try:
            bpy.utils.unregister_class(alx_class)
        except Exception as e:  # pylint: disable=broad-except
            print("Can't Unregister", alx_class, e, "Type:", type(e))


def register():
    alx_register_class_queue()
    bpy.utils.register_class(ImportBFModel)
    bpy.utils.register_class(ExportBFModel)
    bpy.utils.register_class(ExportSKAFile)
    bpy.utils.register_class(NewBFScene)
    bpy.utils.register_class(ShowMessagesOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    alx_unregister_class_queue()
    bpy.utils.unregister_class(ImportBFModel)
    bpy.utils.unregister_class(ExportBFModel)
    bpy.utils.unregister_class(ExportSKAFile)
    bpy.utils.unregister_class(NewBFScene)
    bpy.utils.unregister_class(ShowMessagesOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
