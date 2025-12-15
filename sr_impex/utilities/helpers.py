import os
import json
from typing import Union
from collections import defaultdict
import bpy

from sr_impex.core.message_logger import MessageLogger
from sr_impex.definitions.enums import InformationIndices
from sr_impex.blender.editors.animation_set_editor import ANIM_BLOB_KEY, _resolve_action_name as _editor_resolve
from sr_impex.blender.editors.effect_set_editor import EFFECT_BLOB_KEY

logger = MessageLogger()


def abort(keep_debug_collections: bool, source_collection_copy: bpy.types.Collection):
    if not keep_debug_collections and source_collection_copy is not None:
        bpy.data.collections.remove(source_collection_copy)

    logger.display()

    return {"CANCELLED"}


def get_collection(
    source_collection: bpy.types.Collection, name: str
) -> Union[bpy.types.Collection, None]:
    """Return the sub-collection whose name matches the provided name."""
    for collection in source_collection.children:
        if collection.name.startswith(name):
            return collection
    return None


def verify_collections(
    source_collection: bpy.types.Collection, model_type: str
) -> bool:
    # First Check if the selected Collection is a valid Collection by name DRSModel_...
    if not source_collection.name.startswith("DRSModel_"):
        logger.log(
            "The selected Collection is not a valid Collection. Please select a Collection with the name DRSModel_...",
            "Error",
            "ERROR",
        )
        return False

    # Check if the Collection has the correct Children
    nodes = InformationIndices[model_type]
    for node in nodes:
        if (
            node == "CGeoMesh"
            or node == "CGeoOBBTree"
            or node == "CDspJointMap"
            or node == "CDspMeshFile"
        ):
            mesh_collection = get_collection(source_collection, "Meshes_Collection")

            if mesh_collection is None:
                logger.log("No Meshes Collection found!", "Error", "ERROR")
                return False

            # Check if the Meshes Collection has Meshes
            if len(mesh_collection.objects) == 0:
                logger.log(
                    "No Meshes found in the Meshes Collection!", "Error", "ERROR"
                )
                return False

            # Check if every mesh has a material
            for mesh in mesh_collection.objects:
                if mesh.type == "MESH":
                    if len(mesh.material_slots) == 0:
                        logger.log(
                            f"No Material found for Mesh {mesh.name}!", "Error", "ERROR"
                        )
                        return False
                    else:
                        # print all the nodes with names and types we have in the material
                        material_nodes = mesh.material_slots[0].material.node_tree.nodes
                        for node in material_nodes:
                            if node.type == "Group" and node.label != "DRSMaterial":
                                logger.log(
                                    f"Node {node.name} is not a DRSMaterial node!",
                                    "Error",
                                    "ERROR",
                                )
                                return False
        if node == "collisionShape":
            collision_collection = get_collection(
                source_collection, "CollisionShapes_Collection"
            )

            if collision_collection is None:
                logger.log(
                    "No Collision Collection found! But is required for a model with collision shapes!",
                    "Error",
                    "ERROR",
                )
                return False

            # Get Boxes, Spheres and Cylinders Collections from the Collision Collection
            boxes_collection = None
            spheres_collection = None
            cylinders_collection = None
            for child in collision_collection.children:
                if child.name.startswith("Boxes_Collection"):
                    boxes_collection = child
                if child.name.startswith("Spheres_Collection"):
                    spheres_collection = child
                if child.name.startswith("Cylinders_Collection"):
                    cylinders_collection = child
            # Check if at least one of the Collision Shapes is present
            if (
                boxes_collection is None
                and spheres_collection is None
                and cylinders_collection is None
            ):
                logger.log(
                    "No Collision Shapes found in the Collision Collection!",
                    "Error",
                    "ERROR",
                )
                return False
            # Check if at least one of the Collision Shapes has Collision Shapes (mesh)
            found_collision_shapes = False
            for collision_shape in [
                boxes_collection,
                spheres_collection,
                cylinders_collection,
            ]:
                if collision_shape is not None and len(collision_shape.objects) > 0:
                    found_collision_shapes = True
                    break
            if not found_collision_shapes:
                logger.log(
                    "No Collision Shapes found in the Collision Collection!",
                    "Error",
                    "ERROR",
                )
                return False

    return True


