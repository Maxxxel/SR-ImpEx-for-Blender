"""
BMG Building State Editor

UI panel and operators for managing building mesh states (S0, S2, debris).
Allows switching between undamaged, damaged, and destruction states.
"""

import json
import math

import bpy
from mathutils import Matrix, Vector
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, EnumProperty, FloatProperty

MESHGRID_BLOB_KEY = "sr_impex_meshgrid_blob"
MESHGRID_ROT_CTRL_TAG = "sr_impex_meshgrid_rotation_controller"
MESHGRID_ROT_AXIS_INDEX = 2
MESHGRID_FIXED_CELL_SIZE = 2.0

_rotation_sync_state = {"locked": False}

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
    if obj is None:
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
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return None


def _active_or_first_bmg_model() -> bpy.types.Collection | None:
    active = _find_active_drs_model_collection(bpy.context)
    if active and active.name.startswith("DRSModel_"):
        return active
    for model in _iter_bmg_models():
        return model
    return None


def _sanitize_grid_axis(value: int) -> int:
    return max(0, min(127, int(value)))


def _coerce_square_grid_axes(width: int, height: int) -> tuple[int, int]:
    side = _sanitize_grid_axis(max(int(width), int(height)))
    return side, side


def _safe_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _safe_center_pivoted(value, fallback: int = 1) -> int:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false", "no", "off"}:
            return 0
        if normalized in {"1", "true", "yes", "on"}:
            return 1
    if value is None:
        return 1 if fallback else 0
    return 1 if bool(value) else 0


def _build_default_cells(total_cells: int) -> list[dict]:
    cells: list[dict] = []
    for idx in range(total_cells):
        cells.append(
            {
                "index": idx,
                "has_mesh_set": 0,
                "mesh_object_name": "",
            }
        )
    return cells


def _normalize_meshgrid_blob(blob: dict) -> dict:
    width = _sanitize_grid_axis(int(blob.get("grid_width", blob.get("columns", 0)) or 0))
    height = _sanitize_grid_axis(int(blob.get("grid_height", blob.get("rows", 0)) or 0))
    width, height = _coerce_square_grid_axes(width, height)
    module_distance = MESHGRID_FIXED_CELL_SIZE
    rotation = _safe_float(blob.get("grid_rotation", blob.get("orientation", 0.0)), 0.0)
    is_center_pivoted = _safe_center_pivoted(blob.get("is_center_pivoted", 1), 1)

    total_cells = (width * 2 + 1) * (height * 2 + 1)
    old_cells = blob.get("cells") if isinstance(blob.get("cells"), list) else []
    cells = _build_default_cells(total_cells)
    for idx in range(min(total_cells, len(old_cells))):
        old = old_cells[idx] if isinstance(old_cells[idx], dict) else {}
        cells[idx]["has_mesh_set"] = int(bool(old.get("has_mesh_set", 0)))
        cells[idx]["mesh_object_name"] = str(old.get("mesh_object_name", "") or "")

    blob["grid_width"] = width
    blob["grid_height"] = height
    blob["columns"] = width
    blob["rows"] = height
    blob["module_distance"] = module_distance
    blob["grid_rotation"] = rotation
    blob["orientation"] = rotation
    blob["is_center_pivoted"] = is_center_pivoted
    if is_center_pivoted:
        blob["center_x"] = 0.0
        center_y = 0.0
    else:
        blob["center_x"] = _safe_float(blob.get("center_x", 0.0), 0.0)
        center_y = _safe_float(blob.get("center_y", blob.get("center_z", 0.0)), 0.0)
    blob["center_y"] = center_y
    blob["center_z"] = center_y
    blob["ground_decal"] = str(blob.get("ground_decal", "") or "")
    blob["cells"] = cells
    return blob


def _get_meshgrid_blob(model_collection: bpy.types.Collection) -> dict | None:
    raw_blob = model_collection.get(MESHGRID_BLOB_KEY)
    if not raw_blob:
        return None
    try:
        blob = json.loads(raw_blob)
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    if not isinstance(blob, dict):
        return None
    return _normalize_meshgrid_blob(blob)


