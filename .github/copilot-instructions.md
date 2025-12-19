## Quick context for AI coding agents working on SR-ImpEx-for-Blender

Targeted notes so you can contribute without breaking importer/exporter expectations. Keep edits minimal and aligned with existing add-on conventions.

### Scope and surfaces
- Blender 4.x add-on that imports/exports DRS/BMG formats plus SKA animation data.
- Core areas:
  - `sr_impex/utilities/`: higher-level import/export flows and format helpers (biggest surface).
  - `sr_impex/core/`: binary IO primitives, logging, profiling.
  - `sr_impex/blender/`: Blender operators, UI, materials.
- Primary integration point: `sr_impex/utilities/drs_utility.py` (meshes, materials, collision, OBB, packing helpers).

### Non-negotiable conventions
- Collection names: `DRSModel_<basename>` root; `Meshes_Collection`; `CollisionShapes_Collection` with `Boxes_Collection`/`Spheres_Collection`/`Cylinders_Collection`; `Debug_Collection`; armature collections contain `Armature` (see `ska_utility`).
- Texture suffixes: `_col` color, `_nor` normal, `_par` packed params (metal/roughness/emission/flu mask), `_flu` flu. Mapping helpers live in `drs_utility`.
- Materials: relies on “DRS Shader” node group + label-based lookup. Keep labels like `Separate Metallic`, `Separate Roughness`, `Parameter Map (_par)`, `Flu Map Layer 1` unchanged.
- File-format IDs/constants and texture packing layouts must stay stable unless explicitly approved.

### Key files to open first
1. `sr_impex/utilities/drs_utility.py` — main import/export integration.
2. `sr_impex/core/file_io.py` — binary read/write primitives.
3. `sr_impex/blender/drs_material.py` — material graph construction.
4. `sr_impex/utilities/drs_resolvers.py` — resolver logic for resources.
5. `sr_impex/utilities/ska_utility.py` — SKA animation import/export.
6. `sr_impex/blender/editors/` — UI panels/operators and debug helpers.

### Workflow expectations
- Develop/test inside Blender; `bpy` is not available in plain Python. VS Code “Blender Development” extension is typical.
- Release packaging: `python.exe .\create_release_package.py`.
- No automated tests; validate manually via Blender UI/operators.

### Blender API hygiene
- Avoid `bpy.ops` in hot paths; prefer `bpy.data` and direct datablock edits.
- Do not reassign properties inside update callbacks; defer with `bpy.app.timers.register` if scene edits are needed.
- When linking/unlinking or hiding objects/collections during iteration, collect targets first to avoid invalidation.

### External bits
- Runs on Blender Python (`bpy`, `mathutils`); some paths use `numpy` (ensure availability in Blender env).
- Third-party payloads under `sr_impex/resources/` (e.g., `vgmstream`); treat as fixed integration points—do not move/rename.

### Ask before changing
- File-format identifiers, binary layouts, texture packing or shader graph conventions.
- Naming conventions for collections, objects, materials, or nodes.
