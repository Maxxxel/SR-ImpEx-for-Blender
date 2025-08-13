# transform_utils.py
from math import radians
from contextlib import contextmanager
from mathutils import Matrix
import bpy


@contextmanager
def ensure_mode(desired_mode: str):
    """Context manager to switch Blender's mode and restore the original mode."""
    current_mode = bpy.context.object.mode if bpy.context.object else "OBJECT"
    if current_mode != desired_mode:
        bpy.ops.object.mode_set(mode=desired_mode)
    try:
        yield
    finally:
        if bpy.context.object and bpy.context.object.mode != current_mode:
            bpy.ops.object.mode_set(mode=current_mode)


def get_conversion_matrix(invert: bool = False) -> Matrix:
    """
    Build the composite transformation matrix:
      - Mirror along Y-axis,
      - Rotate -90° about X,
      - Rotate 90° about Z.
    Returns its inverse if `invert` is True.
    """
    mirror_y = Matrix.Scale(-1, 4, (0, 1, 0))
    rot_x = Matrix.Rotation(radians(-90), 4, "X")
    rot_z = Matrix.Rotation(radians(90), 4, "Z")
    transform = rot_z @ rot_x @ mirror_y
    return transform.inverted() if invert else transform


def create_empty(source_collection: bpy.types.Collection) -> bpy.types.Object:
    """
    Create an empty object in the scene with the specified name and location.
    Optionally set its rotation.
    """
    M = get_conversion_matrix(invert=False)
    empty = bpy.data.objects.new("GameOrientation", None)
    source_collection.objects.link(empty)
    empty.matrix_world = M
    return empty


def parent_under_game_axes(source_collection: bpy.types.Collection):
    empty = create_empty(source_collection)

    for obj in source_collection.all_objects:
        if obj.type in {"MESH", "ARMATURE"}:
            if obj.parent is not None:
                # DEBUG PRINT
                print(f"Object {obj.name} has a parent {obj.parent.name}, skipping.")
                continue  # Skip objects that already have a parent
            obj.matrix_parent_inverse = empty.matrix_world.inverted()
            obj.parent = empty
