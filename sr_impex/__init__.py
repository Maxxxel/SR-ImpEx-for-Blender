# ----------------------------------------------------
# Auto-Update Integration: Import updater ops
# ----------------------------------------------------
import os
from os.path import dirname, realpath
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from sr_impex.core.profiler import print_profiling_report
from .blender.editors.obb_debug import (
    DRS_OT_debug_obb_tree,
    register_obb_debug_properties,
    unregister_obb_debug_properties,
)
from .utilities.drs_utility import (
    load_drs,
    save_drs,
    create_new_bf_scene,
)
from .utilities.bmg_utility import load_bmg, save_bmg
from .utilities.ska_utility import export_ska, get_actions
from .updater import addon_updater_ops
from .blender.editors import locator_editor
from .blender.editors import animation_set_editor
from .blender.editors import material_flow_editor
from .blender.editors import material_editor
from .blender import battleforge_preview
from .blender import asset_preferences
from .blender.editors import effect_set_editor
from .blender.editors import bmg_state_editor, building_editor
from .blender.editors import ska_editor
from .blender.editors import bms_editor
from .blender.editors import environment_cubemap_editor

bl_info = {
    "name": "SR-ImpEx",
    "author": "Maxxxel",
    "description": "Addon for importing and exporting Battleforge drs/bmg files.",
    "blender": (4, 5, 0),
    "version": (4, 0, 0),
    "location": "File > Import",
    "warning": "",
    "category": "Import-Export",
    "tracker_url": "",
}

IS_DEV_VERSION = False
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


MIP_MAP_ITEMS = [
    (
        "auto",
        "Auto",
        "Use texconv default mip generation (-m 0, full chain per texture)",
    ),
    (
        "none",
        "None",
        "Disable mip maps (-m 1, only top level)",
    ),
]
for _level in range(1, 21):
    MIP_MAP_ITEMS.append(
        (
            str(_level),
            f"Max {_level}",
            (
                f"Generate up to {_level} levels. Final value is clamped per image size "
                "(for example 256x256 allows up to 9 levels down to 1x1)."
            ),
        )
    )


_MENUES_ATTACHED = False


def _attach_menus_idempotent():
    global _MENUES_ATTACHED
    if _MENUES_ATTACHED:
        return
    # Remove old callbacks if they exist (safe if they don't)
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    # Append once
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    _MENUES_ATTACHED = True


