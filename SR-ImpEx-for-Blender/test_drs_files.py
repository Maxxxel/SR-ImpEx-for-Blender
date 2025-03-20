# import os
# import json
# from collections import defaultdict
# from .drs_definitions_copy_for_tests import DRS

# # Known bit flags to filter out (as integers)
# known_flags_set = {
#     1,  # EnableAlphaTest: 1 << 0
#     1 << 1,  # DecalMode: 1 << 1
#     1 << 16,  # UseParameterMap: 1 << 16
#     1 << 17,  # UseNormalMap: 1 << 17
#     1 << 18,  # UseEnvironmentMap: 1 << 18
#     1 << 19,  # DisableReceiveShadows: 1 << 19
#     1 << 20,  # EnableSHLighting: 1 << 20
# }

# # Compute the combined known mask for convenience.
# known_mask = 0
# for flag in known_flags_set:
#     known_mask |= flag

# # Dictionary to aggregate unknown bit flags.
# aggregated_by_bit = {}

# # Set your files directory.
# files_dir = r"D:\Games\Skylords Reborn\Mods\Unpack\bf1\gfx"
# files = []
# for root, dirs, file_list in os.walk(files_dir):
#     for f in file_list:
#         if f.endswith(".drs") and "effects" not in root and "terrain" not in root:
#             files.append(os.path.relpath(os.path.join(root, f), files_dir))

# total_files = len(files)
# print(f"Found {total_files} files to process.")

# # Process each file only once.
# for i, file in enumerate(files, start=1):
#     file_path = os.path.join(files_dir, file)
#     try:
#         drs_file = DRS().read(file_path)
#         # Process only if there's a CDSPMesh file.
#         if hasattr(drs_file, "cdsp_mesh_file") and drs_file.cdsp_mesh_file:
#             for mesh in drs_file.cdsp_mesh_file.meshes:
#                 bool_param = mesh.bool_parameter
#                 unsigned_bool_param = bool_param & 0xFFFFFFFF
#                 unknown_value = unsigned_bool_param & ~known_mask
#                 # Calculate the unknown part by masking out the known flags.
#                 # unknown_value = bool_param & ~known_mask
#                 if unknown_value:
#                     # Break the composite unknown_value into individual power-of-two flags.
#                     for bit_position in range(unknown_value.bit_length()):
#                         if (unknown_value >> bit_position) & 1:
#                             bit_flag = 1 << bit_position
#                             # If by chance this bit is part of known flags, skip it.
#                             if bit_flag in known_flags_set:
#                                 continue
#                             # Initialize the aggregate for this flag if needed.
#                             if bit_flag not in aggregated_by_bit:
#                                 aggregated_by_bit[bit_flag] = {
#                                     "bit_flag_decimal": bit_flag,
#                                     "bit_flag_binary": format(bit_flag, "b"),
#                                     "count": 0,
#                                     "files": [],
#                                     "categories": defaultdict(int),
#                                 }
#                             aggregated_by_bit[bit_flag]["count"] += 1
#                             aggregated_by_bit[bit_flag]["files"].append(file)
#                             # Derive category from the first folder in the relative path.
#                             category = os.path.normpath(file).split(os.sep)[0]
#                             aggregated_by_bit[bit_flag]["categories"][category] += 1
#     except Exception as e:
#         # Skip files with errors; optionally, log e.
#         pass
#     print(f"Progress: {i}/{total_files} ({(i/total_files)*100:.2f}%)", end="\r")

# # Transform the aggregated data into a sorted list.
# aggregated_list = []
# for bit, data in aggregated_by_bit.items():
#     aggregated_list.append(
#         {
#             "bit_flag_decimal": data["bit_flag_decimal"],
#             "bit_flag_binary": data["bit_flag_binary"],
#             "count": data["count"],
#             "files": data["files"],
#             "categories": dict(data["categories"]),
#         }
#     )

# # Sort the list by the number of files (most frequent first).
# aggregated_list.sort(key=lambda x: x["count"], reverse=True)

# # Save the result to a JSON file.
# output_file = "aggregated_by_unique_bit_flags.json"
# with open(output_file, "w") as f:
#     json.dump(aggregated_list, f, indent=4)

# print(f"\nAggregated unique unknown bit flags have been saved to {output_file}")
pass
