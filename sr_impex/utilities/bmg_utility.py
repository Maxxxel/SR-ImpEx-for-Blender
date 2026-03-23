"""
BMG (Building Mesh Grid) Utility Module

This module handles loading and importing BMG files into Blender.
BMG files define building layouts with modular grids and state-based meshes.
"""

import os
import json
import time
from typing import Tuple, Dict, Optional
import xml.etree.ElementTree as ET
from mathutils import Matrix
import bpy

from sr_impex.core.message_logger import MessageLogger

from sr_impex.definitions.bmg_definitions import BMG, BMS
from sr_impex.definitions.drs_definitions import DRS
from sr_impex.definitions.ska_definitions import SKA
from sr_impex.definitions.locator_definitions import SLocator
from sr_impex.definitions.grid_definitions import MeshGridModule, MeshSetGrid, StateBasedMeshSet
from sr_impex.definitions.base_types import ExportError
from sr_impex.definitions.enums import InformationIndices

from sr_impex.blender.editors.animation_set_editor import ANIM_BLOB_KEY
from sr_impex.blender.editors.effect_set_editor import (
    EFFECT_BLOB_KEY,
)
from sr_impex.blender.editors.bmg_state_editor import MESHGRID_BLOB_KEY, switch_meshset_state
from sr_impex.utilities.helpers import verify_collections, abort, copy, build_ska_export_name_map

# Import required functions from drs_utility
# These are shared between DRS and BMG import/export
from sr_impex.utilities.drs_utility import (
    create_static_mesh,
    create_material,
    create_mesh_object,
    setup_armature,
    import_collision_shapes,
    import_ska_animation,
    import_animation_ik_atlas,
    parent_under_game_axes,
    ensure_mode,
    find_or_create_collection,
    persist_animset_blob_on_collection,
    setup_material_parameters,
    create_collision_shape_box_object,
    create_collision_shape_sphere_object,
    create_collision_shape_cylinder_object,
)


logger = MessageLogger()

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


def import_debris_from_xml(xml_file_path: str, dir_name: str, base_name: str, collection_name: str) -> bpy.types.Collection:
    """
    Import debris models from an XML file and return a collection containing them.

    Args:
        xml_file_path: Path to the XML file defining debris
        dir_name: Directory containing the mesh files
        base_name: Base name for material naming
        collection_name: Name for the debris collection

    Returns:
        Collection containing all debris meshes from the XML
    """
    debris_collection = bpy.data.collections.new(collection_name)

    # Load and parse the XML file
    with open(xml_file_path, "r", encoding="utf-8") as file:
        xml_file = file.read()
    xml_root = ET.fromstring(xml_file)

    # Loop through PhysicObject elements and create meshes
    for element in xml_root.findall(".//Element[@type='PhysicObject']"):
        resource = element.attrib.get("resource")
        name = element.attrib.get("name")
        if resource and name:
            debris_drs_file = DRS().read(os.path.join(dir_name, "meshes", resource))
            for mesh_index in range(debris_drs_file.cdsp_mesh_file.mesh_count):
                # Create the mesh data and object
                mesh_data = create_static_mesh(
                    debris_drs_file.cdsp_mesh_file, mesh_index
                )
                mesh_object = bpy.data.objects.new(
                    f"CDspMeshFile_{name}", mesh_data
                )

                # Create and assign the material
                material = create_material(
                    dir_name,
                    mesh_index,
                    debris_drs_file.cdsp_mesh_file.meshes[mesh_index],
                    f"{base_name}_{name}",
                )
                mesh_data.materials.append(material)

                # Link the debris mesh object to the collection
                debris_collection.objects.link(mesh_object)

    return debris_collection


# region Import BMG

