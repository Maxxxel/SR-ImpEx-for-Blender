## Quick context for AI coding agents working on SR-ImpEx-for-Blender

This file gives targeted, actionable knowledge to help an AI coding agent be productive immediately in this repository.

Keep this short and practical — reference code locations when possible.

### Big picture
- The repo is a Blender-focused importer/exporter for a game's DRS/BMG model formats. The main Python package is `sr_impex/`.
- `sr_impex/drs_utility.py` is the largest single file — it implements both import and export flows for model, mesh, material and animation data. Treat it as the primary integration surface.
- Other important modules: `sr_impex/file_io.py` (format parsing), `sr_impex/drs_material.py` (material builder), `sr_impex/drs_resolvers.py` and `sr_impex/pak_indexer.py`. Use these for format semantics and I/O patterns.
- There's a small tooling surface: `create_release_package.py` (packaging), `sr_impex/resources` (third-party or large binary resources, e.g. `vgmstream`).

### Key conventions and patterns (use these verbatim)
- Collection / object naming conventions used by the addon (search and match exactly):
  - DRS model container collections are named with prefix `DRSModel_<basename>`
  - Meshes live in `Meshes_Collection` under the model collection
  - Collision shapes live in `CollisionShapes_Collection` and subcollections `Boxes_Collection`, `Spheres_Collection`, `Cylinders_Collection`
  - Debug assets go into `Debug_Collection`
- Texture file suffixes used across importer/exporter and tooling:
  - Color: `_col`  (see `set_color_map` in `drs_utility.py`)
  - Normal: `_nor`  (see `set_normal_map`)
  - Parameter pack: `_par` (metallic/roughness/emission/flu mask — see `set_metallic_roughness_emission_map`)
  - Flu map: `_flu`
- Material/node discovery patterns:
  - The project relies on labeled image nodes and a custom 'DRS Shader' node group; node labels like `Separate Metallic`, `Separate Roughness`, `Parameter Map (_par)`, `Flu Map Layer 1` are used to locate images.
  - Many routines do "find-by-label" — prefer adding or updating tests that exercise node-tree lookup functions (`_find_by_label`, `_first_image_upstream`, `_find_drs_bsdf`).
- Numeric constants are meaningful: texture records use integer identifiers (for example 1684432499 for color, 1936745324 for _par). Don't change them without checking importer expectations.

### Developer workflows (how to run / debug locally)
- Run the addon inside Blender. Typical dev flow uses the VS Code Blender Development extension and launching Blender with the project as the script target. The project has been run with Blender 4.x in this workspace.
- Packaging: `python.exe .\create_release_package.py` (Windows Powershell) — this script is present at repo root and used to assemble release artifacts.
- Use the Blender bundled Python to execute addon logic (bpy is only available inside Blender). Unit tests are not present; for functional checks you must run Blender and exercise importer/exporter from the UI or via short driver scripts run inside Blender.

### Integration and external dependencies
- The addon depends on Blender's Python + `bpy`. Native modules used by the code include `numpy` (used actively in `drs_utility.py` for PCA/OBB computations). Ensure numpy is available to the Blender Python environment when executing scripts that use those functions.
- Large third-party assets/tools live under `sr_impex/resources` (e.g. `vgmstream`) — these are integration points for audio handling and binary helpers.

### Code architecture notes (how data flows)
- Import flow (high-level): read DRS/BMG -> create `DRSModel_<name>` collection -> create armature (skeleton) -> create `Meshes_Collection` and mesh objects -> create/link materials -> optionally import collision shapes, OBB tree, cgeomesh, and animation/IK atlas. See `load_drs()` in `drs_utility.py`.
- Export flow (high-level): gather collections/meshes -> create unified mesh -> convert to CDspMeshFile/CollisionShape/OBB tree using helpers such as `create_unified_mesh`, `create_cdsp_mesh_file`, `create_cgeo_obb_tree`.
- Material export expects specific node graph outputs. `set_metallic_roughness_emission_map` packs channels from up to four sources into a `_par` PNG — match the same packing when modifying exporter.

### Typical edit patterns and low-risk areas to change
- Small bugfixes inside helper utilities (`_find_by_label`, `_first_image_upstream`, `get_converted_texture`) are generally safe and well-contained. Add unit-style scripts for these functions if you want regression checks.
- Avoid refactoring large blocks of `drs_utility.py` all at once. Prefer extracting small helpers and running manual Blender checks: the file contains many cross-cutting responsibilities tied to Blender runtime state.

### Files to open first (priority)
1. `sr_impex/drs_utility.py` — importer/exporter, node conventions and naming (primary).
2. `sr_impex/file_io.py` — format parsing/serialization helpers.
3. `sr_impex/drs_material.py` — material node builder (labels and nodes used by exporter/importer).
4. `create_release_package.py` — packaging workflow.
5. `sr_impex/message_logger.py` — logging pattern used across the addon.

### When you need more context or permission
- If you plan to change numeric identifiers, texture packing, or on-disk file layout, confirm with the repo owner — importer expects exact identifiers and packing.
- If you need to run or install Python packages into Blender's Python (e.g. numpy), mention the Blender version and OS so maintainers can supply exact install steps.

If anything in this summary is unclear or you want a shorter vs longer version, tell me which parts to expand (examples, code pointers, or a checklist for onboarding new contributors).
