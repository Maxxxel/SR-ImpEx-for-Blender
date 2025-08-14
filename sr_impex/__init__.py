# ----------------------------------------------------
# Auto-Update Integration: Import updater ops
# ----------------------------------------------------
import os
from os.path import dirname, realpath
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .sr_impex_socket import (
    DRS_PT_SocketPanel,
    StartSocketSyncOperator,
    StopSocketSyncOperator,
    send_path_to_gui,
)
from .drs_utility import (
    load_drs,
    save_drs,
    load_bmg,
    create_new_bf_scene,
    # DRS_OT_debug_obb_tree,
)
from .ska_utility import export_ska, get_actions
from . import addon_updater_ops
from . import locator_editor
from . import animation_set_editor

bl_info = {
    "name": "SR-ImpEx",
    "author": "Maxxxel",
    "description": "Addon for importing and exporting Battleforge drs/bmg files.",
    "blender": (4, 4, 0),
    "version": (3, 0, 1),
    "location": "File > Import",
    "warning": "",
    "category": "Import-Export",
    "tracker_url": "",
}

is_dev_version = False
resource_dir = dirname(realpath(__file__)) + "/resources"


def update_filename(self, context):
    if self.action and self.action != "None":
        # Ensure we are currently in FILE_BROWSER space
        if context.space_data and context.space_data.type == "FILE_BROWSER":
            params = context.space_data.params
            if params:
                params.filename = bpy.path.ensure_ext(self.action, ".ska")


def available_actions(_self, _context):
    actions = get_actions()  # Your function that returns a list of action names

    # If no actions are available, provide a default fallback
    if not actions:
        return [("None", "No actions available", "")]

    # Otherwise, dynamically construct the EnumProperty items
    return [(act, act, "") for act in actions]


_menus_attached = False


def _attach_menus_idempotent():
    global _menus_attached
    if _menus_attached:
        return
    # Remove old callbacks if they exist (safe if they don't)
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    # pylint: disable=broad-exception-caught
    except Exception:
        pass
    # Append once
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    _menus_attached = True


def _detach_menus_safely():
    global _menus_attached
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    # pylint: disable=broad-exception-caught
    except Exception:
        pass
    _menus_attached = False


