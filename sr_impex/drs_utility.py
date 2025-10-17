import os
import json
from os.path import dirname, realpath
from math import radians
import time
import uuid
import hashlib
import subprocess
from struct import pack
from collections import defaultdict
from typing import Tuple, List, Dict, Optional, Union
import xml.etree.ElementTree as ET
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
import bpy
from bmesh.ops import (
    triangulate as tri,
    remove_doubles,
    split_edges,
    create_uvsphere,
    create_cone,
)
import bmesh

# pylint: disable=import-error
import numpy as np

from .drs_definitions import (
    DRS,
    BMS,
    BMG,
    BoneMatrix,
    CDspMeshFile,
    CylinderShape,
    Face,
    BattleforgeMesh,
    DRSBone,
    CSkSkeleton,
    Bone,
    BoneVertex,
    BoxShape,
    ModeAnimationKey,
    SLocator,
    SphereShape,
    CGeoCylinder,
    CSkSkinInfo,
    CGeoAABox,
    CGeoMesh,
    BoneWeight,
    CGeoOBBTree,
    OBBNode,
    CMatCoordinateSystem,
    CDspJointMap,
    MeshData,
    StateBasedMeshSet,
    Vertex,
    LevelOfDetail,
    EmptyString,
    Flow,
    Textures,
    Texture,
    Refraction,
    Materials,
    DrwResourceMeta,
    JointGroup,
    Vector3,
    Vector4,
    InformationIndices,
    CollisionShape,
    AnimationSet,
    AnimationTimings,
    VertexData,
    AnimationSetVariant,
    CGeoSphere,
    Matrix3x3,
    CDrwLocatorList,
    AnimationMarkerSet,
    AnimationMarker,
)
from .drs_material import DRSMaterial
from .ska_definitions import SKA
from .ska_utility import get_actions
from .transform_utils import (
    ensure_mode,
    parent_under_game_axes,
    create_empty,
)
from .bmesh_utils import new_bmesh_from_object, edit_bmesh_from_object, new_bmesh
from .animation_utils import import_ska_animation
from .message_logger import MessageLogger
from .locator_editor import BLOB_KEY, UID_KEY

logger = MessageLogger()
resource_dir = dirname(realpath(__file__)) + "/resources"
texture_cache_col = {}
texture_cache_nor = {}
texture_cache_par = {}
texture_cache_ref = {}

with open(resource_dir + "/bone_versions.json", "r", encoding="utf-8") as f:
    bones_list = json.load(f)

# region General Helper Functions
BLOB_KEY = "CDrwLocatorListJSON"
ANIM_BLOB_KEY = "AnimationSetJSON"


def persist_locator_blob_on_collection(
    source_collection: bpy.types.Collection, drs_file: "DRS"
) -> dict | None:
    """Create and store the CDrwLocatorList blob (with stable UIDs) on the model collection."""
    if not hasattr(drs_file, "cdrw_locator_list") or drs_file.cdrw_locator_list is None:
        return None
    blob = _cdrw_to_blob(drs_file.cdrw_locator_list)
    source_collection[BLOB_KEY] = json.dumps(
        blob, separators=(",", ":"), ensure_ascii=False
    )
    return blob


def _cdrw_to_blob(cdrw_list: "CDrwLocatorList") -> dict:
    """Serialize CDrwLocatorList into the editor's JSON blob format."""

    def _stable_uid(
        class_id: int,
        bone_id: int,
        file_name: str,
        rot9: list[float],
        pos3: list[float],
    ) -> str:
        # stable (session-independent) hex UID derived from content at import-time
        key = f"{class_id}|{bone_id}|{file_name}|{','.join(f'{x:.6f}' for x in rot9)}|{','.join(f'{x:.6f}' for x in pos3)}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    locs = []
    for loc in cdrw_list.slocators or []:
        rot9 = list(loc.cmat_coordinate_system.matrix.matrix)  # 9 floats
        pos3 = [
            loc.cmat_coordinate_system.position.x,
            loc.cmat_coordinate_system.position.y,
            loc.cmat_coordinate_system.position.z,
        ]
        entry = {
            "uid": _stable_uid(
                int(loc.class_id), int(loc.bone_id), loc.file_name or "", rot9, pos3
            ),
            "class_id": int(loc.class_id),
            "file": loc.file_name or "",
            "bone_id": int(loc.bone_id),
            "uk_int": (
                int(loc.uk_int)
                if hasattr(loc, "uk_int") and loc.uk_int is not None
                else -1
            ),
            "rot3x3": rot9,
            "pos": pos3,
        }
        locs.append(entry)

    return {"version": int(cdrw_list.version), "locators": locs}


def _v3_to_list(v) -> list[float]:
    try:
        return [float(v.x), float(v.y), float(v.z)]
    # pylint: disable=broad-exception-caught
    except Exception:
        return [0.0, 0.0, 0.0]


def animset_to_blob(anim: "AnimationSet") -> dict:
    """Serialize drs_definitions.AnimationSet into the editor JSON schema."""
    # Top-level scalars (see AnimationSet fields in drs_definitions)
    blob = {
        "default_run_speed": float(getattr(anim, "default_run_speed", 5.0) or 5.0),
        "default_walk_speed": float(getattr(anim, "default_walk_speed", 2.0) or 2.0),
        "mode_change_type": int(getattr(anim, "mode_change_type", 0) or 0),
        "hovering_ground": int(getattr(anim, "hovering_ground", 0) or 0),
        "fly_bank_scale": float(getattr(anim, "fly_bank_scale", 0.0) or 0.0),
        "fly_accel_scale": float(getattr(anim, "fly_accel_scale", 0.0) or 0.0),
        "fly_hit_scale": float(getattr(anim, "fly_hit_scale", 0.0) or 0.0),
        # Mind the spelling in defs: allign_to_terrain
        "align_to_terrain": int(getattr(anim, "allign_to_terrain", 0) or 0),
        "mode_keys": [],
        "marker_sets": [],
    }

    # ModeAnimationKeys -> Mode Keys (UI)
    for k in getattr(anim, "mode_animation_keys", []) or []:
        variants = []
        for var in getattr(k, "animation_set_variants", []) or []:
            variants.append(
                {
                    "weight": int(getattr(var, "weight", 100) or 0),
                    "start": float(getattr(var, "start", 0.0) or 0.0),
                    "end": float(getattr(var, "end", 1.0) or 1.0),
                    "allows_ik": int(getattr(var, "allows_ik", 0) or 0),
                    "file": (getattr(var, "file", "") or ""),
                }
            )

        blob["mode_keys"].append(
            {
                "vis_job": int(getattr(k, "vis_job", 0) or 0),
                "variants": variants,
                "special_mode": int(getattr(k, "special_mode", 0) or 0),
            }
        )

    # AnimationMarkerSets -> Marker Sets (UI). Always 1 marker per set.
    for ms in getattr(anim, "animation_marker_sets", []) or []:
        am_id = getattr(ms, "animation_marker_id", 0)
        try:
            am_id_str = str(int(am_id))
        # pylint: disable=broad-exception-caught
        except Exception:
            am_id_str = str(am_id) if am_id else str(uuid.uuid4())

        if getattr(ms, "animation_markers", None):
            m = ms.animation_markers[0]
            marker = {
                "is_spawn_animation": int(getattr(m, "is_spawn_animation", 0) or 0),
                "time": float(getattr(m, "time", 0.0) or 0.0),
                "direction": _v3_to_list(getattr(m, "direction", None)),
                "position": _v3_to_list(getattr(m, "position", None)),
            }
        else:
            marker = {
                "is_spawn_animation": 0,
                "time": 0.0,
                "direction": [0.0, 0.0, 0.0],
                "position": [0.0, 0.0, 0.0],
            }

        blob["marker_sets"].append(
            {
                "anim_id": int(getattr(ms, "anim_id", 0) or 0),
                "file": (getattr(ms, "name", "") or ""),
                "animation_marker_id": am_id_str,
                "markers": [marker],
            }
        )

    return blob


# --- AnimationTimings <-> Blob ----------------------------------------------


def _timing_direction_to_list(tdir) -> list[float]:
    try:
        return [float(tdir.x), float(tdir.y), float(tdir.z)]
    except Exception:
        return [0.0, 0.0, 0.0]


def animtimings_to_blob(anim_timings) -> list[dict]:
    """
    Convert drs_definitions.AnimationTimings into a compact, deduped blob list.

    Schema we emit:
    [
      {
        "animation_type": int,
        "animation_tag_id": int,
        "is_enter_mode": int,
        "variants": [
           {
             "variant_index": int,
             "weight": int,
             "cast_ms": int,
             "resolve_ms": int,
             "direction": [x,y,z],
             "animation_marker_id": int
           },
           ...
        ]
      },
      ...
    ]
    """
    out = []
    if not anim_timings:
        return out

    for at in getattr(anim_timings, "animation_timings", []) or []:
        entry = {
            "animation_type": int(getattr(at, "animation_type", 0) or 0),
            "animation_tag_id": int(getattr(at, "animation_tag_id", 0) or 0),
            "is_enter_mode": int(getattr(at, "is_enter_mode_animation", 0) or 0),
            "variants": [],
        }

        for var in getattr(at, "timing_variants", []) or []:
            v_idx = int(getattr(var, "variant_index", 0) or 0)
            w = int(getattr(var, "weight", 100) or 100)

            # Deduplicate timings inside the variant (files often repeat n×n)
            seen = set()
            picked = None
            for t in getattr(var, "timings", []) or []:
                sig = (
                    int(getattr(t, "cast_ms", 0) or 0),
                    int(getattr(t, "resolve_ms", 0) or 0),
                    int(getattr(t, "animation_marker_id", 0) or 0),
                    tuple(_timing_direction_to_list(getattr(t, "direction", None))),
                )
                if sig in seen:
                    continue
                seen.add(sig)
                picked = t
                break

            if picked is None:
                # No timing data; still emit a stub so the UI can create it later
                entry["variants"].append(
                    {
                        "variant_index": v_idx,
                        "weight": w,
                        "cast_ms": 0,
                        "resolve_ms": 0,
                        "direction": [0.0, 0.0, 0.0],
                        "animation_marker_id": 0,
                    }
                )
            else:
                entry["variants"].append(
                    {
                        "variant_index": v_idx,
                        "weight": w,
                        "cast_ms": int(getattr(picked, "cast_ms", 0) or 0),
                        "resolve_ms": int(getattr(picked, "resolve_ms", 0) or 0),
                        "direction": _timing_direction_to_list(
                            getattr(picked, "direction", None)
                        ),
                        "animation_marker_id": int(
                            getattr(picked, "animation_marker_id", 0) or 0
                        ),
                    }
                )

        out.append(entry)

    return out


def blob_to_animationtimings(blob) -> "AnimationTimings":
    from .drs_definitions import (
        AnimationTimings,
        AnimationTiming,
        TimingVariant,
        Timing,
    )  # reuse your defs

    at_root = AnimationTimings()
    at_root.version = 4
    at_root.animation_timings = []
    for group in blob.get("timings") or []:
        at = AnimationTiming()
        at.animation_type = int(group.get("animation_type", 0) or 0)
        at.animation_tag_id = int(group.get("animation_tag_id", 0) or 0)
        at.is_enter_mode_animation = int(group.get("is_enter_mode", 0) or 0)
        at.timing_variants = []
        for v in group.get("variants") or []:
            tv = TimingVariant()
            tv.weight = int(v.get("weight", 100) or 100)
            tv.variant_index = int(v.get("variant_index", 0) or 0)
            # single unique Timing
            t = Timing()
            t.cast_ms = int(v.get("cast_ms", 0) or 0)
            t.resolve_ms = int(v.get("resolve_ms", 0) or 0)
            t.animation_marker_id = int(v.get("animation_marker_id", 0) or 0)
            dx, dy, dz = v.get("direction") or [0.0, 0.0, 0.0]
            t.direction.x, t.direction.y, t.direction.z = (
                float(dx),
                float(dy),
                float(dz),
            )
            tv.timings = [t]
            tv.timing_count = 1
            at.timing_variants.append(tv)
        at.variant_count = len(at.timing_variants)
        at_root.animation_timings.append(at)

    at_root.animation_timing_count = len(at_root.animation_timings)
    # keep your StructV3 as-is; no change needed
    return at_root


def persist_animset_blob_on_collection(
    source_collection: bpy.types.Collection, drs_file: "DRS"
) -> dict | None:
    """
    Create and store the AnimationSet blob on the model collection.

    Usage right after you've loaded the DRS:
        persist_animset_blob_on_collection(model_collection, drs_file)
    """
    anim = getattr(drs_file, "animation_set", None)
    if anim is None:
        return None
    blob = animset_to_blob(anim)
    try:
        if hasattr(drs_file, "animation_timings") and drs_file.animation_timings:
            blob["timings"] = animtimings_to_blob(drs_file.animation_timings)
        else:
            blob["timings"] = []
    except Exception:
        blob.setdefault("timings", [])
    source_collection[ANIM_BLOB_KEY] = json.dumps(
        blob, separators=(",", ":"), ensure_ascii=False
    )
    return blob


def find_or_create_collection(
    source_collection: bpy.types.Collection, collection_name: str
) -> bpy.types.Collection:
    collection = source_collection.children.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        source_collection.children.link(collection)

    return collection


def get_collection(
    source_collection: bpy.types.Collection, name: str
) -> Union[bpy.types.Collection, None]:
    """Return the sub-collection whose name matches the provided name."""
    for collection in source_collection.children:
        if collection.name.startswith(name):
            return collection
    return None


def abort(keep_debug_collections: bool, source_collection_copy: bpy.types.Collection):
    if not keep_debug_collections and source_collection_copy is not None:
        bpy.data.collections.remove(source_collection_copy)

    logger.display()

    return {"CANCELLED"}


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


def triangulate(meshes_collection: bpy.types.Collection) -> None:
    for obj in meshes_collection.objects:
        if obj.type == "MESH":
            with new_bmesh_from_object(obj) as bm:
                tri(bm, faces=bm.faces[:])  # pylint: disable=E1111, E1120
                # V2.79 : bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method=0, ngon_method=0)


def verify_mesh_vertex_count(meshes_collection: bpy.types.Collection) -> bool:
    """Check if the Models are valid for the game. This includes the following checks:
    - Check if the Meshes have more than 32767 Vertices"""
    with new_bmesh() as unified_mesh:
        for obj in meshes_collection.objects:
            if obj.type == "MESH":
                if len(obj.data.vertices) > 32767:
                    logger.log(
                        f"Mesh '{obj.name}' has more than 32767 Vertices. This is not supported by the game.",
                        "Error",
                        "ERROR",
                    )
                    return False
                unified_mesh.from_mesh(obj.data)

        unified_mesh.verts.ensure_lookup_table()
        unified_mesh.verts.index_update()
        remove_doubles(unified_mesh, verts=unified_mesh.verts, dist=1e-6)

        if len(unified_mesh.verts) > 32767:
            logger.log(
                "The unified Mesh has more than 32767 Vertices. This is not supported by the game.",
                "Error",
                "ERROR",
            )
            return False

    return True


def split_meshes_by_uv_islands(meshes_collection: bpy.types.Collection) -> None:
    """Split the Meshes by UV Islands."""
    for obj in meshes_collection.objects:
        if obj.type == "MESH":
            bpy.context.view_layer.objects.active = obj
            with ensure_mode("EDIT"):
                with edit_bmesh_from_object(obj) as bm:
                    # old seams
                    old_seams = [e for e in bm.edges if e.seam]
                    # unmark
                    for e in old_seams:
                        e.seam = False
                    # mark seams from uv islands
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.uv.select_all(action="SELECT")
                    bpy.ops.uv.seams_from_islands()
                    seams = [e for e in bm.edges if e.seam]
                    # split on seams
                    split_edges(bm, edges=seams)  # pylint: disable=E1120
                    # re instate old seams.. could clear new seams.
                    for e in old_seams:
                        e.seam = True


def set_origin_to_world_origin(meshes_collection: bpy.types.Collection) -> None:
    for obj in meshes_collection.objects:
        if obj.type == "MESH":
            # Set the object's active scene to the current scene
            bpy.context.view_layer.objects.active = obj
            # Select the object
            obj.select_set(True)
            # Set the origin to the world origin (0, 0, 0)
            bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
            # Deselect the object
            obj.select_set(False)
    # Move the cursor back to the world origin
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)


def get_bb(obj) -> Tuple[Vector3, Vector3]:
    """Get the Bounding Box of an Object. Returns the minimum and maximum Vector of the Bounding Box."""
    bb_min = Vector3(0, 0, 0)
    bb_max = Vector3(0, 0, 0)

    if obj.type == "MESH":
        for _vertex in obj.data.vertices:
            _vertex = _vertex.co

            if _vertex.x < bb_min.x:
                bb_min.x = _vertex.x
            if _vertex.y < bb_min.y:
                bb_min.y = _vertex.y
            if _vertex.z < bb_min.z:
                bb_min.z = _vertex.z
            if _vertex.x > bb_max.x:
                bb_max.x = _vertex.x
            if _vertex.y > bb_max.y:
                bb_max.y = _vertex.y
            if _vertex.z > bb_max.z:
                bb_max.z = _vertex.z

    return bb_min, bb_max


def get_image_and_pixels(map_node, map_name):
    if map_node is None or not map_node.is_linked:
        return None, None

    from_node = map_node.links[0].from_node
    if from_node.type in {"SEPRGB", "SEPARATE_COLOR"}:
        if not from_node.inputs[0].is_linked:
            logger.log(
                f"The {map_name} input is not linked. Please connect an Image Node!",
                "Info",
                "INFO",
            )
            return None, None
        input_node = from_node.inputs[0].links[0].from_node
        img = getattr(input_node, "image", None)
    else:
        img = getattr(from_node, "image", None)

    if img is None or not img.pixels:
        logger.log(
            f"The {map_name} is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!",
            "Info",
            "INFO",
        )
        return None, None

    return img, img.pixels[:]


def create_new_bf_scene(scene_type: str, collision_support: bool):
    # Create the main collection with a name based on the scene type.
    main_collection_name = f"DRSModel_{scene_type}_CHANGENAME"
    main_collection = bpy.data.collections.new(main_collection_name)
    bpy.context.scene.collection.children.link(main_collection)

    # Create and link the Meshes_Collection.
    meshes_collection = bpy.data.collections.new("Meshes_Collection")
    main_collection.children.link(meshes_collection)

    if collision_support:
        # Create the CollisionShapes_Collection and its subcollections.
        collision_collection = bpy.data.collections.new("CollisionShapes_Collection")
        main_collection.children.link(collision_collection)

        boxes_collection = bpy.data.collections.new("Boxes_Collection")
        collision_collection.children.link(boxes_collection)

        spheres_collection = bpy.data.collections.new("Spheres_Collection")
        collision_collection.children.link(spheres_collection)

        cylinders_collection = bpy.data.collections.new("Cylinders_Collection")
        collision_collection.children.link(cylinders_collection)

    # Add the empty object to the main collection.
    create_empty(main_collection)

    list_paths = [
        ("Battleforge Assets", resource_dir + "/assets"),
    ]

    offset = len(bpy.context.preferences.filepaths.asset_libraries)
    index = offset

    try:
        for path in list_paths:
            if offset == 0:
                # Add them without any Checks
                bpy.ops.preferences.asset_library_add(directory=path[1])
                # give a name to your asset dir
                bpy.context.preferences.filepaths.asset_libraries[index].name = path[0]
                index += 1
                logger.log(f"Added Asset Library: {path[0]}", "Info", "INFO")
            else:
                for _, user_path in enumerate(
                    bpy.context.preferences.filepaths.asset_libraries
                ):
                    if user_path.name != path[0]:
                        bpy.ops.preferences.asset_library_add(directory=path[1])
                        # give a name to your asset dir
                        bpy.context.preferences.filepaths.asset_libraries[
                            index
                        ].name = path[0]
                        index += 1
                        logger.log(f"Added Asset Library: {path[0]}", "Info", "INFO")
                        break
                    else:
                        logger.log(
                            "Asset Library already exists: " + path[0], "Info", "INFO"
                        )
                        break
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error while adding Asset Libraries: {e}", "Error", "ERROR")

    logger.display()


