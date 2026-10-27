# Building Creation Guide

Buildings add a mesh grid, mesh states, and referenced resources to the ordinary DRS mesh/material workflow. A `.bmg` is not simply a static `.drs` with a different filename.

Start with the [Object Creation Guide](object_creation_guide.md) for mesh, material, collision, and GO basics. Use the [Unit Creation Guide](unit_creation_buide.md) for skeletons and SKA actions when the building is animated.

> **Current support boundary:** Building import, state visibility, and mesh-grid editing are available. Full building export is still incomplete: the current BMG writer does not assemble the complete state/resource graph, and several animation, effect, and collision export branches remain unimplemented. The export menu and a successful completion message do **not** guarantee a game-ready building. Work on copies and retain the original BMG and its referenced assets.

## 1. Start from an Existing Building

For building work, importing a comparable building is more useful than starting with an empty object scene. It supplies the mesh-state relationships, resource names, and grid metadata that the simple scene generator does not create.

1. Keep the source `.bmg`, its referenced state `.drs` files, textures, debris XML, and any `.ska` files together in their expected resource layout.
2. Choose **File > Import > Battleforge (.drs/.bmg)** and select the building.
3. Review the import options before confirming. **Clear Scene** is on by default; disable it if you need to keep the current scene.
4. Save the imported setup to a new `.blend` file before editing it.

Useful options:

| Option | Purpose |
|---|---|
| `Apply Transform` | Controls the import's GO display-axis conversion. Use the same setting when comparing two imports. |
| `Import Collision Shape` | Imports building-level collision and eligible state collision data. |
| `Import S0 Collision Shapes` | Also imports collision from undamaged state DRS files; off by default because building-level collision can already represent those states. |
| `Import Debris` | Imports the referenced debris setup where available. |
| `Import Construction` | Imports referenced construction pieces. |
| `Import Animation` | Enables animation import for a rigged building. |

A missing referenced file is a resource problem, not something that can be fixed by changing a collection's name.

## 2. Understand the Imported Structure

A typical imported building contains the following collection structure. Optional resources and Blender numeric suffixes vary by asset:

```text
DRSModel_<building>
├── GameOrientation                  (Empty object)
├── GroundDecal_Collection            (optional)
├── CollisionShapes_Collection        (building-level collision, if present)
│   ├── Boxes_Collection
│   ├── Spheres_Collection
│   └── Cylinders_Collection
├── Armature_Collection              (if the building is rigged)
├── SLocators_Collection              (construction helpers, if imported)
└── MeshSetGrid_0
    ├── MeshSet_0
    │   ├── Active_State_MeshSet_0    (Empty marker)
    │   └── States_Collection_0
    │       ├── S0_Undamaged
    │       │   └── Meshes_Collection
    │       ├── S2_Damaged
    │       │   ├── Meshes_Collection
    │       │   └── CollisionShapes_Collection (when imported)
    │       └── Debris_Collection
    │           ├── S2_Debris
    │           └── S3_Debris
    └── MeshSet_1 ...
```

A state can contain its own collision subcollections. The grid references individual mesh sets, and each mesh set groups its related states. Do not flatten all state meshes into the root or combine every state into one ordinary object export collection.

### GO and parenting

> **Good practice:** Use the building's GO coordinate convention consistently for new meshes, collision shapes, and non-bone helpers. Parenting a new primitive before fitting it is convenient, but not a required modeling order; correcting and applying a mesh rotation after parenting is also a supported workflow.

Collection nesting is not object parenting. Inspect the actual parent relationship when adding a mesh to an imported state. Keep existing armature and bone-attached relationships intact rather than parenting every object directly to GO. Do not reset or apply GO itself to compensate for one misaligned state.

The mesh-grid visualization expects the model's GO helper to exist. Keeping that helper for the editor is different from requiring every mesh to be parented before modeling.

## 3. Inspect States in the BMG Editor

Open the 3D Viewport sidebar (`N`) and select **BMG Editor > BMG Mesh State Editor**.

| Button | What to inspect |
|---|---|
| `Show undamaged` | The `S0_Undamaged` meshes. |
| `Show damaged` | The `S2_Damaged` meshes on their own. |
| `Show damaged + Debris (should look undamaged)` | Damaged geometry together with `S2_Debris`; useful for checking how pieces fit. |
| `Show Debris` | The imported debris collections. |
| `Show All Stages` | All state collections together for comparison. Overlapping geometry is expected in this view. |

These controls switch visibility; they do not create missing states, author debris physics, or define gameplay transitions. The **Switch All States** controls operate on mesh sets across the scene, so take care when several buildings are loaded.

Use **Show Collision Shapes** and **Show SLocators** to reduce clutter. Hiding a helper for editing is not a substitute for removing unwanted resource references from an export setup.

## 4. Inspect or Fit a Mesh Grid

Make the intended `DRSModel_...` root active before using the grid controls.