def _set_meshgrid_blob(model_collection: bpy.types.Collection, blob: dict) -> None:
    normalized = _normalize_meshgrid_blob(blob)
    model_collection[MESHGRID_BLOB_KEY] = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False)


def _remove_meshgrid_blob(model_collection: bpy.types.Collection) -> None:
    if MESHGRID_BLOB_KEY in model_collection:
        del model_collection[MESHGRID_BLOB_KEY]


def _collection_has_ancestor_prefix(
    model_collection: bpy.types.Collection,
    collection: bpy.types.Collection,
    prefix: str,
) -> bool:
    current = collection
    for _ in range(64):
        if current.name.startswith(prefix):
            return True
        if current == model_collection:
            break
        parent = _find_parent_collection(model_collection, current)
        if parent is None:
            break
        current = parent
    return False


def _iter_meshgrid_fit_mesh_objects(model_collection: bpy.types.Collection):
    seen = set()
    for obj in model_collection.all_objects:
        if obj.type != "MESH":
            continue
        if obj.name in seen:
            continue
        if any(col.name.endswith("_GridVis") for col in getattr(obj, "users_collection", []) or []):
            continue

        in_s0_meshes_collection = False
        for col in getattr(obj, "users_collection", []) or []:
            if (
                _collection_has_ancestor_prefix(model_collection, col, "S0_Undamaged")
                and _collection_has_ancestor_prefix(model_collection, col, "Meshes_Collection")
            ):
                in_s0_meshes_collection = True
                break
        if not in_s0_meshes_collection:
            continue

        seen.add(obj.name)
        yield obj


def _compute_model_half_extents_xy(
    model_collection: bpy.types.Collection,
) -> tuple[float, float, float, float, float, float, float, int] | None:
    center_x_sum = 0.0
    center_z_sum = 0.0
    size_x = 0.0
    size_y = 0.0
    size_z = 0.0
    mesh_count = 0

    game_orientation = _find_game_orientation(model_collection)
    to_local = game_orientation.matrix_world.inverted() if game_orientation else None

    for obj in _iter_meshgrid_fit_mesh_objects(model_collection):
        mesh_count += 1
        bbox_center_local = Vector((
            sum(corner[0] for corner in obj.bound_box) / 8.0,
            sum(corner[1] for corner in obj.bound_box) / 8.0,
            sum(corner[2] for corner in obj.bound_box) / 8.0,
        ))
        center_world = obj.matrix_world @ bbox_center_local
        center_local = to_local @ center_world if to_local else center_world
        center_x_sum += float(center_local.x)
        center_z_sum += float(center_local.z)

        # Keep fit sizing simple and stable: read dimensions directly from Blender object data.
        dims = obj.dimensions
        size_x = max(size_x, float(dims.x))
        size_y = max(size_y, float(dims.y))
        size_z = max(size_z, float(dims.z))

    if mesh_count == 0:
        return None

    center_x = center_x_sum / mesh_count
    center_z = center_z_sum / mesh_count
    half_x = max(0.0, size_x * 0.5)
    half_z = max(0.0, size_z * 0.5)
    return center_x, center_z, half_x, half_z, size_x, size_y, size_z, mesh_count


def _debug_print_model_dimensions_before_grid(model_collection: bpy.types.Collection) -> None:
    extents = _compute_model_half_extents_xy(model_collection)
    if extents is None:
        print(
            f"[BMG MeshGrid] Model dimensions before create for '{model_collection.name}': "
            "no S0 mesh bounds found (X=0.00, Y=0.00, Z=0.00)"
        )
        return

    center_x, center_z, _, _, size_x, size_y, size_z, mesh_count = extents
    print(
        f"[BMG MeshGrid] Model dimensions before create for '{model_collection.name}': "
        f"X={size_x:.2f}, Y={size_y:.2f}, Z={size_z:.2f}, meshes={mesh_count}, "
        f"center_x={center_x:.2f}, center_z={center_z:.2f}"
    )