def get_base_transform(coord_system) -> Matrix:
    rotation_flat = coord_system.matrix.matrix  # Expects 9 elements (flattened 3x3)
    position = coord_system.position  # Expected to have attributes x, y, z

    rot_mat = Matrix(
        (
            (rotation_flat[0], rotation_flat[1], rotation_flat[2], 0.0),
            (rotation_flat[3], rotation_flat[4], rotation_flat[5], 0.0),
            (rotation_flat[6], rotation_flat[7], rotation_flat[8], 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    transform = rot_mat.copy()
    transform.translation = Vector((position.x, position.y, position.z))
    return transform


def get_base_transform_transposed(coord_system) -> Matrix:
    rotation_flat = coord_system.matrix.matrix
    position = coord_system.position

    rot_mat = Matrix(
        (
            (rotation_flat[0], rotation_flat[1], rotation_flat[2]),
            (rotation_flat[3], rotation_flat[4], rotation_flat[5]),
            (rotation_flat[6], rotation_flat[7], rotation_flat[8]),
        )
    )

    # This swaps the rows and columns to correct the orientation
    rot_mat.transpose()

    # Now, build the full 4x4 matrix
    transform = rot_mat.to_4x4()
    transform.translation = Vector((position.x, position.y, position.z))

    return transform


def generate_bone_id(bone_name: str) -> int:
    """Generate a unique bone ID based on the bone name."""
    # Generate a unique ID for the bone based on its name
    # This is a simple hash function, you can replace it with a more complex one if needed
    bone_id = sum(ord(char) for char in bone_name) % (2**32 - 1)
    return bone_id


def load_static_bms_module(
    file_name: str, dir_name: str, parent_collection: bpy.types.Collection
):
    # if filename has .module extension replace it with bms
    if file_name.endswith(".module"):
        file_name = file_name.replace(".module", ".bms")
    bms_file: BMS = BMS().read(os.path.join(dir_name, file_name))

    if bms_file.state_based_mesh_set is None:
        logger.log(
            f"Warning [load_static_bms_module]: State-based mesh set not found in {file_name}.",
            "Warning",
            "WARNING",
        )
        return None

    # StateBasedMeshSet has MeshStates and DestructionStates
    mesh_state_collection = find_or_create_collection(
        parent_collection, "Destructible_Meshes"
    )

    # We shall have only one State Mesh
    if bms_file.state_based_mesh_set.num_mesh_states > 1:
        logger.log(
            f"Warning [load_static_bms_module]: Multiple state meshes found in {file_name}. Only the first one will be used.",
            "Warning",
            "WARNING",
        )

    for mesh_state in bms_file.state_based_mesh_set.mesh_states:
        drs_file = DRS().read(os.path.join(dir_name, mesh_state.drs_file))
        mesh_object, _ = create_mesh_object(
            drs_file, 0, dir_name, f"State_{mesh_state.state_num}", None
        )
        mesh_state_collection.objects.link(mesh_object)
        return mesh_object


def load_animated_bms_module(
    file_name: str,
    dir_name: str,
    parent_collection: bpy.types.Collection,
    smooth_animation,
):
    # if filename has .module extension replace it with bms
    if file_name.endswith(".module"):
        file_name = file_name.replace(".module", ".bms")
    bms_file: BMS = BMS().read(os.path.join(dir_name, file_name))

    if bms_file.state_based_mesh_set is None:
        logger.log(
            f"Warning [load_animated_bms_module]: State-based mesh set not found in {file_name}.",
            "Warning",
            "WARNING",
        )
        return None

    # StateBasedMeshSet has MeshStates and DestructionStates
    mesh_state_collection = find_or_create_collection(parent_collection, "State_Meshes")

    # We shall have only one State Mesh
    if bms_file.state_based_mesh_set.num_mesh_states > 1:
        logger.log(
            f"Warning [load_animated_bms_module]: Multiple state meshes found in {file_name}. Only the first one will be used.",
            "Warning",
            "WARNING",
        )

    for mesh_state in bms_file.state_based_mesh_set.mesh_states:
        drs_file = DRS().read(os.path.join(dir_name, mesh_state.drs_file))
        armature_object, bone_list = setup_armature(
            mesh_state_collection, drs_file, "Locator_Wheel_"
        )
        mesh_object, _ = create_mesh_object(
            drs_file, 0, dir_name, f"State_{mesh_state.state_num}", armature_object
        )
        mesh_state_collection.objects.link(mesh_object)

        # We need to parent the Mesh_object under the ArmatureObject
        if armature_object is not None:
            mesh_object.parent = armature_object
            mesh_object.matrix_parent_inverse.identity()

        if drs_file.animation_set is not None and armature_object is not None:
            with ensure_mode("POSE"):
                for animation_key in drs_file.animation_set.mode_animation_keys:
                    for variant in animation_key.animation_set_variants:
                        ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
                        # Create the Animation
                        import_ska_animation(
                            ska_file,
                            armature_object,
                            bone_list,
                            variant.file,
                            smooth_animation,
                            file_name,
                            map_collection=parent_collection,
                        )

        return armature_object


def load_turret_animation(
    file_name: str,
    dir_name: str,
    armature_object: bpy.types.Object,
    bone_list: List[DRSBone],
    smooth_animation,
):
    ska_file: SKA = SKA().read(os.path.join(dir_name, file_name))
    # Create the Animation
    import_ska_animation(
        ska_file,
        armature_object,
        bone_list,
        file_name,
        smooth_animation,
        file_name,
        map_collection=(
            None
            if armature_object is None
            else (
                armature_object.users_collection[0]
                if armature_object.users_collection
                else None
            )
        ),
    )


def process_slocator_import(
    slocator: SLocator,
    source_collection: bpy.types.Collection,
    bone_list: List[DRSBone],
    armature_object: bpy.types.Object,
    dir_name: str,
    smooth_animation,
):
    locator_object: Union[bpy.types.Object, None] = None

    # Build stable UID EXACTLY like _cdrw_to_blob
    rot9 = list(slocator.cmat_coordinate_system.matrix.matrix)
    pos3 = list(slocator.cmat_coordinate_system.position.xyz)

    key = f"{int(slocator.class_id)}|{int(slocator.bone_id)}|{slocator.file_name or ''}|{','.join(f'{x:.6f}' for x in rot9)}|{','.join(f'{x:.6f}' for x in pos3)}"
    stable_uid = hashlib.sha1(key.encode("utf-8")).hexdigest()

    # Convert locator local transform
    local_offset = Vector(slocator.cmat_coordinate_system.position.xyz)
    local_rot = Matrix(slocator.cmat_coordinate_system.matrix.math_matrix)

    # Default world transform (used if no bone is attached)
    world_loc = local_offset.copy()
    world_rot = local_rot.copy()

    # Depending on the Type we create a Marker or load a drs-file or ska-file
    if slocator.class_type == "DestructiblePart":
        locator_object = load_static_bms_module(
            slocator.file_name, dir_name, source_collection
        )
    elif slocator.class_type == "Wheel":
        locator_object = load_animated_bms_module(
            slocator.file_name,
            dir_name,
            source_collection,
            smooth_animation,
        )
    elif slocator.class_type == "Turret" and slocator.file_name_length > 0:
        load_turret_animation(
            slocator.file_name,
            dir_name,
            armature_object,
            bone_list,
            smooth_animation,
        )
        return
    else:
        # We sometimes have .fxb files -> Effects, we ignore them for now
        # Create visual sphere for locator
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(0, 0, 0))
        locator_object = bpy.context.object
        locator_object.name = f"Locator_{slocator.class_type}"
        source_collection.objects.link(locator_object)
        bpy.context.collection.objects.unlink(locator_object)

    if not locator_object and slocator.class_type != "Turret":
        logger.log(
            f"Warning [process_slocator_import]: Locator object for {slocator.class_type} not found, file: {slocator.file_name}."
        )
        return

    # Assign stable UID so GUI can match object <-> blob directly
    locator_object[UID_KEY] = stable_uid

    if slocator.bone_id >= 0:
        bone = next((b for b in bone_list if b.identifier == slocator.bone_id), None)
        if bone:
            bone_name = bone.name
            locator_object.parent = armature_object
            locator_object.parent_type = "BONE"
            locator_object.parent_bone = bone_name
            locator_object.matrix_parent_inverse.identity()
            locator_object.location = local_offset
            locator_object.rotation_mode = "QUATERNION"
            locator_object.rotation_quaternion = local_rot.to_quaternion()
        else:
            print(
                f"Warning [process_slocator_import]: Locator bone_id {slocator.bone_id} not found."
            )
            locator_object.parent = None
            locator_object.location = world_loc
            locator_object.rotation_mode = "QUATERNION"
            locator_object.rotation_quaternion = world_rot.to_quaternion()
    else:
        # Apply transform to sphere
        locator_object.location = world_loc
        locator_object.rotation_mode = "QUATERNION"
        locator_object.rotation_quaternion = world_rot.to_quaternion()


def process_debris_import(state_based_mesh_set, source_collection, dir_name, base_name):
    for destruction_state in state_based_mesh_set.destruction_states:
        state_collection_name = f"Destruction_State_{destruction_state.state_num}"
        state_collection = find_or_create_collection(
            source_collection, state_collection_name
        )

        # Load and parse the XML file.
        xml_file_path = os.path.join(dir_name, destruction_state.file_name)
        with open(xml_file_path, "r", encoding="utf-8") as file:
            xml_file = file.read()
        xml_root = ET.fromstring(xml_file)

        # Loop through PhysicObject elements and create meshes.
        for element in xml_root.findall(".//Element[@type='PhysicObject']"):
            resource = element.attrib.get("resource")
            name = element.attrib.get("name")
            if resource and name:
                debris_drs_file = DRS().read(os.path.join(dir_name, "meshes", resource))
                for mesh_index in range(debris_drs_file.cdsp_mesh_file.mesh_count):
                    # Create the mesh data and object.
                    mesh_data = create_static_mesh(
                        debris_drs_file.cdsp_mesh_file, mesh_index
                    )
                    mesh_object = bpy.data.objects.new(
                        f"CDspMeshFile_{name}", mesh_data
                    )

                    # Create and assign the material.
                    material = create_material(
                        dir_name,
                        mesh_index,
                        debris_drs_file.cdsp_mesh_file.meshes[mesh_index],
                        f"{base_name}_{name}",
                    )
                    mesh_data.materials.append(material)

                    # Link the debris mesh object to the collection.
                    state_collection.objects.link(mesh_object)


def convert_image_to_dds(
    img: bpy.types.Image,
    output_filename: str,
    folder_path: str,
    dxt_format: str = "DXT5",
    extra_args: list[str] = None,
):
    # Create a temporary PNG file in the system temporary directory
    # temp_dir = tempfile.gettempdir()
    # We will use the addonbs temp directory instead
    temp_dir = os.path.join(resource_dir, "temp")
    # Ensure no accidental quotes are present in the filename
    temp_filename = output_filename + ".png"
    temp_filename = temp_filename.strip('"').strip("'")
    temp_path = os.path.join(temp_dir, temp_filename)

    # Save the image as PNG using Blender's save_render function
    img.file_format = "PNG"
    try:
        img.save(filepath=temp_path)
    except Exception as e: # pylint: disable=broad-except
        logger.log(
            f"Failed to save image {output_filename} as PNG: {e}",
            "Error",
            "ERROR",
        )
        return (1, "", f"Failed to save image as PNG: {e}")

    # Build the argument list for texconv.exe
    texconv_exe = os.path.join(resource_dir, "texconv.exe")
    args = [texconv_exe, "-ft", "dds", "-f", dxt_format, "-dx9", "-pow2", "-srgb"]

    if extra_args:
        args.extend(extra_args)

    args.extend(
        [
            "-y",
            output_filename + ".dds",
            "-o",
            folder_path,
            temp_path,
        ]
    )

    final_cmd = subprocess.list2cmdline(args)

    try:
        result = subprocess.run(
            final_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            shell=False,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.log(
            f"Failed to run texconv.exe for {output_filename}: {e}. Command: {final_cmd}",
            "Error",
            "ERROR",
        )
        return (1, "", f"Failed to run texconv.exe: {e}")

    # Construct the expected output DDS file path.
    output_path = os.path.join(folder_path, output_filename + ".dds")

    # Check if output file exists; if so, override the return code to 0.
    if os.path.exists(output_path):
        ret_code = 0
    else:
        ret_code = result.returncode

    # Clean up the temporary PNG file.
    if os.path.exists(temp_path):
        os.remove(temp_path)

    return (ret_code, result.stdout, result.stderr)


def compute_texture_key(image):
    # Check if image is valid
    if image is None:
        raise ValueError("Image is None")

    # Force Blender to update image data if necessary
    image.update()

    try:
        # Copy the pixel data safely
        pixels = image.pixels[:]
    except Exception as e:
        raise RuntimeError(f"Failed to access image pixels: {e}") from e

    # Pack the floats into bytes safely
    try:
        pixel_bytes = pack(f"{len(pixels)}f", *pixels)
    except Exception as e:
        raise RuntimeError(f"Failed to pack pixel data: {e}") from e

    image_hash = hashlib.md5(pixel_bytes).hexdigest()
    return f"{image_hash}"


def get_cache_for_type(file_ending: str) -> dict:
    if file_ending == "_col":
        return texture_cache_col
    elif file_ending == "_nor":
        return texture_cache_nor
    elif file_ending == "_par":
        return texture_cache_par
    elif file_ending == "_ref":
        return texture_cache_ref
    else:
        # Fallback to a general cache if needed.
        logger.log(
            f"Unknown file ending '{file_ending}'. Using default cache.",
            "Warning",
            "WARNING",
        )
        return {}


def get_converted_texture(
    img: bpy.types.Image,
    model_name: str,
    mesh_index: int,
    folder_path: str,
    file_ending: str = "_col",
    dxt_format: str = "DXT5",
    extra_args: list[str] = None,
):
    # Select the appropriate cache based on the file ending.
    cache = get_cache_for_type(file_ending)
    key = compute_texture_key(img)

    print(f"Generating Key for {model_name} {file_ending}: {key}")
    if key in cache:
        print(f"Found {model_name} {file_ending} in cache: {cache[key]}")
        # Texture already converted, reuse the existing DDS file path.
        return cache[key]

    # If no texture of this type has been cached yet, use model_name without the mesh index.
    # Otherwise, include the mesh_index to distinguish this texture.
    if len(cache) == 0:
        texture_name = f"{model_name}{file_ending}"
    else:
        texture_name = f"{model_name}{mesh_index}{file_ending}"

    # Call your conversion function (make sure convert_image_to_dds is defined and available)
    try:
        ret_code, _, stderr = convert_image_to_dds(
            img, texture_name, folder_path, dxt_format, extra_args
        )
        if ret_code != 0:
            logger.log(
                f"Conversion failed for {model_name}'s {file_ending} map: {stderr}",
                "Error",
                "ERROR",
            )
            return None
    except Exception as e:
        logger.log(
            f"Exception during conversion for {model_name}'s {file_ending} map: {e}",
            "Error",
            "ERROR",
        )
        return None

    # Assume the DDS file is generated as <texture_name>.dds in folder_path.
    try:
        dds_path = os.path.join(texture_name)
    except Exception as e:
        logger.log(
            f"Failed to construct DDS path for {model_name}'s {file_ending} map: {e}",
            "Error",
            "ERROR",
        )
        return None
    cache[key] = dds_path
    return dds_path


def clean_vector(vec, tol=1e-6):
    """Set any component of vec to 0 if its absolute value is below tol."""
    return Vector([0.0 if abs(c) < tol else c for c in vec])


# class DRS_OT_debug_obb_tree(bpy.types.Operator):
#     """Calculates and visualizes an OBBTree for the selected collection's meshes."""

#     bl_idname = "drs.debug_obb_tree"
#     bl_label = "Debug OBBTree"
#     bl_description = "Calculates a new OBBTree from the meshes in the active collection and visualizes it"

#     def execute(self, context):
#         start_time = time.time()
#         # 1. Check if a valid collection is selected
#         active_layer_coll = context.view_layer.active_layer_collection
#         if active_layer_coll is None or active_layer_coll == context.scene.collection:
#             logger.log(
#                 "Please select a specific model collection in the Outliner.",
#                 "Error",
#                 "ERROR",
#             )
#             logger.display()
#             return {"CANCELLED"}

#         source_collection = active_layer_coll.collection

#         # 2. Verify collection name and find the Meshes_Collection
#         if not source_collection.name.startswith("DRSModel_"):
#             logger.log(
#                 f"Selected collection '{source_collection.name}' is not a valid DRSModel collection.",
#                 "Error",
#                 "ERROR",
#             )
#             logger.display()
#             return {"CANCELLED"}

#         meshes_collection = get_collection(source_collection, "Meshes_Collection")
#         if not meshes_collection:
#             logger.log(
#                 f"Could not find a 'Meshes_Collection' within '{source_collection.name}'.",
#                 "Error",
#                 "ERROR",
#             )
#             logger.display()
#             return {"CANCELLED"}

#         # 3. Gather mesh objects ONLY from that specific collection
#         mesh_objects = [obj for obj in meshes_collection.objects if obj.type == "MESH"]
#         if not mesh_objects:
#             logger.log(
#                 "No mesh objects found in 'Meshes_Collection'.", "Error", "ERROR"
#             )
#             logger.display()
#             return {"CANCELLED"}

#         # Create the unified Mesh
#         unified_mesh = create_unified_mesh(meshes_collection)

#         cgeo_obb_tree = create_cgeo_obb_tree(unified_mesh)

#         end_time = time.time()
#         elapsed_time = end_time - start_time
#         logger.log(
#             f"OBBTree calculation and visualization completed in {elapsed_time:.2f} seconds.",
#             "Info",
#             "INFO",
#         )
#         logger.display()

#         return {"FINISHED"}


# endregion

# region Import DRS Model to Blender


def add_skin_weights_to_mesh(
    mesh_object: bpy.types.Object,
    cdsp_mesh_file_data: BattleforgeMesh,
    joint_group: JointGroup,
    armature_object: bpy.types.Object,
) -> None:

    skined_vertices_data = next(
        (
            mesh.vertices
            for mesh in cdsp_mesh_file_data.mesh_data
            if mesh.revision == 12
        ),
    )

    if not skined_vertices_data:
        logger.log(
            f"Mesh {mesh_object.name} does not have skin weights.",
            "Info",
            "INFO",
        )
        return

    for vertex_index, vertex in enumerate(skined_vertices_data):
        for i in range(4):
            if vertex.raw_weights[i] > 0:
                joint_index = vertex.bone_indices[i]
                bone_index = joint_group.joints[joint_index]
                bone_name = armature_object.data.bones[bone_index].name
                if bone_name not in mesh_object.vertex_groups:
                    vertex_group = mesh_object.vertex_groups.new(name=bone_name)
                    vertex_group.add([vertex_index], vertex.raw_weights[i] / 255, "ADD")
                else:
                    vertex_group = mesh_object.vertex_groups[bone_name]
                    vertex_group.add([vertex_index], vertex.raw_weights[i] / 255, "ADD")


def record_bind_pose(bone_list: list[DRSBone], armature: bpy.types.Armature) -> None:
    # Record bind pose transform to parent space
    # Used to set pose bones for animation
    for bone_data in bone_list:
        armature_bone: bpy.types.Bone = armature.bones[bone_data.name]
        matrix_local = armature_bone.matrix_local

        if armature_bone.parent:
            matrix_local = (
                armature_bone.parent.matrix_local.inverted_safe() @ matrix_local
            )

        bone_data.bind_loc = matrix_local.to_translation()
        bone_data.bind_rot = matrix_local.to_quaternion()


def create_bone_tree(armature_data: bpy.types.Armature,bone_list: list[DRSBone],bone_data: DRSBone,bone_len: float = 0.1):
    eb = armature_data.edit_bones.new(bone_data.name)
    armature_data.display_type = "STICK"

    M = bone_data.bone_matrix
    R = M.to_3x3()

    # exact head from bind pose
    eb.head = M @ Vector((0, 0, 0))

    # make tail along local +Y of the bind pose, fixed short length
    y_dir = (R @ Vector((0, 1, 0))).normalized()
    if y_dir.length < 1e-8:
        y_dir = Vector((0, 1, 0))  # extremely defensive
    eb.tail = eb.head + y_dir * bone_len

    # roll from bind pose Z axis
    eb.align_roll(R @ Vector((0, 0, 1)))

    # never force connection for coincident heads
    if bone_data.parent != -1:
        parent_name = bone_list[bone_data.parent].name
        parent_bone = armature_data.edit_bones.get(parent_name)
        if parent_bone:
            eb.parent = parent_bone
            eb.use_connect = False  # critical: OFFSET parenting, no merging

    # recurse
    for child in [b for b in bone_list if b.parent == bone_data.identifier]:
        create_bone_tree(armature_data, bone_list, child, bone_len)


def init_bones(skeleton_data: CSkSkeleton, suffix: str = None) -> list[DRSBone]:
    bone_list: list[DRSBone] = []

    # Init the Bone List with empty DRSBone Objects
    for i in range(skeleton_data.bone_count):
        bone_list.append(DRSBone())

    # Set the Bone Datapoints
    for i in range(skeleton_data.bone_count):
        bone_data: Bone = skeleton_data.bones[i]

        # Get the RootBone Vertices
        bone_vertices: list[BoneVertex] = skeleton_data.bone_matrices[
            bone_data.identifier
        ].bone_vertices

        vec_0 = Vector(
            (
                bone_vertices[0].position.x,
                bone_vertices[0].position.y,
                bone_vertices[0].position.z,
            )
        )
        vec_1 = Vector(
            (
                bone_vertices[1].position.x,
                bone_vertices[1].position.y,
                bone_vertices[1].position.z,
            )
        )
        vec_2 = Vector(
            (
                bone_vertices[2].position.x,
                bone_vertices[2].position.y,
                bone_vertices[2].position.z,
            )
        )
        vec_3 = Vector(
            (
                bone_vertices[3].position.x,
                bone_vertices[3].position.y,
                bone_vertices[3].position.z,
            )
        )

        # Get the Location of the Bone and flip the Z-Axis
        location = -vec_3
        # # Get the Rotation of the Bone
        rotation = Matrix((vec_0, vec_1, vec_2))
        # # Get the Scale of the Bone
        scale = Vector((1, 1, 1))
        # # Set the Bone Matrix
        location = rotation @ location
        bone_matrix = Matrix.LocRotScale(location, rotation, scale)

        # Set Data
        bone_list_item: DRSBone = bone_list[bone_data.identifier]
        bone_list_item.ska_identifier = bone_data.version
        bone_list_item.identifier = bone_data.identifier
        bone_list_item.name = bone_data.name + (f"_{suffix}" if suffix else "")
        bone_list_item.bone_matrix = bone_matrix

        # Set the Bone Children
        bone_list_item.children = bone_data.children

        # Set the Bones Children's Parent ID
        for j in range(bone_data.child_count):
            child_id = bone_data.children[j]
            bone_list[child_id].parent = bone_data.identifier

    # Order the Bones by Parent ID
    bone_list.sort(key=lambda x: x.identifier)

    # Go through the Bone List find the bones without a parent
    for bone in bone_list:
        if bone.parent == -1 and bone.identifier != 0:
            bone.parent = 0
            logger.log(
                "Bone {bone.name} has no parent, setting it to the root bone.",
                "Info",
                "INFO",
            )

    # Return the BoneList
    return bone_list


def import_csk_skeleton(
    source_collection: bpy.types.Collection, drs_file: DRS, locator_prefix: str = ""
) -> Tuple[bpy.types.Object, list[DRSBone]]:
    # Create the Armature Data
    armature_data: bpy.types.Armature = bpy.data.armatures.new(
        f"{locator_prefix}CSkSkeleton"
    )
    # Create the Armature Object and add the Armature Data to it
    armature_collection = bpy.data.collections.new(
        f"{locator_prefix}Armature_Collection"
    )
    source_collection.children.link(armature_collection)
    armature_object: bpy.types.Object = bpy.data.objects.new(
        f"{locator_prefix}Armature", armature_data
    )
    # Now link it to the intended destination collection
    armature_collection.objects.link(armature_object)
    # Create the Skeleton
    bone_list = init_bones(drs_file.csk_skeleton)
    # Directly set armature data to edit mode
    bpy.context.view_layer.objects.active = armature_object

    with ensure_mode("EDIT"):
        # Create the Bone Tree without using bpy.ops or context
        create_bone_tree(armature_data, bone_list, bone_list[0])
        # Parent the bones using the parent_index from the DRSBone objects
        edit_bones = armature_data.edit_bones
        
        # Old Approach, working but ugly
        for _, bone_data in enumerate(bone_list):
            if bone_data.parent != -1:  # Root bones have a parent_index of -1
                child_bone = edit_bones.get(bone_data.name)
                # The parent is found by its index in the bone_list
                parent_bone_data = bone_list[bone_data.parent]
                parent_bone = edit_bones.get(parent_bone_data.name)

                if child_bone and parent_bone:
                    child_bone.parent = parent_bone

    # Your bind pose recording function is correct and should be called at the end.
    record_bind_pose(bone_list, armature_data)
    
    # auto_align_tails(armature_object)
    
    return armature_object, bone_list
        


def create_bone_weights(
    mesh_file: CDspMeshFile, skin_data: CSkSkinInfo, geo_mesh_data: CGeoMesh
) -> list[BoneWeight]:
    total_vertex_count = sum(mesh.vertex_count for mesh in mesh_file.meshes)
    bone_weights = [BoneWeight() for _ in range(total_vertex_count)]
    vertex_positions = [
        vertex.position
        for mesh in mesh_file.meshes
        for vertex in mesh.mesh_data[0].vertices
    ]
    geo_mesh_positions = [
        [vertex.x, vertex.y, vertex.z] for vertex in geo_mesh_data.vertices
    ]

    for index, check in enumerate(vertex_positions):
        j = geo_mesh_positions.index(check)
        bone_weights[index] = BoneWeight(
            skin_data.vertex_data[j].bone_indices, skin_data.vertex_data[j].weights
        )

    return bone_weights


def create_static_mesh(mesh_file: CDspMeshFile, mesh_index: int) -> bpy.types.Mesh:
    battleforge_mesh_data: BattleforgeMesh = mesh_file.meshes[mesh_index]
    # _name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
    mesh_data = bpy.data.meshes.new(f"MeshData_{mesh_index}")

    vertices = list()
    faces = list()
    normals = list()
    uv_list = list()

    for _ in range(battleforge_mesh_data.face_count):
        face = battleforge_mesh_data.faces[_].indices
        faces.append([face[0], face[1], face[2]])

    for _ in range(battleforge_mesh_data.vertex_count):
        vertex = battleforge_mesh_data.mesh_data[0].vertices[_]
        vertices.append(vertex.position)
        normals.append(vertex.normal)
        # Negate the UVs Y Axis before adding them
        uv_list.append((vertex.texture[0], -vertex.texture[1]))

    mesh_data.from_pydata(vertices, [], faces)
    mesh_data.polygons.foreach_set("use_smooth", [True] * len(mesh_data.polygons))
    if bpy.app.version[:2] in [
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 0),
    ]:  # pylint: disable=unsubscriptable-object
        mesh_data.use_auto_smooth = True

    custom_normals = [normals[loop.vertex_index] for loop in mesh_data.loops]
    mesh_data.normals_split_custom_set(custom_normals)
    mesh_data.update()

    uv_list = [
        i
        for poly in mesh_data.polygons
        for vidx in poly.vertices
        for i in uv_list[vidx]
    ]
    mesh_data.uv_layers.new().data.foreach_set("uv", uv_list)

    return mesh_data


def import_cdsp_mesh_file(
    mesh_index: int, mesh_file: CDspMeshFile
) -> Tuple[bpy.types.Object, bpy.types.Mesh]:
    # Create the Mesh Data
    mesh_data = create_static_mesh(mesh_file, mesh_index)
    # Create the Mesh Object and add the Mesh Data to it
    mesh_object: bpy.types.Object = bpy.data.objects.new(
        f"CDspMeshFile_{mesh_index}", mesh_data
    )

    return mesh_object, mesh_data


def create_mesh_object(
    drs_file: DRS,
    mesh_index: int,
    dir_name,
    base_name,
    armature_object=None,
):
    # Create the mesh data using your existing helper.
    mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)

    # Create the mesh object.
    mesh_object = bpy.data.objects.new(f"CDspMeshFile_{mesh_index}", mesh_data)

    # Add skin weights if available ==> any of drs_file.cdsp_mesh_file.meshes[mesh_index].mesh_data[n].revision == 12
    if (
        drs_file.csk_skin_info
        and any(
            mesh.revision == 12
            for mesh in drs_file.cdsp_mesh_file.meshes[mesh_index].mesh_data
        )
        and armature_object
    ):
        add_skin_weights_to_mesh(
            mesh_object,
            drs_file.cdsp_mesh_file.meshes[mesh_index],
            drs_file.cdsp_joint_map.joint_groups[mesh_index],
            armature_object,
        )

    # Link armature if a skeleton exists.
    if drs_file.csk_skeleton and armature_object:
        modifier = mesh_object.modifiers.new(type="ARMATURE", name="Armature")
        modifier.object = armature_object

    # Create and assign material.
    material = create_material(
        dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name
    )
    mesh_data.materials.append(material)

    # after you've created `mesh_object` for mesh index `mesh_index`…
    # Seed Material flags + Flow custom props on the object so users can edit them.
    try:
        bf_mesh = drs_file.cdsp_mesh_file.meshes[mesh_index]
        # bool_parameter
        if hasattr(mesh_object, "drs_material") and mesh_object.drs_material:
            mesh_object.drs_material.bool_parameter = int(bf_mesh.bool_parameter)
            # ensure bits reflect the value
            # (update callback in the PG expands bits from the raw int)
        # flow
        if hasattr(mesh_object, "drs_flow") and mesh_object.drs_flow:
            f = bf_mesh.flow
            # flow.length==4 indicates it is present in -86061050 branch
            use = int(getattr(f, "length", 0) or 0) == 4
            mesh_object.drs_flow.use_flow = use
            if use:
                mesh_object.drs_flow.max_flow_speed = (
                    f.max_flow_speed.x,
                    f.max_flow_speed.y,
                    f.max_flow_speed.z,
                    f.max_flow_speed.w,
                )
                mesh_object.drs_flow.min_flow_speed = (
                    f.min_flow_speed.x,
                    f.min_flow_speed.y,
                    f.min_flow_speed.z,
                    f.min_flow_speed.w,
                )
                mesh_object.drs_flow.flow_speed_change = (
                    f.flow_speed_change.x,
                    f.flow_speed_change.y,
                    f.flow_speed_change.z,
                    f.flow_speed_change.w,
                )
                mesh_object.drs_flow.flow_scale = (
                    f.flow_scale.x,
                    f.flow_scale.y,
                    f.flow_scale.z,
                    f.flow_scale.w,
                )
    except Exception:
        # keep import robust if the PGs are not available for some reason
        pass

    return mesh_object, mesh_data


def setup_armature(source_collection, drs_file: DRS, locator_prefix: str = ""):
    armature_object, bone_list = None, None
    if drs_file.csk_skeleton is not None:
        armature_object, bone_list = import_csk_skeleton(
            source_collection, drs_file, locator_prefix
        )
        # Optionally: add any shared animation setup here.
    return armature_object, bone_list


def create_material(
    dir_name: str, mesh_index: int, mesh_data: BattleforgeMesh, base_name: str
) -> bpy.types.Material:
    modules = []

    for texture in mesh_data.textures.textures:
        if texture.length > 0:
            match texture.identifier:
                case 1684432499:
                    modules.append("_col")
                case 1936745324:
                    modules.append("_par")
                case 1852992883:
                    modules.append("_nor")
                case 1919116143:
                    modules.append("_ref")

    drs_material: "DRSMaterial" = DRSMaterial(
        f"MaterialData_{base_name}_{mesh_index}", modules=modules
    )

    for texture in mesh_data.textures.textures:
        if texture.length > 0:
            match texture.identifier:
                case 1684432499:
                    drs_material.set_color_map(texture.name, dir_name)
                case 1936745324:
                    drs_material.set_parameter_map(texture.name, dir_name)
                case 1852992883:
                    drs_material.set_normal_map(texture.name, dir_name)
                case 1919116143:
                    drs_material.set_refraction_map(
                        texture.name, dir_name, mesh_data.refraction.rgb
                    )

    return drs_material.material


def create_collision_shape_box_object(
    box_shape: BoxShape, index: int
) -> bpy.types.Object:
    # Extract the lower-left and upper-right corner coordinates
    llc = box_shape.geo_aabox.lower_left_corner  # Vector3
    urc = box_shape.geo_aabox.upper_right_corner  # Vector3

    # Ensure the coordinates are in the correct order
    x0, x1 = sorted((llc.x, urc.x))
    y0, y1 = sorted((llc.y, urc.y))
    z0, z1 = sorted((llc.z, urc.z))

    # Define the vertices of the box in local space
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]

    # Define the faces of the box (each face is a list of four vertex indices)
    faces = [
        (0, 1, 2, 3),  # Bottom face
        (4, 5, 6, 7),  # Top face
        (0, 1, 5, 4),  # Front face
        (1, 2, 6, 5),  # Right face
        (2, 3, 7, 6),  # Back face
        (3, 0, 4, 7),  # Left face
    ]

    # Create a new mesh and object for the box
    box_shape_mesh_data = bpy.data.meshes.new("CollisionBoxMesh")
    box_object = bpy.data.objects.new(f"CollisionBox_{index}", box_shape_mesh_data)

    # Create the mesh from the vertices and faces
    box_shape_mesh_data.from_pydata(vertices, [], faces)
    box_shape_mesh_data.update()

    transform_matrix = get_base_transform(box_shape.coord_system)

    # Assign the transformation matrix to the object's world matrix
    box_object.matrix_world = transform_matrix

    # Display the object as wired
    box_object.display_type = "WIRE"

    return box_object


