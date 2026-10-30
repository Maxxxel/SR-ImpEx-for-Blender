import os
from datetime import datetime
import bpy

from sr_impex.utilities.drs_utility import (
    ENV_TEXTURE_SUFFIX,
    create_environment_cubemap_helper,
    convert_image_to_dds,
    remove_environment_cubemap_helper,
    get_environment_cubemap_image,
    resource_dir,
)


def _find_parent_collection(
    root: bpy.types.Collection,
    target: bpy.types.Collection,
) -> bpy.types.Collection | None:
    for child in root.children:
        if child == target:
            return root
        found = _find_parent_collection(child, target)
        if found is not None:
            return found
    return None


def _find_drs_model_from_object(context: bpy.types.Context) -> bpy.types.Collection | None:
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None

    for start_col in getattr(obj, "users_collection", []) or []:
        col = start_col
        for _ in range(32):
            if col is None:
                break
            if col.name.startswith("DRSModel_"):
                return col
            col = _find_parent_collection(context.scene.collection, col)
    return None


def _find_active_drs_model_collection(context: bpy.types.Context) -> bpy.types.Collection | None:
    from_active_object = _find_drs_model_from_object(context)
    if from_active_object is not None:
        return from_active_object

    layer_col = context.view_layer.active_layer_collection
    if not layer_col:
        return None

    active = layer_col.collection
    if active and active.name.startswith("DRSModel_"):
        return active

    for top in context.scene.collection.children:
        if not top.name.startswith("DRSModel_"):
            continue
        if top == active:
            return top
        try:
            for sub in top.children_recursive:
                if sub == active:
                    return top
        except Exception:
            pass
    return None


def _default_earth_cubemap_path() -> str:
    return os.path.join(resource_dir, "assets", "earth-cubemap.dds")


def _has_env_cubemap(source_collection: bpy.types.Collection) -> bool:
    return get_environment_cubemap_image(source_collection) is not None


def _is_material_editor_mesh_selected(context: bpy.types.Context) -> bool:
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return False
    return any(
        ("Meshes_Collection" in col.name) or (col.name == "GroundDecal_Collection")
        for col in getattr(obj, "users_collection", []) or []
    )


def _debug_export_dir() -> str:
    # resource_dir points to <addon>/sr_impex/resources.
    # Debug exports go to <addon>/sr_impex/debug.
    return os.path.join(os.path.dirname(resource_dir), "debug")


class DRS_OT_init_environment_cubemap(bpy.types.Operator):
    bl_idname = "drs.init_environment_cubemap"
    bl_label = "Init Cubemap"
    bl_description = "Create/update the environment cubemap helper using the bundled earth cubemap"

    def execute(self, context):
        source_collection = _find_active_drs_model_collection(context)
        if source_collection is None:
            self.report({"ERROR"}, "Select a DRSModel_* collection first.")
            return {"CANCELLED"}

        default_env = _default_earth_cubemap_path()
        helper = create_environment_cubemap_helper(
            source_collection,
            image_path=default_env if os.path.exists(default_env) else None,
        )
        if helper is None:
            self.report({"ERROR"}, "Failed to create environment cubemap helper.")
            return {"CANCELLED"}

        self.report({"INFO"}, "Environment cubemap helper initialized.")
        return {"FINISHED"}


class DRS_OT_remove_environment_cubemap(bpy.types.Operator):
    bl_idname = "drs.remove_environment_cubemap"
    bl_label = "Remove Cubemap"
    bl_description = "Remove the environment cubemap helper collection from the active DRS model"

    def execute(self, context):
        source_collection = _find_active_drs_model_collection(context)
        if source_collection is None:
            self.report({"ERROR"}, "Select a DRSModel_* collection first.")
            return {"CANCELLED"}

        removed = remove_environment_cubemap_helper(source_collection)
        if not removed:
            self.report({"INFO"}, "No environment cubemap helper found.")
            return {"CANCELLED"}

        self.report({"INFO"}, "Environment cubemap helper removed.")
        return {"FINISHED"}


class DRS_OT_material_add_environment_cubemap(bpy.types.Operator):
    bl_idname = "drs.material_add_environment_cubemap"
    bl_label = "Add Cubemap"
    bl_description = "Add or reset the model environment cubemap using the bundled earth cubemap"

    def execute(self, context):
        source_collection = _find_active_drs_model_collection(context)
        if source_collection is None:
            self.report({"ERROR"}, "Active object is not part of a DRSModel_* collection.")
            return {"CANCELLED"}

        default_env = _default_earth_cubemap_path()
        helper = create_environment_cubemap_helper(
            source_collection,
            image_path=default_env if os.path.exists(default_env) else None,
        )
        if helper is None:
            self.report({"ERROR"}, "Failed to add environment cubemap.")
            return {"CANCELLED"}

        from .material_editor import modern, sync_material
        obj=context.object
        if obj and modern(obj.active_material):
            material=obj.active_material
            image=get_environment_cubemap_image(source_collection)
            for row in material.drs_settings.textures:
                if 'environment' in row.name.lower():row.image=image;row.enabled=True
            sync_material(material,obj)
        self.report({"INFO"}, "Environment cubemap added to model.")
        return {"FINISHED"}


