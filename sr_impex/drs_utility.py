import os
import json
from os.path import dirname, realpath
from math import radians
import time
import hashlib
import subprocess
from struct import pack
from collections import defaultdict
from typing import Tuple, List, Dict, Optional
import xml.etree.ElementTree as ET
from mathutils import Matrix, Vector
import bpy
from bmesh.ops import (
    triangulate as tri,
    remove_doubles,
    split_edges,
    create_uvsphere,
    create_cone,
)
import bmesh.types

from .drs_definitions import (
    DRS,
    BMS,
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
    Matrix3x3,
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
    AMS,
)
from .drs_material import DRSMaterial
from .ska_definitions import SKA
from .ska_utility import get_actions
from .transform_utils import (
    ensure_mode,
    apply_transformation,
    get_collection,
)
from .bmesh_utils import new_bmesh_from_object, edit_bmesh_from_object, new_bmesh
from .animation_utils import import_ska_animation
from .message_logger import MessageLogger

logger = MessageLogger()
resource_dir = dirname(realpath(__file__)) + "/resources"
texture_cache_col = {}
texture_cache_nor = {}
texture_cache_par = {}
texture_cache_ref = {}

with open(resource_dir + "/bone_versions.json", "r", encoding="utf-8") as f:
    bones_list = json.load(f)

# region General Helper Functions


def find_or_create_collection(
    source_collection: bpy.types.Collection, collection_name: str
) -> bpy.types.Collection:
    collection = source_collection.children.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        source_collection.children.link(collection)

    return collection


def abort(
    keep_debug_collections: bool, source_collection_copy: bpy.types.Collection
) -> dict:
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
        remove_doubles(unified_mesh, verts=unified_mesh.verts, dist=0.0001)

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
    """
    Create the new Battleforge scene structure with the following hierarchy:
      - DRSModel_<scene_type>
             ├── Meshes_Collection
             └── CollisionShapes_Collection (if collision_support is True)
                      ├── Boxes_Collection
                      ├── Spheres_Collection
                      └── Cylinders_Collection
    """

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


def process_module_import(
    slocator,
    source_collection,
    armature_object,
    dir_name,
    drs_file,
    import_animation,
    import_debris,
):
    # Determine module type and choose the correct collection name.
    module_type = slocator.class_type  # e.g., "Module1" or "Module2"
    module_collection_name = "Modules1" if module_type == "Module1" else "Modules2"
    module_collection = find_or_create_collection(
        source_collection, module_collection_name
    )

    # Replace the module extension with .bms and read the module file.
    module_file_name = slocator.file_name.replace(".module", ".bms")
    module = BMS().read(os.path.join(dir_name, module_file_name))

    # Build a module-specific name and prefix.
    module_name = f"{module_type}_{slocator.sub_id}"
    prefix = "Module_1_" if module_type == "Module1" else "Module_2_"

    # Call the existing state-based mesh importer with the proper parameters.
    import_state_based_mesh_set(
        module.state_based_mesh_set,
        module_collection,
        armature_object,
        dir_name,
        drs_file,
        import_animation,
        import_debris,
        module_name,
        slocator,
        prefix,
    )


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
    img.save(filepath=temp_path)

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

    result = subprocess.run(
        final_cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        shell=False,
    )

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
        raise RuntimeError(f"Failed to access image pixels: {e}")

    # Pack the floats into bytes safely
    try:
        pixel_bytes = pack(f"{len(pixels)}f", *pixels)
    except Exception as e:
        raise RuntimeError(f"Failed to pack pixel data: {e}")

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

    # Assume the DDS file is generated as <texture_name>.dds in folder_path.
    dds_path = os.path.join(texture_name)
    cache[key] = dds_path
    return dds_path


def clean_vector(vec, tol=1e-6):
    """Set any component of vec to 0 if its absolute value is below tol."""
    return Vector([0.0 if abs(c) < tol else c for c in vec])


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