def _build_fitted_meshgrid_blob(
    model_collection: bpy.types.Collection,
    cell_size: float,
    rotation_degrees: float = 0.0,
    is_center_pivoted: bool = True,
) -> dict:
    _ = cell_size
    safe_cell_size = MESHGRID_FIXED_CELL_SIZE
    extents = _compute_model_half_extents_xy(model_collection)
    if extents is None:
        center_x = 0.0
        center_z = 0.0
        half_x = 0.0
        half_z = 0.0
        width = 0
        height = 0
        raw_width = 0
        raw_height = 0
    else:
        center_x, center_z, half_x, half_z, _, _, _, _ = extents
        raw_width = _sanitize_grid_axis(math.ceil(max(0.0, half_x - safe_cell_size * 0.5) / safe_cell_size))
        raw_height = _sanitize_grid_axis(math.ceil(max(0.0, half_z - safe_cell_size * 0.5) / safe_cell_size))
        width = raw_width
        height = raw_height
    width, height = _coerce_square_grid_axes(width, height)

    total_cells = (width * 2 + 1) * (height * 2 + 1)

    # Debug Print
    print(f"[BMG MeshGrid] Fitting grid to model '{model_collection.name}' with cell size {cell_size}")
    print(f"[BMG MeshGrid] Computed extents: center=({center_x:.2f}, {center_z:.2f}), half_x={half_x:.2f}, half_z={half_z:.2f}")
    print(f"[BMG MeshGrid] Raw grid size: width={raw_width}, height={raw_height}")
    print(f"[BMG MeshGrid] Final grid size: width={width}, height={height}")
    print(f"[BMG MeshGrid] Total cells: {total_cells}")

    return {
        "grid_width": width,
        "grid_height": height,
        "columns": width,
        "rows": height,
        "module_distance": safe_cell_size,
        "grid_rotation": float(rotation_degrees),
        "orientation": float(rotation_degrees),
        "is_center_pivoted": 1 if is_center_pivoted else 0,
        "center_x": 0.0 if is_center_pivoted else float(center_x),
        "center_y": 0.0 if is_center_pivoted else float(center_z),
        "center_z": 0.0 if is_center_pivoted else float(center_z),
        "ground_decal": "",
        "cells": _build_default_cells(total_cells),
    }


def _resolve_meshgrid_center(
    model_collection: bpy.types.Collection,
    blob: dict,
) -> tuple[float, float]:
    _ = model_collection
    if _safe_center_pivoted(blob.get("is_center_pivoted", 1), 1):
        return 0.0, 0.0

    center_x = _safe_float(blob.get("center_x", 0.0), 0.0)
    center_y = _safe_float(blob.get("center_y", blob.get("center_z", 0.0)), 0.0)
    return center_x, center_y


def _iter_bmg_models():
    """Yield all DRSModel collections in the scene."""
    for col in bpy.data.collections:
        if not col.name.startswith("DRSModel_"):
            continue
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


def _ensure_meshgrid_anchor_collection(model_collection: bpy.types.Collection) -> bpy.types.Collection:
    for child in model_collection.children:
        if child.name.startswith("MeshSetGrid_"):
            return child
    anchor = bpy.data.collections.new("MeshSetGrid_0")
    model_collection.children.link(anchor)
    return anchor


def _iter_rotation_targets(model_collection: bpy.types.Collection):
    seen = set()
    candidates: list[bpy.types.Object] = []
    game_orientation = _find_game_orientation(model_collection)

    for col in model_collection.children_recursive:
        if not (
            col.name.startswith("Meshes_Collection")
            or col.name.startswith("CollisionShapes_Collection")
        ):
            continue
        for obj in col.all_objects:
            if obj.name in seen:
                continue
            seen.add(obj.name)
            candidates.append(obj)

    for obj in model_collection.all_objects:
        if obj.type != "ARMATURE":
            continue
        if obj.name in seen:
            continue
        seen.add(obj.name)
        candidates.append(obj)

    candidate_ids = {obj.as_pointer() for obj in candidates}
    for obj in candidates:
        parent = obj.parent
        if parent is None or parent == game_orientation or parent.get(MESHGRID_ROT_CTRL_TAG):
            yield obj
            continue
        if parent.as_pointer() in candidate_ids:
            continue