def create_collision_shape_sphere_object(
    sphere_shape: SphereShape, index: int
) -> bpy.types.Object:
    sphere_shape_mesh_data = bpy.data.meshes.new("CollisionSphereMesh")
    sphere_object = bpy.data.objects.new(
        f"CollisionSphere_{index}", sphere_shape_mesh_data
    )

    with new_bmesh() as bm:
        segments = 32
        radius = sphere_shape.geo_sphere.radius
        transform_matrix = get_base_transform(sphere_shape.coord_system)

        # Create the sphere using bmesh
        create_uvsphere(
            bm,
            u_segments=segments,
            v_segments=segments,
            radius=radius,
            matrix=transform_matrix,
            calc_uvs=False,
        )

        # Finish up, write the bmesh into the mesh
        bm.to_mesh(sphere_shape_mesh_data)

    # Display the object as wired
    sphere_object.display_type = "WIRE"

    return sphere_object


def create_collision_shape_cylinder_object(
    cylinder_shape: CylinderShape, index: int
) -> bpy.types.Object:
    cylinder_shape_mesh_data = bpy.data.meshes.new("CollisionCylinderMesh")
    cylinder_object = bpy.data.objects.new(
        f"CollisionCylinder_{index}", cylinder_shape_mesh_data
    )

    with new_bmesh() as bm:
        segments = 32
        radius = cylinder_shape.geo_cylinder.radius
        depth = cylinder_shape.geo_cylinder.height
        base_transform = get_base_transform(cylinder_shape.coord_system)
        base_translation = base_transform.to_translation()
        # We need to rotate the cylinder by 90 degrees cause the cylinder is always created along the z axis, but we need it along the y axis for imported models
        additional_rot = Matrix.Rotation(radians(90), 4, "X")
        new_rotation = additional_rot @ base_transform
        transform_matrix = new_rotation.to_4x4()
        transform_matrix.translation = base_translation.copy()
        # Add half the height to the translation to center the cylinder
        transform_matrix.translation.y += depth / 2

        # Create the cylinder using bmesh
        create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=radius,  # Diameter at the bottom
            radius2=radius,  # Diameter at the top (same for cylinder)
            depth=depth,
            matrix=transform_matrix,
            calc_uvs=False,
        )

        # Finish up, write the bmesh into the mesh
        bm.to_mesh(cylinder_shape_mesh_data)

    # Display the object as wired
    cylinder_object.display_type = "WIRE"

    return cylinder_object


