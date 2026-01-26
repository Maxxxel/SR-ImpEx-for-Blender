"""
BMG Building State Editor

UI panel and operators for managing building mesh states (S0, S2, debris).
Allows switching between undamaged, damaged, and destruction states.
"""

import json
import math

import bpy
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, EnumProperty, FloatProperty

MESHGRID_BLOB_KEY = "sr_impex_meshgrid_blob"

def switch_meshset_state(meshset_collection: bpy.types.Collection, target_state: str):
    """
    Switch which state is visible/active for editing in a MeshSet.

    Args:
        meshset_collection: The MeshSet_N collection
        target_state: One of 'S0', 'S2', 'S2_with_debris', 'S3_destroyed', 'all_states'
    """
    def show_collection_recursive(col):
        """Recursively show a collection and all its children"""
        col.hide_viewport = False
        col.hide_render = False
        for child in col.children:
            show_collection_recursive(child)

    # Find States_Collection (may have suffix like .001 if renamed by Blender)
    states_col = None
    for child in meshset_collection.children:
        if child.name.startswith("States_Collection"):
            states_col = child
            break

    if not states_col:
        print(f"[BMG State] No States_Collection found in {meshset_collection.name}")
        return

    print(f"[BMG State] Switching {meshset_collection.name} to {target_state}")
    print(f"[BMG State] States_Collection children: {[c.name for c in states_col.children]}")

    # First, make States_Collection itself visible (parent must be visible)
    states_col.hide_viewport = False

    # Hide all child states first
    for col in states_col.children_recursive:
        col.hide_viewport = True
        col.hide_render = True

    # Show requested state(s)
    if target_state == "S0":
        for child in states_col.children:
            if child.name.startswith("S0_Undamaged"):
                show_collection_recursive(child)
                break

    elif target_state == "S2":
        for child in states_col.children:
            if child.name.startswith("S2_Damaged"):
                show_collection_recursive(child)
                break

    elif target_state == "S2_with_debris":
        # Show S2 damaged state
        for child in states_col.children:
            if child.name.startswith("S2_Damaged"):
                print(f"[BMG State] Showing S2_Damaged: {child.name}")
                show_collection_recursive(child)
                break
        # Show S2 debris
        for child in states_col.children:
            if child.name.startswith("Debris_Collection"):
                print(f"[BMG State] Found Debris_Collection: {child.name}")
                print(f"[BMG State] Debris children: {[c.name for c in child.children]}")
                child.hide_viewport = False  # Make Debris_Collection itself visible
                child.hide_render = False
                for debris_col in child.children:
                    if debris_col.name.startswith("S2_Debris"):
                        print(f"[BMG State] Showing S2_Debris: {debris_col.name}")
                        show_collection_recursive(debris_col)
                        print(f"[BMG State] S2_Debris visibility: viewport={not debris_col.hide_viewport}, render={not debris_col.hide_render}")
                        break
                break

    elif target_state == "S3_destroyed":
        for child in states_col.children:
            if child.name.startswith("Debris_Collection"):
                print(f"[BMG State] Found Debris_Collection for S3: {child.name}")
                child.hide_viewport = False  # Make Debris_Collection itself visible
                child.hide_render = False
                for debris_col in child.children:
                    print(f"[BMG State] Showing debris: {debris_col.name}")
                    show_collection_recursive(debris_col)
                    print(f"[BMG State] Debris visibility after show: viewport={not debris_col.hide_viewport}, render={not debris_col.hide_render}")
                break

    elif target_state == "all_states":
        # Show everything for editing
        states_col.hide_viewport = False
        for col in states_col.children_recursive:
            col.hide_viewport = False

    # Update active marker
    for obj in meshset_collection.objects:
        if obj.type == 'EMPTY' and "active_state" in obj:
            obj["active_state"] = target_state


def _iter_bmg_models():
    """Yield DRSModel collections that contain MeshSetGrid children."""
    for col in bpy.data.collections:
        if not col.name.startswith("DRSModel_"):
            continue
        if any(child.name.startswith("MeshSetGrid_") for child in col.children_recursive):
            yield col


def _collect_child_collections(prefix: str) -> list[bpy.types.Collection]:
    matches: list[bpy.types.Collection] = []
    for model in _iter_bmg_models():
        for child in model.children_recursive:
            if child.name.startswith(prefix):
                matches.append(child)
    return matches