def _detach_menus_safely():
    global _MENUES_ATTACHED
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    # pylint: disable=broad-exception-caught
    except Exception:
        pass
    _MENUES_ATTACHED = False


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
    skylords_root: StringProperty(
        name="Skylords Reborn Folder",
        description="Game installation; preview assets are read from Mods/Unpack and base/pak",
        subtype="DIR_PATH",
        default="",
        update=asset_preferences.changed,
    )  # type: ignore
    effects_folder: StringProperty(
        name="Effects Folder",
        description="Optional loose effect library, normally Mods/Unpack/bf1/gfx/effects; overrides game assets for Blender previews",
        subtype="DIR_PATH", default="",update=asset_preferences.changed,
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        addon_updater_ops.check_for_update_background()
        # Add path picker on top
        box = layout.box()
        box.label(text="Asset Library", icon="ASSET_MANAGER")
        box.prop(self, "skylords_root")
        box.prop(self, "effects_folder")
        box.operator('drs.effect_refresh_library', text='Refresh Effect Library', icon='FILE_REFRESH')
        # existing updater UI
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
        description="DRS model or BMG building file to import",
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
    import_s0_collision_shapes: BoolProperty(
        name="Import S0 Collision Shapes",
        description="Import collision shapes for S0 (undamaged) meshsets. S2 collision shapes are always imported as they differ from S0. BMG-level collision shapes apply to all S0 meshsets.",
        default=False,
    )  # type: ignore
    import_animation: BoolProperty(
        name="Import Animation", description="Import animation", default=True
    )  # type: ignore
    import_all_supported_animations: BoolProperty(
        name="Import all supported Animations",
        description="Import all supported animation files in the same folder as the model",
        default=False,
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
    import_environment_cubemap: BoolProperty(
        name="Import Environment Cubemap",
        description="Create an environment helper cube when an _env texture is present",
        default=True,
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
        name="[DEBUG] Import CGeoMesh (DRS only)",
        description="Import additional geometry mesh data.",
        default=False,
    )  # type: ignore
    import_obbtree: BoolProperty(
        name="[DEBUG] Import CGeoOBBTree (DRS only)",
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
        name="[DEBUG] Import MeshBoundingBox (DRS only)",
        description="Import additional axis-aligned bounding box data.",
        default=False,
    )  # type: ignore
    use_control_rig: BoolProperty(
        name="Use Control Rig for IK",
        description="Use a separate Control Rig for IK handling",
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
        layout.prop(self, "import_all_supported_animations")
        layout.prop(self, "smooth_animation")
        layout.prop(self, "import_ik_atlas")
        layout.prop(self, "use_control_rig")
        # Add a separator
        layout.separator()
        # Create a Modules Section
        layout.label(text="Modules Settings", icon="OBJECT_DATA")
        layout.prop(self, "import_collision_shape")
        layout.prop(self, "import_s0_collision_shapes")
        layout.prop(self, "import_modules")
        layout.prop(self, "import_construction")
        layout.prop(self, "import_debris")
        layout.prop(self, "import_environment_cubemap")
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
        keywords["import_s0_collision_shapes"] = self.import_s0_collision_shapes
        keywords["import_animation"] = self.import_animation
        keywords["import_all_supported_animations"] = (
            self.import_all_supported_animations
        )
        keywords["smooth_animation"] = self.smooth_animation
        keywords["import_ik_atlas"] = self.import_ik_atlas
        keywords["use_control_rig"] = self.use_control_rig
        keywords["import_modules"] = self.import_modules
        keywords["import_construction"] = self.import_construction
        keywords["import_debris"] = self.import_debris
        keywords["import_environment_cubemap"] = self.import_environment_cubemap

        if self.clear_scene:
            from .blender.effect_preview import clear as clear_effect_preview
            clear_effect_preview(context.scene)
            # Delete all collections
            for collection in bpy.data.collections:
                bpy.data.collections.remove(collection)
            # Also clean all actions
            for action in bpy.data.actions:
                bpy.data.actions.remove(action)
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete(use_global=False)
            # Purge unused data blocks
            bpy.ops.outliner.orphans_purge(do_recursive=True)

        # Check if the file is a DRS or a BMG file
        if self.filepath.endswith(".drs"):
            keywords.pop("import_debris")
            keywords.pop("import_construction")
            keywords.pop("import_s0_collision_shapes")
            load_drs(context, **keywords)
            print_profiling_report()
            return {"FINISHED"}
        elif self.filepath.endswith(".bmg"):
            keywords.pop("import_all_supported_animations")
            keywords.pop("import_modules")
            keywords.pop("import_environment_cubemap")
            load_bmg(context, **keywords)
            print_profiling_report()
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "Unsupported file type")
            return {"CANCELLED"}


class ExportDRSModel(bpy.types.Operator, ExportHelper):
    """Export a Battleforge drs file"""

    bl_idname: str = "export_scene.drs"
    bl_label: str = "Export DRS"
    filename_ext: str = ".drs"
    bl_description='Export the selected Skylords model and its textures; the model is detected from its mesh or collection'
    advanced_options: BoolProperty(name='Advanced Mesh Settings',default=False,options={'SKIP_SAVE'},
        description='Show mesh preparation and diagnostic options; the defaults suit most static objects')

    # this one needs to be named exactly 'filepath' for ExportHelper
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the DRS",
        maxlen=1024,
        subtype="FILE_PATH",
    )  # type: ignore
    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.drs;",
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
        default=False,
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
            ("AnimatedUnit", "Animated Unit", ""),
        ],
        default="StaticObjectNoCollision",
    )  # type: ignore
    export_all_ska_actions: BoolProperty(
        name="Export All SKA Actions",
        description="Export all SKA actions associated with the model",
        default=True,
    )  # type: ignore
    set_model_name_prefix: EnumProperty(
        name="Model Name Prefix",
        description="Set a prefix for the exported SKA actions",
        items=[
            ("none", "No Prefix", "Export SKA actions without any prefix: idle.ska"),
            ("model_name", "Model Name Prefix", "Prefix SKA actions with the model name: new_model_idle.ska"),
            ("folder_name", "Folder Name Prefix", "Prefix SKA actions with the folder name: new_model_folder_idle.ska"),
            ("keep_existing", "Keep Existing Prefix", "Keep existing prefixes of imported SKA actions: skel_human_2h_idle.ska"),
        ],
        default="none",
    )  # type: ignore
    auto_fix_quad_faces: BoolProperty(
        name="Auto-fix Quad Faces",
        description="Automatically fix quad faces that may cause issues in Battleforge",
        default=True,
    )  # type: ignore
    export_tangents: BoolProperty(
        name="[DEBUG] Export SKA Tangents",
        description="Export Hermite tangents for smooth interpolation. Disable for flat/stepped curves (debugging)",
        default=True,
    )  # type: ignore
    mip_maps: EnumProperty(
        name="Mip Maps",
        description=(
            "Mips are generated per image. Numeric modes are treated as a per-texture maximum "
            "and clamped to what that image can support down to 1x1"
        ),
        items=MIP_MAP_ITEMS,
        default="auto",
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export Settings", icon="EXPORT")
        layout.prop(self, "model_type")
        layout.prop(self, "mip_maps")
        layout.separator()
        if self.model_type.startswith('Animated'):
            layout.label(text="Animation Export", icon="ANIM_DATA")
            layout.prop(self, "export_all_ska_actions")
            if self.export_all_ska_actions:layout.prop(self, "set_model_name_prefix")
        layout.prop(self,'advanced_options',toggle=True)
        if self.advanced_options:
            layout.prop(self, "split_mesh_by_uv_islands")
            layout.prop(self, "flip_normals")
            layout.prop(self, "auto_fix_quad_faces")
            layout.prop(self, "keep_debug_collections")


    def invoke(self, context, event):
        from .utilities.artist_context import find_model
        root=find_model(context,kind='DRS')
        if root is None:
            self.report({'ERROR'},'Select a mesh belonging to a Skylords model before exporting.');return {'CANCELLED'}
        model_name=root.name.removeprefix('DRSModel_')
        collision=any(c.name.startswith('CollisionShapes_Collection') and any(o.type=='MESH' for o in c.all_objects) for c in root.children)
        animated=any(o.type=='ARMATURE' for o in root.all_objects)
        self.model_type='AnimatedUnit' if root.get('_sr_model_type')=='unit' else ('AnimatedObject' if animated else 'StaticObject')+('Collision' if collision else 'NoCollision')
        if not animated:self.export_all_ska_actions=False

        # Update the file name with the model name
        self.filepath = bpy.path.ensure_ext(model_name, ".drs")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing", "advanced_options"))
        keywords["split_mesh_by_uv_islands"] = self.split_mesh_by_uv_islands
        keywords["flip_normals"] = self.flip_normals
        keywords["keep_debug_collections"] = self.keep_debug_collections
        keywords["model_type"] = self.model_type
        keywords["export_all_ska_actions"] = self.export_all_ska_actions
        if not self.model_type.startswith('Animated'):keywords['export_all_ska_actions']=False
        keywords["set_model_name_prefix"] = self.set_model_name_prefix
        keywords["auto_fix_quad_faces"] = self.auto_fix_quad_faces
        keywords["export_tangents"] = self.export_tangents
        keywords["mip_maps"] = self.mip_maps

        # update model_name by file_path
        model_name = os.path.basename(self.filepath)
        # remove the extension
        model_name = os.path.splitext(model_name)[0]
        keywords["model_name"] = model_name

        self.filepath = bpy.path.ensure_ext(self.filepath, ".drs")

        result = save_drs(context, **keywords)
        if result == {"FINISHED"}:
            self.report({"INFO"}, "Export complete.")
        else:
            self.report({"ERROR"}, "Export failed. Check details in the Log..")

        print_profiling_report()

        # Purge unused data blocks
        bpy.ops.outliner.orphans_purge(do_recursive=True)

        return result


class ExportBMGModel(bpy.types.Operator, ExportHelper):
    """Export a Battleforge bmg file"""

    bl_idname: str = "export_scene.bmg"
    bl_label: str = "Export BMG"
    filename_ext: str = ".bmg"

    # this one needs to be named exactly 'filepath' for ExportHelper
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the BMG",
        maxlen=1024,
        subtype="FILE_PATH",
    )  # type: ignore
    filter_glob: StringProperty(
        # type: ignore # ignore
        default="*.bmg;",
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
        default=False,
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
            ("AUTO", "Preserve / Auto", "Preserve imported nodes or derive a new building layout"),
            ("StaticBuildingNoCollision", "Static Building (no collision)", "Export as static building without collision"),
            ("StaticBuildingCollision", "Static Building (with collision)", "Export as static building with collision"),
            ("AnimatedBuildingCollisionEffects", "Animated Building (with collision & effects)", "Export as animated building with collision and effects"),
            ("AnimatedBuildingCollisionNoEffects", "Animated Building (with collision, no effects)", "Export as animated building with collision but no effects"),
        ],
        default="AUTO",
    )  # type: ignore
    export_all_ska_actions: BoolProperty(
        name="Export All SKA Actions",
        description="Export all SKA actions associated with the model",
        default=True,
    )  # type: ignore
    set_model_name_prefix: EnumProperty(
        name="Model Name Prefix",
        description="Set a prefix for the exported SKA actions",
        items=[
            ("none", "No Prefix", "Export SKA actions without any prefix: idle.ska"),
            ("model_name", "Model Name Prefix", "Prefix SKA actions with the model name: new_model_idle.ska"),
            ("folder_name", "Folder Name Prefix", "Prefix SKA actions with the folder name: new_model_folder_idle.ska"),
            ("keep_existing", "Keep Existing Prefix", "Keep existing prefixes of imported SKA actions: skel_human_2h_idle.ska"),
        ],
        default="keep_existing",
    )  # type: ignore
    auto_fix_quad_faces: BoolProperty(
        name="Auto-fix Quad Faces",
        description="Automatically fix quad faces that may cause issues in Battleforge",
        default=True,
    )  # type: ignore
    mip_maps: EnumProperty(
        name="Mip Maps",
        description=(
            "Mips are generated per image. Numeric modes are treated as a per-texture maximum "
            "and clamped to what that image can support down to 1x1"
        ),
        items=MIP_MAP_ITEMS,
        default="auto",
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export Settings", icon="EXPORT")
        layout.prop(self, "model_type")
        layout.separator()
        layout.label(text="Mesh Export Settings", icon="MESH_CUBE")
        layout.prop(self, "split_mesh_by_uv_islands")
        layout.prop(self, "flip_normals")
        layout.prop(self, "auto_fix_quad_faces")
        layout.prop(self, "mip_maps")
        layout.separator()
        layout.label(text="SKA Export Settings", icon="ANIM_DATA")
        layout.prop(self, "export_all_ska_actions")
        layout.prop(self, "set_model_name_prefix")
        layout.label(text="Temporary export meshes are cleaned up automatically.")


    def invoke(self, context, event):
        from .utilities.building_export import find_building
        try:
            root = find_building(context)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.filepath = bpy.path.ensure_ext(root.name.removeprefix("DRSModel_"), ".bmg")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        self.filepath = os.path.splitext(self.filepath)[0] + ".bmg"
        keywords: list = self.as_keywords(ignore=("filter_glob", "check_existing"))
        keywords["split_mesh_by_uv_islands"] = self.split_mesh_by_uv_islands
        keywords["flip_normals"] = self.flip_normals
        keywords["keep_debug_collections"] = self.keep_debug_collections
        keywords["model_type"] = self.model_type
        keywords["export_all_ska_actions"] = self.export_all_ska_actions
        keywords["set_model_name_prefix"] = self.set_model_name_prefix
        keywords["auto_fix_quad_faces"] = self.auto_fix_quad_faces
        keywords["mip_maps"] = self.mip_maps

        # update model_name by file_path
        model_name = os.path.basename(self.filepath)
        # remove the extension
        model_name = os.path.splitext(model_name)[0]
        keywords["model_name"] = model_name


        result = save_bmg(context, **keywords)
        if result == {"FINISHED"}:
            self.report({"INFO"}, "Export successfull.")
        else:
            self.report({"ERROR"}, "Export failed. Check details in the Log..")

        print_profiling_report()


        return result


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

    export_tangents: BoolProperty(
        name="Export Tangents",
        description="Export tangents for the animation (if available)",
        default=False,
    )  # type: ignore

    def invoke(self, context, event):
        # Retrieve the active collection from the active layer collection
        active_coll = context.view_layer.active_layer_collection.collection
        if not active_coll.name.startswith("DRSModel_"):
            self.report({"ERROR"}, "You haven't selected a DRS model collection")
            return {"CANCELLED"}

        armature = next((o for o in active_coll.objects if o.type == "ARMATURE"), None)
        armature_coll = None
        if armature is None:
            # Check for an Armature_Collection inside the active collection
            armature_coll = active_coll.children.get("Armature_Collection")
            if armature_coll:
                # Be sure not to take the Control_Rig Armature, but the actual Armature*
                armature = next(
                    (o for o in armature_coll.objects if o.type == "ARMATURE" and not o.name.startswith("Control_Rig")), None
                )
            else:
                self.report({"ERROR"}, "No armature collection found in the selected collection")
                return {"CANCELLED"}

        if armature is None:
            self.report({"ERROR"}, "No armature found in the selected collection")
            return {"CANCELLED"}

        for obj in context.view_layer.objects:
            obj.select_set(False)
        armature.select_set(True)
        context.view_layer.objects.active = armature

        bpy.ops.object.mode_set(mode="OBJECT")

        actions = get_actions(armature_coll)
        if not actions:
            self.report({"ERROR"}, "No actions found in the selected armature")
            return {"CANCELLED"}

        # Get the first valid action
        first_action = next((act for act in actions if act != "None"), None)
        if first_action is None:
            self.report({"ERROR"}, "No valid actions found in the selected armature")
            return {"CANCELLED"}
        self.action = first_action
        self.filepath = bpy.path.ensure_ext(self.action, ".ska")

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Export Settings", icon="EXPORT")
        layout.prop(self, "action", text="Action")
        layout.prop(self, "export_tangents", text="Export Tangents")

    def execute(self, context):
        export_ska(context, self.filepath, self.action, export_tangents=self.export_tangents)

        return {"FINISHED"}


class NewBFScene(bpy.types.Operator):
    """Create a new Battleforge scene with selectable type and collision support"""

    bl_idname = "scene.new_bf_scene"
    bl_label = "Set Up Skylords Model"
    bl_description = "Create model folders and GameOrientation in this scene; optionally include selected meshes without moving them"
    bl_options = {"REGISTER", "UNDO"}

    scene_type: EnumProperty(  # type: ignore
        name="Scene Type",
        description="Select the type of scene to create",
        items=[
            ("object", "Static Object", "Create a static object scene"),
            ("animated_object", "Animated Object", "Create folders for an animated object; add its rig and animations separately"),
            ("unit", "Unit", "Create folders for a unit; add its rig and animations separately"),
        ],
        default="object",
    )

    collision_support: BoolProperty(  # type: ignore
        name="Collision Support",
        description="Include collision shape collections",
        default=False,
    )
    model_name: StringProperty(name="Model Name",default="object_custom",
        description="Name used for the model collection and suggested export filename")
    use_selected: BoolProperty(name="Include Selected Meshes",default=True,
        description="Move selected meshes into this model and parent them to GameOrientation while keeping their visible position")

    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self,width=380)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scene_type")
        layout.prop(self, "model_name")
        layout.prop(self, "use_selected")
        layout.prop(self, "collision_support")

    def execute(self, context):
        import re
        name=re.sub(r'[^a-zA-Z0-9_]+','_',self.model_name.strip()).strip('_')
        if not name:
            self.report({'ERROR'},'Enter a model name');return {'CANCELLED'}
        selected=[o for o in context.selected_objects if o.type=='MESH'] if self.use_selected else []
        for collection in bpy.data.collections:
            if collection.name.startswith('DRSModel_') and any(o.name in collection.all_objects for o in selected):
                self.report({'ERROR'},'These meshes already belong to a model. Select a new mesh or turn off Include Selected Meshes.');return {'CANCELLED'}
        root=create_new_bf_scene(self.scene_type,self.collision_support,name)
        go=next(o for o in root.objects if o.name.startswith('GameOrientation'))
        meshes=next(c for c in root.children if c.name.startswith('Meshes_Collection'))
        for obj in selected:
            world=obj.matrix_world.copy()
            for collection in list(obj.users_collection):collection.objects.unlink(obj)
            meshes.objects.link(obj);obj.parent=go;obj.matrix_world=world
        root['_sr_format']='DRS';root['_sr_model_type']=self.scene_type
        from .utilities.artist_context import find_model
        for branch in context.view_layer.layer_collection.children:
            if branch.collection==root:context.view_layer.active_layer_collection=branch;break
        self.report({"INFO"}, "Model setup created. Select a mesh to create its DRS material.")
        return {"FINISHED"}