def copy_objects(
    from_col: bpy.types.Collection,
    to_col: bpy.types.Collection,
    linked: bool,
    dupe_lut: dict[bpy.types.Object, bpy.types.Object],
) -> None:
    for o in from_col.objects:
        dupe = o.copy()
        if not linked and o.data:
            dupe.data = dupe.data.copy()
        to_col.objects.link(dupe)
        dupe_lut[o] = dupe


def update_armature_references(
    dupe_lut: dict[bpy.types.Object, bpy.types.Object],
) -> None:
    for _, copied in dupe_lut.items():
        if copied and copied.type == "MESH":
            for modifier in copied.modifiers:
                if modifier.type == "ARMATURE" and modifier.object in dupe_lut:
                    # Update the modifier's armature reference to the copied armature
                    modifier.object = dupe_lut[modifier.object]


def copy(
    parent: bpy.types.Collection, collection: bpy.types.Collection, linked: bool = False
) -> bpy.types.Collection:
    dupe_lut = defaultdict(lambda: None)

    def _copy(parent, collection, linked=False) -> bpy.types.Collection:
        cc = bpy.data.collections.new(collection.name)
        copy_objects(collection, cc, linked, dupe_lut)

        for c in collection.children:
            _copy(cc, c, linked)

        parent.children.link(cc)
        return cc

    # Create the copied collection hierarchy
    new_coll = _copy(parent, collection, linked)

    # Set the parent for each copied object based on the original hierarchy
    for o, dupe in tuple(dupe_lut.items()):
        parent = dupe_lut[o.parent]
        if parent:
            dupe.parent = parent

    # Update armature modifiers in copied objects to reference copied armatures
    update_armature_references(dupe_lut)

    return new_coll


def _collect_ska_references(col: bpy.types.Collection) -> list[tuple[str, str | None]]:
    """Return (current, original) tuples for every animation reference in the blobs."""
    refs: list[tuple[str, str | None]] = []

    def _add(name: str | None, original: str | None = None) -> None:
        s = (name or "").strip()
        if not s:
            return
        refs.append((s, (original or "").strip() or None))

    raw_anim = col.get(ANIM_BLOB_KEY)
    if raw_anim:
        try:
            blob = json.loads(raw_anim)
        except Exception:
            blob = {}
        for mk in blob.get("mode_keys", []) or []:
            for v in mk.get("variants", []) or []:
                _add(v.get("file"), v.get("original_file_name"))
        for msd in blob.get("marker_sets", []) or []:
            _add(msd.get("file"), msd.get("original_file_name"))

    raw_effect = col.get(EFFECT_BLOB_KEY)
    if raw_effect:
        try:
            eff_blob = json.loads(raw_effect)
        except Exception:
            eff_blob = {}
        for ed in eff_blob.get("effects", []) or []:
            _add(ed.get("action"))

    return refs


def _resolve_action_from_blob_name(col: bpy.types.Collection, file_or_base: str) -> str:
    """
    Map 'skel_human_2h_idle1(.ska)' -> actual Action name (e.g. 'idle1').
    Tries:
      - user mapping _drs_action_map
      - animation_set_editor._resolve_action_name
      - basename / .ska stripping / truncations
    Returns the Action name that exists in bpy.data.actions or "".
    """
    if not file_or_base:
        return ""
    s = (file_or_base or "").strip()
    base = s[:-4] if s.lower().endswith(".ska") else s
    # try mapping saved by importer
    try:
        raw = col.get("_drs_action_map", "{}")
        mp = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        mp = {}

    for key in (s, os.path.basename(s), base, os.path.basename(base)):
        cand = mp.get(key)
        if cand and cand in bpy.data.actions:
            return cand

    # fall back to the editor's robust resolver
    try:
        cand = _editor_resolve(s)
        if cand != "NONE" and cand in bpy.data.actions:
            return cand
    except Exception:
        pass

    # naive fallbacks
    for cand in (base, os.path.basename(base), base + ".ska"):
        if cand in bpy.data.actions:
            return cand

    # truncation fallback (Blender 63-char)
    t = base[:63]
    if t in bpy.data.actions:
        return t

    return ""