def _set_visibility(collections: list[bpy.types.Collection], visible: bool) -> None:
    for col in collections:
        col.hide_viewport = not visible
        col.hide_render = not visible


def _tag_viewports() -> None:
    ctx = bpy.context
    screen = getattr(ctx, "screen", None) if ctx else None
    if not screen:
        return
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _get_show_collision_shapes(_self) -> bool:
    cols = _collect_child_collections("CollisionShapes_Collection")
    if not cols:
        return False
    return any(not col.hide_viewport for col in cols)


def _set_show_collision_shapes(_self, value: bool) -> None:
    _set_visibility(_collect_child_collections("CollisionShapes_Collection"), value)
    _tag_viewports()


def _get_show_slocators(_self) -> bool:
    cols = _collect_child_collections("SLocators_Collection")
    if not cols:
        return False
    return any(not col.hide_viewport for col in cols)


def _set_show_slocators(_self, value: bool) -> None:
    _set_visibility(_collect_child_collections("SLocators_Collection"), value)
    _tag_viewports()


def _find_game_orientation(model_collection: bpy.types.Collection) -> bpy.types.Object | None:
    """Return the GameOrientation helper inside the given model collection if present."""
    for obj in model_collection.objects:
        if obj.name.startswith("GameOrientation"):
            return obj
    return None


def _ensure_meshgrid_collection(model_collection: bpy.types.Collection) -> tuple[bpy.types.Collection, str]:
    """Find or create the visual grid collection, named alongside the real MeshSetGrid_* collection."""
    base_grid_name = None
    for child in model_collection.children:
        if child.name.startswith("MeshSetGrid_"):
            base_grid_name = child.name
            break
    base_grid_name = base_grid_name or "MeshSetGrid_0"
    vis_name = f"{base_grid_name}_GridVis"

    for child in model_collection.children:
        if child.name == vis_name:
            return child, base_grid_name

    grid_col = bpy.data.collections.new(vis_name)
    model_collection.children.link(grid_col)
    return grid_col, base_grid_name


def _cleanup_grid_objects(grid_collection: bpy.types.Collection) -> None:
    """Remove existing grid objects (and orphaned meshes) before rebuilding."""
    for obj in list(grid_collection.objects):
        mesh_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)


def _get_grid_fill_material() -> bpy.types.Material:
    """Get or create the shared semi-transparent fill material for occupied cells."""
    mat_name = "BMG_MeshGrid_Fill"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = False
        mat.diffuse_color = (0.12, 0.65, 0.25, 0.35)  # rgba
        mat.blend_method = "BLEND"
        mat.shadow_method = "NONE"
    return mat