def create_meshset_structure(
    parent_collection: bpy.types.Collection,
    meshset_index: int,
    mesh_states: list,
    destruction_states: list,
    dir_name: str,
    base_name: str,
    armature_object: bpy.types.Object = None,
    import_collision_shape: bool = False,
    import_s0_collision_shapes: bool = False,
) -> tuple[bpy.types.Collection, bpy.types.Object]:
    """
    Create organized hierarchical structure for a single MeshSet with all states.

    Structure:
        MeshSet_N
        ├── States_Collection (hidden by default)
        │   ├── S0_Undamaged
        │   ├── S2_Damaged
        │   └── Debris_Collection
        │       ├── S2_Debris (hidden)
        │       └── S3_Debris (hidden)
        └── Active_State (empty marker)

    Args:
        parent_collection: Parent collection to link the MeshSet to
        meshset_index: Index of this MeshSet
        mesh_states: List of MeshState objects from StateBasedMeshSet
        destruction_states: List of DestructionState objects
        dir_name: Directory containing files
        base_name: Base name for materials
        armature_object: Armature to parent meshes to
        import_collision_shape: Whether to import collision shapes for S2 states
        import_s0_collision_shapes: Whether to import collision shapes for S0 states (BMG-level shapes apply to all S0)

    Returns:
        (meshset_collection, active_marker) tuple
    """
    # Create MeshSet container
    meshset_col = bpy.data.collections.new(f"MeshSet_{meshset_index}")
    parent_collection.children.link(meshset_col)

    # Create States subcollection (hidden by default) with unique name
    states_col = bpy.data.collections.new(f"States_Collection_{meshset_index}")
    meshset_col.children.link(states_col)
    states_col.hide_viewport = True
    states_col.hide_render = True

    # Import each mesh state (S0, S2, etc.)
    for mesh_state in mesh_states:
        if mesh_state.has_files:
            state_name = f"S{mesh_state.state_num}_{'Undamaged' if mesh_state.state_num == 0 else 'Damaged'}"
            state_col = bpy.data.collections.new(state_name)
            state_col["state_type"] = f"S{mesh_state.state_num}"
            state_col["mesh_set_index"] = meshset_index
            states_col.children.link(state_col)

            # Create Meshes subcollection
            meshes_col = bpy.data.collections.new("Meshes_Collection")
            state_col.children.link(meshes_col)

            # Load DRS file
            drs_file: DRS = DRS().read(os.path.join(dir_name, mesh_state.drs_file))

            # Import collision shapes if present
            # S0 (undamaged): only import if import_s0_collision_shapes is True (BMG-level shapes apply to all S0)
            # S2+ (damaged): always import as they differ from S0 due to damage
            should_import_collision = False
            if drs_file.collision_shape is not None and import_collision_shape:
                if mesh_state.state_num == 0:
                    should_import_collision = import_s0_collision_shapes
                else:
                    should_import_collision = True

            if should_import_collision:
                import_collision_shapes(state_col, drs_file)

            # Import meshes
            for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
                mesh_object, _ = create_mesh_object(
                    drs_file,
                    mesh_index,
                    dir_name,
                    base_name,
                    armature_object,
                )
                setup_material_parameters(mesh_object, drs_file, mesh_index)
                meshes_col.objects.link(mesh_object)

    # Create Debris subcollection
    if destruction_states and len(destruction_states) > 0:
        debris_col = bpy.data.collections.new("Debris_Collection")
        states_col.children.link(debris_col)
        debris_col.hide_viewport = True
        debris_col.hide_render = True

        # Import debris from each destruction state XML
        for destruction_state in destruction_states:
            xml_file_path = os.path.join(dir_name, destruction_state.file_name)
            if os.path.exists(xml_file_path):
                debris_state_name = f"S{destruction_state.state_num}_Debris"
                debris_state_col = import_debris_from_xml(
                    xml_file_path,
                    dir_name,
                    base_name,
                    debris_state_name
                )
                debris_state_col["state_type"] = f"S{destruction_state.state_num}_debris"
                debris_state_col["mesh_set_index"] = meshset_index
                debris_col.children.link(debris_state_col)

    # Create active state marker (empty object)
    active_marker = bpy.data.objects.new(f"Active_State_MeshSet_{meshset_index}", None)
    active_marker.empty_display_type = 'CUBE'
    active_marker.empty_display_size = 0.5
    active_marker["active_state"] = "S0"  # Default to undamaged
    active_marker["mesh_set_index"] = meshset_index
    meshset_col.objects.link(active_marker)

    # Initially show S0 (undamaged) state
    switch_meshset_state(meshset_col, "S0")

    return meshset_col, active_marker