def _target_rotation_radians_for_object(
    _model_collection: bpy.types.Collection,
    _obj: bpy.types.Object,
    degrees_value: float,
) -> tuple[int, float]:
    return 1, -math.radians(degrees_value)


def _find_rotation_controller(model_collection: bpy.types.Collection) -> bpy.types.Object | None:
    for obj in model_collection.objects:
        if obj.get(MESHGRID_ROT_CTRL_TAG):
            return obj
    return None


def _matrices_close(a: Matrix, b: Matrix, epsilon: float = 1e-6) -> bool:
    for row in range(4):
        for col in range(4):
            if abs(float(a[row][col]) - float(b[row][col])) > epsilon:
                return False
    return True


def _align_rotation_controller_to_game_orientation(
    model_collection: bpy.types.Collection,
    controller: bpy.types.Object,
) -> None:
    game_orientation = _find_game_orientation(model_collection)
    if game_orientation is None:
        return

    if controller.parent is not None:
        controller.parent = None

    target_matrix = game_orientation.matrix_world.copy()
    if not _matrices_close(controller.matrix_world, target_matrix):
        controller.matrix_world = target_matrix


def _ensure_rotation_controller(
    model_collection: bpy.types.Collection,
    base_grid_name: str,
) -> bpy.types.Object:
    existing = _find_rotation_controller(model_collection)
    if existing:
        return existing

    ctrl = bpy.data.objects.new(f"{base_grid_name}_RotCtrl", None)
    ctrl.empty_display_type = "ARROWS"
    ctrl.empty_display_size = 0.8
    ctrl[MESHGRID_ROT_CTRL_TAG] = 1
    model_collection.objects.link(ctrl)
    _align_rotation_controller_to_game_orientation(model_collection, ctrl)
    return ctrl


def _remove_rotation_controller(model_collection: bpy.types.Collection) -> None:
    ctrl = _find_rotation_controller(model_collection)
    if ctrl is not None:
        bpy.data.objects.remove(ctrl, do_unlink=True)


def _set_model_rotation(
    model_collection: bpy.types.Collection,
    rotation_degrees: float,
    rebuild_grid: bool,
) -> None:
    if _rotation_sync_state["locked"]:
        return

    blob = _get_meshgrid_blob(model_collection)
    if blob is None:
        return

    _rotation_sync_state["locked"] = True
    try:
        blob["grid_rotation"] = float(rotation_degrees)
        blob["orientation"] = float(rotation_degrees)
        _set_meshgrid_blob(model_collection, blob)

        _apply_rotation_to_targets(model_collection, float(rotation_degrees))

        if rebuild_grid:
            _build_meshgrid_display(model_collection)
    finally:
        _rotation_sync_state["locked"] = False


def _apply_rotation_to_targets(
    model_collection: bpy.types.Collection,
    rotation_degrees: float,
) -> None:
    for target in _iter_rotation_targets(model_collection):
        if target.get(MESHGRID_ROT_CTRL_TAG):
            continue
        if any(col.name.endswith("_GridVis") for col in getattr(target, "users_collection", []) or []):
            continue
        axis_index, target_rot = _target_rotation_radians_for_object(
            model_collection,
            target,
            float(rotation_degrees),
        )
        if abs(target.rotation_euler[axis_index] - target_rot) > 1e-6:
            target.rotation_euler[axis_index] = target_rot


