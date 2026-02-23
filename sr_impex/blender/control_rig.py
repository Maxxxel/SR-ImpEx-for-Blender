"""Control rig and bone display helpers for DRS skeleton imports.

Provides two main features:

1. ``apply_joint_display(armature)``
   Replace the default stick-bone visuals with Maya-style joint spheres on the
   *existing* deform rig.  Non-destructive and animation-safe (no rest-pose
   changes).

2. ``build_control_rig(deform_armature, bone_list, collection)``
   Create a separate armature with bones re-oriented parent→child, giving a
   true "node & wire" display.  The deform rig receives world-space
   COPY_TRANSFORMS constraints so it follows the control rig exactly.

Both leverage Blender 4.0+ custom-shape features (per-bone wire overlay,
shape-independent scaling, and per-bone color themes) which allow a Maya-style
"node & wire" rig display inside Blender.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import bmesh
import bpy
from mathutils import Vector

from sr_impex.blender.transform_utils import ensure_mode

if TYPE_CHECKING:
    from sr_impex.definitions.skeleton_definitions import DRSBone

# ---------------------------------------------------------------------------
# Bone color themes (Blender 4.0+)
# ---------------------------------------------------------------------------

# Root bone:   yellow  (THEME07)
# Branch bone: green   (THEME03)
# Leaf bone:   blue    (THEME02)
_BONE_COLOR_ROOT = "THEME07"
_BONE_COLOR_BRANCH = "THEME03"
_BONE_COLOR_LEAF = "THEME02"


def _apply_bone_color(pose_bone: "bpy.types.PoseBone", palette: str) -> None:
    """Assign a color theme to a pose bone if the API is available (Blender 4.0+)."""
    try:
        pose_bone.color.palette = palette
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# Shared custom-shape helpers
# ---------------------------------------------------------------------------

_SHAPE_COLLECTION_NAME = "_DRS_ControlRig_Shapes"


def _shapes_collection() -> bpy.types.Collection:
    """Return (or lazily create) a hidden collection that owns shape objects."""
    col = bpy.data.collections.get(_SHAPE_COLLECTION_NAME)
    if col is None:
        col = bpy.data.collections.new(_SHAPE_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(col)
    col.hide_viewport = True
    col.hide_render = True
    return col


def _get_or_create_shape(
    name: str, create_fn, *, collection: bpy.types.Collection | None = None
) -> bpy.types.Object:
    """Return an existing shape object or create one via *create_fn(mesh)*."""
    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    create_fn(mesh)
    obj = bpy.data.objects.new(name, mesh)
    col = collection or _shapes_collection()
    col.objects.link(obj)
    return obj


def _fill_icosphere(mesh: bpy.types.Mesh, *, radius: float = 1.0, subdivisions: int = 2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def get_joint_shape(radius: float = 1.0) -> bpy.types.Object:
    """Shared icosphere used as joint indicator on every bone."""
    return _get_or_create_shape(
        "_CS_DRS_Joint",
        lambda m: _fill_icosphere(m, radius=radius, subdivisions=2),
    )


def _build_joint_wire_shape(
    bone_name: str,
    child_offsets: list[Vector],
    joint_radius: float,
) -> bpy.types.Object:
    """Create a custom shape mesh with a sphere + wire edges to each child.

    The sphere sits at the origin (bone head in custom-shape space).
    Each child offset is expressed in bone-local coordinates so the edge
    visually connects to the child's head position.
    """
    shape_name = f"_CS_DRS_Wire_{bone_name}"
    existing = bpy.data.objects.get(shape_name)
    if existing is not None:
        return existing

    bm = bmesh.new()

    # Sphere at origin
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=joint_radius)

    # Wire edges from origin to each child head
    origin_vert = bm.verts.new((0.0, 0.0, 0.0))
    for offset in child_offsets:
        child_vert = bm.verts.new(offset)
        bm.edges.new((origin_vert, child_vert))

    mesh = bpy.data.meshes.new(f"{shape_name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(shape_name, mesh)
    _shapes_collection().objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# 1.  apply_joint_display  –  Maya-style "node & wire" on the deform rig
# ---------------------------------------------------------------------------


def apply_joint_display(
    armature_object: bpy.types.Object,
    *,
    joint_radius: float = 0.04,
) -> None:
    """Replace default bone visuals with sphere + wire custom shapes.

    For each bone a unique mesh is built containing:
    - An icosphere at the origin (the "joint node").
    - Wire edges from the origin to every child bone's head position,
      expressed in the bone's local coordinate space.

    This produces a fully connected "node & wire" skeleton display without
    altering the rest pose, so all existing animations keep working.

    Parameters
    ----------
    armature_object : bpy.types.Object
        An armature object whose pose bones will receive custom shapes.
    joint_radius : float
        World-space radius (in Blender units) of each joint sphere.
    """
    if armature_object is None or armature_object.type != "ARMATURE":
        return

    arm_data = armature_object.data
    bones = arm_data.bones

    # Build parent → children map from the armature hierarchy
    children_map: dict[str, list[str]] = {b.name: [] for b in bones}
    for b in bones:
        if b.parent is not None:
            children_map.setdefault(b.parent.name, [])
            children_map[b.parent.name].append(b.name)

    # Precompute each bone's rest-pose matrix (armature space)
    bone_matrices = {b.name: b.matrix_local.copy() for b in bones}

    # Leaf-only shape (sphere, no wires) — shared across all leaf bones
    leaf_shape = get_joint_shape(radius=joint_radius)

    bpy.context.view_layer.objects.active = armature_object

    with ensure_mode("POSE"):
        for pb in armature_object.pose.bones:
            bone = pb.bone
            child_names = children_map.get(bone.name, [])

            if child_names:
                # Compute child head positions in this bone's local space
                bone_mat_inv = bone_matrices[bone.name].inverted_safe()
                child_offsets = []
                for cname in child_names:
                    child_head_arm = bones[cname].head_local
                    offset = bone_mat_inv @ child_head_arm
                    child_offsets.append(offset)

                shape = _build_joint_wire_shape(
                    bone.name, child_offsets, joint_radius
                )
            else:
                shape = leaf_shape

            pb.custom_shape = shape
            # Draw at 1:1 scale — sphere radius and wire offsets are already
            # baked into the mesh in bone-local units.
            pb.use_custom_shape_bone_size = False
            pb.custom_shape_scale_xyz = (1.0, 1.0, 1.0)

            # Wire overlay so the custom shape edges render as wires
            bone.show_wire = True

            pb.rotation_mode = "QUATERNION"

            # Per-bone color theme (Blender 4.0+): root=yellow, branch=green, leaf=blue
            if bone.parent is None:
                _apply_bone_color(pb, _BONE_COLOR_ROOT)
            elif child_names:
                _apply_bone_color(pb, _BONE_COLOR_BRANCH)
            else:
                _apply_bone_color(pb, _BONE_COLOR_LEAF)

            # Lock scale — the game format has no per-bone scale channel
            pb.lock_scale = (True, True, True)

            # Lock location on non-root bones to prevent accidental detachment
            if bone.parent is not None:
                pb.lock_location = (True, True, True)

    # WIRE display hides the default stick/octahedral bones
    arm_data.display_type = "WIRE"
    # Show custom shapes in front of meshes for clarity
    armature_object.show_in_front = True


# ---------------------------------------------------------------------------
# 2.  build_control_rig  –  re-oriented "node & wire" rig
# ---------------------------------------------------------------------------


def build_control_rig(
    deform_armature: bpy.types.Object,
    bone_list: List["DRSBone"],
    parent_collection: bpy.types.Collection,
    *,
    joint_radius: float = 0.04,
    leaf_bone_length_ratio: float = 0.30,
    leaf_bone_min_length: float = 0.02,
    connect_threshold: float = 1e-4,
) -> Optional[bpy.types.Object]:
    """Build a Maya joint-style control rig and connect the deform rig.

    Bones are re-oriented so each tail points toward its first child, giving
    solid visual connections.  Leaf bones extend in the parent→bone direction.
    A small sphere custom shape is assigned to every bone with
    ``bone.show_wire = True``, producing the "node & wire" illusion.

    The deform rig receives ``COPY_TRANSFORMS`` (world space) constraints and
    is hidden so the animator interacts only with the clean control rig.

    Parameters
    ----------
    deform_armature : bpy.types.Object
        The mathematically correct deform armature (the "floating sticks").
    bone_list : list[DRSBone]
        The bone list produced by ``init_bones()`` during import.
    parent_collection : bpy.types.Collection
        Collection to link the new control rig armature into.
    joint_radius : float
        Visual radius of each joint sphere.
    leaf_bone_length_ratio : float
        Leaf bones extend this fraction of the parent→bone distance.
    leaf_bone_min_length : float
        Minimum tail offset for leaf bones (avoids zero-length bones).
    connect_threshold : float
        If a child head is within this distance of its parent's tail, the
        bones are connected (solid line instead of relationship line).

    Returns
    -------
    bpy.types.Object or None
        The control rig armature object, or None on failure.
    """
    if deform_armature is None or deform_armature.type != "ARMATURE":
        return None

    src_bones = deform_armature.data.bones

    # ── hierarchy maps ──
    bone_by_id: dict[int, "DRSBone"] = {b.identifier: b for b in bone_list}
    children_map: dict[int, list[int]] = {}
    for b in bone_list:
        children_map.setdefault(b.identifier, [])
        if b.parent >= 0:
            children_map.setdefault(b.parent, [])
            children_map[b.parent].append(b.identifier)

    # Bone head positions in armature space
    head_pos: dict[str, Vector] = {}
    for b in bone_list:
        src = src_bones.get(b.name)
        if src:
            head_pos[b.name] = src.head_local.copy()

    # ── create armature data + object ──
    ctrl_arm = bpy.data.armatures.new(f"Control_Rig_{deform_armature.data.name}")
    ctrl_arm.display_type = "WIRE"

    ctrl_obj = bpy.data.objects.new(
        f"Control_Rig_{deform_armature.name}", ctrl_arm
    )
    parent_collection.objects.link(ctrl_obj)
    ctrl_obj.matrix_world = deform_armature.matrix_world.copy()

    bpy.context.view_layer.objects.active = ctrl_obj

    # ── EDIT mode: create & orient bones ──
    with ensure_mode("EDIT"):
        ebs = ctrl_arm.edit_bones

        # First pass — create bones with head/tail
        for bd in bone_list:
            head = head_pos.get(bd.name)
            if head is None:
                continue

            eb = ebs.new(bd.name)
            eb.head = head
            eb.use_deform = False

            child_ids = children_map.get(bd.identifier, [])

            if child_ids:
                # ── tail → child (single) or average (multi) ──
                if len(child_ids) == 1:
                    target = head_pos.get(bone_by_id[child_ids[0]].name)
                else:
                    targets = [
                        head_pos[bone_by_id[cid].name]
                        for cid in child_ids
                        if bone_by_id[cid].name in head_pos
                    ]
                    target = (
                        sum(targets, Vector()) / len(targets) if targets else None
                    )

                if target is not None and (target - head).length > 1e-6:
                    eb.tail = target
                else:
                    eb.tail = _fallback_tail(head, bd, src_bones)
            else:
                # ── leaf bone: extend along parent → this direction ──
                if bd.parent >= 0:
                    parent_data = bone_by_id.get(bd.parent)
                    parent_head = (
                        head_pos.get(parent_data.name) if parent_data else None
                    )
                    if parent_head is not None:
                        direction = head - parent_head
                        if direction.length > 1e-6:
                            length = max(
                                direction.length * leaf_bone_length_ratio,
                                leaf_bone_min_length,
                            )
                            eb.tail = head + direction.normalized() * length
                        else:
                            eb.tail = _fallback_tail(head, bd, src_bones)
                    else:
                        eb.tail = _fallback_tail(head, bd, src_bones)
                else:
                    # Root with no children (unusual)
                    eb.tail = _fallback_tail(head, bd, src_bones)

        # Second pass — parenting & optional connect
        for bd in bone_list:
            if bd.parent < 0:
                continue
            child_eb = ebs.get(bd.name)
            parent_data = bone_by_id.get(bd.parent)
            if child_eb is None or parent_data is None:
                continue
            parent_eb = ebs.get(parent_data.name)
            if parent_eb is None:
                continue

            child_eb.parent = parent_eb
            # Connect when the child head lands exactly on the parent tail
            if (child_eb.head - parent_eb.tail).length < connect_threshold:
                child_eb.use_connect = True

    # ── POSE mode: custom shapes & wire overlay ──
    joint_shape = get_joint_shape(radius=1.0)

    # Build a quick children map for color classification
    _ctrl_children: dict[str, list[str]] = {b.name: [] for b in ctrl_arm.bones}
    for b in ctrl_arm.bones:
        if b.parent is not None:
            _ctrl_children[b.parent.name].append(b.name)

    with ensure_mode("POSE"):
        for pb in ctrl_obj.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.custom_shape = joint_shape
            pb.use_custom_shape_bone_size = False
            pb.custom_shape_scale_xyz = (joint_radius, joint_radius, joint_radius)

            # Wire overlay alongside the shape → "node & wire"
            pb.bone.show_wire = True

            # Per-bone color theme (Blender 4.0+): root=yellow, branch=green, leaf=blue
            _children = _ctrl_children.get(pb.name, [])
            if pb.bone.parent is None:
                _apply_bone_color(pb, _BONE_COLOR_ROOT)
            elif _children:
                _apply_bone_color(pb, _BONE_COLOR_BRANCH)
            else:
                _apply_bone_color(pb, _BONE_COLOR_LEAF)

            # Lock scale — the game format has no per-bone scale channel
            pb.lock_scale = (True, True, True)

            # Lock location on non-root bones to prevent accidental detachment
            if pb.bone.parent is not None:
                pb.lock_location = (True, True, True)

    # ── Constraints: deform copies control (world space) ──
    bpy.context.view_layer.objects.active = deform_armature

    with ensure_mode("POSE"):
        for pb in deform_armature.pose.bones:
            if ctrl_obj.pose.bones.get(pb.name) is None:
                continue
            ct = pb.constraints.new(type="COPY_TRANSFORMS")
            ct.name = "Control_Rig_Driver"
            ct.target = ctrl_obj
            ct.subtarget = pb.name
            ct.target_space = "WORLD"
            ct.owner_space = "WORLD"

    # ── Hide the deform rig, keep it selectable for export ──
    deform_armature.hide_set(True)

    # ── GRT Action Bakery integration ──
    if hasattr(bpy.context.scene, "GRT_Action_Bakery_Global_Settings"):
        settings = bpy.context.scene.GRT_Action_Bakery_Global_Settings
        settings.Target_Armature = deform_armature
        settings.Source_Armature = ctrl_obj

    return ctrl_obj


# ---------------------------------------------------------------------------
# 3.  bake_control_rig_action  –  native Blender action baking
# ---------------------------------------------------------------------------


def bake_control_rig_action(
    ctrl_obj: bpy.types.Object,
    deform_armature: bpy.types.Object,
    *,
    clean_curves: bool = True,
) -> Optional[bpy.types.Action]:
    """Bake the active action from *ctrl_obj* onto *deform_armature*.

    Uses Blender's built-in NLA bake (``bpy.ops.nla.bake``) with
    ``visual_keying=True`` so the COPY_TRANSFORMS result is baked into
    plain keyframes.  The resulting action is named after the source action
    with a ``_baked`` suffix, and all SKA metadata (``frame_length``,
    ``original_fps``, ``repeat``, ``prefix``) is copied across.

    Parameters
    ----------
    ctrl_obj : bpy.types.Object
        The control rig armature that has the action to bake.
    deform_armature : bpy.types.Object
        The deform rig that receives the baked keyframes.
    clean_curves : bool
        Remove redundant keyframes from the baked result.

    Returns
    -------
    bpy.types.Action or None
        The baked action, or None if baking failed.
    """
    if ctrl_obj is None or deform_armature is None:
        return None
    if ctrl_obj.animation_data is None or ctrl_obj.animation_data.action is None:
        return None

    src_action = ctrl_obj.animation_data.action
    frame_start = int(src_action.frame_range[0])
    frame_end = int(src_action.frame_range[1])

    # Temporarily unhide the deform rig so the operator can select it
    was_hidden = deform_armature.hide_get()
    deform_armature.hide_set(False)

    # Ensure deform rig is the active object
    prev_active = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = deform_armature
    deform_armature.select_set(True)

    try:
        bpy.ops.nla.bake(
            frame_start=frame_start,
            frame_end=frame_end,
            step=1,
            only_selected=False,
            visual_keying=True,
            clear_constraints=False,
            clear_parents=False,
            use_current_action=False,
            clean_curves=clean_curves,
            bake_types={"POSE"},
        )
    except Exception as exc:
        import traceback
        print(f"[SR-ImpEx] bake_control_rig_action failed: {exc}")
        traceback.print_exc()
        deform_armature.hide_set(was_hidden)
        if prev_active is not None:
            bpy.context.view_layer.objects.active = prev_active
        return None

    # Restore visibility / active object
    deform_armature.hide_set(was_hidden)
    if prev_active is not None:
        bpy.context.view_layer.objects.active = prev_active

    if deform_armature.animation_data is None or deform_armature.animation_data.action is None:
        return None

    baked = deform_armature.animation_data.action

    # Rename and copy metadata from the source action
    baked_name = src_action.name
    if not baked_name.endswith("_baked"):
        baked_name += "_baked"
    baked.name = baked_name

    for key in ("frame_length", "original_fps", "repeat", "prefix"):
        if key in src_action:
            baked[key] = src_action[key]

    return baked


def _fallback_tail(
    head: Vector, bd: "DRSBone", src_bones
) -> Vector:
    """Compute a reasonable tail when the primary strategy fails."""
    src = src_bones.get(bd.name)
    if src is not None:
        return src.tail_local.copy()
    return head + Vector((0, 0.05, 0))