def persist_meshgrid_blob_on_collection(
    collection: bpy.types.Collection, bmg_file: BMG
):
    """Store MeshSetGrid data as JSON blob on collection for export roundtrip."""
    if not bmg_file.mesh_set_grid:
        return

    grid = bmg_file.mesh_set_grid
    blob = {
        "rows": grid.grid_height,
        "columns": grid.grid_width,
        "orientation": grid.grid_rotation if hasattr(grid, "grid_rotation") else 0,
        "ground_decal": grid.ground_decal if grid.ground_decal else "",
        "cells": [],
    }

    for i, module in enumerate(grid.mesh_modules):
        cell = {
            "index": i,
            "has_mesh_set": module.has_mesh_set,
            "mesh_object_name": "",  # Will be filled during import
        }
        blob["cells"].append(cell)

    collection[MESHGRID_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


def import_state_based_mesh_set(
    state_based_mesh_set: StateBasedMeshSet,
    source_collection: bpy.types.Collection,
    armature_object: bpy.types.Object,
    bone_list: list,
    dir_name: str,
    bmg_file: DRS,
    import_animation: bool,
    smooth_animation: bool,
    import_debris: bool,
    import_collision_shape: bool,
    import_s0_collision_shapes: bool,
    import_ik_atlas: bool,
    base_name: str,
    slocator: SLocator = None,
    prefix: str = "",
) -> bpy.types.Object:
    """Import a state-based mesh set (used by both BMG and construction pieces)"""
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
                    base_name
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

    # Get individual destruction States
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
    import_s0_collision_shapes: bool,
    import_ik_atlas: bool,
) -> Tuple[bpy.types.Object, Optional[list], Dict[int, str]]:
    """
    Import a MeshSetGrid using the new hierarchical collection structure.

    Creates a cleaner hierarchy:
        MeshSetGrid_0
        ├── MeshSet_0
        │   ├── States_Collection (hidden)
        │   │   ├── S0_Undamaged
        │   │   ├── S2_Damaged
        │   │   └── Debris_Collection (hidden)
        │   └── Active_State (marker)
        └── MeshSet_1
            └── ...

    Returns:
        Tuple of (armature_object, bone_list, module_mesh_map)
    """
    # Create MeshSetGrid Collection to organize all MeshSets
    mesh_set_grid_collection: bpy.types.Collection = bpy.data.collections.new(
        "MeshSetGrid_0"
    )
    source_collection.children.link(mesh_set_grid_collection)
    bone_list = None

    # Track mesh objects per module index for grid mapping
    module_mesh_map = {}
    module_index = 0

    for module in bmg_file.mesh_set_grid.mesh_modules:
        if module.has_mesh_set:
            # Setup armature if needed (shared across all modules)
            if armature_object is None:
                # Try to get skeleton from first available mesh state
                for mesh_state in module.state_based_mesh_set.mesh_states:
                    if mesh_state.has_files:
                        file_path = os.path.join(dir_name, mesh_state.drs_file)
                        drs_file = DRS().read(file_path)
                        if drs_file.csk_skeleton is not None:
                            armature_object, bone_list = setup_armature(
                                source_collection, drs_file
                            )
                            break

            # Create structured MeshSet with all states organized hierarchically
            meshset_col, _ = create_meshset_structure(
                parent_collection=mesh_set_grid_collection,
                meshset_index=module_index,
                mesh_states=module.state_based_mesh_set.mesh_states,
                destruction_states=module.state_based_mesh_set.destruction_states if import_debris else [],
                dir_name=dir_name,
                base_name=base_name,
                armature_object=armature_object,
                import_collision_shape=import_collision_shape,
                import_s0_collision_shapes=import_s0_collision_shapes,
            )

            # Store reference to first mesh object for grid mapping
            states_col = None
            for child in meshset_col.children:
                if child.name.startswith("States_Collection"):
                    states_col = child
                    break

            if states_col:
                # Get first mesh from S0 state
                s0_col = None
                for child in states_col.children:
                    if child.name.startswith("S0_Undamaged"):
                        s0_col = child
                        break

                if s0_col:
                    meshes_col = None
                    for child in s0_col.children:
                        if child.name.startswith("Meshes_Collection"):
                            meshes_col = child
                            break

                    if meshes_col and len(meshes_col.objects) > 0:
                        first_mesh = meshes_col.objects[0]
                        module_mesh_map[module_index] = first_mesh.name
                        first_mesh["grid_cell_index"] = module_index

            # Handle IK atlas if needed
            if import_ik_atlas and armature_object is not None and bone_list is not None:
                for mesh_state in module.state_based_mesh_set.mesh_states:
                    if mesh_state.has_files:
                        file_path = os.path.join(dir_name, mesh_state.drs_file)
                        drs_file = DRS().read(file_path)
                        if (
                            drs_file.csk_skeleton is not None
                            and drs_file.animation_set is not None
                        ):
                            import_animation_ik_atlas(
                                armature_object, drs_file.animation_set, bone_list
                            )
                            break  # Only need to do this once per module

        # Increment module index for each module (even if no mesh)
        module_index += 1

    return armature_object, bone_list, module_mesh_map