def import_collision_shapes(
    source_collection: bpy.types.Collection, drs_file: DRS
) -> None:
    # Create a Collision Shape Collection to store the Collision Shape Objects
    collision_shape_collection: bpy.types.Collection = bpy.data.collections.new(
        "CollisionShapes_Collection"
    )
    source_collection.children.link(collision_shape_collection)
    # Create a Box Collection to store the Box Objects
    box_collection: bpy.types.Collection = bpy.data.collections.new("Boxes_Collection")
    collision_shape_collection.children.link(box_collection)
    for _ in range(drs_file.collision_shape.box_count):
        box_object = create_collision_shape_box_object(
            drs_file.collision_shape.boxes[_], _
        )
        box_collection.objects.link(box_object)
        # TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
        box_object.location = (
            box_object.location.x,
            box_object.location.y,
            -box_object.location.z,
        )

    # Create a Sphere Collection to store the Sphere Objects
    sphere_collection: bpy.types.Collection = bpy.data.collections.new(
        "Spheres_Collection"
    )
    collision_shape_collection.children.link(sphere_collection)
    for _ in range(drs_file.collision_shape.sphere_count):
        sphere_object = create_collision_shape_sphere_object(
            drs_file.collision_shape.spheres[_], _
        )
        sphere_collection.objects.link(sphere_object)

    # Create a Cylinder Collection to store the Cylinder Objects
    cylinder_collection: bpy.types.Collection = bpy.data.collections.new(
        "Cylinders_Collection"
    )
    collision_shape_collection.children.link(cylinder_collection)
    for _ in range(drs_file.collision_shape.cylinder_count):
        cylinder_object = create_collision_shape_cylinder_object(
            drs_file.collision_shape.cylinders[_], _
        )
        cylinder_collection.objects.link(cylinder_object)


def import_animation_ik_atlas(
    armature_object: bpy.types.Object,
    animation_set: AnimationSet,
    bone_list: list[DRSBone],
) -> None:
    for atlas in animation_set.ik_atlases:
        # Get Bone with same Identifier
        bone = next((b for b in bone_list if b.identifier == atlas.identifier), None)
        if bone is None:
            logger.log(
                f"Bone with identifier {atlas.identifier} not found in bone list.",
                "Warning",
                "WARNING",
            )
            continue
        # Get the Pose Bone
        pose_bone = armature_object.pose.bones.get(bone.name)
        if pose_bone is None:
            logger.log(
                f"Pose bone {bone.name} not found in armature.",
                "Warning",
                "WARNING",
            )
            continue
        # Mark the Bone as Active
        armature_object.data.bones.active = armature_object.data.bones[bone.name]
        # Remove a previously added constraint with the same name if exists
        constraint_name = "IK_Atlas_LimitRotation"
        for con in list(pose_bone.constraints):
            if con.name == constraint_name:
                pose_bone.constraints.remove(con)
        # Create a new Limit Rotation constraint
        limit_rot = pose_bone.constraints.new(type="LIMIT_ROTATION")
        limit_rot.name = constraint_name
        # I want to loop the constraints (0, 1, 2) but get the according value as str (x, y, z)
        for i in range(3):
            constaint = atlas.constraints[i]
            if i == 0:
                limit_rot.use_limit_x = True
                limit_rot.min_x = constaint.left_angle
                limit_rot.max_x = constaint.right_angle
            elif i == 1:
                limit_rot.use_limit_y = True
                limit_rot.min_y = constaint.left_angle
                limit_rot.max_y = constaint.right_angle
            elif i == 2:
                limit_rot.use_limit_z = True
                limit_rot.min_z = constaint.left_angle
                limit_rot.max_z = constaint.right_angle
        limit_rot.owner_space = "LOCAL"


def import_cgeo_mesh(cgeo_mesh: CGeoMesh, collection: bpy.types.Collection) -> None:
    start_time = time.time()
    cgeo_mesh_mesh = bpy.data.meshes.new("CGeoMesh")
    vertices = list()
    faces = list()

    for face in cgeo_mesh.faces:
        faces.append([face.indices[0], face.indices[1], face.indices[2]])

    for vertex in cgeo_mesh.vertices:
        vertices.append([vertex.x, vertex.y, vertex.z])

    cgeo_mesh_mesh.from_pydata(vertices, [], faces)
    cgeo_mesh_mesh.polygons.foreach_set(
        "use_smooth", [True] * len(cgeo_mesh_mesh.polygons)
    )
    if bpy.app.version[:2] in [
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 0),
    ]:  # pylint: disable=unsubscriptable-object
        cgeo_mesh_mesh.use_auto_smooth = True

    cgeo_mesh_object = bpy.data.objects.new("CGeoMesh", cgeo_mesh_mesh)
    cgeo_mesh_object.display_type = "WIRE"
    collection.objects.link(cgeo_mesh_object)
    end_time = time.time()
    logger.log(f"Imported CGeoMesh in {end_time - start_time:.2f} seconds.")


def import_obb_tree(
    obb_tree: CGeoOBBTree, collection: bpy.types.Collection, limit_depth: int
) -> None:
    """
    Creates a true hierarchical representation of the OBB tree in Blender
    using nested collections and efficient object creation.
    """
    if not obb_tree.obb_nodes:
        print("OBBTree has no nodes to import.")
        return

    start_time = time.time()

    # --- Create a single, reusable cube mesh ---
    # This avoids using the slow bpy.ops operator in a loop.
    template_mesh = bpy.data.meshes.new("OBB_Cube_Mesh")
    template_mesh.from_pydata(
        [
            (-1, -1, -1),
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, 1, 1),
        ],
        [],
        [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ],
    )
    template_mesh.update()

    blender_collections = [None] * len(obb_tree.obb_nodes)

    # --- Create a cache for materials to avoid creating duplicate ones ---
    material_cache = {}

    def create_node_hierarchy(node_index, parent_collection):
        if blender_collections[node_index] is not None:
            return blender_collections[node_index]

        node_data = obb_tree.obb_nodes[node_index]

        if node_data.node_depth > limit_depth:
            return None

        # --- Create a new collection for this node ---
        node_collection = bpy.data.collections.new(
            f"OBB_Node_{node_index}_Depth_{node_data.node_depth}"
        )
        parent_collection.children.link(node_collection)
        blender_collections[node_index] = node_collection

        # --- Create the Visual Object using the template mesh (very fast) ---
        cube_obj = bpy.data.objects.new(f"OBB_Node_{node_index}", template_mesh)
        node_collection.objects.link(cube_obj)

        # Set the transformation from the OBB data
        transform_matrix = get_base_transform_transposed(
            node_data.oriented_bounding_box
        )
        cube_obj.matrix_world = transform_matrix

        # --- Use a cached material for visualization ---
        mat = material_cache.get(node_data.node_depth)
        if not mat:
            mat = bpy.data.materials.new(name=f"OBB_Depth_{node_data.node_depth}_Mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                gradient = (
                    1.0 - node_data.node_depth / 11.0
                )  # Normalized over an assumed max depth
                bsdf.inputs["Base Color"].default_value = (
                    gradient,
                    gradient,
                    gradient,
                    1,
                )
                mat.blend_method = "BLEND"
                bsdf.inputs["Alpha"].default_value = 0.25
            material_cache[node_data.node_depth] = mat

        cube_obj.data.materials.append(mat)

        # --- Recursive Creation for Children ---
        if node_data.first_child_index > 0:
            create_node_hierarchy(node_data.first_child_index, node_collection)

        if node_data.second_child_index > 0:
            create_node_hierarchy(node_data.second_child_index, node_collection)

        return node_collection

    # Create a root collection for the entire OBB Tree
    obb_tree_root_collection = bpy.data.collections.new("OBBTree_Hierarchy")
    collection.children.link(obb_tree_root_collection)

    # Start the recursive creation from the root node (index 0)
    create_node_hierarchy(0, obb_tree_root_collection)

    end_time = time.time()
    logger.log(f"OBB Tree creation took {end_time - start_time:.2f} seconds.")


def import_bounding_box(
    cdsp_mesh_file: CDspMeshFile, collection: bpy.types.Collection
) -> None:
    """
    Creates a wireframe cube in Blender that represents the Axis-Aligned Bounding Box (AABB)
    defined by the lower-left and upper-right corners.

    Args:
        cdsp_mesh_file (CDspMeshFile): The data object containing the bounding box corners.
        collection (bpy.types.Collection): The collection to link the new object to.
    """
    start_time = time.time()
    # Extract the corner vectors from the input data
    llc_data = cdsp_mesh_file.bounding_box_lower_left_corner
    urc_data = cdsp_mesh_file.bounding_box_upper_right_corner

    # Convert to Blender's Vector type for easier math
    llc = Vector((llc_data.x, llc_data.y, llc_data.z))
    urc = Vector((urc_data.x, urc_data.y, urc_data.z))

    # 1. Calculate the dimensions (size) of the bounding box
    dimensions = urc - llc

    # 2. Calculate the center of the bounding box
    # This will be the location of the cube's origin in Blender
    center = llc + (dimensions / 2.0)

    # 3. Create the cube primitive at the calculated center
    bpy.ops.mesh.primitive_cube_add(
        size=1, enter_editmode=False, align="WORLD", location=center
    )
    bbox_obj = bpy.context.object
    bbox_obj.name = "AABB_BoundingBox"

    # 4. Set the final dimensions of the cube
    bbox_obj.dimensions = dimensions

    # 5. Link the new object to your target collection and unlink from the scene's default
    # This prevents the object from appearing in the wrong place in the outliner
    scene_collection = bpy.context.scene.collection
    if scene_collection.name in [c.name for c in bbox_obj.users_collection]:
        scene_collection.objects.unlink(bbox_obj)

    if collection.name not in [c.name for c in bbox_obj.users_collection]:
        collection.objects.link(bbox_obj)

    # 6. Set display properties for better visualization
    bbox_obj.display_type = "WIRE"  # Show as a wireframe
    bbox_obj.show_in_front = True  # Make the wireframe visible through other objects

    end_time = time.time()
    logger.log(f"AABB Bounding Box creation took {end_time - start_time:.2f} seconds.")


def load_drs(
    context: bpy.types.Context,
    filepath="",
    apply_transform=True,
    import_collision_shape=False,
    import_animation=True,
    smooth_animation=True,
    import_ik_atlas=False,
    import_modules=True,
    import_geomesh=False,
    import_obbtree=False,
    limit_obb_depth=5,
    import_bb=False,
):
    start_time = time.time()
    base_name = os.path.basename(filepath).split(".")[0]
    dir_name = os.path.dirname(filepath)
    drs_file: DRS = DRS().read(filepath)

    source_collection: bpy.types.Collection = bpy.data.collections.new(
        "DRSModel_" + base_name
    )
    context.scene.collection.children.link(source_collection)

    persist_locator_blob_on_collection(source_collection, drs_file)
    persist_animset_blob_on_collection(source_collection, drs_file)

    armature_object, bone_list = setup_armature(source_collection, drs_file)

    mesh_collection: bpy.types.Collection = bpy.data.collections.new(
        "Meshes_Collection"
    )
    source_collection.children.link(mesh_collection)

    for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
        mesh_object, _ = create_mesh_object(
            drs_file, mesh_index, dir_name, base_name, armature_object
        )
        mesh_collection.objects.link(mesh_object)

    if drs_file.collision_shape is not None and import_collision_shape:
        import_collision_shapes(source_collection, drs_file)

    if (
        drs_file.animation_set is not None
        and armature_object is not None
        and import_animation
    ):
        with ensure_mode("POSE"):
            for animation_key in drs_file.animation_set.mode_animation_keys:
                for variant in animation_key.animation_set_variants:
                    ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
                    # Create the Animation
                    import_ska_animation(
                        ska_file,
                        armature_object,
                        bone_list,
                        variant.file,
                        smooth_animation,
                        filepath,
                        map_collection=source_collection,
                    )

    if (
        import_ik_atlas
        and drs_file.csk_skeleton is not None
        and armature_object is not None
        and drs_file.animation_set is not None
        and bone_list is not None
    ):
        import_animation_ik_atlas(armature_object, drs_file.animation_set, bone_list)

    if import_modules and drs_file.cdrw_locator_list is not None:
        slocator_collection = bpy.data.collections.new("SLocators_Collection")
        for slocator in drs_file.cdrw_locator_list.slocators:
            process_slocator_import(
                slocator,
                slocator_collection,
                bone_list,
                armature_object,
                dir_name,
                smooth_animation,
            )
        source_collection.children.link(slocator_collection)

    if import_obbtree and drs_file.cgeo_obb_tree is not None:
        debug_collection = find_or_create_collection(
            source_collection, "Debug_Collection"
        )
        import_obb_tree(drs_file.cgeo_obb_tree, debug_collection, limit_obb_depth)

    if import_geomesh and drs_file.cgeo_mesh is not None:
        debug_collection = find_or_create_collection(
            source_collection, "Debug_Collection"
        )
        import_cgeo_mesh(drs_file.cgeo_mesh, debug_collection)

    if import_bb and drs_file.cdsp_mesh_file is not None:
        debug_collection = find_or_create_collection(
            source_collection, "Debug_Collection"
        )
        import_bounding_box(drs_file.cdsp_mesh_file, debug_collection)

    # Apply the Transformations to the Source Collection
    parent_under_game_axes(source_collection, apply_transform)
    
    # Create a duplicate of the armature and call it control_rig
    if armature_object:
        # Select the armature object
        bpy.ops.object.select_all(action='DESELECT')
        armature_object.select_set(True)
        bpy.context.view_layer.objects.active = armature_object
        # Duplicate the armature
        bpy.ops.object.duplicate()
        control_rig = bpy.context.view_layer.objects.active
        control_rig.name = f"{armature_object.name}_Control_Rig"
        
        # Now we need to set constraints on the original armature to copy transforms from the control rig
        with ensure_mode('POSE'):
            for bone in armature_object.pose.bones:
                # Add a Copy Transforms constraint
                constraint = bone.constraints.new(type='COPY_TRANSFORMS')
                constraint.target_space = "WORLD"
                constraint.owner_space = "WORLD"
                constraint.target = control_rig
                constraint.subtarget = bone.name
        with ensure_mode('EDIT'):
            for bone in control_rig.data.edit_bones:
                bone.use_deform = False  # Disable deformation on the original armature
        
        # Link the both Rigs to the GRT_Action_Bakery_Global_Settings if available
        if hasattr(bpy.context.scene, "GRT_Action_Bakery_Global_Settings"):
            bpy.context.scene.GRT_Action_Bakery_Global_Settings.Target_Armature = armature_object
            bpy.context.scene.GRT_Action_Bakery_Global_Settings.Source_Armature = control_rig


    # Print the Time Measurement
    logger.log(
        f"Imported {base_name} in {time.time() - start_time:.2f} seconds.",
        "Import Time",
        "INFO",
    )
    logger.display()
    return {"FINISHED"}


def import_state_based_mesh_set(
    state_based_mesh_set: StateBasedMeshSet,
    source_collection: bpy.types.Collection,
    armature_object: bpy.types.Object,
    bone_list: list[DRSBone],
    dir_name: str,
    bmg_file: DRS,
    import_animation: bool,
    smooth_animation,
    import_debris: bool,
    import_collision_shape: bool,
    import_ik_atlas: bool,
    base_name: str,
    slocator: SLocator = None,
    prefix: str = "",
) -> bpy.types.Object:
    # Get individual mesh states
    # Create a Mesh Collection to store the Mesh Objects
    mesh_collection: bpy.types.Collection = bpy.data.collections.new(
        "Meshes_Collection"
    )
    source_collection.children.link(mesh_collection)
    for mesh_set in state_based_mesh_set.mesh_states:
        if mesh_set.has_files:
            # Create a new Collection for the State
            state_collection_name = f"{prefix}Mesh_State_{mesh_set.state_num}"
            state_collection = find_or_create_collection(
                mesh_collection, state_collection_name
            )
            # Load the DRS Files
            drs_file: DRS = DRS().read(os.path.join(dir_name, mesh_set.drs_file))

            if not armature_object:
                armature_object, bone_list = setup_armature(source_collection, drs_file)

            if drs_file.collision_shape is not None and import_collision_shape:
                import_collision_shapes(state_collection, drs_file)

            for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
                # Create the Mesh Data
                mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)
                # Create the Mesh Object and add the Mesh Data to it
                mesh_object: bpy.types.Object = bpy.data.objects.new(
                    f"CDspMeshFile_{mesh_index}", mesh_data
                )

                # Check if the Mesh has a Skeleton and modify the Mesh Object accordingly
                if drs_file.csk_skeleton is not None:
                    # Set the Armature Object as the Parent of the Mesh Object
                    mesh_object.parent = armature_object
                    # Add the Armature Modifier to the Mesh Object
                    modifier = mesh_object.modifiers.new(
                        type="ARMATURE", name="Armature"
                    )
                    modifier.object = armature_object
                if slocator is not None:
                    location = (
                        slocator.cmat_coordinate_system.position.x,
                        slocator.cmat_coordinate_system.position.y,
                        slocator.cmat_coordinate_system.position.z,
                    )
                    rotation = slocator.cmat_coordinate_system.matrix.matrix
                    rotation_matrix = [
                        list(rotation[i : i + 3]) for i in range(0, len(rotation), 3)
                    ]
                    transposed_rotation = Matrix(rotation_matrix).transposed()
                    # Create a new Matrix with the Location and Rotation
                    local_matrix = (
                        Matrix.Translation(location) @ transposed_rotation.to_4x4()
                    )
                    mesh_object.matrix_world = local_matrix
                # Create the Material Data
                material_data = create_material(
                    dir_name,
                    mesh_index,
                    drs_file.cdsp_mesh_file.meshes[mesh_index],
                    base_name,
                )
                # Assign the Material to the Mesh
                mesh_data.materials.append(material_data)
                # Link the Mesh Object to the Source Collection
                state_collection.objects.link(mesh_object)
            if (
                bmg_file.animation_set is not None
                and armature_object is not None
                and import_animation
            ):
                # POSE MODE is only for Armature Objects, so we need to ensure we're in the right context
                if armature_object:
                    bpy.context.view_layer.objects.active = armature_object
                with ensure_mode("POSE"):
                    for animation_key in bmg_file.animation_set.mode_animation_keys:
                        for variant in animation_key.animation_set_variants:
                            ska_file: SKA = SKA().read(
                                os.path.join(dir_name, variant.file)
                            )
                            import_ska_animation(
                                ska_file,
                                armature_object,
                                bone_list,
                                variant.file,
                                smooth_animation,
                                base_name,
                                map_collection=source_collection,
                            )

            if (
                import_ik_atlas
                and armature_object is not None
                and import_animation
                and drs_file.animation_set is not None
                and bone_list is not None
            ):
                import_animation_ik_atlas(
                    armature_object, drs_file.animation_set, bone_list
                )

    # Get individual desctruction States
    if import_debris:
        destruction_collection: bpy.types.Collection = bpy.data.collections.new(
            "Destruction_State_Collection"
        )
        source_collection.children.link(destruction_collection)
        process_debris_import(
            state_based_mesh_set, destruction_collection, dir_name, base_name
        )

    return armature_object