def _determine_action_for_blob_name(col: bpy.types.Collection, blob_name: str) -> bpy.types.Action | None:
    resolved_name = _resolve_action_from_blob_name(col, blob_name)
    if not resolved_name:
        return None
    act = bpy.data.actions.get(resolved_name)
    if not act:
        return None
    if isinstance(act.name, str) and "." in act.name:
        base, suffix = act.name.rsplit(".", 1)
        if suffix.isdigit() and base in bpy.data.actions:
            return bpy.data.actions.get(base)
    return act


def _effective_prefix_for_action(action: bpy.types.Action | None, export_prefix: str | None) -> str:
    if export_prefix is None:
        try:
            return str(action.get("prefix", "")) if action else ""
        except Exception:
            return ""
    return export_prefix or ""


def _derive_action_short_name(action: bpy.types.Action | None, fallback: str) -> str:
    if action:
        name = (action.name or "").strip()
        if name:
            return name
        try:
            ui = action.get("ui_name", None)
        except Exception:
            ui = None
        if ui:
            return str(ui)
    return fallback


def _make_unique_export_basename(base: str, used: set[str]) -> str:
    """Ensure exported basenames stay unique (case-insensitive) and within 63 chars."""
    sanitized = (base or "animation").strip().replace(" ", "_")
    if sanitized.lower().endswith(".ska"):
        sanitized = sanitized[:-4]
    sanitized = sanitized or "animation"
    sanitized = sanitized[:63]
    cand = sanitized
    idx = 2
    while cand.lower() in used:
        suffix = f"_{idx:02d}"
        trimmed = sanitized[: max(1, 63 - len(suffix))]
        cand = f"{trimmed}{suffix}"
        idx += 1
    used.add(cand.lower())
    return cand


def _norm_ska_key(name: str | None) -> str:
    """Map any animation reference to a normalized lowercase key without extension."""
    if not name:
        return ""
    base = os.path.basename((name or "").strip())
    if base.lower().endswith(".ska"):
        base = base[:-4]
    return base.strip().lower()


def build_ska_export_name_map(
    current_collection: bpy.types.Collection,
    export_prefix: str | None,
) -> dict[str, str]:
    """
    Build a mapping from normalized blob keys to their final exported SKA basenames
    without mutating the underlying JSON blobs.
    """
    refs = _collect_ska_references(current_collection)
    if not refs:
        return {}

    used: set[str] = set()
    name_map: dict[str, str] = {}
    seen_keys: set[str] = set()

    for blob_name, original in refs:
        key = _norm_ska_key(blob_name)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)

        act = _determine_action_for_blob_name(current_collection, blob_name)
        short = _derive_action_short_name(act, key)
        eff_prefix = _effective_prefix_for_action(act, export_prefix)

        base = short
        if eff_prefix:
            pref = eff_prefix.strip().replace(" ", "_")
            if not base.startswith(pref + "_"):
                base = f"{pref}_{base}"

        if not act and export_prefix is None and original:
            # fall back to the original full name if we are supposed to keep it
            base = os.path.basename((original or "").strip()) or base

        final_base = _make_unique_export_basename(base, used)
        name_map[key] = final_base

        # also map the original reference if present
        orig_key = _norm_ska_key(original)
        if orig_key and orig_key not in name_map:
            name_map[orig_key] = final_base

    return name_map