def _create_cell_mesh(name: str, size: float, height: float = 0.0) -> bpy.types.Object:
    """Create a square cell mesh; if height>0, build a cube with that height."""
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    half = size * 0.5
    if height > 0:
        h = height
        verts = [
            (-half, -half, 0.0),
            (half, -half, 0.0),
            (half, half, 0.0),
            (-half, half, 0.0),
            (-half, -half, h),
            (half, -half, h),
            (half, half, h),
            (-half, half, h),
        ]
        faces = [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
    else:
        verts = [
            (-half, -half, 0.0),
            (half, -half, 0.0),
            (half, half, 0.0),
            (-half, half, 0.0),
        ]
        faces = [(0, 1, 2, 3)]

    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.display_type = "WIRE"
    obj.show_in_front = True
    return obj


def _build_meshgrid_display(model_collection: bpy.types.Collection) -> bpy.types.Collection | None:
    """Materialize the MeshSetGrid cells as wireframe meshes under the model collection."""
    raw_blob = model_collection.get(MESHGRID_BLOB_KEY)
    if not raw_blob:
        return None

    try:
        blob = json.loads(raw_blob)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[BMG MeshGrid] Failed to parse mesh grid blob: {exc}")
        return None

    # Blob can come from bmg_utility (rows/columns) or drs_utility (grid_width/grid_height)
    width_raw = blob.get("grid_width", blob.get("columns", 0))
    height_raw = blob.get("grid_height", blob.get("rows", 0))
    width = int(width_raw or 0)
    height = int(height_raw or 0)
    cols = width * 2 + 1
    rows = height * 2 + 1
    if cols <= 0 or rows <= 0:
        return None

    step = float(blob.get("module_distance", 2.0) or 2.0)
    rotation = math.radians(float(blob.get("grid_rotation", blob.get("orientation", 0)) or 0)) + math.radians(180.0)
    cells = blob.get("cells", [])

    grid_collection, base_grid_name = _ensure_meshgrid_collection(model_collection)
    _cleanup_grid_objects(grid_collection)

    game_orientation = _find_game_orientation(model_collection)

    # Create a root empty so rotation is applied once to the whole grid (avoids overlapping rotated cells)
    root_name = f"{base_grid_name}_GridRoot"
    root_obj = bpy.data.objects.new(root_name, None)
    root_obj.empty_display_type = "PLAIN_AXES"
    root_obj.rotation_euler[2] = rotation
    if game_orientation:
        root_obj.parent = game_orientation
        root_obj.matrix_parent_inverse = game_orientation.matrix_world.inverted()
    grid_collection.objects.link(root_obj)
    base_x = -((cols - 1) * step) * 0.5
    base_y = ((rows - 1) * step) * 0.5

    for idx in range(min(len(cells), rows * cols) if cells else rows * cols):
        col_idx = idx % cols
        row_idx = idx // cols
        x = base_x + col_idx * step
        y = base_y - row_idx * step

        grid_x = col_idx - width
        grid_y = height - row_idx

        meshset_name = f"MeshSet_{idx}"
        name = f"{meshset_name}_GridCell_x{grid_x}_y{grid_y}"
        has_mesh = bool(cells[idx]["has_mesh_set"]) if idx < len(cells) else False
        mesh_object_name = ""
        if idx < len(cells):
            mesh_object_name = cells[idx].get("mesh_object_name", "") or ""
        mesh_obj = bpy.data.objects.get(mesh_object_name) if mesh_object_name else None
        height = 10.0 if has_mesh else 0.0
        obj = _create_cell_mesh(name, step, height)
        obj.parent = root_obj
        obj.location = (x, y, 0.0)
        obj["grid_cell_index"] = idx
        obj["meshset_name"] = meshset_name
        obj["grid_coord"] = (grid_x, grid_y)
        obj["grid_has_mesh_set"] = int(has_mesh)
        if mesh_object_name:
            obj["mesh_object_name"] = mesh_object_name

        if has_mesh:
            obj.display_type = "SOLID"
            obj.show_in_front = True
            obj.color = (0.12, 0.65, 0.25, 0.55)  # viewport tint
            obj.active_material = _get_grid_fill_material()

        grid_collection.objects.link(obj)

        if mesh_obj:
            obj.hide_viewport = mesh_obj.hide_viewport
            obj.hide_render = mesh_obj.hide_render

    return grid_collection


def _iter_vis_grid_collections() -> list[bpy.types.Collection]:
    cols: list[bpy.types.Collection] = []
    for model in _iter_bmg_models():
        for child in model.children:
            if child.name.endswith("_GridVis"):
                cols.append(child)
    return cols


def _iter_grid_cell_objects():
    for col in _iter_vis_grid_collections():
        for obj in col.objects:
            yield obj


def _sync_grid_cell_mesh_visibility(_depsgraph):
    wm = getattr(bpy.context, "window_manager", None)
    if wm and not getattr(wm, "bmg_show_meshgrid", True):
        return
    for cell in _iter_grid_cell_objects():
        mesh_name = cell.get("mesh_object_name")
        if not mesh_name:
            continue
        mesh_obj = bpy.data.objects.get(mesh_name)
        if not mesh_obj:
            continue
        if mesh_obj.hide_viewport != cell.hide_viewport:
            mesh_obj.hide_viewport = cell.hide_viewport
        if mesh_obj.hide_render != cell.hide_viewport:
            mesh_obj.hide_render = cell.hide_viewport


def _read_meshgrid_rotation_degrees() -> float | None:
    """Return the first available mesh grid rotation in degrees, if any."""
    for model in _iter_bmg_models():
        raw_blob = model.get(MESHGRID_BLOB_KEY)
        if not raw_blob:
            continue
        try:
            blob = json.loads(raw_blob)
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        rot_val = blob.get("grid_rotation", blob.get("orientation"))
        if rot_val is None:
            continue
        try:
            return float(rot_val)
        except (TypeError, ValueError):
            continue
    return None


def _get_meshgrid_rotation(_self) -> float:
    rotation_val = _read_meshgrid_rotation_degrees()
    return float(rotation_val) if rotation_val is not None else 0.0


def _set_meshgrid_rotation(_self, value: float) -> None:
    show_grid = getattr(getattr(bpy.context, "window_manager", None), "bmg_show_meshgrid", False)
    for model in _iter_bmg_models():
        raw_blob = model.get(MESHGRID_BLOB_KEY)
        if not raw_blob:
            continue
        try:
            blob = json.loads(raw_blob)
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        blob["grid_rotation"] = float(value)
        blob["orientation"] = float(value)
        model[MESHGRID_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)

        vis_col = _build_meshgrid_display(model)
        if vis_col:
            vis_col.hide_viewport = not show_grid
            vis_col.hide_render = not show_grid
    _tag_viewports()


def _get_show_meshgrid(_self) -> bool:
    cols = _iter_vis_grid_collections()
    if not cols:
        return False
    return any(not col.hide_viewport for col in cols)


def _set_show_meshgrid(_self, value: bool) -> None:
    for model in _iter_bmg_models():
        if value:
            _build_meshgrid_display(model)
        for child in model.children:
            if child.name.endswith("_GridVis"):
                child.hide_viewport = not value
                child.hide_render = not value
    _tag_viewports()

class BMG_OT_SwitchMeshState(Operator):
    """Switch the visible state of a MeshSet"""
    bl_idname = "bmg.switch_mesh_state"
    bl_label = "Switch Mesh State"
    bl_options = {'REGISTER', 'UNDO'}

    state: EnumProperty(
        name="State",
        description="Which state to display",
        items=[
            ('S0', "S0 - Undamaged", "Show undamaged building state"),
            ('S2', "S2 - Damaged", "Show damaged building state"),
            ('S2_with_debris', "S2 + Debris", "Show damaged state with debris"),
            ('S3_destroyed', "S3 - Destroyed", "Show only debris (destroyed state)"),
            ('all_states', "All States", "Show all states (for editing)"),
        ],
        default='S0'
    )

    @classmethod
    def poll(cls, context):
        """Only enable if a MeshSet collection is selected or active"""
        if context.collection:
            return context.collection.name.startswith("MeshSet_")
        if context.active_object and context.active_object.users_collection:
            for col in context.active_object.users_collection:
                if col.name.startswith("MeshSet_"):
                    return True
        return False

    def execute(self, context):
        # Try to get MeshSet collection from context
        meshset_collection = None

        if context.collection and context.collection.name.startswith("MeshSet_"):
            meshset_collection = context.collection
        elif context.active_object:
            for col in context.active_object.users_collection:
                if col.name.startswith("MeshSet_"):
                    meshset_collection = col
                    break

        if not meshset_collection:
            self.report({'WARNING'}, "No MeshSet collection found")
            return {'CANCELLED'}

        # Switch the state
        switch_meshset_state(meshset_collection, self.state)

        # Update viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        self.report({'INFO'}, f"Switched to state: {self.state}")
        return {'FINISHED'}


class BMG_OT_SwitchAllMeshSetsState(Operator):
    """Switch the visible state of all MeshSets in the current BMG model"""
    bl_idname = "bmg.switch_all_meshsets_state"
    bl_label = "Switch All MeshSets State"
    bl_options = {'REGISTER', 'UNDO'}

    state: EnumProperty(
        name="State",
        description="Which state to display",
        items=[
            ('S0', "S0 - Undamaged", "Show undamaged building state"),
            ('S2', "S2 - Damaged", "Show damaged building state"),
            ('S2_with_debris', "S2 + Debris", "Show damaged state with debris"),
            ('S3_destroyed', "S3 - Destroyed", "Show only debris (destroyed state)"),
            ('all_states', "All States", "Show all states (for editing)"),
        ],
        default='S0'
    )

    @classmethod
    def poll(cls, context):
        """Only enable if a DRSModel collection exists in the scene"""
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                return True
        return False

    def execute(self, context):
        count = 0
        # Find all DRSModel collections first, then look for MeshSetGrid children
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                # Look for MeshSetGrid in children
                for child in col.children:
                    if child.name.startswith("MeshSetGrid_"):
                        # Find all MeshSet children
                        for meshset in child.children:
                            if meshset.name.startswith("MeshSet_"):
                                switch_meshset_state(meshset, self.state)
                                count += 1

        if count == 0:
            self.report({'WARNING'}, "No MeshSet collections found")
            return {'CANCELLED'}

        # Update viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        self.report({'INFO'}, f"Switched {count} MeshSet(s) to state: {self.state}")
        return {'FINISHED'}


class BMG_PT_MeshStateEditor(Panel):
    """Panel for controlling BMG building mesh states"""
    bl_label = "BMG Mesh State Editor"
    bl_idname = "BMG_PT_mesh_state_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BMG Editor'

    @classmethod
    def poll(cls, context):
        """Only show panel if a BMG model is present"""
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                for child in col.children_recursive:
                    if child.name.startswith("MeshSetGrid_"):
                        return True
        return False

    def draw(self, context):
        layout = self.layout

        # Mesh grid controls
        grid_box = layout.box()
        grid_box.label(text="Mesh Grid", icon='SNAP_INCREMENT')
        grid_box.prop(context.window_manager, "bmg_show_meshgrid", text="Show Mesh Grid")
        grid_box.prop(
            context.window_manager,
            "bmg_meshgrid_rotation",
            text="Rotation",
            slider=True,
        )

        # Visibility toggles
        vis_box = layout.box()
        vis_box.label(text="Visibility", icon='HIDE_OFF')
        vis_box.prop(context.window_manager, "bmg_show_collision_shapes", text="Show Collision Shapes")
        vis_box.prop(context.window_manager, "bmg_show_slocators", text="Show SLocators")

        # All MeshSets section
        box = layout.box()
        box.label(text="All MeshSets in Scene", icon='WORLD')

        col = box.column(align=True)
        col.label(text="Switch All States:")

        op = col.operator("bmg.switch_all_meshsets_state", text="Show undamaged", icon='MESH_CUBE')
        op.state = 'S0'

        op = col.operator("bmg.switch_all_meshsets_state", text="Show damaged", icon='MOD_EXPLODE')
        op.state = 'S2'

        op = col.operator("bmg.switch_all_meshsets_state", text="Show damaged + Debris (should look undamaged)", icon='PHYSICS')
        op.state = 'S2_with_debris'

        op = col.operator("bmg.switch_all_meshsets_state", text="Show Debris", icon='PARTICLE_DATA')
        op.state = 'S3_destroyed'

        col.separator()
        op = col.operator("bmg.switch_all_meshsets_state", text="Show All Stages", icon='PRESET')
        op.state = 'all_states'


# Registration
classes = (
    BMG_OT_SwitchMeshState,
    BMG_OT_SwitchAllMeshSetsState,
    BMG_PT_MeshStateEditor,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.bmg_show_meshgrid = BoolProperty(
        name="Show Mesh Grid",
        description="Toggle visibility of MeshSetGrid cells for all BMG models",
        get=_get_show_meshgrid,
        set=_set_show_meshgrid,
    )
    bpy.types.WindowManager.bmg_meshgrid_rotation = FloatProperty(
        name="Mesh Grid Rotation",
        description="Rotate MeshSet grid visualization (degrees)",
        min=-360.0,
        max=360.0,
        soft_min=-360.0,
        soft_max=360.0,
        step=1,
        precision=1,
        get=_get_meshgrid_rotation,
        set=_set_meshgrid_rotation,
    )
    bpy.types.WindowManager.bmg_show_collision_shapes = BoolProperty(
        name="Show Collision Shapes",
        description="Toggle visibility of CollisionShapes_Collection in all BMG models",
        get=_get_show_collision_shapes,
        set=_set_show_collision_shapes,
    )
    bpy.types.WindowManager.bmg_show_slocators = BoolProperty(
        name="Show SLocators",
        description="Toggle visibility of SLocators_Collection in all BMG models",
        get=_get_show_slocators,
        set=_set_show_slocators,
    )
    if _sync_grid_cell_mesh_visibility not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_sync_grid_cell_mesh_visibility)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.bmg_show_meshgrid
    del bpy.types.WindowManager.bmg_meshgrid_rotation
    del bpy.types.WindowManager.bmg_show_slocators
    del bpy.types.WindowManager.bmg_show_collision_shapes
    if _sync_grid_cell_mesh_visibility in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_grid_cell_mesh_visibility)


if __name__ == "__main__":
    register()