def import_mesh_set_grid(
    bmg_file: BMG,
    source_collection: bpy.types.Collection,
    armature_object: bpy.types.Object,
    dir_name: str,
    base_name: str,
    import_debris: bool,
    import_collision_shape: bool,
    import_ik_atlas: bool,
):
    # Create StateBasedMeshSet Collection to store the Mesh Objects
    state_based_mesh_set_collection: bpy.types.Collection = bpy.data.collections.new(
        "StateBasedMeshSet_Collection"
    )
    source_collection.children.link(state_based_mesh_set_collection)
    bone_list = None

    for module in bmg_file.mesh_set_grid.mesh_modules:
        if module.has_mesh_set:
            for mesh_set in module.state_based_mesh_set.mesh_states:
                if mesh_set.has_files:
                    file_path = os.path.join(dir_name, mesh_set.drs_file)
                    drs_file = DRS().read(file_path)

                    if armature_object is None:
                        armature_object, bone_list = setup_armature(
                            source_collection, drs_file
                        )

                    state_collection_name = f"Mesh_State_{mesh_set.state_num}"
                    state_collection = find_or_create_collection(
                        state_based_mesh_set_collection, state_collection_name
                    )

                    state_meshes_collection: bpy.types.Collection = (
                        bpy.data.collections.new("Meshes_Collection")
                    )
                    state_collection.children.link(state_meshes_collection)

                    for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
                        mesh_object, _ = create_mesh_object(
                            drs_file,
                            mesh_index,
                            dir_name,
                            base_name,
                            armature_object,
                        )
                        state_meshes_collection.objects.link(mesh_object)

                    if drs_file.collision_shape is not None and import_collision_shape:
                        import_collision_shapes(state_collection, drs_file)

                        if (
                            import_ik_atlas
                            and drs_file.csk_skeleton is not None
                            and armature_object is not None
                            and drs_file.animation_set is not None
                            and bone_list is not None
                        ):
                            import_animation_ik_atlas(
                                armature_object, drs_file.animation_set, bone_list
                            )

            # Get individual desctruction States
            if import_debris:
                destruction_collection: bpy.types.Collection = bpy.data.collections.new(
                    "Destruction_State_Collection"
                )
                source_collection.children.link(destruction_collection)
                process_debris_import(
                    module.state_based_mesh_set,
                    destruction_collection,
                    dir_name,
                    base_name,
                )

    return armature_object, bone_list


def load_bmg(
    context: bpy.types.Context,
    filepath="",
    apply_transform=True,
    import_collision_shape=False,
    import_animation=True,
    smooth_animation=True,
    import_ik_atlas=False,
    import_debris=True,
    import_construction=True,
    import_geomesh=False,
    import_obbtree=False,
    limit_obb_depth=5,
    import_bb=False,
):
    start_time = time.time()
    dir_name = os.path.dirname(filepath)
    base_name = os.path.basename(filepath).split(".")[0]
    source_collection: bpy.types.Collection = bpy.data.collections.new(
        "DRSModel_" + base_name
    )
    context.collection.children.link(source_collection)
    bmg_file: BMG = BMG().read(filepath)

    # persist_locator_blob_on_collection(source_collection, bmg_file)
    persist_animset_blob_on_collection(source_collection, bmg_file)

    # Models share the same Skeleton Files, so we only need to create one Armature and share it across all sub-modules!
    armature_object = None
    bone_list = None

    # Ground Decal
    if bmg_file.mesh_set_grid.ground_decal is not None:
        # Decal Collection
        ground_decal_collection: bpy.types.Collection = bpy.data.collections.new(
            "GroundDecal_Collection"
        )
        source_collection.children.link(ground_decal_collection)
        # Load the DRS Files
        ground_decal: DRS = DRS().read(
            os.path.join(dir_name, bmg_file.mesh_set_grid.ground_decal)
        )
        # Load the Meshes
        for mesh_index in range(ground_decal.cdsp_mesh_file.mesh_count):
            # Create the Mesh Data
            mesh_data = create_static_mesh(ground_decal.cdsp_mesh_file, mesh_index)
            # Create the Mesh Object and add the Mesh Data to it
            mesh_object: bpy.types.Object = bpy.data.objects.new(
                f"GroundDecal{mesh_index}", mesh_data
            )
            # Create the Material Data
            material_data = create_material(
                dir_name,
                mesh_index,
                ground_decal.cdsp_mesh_file.meshes[mesh_index],
                "GroundDecal",
            )
            # Assign the Material to the Mesh
            mesh_data.materials.append(material_data)
            # Link the Mesh Object to the Source Collection
            ground_decal_collection.objects.link(mesh_object)

    # Collision Shape
    if bmg_file.collision_shape is not None and import_collision_shape:
        # Create a Collision Shape Collection to store the Collision Shape Objects
        collision_shape_collection: bpy.types.Collection = bpy.data.collections.new(
            "CollisionShapes_Collection"
        )
        source_collection.children.link(collision_shape_collection)
        # Create a Box Collection to store the Box Objects
        box_collection: bpy.types.Collection = bpy.data.collections.new(
            "Boxes_Collection"
        )
        collision_shape_collection.children.link(box_collection)
        for _ in range(bmg_file.collision_shape.box_count):
            box_object = create_collision_shape_box_object(
                bmg_file.collision_shape.boxes[_], _
            )
            box_collection.objects.link(box_object)
            # TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
            box_object.location = (
                box_object.location.x,
                box_object.location.y,
                -box_object.location.z,
            )

        # Create a Sphere Collection to store the Sphere Objects
        sphere_collection: bpy.types.Collection = bpy.data.collections.new(
            "Spheres_Collection"
        )
        collision_shape_collection.children.link(sphere_collection)
        for _ in range(bmg_file.collision_shape.sphere_count):
            sphere_object = create_collision_shape_sphere_object(
                bmg_file.collision_shape.spheres[_], _
            )
            sphere_collection.objects.link(sphere_object)

        # Create a Cylinder Collection to store the Cylinder Objects
        cylinder_collection: bpy.types.Collection = bpy.data.collections.new(
            "Cylinders_Collection"
        )
        collision_shape_collection.children.link(cylinder_collection)
        for _ in range(bmg_file.collision_shape.cylinder_count):
            cylinder_object = create_collision_shape_cylinder_object(
                bmg_file.collision_shape.cylinders[_], _
            )
            cylinder_collection.objects.link(cylinder_object)

    # Import Mesh Set Grid
    if bmg_file.mesh_set_grid is not None:
        armature_object, bone_list = import_mesh_set_grid(
            bmg_file,
            source_collection,
            armature_object,
            dir_name,
            base_name,
            import_debris,
            import_collision_shape,
            import_ik_atlas,
        )

    # Import Construction
    if import_construction:
        slocator_collection: bpy.types.Collection = bpy.data.collections.new(
            "SLocators_Collection"
        )
        source_collection.children.link(slocator_collection)
        for slocator in bmg_file.mesh_set_grid.cdrw_locator_list.slocators:
            if slocator.file_name_length > 0 and slocator.class_type == "Construction":
                location = (
                    slocator.cmat_coordinate_system.position.x,
                    slocator.cmat_coordinate_system.position.y,
                    slocator.cmat_coordinate_system.position.z,
                )
                rotation = (
                    slocator.cmat_coordinate_system.matrix.matrix
                )  # Tuple ((float, float, float), (float, float, float), (float, float, float))
                rotation_matrix = [
                    list(rotation[i : i + 3]) for i in range(0, len(rotation), 3)
                ]
                transposed_rotation = Matrix(rotation_matrix).transposed()
                # Create a new Matrix with the Location and Rotation
                local_matrix = (
                    Matrix.Translation(location) @ transposed_rotation.to_4x4()
                )
                # We need to move two directory up to find the construction folder
                construction_dir = os.path.join(dir_name, "..", "..", "construction")
                # Check for file ending (DRS or BMS)

                if slocator.file_name.endswith(".bms"):
                    bms_file: BMS = BMS().read(
                        os.path.join(construction_dir, slocator.file_name)
                    )
                    module_name = slocator.class_type + "_" + str(slocator.bone_id)
                    import_state_based_mesh_set(
                        bms_file.state_based_mesh_set,
                        slocator_collection,
                        armature_object,
                        bone_list,
                        construction_dir,
                        bms_file,
                        import_animation,
                        smooth_animation,
                        import_debris,
                        import_collision_shape,
                        import_ik_atlas,
                        module_name,
                        slocator,
                        "Construction_",
                    )
                elif slocator.file_name.endswith(".drs"):
                    drs_file: DRS = DRS().read(
                        os.path.join(construction_dir, slocator.file_name)
                    )
                    for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
                        # Create the Mesh Data
                        mesh_data = create_static_mesh(
                            drs_file.cdsp_mesh_file, mesh_index
                        )
                        # Create the Mesh Object and add the Mesh Data to it
                        mesh_object: bpy.types.Object = bpy.data.objects.new(
                            f"CDspMeshFile_{slocator.class_type}", mesh_data
                        )
                        # Create the Material Data
                        material_data = create_material(
                            construction_dir,
                            mesh_index,
                            drs_file.cdsp_mesh_file.meshes[mesh_index],
                            base_name + "_Construction_" + str(mesh_index),
                        )
                        # Assign the Material to the Mesh
                        mesh_data.materials.append(material_data)
                        # Apply the Transformations to the Mesh Object
                        mesh_object.matrix_world = local_matrix
                        # Link the Mesh Object to the Source Collection
                        slocator_collection.objects.link(mesh_object)
                else:
                    logger.log(
                        f"Construction file {slocator.file_name} has an unsupported file ending.",
                        "Error",
                        "ERROR",
                    )
            elif slocator.file_name_length > 0:
                logger.log(
                    f"Slocator {slocator.file_name} is not a Construction file (but {slocator.class_type}). Skipping it.",
                    "Error",
                    "ERROR",
                )

    # Import Animation
    if (
        bmg_file.animation_set is not None
        and armature_object is not None
        and bones_list is not None
        and import_animation
    ):
        with ensure_mode("POSE"):
            for animation_key in bmg_file.animation_set.mode_animation_keys:
                for variant in animation_key.animation_set_variants:
                    ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
                    # Create the Animation
                    import_ska_animation(
                        ska_file,
                        armature_object,
                        bone_list,
                        variant.file,
                        smooth_animation,
                        filepath,
                        map_collection=source_collection,
                    )

    # Apply the Transformations to the Source Collection
    parent_under_game_axes(source_collection, apply_transform)

    # Print the Time Measurement
    logger.log(
        f"Imported {base_name} in {time.time() - start_time:.2f} seconds.",
        "Import Time",
        "INFO",
    )
    logger.display()

    return {"FINISHED"}


# endregion

# region Export Blender Model to DRS


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


def create_unified_mesh(meshes_collection: bpy.types.Collection) -> bpy.types.Mesh:
    """Create a unified Mesh from a Collection of Meshes."""

    with new_bmesh() as bm_out:
        for obj in meshes_collection.objects:
            if obj.type != "MESH":
                continue

            # Build a temporary BMesh from the object's RAW mesh (rest pose)
            bm_tmp = bmesh.new()
            bm_tmp.from_mesh(obj.data)
            # Apply object->world transform (includes parents like GameOrientation)
            bm_tmp.transform(obj.matrix_world)

            # Pipe into the output BMesh
            tmp_me = bpy.data.meshes.new(name="__tmp__")
            bm_tmp.to_mesh(tmp_me)
            bm_tmp.free()

            bm_out.from_mesh(tmp_me)
            bpy.data.meshes.remove(tmp_me)

        # Weld tiny duplicates after the transform
        bm_out.verts.ensure_lookup_table()
        remove_doubles(bm_out, verts=bm_out.verts, dist=1e-6)

        # Bake to a new Mesh
        unified = bpy.data.meshes.new("unified_mesh")
        bm_out.to_mesh(unified)

    return unified


def create_cgeo_mesh(unique_mesh: bpy.types.Mesh) -> CGeoMesh:
    """Create a CGeoMesh from a Blender Mesh Object."""
    _cgeo_mesh = CGeoMesh()
    _cgeo_mesh.index_count = len(unique_mesh.polygons) * 3
    _cgeo_mesh.vertex_count = len(unique_mesh.vertices)
    _cgeo_mesh.faces = []
    _cgeo_mesh.vertices = []

    for _face in unique_mesh.polygons:
        new_face = Face()
        new_face.indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
        _cgeo_mesh.faces.append(new_face)

    for _vertex in unique_mesh.vertices:
        _cgeo_mesh.vertices.append(
            Vector4(_vertex.co.x, _vertex.co.y, _vertex.co.z, 1.0)
        )

    return _cgeo_mesh