# ----------------------------------------------------
# Addon Preferences: A nice menu for update settings
# ----------------------------------------------------
class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )  # type: ignore
    updater_interval_months: IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )  # type: ignore
    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
    )  # type: ignore
    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )  # type: ignore
    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )  # type: ignore

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
    # this one needs to be named exactly 'filepath' for ExportHelper
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the SKA",
        maxlen=1024,
        subtype="FILE_PATH",
    )  # type: ignore
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
    import_animation: BoolProperty(
        name="Import Animation", description="Import animation", default=True
    )  # type: ignore
    import_animation_type: EnumProperty(
        name="Type",
        description="Select the animation type to import",
        items=[
            ("FRAMES", "Frames", "Import animation in frames"),
            ("SECONDS", "Seconds", "Import animation in seconds"),
        ],
        default="SECONDS",
    )  # type: ignore
    import_animation_fps: IntProperty(
        name="Animation FPS",
        description="FPS for the imported animation",
        default=30,
        min=1,
        max=100,
    )  # type: ignore
    smooth_animation: BoolProperty(
        name="Import Animation Smoothing",
        description="Import animation smoothing",
        default=True,
    )  # type: ignore
    import_ik_atlas: BoolProperty(
        name="Import IK Atlas (Experimental)",
        description="Import IK Atlas",
        default=True,
    )  # type: ignore
    import_debris: BoolProperty(
        name="Import Debris", description="Import debris for bmg files", default=True
    )  # type: ignore
    import_modules: BoolProperty(
        name="Import Modules/Locators",
        description="Import modules and locators for drs files",
        default=True,
    )  # type: ignore
    import_construction: BoolProperty(
        name="Import Construction",
        description="Import construction for bmg files",
        default=True,
    )  # type: ignore
    import_geomesh: BoolProperty(
        name="[DEBUG] Import CGeoMesh",
        description="Import additional geometry mesh data.",
        default=False,
    )  # type: ignore
    import_obbtree: BoolProperty(
        name="[DEBUG] Import CGeoOBBTree",
        description="Import additional OBB tree data.",
        default=False,
    )  # type: ignore
    limit_obb_depth: IntProperty(
        name="[DEBUG] Limit OBB Depth",
        description="Limit the depth of the OBB tree.",
        default=5,
        min=1,
        max=1000,
    )  # type: ignore
    import_bb: BoolProperty(
        name="[DEBUG] Import MeshBoundingBox",
        description="Import additional axis-aligned bounding box data.",
        default=False,
    )  # type: ignore

    def draw(self, context):
        # Auto-Update Integration: Addon Updater by using addon_updater_ops.check_for_update_background(context) in the beginning of the function and addon_updater_ops.update_notice_box_ui(self, context) at the end of the function
        addon_updater_ops.check_for_update_background()
        layout = self.layout
        layout.label(text="Import Settings", icon="IMPORT")
        layout.prop(self, "clear_scene")
        layout.prop(self, "apply_transform")
        # Add a separator
        layout.separator()
        # Create an Animation Section
        layout.label(text="Animation Settings", icon="ANIM_DATA")
        layout.prop(self, "import_animation")
        layout.prop(self, "import_animation_type")
        layout.prop(self, "import_animation_fps")
        layout.prop(self, "smooth_animation")
        layout.prop(self, "import_ik_atlas")
        # Add a separator
        layout.separator()
        # Create a Modules Section
        layout.label(text="Modules Settings", icon="OBJECT_DATA")
        layout.prop(self, "import_collision_shape")
        layout.prop(self, "import_modules")
        layout.prop(self, "import_construction")
        layout.prop(self, "import_debris")
        # Add a separator
        layout.separator()
        # Debug Section
        layout.label(text="Debug Settings", icon="CONSOLE")
        layout.prop(self, "import_geomesh")
        layout.prop(self, "import_obbtree")
        layout.prop(self, "limit_obb_depth")
        layout.prop(self, "import_bb")
        # layout.prop(self, "create_size_reference")
        if addon_updater_ops.updater.update_ready is True:
            layout.label(
                text="Update available! Please check the preferences.",
                icon="INFO",
            )
        layout.separator()
        addon_updater_ops.update_notice_box_ui(self, context)

    def execute(self, context):
        keywords: list = self.as_keywords(
            ignore=("filter_glob", "clear_scene", "create_size_reference")
        )
        keywords["import_collision_shape"] = self.import_collision_shape
        keywords["import_animation"] = self.import_animation
        keywords["import_animation_type"] = self.import_animation_type
        keywords["import_animation_fps"] = self.import_animation_fps
        keywords["smooth_animation"] = self.smooth_animation
        keywords["import_ik_atlas"] = self.import_ik_atlas
        keywords["import_modules"] = self.import_modules
        keywords["import_construction"] = self.import_construction
        keywords["import_debris"] = self.import_debris

        if self.clear_scene:
            # Delete all collections
            for collection in bpy.data.collections:
                bpy.data.collections.remove(collection)
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete(use_global=False)
            # Purge unused data blocks
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        # Check if the file is a DRS or a BMG file
        if self.filepath.endswith(".drs"):
            keywords.pop("import_debris")
            keywords.pop("import_construction")
            load_drs(context, **keywords)
            send_path_to_gui(self.filepath)
            return {"FINISHED"}
        elif self.filepath.endswith(".bmg"):
            keywords.pop("import_modules")
            load_bmg(context, **keywords)
            send_path_to_gui(self.filepath)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "Unsupported file type")
            return {"CANCELLED"}