def _ensure_meshgrid_collection(model_collection: bpy.types.Collection) -> tuple[bpy.types.Collection, str]:
    """Find or create the visual grid collection, named alongside the real MeshSetGrid_* collection."""
    base_grid_name = _ensure_meshgrid_anchor_collection(model_collection).name
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
        if bpy.app.version < (4, 3):
            mat.shadow_method = "NONE"
    return mat


def _create_cell_mesh(name: str, size: float, height: float = 0.0) -> bpy.types.Object:
    """Create a square cell on the XY plane; if height>0, build a Z-up box."""
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
    blob = _get_meshgrid_blob(model_collection)
    if not blob:
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

    step = float(blob.get("module_distance", MESHGRID_FIXED_CELL_SIZE) or MESHGRID_FIXED_CELL_SIZE)
    grid_rotation_degrees = float(blob.get("grid_rotation", blob.get("orientation", 0)) or 0)
    center_x, center_y = _resolve_meshgrid_center(model_collection, blob)
    cells = blob.get("cells", [])

    grid_collection, base_grid_name = _ensure_meshgrid_collection(model_collection)
    _cleanup_grid_objects(grid_collection)

    game_orientation = _find_game_orientation(model_collection)
    if game_orientation is None:
        print(f"[BMG Grid] Missing GameOrientation in {model_collection.name}; skipping grid display build")
        return None

    # Create a root empty so rotation is applied once to the whole grid (avoids overlapping rotated cells)
    root_name = f"{base_grid_name}_GridRoot"
    root_obj = bpy.data.objects.new(root_name, None)
    root_obj.empty_display_type = "PLAIN_AXES"
    root_obj.rotation_euler[MESHGRID_ROT_AXIS_INDEX] = math.radians(180.0 + grid_rotation_degrees)
    root_obj.parent = game_orientation
    root_obj.matrix_parent_inverse = game_orientation.matrix_world.inverted()
    grid_collection.objects.link(root_obj)
    base_x = center_x - ((cols - 1) * step) * 0.5
    base_y = center_y + ((rows - 1) * step) * 0.5

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
    model = _active_or_first_bmg_model()
    if not model:
        return None
    blob = _get_meshgrid_blob(model)
    if not blob:
        return None
    rot_val = blob.get("grid_rotation", blob.get("orientation"))
    if rot_val is None:
        return None
    try:
        return float(rot_val)
    except (TypeError, ValueError):
        return None


def _get_meshgrid_rotation(_self) -> float:
    rotation_val = _read_meshgrid_rotation_degrees()
    return float(rotation_val) if rotation_val is not None else 0.0


def _set_meshgrid_rotation(_self, value: float) -> None:
    show_grid = getattr(getattr(bpy.context, "window_manager", None), "bmg_show_meshgrid", False)
    model = _active_or_first_bmg_model()
    if not model:
        return
    if _get_meshgrid_blob(model) is None:
        return

    _set_model_rotation(model, float(value), rebuild_grid=bool(show_grid))

    vis_col = None
    if show_grid:
        for child in model.children:
            if child.name.endswith("_GridVis"):
                vis_col = child
                break
    if vis_col:
        vis_col.hide_viewport = not show_grid
        vis_col.hide_render = not show_grid
    _tag_viewports()


def _get_show_meshgrid(_self) -> bool:
    cols = _iter_vis_grid_collections()
    if not cols:
        return False
    return any(not col.hide_viewport for col in cols)


def _get_meshgrid_center_pivoted(_self) -> bool:
    model = _active_or_first_bmg_model()
    if not model:
        return True
    blob = _get_meshgrid_blob(model)
    if not blob:
        return True
    return bool(_safe_center_pivoted(blob.get("is_center_pivoted", 1), 1))


