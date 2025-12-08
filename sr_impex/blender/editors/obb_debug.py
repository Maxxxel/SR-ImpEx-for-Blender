import time
import bpy
from bpy.props import IntProperty

from sr_impex.utilities.drs_utility import (
    create_cgeo_obb_tree,
    create_unified_mesh,
    find_or_create_collection,
    get_collection,
    import_obb_tree,
    logger,
)


def _get_child_collection(parent: bpy.types.Collection | None, name: str) -> bpy.types.Collection | None:
    if not parent:
        return None
    # bpy child lookup may not support __contains__ reliably
    for child in parent.children:
        if child.name == name:
            return child
    return None


def _iter_children_recursive(col: bpy.types.Collection):
    stack = [col]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        yield current
        for ch in current.children:
            stack.append(ch)


def update_obb_debug_visibility(context: bpy.types.Context | None, target_depth: int) -> None:
    """Show only the requested OBB depth in the existing visualization, if present."""
    try:
        if not context or not getattr(context, "view_layer", None) or not getattr(context, "scene", None):
            return
        alc = context.view_layer.active_layer_collection
        if not alc or alc == context.scene.collection:
            return
        source_collection = getattr(alc, "collection", None)
        if not source_collection or not getattr(source_collection, "name", "").startswith("DRSModel_"):
            return

        debug_collection = _get_child_collection(source_collection, "Debug_Collection")
        if not debug_collection:
            return

        obb_root = _get_child_collection(debug_collection, "OBBTree_Hierarchy")
        if not obb_root:
            return

        def parse_depth(name: str) -> int | None:
            if "_Depth_" not in name:
                return None
            try:
                return int(name.rsplit("_Depth_", 1)[1])
            except Exception:
                return None

        clamped_depth = max(1, int(target_depth))
        
        # Collect all collections and objects first to avoid iterator invalidation
        collections_to_update = []
        for child in _iter_children_recursive(obb_root):
            # Validate the collection is still valid
            if not child or child.name not in bpy.data.collections:
                continue
            depth = parse_depth(child.name)
            
            # Collections: show if depth is None (root/special) or <= target depth
            # This keeps the hierarchy visible down to the target
            show_collection = depth is None or depth <= clamped_depth
            
            # Objects: show only if depth matches target or is the root (depth 0)
            show_objects = depth is None or depth == clamped_depth
            
            collections_to_update.append((child, show_collection, show_objects))
        
        # Now apply visibility changes
        for col, show_collection, show_objects in collections_to_update:
            try:
                # Double-check collection is still valid before modifying
                if col and col.name in bpy.data.collections:
                    col.hide_viewport = not show_collection
                    col.hide_render = not show_collection
                    # Process objects separately with validation
                    for obj in list(col.objects):
                        if obj and obj.name in bpy.data.objects:
                            obj.hide_viewport = not show_objects
                            obj.hide_render = not show_objects
            except (ReferenceError, AttributeError):
                # Skip invalid references
                continue
                
    except Exception as e:
        # Log errors for debugging but don't crash
        print(f"OBB visibility update error: {e}")
        import traceback
        traceback.print_exc()


def register_obb_debug_properties() -> None:
    """Register WindowManager properties for OBB debug controls."""

    def _on_depth_max(self, _context):
        # Clamp max depth value
        current_max = max(1, min(int(self.drs_obb_depth_max), 100))
        # Only update if it actually changed to avoid recursion
        if self.drs_obb_depth_max != current_max:
            self.drs_obb_depth_max = current_max
        
        # Ensure view depth doesn't exceed max depth
        if hasattr(self, "drs_obb_depth_view"):
            current_view = int(self.drs_obb_depth_view)
            if current_view > current_max:
                # This will trigger _on_view_depth, which is fine
                self.drs_obb_depth_view = current_max

    def _on_view_depth(self, context):
        # Don't modify the property value here - it causes recursive callbacks!
        # Clamping is handled by the property's min/max parameters
        depth_val = int(self.drs_obb_depth_view)

        def _deferred_apply():
            try:
                # Get fresh context for the timer callback
                ctx = bpy.context
                if ctx and ctx.view_layer and ctx.scene:
                    update_obb_debug_visibility(ctx, depth_val)
            except Exception as e:
                print(f"Deferred OBB visibility update failed: {e}")
            return None  # run once

        try:
            # Use a small delay to ensure Blender is in a stable state
            bpy.app.timers.register(_deferred_apply, first_interval=0.01)
        except Exception:
            # Fallback: don't apply immediately as it may cause crashes
            # Better to skip the update than crash Blender
            print("Warning: Could not register timer for OBB visibility update")

    for attr in ("drs_obb_depth_view", "drs_obb_depth_max"):
        try:
            delattr(bpy.types.WindowManager, attr)
        except Exception:
            pass

    bpy.types.WindowManager.drs_obb_depth_max = IntProperty(
        name="OBB Depth",
        description="Maximum depth to visualize (larger values may be slow)",
        default=5,
        min=1,
        max=100,
        update=_on_depth_max,
    )

    bpy.types.WindowManager.drs_obb_depth_view = IntProperty(
        name="View Depth",
        description="Show only this depth in the debug visualization",
        default=5,
        min=1,
        max=100,
        soft_max=100,
        update=_on_view_depth,
    )