class ExportBFModel(bpy.types.Operator, ExportHelper):
    """Export a Battleforge drs/bmg file"""

    bl_idname: str = "export_scene.drs"
    bl_label: str = "Export DRS"
    filename_ext: str = ".drs"

    # this one needs to be named exactly 'filepath' for ExportHelper
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the SKA",
        maxlen=1024,
        subtype="FILE_PATH",
    )  # type: ignore
    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.drs;*.bmg",
        options={"HIDDEN"},
        maxlen=255,
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
    model_type: EnumProperty(
        name="Model Type",
        description="Select the model type",
        items=[
            ("StaticObjectNoCollision", "Static Object (no collision)", ""),
            ("StaticObjectCollision", "Static Object (with collision)", ""),
            ("AnimatedObjectNoCollision", "Animated Object (no collision)", ""),
            ("AnimatedObjectCollision", "Animated Object (with collision)", ""),
        ],
        default="StaticObjectNoCollision",
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export Settings", icon="EXPORT")
        layout.prop(self, "split_mesh_by_uv_islands")
        layout.prop(self, "flip_normals")
        layout.prop(self, "keep_debug_collections")
        layout.prop(self, "model_type")

    def invoke(self, context, event):
        # Retrieve the active collection from the active layer collection
        active_coll = context.view_layer.active_layer_collection.collection
        coll_name = active_coll.name

        # Strip off the "DRSModel_" prefix if present
        if coll_name.startswith("DRSModel_"):
            model_name = coll_name[9:]
        else:
            model_name = "you havent selected a DRS model collection"

        # Update the file name with the model name
        self.filepath = bpy.path.ensure_ext(model_name, ".drs")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing"))
        keywords["split_mesh_by_uv_islands"] = self.split_mesh_by_uv_islands
        keywords["flip_normals"] = self.flip_normals
        keywords["keep_debug_collections"] = self.keep_debug_collections
        keywords["model_type"] = self.model_type

        # update model_name by file_path
        model_name = os.path.basename(self.filepath)
        # remove the extension
        model_name = os.path.splitext(model_name)[0]
        keywords["model_name"] = model_name

        self.filepath = bpy.path.ensure_ext(self.filepath, ".drs")

        save_drs(context, **keywords)

        if self.model_type in {"AnimatedObjectNoCollision", "AnimatedObjectCollision"}:
            # Get all Action
            all_actions = get_actions()
            export_folder = os.path.dirname(self.filepath)

            # We only allow actions with the same name as the export animation name or _idle
            nbr_actions = len(all_actions)
            if nbr_actions == 1:
                export_ska(
                    context, os.path.join(export_folder, all_actions[0]), all_actions[0]
                )
            else:
                for action_name in all_actions:
                    action_name_without_ska = action_name.replace(".ska", "")
                    if (
                        action_name_without_ska == model_name
                        or action_name_without_ska.find("_idle") != -1
                    ):

                        export_ska(
                            context,
                            os.path.join(export_folder, action_name),
                            action_name,
                        )

        # Purge unused data blocks
        bpy.ops.outliner.orphans_purge(do_recursive=True)

        return {"FINISHED"}


class ExportSKAFile(bpy.types.Operator, ExportHelper):
    """Export a Battleforge ska animation file"""

    bl_idname: str = "export_animation.ska"
    bl_label: str = "Export SKA"
    bl_options = {"REGISTER"}
    filename_ext: str = ".ska"

    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.ska",
        options={"HIDDEN"},
        maxlen=255,
    )

    # this one needs to be named exactly 'filepath' for ExportHelper
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the SKA",
        maxlen=1024,
        subtype="FILE_PATH",
    )  # type: ignore

    # Create an enum with all the actions for the selected object
    action: EnumProperty(
        name="Action",
        description="Select the action to export",
        items=available_actions,  # Note: Pass the function, not the call result!
        update=update_filename,
    )  # type: ignore

    def invoke(self, context, event):
        # Retrieve the active collection from the active layer collection
        active_coll = context.view_layer.active_layer_collection.collection
        if not active_coll.name.startswith("DRSModel_"):
            self.report({"ERROR"}, "You haven't selected a DRS model collection")
            return {"CANCELLED"}

        armature = next((o for o in active_coll.objects if o.type == "ARMATURE"), None)
        if armature is None:
            self.report({"ERROR"}, "No armature found in the selected collection")
            return {"CANCELLED"}

        for obj in context.view_layer.objects:
            obj.select_set(False)
        armature.select_set(True)
        context.view_layer.objects.active = armature

        bpy.ops.object.mode_set(mode="OBJECT")

        actions = get_actions()
        if not actions:
            self.report({"ERROR"}, "No actions found in the selected armature")
            return {"CANCELLED"}

        self.action = actions[0]
        self.filepath = bpy.path.ensure_ext(self.action, ".ska")

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export Settings", icon="EXPORT")
        layout.prop(self, "action", text="Action")

    def execute(self, context):
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
    _attach_menus_idempotent()
    bpy.utils.register_class(MyAddonPreferences)
    bpy.utils.register_class(DRS_PT_SocketPanel)
    bpy.utils.register_class(StartSocketSyncOperator)
    bpy.utils.register_class(StopSocketSyncOperator)
    # bpy.utils.register_class(DRS_OT_debug_obb_tree)
    locator_editor.register()
    animation_set_editor.register()


def unregister():
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(ImportBFModel)
    bpy.utils.unregister_class(ExportBFModel)
    bpy.utils.unregister_class(ExportSKAFile)
    bpy.utils.unregister_class(NewBFScene)
    bpy.utils.unregister_class(ShowMessagesOperator)
    _detach_menus_safely()
    bpy.utils.unregister_class(MyAddonPreferences)
    bpy.utils.unregister_class(DRS_PT_SocketPanel)
    bpy.utils.unregister_class(StartSocketSyncOperator)
    bpy.utils.unregister_class(StopSocketSyncOperator)
    # bpy.utils.unregister_class(DRS_OT_debug_obb_tree)
    locator_editor.unregister()
    animation_set_editor.unregister()