def create_bone_tree(
    armature_data: bpy.types.Armature, bone_list: list[DRSBone], bone_data: DRSBone
):
    edit_bones = armature_data.edit_bones
    edit_bone = edit_bones.new(bone_data.name)
    armature_data.display_type = "STICK"
    edit_bone.head = bone_data.bone_matrix @ Vector((0, 0, 0))
    edit_bone.tail = bone_data.bone_matrix @ Vector((0, 1, 0))
    edit_bone.length = 0.1
    edit_bone.align_roll(bone_data.bone_matrix.to_3x3() @ Vector((0, 0, 1)))

    # Set the parent bone
    if bone_data.parent != -1:
        parent_bone_name = bone_list[bone_data.parent].name
        edit_bone.parent = armature_data.edit_bones.get(parent_bone_name)

    for child_bone in [b for b in bone_list if b.parent == bone_data.identifier]:
        create_bone_tree(armature_data, bone_list, child_bone)


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
        bone_list_item.parent = bone_vertices[0].parent

        # Print if parent = -1
        if bone_list_item.parent == -1:
            print(f"Bone {bone_list_item.name} has no parent.")

    # Order the Bones by Parent ID
    bone_list.sort(key=lambda x: x.identifier)

    # Return the BoneList
    return bone_list


def import_csk_skeleton(
    source_collection: bpy.types.Collection, drs_file: DRS
) -> Tuple[bpy.types.Object, list[DRSBone]]:
    # Create the Armature Data
    armature_data: bpy.types.Armature = bpy.data.armatures.new("CSkSkeleton")
    # Create the Armature Object and add the Armature Data to it
    armature_object: bpy.types.Object = bpy.data.objects.new("Armature", armature_data)
    # Link the Armature Object to the Source Collection
    source_collection.objects.link(armature_object)
    # Create the Skeleton
    bone_list = init_bones(drs_file.csk_skeleton)
    # Directly set armature data to edit mode
    bpy.context.view_layer.objects.active = armature_object
    with ensure_mode("EDIT"):
        create_bone_tree(armature_data, bone_list, bone_list[0])
    record_bind_pose(bone_list, armature_data)
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
        face: Face = battleforge_mesh_data.faces[_].indices
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
    mesh_index,
    dir_name,
    base_name,
    bone_list=None,
    bone_weights: List[VertexData] = None,
    armature_object=None,
    transform_matrix=None,
    cgeo_mesh: CGeoMesh = None,
    offset: int = None,
):
    # Create the mesh data using your existing helper.
    mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)

    # Create the mesh object.
    mesh_object = bpy.data.objects.new(f"CDspMeshFile_{mesh_index}", mesh_data)

    # Add skin weights if available.
    if drs_file.csk_skin_info and bone_weights and bone_list:
        add_skin_weights_to_mesh(
            mesh_object,
            drs_file.cdsp_mesh_file.meshes[mesh_index],
            drs_file.cdsp_joint_map.joint_groups[mesh_index],
            armature_object,
        )

    # Link armature if a skeleton exists.
    if drs_file.csk_skeleton and armature_object:
        mesh_object.parent = armature_object
        modifier = mesh_object.modifiers.new(type="ARMATURE", name="Armature")
        modifier.object = armature_object

    # Apply transformation if provided.
    if transform_matrix is not None:
        mesh_object.matrix_world = transform_matrix

    # Create and assign material.
    material = create_material(
        dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name
    )
    mesh_data.materials.append(material)

    return mesh_object, mesh_data


def setup_armature(
    source_collection, drs_file: DRS
) -> Tuple[bpy.types.Object, list[DRSBone]]:
    armature_object, bone_list = None, None
    if drs_file.csk_skeleton is not None:
        armature_object, bone_list = import_csk_skeleton(source_collection, drs_file)
        # Optionally: add any shared animation setup here.
    return armature_object, bone_list


def apply_slocator_transform(mesh_object, slocator):
    location = (
        slocator.cmat_coordinate_system.position.x,
        slocator.cmat_coordinate_system.position.y,
        slocator.cmat_coordinate_system.position.z,
    )
    # Convert the flat rotation list into a 3x3 Matrix.
    rotation_vals = slocator.cmat_coordinate_system.matrix.matrix
    rotation_matrix = Matrix(
        [list(rotation_vals[i : i + 3]) for i in range(0, len(rotation_vals), 3)]
    ).transposed()
    local_matrix = Matrix.Translation(location) @ rotation_matrix.to_4x4()
    mesh_object.matrix_world = local_matrix


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