def unregister_obb_debug_properties() -> None:
    """Unregister WindowManager properties for OBB debug controls."""

    for attr in ("drs_obb_depth_view", "drs_obb_depth_max"):
        if hasattr(bpy.types.WindowManager, attr):
            delattr(bpy.types.WindowManager, attr)


class DRS_OT_debug_obb_tree(bpy.types.Operator):
    """Calculates and visualizes an OBBTree for the selected collection's meshes."""

    bl_idname = "drs.debug_obb_tree"
    bl_label = "Debug OBBTree"
    bl_description = "Calculates a new OBBTree from the meshes in the active collection and visualizes it"

    def execute(self, context):
        start_time = time.time()
        active_layer_coll = context.view_layer.active_layer_collection
        if active_layer_coll is None or active_layer_coll == context.scene.collection:
            logger.log("Please select a valid DRS model collection in the Outliner.", "Error", "ERROR")
            logger.display()
            return {"CANCELLED"}

        source_collection = active_layer_coll.collection

        if not source_collection.name.startswith("DRSModel_"):
            logger.log(
                "The active collection must start with 'DRSModel_'.", "Error", "ERROR"
            )
            logger.display()
            return {"CANCELLED"}

        meshes_collection = get_collection(source_collection, "Meshes_Collection")
        if not meshes_collection:
            logger.log(
                f"Could not find a 'Meshes_Collection' within '{source_collection.name}'.",
                "Error",
                "ERROR",
            )
            logger.display()
            return {"CANCELLED"}

        mesh_objects = [obj for obj in meshes_collection.objects if obj.type == "MESH"]
        if not mesh_objects:
            logger.log(
                "No mesh objects found in 'Meshes_Collection'.", "Error", "ERROR"
            )
            logger.display()
            return {"CANCELLED"}

        unified_mesh = create_unified_mesh(meshes_collection)
        elapsed_time = time.time() - start_time
        logger.log(
            f"Unified mesh created with {len(unified_mesh.polygons)} polygons. Time taken: {elapsed_time:.2f} seconds.",
            "Info",
            "INFO",
        )
        cgeo_obb_tree = create_cgeo_obb_tree(unified_mesh)
        elapsed_time = time.time() - start_time
        logger.log(
            f"OBBTree created. Time taken: {elapsed_time:.2f} seconds.",
            "Info",
            "INFO",
        )

        debug_collection = find_or_create_collection(
            source_collection, "Debug_Collection"
        )
        wm = context.window_manager
        max_depth = int(getattr(wm, "drs_obb_depth_max", 5))
        max_depth = max(1, min(max_depth, 100))
        view_depth = int(getattr(wm, "drs_obb_depth_view", max_depth))
        view_depth = max(1, min(view_depth, max_depth))
        import_obb_tree(cgeo_obb_tree, debug_collection, max_depth, view_depth=view_depth)

        elapsed_time = time.time() - start_time
        logger.log(
            f"OBBTree calculation and visualization completed in {elapsed_time:.2f} seconds.",
            "Info",
            "INFO",
        )
        logger.display()

        return {"FINISHED"}


class DRS_PT_debug_tools(bpy.types.Panel):
    """Expose debug helpers in the DRS Editor side panel."""

    bl_label = "Debug Tools"
    bl_idname = "DRS_PT_debug_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        layer_col = context.view_layer.active_layer_collection
        if not layer_col or layer_col == context.scene.collection:
            return False
        col = layer_col.collection
        return bool(col and col.name.startswith("DRSModel_"))

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="OBB Tree", icon="OUTLINER_OB_EMPTY")
        wm = context.window_manager
        box.prop(wm, "drs_obb_depth_max", text="Max Depth")
        box.prop(wm, "drs_obb_depth_view", text="Show Depth")
        box.operator("drs.debug_obb_tree", text="Rebuild OBB Tree", icon="MOD_BOOLEAN")