def load_bmg(
    context: bpy.types.Context,
    filepath="",
    apply_transform=True,
    import_collision_shape=False,
    import_s0_collision_shapes=False,
    import_animation=True,
    smooth_animation=True,
    import_ik_atlas=False,
    use_control_rig=False,
    import_debris=True,
    import_construction=True,
    import_geomesh=False,
    import_obbtree=False,
    limit_obb_depth=5,
    import_bb=False,
):
    """
    Load a BMG (Building Mesh Grid) file into Blender.

    BMG files contain building layouts with modular grids and state-based meshes.
    Each grid cell can contain different mesh states (undamaged, damaged, destroyed)
    and debris physics objects.
    """
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
    persist_meshgrid_blob_on_collection(source_collection, bmg_file)

    # Models share the same Skeleton Files, so we only need to create one Armature and share it across all sub-modules!
    armature_object = None
    bone_list = None

    # Ground Decal
    if bmg_file.mesh_set_grid.ground_decal is not None and bmg_file.mesh_set_grid.ground_decal != "" and bmg_file.mesh_set_grid.ground_decal_length > 0:
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
            # Material Parameters
            setup_material_parameters(mesh_object, ground_decal, mesh_index)
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
        armature_object, bone_list, module_mesh_map = import_mesh_set_grid(
            bmg_file,
            source_collection,
            armature_object,
            dir_name,
            base_name,
            import_debris,
            import_collision_shape,
            import_s0_collision_shapes,
            import_ik_atlas,
        )

        # Update blob with mesh object names
        if module_mesh_map:
            blob_data = source_collection.get(MESHGRID_BLOB_KEY)
            if blob_data:
                try:
                    blob = json.loads(blob_data)
                    cells = blob.get("cells", [])
                    for idx, mesh_name in module_mesh_map.items():
                        if idx < len(cells):
                            cells[idx]["mesh_object_name"] = mesh_name
                    source_collection[MESHGRID_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)
                except Exception as e:
                    print(f"Warning: Failed to update mesh grid blob with mesh names: {e}")

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
                        import_s0_collision_shapes,
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
        and bone_list is not None
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

# region Export Blender Model to BMG


def create_mesh_set_grid():
    _mesh_set_grid = MeshSetGrid()
    # TODO: Calculate grid_width and grid_height based on model boundaries
    # TODO: Check if UUID needs to be generated
    # TODO: Check if we have a ground_decal in blender to use here
    # TODO: Check how effect_gen_debris is used and make it an export option (only nature and fire)
    # TODO: Create the total Cells based on the Mesh Size, and fill the cell(s) with the geiven mesh(es). Check if we need multi-cell setups anyway.
    _total_cells = (_mesh_set_grid.grid_width * 2 + 1) * (_mesh_set_grid.grid_height * 2 + 1)
    for _ in range(_total_cells):
        _mesh_grid_module: MeshGridModule = MeshGridModule()
        # TODO: Logic to select the cell for the model, for now we use center cell (0, 0)
        if _ == _total_cells // 2 + 1:
            _mesh_grid_module.has_mesh_set = 1
            # TODO: Assign the mesh to the cell
            # _mesh_grid_module.state_based_mesh_set =
            # We can break here as we try the 1 cell setup
            break
    # TODO: Create the Locators here, we dont need a separate outside Locator class for buildings it seems
    return _mesh_set_grid