class DRS_OT_material_remove_environment_cubemap(bpy.types.Operator):
    bl_idname = "drs.material_remove_environment_cubemap"
    bl_label = "Remove Cubemap"
    bl_description = "Remove the environment cubemap from the active DRS model"

    def execute(self, context):
        source_collection = _find_active_drs_model_collection(context)
        if source_collection is None:
            self.report({"ERROR"}, "Active object is not part of a DRSModel_* collection.")
            return {"CANCELLED"}

        removed = remove_environment_cubemap_helper(source_collection)
        if not removed:
            self.report({"INFO"}, "No environment cubemap found on this model.")
            return {"CANCELLED"}

        self.report({"INFO"}, "Environment cubemap removed from model.")
        return {"FINISHED"}


class DRS_OT_material_debug_export_environment_cubemap(bpy.types.Operator):
    bl_idname = "drs.material_debug_export_environment_cubemap"
    bl_label = "Debug Export Cubemap"
    bl_description = "Export the assigned cubemap to the plugin debug folder using texassemble/texconv"

    def execute(self, context):
        source_collection = _find_active_drs_model_collection(context)
        if source_collection is None:
            self.report({"ERROR"}, "Active object is not part of a DRSModel_* collection.")
            return {"CANCELLED"}

        env_image = get_environment_cubemap_image(source_collection)
        if env_image is None:
            self.report({"ERROR"}, "No cubemap assigned to this model.")
            return {"CANCELLED"}

        debug_dir = _debug_export_dir()
        os.makedirs(debug_dir, exist_ok=True)

        model_tag = bpy.path.clean_name(source_collection.name.replace("DRSModel_", ""))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{model_tag}_debug_env_{timestamp}"

        ret_code, stdout, stderr = convert_image_to_dds(
            env_image,
            output_name,
            debug_dir,
            dxt_format="DXT5",
            extra_args=None,
            file_ending=ENV_TEXTURE_SUFFIX,
            mip_maps="auto",
        )
        if ret_code != 0:
            log_path = os.path.join(debug_dir, output_name + "_error.log")
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("Cubemap debug export failed\n")
                    f.write(f"Return code: {ret_code}\n")
                    f.write(f"Model collection: {source_collection.name}\n")
                    f.write(f"Image: {getattr(env_image, 'name', '<unknown>')}\n")
                    f.write(
                        f"Image size: {int(env_image.size[0])}x{int(env_image.size[1])}\n"
                    )
                    f.write(f"Output DDS: {os.path.join(debug_dir, output_name + '.dds')}\n")
                    f.write("\n--- STDERR ---\n")
                    f.write((stderr or "<empty>").strip() + "\n")
                    f.write("\n--- STDOUT ---\n")
                    f.write((stdout or "<empty>").strip() + "\n")
            except Exception:
                log_path = ""

            err = (stderr or stdout or "Conversion failed.").strip()
            if log_path:
                self.report(
                    {"ERROR"},
                    f"Cubemap debug export failed. Details: {log_path}",
                )
            else:
                self.report({"ERROR"}, f"Cubemap debug export failed: {err[:220]}")
            return {"CANCELLED"}

        out_path = os.path.join(debug_dir, output_name + ".dds")
        self.report({"INFO"}, f"Cubemap exported: {out_path}")
        return {"FINISHED"}


def environment_controls_relevant(context):
    obj=context.object
    if not obj or obj.type!='MESH' or not hasattr(obj,'drs_material'):return False
    from .material_editor import modern, schema
    material=obj.active_material
    if modern(material):
        definition=schema(name=material.drs_settings.material_type)
        flag=next((f for f in definition['flags'] if f['name']=='UseEnvironmentMap'),None)
        return bool(flag and (int(obj.drs_material.bool_parameter)&(1<<flag['bit'])))
    return bool(int(obj.drs_material.bool_parameter)&(1<<18))


def draw_environment_settings(layout,context):
    if not environment_controls_relevant(context):return
    source=_find_active_drs_model_collection(context)
    if source is None:return
    from .material_editor import modern
    material=context.object.active_material
    debug=modern(material) and material.drs_settings.technical_controls
    env_rows=[r for r in material.drs_settings.textures if 'environment' in r.name.lower()] if modern(material) else []
    # The material image picker is already the primary artist control.
    assigned=any(r.enabled and r.image for r in env_rows)
    if assigned and not debug:return
    box=layout.box();box.label(text='Environment Map',icon='WORLD')
    has_env=_has_env_cubemap(source)
    if not assigned:
        box.operator('drs.material_add_environment_cubemap',text='Use Bundled Environment',icon='WORLD')
    if debug:
        box.label(text='Model environment: '+('Assigned' if has_env else 'Not assigned'))
        if has_env:box.operator('drs.material_remove_environment_cubemap',text='Remove Model Environment',icon='X')
        if has_env:box.operator('drs.material_debug_export_environment_cubemap',text='Export Environment Diagnostic',icon='EXPORT')


_CLASSES = (
    DRS_OT_init_environment_cubemap,
    DRS_OT_remove_environment_cubemap,
    DRS_OT_material_add_environment_cubemap,
    DRS_OT_material_remove_environment_cubemap,
    DRS_OT_material_debug_export_environment_cubemap,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