def create_cgeo_obb_tree(unified_mesh: bpy.types.Mesh) -> CGeoOBBTree:
    unified_mesh.calc_loop_triangles()
    vcount = len(unified_mesh.vertices)
    verts = np.empty(vcount * 3, dtype=np.float64)
    unified_mesh.vertices.foreach_get("co", verts)
    verts = verts.reshape(vcount, 3)
    tris = np.array(
        [lt.vertices[:] for lt in unified_mesh.loop_triangles], dtype=np.int32
    )
    tri_count = len(tris)
    if tri_count == 0:
        tree = CGeoOBBTree()
        tree.matrix_count = 0
        tree.obb_nodes = []
        tree.triangle_count = 0
        tree.faces = []
        return tree

    tri_centroids = verts[tris].mean(axis=1)

    def volume_from_axes(points: np.ndarray, A: np.ndarray):
        P = points @ A
        mn = P.min(axis=0)
        mx = P.max(axis=0)
        e = 0.5 * (mx - mn)
        return float(8.0 * e[0] * e[1] * e[2])

    def pca_axes(points: np.ndarray):
        c = points.mean(axis=0)
        X = points - c
        _U, _S, Vt = np.linalg.svd(X, full_matrices=False)
        A = Vt.T
        if np.linalg.det(A) < 0:
            A[:, 2] *= -1.0
        return A

    def rodrigues(w):
        t = np.linalg.norm(w)
        if t < 1e-12:
            return np.eye(3)
        k = w / t
        K = np.array(
            [[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]], dtype=np.float64
        )
        return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * (K @ K)

    def nm_simplex(func, x0, step, iters):
        x = np.array(
            [
                x0,
                x0 + np.array([step, 0, 0]),
                x0 + np.array([0, step, 0]),
                x0 + np.array([0, 0, step]),
            ],
            dtype=np.float64,
        )
        fx = np.array([func(xi) for xi in x], dtype=np.float64)
        for _ in range(iters):
            order = np.argsort(fx)
            x = x[order]
            fx = fx[order]
            c = x[:3].mean(axis=0)
            xr = c + (c - x[3])
            fr = func(xr)
            if fr < fx[0]:
                xe = c + 2 * (xr - c)
                fe = func(xe)
                x[3], fx[3] = (xe, fe) if fe < fr else (xr, fr)
            elif fr < fx[2]:
                x[3], fx[3] = xr, fr
            else:
                xc = c + 0.5 * (x[3] - c)
                fc = func(xc)
                if fc < fx[3]:
                    x[3], fx[3] = xc, fc
                else:
                    x[1:] = x[0] + 0.5 * (x[1:] - x[0])
                    fx[1:] = np.array([func(xi) for xi in x[1:]])
        order = np.argsort(fx)
        return x[order][0], fx[order][0]

    def hybbrid_orientation(points: np.ndarray):
        # Seeds: PCA, identity, plus up to two hull feature frames.
        bm = bmesh.new()
        for p in points:
            bm.verts.new((float(p[0]), float(p[1]), float(p[2])))
        bm.verts.ensure_lookup_table()
        bmesh.ops.convex_hull(bm, input=bm.verts[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        H = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
        normals = [
            np.array(f.normal[:], dtype=np.float64)
            for f in bm.faces
            if f.normal.length > 1e-12
        ]
        edges = []
        for e in bm.edges:
            d = H[e.verts[1].index] - H[e.verts[0].index]
            n = np.linalg.norm(d)
            if n > 1e-9:
                edges.append(d / n)
        bm.free()

        seeds = [pca_axes(points), np.eye(3)]
        if normals:
            z = normals[0] / (np.linalg.norm(normals[0]) + 1e-30)
            if edges:
                t = edges[0]
                u = t - z * (t @ z)
                if np.linalg.norm(u) > 1e-9:
                    u /= np.linalg.norm(u)
                    v = np.cross(z, u)
                    seeds.append(np.column_stack([u, v, z]))
        if len(normals) > 1:
            z = normals[-1] / (np.linalg.norm(normals[-1]) + 1e-30)
            if edges:
                t = edges[-1]
                u = t - z * (t @ z)
                if np.linalg.norm(u) > 1e-9:
                    u /= np.linalg.norm(u)
                    v = np.cross(z, u)
                    seeds.append(np.column_stack([u, v, z]))

        best_A = seeds[0]
        best_V = volume_from_axes(points, best_A)
        step = 0.15  # ~8.6°
        iters = 10

        for A0 in seeds:

            def func(w):
                R = rodrigues(w)
                A = A0 @ R
                if np.linalg.det(A) < 0:
                    A[:, 2] = np.cross(A[:, 0], A[:, 1])
                return volume_from_axes(points, A)

            w_best, v_best = nm_simplex(func, np.zeros(3), step, iters)
            if v_best < best_V:
                R = rodrigues(w_best)
                best_A = A0 @ R
                if np.linalg.det(best_A) < 0:
                    best_A[:, 2] = np.cross(best_A[:, 0], best_A[:, 1])
                best_V = v_best

        P = points @ best_A
        mn = P.min(axis=0)
        mx = P.max(axis=0)
        e = 0.5 * (mx - mn)
        mid = 0.5 * (mx + mn)
        c = mid @ best_A.T
        return c, best_A, np.maximum(e + 1e-6, 1e-9)

    def build(face_idx: np.ndarray, depth: int, nodes: list) -> int:
        uniq = np.unique(tris[face_idx].reshape(-1))
        pts = verts[uniq]
        c, A, E = hybbrid_orientation(pts)

        cs = CMatCoordinateSystem()
        cs.position = Vector3(x=float(c[0]), y=float(c[1]), z=float(c[2]))
        scaled = A * E[None, :]
        M_store = scaled.T  # store rows; importer does one transpose
        cs.matrix = Matrix3x3(
            matrix=[
                float(M_store[0, 0]),
                float(M_store[0, 1]),
                float(M_store[0, 2]),
                float(M_store[1, 0]),
                float(M_store[1, 1]),
                float(M_store[1, 2]),
                float(M_store[2, 0]),
                float(M_store[2, 1]),
                float(M_store[2, 2]),
            ]
        )

        node = OBBNode()
        node.oriented_bounding_box = cs
        node.first_child_index = 0
        node.second_child_index = 0
        node.skip_pointer = 0
        node.node_depth = depth
        node.triangle_offset = 0
        node.total_triangles = int(len(face_idx))

        my = len(nodes)
        nodes.append(node)

        MIN_TRIS = 12
        MAX_DEPTH = 32
        if len(face_idx) <= MIN_TRIS or depth >= MAX_DEPTH:
            return my

        axis_id = int(np.argmax(E))
        dir_world = A[:, axis_id] / (np.linalg.norm(A[:, axis_id]) + 1e-30)
        vals = (tri_centroids[face_idx] - c) @ dir_world
        med = np.median(vals)
        left_mask = vals <= med
        right_mask = ~left_mask
        left_idx = face_idx[left_mask]
        right_idx = face_idx[right_mask]
        if len(left_idx) == 0 or len(right_idx) == 0:
            order = np.argsort(vals)
            half = len(order) // 2
            if half == 0:
                return my
            left_idx = face_idx[order[:half]]
            right_idx = face_idx[order[half:]]

        li = build(left_idx, depth + 1, nodes)
        ri = build(right_idx, depth + 1, nodes)
        nodes[my].first_child_index = li if li > 0 else 0
        nodes[my].second_child_index = ri if ri > 0 else 0
        return my

    nodes: list[OBBNode] = []
    all_faces = np.arange(tri_count, dtype=np.int32)
    build(all_faces, 0, nodes)

    tree = CGeoOBBTree()
    tree.matrix_count = len(nodes)
    tree.obb_nodes = nodes
    tree.triangle_count = tri_count
    out_faces = []
    for a, b, c in tris:
        _face = Face()
        _face.indices = [int(a), int(b), int(c)]
        out_faces.append(_face)
    tree.faces = out_faces
    return tree


def create_cdsp_joint_map(
    add_skin_mesh: bool,
    mesh_bone_data: List[Dict[str, int]],
    bone_map: Dict[str, Dict[str, int]],
) -> CDspJointMap:
    """Create a CDspJointMap. If empty is True, the CDspJointMap will be empty."""
    _joint_map = CDspJointMap()

    if add_skin_mesh:
        for _mesh_index, per_mesh_bone_data in enumerate(mesh_bone_data):
            _joint_map.joint_group_count += 1
            _joint_group = JointGroup()
            _joint_group.joint_count = len(per_mesh_bone_data) - 1  # -1 for root_ref
            _joint_group.joints = [-1] * _joint_group.joint_count
            root_added = False
            for bone_name, local_index in per_mesh_bone_data.items():
                if bone_name != "root_ref":
                    bone_identifier = bone_map[bone_name]["id"]
                    _joint_group.joints[local_index] = bone_identifier
                    if bone_identifier == 0:
                        root_added = True
                        # Update the root_ref in the mesh_bone_data
                        mesh_bone_data[_mesh_index]["root_ref"] = local_index
            _joint_map.joint_groups.append(_joint_group)
            # Assure, that we have added the root in any case
            if not root_added:
                # Add the root to the end of the list
                _joint_group.joints.extend([0])
                _joint_group.joint_count += 1
                # Add a note to the mesh_bone_data
                mesh_bone_data[_mesh_index]["root_ref"] = _joint_group.joint_count - 1
    else:
        _joint_map.joint_group_count = 0
        _joint_map.joint_groups = []
    return _joint_map


def set_color_map(
    color_map_node: bpy.types.Node,
    new_mesh: BattleforgeMesh,
    mesh_index: int,
    model_name: str,
    folder_path: str,
) -> bool:
    if color_map_node is None:
        logger.log(
            "The color_map is None. Please check the Material Node.", "Error", "ERROR"
        )
        return False

    img = color_map_node.links[0].from_node.image
    if img is None:
        logger.log(
            "The color_map Texture is not an Image or the Image is None!",
            "Error",
            "ERROR",
        )
        return False

    # Update your new_mesh texture list as needed here
    new_mesh.textures.length += 1
    color_map_texture = Texture()
    color_map_texture.name = get_converted_texture(
        img, model_name, mesh_index, folder_path, file_ending="_col", dxt_format="DXT5"
    )
    color_map_texture.length = len(color_map_texture.name)
    color_map_texture.identifier = 1684432499
    new_mesh.textures.textures.append(color_map_texture)

    return True


def set_normal_map(
    normal_map_node: bpy.types.Node,
    new_mesh: BattleforgeMesh,
    mesh_index: int,
    model_name: str,
    folder_path: str,
    bool_param_bit_flag: int,
) -> int:
    if normal_map_node is None:
        logger.log(
            "The normal_map is None. Please check the Material Node.", "Error", "ERROR"
        )
        return False

    img = normal_map_node.links[0].from_node.image
    if img is None:
        logger.log(
            "The normal_map Texture is not an Image or the Image is None!",
            "Error",
            "ERROR",
        )
        return False

    new_mesh.textures.length += 1
    normal_map_texture = Texture()
    normal_map_texture.name = get_converted_texture(
        img,
        model_name,
        mesh_index,
        folder_path,
        file_ending="_nor",
        dxt_format="DXT1",
        extra_args=["-at", "0.0"],
    )
    normal_map_texture.length = len(normal_map_texture.name)
    normal_map_texture.identifier = 1852992883
    new_mesh.textures.textures.append(normal_map_texture)
    bool_param_bit_flag += 100000000000000000

    return bool_param_bit_flag


def set_metallic_roughness_emission_map(
    metallic_map_node: bpy.types.Node,
    roughness_map_node: bpy.types.Node,
    emission_map_node: bpy.types.Node,
    new_mesh: BattleforgeMesh,
    mesh_index: int,
    model_name: str,
    folder_path: str,
    bool_param_bit_flag: int,
) -> int:

    # Check if any of the maps are linked
    if not any(
        map_node and map_node.is_linked
        for map_node in [metallic_map_node, roughness_map_node, emission_map_node]
    ):
        return -1

    # Retrieve images and pixels
    img_r, pixels_r = get_image_and_pixels(metallic_map_node, "metallic_map")
    img_g, pixels_g = get_image_and_pixels(roughness_map_node, "roughness_map")
    img_a, pixels_a = get_image_and_pixels(emission_map_node, "emission_map")

    # Determine image dimensions
    for img in [img_r, img_g, img_a]:
        if img:
            width, height = img.size
            break
    else:
        logger.log(
            "No Image is set for the parameter map. Please set an Image!",
            "Info",
            "INFO",
        )
        return -1

    # Combine the images into a new image
    new_img = bpy.data.images.new(
        name="temp_image", width=width, height=height, alpha=True, float_buffer=False
    )
    new_pixels = []
    total_pixels = width * height * 4

    for i in range(0, total_pixels, 4):
        new_pixels.extend(
            [
                pixels_r[i] if pixels_r else 0,  # Red channel
                pixels_g[i + 1] if pixels_g else 0,  # Green channel
                0,  # Blue channel (placeholder for Fluid Map)
                pixels_a[i + 3] if pixels_a else 0,  # Alpha channel
            ]
        )

    new_img.pixels = new_pixels
    new_img.file_format = "PNG"
    new_img.update()

    # Update mesh textures and flags
    new_mesh.textures.length += 1
    metallic_map_texture = Texture()
    metallic_map_texture.name = get_converted_texture(
        new_img,
        model_name,
        mesh_index,
        folder_path,
        file_ending="_par",
        dxt_format="DXT5",
        extra_args=["-bc", "d"],
    )
    metallic_map_texture.length = len(metallic_map_texture.name)
    metallic_map_texture.identifier = 1936745324
    new_mesh.textures.textures.append(metallic_map_texture)
    bool_param_bit_flag += 10000000000000000

    return bool_param_bit_flag


def set_refraction_color_and_map(
    refraction_color_node: bpy.types.Node,
    refraction_map_node: bpy.types.Node,
    new_mesh: BattleforgeMesh,
    mesh_index: int,
    model_name: str,
    folder_path: str,
) -> List[float]:
    # Check if the Refraction Color is set
    if refraction_color_node is None:
        return [0.0, 0.0, 0.0]

    refraction_color_parent = refraction_color_node.links[0].from_node
    rgb = list(refraction_color_parent.outputs[0].default_value)
    # Delete the Alpha Channel
    del rgb[3]

    refraction_map_parent = refraction_map_node.links[0].from_node
    img = refraction_map_parent.image

    if img is None:
        logger.log(
            "The refraction_map Texture is not an Image or the Image is None!",
            "Error",
            "ERROR",
        )
        return [0.0, 0.0, 0.0]

    new_mesh.textures.length += 1
    refraction_map_texture = Texture()
    refraction_map_texture.name = get_converted_texture(
        img, model_name, mesh_index, folder_path, file_ending="_ref", dxt_format="DXT5"
    )
    refraction_map_texture.length = len(refraction_map_texture.name)
    refraction_map_texture.identifier = 1919116143
    new_mesh.textures.textures.append(refraction_map_texture)

    return rgb


def create_mesh(
    mesh: bpy.types.Object,
    mesh_index: int,
    model_name: str,
    folder_path: str,
    flip_normals: bool,
    add_skin_mesh: bool = False,
) -> Tuple[Union[BattleforgeMesh, None], Dict[str, int]]:
    """Create a Battleforge Mesh from a Blender Mesh Object."""
    if flip_normals:
        with ensure_mode("EDIT"):
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.flip_normals()
            bpy.ops.mesh.select_all(action="DESELECT")

    mesh.data.calc_tangents()
    per_mesh_bone_data: Dict[str, int] = {}
    per_mesh_bone_data["root_ref"] = -1

    new_mesh = BattleforgeMesh()
    new_mesh.vertex_count = len(mesh.data.vertices)
    new_mesh.face_count = len(mesh.data.polygons)
    new_mesh.faces = []

    new_mesh.mesh_count = 2 if not add_skin_mesh else 3
    new_mesh.mesh_data = []

    _mesh_0_data = MeshData()
    _mesh_0_data.vertices = [Vertex() for _ in range(new_mesh.vertex_count)]
    _mesh_0_data.revision = 133121
    _mesh_0_data.vertex_size = 32

    _mesh_1_data = MeshData()
    _mesh_1_data.vertices = [Vertex() for _ in range(new_mesh.vertex_count)]
    _mesh_1_data.revision = 12288
    _mesh_1_data.vertex_size = 24

    if add_skin_mesh:
        _mesh_2_data = MeshData()
        _mesh_2_data.vertices = [Vertex() for _ in range(new_mesh.vertex_count)]
        _mesh_2_data.revision = 12
        _mesh_2_data.vertex_size = 8

    for _face in mesh.data.polygons:
        new_face = Face()
        new_face.indices = []
        for index in _face.loop_indices:
            vertex: bpy.types.MeshLoop = mesh.data.loops[index]
            vertex2: bpy.types.MeshVertex = mesh.data.vertices[vertex.vertex_index]
            position = vertex2.co
            normal = vertex.normal
            uv = mesh.data.uv_layers.active.data[index].uv.copy()
            uv.y = -uv.y
            _mesh_0_data.vertices[vertex.vertex_index] = Vertex(
                position=position, normal=normal, texture=uv
            )

            if new_mesh.mesh_count > 1:
                tangent = vertex.tangent
                bitangent = vertex.bitangent_sign * normal.cross(tangent)
                # Switch X and Y as the Tangent is flipped
                tangent = Vector((tangent.y, tangent.x, tangent.z))
                _mesh_1_data.vertices[vertex.vertex_index] = Vertex(
                    tangent=tangent, bitangent=bitangent
                )

            if add_skin_mesh:
                weights = []
                bone_indices = []
                for group in vertex2.groups:
                    # only if weight > 0.0
                    if group.weight <= 0.0:
                        continue
                    # Weight is between 0.0 and 1.0, we need to convert it to 0-255
                    weight = int(group.weight * 255)
                    bone_name = mesh.vertex_groups[group.group].name
                    local_index = group.group
                    # We need to use local_index and bone_name and map them into the JointMap
                    if bone_name not in per_mesh_bone_data:
                        per_mesh_bone_data[bone_name] = local_index
                    weights.append(weight)
                    bone_indices.append(local_index)

                while len(weights) < 4:
                    weights.append(0)
                    bone_indices.append(-1)  # Root Reference, we update that later.

                # Check if we have more than 4 weights, if so, we need to clip them
                if len(weights) > 4:
                    logger.log(
                        f"More than 4 weights found for vertex {vertex.vertex_index}. Clipping to 4.",
                        "Warning",
                        "WARNING",
                    )
                    # We remove the lowest weights until we have 4 left
                    while len(weights) > 4:
                        min_weight_index = weights.index(min(weights))
                        weights.pop(min_weight_index)
                        bone_indices.pop(min_weight_index)

                _mesh_2_data.vertices[vertex.vertex_index] = Vertex(
                    raw_weights=weights, bone_indices=bone_indices
                )

            new_face.indices.append(vertex.vertex_index)

        new_mesh.faces.append(new_face)

    new_mesh.mesh_data.append(_mesh_0_data)
    new_mesh.mesh_data.append(_mesh_1_data)
    if add_skin_mesh:
        new_mesh.mesh_data.append(_mesh_2_data)

    # We need to investigate the Bounding Box further, as it seems to be wrong
    (
        new_mesh.bounding_box_lower_left_corner,
        new_mesh.bounding_box_upper_right_corner,
    ) = get_bb(mesh)
    new_mesh.material_id = 25702
    # Node Group for Access the Data
    mesh_material = mesh.material_slots[0].material
    material_nodes = mesh_material.node_tree.nodes
    # Find the DRS Node
    color_map = None
    # alpha_map = None # Needed?
    metallic_map = None
    roughness_map = None
    emission_map = None
    normal_map = None
    refraction_map = None
    refraction_color = None
    flu_map = None
    skip_normal_map = True
    skip_param_map = True

    for node in material_nodes:
        if node.type == "GROUP":
            if node.node_tree.name.find("DRS") != -1:
                color_map = node.inputs[0]
                # alpha_map = node.inputs[1] # Needed?
                if len(node.inputs) >= 5:
                    metallic_map = node.inputs[2]
                    roughness_map = node.inputs[3]
                    emission_map = node.inputs[4]
                    skip_param_map = False
                if len(node.inputs) >= 6:
                    normal_map = node.inputs[5]
                    skip_normal_map = False
                if len(node.inputs) >= 8:
                    refraction_color = node.inputs[6]
                    refraction_map = node.inputs[7]
                break

    # if flu_map is None or flu_map.is_linked is False:
    # new_mesh.material_parameters = -86061055
    # -86061055: Bool, Textures, Refraction, Materials
    # -86061054: Bool, Textures, Refraction, Materials, LOD
    # -86061053: Bool, Textures, Refraction, Materials, LOD, Empty String
    # -86061052: Bool, Textures, Refraction, Materials, LOD, Empty String, Material Stuff
    # -86061051: Bool, Textures, Refraction, Materials, LOD, Empty String, Material Stuff
    # else:
    # -86061050: Bool, Textures, Refraction, Materials, LOD, Empty String, Material Stuff, Flow
    new_mesh.material_parameters = -86061050  # Hex: 0xFADED006
    new_mesh.material_stuff = 0  # Added for Hex 0xFADED004+
    # Level of Detail
    new_mesh.level_of_detail = LevelOfDetail()  # Added for Hex 0xFADED002+
    # Empty String
    new_mesh.empty_string = EmptyString()  # Added for Hex 0xFADED003+
    # Flow
    new_mesh.flow = Flow()

    # Individual Material Parameters depending on the MaterialID:
    new_mesh.bool_parameter = 0
    bool_param_bit_flag = 0
    # Textures
    new_mesh.textures = Textures()

    # Check if the Color Map is set
    try:
        if not set_color_map(color_map, new_mesh, mesh_index, model_name, folder_path):
            return None, per_mesh_bone_data
    except Exception as e: # pylint: disable=broad-except
        logger.log(
            f"An error occurred while setting the Color Map for mesh {mesh.name}: {e}",
            "Error",
            "ERROR",
        )
        return None, per_mesh_bone_data

    # Check if the Normal Map is set
    if not skip_normal_map:
        try:
            bool_param_bit_flag = set_normal_map(
                normal_map,
                new_mesh,
                mesh_index,
                model_name,
                folder_path,
                bool_param_bit_flag,
            )
        except Exception as e: # pylint: disable=broad-except
            logger.log(
                f"An error occurred while setting the Normal Map for mesh {mesh.name}: {e}",
                "Error",
                "ERROR",
            )
            return None, per_mesh_bone_data

    # Check if the Metallic, Roughness and Emission Map is set
    if not skip_param_map:
        try:
            bool_param_bit_flag = set_metallic_roughness_emission_map(
                metallic_map,
                roughness_map,
                emission_map,
                new_mesh,
                mesh_index,
                model_name,
                folder_path,
                bool_param_bit_flag,
            )
            if bool_param_bit_flag == -1:
                return None, per_mesh_bone_data
        except Exception as e: # pylint: disable=broad-except
            logger.log(
                f"An error occurred while setting the Parameter Map for mesh {mesh.name}: {e}",
                "Error",
                "ERROR",
            )
            return None, per_mesh_bone_data

    # Set the Bool Parameter by a bin -> dec conversion
    new_mesh.bool_parameter = int(str(bool_param_bit_flag), 2)
    # --- SR override from UI: if the mesh has drs_material set, prefer that value
    try:
        mp = getattr(mesh, "drs_material", None)
        if mp and int(mp.bool_parameter) >= 0:
            new_mesh.bool_parameter = int(mp.bool_parameter) & 0xFFFFFFFF
    except Exception:
        logger.log(
            f"An error occurred while setting the Bool Parameter override for mesh {mesh.name}.",
            "Warning",
            "WARNING",
        )
        pass
    new_mesh.materials = Materials()

    # --- SR override Flow from UI (only when enabled)
    try:
        fp = getattr(mesh, "drs_flow", None)
        if fp and bool(fp.use_flow):
            new_mesh.flow.length = 4
            # push vectors
            v = new_mesh.flow
            # each is Vector4(x,y,z,w)
            (
                v.max_flow_speed.x,
                v.max_flow_speed.y,
                v.max_flow_speed.z,
                v.max_flow_speed.w,
            ) = fp.max_flow_speed
            (
                v.min_flow_speed.x,
                v.min_flow_speed.y,
                v.min_flow_speed.z,
                v.min_flow_speed.w,
            ) = fp.min_flow_speed
            (
                v.flow_speed_change.x,
                v.flow_speed_change.y,
                v.flow_speed_change.z,
                v.flow_speed_change.w,
            ) = fp.flow_speed_change
            v.flow_scale.x, v.flow_scale.y, v.flow_scale.z, v.flow_scale.w = (
                fp.flow_scale
            )
            # material_parameters path that includes Flow is -86061050 in your writer
            # (that branch writes 'flow' and the extra material blocks)
            new_mesh.material_parameters = -86061050
    except Exception:
        logger.log(
            f"An error occurred while setting the Flow override for mesh {mesh.name}.",
            "Warning",
            "WARNING",
        )

    # Refraction
    refraction = Refraction()
    refraction.length = 1
    refraction.rgb = set_refraction_color_and_map(
        refraction_color, refraction_map, new_mesh, mesh_index, model_name, folder_path
    )
    new_mesh.refraction = refraction

    # Materials
    # Almost no material data is used in the game, so we set it to defaults
    new_mesh.materials = Materials()

    return new_mesh, per_mesh_bone_data


def create_cdsp_mesh_file(
    meshes_collection: bpy.types.Collection,
    model_name: str,
    filepath: str,
    flip_normals: bool,
    add_skin_mesh: bool = False,
):
    """Create a CDspMeshFile from a Collection of Meshes."""
    _cdsp_meshfile = CDspMeshFile()
    _cdsp_meshfile.mesh_count = 0

    mesh_bone_data: List[Dict[str, int]] = []

    try:
        for mesh in meshes_collection.objects:
            if mesh.type == "MESH":
                _mesh, _per_mesh_bone_data = create_mesh(
                    mesh,
                    _cdsp_meshfile.mesh_count,
                    model_name,
                    filepath,
                    flip_normals,
                    add_skin_mesh,
                )
                if _mesh is None:
                    return
                _cdsp_meshfile.meshes.append(_mesh)
                _cdsp_meshfile.mesh_count += 1
                mesh_bone_data.append(_per_mesh_bone_data)
    except Exception as e: # pylint: disable=broad-except
        logger.log(
            f"An error occurred while creating the CDspMeshFile: {e}",
            "Error",
            "ERROR",
        )
        return None, None

    _cdsp_meshfile.bounding_box_lower_left_corner = Vector3(0, 0, 0)
    _cdsp_meshfile.bounding_box_upper_right_corner = Vector3(0, 0, 0)

    for _mesh in _cdsp_meshfile.meshes:
        _cdsp_meshfile.bounding_box_lower_left_corner.x = min(
            _cdsp_meshfile.bounding_box_lower_left_corner.x,
            _mesh.bounding_box_lower_left_corner.x,
        )
        _cdsp_meshfile.bounding_box_lower_left_corner.y = min(
            _cdsp_meshfile.bounding_box_lower_left_corner.y,
            _mesh.bounding_box_lower_left_corner.y,
        )
        _cdsp_meshfile.bounding_box_lower_left_corner.z = min(
            _cdsp_meshfile.bounding_box_lower_left_corner.z,
            _mesh.bounding_box_lower_left_corner.z,
        )

        _cdsp_meshfile.bounding_box_upper_right_corner.x = max(
            _cdsp_meshfile.bounding_box_upper_right_corner.x,
            _mesh.bounding_box_upper_right_corner.x,
        )
        _cdsp_meshfile.bounding_box_upper_right_corner.y = max(
            _cdsp_meshfile.bounding_box_upper_right_corner.y,
            _mesh.bounding_box_upper_right_corner.y,
        )
        _cdsp_meshfile.bounding_box_upper_right_corner.z = max(
            _cdsp_meshfile.bounding_box_upper_right_corner.z,
            _mesh.bounding_box_upper_right_corner.z,
        )

    return _cdsp_meshfile, mesh_bone_data


def create_box_shape(box: bpy.types.Object) -> BoxShape:
    """Create a BoxShape from a Blender Object previously created by create_collision_shape_box_object."""
    # Instantiate the new BoxShape and its sub-components.
    _box_shape = BoxShape()
    _box_shape.coord_system = CMatCoordinateSystem()
    _box_shape.geo_aabox = CGeoAABox()

    # Extract the transformation from the object's world matrix.
    # The rotation part (a 3x3 matrix) and the translation (a vector) directly correspond
    # to the coordinate system used during creation.
    world_matrix = box.matrix_world
    rotation = world_matrix.to_3x3()
    translation = world_matrix.to_translation()

    # Set the coordinate system position.
    _box_shape.coord_system.position = Vector3(
        translation.x, translation.y, translation.z
    )
    # Flatten the 3x3 rotation matrix into a row-major list of 9 floats.
    _box_shape.coord_system.matrix.matrix = [
        rotation[0][0],
        rotation[0][1],
        rotation[0][2],
        rotation[1][0],
        rotation[1][1],
        rotation[1][2],
        rotation[2][0],
        rotation[2][1],
        rotation[2][2],
    ]

    # Compute the axis aligned bounding box from the object's mesh vertices (in local space).
    # These vertices were created directly from the original AABox corners.
    vertices = [v.co for v in box.data.vertices]
    if not vertices:
        raise ValueError("The object has no vertices to compute a bounding box from.")

    # Determine the minimum and maximum extents along each axis.
    min_x = min(v.x for v in vertices)
    min_y = min(v.y for v in vertices)
    min_z = min(v.z for v in vertices)
    max_x = max(v.x for v in vertices)
    max_y = max(v.y for v in vertices)
    max_z = max(v.z for v in vertices)

    _box_shape.geo_aabox.lower_left_corner = Vector3(min_x, min_y, min_z)
    _box_shape.geo_aabox.upper_right_corner = Vector3(max_x, max_y, max_z)

    return _box_shape


def create_sphere_shape(sphere: bpy.types.Object) -> SphereShape:
    """
    Exports a Blender sphere object to a foreign SphereShape.
    """
    # Initialize our export structure
    _sphere_shape = SphereShape()
    _sphere_shape.coord_system = CMatCoordinateSystem()
    _sphere_shape.geo_sphere = CGeoSphere()

    # Ensure the mesh data is up to date.
    mesh = sphere.data
    mesh.calc_loop_triangles()

    # Compute world-space coordinates for each vertex.
    vertices_world = [sphere.matrix_world @ v.co for v in mesh.vertices]
    if not vertices_world:
        raise ValueError(
            "The sphere object has no vertices to compute a bounding sphere from."
        )

    # Compute the center as the centroid of the vertices.
    # (This works well if the object is a well-formed sphere.)
    center = sum(vertices_world, Vector((0, 0, 0))) / len(vertices_world)

    # Compute the radius as the maximum distance from the center to any vertex.
    radius = max((v - center).length for v in vertices_world)

    # Assign the computed center to the exported coordinate system.
    _sphere_shape.coord_system.position = Vector3(center.x, center.y, center.z)

    # Extract a pure rotation without scaling by converting to and from a quaternion.
    # This is important if the object has non-uniform scaling.
    pure_rotation = sphere.matrix_world.to_quaternion().to_matrix()
    # Flatten the 3x3 rotation matrix in row-major order.
    _sphere_shape.coord_system.matrix.matrix = [
        pure_rotation[0][0],
        pure_rotation[0][1],
        pure_rotation[0][2],
        pure_rotation[1][0],
        pure_rotation[1][1],
        pure_rotation[1][2],
        pure_rotation[2][0],
        pure_rotation[2][1],
        pure_rotation[2][2],
    ]

    # Fill in the geometric sphere information.
    _sphere_shape.geo_sphere.radius = radius
    _sphere_shape.geo_sphere.center = Vector3(0, 0, 0)

    return _sphere_shape


def create_cylinder_shape(cylinder: bpy.types.Object) -> CylinderShape:
    """
    Exports a Blender cylinder object to a foreign CylinderShape.
    This function assumes that the cylinder was imported using a 90° X rotation
    and a translation offset of half its height.
    """
    # Initialize our export structure
    _cylinder_shape = CylinderShape()
    _cylinder_shape.coord_system = CMatCoordinateSystem()
    _cylinder_shape.geo_cylinder = CGeoCylinder()

    # Ensure the mesh data is up to date.
    mesh = cylinder.data
    mesh.calc_loop_triangles()

    # Get all vertices in world space.
    verts = [cylinder.matrix_world @ v.co for v in mesh.vertices]
    # Compute the bounding box (min and max coordinates)
    min_co = Vector(
        (min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts))
    )
    max_co = Vector(
        (max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts))
    )
    # The center of the bounding box
    center = (min_co + max_co) * 0.5

    # The exported depth (height) is the Y extent
    depth = max_co.y - min_co.y
    # Use the average of the X and Z extents to compute the radius.
    radius_x = (max_co.x - min_co.x) / 2.0
    radius_z = (max_co.z - min_co.z) / 2.0
    radius = (radius_x + radius_z) / 2.0

    # In the import, we offset the translation by adding half the depth to Y.
    # So here we subtract that offset to recover the original (foreign) translation.
    foreign_position = center - Vector((0, depth * 0.5, 0))

    # In the import the cylinder was rotated by 90° about X,
    # so we remove that extra rotation:
    # rot_inv = Matrix.Rotation(-radians(90), 4, 'X')
    # No we do not want to rotate
    rot_inv = Matrix.Identity(4)
    # Here we assume the object has no additional baked rotation.
    foreign_rot = rot_inv @ Matrix.Identity(4)
    foreign_rot_3x3 = foreign_rot.to_3x3()

    # Fill in the coordinate system data:
    _cylinder_shape.coord_system.position.x = foreign_position.x
    _cylinder_shape.coord_system.position.y = foreign_position.y
    _cylinder_shape.coord_system.position.z = foreign_position.z

    _cylinder_shape.coord_system.matrix.matrix = (
        foreign_rot_3x3[0][0],
        foreign_rot_3x3[0][1],
        foreign_rot_3x3[0][2],
        foreign_rot_3x3[1][0],
        foreign_rot_3x3[1][1],
        foreign_rot_3x3[1][2],
        foreign_rot_3x3[2][0],
        foreign_rot_3x3[2][1],
        foreign_rot_3x3[2][2],
    )

    # Fill in the geometric cylinder data.
    _cylinder_shape.geo_cylinder.height = depth
    _cylinder_shape.geo_cylinder.radius = radius
    # For the cylinder's center, we use the recovered foreign position.
    _cylinder_shape.geo_cylinder.center.x = foreign_position.x
    _cylinder_shape.geo_cylinder.center.y = foreign_position.y
    _cylinder_shape.geo_cylinder.center.z = foreign_position.z

    return _cylinder_shape