- **Show Mesh Grid** toggles the visualization.
- **Create Grid** fits new grid metadata to eligible undamaged-state meshes. It uses a fixed cell size of `2.0` and currently creates a square grid with an odd number of cells along each axis.
- **Rotation** changes the editor's grid/model orientation in degrees. It is not a reason to rotate GO manually.
- **Center Pivot At Origin (0,0,0)** chooses whether the grid is centered at the origin or the detected model center.
- **Remove Grid** removes stored grid data and its visualization, not the building's visible meshes.

> Save before recreating a grid. **Create Grid** rebuilds metadata and resets the grid/model rotation to zero before fitting; it is not a harmless visibility toggle. Review the result instead of assuming an imported layout or cell assignment was preserved.

The fitting code looks for meshes inside the undamaged-state `Meshes_Collection` hierarchy. An ordinary object scene with no `S0_Undamaged` meshes is not automatically a fully configured building just because the grid button is available. Empty or unexpectedly small grids are a reason to check the hierarchy and dimensions first.

A visible grid is an authoring aid, not proof that the complete BMG state graph can currently be exported.

## 5. Edit Materials, Collision, and Optional Resources

### Visible meshes and materials

Edit each state's render meshes in its own `Meshes_Collection`. Apply the same UV, triangulation, material, and vertex-budget checks described in the [Object Creation Guide](object_creation_guide.md#4-model-the-object). Use the [Advanced Shading Guide](advanced_shading_guide.md) for packed parameters, wind, refraction, and environment maps.

### Collision

Keep building-level collision separate from damage-state collision. A damaged state may need a different approximation than the undamaged building.

When adding a shape, use its state's matching box/sphere/cylinder collection. As for visible meshes, using the correct model's GO is good practice; fitting the shape first and correcting its rotation after parenting is also possible. Preserve the primitive's geometry: boxes remain rectangular, spheres remain round, and cylinders remain circular and capped. See [Object Creation Guide, step 8](object_creation_guide.md#8-create-collision-shapes).

### Ground decal

`GroundDecal_Collection` is imported when the BMG references a ground decal DRS. It is optional and distinct from both building collision and the grid visualization. A new mesh placed in this collection is not automatically wired into a complete exported building resource graph.

### Construction pieces and debris

Preserve their referenced assets and the imported relationships. A construction helper or debris mesh is not equivalent to a finished building state. The current UI can inspect these resources, but it does not replace an external debris/resource authoring workflow.

## 6. Animated Buildings and Visual Hooks

Use the building's deform skeleton, skin weights, and SKA actions as described in the [Unit Creation Guide](unit_creation_buide.md). A building is not limited to one idle animation: relevant assets may use spawn, attack, casting, channeling, or turret-related animation modes.

Choose only the modes required by the target asset. A long list of available animation types is not a checklist that every building needs to implement. See the [Advanced Abilities Guide](advanced_abilities_guide.md) for action/marker relationships and the [Advanced Effects Guide](advanced_effects_guide.md) for sound metadata.

Non-bone locators use the model's coordinate convention, while bone locators follow the armature. Use the [Advanced Locators Guide](advanced_locators_guide.md) rather than manually forcing all helpers under GO.

## 7. Save, Export Cautiously, and Validate

The menu **File > Export > Battleforge Building (.bmg)** offers static and animated building model types, mesh options, and SKA naming controls. Those UI options do not mean every corresponding BMG export branch is complete.

For now:

1. Save the edited `.blend` file as the authoritative working copy.
2. Keep the source BMG and every referenced resource unchanged in a separate location.
3. If testing BMG export, use a disposable folder and inspect the actual files produced. The current save path can produce a `.drs`-suffixed file despite the BMG menu; renaming it alone does not implement the missing building data.
4. If exporting a component DRS separately, prepare a proper standalone `DRSModel_...` hierarchy and follow the object/unit export guide. A nested state collection is not automatically a standalone export root.
5. Re-import tests into a separate scene, compare matching states with the same display-axis settings, and verify resources and behavior in game before distributing anything.

### Building checklist

- [ ] The original BMG and referenced DRS/XML/DDS/SKA files are backed up.
- [ ] Each mesh remains in the correct mesh set and state.
- [ ] New geometry follows the intended GO convention without breaking existing rig/bone parents.
- [ ] Undamaged, damaged, and debris views were checked separately.
- [ ] Building-level and state-level collision were not accidentally confused or duplicated.
- [ ] Grid rotation, pivot, and cell layout were checked after any rebuild.
- [ ] Export limitations are understood; no completion message was treated as proof of a full building round trip.

## Related Guides

- [Object Creation Guide](object_creation_guide.md)
- [Unit Creation Guide](unit_creation_buide.md)
- [Advanced Shading Guide](advanced_shading_guide.md)
- [Advanced Locators Guide](advanced_locators_guide.md)
- [Advanced Abilities Guide](advanced_abilities_guide.md)
- [Advanced Effects Guide](advanced_effects_guide.md)
