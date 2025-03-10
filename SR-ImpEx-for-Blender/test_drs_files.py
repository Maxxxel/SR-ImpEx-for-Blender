import os
from .drs_definitions_copy_for_tests import DRS

# Collsion Shapes -> ALL
# Collision shapes found in greenland\architecture\object_greenland_head_l_003.drs
# Collision shapes found in greenland\architecture\object_greenland_head_xl_002.drs

# Debug the file by loading it, write a main
if __name__ == "__main__":
    # Load ALL DRS files in given directory
    # Create an array sorted by the amount of bones
    # check how many duplicate bones the models have and create a ranking, like: only uniques, 2 duplicates, etc. with a counter
    files_dir = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx\\objects"
    # Load all DRS files in the subdirectories, not main
    files = []
    for root, dirs, file in os.walk(files_dir):
        for f in file:
            if f.endswith(".drs"):
                # Append full path
                files.append(os.path.relpath(os.path.join(root, f), files_dir))

    for file in files:
        _dir = os.path.dirname(file)
        # print(f"Loading: {file} +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        try:
            drs_file: "DRS" = DRS().read(os.path.join(files_dir, file))

            # Find files with collisionShapes
            if drs_file.collision_shape is not None:
                box_count = drs_file.collision_shape.box_count
                sphere_count = drs_file.collision_shape.sphere_count
                cylinder_count = drs_file.collision_shape.cylinder_count

                if box_count > 0 and sphere_count > 0 and cylinder_count > 0:
                    print(f"Collision shapes found in {file}")

            # for module in bmg_file.mesh_set_grid.mesh_modules:
            #     if module.has_mesh_set:
            #         meshes: DRS = []
            #         for mesh_set in module.state_based_mesh_set.mesh_states:
            #             state = mesh_set.state_num
            #             if mesh_set.has_files:
            #                 drs_file: DRS = DRS().read(
            #                     os.path.join(files_dir, _dir, mesh_set.drs_file)
            #                 )
            #                 meshes.append(drs_file)

            #         # Comapre CSKskeletons of the meshes
            #         for i, mesh in enumerate(meshes):
            #             mesh: DRS = meshes[i]
            #             if i == 0:
            #                 continue
            #             next_mesh: DRS = meshes[i - 1]
            #             if mesh.csk_skeleton is None or next_mesh.csk_skeleton is None:
            #                 print(f"No skeleton found in {file}")
            #                 continue
            #             if (
            #                 mesh.csk_skeleton.bone_count
            #                 != next_mesh.csk_skeleton.bone_count
            #             ):
            #                 print(f"Bone count mismatch in {file}")
            #                 continue
            #             for bone in mesh.csk_skeleton.bones:
            #                 # Check if the same bone name or bone Id exists in the other mesh
            #                 if bone.name not in [
            #                     b.name for b in next_mesh.csk_skeleton.bones
            #                 ]:
            #                     print(f"Bone name mismatch in {file}")
            #                     continue
            #                 if bone.identifier not in [
            #                     b.identifier for b in next_mesh.csk_skeleton.bones
            #                 ]:
            #                     print(f"Bone identifier mismatch in {file}")
            #                     continue

        except Exception as e:  # pylint: disable=broad-except
            print(f"Error loading {file}: {e}. Type: {type(e)}")
            continue

    print("DONE")