def _set_meshgrid_center_pivoted(_self, value: bool) -> None:
    model = _active_or_first_bmg_model()
    if not model:
        return

    blob = _get_meshgrid_blob(model)
    if not blob:
        return

    blob["is_center_pivoted"] = 1 if value else 0
    if value:
        blob["center_x"] = 0.0
        blob["center_y"] = 0.0
        blob["center_z"] = 0.0
    else:
        extents = _compute_model_half_extents_xy(model)
        if extents is not None:
            center_x, center_z, _, _, _, _, _, _ = extents
            blob["center_x"] = float(center_x)
            blob["center_y"] = float(center_z)
            blob["center_z"] = float(center_z)

    _set_meshgrid_blob(model, blob)

    show_grid = bool(getattr(getattr(bpy.context, "window_manager", None), "bmg_show_meshgrid", False))
    if show_grid:
        vis_col = _build_meshgrid_display(model)
        if vis_col:
            vis_col.hide_viewport = False
            vis_col.hide_render = False
    _tag_viewports()


def _set_show_meshgrid(_self, value: bool) -> None:
    for model in _iter_bmg_models():
        if value:
            _build_meshgrid_display(model)
        for child in model.children:
            if child.name.endswith("_GridVis"):
                child.hide_viewport = not value
                child.hide_render = not value
    _tag_viewports()


def _sync_meshgrid_rotation_controller(_depsgraph):
    if _rotation_sync_state["locked"]:
        return

    for model in _iter_bmg_models():
        blob = _get_meshgrid_blob(model)
        if blob is None:
            continue

        # Rotation controller is no longer used for grid parenting; remove stale empties.
        _remove_rotation_controller(model)
        blob_degrees = _safe_float(blob.get("grid_rotation", blob.get("orientation", 0.0)), 0.0)

        for target in _iter_rotation_targets(model):
            if target.get(MESHGRID_ROT_CTRL_TAG):
                continue
            if any(col.name.endswith("_GridVis") for col in getattr(target, "users_collection", []) or []):
                continue
            axis_index, target_radians = _target_rotation_radians_for_object(model, target, blob_degrees)
            if abs(target.rotation_euler[axis_index] - target_radians) > 1e-6:
                target.rotation_euler[axis_index] = target_radians

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
    def poll(cls, _context):
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


class BMG_OT_CreateMeshGridForActiveModel(Operator):
    """Create and fit a new mesh grid for the active DRS model"""
    bl_idname = "bmg.create_meshgrid_active_model"
    bl_label = "Create Mesh Grid"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        model = _find_active_drs_model_collection(context)
        return bool(model and model.name.startswith("DRSModel_"))

    def execute(self, context):
        model = _find_active_drs_model_collection(context)
        if not model:
            self.report({'ERROR'}, "Select a DRSModel_* collection first")
            return {'CANCELLED'}

        wm = context.window_manager
        cell_size = MESHGRID_FIXED_CELL_SIZE
        use_origin_pivot = bool(getattr(wm, "bmg_meshgrid_center_pivoted", True))

        # Normalize rotation before fitting so first create matches subsequent recreates.
        _apply_rotation_to_targets(model, 0.0)
        context.view_layer.update()

        _debug_print_model_dimensions_before_grid(model)

        blob = _build_fitted_meshgrid_blob(
            model,
            cell_size,
            rotation_degrees=0.0,
            is_center_pivoted=use_origin_pivot,
        )
        _set_meshgrid_blob(model, blob)

        _set_model_rotation(model, 0.0, rebuild_grid=True)

        show_grid = bool(getattr(wm, "bmg_show_meshgrid", True))
        vis_col = _build_meshgrid_display(model)
        if vis_col:
            vis_col.hide_viewport = not show_grid
            vis_col.hide_render = not show_grid

        self.report(
            {'INFO'},
            f"Created mesh grid ({blob['grid_width'] * 2 + 1}x{blob['grid_height'] * 2 + 1}) for {model.name}",
        )
        _tag_viewports()
        return {'FINISHED'}