def create_collision_shape(meshes_collection: bpy.types.Collection) -> CollisionShape:
    """Create a Collision Shape from a Collection of Collision Shapes."""
    _collision_shape = CollisionShape()
    collision_collection = get_collection(
        meshes_collection, "CollisionShapes_Collection"
    )
    for child in collision_collection.children:
        if child.name.startswith("Boxes_Collection"):
            if len(child.objects) > 0:
                for box in child.objects:
                    if box.type == "MESH":
                        _collision_shape.box_count += 1
                        _collision_shape.boxes.append(create_box_shape(box))
        if child.name.startswith("Spheres_Collection"):
            if len(child.objects) > 0:
                for sphere in child.objects:
                    if sphere.type == "MESH":
                        _collision_shape.sphere_count += 1
                        _collision_shape.spheres.append(create_sphere_shape(sphere))
        if child.name.startswith("Cylinders_Collection"):
            if len(child.objects) > 0:
                for cylinder in child.objects:
                    if cylinder.type == "MESH":
                        _collision_shape.cylinder_count += 1
                        _collision_shape.cylinders.append(
                            create_cylinder_shape(cylinder)
                        )
    return _collision_shape


def create_skin_info(
    unified_mesh: bpy.types.Mesh,
    meshes_collection: bpy.types.Collection,
    bone_map: Dict[str, Dict[str, int]],
) -> CSkSkinInfo:
    """Create CSkSkinInfo by matching world-space vertices to the unified mesh."""
    TOL_DIGITS = 6  # ~1e-6 (your original rounding)
    KD_TOL = 1e-5  # tolerant fallback for welded/shifted verts

    skin_info = CSkSkinInfo()
    skin_info.vertex_count = len(unified_mesh.vertices)

    # Build coordinate -> index hashtable (fast path). The unified mesh is already in WORLD space.
    unified_hashtable: dict[tuple[float, float, float], int] = {}
    for v in unified_mesh.vertices:
        key = (
            round(v.co.x, TOL_DIGITS),
            round(v.co.y, TOL_DIGITS),
            round(v.co.z, TOL_DIGITS),
        )
        if key in unified_hashtable:
            logger.log(
                f"Duplicate vertex found in unified mesh: {v.co}", "Error", "ERROR"
            )
            skin_info.vertex_data = [
                VertexData(bone_indices=[0, 0, 0, 0], weights=[0.0, 0.0, 0.0, 0.0])
            ] * skin_info.vertex_count
            return skin_info
        unified_hashtable[key] = v.index

    # Build KDTree as a robust fallback (handles tiny weld shifts from remove_doubles)
    kd = KDTree(len(unified_mesh.vertices))
    for v in unified_mesh.vertices:
        kd.insert(v.co, v.index)
    kd.balance()

    vertex_data: list[VertexData | None] = [None] * skin_info.vertex_count
    misses = 0

    for obj in meshes_collection.objects:
        if obj.type != "MESH":
            continue
        mw = obj.matrix_world.copy()
        vgroups = obj.vertex_groups

        for v in obj.data.vertices:
            wco = mw @ v.co
            key = (
                round(wco.x, TOL_DIGITS),
                round(wco.y, TOL_DIGITS),
                round(wco.z, TOL_DIGITS),
            )

            idx = unified_hashtable.get(key)
            if idx is None:
                # KD fallback
                _pos, kd_idx, dist = kd.find(wco)
                if kd_idx is None or dist > KD_TOL:
                    if misses < 20:  # avoid spam
                        logger.log(
                            f"Vertex {v.index} not found in unified mesh (ws: {wco})",
                            "Warning",
                            "WARNING",
                        )
                    misses += 1
                    continue
                idx = kd_idx

            if vertex_data[idx] is None:
                vertex_data[idx] = VertexData(bone_indices=[], weights=[])

            for g in v.groups:
                if g.weight <= 0.0:
                    continue
                bone_name = vgroups[g.group].name
                bone_info = bone_map.get(bone_name, -1)
                if bone_info == -1:
                    logger.log(
                        f"Bone {bone_name} not in bone map for vertex {v.index}",
                        "Error",
                        "ERROR",
                    )
                    continue
                bone_id = bone_info["id"]
                if bone_id not in vertex_data[idx].bone_indices:
                    vertex_data[idx].bone_indices.append(bone_id)
                    vertex_data[idx].weights.append(g.weight)

    if misses > 20:
        logger.log(
            f"{misses} vertices could not be matched to the unified mesh (after KD fallback).",
            "Warning",
            "WARNING",
        )

    # Normalize to 4 influences per vertex (pad/truncate) — unchanged
    for i, vd in enumerate(vertex_data):
        if vd is None:
            vertex_data[i] = VertexData(
                bone_indices=[0, 0, 0, 0], weights=[0.0, 0.0, 0.0, 0.0]
            )
            continue
        if len(vd.weights) > 4:
            order = sorted(
                range(len(vd.weights)), key=lambda k: vd.weights[k], reverse=True
            )[:4]
            vd.bone_indices = [vd.bone_indices[k] for k in order]
            vd.weights = [vd.weights[k] for k in order]
        while len(vd.bone_indices) < 4:
            vd.bone_indices.append(0)
            vd.weights.append(0.0)

    skin_info.vertex_data = vertex_data  # type: ignore[assignment]
    return skin_info


def create_skeleton(
    armature_object: bpy.types.Object,
    bone_map: Dict[str, Dict[str, Optional[int]]],
) -> CSkSkeleton:
    csk_skeleton = CSkSkeleton()
    csk_skeleton.bone_count = 0
    csk_skeleton.bone_matrix_count = 0
    csk_skeleton.bones = []
    csk_skeleton.bone_matrices = []

    # bones are ordered by their version number, starting with the lowest version number
    unordered_bones = []
    for bone in armature_object.data.bones:
        # Get the Version from the version List
        version = bones_list.get(bone.name, -1)
        if version == -1:
            # Create a new version number for the bone
            version = generate_bone_id(bone.name)
        # Insert the bone into the list, sorted by version number
        unordered_bones.append((bone.name, version))
    # Sort the bones by version number
    unordered_bones.sort(key=lambda x: x[1])

    # Loop the sorted bones and fill the bones array
    for bone_name, version in unordered_bones:
        drs_bone = Bone()
        armature_bone: bpy.types.Bone = armature_object.data.bones[bone_name]
        drs_bone.name = bone_name
        drs_bone.name_length = len(bone_name)
        drs_bone.version = version
        drs_bone.identifier = bone_map[bone_name]["id"]
        drs_bone.child_count = len(armature_bone.children)
        # Child IDs taken from bone_map
        drs_bone.children = [
            bone_map[child.name]["id"] for child in armature_bone.children
        ]
        csk_skeleton.bones.append(drs_bone)
        csk_skeleton.bone_count += 1

    for bone_name, _ in bone_map.items():
        # Get the Bone from the armature object
        armature_bone: bpy.types.Bone = armature_object.data.bones[bone_name]
        if armature_bone is None:
            logger.log(
                f"Bone {bone_name} not found in armature object. Skipping it.",
                "Error",
                "ERROR",
            )
            continue
        # Get the matrix from the armature object
        rest_mat = armature_bone.matrix_local.copy()
        rot = rest_mat.to_3x3()
        loc = rest_mat.to_translation()
        vec_3 = -(rot.inverted() @ loc)
        vec_0 = rot[0].copy()
        vec_1 = rot[1].copy()
        vec_2 = rot[2].copy()

        bone_vertex_0 = BoneVertex()
        bone_vertex_0.position = Vector3(vec_0.x, vec_0.y, vec_0.z)
        # Check for the parent bone, if it exists
        if armature_bone.parent is not None:
            parent_bone_name = armature_bone.parent.name
            parent_bone_id = bone_map.get(parent_bone_name, {}).get("id", -1)
            if parent_bone_id == -1:
                logger.log(
                    f"Parent Bone {parent_bone_name} not found in bone map for vertex {bone_name}. Skipping unused bone.",
                    "Warning",
                    "WARNING",
                )
                parent_bone_id = -1
            bone_vertex_0.parent = parent_bone_id
        else:
            bone_vertex_0.parent = -1  # Root bone has no parent

        bone_vertex_1 = BoneVertex()
        bone_vertex_1.position = Vector3(vec_1.x, vec_1.y, vec_1.z)
        # Here we need the index of the bone in our csk_skeleton.bones Array
        bone_name = armature_bone.name
        bone_index = next(
            (i for i, b in enumerate(csk_skeleton.bones) if b.name == bone_name),
            None,
        )
        if bone_index is None:
            logger.log(
                f"Bone {bone_name} not found in csk_skeleton.bones. Skipping it.",
                "Error",
                "ERROR",
            )
            continue
        # We need to get the bone index from the csk_skeleton.bones array
        bone_vertex_1.parent = bone_index

        bone_vertex_2 = BoneVertex()
        bone_vertex_2.position = Vector3(vec_2.x, vec_2.y, vec_2.z)
        bone_vertex_2.parent = 0  # Maybe always 0?

        bone_vertex_3 = BoneVertex()
        bone_vertex_3.position = Vector3(vec_3.x, vec_3.y, vec_3.z)
        bone_vertex_3.parent = 0  # Maybe always 0?

        bone_matrix = BoneMatrix()
        bone_matrix.bone_vertices = [
            bone_vertex_0,
            bone_vertex_1,
            bone_vertex_2,
            bone_vertex_3,
        ]

        csk_skeleton.bone_matrices.append(bone_matrix)
        csk_skeleton.bone_matrix_count += 1

    return csk_skeleton


