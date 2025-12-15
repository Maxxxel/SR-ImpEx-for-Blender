## Quick context for AI coding agents working on SR-ImpEx-for-Blender

Targeted, actionable notes to be productive in this repo fast. Keep changes minimal and consistent with existing Blender add-on patterns.

### Big picture
- This is a Blender 4.x add-on to import/export game formats (DRS/BMG + related animation data like SKA).
- The main package is `sr_impex/` with three main surfaces:
  - `sr_impex/utilities/`: format logic + higher-level import/export utilities (largest integration surface).
  - `sr_impex/core/`: binary reading/writing, logging, profiling.
  - `sr_impex/blender/`: Blender-specific operators/UI/helpers and material building.
- Primary integration file: `sr_impex/utilities/drs_utility.py` (import/export, meshes, materials, collision, OBB tree helpers).

### Key conventions (match exactly)
- Collection naming used by the add-on:
  - DRS model container collections: `DRSModel_<basename>`
  - Meshes: `Meshes_Collection` under the model collection
  - Collision: `CollisionShapes_Collection` with subcollections `Boxes_Collection`, `Spheres_Collection`, `Cylinders_Collection`
  - Debug content: `Debug_Collection`
  - Armature collections typically contain `Armature` in the name (see `sr_impex/utilities/ska_utility.py`).
- Texture suffix conventions:
  - Color: `_col`
  - Normal: `_nor`
  - Packed parameters: `_par` (metallic/roughness/emission/flu mask)
  - Flu map: `_flu`
  - See mapping/packing helpers in `sr_impex/utilities/drs_utility.py`.
- Material/node discovery:
  - The add-on relies on a custom “DRS Shader” node group and “find-by-label” logic.
  - Keep node labels stable (examples: `Separate Metallic`, `Separate Roughness`, `Parameter Map (_par)`, `Flu Map Layer 1`).
- Numeric IDs/constants in file formats matter. Don’t change texture record IDs/packing without confirming importer expectations.

### Where things live (open these first)
1. `sr_impex/utilities/drs_utility.py` — main import/export integration surface.
2. `sr_impex/core/file_io.py` — binary parsing/serialization primitives.
3. `sr_impex/blender/drs_material.py` — material node construction and conventions.
4. `sr_impex/utilities/drs_resolvers.py` — resolver logic used by import/export.
5. `sr_impex/utilities/ska_utility.py` — animation export/import helpers (SKA).
6. `sr_impex/blender/editors/` — UI panels/editors/operators (debug tooling lives here too).

### Developer workflow (Windows/Blender)
- Run inside Blender (bpy is only available there). This repo is typically developed using the VS Code “Blender Development” extension.
- Packaging/release assembly: `python.exe .\create_release_package.py`.
- There are no conventional unit tests; validate changes by running Blender and exercising the UI/operators.

### Blender API gotchas (important)
- Avoid `bpy.ops` in tight loops; prefer `bpy.data.*` + direct datablock edits for speed and stability.
- Don’t mutate Blender datablocks inside property update callbacks in a way that reassigns the same property (can recurse/crash). If you must touch scene data from an update callback, defer with `bpy.app.timers.register`.
- When iterating collections/objects that you also hide/link/unlink, collect targets first to avoid iterator invalidation.

### External dependencies / resources
- Runs on Blender’s Python (`bpy`, `mathutils`). Some utilities use `numpy` (ensure it’s available in the Blender Python env when needed).
- Large third-party helpers live in `sr_impex/resources/` (e.g. `vgmstream`). Treat as integration points; avoid renaming/moving.

### When to ask before changing
- File-format identifiers, texture packing, on-disk layouts, or shader graph conventions.
- Anything that changes naming conventions for collections/objects/material nodes.
