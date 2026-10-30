"""Keep engine joint identities separate from Blender's limited display names."""
from .bone_ids import resolve_bone_ids

SOURCE_NAME = "_sr_source_bone_name"
SOURCE_KEY = "_sr_source_bone_key"
SOURCE_INDEX = "_sr_source_joint_index"
SOURCE_CHILDREN = "_sr_source_child_indices"
DISPLAY_NAME = "_sr_imported_bone_name"
EXTRA_WORDS = "_sr_joint_extra_words"
INV_REF_XYZ = "_sr_inverse_reference_xyz"
IMPORTED_REST = "_sr_imported_rest_matrix"
SUPER_PARENT = "_sr_skeleton_super_parent"
RESOURCE_META = "_sr_resource_meta"


def display_bone_name(name, key):
    """Retain familiar UI aliases without changing the serialized engine name."""
    alias = name
    for prefix in ("building_bandits_air_defense_launcher_", "building_frost_fortress_",
                   "building_twilight_XL_spawn_shell_"):
        alias = alias.replace(prefix, "")
    if alias.startswith("building_nature_versatile_tower_"):
        alias = alias.removeprefix("building_nature_versatile_tower_")
        if "|" in alias:
            contains_jnt1 = "_jnt1" in alias
            alias = alias.split("|")[-1]
            if contains_jnt1:
                alias = alias.replace("_jnt", "_end")
    raw = alias.encode("utf8", errors="replace")
    if len(raw) > 63 or "\0" in alias or not alias:
        alias = raw[:48].decode("utf8", errors="ignore").replace("\0", "_") + f"_{key:08x}"
    return alias


def export_bone_identities(bones, known_ids):
    """Preserve unrenamed imported names/keys; renamed and new bones use the CRC resolver."""
    records = []
    preserved = dict(known_ids)
    for bone in bones:
        name = bone.name
        source_name = name
        if bone.get(DISPLAY_NAME) == name and SOURCE_NAME in bone and SOURCE_KEY in bone:
            source_name = bone[SOURCE_NAME]
            preserved[source_name] = int(bone[SOURCE_KEY], 16)
        records.append((name, source_name))
    source_names = [source for _, source in records]
    if len(set(source_names)) != len(source_names):
        raise ValueError("Skeleton bones resolve to duplicate serialized names")
    keys = resolve_bone_ids(source_names, preserved)
    return {name: {"name": source, "key": keys[source]} for name, source in records}


def super_parent_matrix(armature_data):
    """Convert the engine's row-vector matrix into Blender column-vector form."""
    from mathutils import Matrix
    values = armature_data.get(SUPER_PARENT)
    if values is None:
        return Matrix.Identity(4)
    if len(values) != 16:
        raise ValueError("Stored skeleton super-parent requires 16 components")
    return Matrix(tuple(tuple(values[i:i + 4]) for i in range(0, 16, 4))).transposed()
