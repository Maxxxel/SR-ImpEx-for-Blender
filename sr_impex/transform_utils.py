# transform_utils.py
from math import radians
from contextlib import contextmanager
from mathutils import Matrix, Vector
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


def mirror_object_by_vector(obj, vector: Vector) -> None:
    """
    Mirrors an object's world matrix across a normalized vector.
    """
    vector = vector.normalized()
    reflection_matrix = Matrix(
        (
            (
                1 - 2 * vector.x**2,
                -2 * vector.x * vector.y,
                -2 * vector.x * vector.z,
                0,
            ),
            (
                -2 * vector.x * vector.y,
                1 - 2 * vector.y**2,
                -2 * vector.y * vector.z,
                0,
            ),
            (
                -2 * vector.x * vector.z,
                -2 * vector.y * vector.z,
                1 - 2 * vector.z**2,
                0,
            ),
            (0, 0, 0, 1),
        )
    )
    obj.matrix_world = reflection_matrix @ obj.matrix_world


def apply_transformation_to_objects(
    objects, transform: Matrix, apply_operator: bool = False
) -> None:
    """
    Applies a transformation matrix to a list of objects.
    Optionally applies Blender's transform operator.
    """
    for obj in objects:
        obj.matrix_world = transform @ obj.matrix_world
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if apply_operator:
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def get_collection(
    source_collection: bpy.types.Collection, name: str
) -> bpy.types.Collection:
    """Return the sub-collection whose name matches the provided name."""
    for collection in source_collection.children:
        if collection.name.startswith(name):
            return collection
    return None


def apply_transformation(
    source_collection,
    armature_object=None,
    apply_transform=True,
    invert=False,
    operator_on_meshes=False,
    operator_on_collision=False,
    operator_on_ground_decal=False,
    operator_on_slocators=False,
) -> None:
    """
    Applies a composite transformation to objects in the source collection or to a provided armature.
    If `invert` is True, the inverse of the transformation is used.
    """
    if not apply_transform:
        return

    transform = get_conversion_matrix(invert)
    meshes_collection = get_collection(source_collection, "Meshes_Collection")

    if armature_object is not None:
        armature_object.matrix_world = transform @ armature_object.matrix_world
        bpy.context.view_layer.objects.active = armature_object
        armature_object.select_set(True)
        # Loop the child collections
        for child in meshes_collection.children:
            # Check if there is a CollsionShapes_Collection inside the child
            collision_collection = get_collection(child, "CollisionShapes_Collection")
            if collision_collection:
                if (
                    len(collision_collection.objects) == 0
                    and len(collision_collection.children) > 0
                ):
                    for grandchild in collision_collection.children:
                        apply_transformation_to_objects(
                            grandchild.objects, transform, operator_on_collision
                        )
    else:
        if meshes_collection:
            if (
                len(meshes_collection.objects) == 0
                and len(meshes_collection.children) > 0
            ):
                for child in meshes_collection.children:
                    apply_transformation_to_objects(
                        child.objects, transform, operator_on_meshes
                    )
            else:
                apply_transformation_to_objects(
                    meshes_collection.objects, transform, operator_on_meshes
                )
            # Loop the child collections
            for child in meshes_collection.children:
                # Check if there is a CollsionShapes_Collection inside the child
                collision_collection = get_collection(
                    child, "CollisionShapes_Collection"
                )
                if collision_collection:
                    if (
                        len(collision_collection.objects) == 0
                        and len(collision_collection.children) > 0
                    ):
                        for grandchild in collision_collection.children:
                            apply_transformation_to_objects(
                                grandchild.objects, transform, operator_on_collision
                            )

    collision_collection = get_collection(
        source_collection, "CollisionShapes_Collection"
    )
    if collision_collection:
        if (
            len(collision_collection.objects) == 0
            and len(collision_collection.children) > 0
        ):
            for child in collision_collection.children:
                apply_transformation_to_objects(
                    child.objects, transform, operator_on_collision
                )
        else:
            apply_transformation_to_objects(
                collision_collection.objects, transform, operator_on_collision
            )

    ground_decal_collection = get_collection(
        source_collection, "GroundDecal_Collection"
    )
    if ground_decal_collection:
        apply_transformation_to_objects(
            ground_decal_collection.objects, transform, operator_on_ground_decal
        )

    destruction_states_collection = get_collection(
        source_collection, "Destruction_State_Collection"
    )
    if destruction_states_collection:
        for child in destruction_states_collection.children:
            apply_transformation_to_objects(
                child.objects, transform, apply_operator=True
            )

    obb_collection = get_collection(source_collection, "OBB_Collection")
    if obb_collection:
        for child in obb_collection.children:
            apply_transformation_to_objects(
                child.objects, transform, apply_operator=True
            )

    slocator_collection = get_collection(source_collection, "SLocators_Collection")
    if slocator_collection:
        apply_transformation_to_objects(
            slocator_collection.objects, transform, operator_on_slocators
        )
