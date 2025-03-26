import os
from os.path import dirname, realpath
import importlib  # pylint: disable=unused-import
import fnmatch
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .drs_utility import load_drs, save_drs, load_bmg, create_new_bf_scene
from .ska_utility import export_ska, get_actions

bl_info = {
    "name": "SR-ImpEx",
    "author": "Maxxxel",
    "description": "Addon for importing and exporting Battleforge drs/bmg files.",
    "blender": (4, 3, 0),
    "version": (2, 7, 1),
    "location": "File > Import",
    "warning": "",
    "category": "Import-Export",
    "tracker_url": "",
}

is_dev_version = False
resource_dir = dirname(realpath(__file__)) + "/resources"
temporary_file_path = ""


# ----------------------------------------------------
# Auto-Update Integration: Import updater ops
# ----------------------------------------------------
from . import addon_updater_ops


# ----------------------------------------------------
# Addon Preferences: A nice menu for update settings
# ----------------------------------------------------
class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )
    updater_interval_months: IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )
    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
    )
    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )
    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )

    def draw(self, context):
        layout = self.layout
        # Create a 'Check for Update' button
        addon_updater_ops.check_for_update_background()
        addon_updater_ops.update_settings_ui(self, context)
        addon_updater_ops.update_notice_box_ui(self, context)


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
    import_animation_type: EnumProperty(  # type: ignore
        name="Animation Type",
        description="Select the animation type to import",
        items=[
            ("FRAMES", "Frames", "Import animation in frames"),
            ("SECONDS", "Seconds", "Import animation in seconds"),
        ],
        default="FRAMES",
    )
    import_animation_fps: IntProperty(  # type: ignore
        name="Animation FPS",
        description="FPS for the imported animation",
        default=30,
        min=1,
        max=120,
    )
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
        keywords["import_animation_type"] = self.import_animation_type
        keywords["import_animation_fps"] = self.import_animation_fps
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

        export_ska(context, self.filepath, self.action)
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


def register():
    addon_updater_ops.register(bl_info)
    bpy.utils.register_class(ImportBFModel)
    bpy.utils.register_class(ExportBFModel)
    bpy.utils.register_class(ExportSKAFile)
    bpy.utils.register_class(NewBFScene)
    bpy.utils.register_class(ShowMessagesOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.utils.register_class(MyAddonPreferences)


def unregister():
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(ImportBFModel)
    bpy.utils.unregister_class(ExportBFModel)
    bpy.utils.unregister_class(ExportSKAFile)
    bpy.utils.unregister_class(NewBFScene)
    bpy.utils.unregister_class(ShowMessagesOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(MyAddonPreferences)


def export_install_package() -> None:
    # I want to zip everything inside the src folder to the root of the project named SR-ImpEx-for-Blender-{version}.zip
    # I also want to choose what not to zip, following the .gitignore file
    import zipfile  # pylint: disable=import-outside-toplevel

    # Get the current version
    current_version = (
        f"{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"
    )

    # Get the root and source paths
    root_path = os.path.join(dirname(realpath(__file__)), "../")
    source_path = os.path.join(root_path, "sr_impex/")
    destination_path = os.path.join(
        root_path, f"SR-ImpEx-for-Blender-{current_version}.zip"
    )

    # Read ignore list from .gitignore
    with open(os.path.join(root_path, ".gitignore"), "r") as file:
        ignore_list = [
            line.strip() for line in file if line.strip() and not line.startswith("#")
        ]

    # Create the zip file
    with zipfile.ZipFile(destination_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            for file in files:
                full_path = os.path.join(root, file)
                # Calculate relative path from the project root
                rel_path = os.path.relpath(full_path, root_path)

                # Determine whether to skip the file based on .gitignore rules
                skip = False
                # Simple fnmatch matching: remove a leading "/" from each pattern
                for pattern in ignore_list:
                    pattern = pattern.lstrip("/")
                    if fnmatch.fnmatch(rel_path, pattern):
                        skip = True
                        break

                if skip:
                    print(f"Skipping {rel_path}")
                    continue

                # Add file to zip using the relative path
                zipf.write(full_path, rel_path)

    print(f"Package created: {destination_path}")


# Only enable this for export of the zip package for a new release.
# if True:
#     export_install_package()