class DRS_PT_ModelSetup(bpy.types.Panel):
    bl_label='Model Setup';bl_category='DRS Editor';bl_space_type='VIEW_3D';bl_region_type='UI';bl_order=-100
    def draw(self,context):
        from .utilities.artist_context import find_model
        root=find_model(context)
        if root: self.layout.label(text=root.name.removeprefix('DRSModel_'),icon='OUTLINER_COLLECTION')
        self.layout.operator('scene.new_bf_scene',text='Set Up Model',icon='ADD')
        if root:self.layout.operator('export_scene.drs',text='Export DRS',icon='EXPORT')


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
        text="Battleforge Model (.drs/.bmg) - "
        + (IS_DEV_VERSION and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )
    self.layout.operator(
        NewBFScene.bl_idname,
        text="Set Up Skylords Model - "
        + (IS_DEV_VERSION and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )


def menu_func_export(self, _context):
    self.layout.operator(
        ExportDRSModel.bl_idname,
        text="Battleforge Object/Unit (.drs) - "
        + (IS_DEV_VERSION and "DEV" or "")
        + " v"
        + str(bl_info["version"][0])
        + "."
        + str(bl_info["version"][1])
        + "."
        + str(bl_info["version"][2]),
    )
    self.layout.operator(
        ExportBMGModel.bl_idname,
        text="Battleforge Building (.bmg) - "
        + (IS_DEV_VERSION and "DEV" or "")
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
        + (IS_DEV_VERSION and "DEV" or "")
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
    bpy.utils.register_class(ExportDRSModel)
    bpy.utils.register_class(ExportBMGModel)
    bpy.utils.register_class(ExportSKAFile)
    bpy.utils.register_class(NewBFScene)
    bpy.utils.register_class(DRS_PT_ModelSetup)
    bpy.utils.register_class(ShowMessagesOperator)
    _attach_menus_idempotent()
    bpy.utils.register_class(MyAddonPreferences)
    asset_preferences.register()
    bpy.utils.register_class(DRS_OT_debug_obb_tree)
    register_obb_debug_properties()
    locator_editor.register()
    material_flow_editor.register()
    material_editor.register()
    battleforge_preview.register()
    animation_set_editor.register()
    effect_set_editor.register()
    bmg_state_editor.register()
    building_editor.register()
    ska_editor.register()
    bms_editor.register()
    environment_cubemap_editor.register()


def unregister():
    asset_preferences.unregister()
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(ImportBFModel)
    bpy.utils.unregister_class(ExportDRSModel)
    bpy.utils.unregister_class(ExportBMGModel)
    bpy.utils.unregister_class(ExportSKAFile)
    bpy.utils.unregister_class(NewBFScene)
    bpy.utils.unregister_class(DRS_PT_ModelSetup)
    bpy.utils.unregister_class(ShowMessagesOperator)
    _detach_menus_safely()
    bpy.utils.unregister_class(MyAddonPreferences)
    bpy.utils.unregister_class(DRS_OT_debug_obb_tree)
    unregister_obb_debug_properties()
    locator_editor.unregister()
    battleforge_preview.unregister()
    material_editor.unregister()
    material_flow_editor.unregister()
    animation_set_editor.unregister()
    effect_set_editor.unregister()
    bms_editor.unregister()
    ska_editor.unregister()
    building_editor.unregister()
    bmg_state_editor.unregister()
    environment_cubemap_editor.unregister()