def import_state_based_mesh_set(
    state_based_mesh_set: StateBasedMeshSet,
    source_collection: bpy.types.Collection,
    armature_object: bpy.types.Object,
    dir_name: str,
    bmg_file: DRS,
    import_animation: bool,
    animation_type: str,
    import_debris: bool,
    import_collision_shape: bool,
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

            if drs_file.csk_skeleton is not None and armature_object is None:
                # Create the Armature Data
                armature_data: bpy.types.Armature = bpy.data.armatures.new(
                    "CSkSkeleton"
                )
                # Create the Armature Object and add the Armature Data to it
                armature_object: bpy.types.Object = bpy.data.objects.new(
                    "Armature", armature_data
                )
                # Link the Armature Object to the Source Collection
                source_collection.objects.link(armature_object)
                # Create the Skeleton
                bone_list = init_bones(drs_file.csk_skeleton)
                # Directly set armature data to edit mode
                bpy.context.view_layer.objects.active = armature_object
                with ensure_mode("EDIT"):
                    # Create the Bone Tree without using bpy.ops or context
                    create_bone_tree(armature_data, bone_list, bone_list[0])
                record_bind_pose(bone_list, armature_data)
                # Add the Animations to the Armature Object
                if bmg_file.animation_set is not None:
                    pass

            if drs_file.csk_skin_info is not None:
                # Create the Bone Weights
                bone_weights = create_bone_weights(
                    drs_file.cdsp_mesh_file, drs_file.csk_skin_info, drs_file.cgeo_mesh
                )

            if drs_file.collision_shape is not None and import_collision_shape:
                import_collision_shapes(state_collection, drs_file)

            for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
                offset = (
                    0
                    if mesh_index == 0
                    else drs_file.cdsp_mesh_file.meshes[mesh_index - 1].vertex_count
                )
                # Create the Mesh Data
                mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)
                # Create the Mesh Object and add the Mesh Data to it
                mesh_object: bpy.types.Object = bpy.data.objects.new(
                    f"CDspMeshFile_{mesh_index}", mesh_data
                )
                # Add the Bone Weights to the Mesh Object
                if drs_file.csk_skin_info is not None:
                    add_skin_weights_to_mesh(
                        mesh_object,
                        bone_list,
                        bone_weights,
                        offset,
                        drs_file.cdsp_mesh_file.meshes[mesh_index],
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
                    # Apply the Local Matrix to the Mesh Object
                    # if apply_transform:
                    #     mesh_object.matrix_world = global_matrix @ local_matrix
                    #     mirror_object_by_vector(mesh_object, Vector((0, 0, 1)))
                    # else:
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
                with ensure_mode("POSE"):
                    for animation_key in bmg_file.animation_set.mode_animation_keys:
                        for variant in animation_key.animation_set_variants:
                            ska_file: SKA = SKA().read(
                                os.path.join(dir_name, variant.file)
                            )
                            create_animation(
                                ska_file,
                                armature_object,
                                bone_list,
                                variant.file,
                                animation_type,
                                animation_smoothing,
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


def load_drs(
    context: bpy.types.Context,
    filepath="",
    apply_transform=True,
    import_collision_shape=False,
    import_animation=True,
    import_animation_type="FRAMES",
    import_animation_fps=30,
    animation_smoothing=True,
    import_ik_atlas=False,
    import_debris=False,
    import_modules=True,
) -> None:

    start_time = time.time()
    base_name = os.path.basename(filepath).split(".")[0]
    dir_name = os.path.dirname(filepath)
    drs_file: DRS = DRS().read(filepath)
    bpy.context.scene.render.fps = import_animation_fps

    source_collection: bpy.types.Collection = bpy.data.collections.new(
        "DRSModel_" + base_name
    )
    context.scene.collection.children.link(source_collection)

    armature_object, bone_list = setup_armature(source_collection, drs_file)

    mesh_collection: bpy.types.Collection = bpy.data.collections.new(
        "Meshes_Collection"
    )
    source_collection.children.link(mesh_collection)

    skin_vertex_data = None
    if drs_file.csk_skin_info is not None:
        skin_vertex_data = drs_file.csk_skin_info.vertex_data

    offset = 0
    for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
        mesh_object, _ = create_mesh_object(
            drs_file,
            mesh_index,
            dir_name,
            base_name,
            bone_list,
            skin_vertex_data,
            armature_object,
            None,
            drs_file.cgeo_mesh,
            offset,
        )
        offset += drs_file.cdsp_mesh_file.meshes[mesh_index].vertex_count
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
                        import_animation_fps,
                        animation_smoothing,
                        import_animation_type,
                    )
    else:
        # Check if an model_name.ams file is in the folder
        if os.path.exists(os.path.join(dir_name, base_name + ".ams")):
            # Load the Animation Set from the AMS file
            ams_file: AMS = AMS().read(os.path.join(dir_name, base_name + ".ams"))

            if ams_file:
                with ensure_mode("POSE"):
                    for animation_key in ams_file.animation_set.animations:
                        for variant in animation_key.variants:
                            ska_file: SKA = SKA().read(
                                os.path.join(dir_name, variant.file_name)
                            )
                            # Create the Animation
                            import_ska_animation(
                                ska_file,
                                armature_object,
                                bone_list,
                                variant.file_name,
                                import_animation_fps,
                                animation_smoothing,
                                import_animation_type,
                            )
        # Check if an model_name.ska file is in the folder
        elif os.path.exists(os.path.join(dir_name, base_name + ".ska")):
            # Load the Animation Set from the SKA file
            ska_file: SKA = SKA().read(os.path.join(dir_name, base_name + ".ska"))

            if ska_file:
                with ensure_mode("POSE"):
                    import_ska_animation(
                        ska_file,
                        armature_object,
                        bone_list,
                        base_name + ".ska",
                        import_animation_fps,
                        animation_smoothing,
                        import_animation_type,
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
        for slocator in drs_file.cdrw_locator_list.slocators:
            if slocator.file_name_length > 0 and slocator.class_type in {
                "Module1",
                "Module2",
            }:
                process_module_import(
                    slocator,
                    source_collection,
                    armature_object,
                    dir_name,
                    drs_file,
                    import_animation,
                    import_debris,
                )

    # Apply the Transformations to the Source Collection
    apply_transformation(
        source_collection, armature_object, apply_transform, False, True, True
    )

    # Print the Time Measurement
    logger.log(
        f"Imported {base_name} in {time.time() - start_time:.2f} seconds.",
        "Import Time",
        "INFO",
    )
    logger.display()
    return {"FINISHED"}


def import_mesh_set_grid(
    bmg_file: DRS,
    source_collection: bpy.types.Collection,
    armature_object: bpy.types.Object,
    dir_name: str,
    base_name: str,
    import_animation: bool,
    animation_type: str,
    import_debris: bool,
    import_collision_shape: bool,
) -> bpy.types.Object:
    for module in bmg_file.mesh_set_grid.mesh_modules:
        if module.has_mesh_set:
            temp_armature_object = import_state_based_mesh_set(
                module.state_based_mesh_set,
                source_collection,
                armature_object,
                dir_name,
                bmg_file,
                import_animation,
                animation_type,
                import_debris,
                import_collision_shape,
                base_name,
            )
            if temp_armature_object is not None:
                armature_object = temp_armature_object

    return armature_object


def load_bmg(
    context: bpy.types.Context,
    filepath="",
    apply_transform=True,
    import_collision_shape=False,
    import_animation=True,
    import_animation_type="FRAMES",
    import_animation_fps=30,
    import_debris=True,
    import_construction=True,
) -> None:
    start_time = time.time()
    dir_name = os.path.dirname(filepath)
    base_name = os.path.basename(filepath).split(".")[0]
    bpy.context.scene.render.fps = import_animation_fps
    source_collection: bpy.types.Collection = bpy.data.collections.new(
        "DRSModel_" + base_name
    )
    context.collection.children.link(source_collection)
    bmg_file: DRS = DRS().read(filepath)

    # Models share the same Skeleton Files, so we only need to create one Armature and share it across all sub-modules!
    armature_object = None

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
        armature_object = import_mesh_set_grid(
            bmg_file,
            source_collection,
            armature_object,
            dir_name,
            base_name,
            import_animation,
            import_animation_type,
            import_debris,
            import_collision_shape,
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
                    module_name = slocator.class_type + "_" + str(slocator.sub_id)
                    import_state_based_mesh_set(
                        bms_file.state_based_mesh_set,
                        slocator_collection,
                        construction_dir,
                        bms_file,
                        import_animation,
                        import_debris,
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

    # Apply the Transformations to the Source Collection
    apply_transformation(
        source_collection,
        armature_object,
        apply_transform,
        False,
        True,
        True,
        True,
        True,
    )

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
    with new_bmesh() as bm:
        for mesh in meshes_collection.objects:
            if mesh.type == "MESH":
                bm.from_mesh(mesh.data)

        # Count Faces and Vertices before removing doubles
        face_count = len(bm.faces)
        vertex_count = len(bm.verts)

        # Remove Duplicates by lowest possible float
        remove_doubles(bm, verts=bm.verts, dist=0.00001)

        # Create the new Mesh
        unified_mesh = bpy.data.meshes.new("unified_mesh")
        bm.to_mesh(unified_mesh)

    # Count Faces and Vertices after removing doubles
    face_count_after = len(unified_mesh.polygons)
    vertex_count_after = len(unified_mesh.vertices)

    # Show the Message Box
    logger.log(
        f"Unified Mesh has {face_count_after} Faces and {vertex_count_after} Vertices after removing duplicates. The original Mesh had {face_count} Faces and {vertex_count} Vertices.",
        "Unified Mesh",
        "INFO",
    )

    return unified_mesh


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


def create_obb_node(unique_mesh: bpy.types.Mesh) -> OBBNode:
    """Create an OBB Node for the OBB Tree."""
    obb_node = OBBNode()
    obb_node.node_depth = 0
    obb_node.current_triangle_count = 0
    obb_node.minimum_triangles_found = len(unique_mesh.polygons)
    obb_node.unknown1 = 0
    obb_node.unknown2 = 0
    obb_node.unknown3 = 0
    obb_node.oriented_bounding_box = CMatCoordinateSystem()
    # TODO: We need to update this later as we need to calculate the center of the mesh
    obb_node.oriented_bounding_box.position = Vector((0, 0, 0))
    # TODO: We need to update this later as we need to calculate the rotation of the mesh
    obb_node.oriented_bounding_box.matrix = Matrix.Identity(3)

    return obb_node


def create_cgeo_obb_tree(unique_mesh: bpy.types.Mesh) -> CGeoOBBTree:
    """Create a CGeoOBBTree from a Blender Mesh Object."""
    _cgeo_obb_tree = CGeoOBBTree()
    _cgeo_obb_tree.triangle_count = len(unique_mesh.polygons)
    _cgeo_obb_tree.faces = []

    for _face in unique_mesh.polygons:
        new_face = Face()
        new_face.indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
        _cgeo_obb_tree.faces.append(new_face)

    _cgeo_obb_tree.matrix_count = 0
    _cgeo_obb_tree.obb_nodes = []

    for _ in range(_cgeo_obb_tree.matrix_count):
        _cgeo_obb_tree.obb_nodes.append(create_obb_node(unique_mesh))

    return _cgeo_obb_tree


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
        return

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
        return

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
                # Blue channel (placeholder for Fluid Map)
                0,
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
    mesh: bpy.types.Mesh,
    mesh_index: int,
    model_name: str,
    folder_path: str,
    flip_normals: bool,
    add_skin_mesh: bool = False,
) -> Tuple[BattleforgeMesh, Dict[str, int]]:
    """Create a Battleforge Mesh from a Blender Mesh Object."""
    if flip_normals:
        with ensure_mode("EDIT"):
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.flip_normals()
            bpy.ops.mesh.select_all(action="DESELECT")

    mesh.data.calc_tangents()
    # [bone_name] = local_index
    # ["root_ref"] = root_ref
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
    mesh_material: bpy.types.Material = mesh.material_slots[0].material
    material_nodes: List[bpy.types.Node] = mesh_material.node_tree.nodes
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

    if flu_map is None or flu_map.is_linked is False:
        # -86061055: no MaterialStuff, no Fluid, no String, no LOD
        new_mesh.material_parameters = -86061055  # Hex: 0xFADED001
    else:
        # -86061050: All Materials
        new_mesh.material_parameters = -86061050  # Hex: 0xFADED006
        new_mesh.material_stuff = 0  # Added for Hex 0xFADED004+
        # Level of Detail
        new_mesh.level_of_detail = LevelOfDetail()  # Added for Hex 0xFADED002+
        # Empty String
        new_mesh.empty_string = EmptyString()  # Added for Hex 0xFADED003+
        # Flow
        new_mesh.flow = (
            Flow()
        )  # Maybe later we can add some flow data in blender. Added for Hex 0xFADED006

    # Individual Material Parameters depending on the MaterialID:
    new_mesh.bool_parameter = 0
    bool_param_bit_flag = 0
    # Textures
    new_mesh.textures = Textures()

    # Check if the Color Map is set
    if not set_color_map(color_map, new_mesh, mesh_index, model_name, folder_path):
        return None

    # Check if the Normal Map is set
    if not skip_normal_map:
        bool_param_bit_flag = set_normal_map(
            normal_map,
            new_mesh,
            mesh_index,
            model_name,
            folder_path,
            bool_param_bit_flag,
        )

    # Check if the Metallic, Roughness and Emission Map is set
    if not skip_param_map:
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

    # Set the Bool Parameter by a bin -> dec conversion
    new_mesh.bool_parameter = int(str(bool_param_bit_flag), 2)

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
) -> Tuple[CDspMeshFile, List[Dict[str, int]]]:
    """Create a CDspMeshFile from a Collection of Meshes."""
    _cdsp_meshfile = CDspMeshFile()
    _cdsp_meshfile.mesh_count = 0

    mesh_bone_data: List[Dict[str, int]] = []

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
    """Create a SkinInfo."""
    skin_info = CSkSkinInfo()
    skin_info.vertex_data = []
    skin_info.vertex_count += len(unified_mesh.vertices)

    unified_hashtable = {}
    for v in unified_mesh.vertices:
        key = tuple(round(coord, 6) for coord in v.co)
        if key not in unified_hashtable:
            unified_hashtable[key] = v.index
        else:
            logger.log(
                f"Duplicate vertex found in unified mesh: {v.co}", "Error", "ERROR"
            )
            return skin_info

    vertex_data: List[VertexData] = [None] * len(unified_mesh.vertices)
    for mesh in meshes_collection.objects:
        if mesh.type == "MESH":
            # We need to map the mesh vertex to the unified index
            for vertex in mesh.data.vertices:
                key = tuple(round(coord, 6) for coord in vertex.co)
                if key in unified_hashtable:
                    index = unified_hashtable[key]

                    if vertex_data[index] is None:
                        vertex_data[index] = VertexData(bone_indices=[], weights=[])

                    # We need to get all vertex groups from the mesh and map them to the skeleton, we take the bone order from the armature
                    for vertex_group in vertex.groups:
                        # bone_index = vertex_group.group
                        bone_group = vertex_group.group
                        bone_name: str = mesh.vertex_groups[bone_group].name
                        bone_data = bone_map.get(bone_name, -1)
                        if bone_data == -1:
                            logger.log(
                                f"Bone {bone_name} not found in bone map for vertex {vertex.index}",
                                "Error",
                                "ERROR",
                            )
                            continue
                        bone_index = bone_data["id"]
                        bone_weight = vertex_group.weight
                        if bone_index not in vertex_data[index].bone_indices:
                            vertex_data[index].bone_indices.append(bone_index)
                            vertex_data[index].weights.append(bone_weight)
                else:
                    logger.log(
                        f"Vertex {vertex.index} not found in unified mesh: {vertex.co}",
                        "Error",
                        "ERROR",
                    )
                    continue

    # Fill the vertex data with zeros up to 4 bones
    for vertex in vertex_data:
        if vertex is None:
            continue
        while len(vertex.bone_indices) < 4:
            vertex.bone_indices.append(0)
            vertex.weights.append(0.0)

    skin_info.vertex_data = vertex_data

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
            logger.log(
                f"Bone {bone.name} not found in bones list. Skipping it.",
                "Error",
                "ERROR",
            )
            continue
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
        vec_3 = clean_vector(-(rot.inverted() @ loc))
        vec_0 = clean_vector(rot[0].copy())
        vec_1 = clean_vector(rot[1].copy())
        vec_2 = clean_vector(rot[2].copy())

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
    """Create an AnimationSet."""
    animation_set = AnimationSet()
    animation_set.version = 6
    animation_set.default_run_speed = 4.8
    animation_set.default_walk_speed = 2.3
    animation_set.revision = 6
    animation_set.mode_change_type = 0
    animation_set.hovering_ground = 0
    animation_set.fly_bank_scale = 1.0
    animation_set.fly_accel_scale = 0
    animation_set.fly_hit_scale = 1.0
    animation_set.allign_to_terrain = 0
    animation_set.has_atlas = 1
    animation_set.atlas_count = 0
    animation_set.ik_atlases = []  # Not needed here
    animation_set.subversion = 2
    animation_set.animation_marker_count = 0  # Not needed here
    animation_set.animation_marker_sets = []  # Not needed here
    animation_set.mode_animation_keys = []

    # Get all Action
    all_actions = get_actions()
    available_action = []

    # We only allow actions with the same name as the export animation name or _idle
    for action_name in all_actions:
        action_name_without_ska = action_name.replace(".ska", "")
        if (
            action_name_without_ska == model_name
            or action_name_without_ska.find("_idle") != -1
        ):
            available_action.append(action_name)

    if len(available_action) == 0:
        logger.log(
            "No valid Action found. Please check the Action Names.",
            "Error",
            "ERROR",
        )
        return animation_set

    animation_set.mode_animation_key_count = 1
    animation_key = ModeAnimationKey()
    animation_key.type = 6
    animation_key.length = 11
    animation_key.file = "Battleforge"
    animation_key.unknown = 2
    animation_key.unknown2 = 3
    animation_key.vis_job = 0
    animation_key.unknown3 = 3
    animation_key.unknown4 = 0
    animation_key.animation_set_variants = []
    animation_key.variant_count = 0

    for action_name in available_action:
        animation_key.variant_count += 1
        variant = AnimationSetVariant()
        variant.version = 4
        variant.weight = 100 // len(available_action)
        variant.start = 0
        variant.end = 1
        variant.length = len(action_name)
        variant.file = action_name
        animation_key.animation_set_variants.append(variant)

    animation_set.mode_animation_keys.append(animation_key)

    return animation_set


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
        for j in range(len(skinning_mesh_data.vertices)):
            # Check the 2nd, 3rd and 4th bone index for -1
            if skinning_mesh_data.vertices[j].bone_indices[1] == -1:
                skinning_mesh_data.vertices[j].bone_indices[1] = per_mesh_bone_data[
                    "root_ref"
                ]
            if skinning_mesh_data.vertices[j].bone_indices[2] == -1:
                skinning_mesh_data.vertices[j].bone_indices[2] = per_mesh_bone_data[
                    "root_ref"
                ]
            if skinning_mesh_data.vertices[j].bone_indices[3] == -1:
                skinning_mesh_data.vertices[j].bone_indices[3] = per_mesh_bone_data[
                    "root_ref"
                ]
    return cdsp_mesh_file


def save_drs(
    context: bpy.types.Context,
    filepath: str,
    use_apply_transform: bool,
    split_mesh_by_uv_islands: bool,
    flip_normals: bool,
    keep_debug_collections: bool,
    model_type: str,
    model_name: str,
) -> dict:
    """Save the DRS file."""
    global texture_cache_col, texture_cache_nor, texture_cache_par, texture_cache_ref
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
    if model_type in ["AnimatedObjectNoCollision", "AnimatedObjectCollision"]:
        for obj in source_collection_copy.objects:
            if obj.type == "ARMATURE":
                armature_object = obj
                add_skin_mesh = True
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

    try:
        set_origin_to_world_origin(meshes_collection)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error setting origin for meshes: {e}", "Origin Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    # === APPLY TRANSFORMATIONS =================================================
    apply_transformation(
        source_collection_copy, armature_object, use_apply_transform, True, True, True
    )

    # === CREATE DRS STRUCTURE =================================================
    folder_path = os.path.dirname(filepath)

    new_drs_file: DRS = DRS(model_type=model_type)
    try:
        unified_mesh = create_unified_mesh(meshes_collection)
    except Exception as e:  # pylint: disable=broad-except
        logger.log(f"Error creating unified mesh: {e}", "Unified Mesh Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    # Generate the CDspMeshFile
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
            new_drs_file.animation_timings = AnimationTimings()
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
    # try:
    #     new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))
    # except Exception as e:  # pylint: disable=broad-except
    #     logger.log(f"Error saving DRS file: {e}", "Save Error", "ERROR")
    #     return abort(keep_debug_collections, source_collection_copy)
    new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))

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
