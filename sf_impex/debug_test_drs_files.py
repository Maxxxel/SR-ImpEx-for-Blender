# import os
# from debug_drs_definitions_copy_for_tests import DRS

# # --- CONFIG -------------------------------------------------------------------
# FILES_DIR = r"D:\Games\Skylords Reborn\Mods\Unpack\bf1\gfx"


# def collect_drs_files(root_dir: str) -> list[str]:
#     """
#     Walk the tree with pruning and return relative .drs file paths that match filters.
#     """
#     exclude_dirs = {
#         "buildings",
#         "editor",
#         "effects",
#         "fortification",
#         "generator",
#         "monument",
#         "movies",
#         "objects",
#         "terrain",
#         "ui",
#         # "units",
#         "vis",
#         "meshes",
#     }

#     drs_files: list[str] = []
#     for root, dirs, files in os.walk(root_dir, topdown=True):
#         # Prune excluded directories in-place
#         dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]

#         for f in files:
#             if f.lower().endswith(".drs"):
#                 rel = os.path.relpath(os.path.join(root, f), root_dir)
#                 drs_files.append(rel)
#     return drs_files


# def main():
#     files = collect_drs_files(FILES_DIR)
#     print(f"Found {len(files)} files to process.")

#     for rel in files:
#         # Keep the relative path stem as the unit_name (matches your original behavior)
#         unit_name = os.path.splitext(rel)[0]
#         file_path = os.path.join(FILES_DIR, rel)

#         try:
#             drs_file = DRS().read(file_path)

#             if drs_file.animation_set is None:
#                 continue

#             for mode_key in drs_file.animation_set.mode_animation_keys:
#                 if mode_key.mode > 1:
#                     print(f"Unit: {unit_name}, Mode: {mode_key.mode}")

#         except Exception as e:
#             # print(f"Failed to parse {unit_name}: {e}")
#             pass


# if __name__ == "__main__":
#     main()