def save_bmg(
    context: bpy.types.Context,
    filepath: str,
    split_mesh_by_uv_islands: bool,
    flip_normals: bool,
    keep_debug_collections: bool,
    model_type: str,
    model_name: str,
    export_all_ska_actions: bool,
    set_model_name_prefix: str,
    auto_fix_quad_faces: bool,
    mip_maps: str = "auto",
):
    """
    Save the current Blender scene as a BMG (Building Mesh Grid) file.

    BMG files contain building layouts with modular grids and state-based meshes.
    Each grid cell can contain different mesh states (undamaged, damaged, destroyed)
    and debris physics objects.
    """
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

    # Copy the AnimationSet blob from the source into the export copy (full fidelity)
    try:
        raw_blob = source_collection.get(ANIM_BLOB_KEY)
        if raw_blob:
            source_collection_copy[ANIM_BLOB_KEY] = raw_blob
    except Exception:
        pass

    # Copy the EffectSet blob from the source into the export copy (full fidelity)
    try:
        raw_effect_blob = source_collection.get(EFFECT_BLOB_KEY)
        if raw_effect_blob:
            source_collection_copy[EFFECT_BLOB_KEY] = raw_effect_blob
    except Exception:
        pass

    # Copy the action resolution map so blob names can still be resolved on the copy
    try:
        raw_action_map = source_collection.get("_drs_action_map")
        if raw_action_map:
            source_collection_copy["_drs_action_map"] = raw_action_map
    except Exception:
        pass

    # TODO: Check if we need to get the Locators in MeshSet or somewhere to be checked here with a blob or later when we create the output

    # We need to run checks for several Meshes (states/debris). Maybe we should make the save_drs function more modular, so we can reuse parts here as we need?

    # === Action name strategy for export =========================================
    export_prefix: str | None
    if set_model_name_prefix == "model_name":
        export_prefix = model_name
    elif set_model_name_prefix == "folder_name":
        export_prefix = os.path.basename(os.path.dirname(filepath))
        # assure there are no spaces
        export_prefix = export_prefix.replace(" ", "_")
    elif set_model_name_prefix == "none":
        export_prefix = ""
    else:  # keep_existing
        export_prefix = None

    # Build name mapping once so AnimationSet, EffectSet and SKA files share consistent naming
    # ska_name_map = build_ska_export_name_map(source_collection_copy, export_prefix)

    # === CREATE DRS STRUCTURE ====================
    folder_path = os.path.dirname(filepath)

    # Create the base layout of our bmg file
    new_bmg_file: BMG = BMG(model_type=model_type)

    # First thing we always need to build is the MeshSetGrid
    mesh_set_grid = create_mesh_set_grid()

    # Now we save the Nodes in Order
    nodes = InformationIndices[model_type]
    for node in nodes:
        if node == "MeshSetGrid":
            new_bmg_file.mesh_set_grid = mesh_set_grid
            new_bmg_file.push_node_infos("MeshSetGrid", new_bmg_file.mesh_set_grid)
        elif node == "AnimationSet":
            pass
        elif node == "AnimationTimings":
            pass
        elif node == "EffectSet":
            pass
        elif node == "CGeoPrimitiveContainer":
            # its an empty
            pass
        elif node == "collisionShape":
            # We take the ones we are given at top level, same as state0 collision shapes
            pass
        # TODO: Check if we should support additional types. Maybe they are not used/wrongly exported in existing models

    new_bmg_file.update_offsets()

    # === SAVE THE BMG FILE ====================================================
    try:
        new_bmg_file.save(os.path.join(folder_path, model_name + ".drs"))
    except ExportError as e:
        logger.log(str(e), "Export Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)
    except Exception as e:
        logger.log(f"Unexpected error during save: {e}", "Export Error", "ERROR")
        return abort(keep_debug_collections, source_collection_copy)

    # === Export of SKA Actions ==============================================

    # === CLEANUP & FINALIZE ===================================================
    if not keep_debug_collections:
        bpy.data.collections.remove(source_collection_copy)

    logger.log("Export completed successfully.", "Export Complete", "INFO")
    logger.display()

    # Cleanup variables
    # ska_name_map = None
    mesh_set_grid = None
    new_bmg_file = None
    source_collection_copy = None

    return {"FINISHED"}

# endregion