def create_animation_set(model_name: str) -> AnimationSet:
    """
    Build an AnimationSet for export from the AnimationSetJSON blob.
    Anything not present in the blob falls back to defaults.
    """

    def _active_top_drsmodel() -> bpy.types.Collection | None:
        alc = (
            bpy.context.view_layer.active_layer_collection.collection
            if bpy.context and bpy.context.view_layer
            else None
        )
        if not isinstance(alc, bpy.types.Collection):
            return None
        if not alc.name.startswith("DRSModel_"):
            return None
        for top in bpy.context.scene.collection.children:
            if top == alc:
                return alc
        return None

    def _read_blob(col: bpy.types.Collection) -> dict:
        data = col.get(ANIM_BLOB_KEY)
        if not data:
            return {}
        try:
            b = json.loads(data)
            if not isinstance(b, dict):
                return {}
            # ensure lists exist
            b.setdefault("mode_keys", [])
            b.setdefault("marker_sets", [])
            return b
        except Exception:  # noqa: BLE001
            return {}

    # -- defaults compatible with existing exporter ------------------------------------------------
    anim = AnimationSet()
    anim.version = 6
    anim.revision = 6
    anim.subversion = 2
    anim.has_atlas = 1
    anim.atlas_count = 0
    anim.ik_atlases = []
    anim.mode_animation_keys = []
    anim.mode_animation_key_count = 0

    # sensible defaults (these are the same values you previously emitted)
    anim.default_run_speed = 4.8
    anim.default_walk_speed = 2.3
    anim.mode_change_type = 0
    anim.hovering_ground = 0
    anim.fly_bank_scale = 1.0
    anim.fly_accel_scale = 0.0
    anim.fly_hit_scale = 1.0
    anim.allign_to_terrain = 0

    # ---- try to read blob from the active model --------------------------------------------------
    col = _active_top_drsmodel()
    blob = _read_blob(col) if col else {}

    # top-level scalars
    def _bget(name, default):  # small helper with type coercion
        val = blob.get(name, default)
        return val if val is not None else default

    anim.default_run_speed = float(_bget("default_run_speed", anim.default_run_speed))
    anim.default_walk_speed = float(
        _bget("default_walk_speed", anim.default_walk_speed)
    )
    anim.mode_change_type = int(_bget("mode_change_type", anim.mode_change_type))
    anim.hovering_ground = int(_bget("hovering_ground", anim.hovering_ground))
    anim.fly_bank_scale = float(_bget("fly_bank_scale", anim.fly_bank_scale))
    anim.fly_accel_scale = float(_bget("fly_accel_scale", anim.fly_accel_scale))
    anim.fly_hit_scale = float(_bget("fly_hit_scale", anim.fly_hit_scale))
    anim.allign_to_terrain = int(_bget("align_to_terrain", anim.allign_to_terrain))

    # ---- Mode Keys ------------------------------------------------------------------------------
    mode_keys = blob.get("mode_keys", []) or []
    for mkd in mode_keys:
        try:
            mk = ModeAnimationKey()
            # keep legacy header values that the writer expects
            mk.type = 6
            mk.length = 11
            mk.file = "Battleforge"
            mk.unknown = 2
            mk.unknown2 = 3
            mk.unknown3 = 3

            mk.vis_job = int(mkd.get("vis_job", 0) or 0)
            mk.special_mode = int(mkd.get("special_mode", 0) or 0)

            mk.animation_set_variants = []
            mk.variant_count = 0

            for vd in mkd.get("variants", []) or []:
                # skip empty variants
                f = (vd.get("file") or "").strip()
                if not f or f == "NONE":
                    continue
                if not f.endswith(".ska"):
                    f += ".ska"

                var = AnimationSetVariant()
                var.version = 7
                var.weight = int(vd.get("weight", 100) or 0)
                var.start = float(vd.get("start", 0.0) or 0.0)
                var.end = float(vd.get("end", 1.0) or 1.0)
                var.length = len(f)
                var.allows_ik = int(vd.get("allows_ik", 1))
                var.force_no_blend = bool(int(vd.get("force_no_blend", 0)))
                var.file = f

                mk.animation_set_variants.append(var)

            mk.variant_count = len(mk.animation_set_variants)
            # only append keys that have at least one valid variant
            if mk.variant_count > 0:
                anim.mode_animation_keys.append(mk)
        except Exception:  # noqa: BLE001
            # ignore individual bad keys; continue with the rest
            continue

    anim.mode_animation_key_count = len(anim.mode_animation_keys)

    # ---- Marker sets -----------------------------------------------------------------
    def _to_uint32(v) -> int:
        """Return a non-negative uint32 from int/str/hex/anything."""
        try:
            if isinstance(v, int):
                return v & 0xFFFFFFFF
            s = str(v).strip()
            # decimal?
            try:
                return int(s) & 0xFFFFFFFF
            except Exception:
                pass
            # hex (allow 0x prefix or plain hex)
            try:
                return int(s, 16) & 0xFFFFFFFF
            except Exception:
                pass
            # fallback: stable hash → first 4 bytes (little endian)
            h = hashlib.sha1(s.encode("utf-8")).digest()[:4]
            return int.from_bytes(h, "little", signed=False)
        except Exception:
            return 0

    anim.animation_marker_sets = []
    anim.animation_marker_count = 0

    marker_sets_blob = blob.get("marker_sets") or []
    for msd in marker_sets_blob:
        try:
            name = (msd.get("file") or "").strip()
            if not name:
                # nothing usable
                continue

            ms = AnimationMarkerSet()
            ms.anim_id = int(msd.get("anim_id", 0) or 0)
            ms.name = name
            ms.length = len(ms.name)

            raw_id = msd.get("animation_marker_id", 0)
            ms.animation_marker_id = _to_uint32(raw_id)

            # we keep exactly one marker per set; use first if multiple
            md = (msd.get("markers") or [{}])[0] or {}
            am = AnimationMarker()
            am.is_spawn_animation = int(md.get("is_spawn_animation", 0) or 0)
            am.time = float(md.get("time", 0.0) or 0.0)

            # accept both "direction/position" and legacy "dir/pos" keys
            dir3 = md.get("direction")
            if dir3 is None:
                dir3 = md.get("dir", [0.0, 0.0, 1.0])
            pos3 = md.get("position")
            if pos3 is None:
                pos3 = md.get("pos", [0.0, 0.0, 0.0])

            am.direction = Vector3(
                x=float(dir3[0] if len(dir3) > 0 else 0.0),
                y=float(dir3[1] if len(dir3) > 1 else 0.0),
                z=float(dir3[2] if len(dir3) > 2 else 0.0),
            )
            am.position = Vector3(
                x=float(pos3[0] if len(pos3) > 0 else 0.0),
                y=float(pos3[1] if len(pos3) > 1 else 0.0),
                z=float(pos3[2] if len(pos3) > 2 else 0.0),
            )

            ms.animation_markers = [am]
            ms.marker_count = 1

            anim.animation_marker_sets.append(ms)
        except Exception:
            # be conservative; skip broken entries
            continue

    anim.animation_marker_count = len(anim.animation_marker_sets)

    # ---- Fallback if no blob or no valid variants -----------------------------------------------
    if anim.mode_animation_key_count == 0:
        # previous behavior: pick actions by name and synthesize a single key
        all_actions = get_actions()
        available_action: list[str] = []
        if len(all_actions) == 1:
            available_action.append(all_actions[0])
        elif len(all_actions) > 1:
            for a in all_actions:
                base = a.replace(".ska", "")
                if base == model_name or "_idle" in base:
                    available_action.append(a)

        if available_action:
            mk = ModeAnimationKey()
            mk.type = 6
            mk.length = 11
            mk.file = "Battleforge"
            mk.unknown = 2
            mk.unknown2 = 3
            mk.vis_job = 0
            mk.unknown3 = 3
            mk.unknown4 = 0
            mk.animation_set_variants = []
            for a in available_action:
                f = a if a.endswith(".ska") else (a + ".ska")
                var = AnimationSetVariant()
                var.version = 4
                var.weight = 100 // max(1, len(available_action))
                var.start = 0.0
                var.end = 1.0
                var.length = len(f)
                var.file = f
                var.allows_ik = 1
                mk.animation_set_variants.append(var)
            mk.variant_count = len(mk.animation_set_variants)
            anim.mode_animation_keys = [mk]
            anim.mode_animation_key_count = 1
        else:
            logger.log(
                "No AnimationSet blob found (or it had no valid variants), and no suitable Actions in the scene.",
                "Error",
                "ERROR",
            )

    return anim


def create_animation_timings() -> Optional[AnimationTimings]:
    """
    Build AnimationTimings for export from the AnimationSetJSON blob.
    Returns None if no timings are present so the caller can skip writing.
    """

    # -- locate the active top-level DRSModel_* collection ------------
    def _active_top_drsmodel() -> bpy.types.Collection | None:
        alc = (
            bpy.context.view_layer.active_layer_collection.collection
            if bpy.context and bpy.context.view_layer
            else None
        )
        if not isinstance(alc, bpy.types.Collection):
            return None
        if not alc.name.startswith("DRSModel_"):
            return None
        for top in bpy.context.scene.collection.children:
            if top == alc:
                return alc
        return None

    # -- read the JSON blob from the collection -----------------------
    def _read_blob(col: bpy.types.Collection) -> dict:
        data = col.get(ANIM_BLOB_KEY)
        if not data:
            return {}
        try:
            b = json.loads(data)
            # timings lives alongside mode_keys/marker_sets in this blob
            b.setdefault("timings", [])
            return b
        except Exception:
            return {}

    col = _active_top_drsmodel()
    if not col:
        return None

    blob = _read_blob(col)
    timings_list = blob.get("timings") or []
    if not timings_list:
        return None

    # Use the existing helper to map blob -> AnimationTimings
    return blob_to_animationtimings({"timings": timings_list})


def create_bone_map(
    armature_object: bpy.types.Object,
) -> Dict[str, Dict[str, Optional[int]]]:
    """Create a bone map from the armature object."""
    # We need to start at the root bone and go down the hierarchy
    bone_map = {}
    root_bones = [bone for bone in armature_object.data.bones if not bone.parent]
    if not root_bones:
        logger.log("No root bone found in the armature.", "Error", "ERROR")
        return bone_map
    if len(root_bones) > 1:
        logger.log(
            "Multiple root bones found in the armature. Only the first one will be used.",
            "Warning",
            "WARNING",
        )

    root_bone = root_bones[0]
    index = 0

    def traverse_bone(bone: bpy.types.Bone, parent_id: Optional[int]):
        nonlocal index
        current_id = index
        # Save the current bone with its id and its parent's id (None for the root)
        bone_map[bone.name] = {"id": current_id, "parent": parent_id}
        index += 1
        # Traverse children, passing the current bone's id as the parent id
        for child in bone.children:
            traverse_bone(child, current_id)

    traverse_bone(root_bone, -1)
    return bone_map


def update_mesh_file_root_reference(
    cdsp_mesh_file: CDspMeshFile, mesh_bone_data: List[Dict[str, int]]
) -> CDspMeshFile:
    """Update the mesh file root reference."""
    for i, mesh in enumerate(cdsp_mesh_file.meshes):
        # Get the bone data for this mesh
        per_mesh_bone_data = mesh_bone_data[i]
        # Check if the bone data is valid
        if not per_mesh_bone_data:
            continue
        # Get the SkinningMeshData
        skinning_mesh_data = mesh.mesh_data[2]
        for vertex in skinning_mesh_data.vertices:
            # Check the 2nd, 3rd and 4th bone index for -1
            if not vertex.bone_indices:
                continue
            if vertex.bone_indices[1] == -1:
                vertex.bone_indices[1] = per_mesh_bone_data["root_ref"]
            if vertex.bone_indices[2] == -1:
                vertex.bone_indices[2] = per_mesh_bone_data["root_ref"]
            if vertex.bone_indices[3] == -1:
                vertex.bone_indices[3] = per_mesh_bone_data["root_ref"]
    return cdsp_mesh_file


def save_drs(
    context: bpy.types.Context,
    filepath: str,
    split_mesh_by_uv_islands: bool,
    flip_normals: bool,
    keep_debug_collections: bool,
    model_type: str,
    model_name: str,
):
    """Save the DRS file."""
    global texture_cache_col, texture_cache_nor, texture_cache_par, texture_cache_ref  # pylint: disable=global-statement
    # === PRE-VALIDITY CHECKS =================================================
    # Ensure active collection is valid
    source_collection = bpy.context.view_layer.active_layer_collection.collection
    if not verify_collections(source_collection, model_type):
        return abort(keep_debug_collections, None)

    # Create a safe copy of the collection for export
    try:
        source_collection_copy = copy(context.scene.collection, source_collection)
        source_collection_copy.name += ".copy"
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Failed to duplicate collection: {e}. Type {type(e)}", "ERROR")
        return abort(keep_debug_collections, None)

    # === MESH PREPARATION =====================================================
    meshes_collection = get_collection(source_collection_copy, "Meshes_Collection")
    try:
        triangulate(source_collection_copy)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error during triangulation: {e}", "Triangulation Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    if not verify_mesh_vertex_count(meshes_collection):
        logger.log(
            "Model verification failed: one or more meshes are invalid or exceed vertex limits.",
            "Model Verification Error",
            "ERROR",
        )
        return abort(keep_debug_collections, source_collection_copy)

    if split_mesh_by_uv_islands:
        try:
            split_meshes_by_uv_islands(meshes_collection)
        except Exception as e:  # pylint: disable=broad-except
            logger.log(
                f"Error splitting meshes by UV islands: {e}", "UV Island Error", "ERROR"
            )
            return abort(keep_debug_collections, source_collection_copy)

    # Check if there is an Armature in the Collection
    armature_object = None
    add_skin_mesh = False
    bone_map: Dict[str, Dict[str, Optional[int]]] = {}
    # get the Armature_Collection
    armature_collection = None
    for child in source_collection_copy.children:
        if "Armature_Collection" in child.name:
            armature_collection = child
            break
    if armature_collection is None and model_type in [
        "AnimatedObjectNoCollision",
        "AnimatedObjectCollision",
    ]:
        logger.log(
            "No Armature_Collection found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature_Collection to the Collection.",
            "Error",
            "ERROR",
        )
        return abort(keep_debug_collections, source_collection_copy)
    # Get the armature object from the Armature_Collection, but avoid the "*Control_Rig" armature
    if model_type in ["AnimatedObjectNoCollision", "AnimatedObjectCollision"]:
        try:
            for obj in armature_collection.objects:
                if obj.type == "ARMATURE" and "Control_Rig" not in obj.name:
                    armature_object = obj
                    add_skin_mesh = True
                    # Limit the Weights to max. 4 bones per vertex
                    bpy.ops.object.vertex_group_limit_total(limit=4)
                    # Create a bone map from the armature
                    bone_map = create_bone_map(armature_object)
                    break
            if armature_object is None:
                logger.log(
                    "No Armature found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature to the Collection.",
                    "Error",
                    "ERROR",
                )
                return abort(keep_debug_collections, source_collection_copy)
        except Exception as e:  # pylint: disable=broad-except
            logger.log(f"Error processing armature: {e}", "Armature Error", "ERROR")
            return abort(keep_debug_collections, source_collection_copy)

    try:
        set_origin_to_world_origin(meshes_collection)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error setting origin for meshes: {e}", "Origin Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    # === CREATE DRS STRUCTURE =================================================
    folder_path = os.path.dirname(filepath)

    new_drs_file: DRS = DRS(model_type=model_type)
    try:
        unified_mesh = create_unified_mesh(meshes_collection)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error creating unified mesh: {e}", "Unified Mesh Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    # Generate the CDspMeshFile
    try:
        cdsp_mesh_file, mesh_bone_data = create_cdsp_mesh_file(
            meshes_collection,
            model_name,
            folder_path,
            flip_normals,
            add_skin_mesh,
        )
        if cdsp_mesh_file is None:
            logger.log("Failed to create CDspMeshFile.", "Mesh File Error", "ERROR")
            return abort(keep_debug_collections, source_collection_copy)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error creating CDspMeshFile: {e}", "Mesh File Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    nodes = InformationIndices[model_type]
    for node in nodes:
        if node == "CGeoMesh":
            new_drs_file.cgeo_mesh = create_cgeo_mesh(unified_mesh)
            new_drs_file.push_node_infos("CGeoMesh", new_drs_file.cgeo_mesh)
        elif node == "CGeoOBBTree":
            new_drs_file.cgeo_obb_tree = create_cgeo_obb_tree(unified_mesh)
            new_drs_file.push_node_infos("CGeoOBBTree", new_drs_file.cgeo_obb_tree)
        elif node == "CDspJointMap":
            new_drs_file.cdsp_joint_map = create_cdsp_joint_map(
                add_skin_mesh, mesh_bone_data, bone_map
            )
            new_drs_file.push_node_infos("CDspJointMap", new_drs_file.cdsp_joint_map)
            # Update CDspMeshFile with the RootReference in subMeshes
            if add_skin_mesh:
                cdsp_mesh_file = update_mesh_file_root_reference(
                    cdsp_mesh_file, mesh_bone_data
                )
        elif node == "CDspMeshFile":
            new_drs_file.cdsp_mesh_file = cdsp_mesh_file
            new_drs_file.push_node_infos("CDspMeshFile", new_drs_file.cdsp_mesh_file)
        elif node == "DrwResourceMeta":
            new_drs_file.drw_resource_meta = DrwResourceMeta()
            new_drs_file.push_node_infos(
                "DrwResourceMeta", new_drs_file.drw_resource_meta
            )
        elif node == "collisionShape":
            new_drs_file.collision_shape = create_collision_shape(
                source_collection_copy
            )
            new_drs_file.push_node_infos("collisionShape", new_drs_file.collision_shape)
        elif node == "CSkSkinInfo":
            new_drs_file.csk_skin_info = create_skin_info(
                unified_mesh, meshes_collection, bone_map
            )
            if new_drs_file.csk_skin_info is None:
                logger.log("Failed to create CSkSkinInfo.", "Skin Info Error", "ERROR")
                return abort(keep_debug_collections, source_collection_copy)
            new_drs_file.push_node_infos("CSkSkinInfo", new_drs_file.csk_skin_info)
        elif node == "CSkSkeleton":
            new_drs_file.csk_skeleton = create_skeleton(armature_object, bone_map)
            if new_drs_file.csk_skeleton is None:
                logger.log("Failed to create CSkSkeleton.", "Skeleton Error", "ERROR")
                return abort(keep_debug_collections, source_collection_copy)
            new_drs_file.push_node_infos("CSkSkeleton", new_drs_file.csk_skeleton)
        elif node == "AnimationSet":
            # Empty Set and use external EntityEditor
            new_drs_file.animation_set = create_animation_set(model_name)
            if new_drs_file.animation_set is None:
                logger.log(
                    "Failed to create AnimationSet.", "Animation Set Error", "ERROR"
                )
                return abort(keep_debug_collections, source_collection_copy)
            new_drs_file.push_node_infos("AnimationSet", new_drs_file.animation_set)
        elif node == "AnimationTimings":
            # Empty Set and use external EntityEditor
            new_drs_file.animation_timings = create_animation_timings()
            if new_drs_file.animation_timings is None:
                logger.log(
                    "Failed to create AnimationTimings.",
                    "Animation Timings Error",
                    "ERROR",
                )
                return abort(keep_debug_collections, source_collection_copy)
            new_drs_file.push_node_infos(
                "AnimationTimings", new_drs_file.animation_timings
            )
        elif node == "CGeoPrimitiveContainer":
            pass  # Nothing happens here
        else:
            logger.log(
                f"Node {node} is not a valid DRS node!",
                "Error",
                "ERROR",
            )
            return abort(keep_debug_collections, source_collection_copy)

    new_drs_file.update_offsets()

    # === SAVE THE DRS FILE ====================================================
    try:
        new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error saving DRS file: {e}", "Save Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)
    # new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))

    # === CLEANUP & FINALIZE ===================================================
    if not keep_debug_collections:
        bpy.data.collections.remove(source_collection_copy)

    logger.log("Export completed successfully.", "Export Complete", "INFO")
    logger.display()
    # Cleanup
    texture_cache_col = {}
    texture_cache_nor = {}
    texture_cache_par = {}
    texture_cache_ref = {}
    new_drs_file = None
    unified_mesh = None
    meshes_collection = None
    armature_object = None
    source_collection_copy = None

    return {"FINISHED"}


# endregion
