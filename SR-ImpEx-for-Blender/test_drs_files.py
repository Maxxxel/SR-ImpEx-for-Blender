# import os
# import json
# from collections import defaultdict
# from .drs_definitions_copy_for_tests import DRS

# # Set your files directory.
# files_dir = r"D:\Games\Skylords Reborn\Mods\Unpack\bf1\gfx"
# files = []
# for root, dirs, file_list in os.walk(files_dir):
#     for f in file_list:
#         if f.endswith(".drs") and "effects" not in root and "terrain" not in root:
#             files.append(os.path.relpath(os.path.join(root, f), files_dir))

# total_files = len(files)
# print(f"Found {total_files} files to process.")

# bones_list = []

# # Process each file only once.
# for i, file in enumerate(files, start=1):
#     file_path = os.path.join(files_dir, file)
#     try:
#         drs_file = DRS().read(file_path)
#         # Process only if there's a Skeleton file.
#         if hasattr(drs_file, "csk_skeleton") and drs_file.csk_skeleton is not None:
#             # Process the file here.
#             for bone in drs_file.csk_skeleton.bones:
#                 bones_list.append(
#                     {
#                         "name": bone.name,
#                         "id": bone.identifier,
#                         "version": bone.version,
#                     }
#                 )
#     except Exception as e:
#         print(f"Error processing {file}: {e}")
#     finally:
#         # Clear print statement.
#         print("\033[A\033[K", end="")
#         # Prince % done.
#         print(f"{i/total_files*100:.2f}% done.")

# # Create a josnon file with unique bone_name: version pairs.
# bone_versions = {}
# for bone in bones_list:
#     if bone["name"] not in bone_versions:
#         bone_versions[bone["name"]] = bone["version"]

# with open("bone_versions.json", "w") as f:
#     json.dump(bone_versions, f, indent=4)

# print("bone_versions.json created.")