class BMG_OT_RemoveMeshGridForActiveModel(Operator):
    """Remove mesh grid data and visualization from the active DRS model"""
    bl_idname = "bmg.remove_meshgrid_active_model"
    bl_label = "Remove Mesh Grid"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        model = _find_active_drs_model_collection(context)
        return bool(model and model.name.startswith("DRSModel_"))

    def execute(self, context):
        model = _find_active_drs_model_collection(context)
        if not model:
            self.report({'ERROR'}, "Select a DRSModel_* collection first")
            return {'CANCELLED'}

        removed_any = MESHGRID_BLOB_KEY in model
        _remove_meshgrid_blob(model)

        for child in list(model.children):
            if not child.name.endswith("_GridVis"):
                continue
            _cleanup_grid_objects(child)
            try:
                model.children.unlink(child)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            bpy.data.collections.remove(child)
            removed_any = True

        _remove_rotation_controller(model)

        for child in list(model.children):
            if not child.name.startswith("MeshSetGrid_"):
                continue
            if child.children or child.objects:
                continue
            try:
                model.children.unlink(child)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            bpy.data.collections.remove(child)
            removed_any = True

        if not removed_any:
            self.report({'INFO'}, f"No mesh grid data found on {model.name}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Removed mesh grid from {model.name}")
        _tag_viewports()
        return {'FINISHED'}


class BMG_PT_MeshStateEditor(Panel):
    """Panel for controlling BMG building mesh states"""
    bl_label = "BMG Mesh State Editor"
    bl_idname = "BMG_PT_mesh_state_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BMG Editor'

    @classmethod
    def poll(cls, _context):
        """Only show panel if a BMG model is present"""
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                return True
        return False

    def draw(self, context):
        layout = self.layout
        active_model = _find_active_drs_model_collection(context)
        has_active_model = bool(active_model and active_model.name.startswith("DRSModel_"))
        active_blob = _get_meshgrid_blob(active_model) if has_active_model else None
        has_grid = active_blob is not None

        # Mesh grid controls
        grid_box = layout.box()
        grid_box.label(text="Mesh Grid", icon='SNAP_INCREMENT')
        grid_box.prop(context.window_manager, "bmg_show_meshgrid", text="Show Mesh Grid")

        if has_active_model:
            row = grid_box.row(align=True)
            row.operator("bmg.create_meshgrid_active_model", text="Create Grid", icon='ADD')
            row.operator("bmg.remove_meshgrid_active_model", text="Remove Grid", icon='TRASH')
        else:
            grid_box.label(text="Select a DRSModel_* collection", icon='INFO')

        rot_row = grid_box.row()
        rot_row.enabled = has_grid
        rot_row.prop(
            context.window_manager,
            "bmg_meshgrid_rotation",
            text="Rotation",
            slider=True,
        )

        pivot_row = grid_box.row()
        pivot_row.enabled = has_grid
        pivot_row.prop(
            context.window_manager,
            "bmg_meshgrid_center_pivoted",
            text="Center Pivot At Origin (0,0,0)",
        )
        if not has_grid:
            grid_box.label(text="No mesh grid found for active model", icon='ERROR')

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
    BMG_OT_CreateMeshGridForActiveModel,
    BMG_OT_RemoveMeshGridForActiveModel,
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
    bpy.types.WindowManager.bmg_meshgrid_center_pivoted = BoolProperty(
        name="Center Pivot At Origin",
        description="When enabled, the mesh grid is centered at 0,0,0; otherwise it uses the model center",
        get=_get_meshgrid_center_pivoted,
        set=_set_meshgrid_center_pivoted,
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
    if _sync_meshgrid_rotation_controller not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_sync_meshgrid_rotation_controller)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.bmg_show_meshgrid
    del bpy.types.WindowManager.bmg_meshgrid_rotation
    del bpy.types.WindowManager.bmg_meshgrid_center_pivoted
    del bpy.types.WindowManager.bmg_show_slocators
    del bpy.types.WindowManager.bmg_show_collision_shapes
    if _sync_grid_cell_mesh_visibility in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_grid_cell_mesh_visibility)
    if _sync_meshgrid_rotation_controller in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_meshgrid_rotation_controller)


if __name__ == "__main__":
    register()
