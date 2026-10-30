# Building Creation Guide

Buildings add a mesh grid, mesh states, and referenced resources to the ordinary DRS mesh/material workflow. A `.bmg` is not simply a static `.drs` with a different filename.

Start with the [Object Creation Guide](object_creation_guide.md) for mesh, material, collision, and GO basics. Use the [Unit Creation Guide](unit_creation_buide.md) for skeletons and SKA actions when the building is animated.

> **Current support:** Blender 5 can export new static buildings and edited imported buildings, including skinned state resources and SKA actions. Export rebuilds hidden states too, preserves source metadata, and validates output in a temporary folder. New output still needs Map Editor/in-game validation. Debris XML and construction BMS graphs remain separate authoring work; their preview meshes are not rebuilt automatically.

For skinned states, export operates on temporary mesh copies, ignores non-bone
modifier groups, keeps the strongest four bone weights and normalizes them.
Unweighted vertices stop a building-state export; assign appropriate deform
weights and retry. Warnings about coincident positions with different weights
need review as described in the [Unit Creation Guide](unit_creation_buide.md).

To start a **new static building**, select its render meshes in Object Mode and choose **N > BMG Editor > Building Authoring & Export > Building from Selected Meshes**. This moves them into the central cell's undamaged S0 state. Use **Create / Upgrade Selected Material** for ordinary Blender materials, then configure the DRS material controls. New skinned buildings should start from a compatible animated BMG so the skeleton, animations and state relationships are available.

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

Open the 3D Viewport sidebar (`N`) and select **BMG Editor > BMG State Editor**.

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

When adding a shape, use its state's matching box/sphere/cylinder collection. As for visible meshes, using the correct model's GO is good practice; fitting the shape first and correcting its rotation after parenting is also possible. Preserve the primitive's geometry: boxes remain rectangular, spheres remain round, and cylinders remain circular and capped. See [Add collision shapes](object_creation_guide.md#6-add-collision-shapes).

### Ground decal

`GroundDecal_Collection` is imported when the BMG references a ground decal DRS. It is optional and distinct from both building collision and the grid visualization. Its render meshes are rebuilt into `<building>_ground.drs`; the BMG reference and textures are updated automatically.

### Construction pieces and debris

Preserve their referenced assets and imported relationships. A construction helper or debris mesh is not equivalent to a finished building state. Export preserves their references and copies locally resolvable dependencies, but does not replace an external debris/resource authoring workflow.

## 6. Animated Buildings and Visual Hooks

Use the building's deform skeleton, skin weights, and SKA actions as described in the [Unit Creation Guide](unit_creation_buide.md). A building is not limited to one idle animation: relevant assets may use spawn, attack, casting, channeling, or turret-related animation modes.

Choose only the modes required by the target asset. A long list of available animation types is not a checklist that every building needs to implement. See the [Advanced Abilities Guide](advanced_abilities_guide.md) for action/marker relationships and the [Advanced Effects Guide](advanced_effects_guide.md) for sound metadata.

Non-bone locators use the model's coordinate convention, while bone locators follow the armature. Use the [Advanced Locators Guide](advanced_locators_guide.md) rather than manually forcing all helpers under GO.

## 7. Author States and Grid Settings

Open **N > BMG Editor > Building Authoring & Export**. Selecting a mesh or nested state collection identifies its building; the Outliner does not need to be focused on the root.

| Control | Behavior |
|---|---|
| Building Grid Settings | Edit name, square half extent, spacing, yaw, pivot mode, ground resource and building effects. |
| State from Selected Meshes | Copy selected render meshes into the chosen cell and state ID. Common IDs are 0 intact and 2 damaged. |
| Show | Display one state for that cell, including custom numeric state IDs. |
| Effects | Edit persistent state FX and the effect triggered on entering that state. |
| X beside a state | Remove that state from the exported grid and unlink its meshes from the building. Transition effects are separate records and are retained. |
| Export Building Package | Rebuild the BMG, editable state DRS resources, ground decal and textures. |

Grid half extent 1 means **3 x 3** cells, 2 means **5 x 5**, and so on. Resizing preserves cell coordinates around the origin and updates state collection indices. Shrinking across a populated cell is rejected. Grid display yaw is removed from state geometry during export and written once in MeshSetGrid. Preview rotation preserves artist object transforms.

Each render mesh needs a UV map and a material. Multiple material slots become separate CDsp mesh records. Triangulation and UV/normal discontinuity splitting run on temporary copies. The engine's vertex budget still applies after splitting. Apply modeling modifiers before export; the add-on's WindEffect preview and Armature modifier are handled separately. Material types, flags, textures and parameter lists use the ordinary DRS workflow; Default flow still uses the parameter map's **B channel as its mask**.

Keep each cell's state IDs unique. State IDs and cell indices are collection properties, independent of Blender's automatic numeric name suffixes. Deleting a collection does not necessarily delete its preserved source record: source-only records intentionally survive. Removing source-only records requires an explicit metadata edit.

## Preview Damage and Destruction

1. Set your **Skylords Reborn Folder** in the add-on preferences.
2. Select the building and open **BMG Editor → Building Editor**.
3. Click **Build Damage Preview**, then drag **Damage** from 0% to 100%.
4. Press **Space** to see debris fall and effects play. **Replay Transition** restarts them at the current frame.

Damage changes cell meshes, their state effects and transition effects, and the building's scratch shading. At 100%, the preview selects the destroyed state and plays the building crush effect. A destroyed state can have no replacement mesh: the falling debris is a separate effect.

Assets and physics are cached when you build the preview. Dragging Damage or scrubbing does not reload them. Use **Update Damage Preview** after changing geometry, materials, state effects or terrain. If playing near the end of your timeline, extend its end frame to leave time for the effect.

This is a preview control, not an exported health setting. **Clear Damage Preview** restores the original materials and visibility. Manual **Show** state controls also clear the damage preview. After reopening a saved preview, rebuild it to animate, or clear it to return to editing.

Scratch needs a scratch map with useful alpha; a white alpha mask causes no visible darkening. Buildings with several cells are damaged in a repeatable cell order. In game, the impact position changes that order. Native default inverse inertia is supported; collision/integration and engine-generated impact/crush impulses remain incomplete. Building damage preview audio is currently disabled. Create or change destruction effects in the external Effect Editor; assign their filenames through **State Effects** or **Building Grid Settings**.

The preview automatically raises Cycles' transparency depth for overlapping smoke sprites. Clearing it restores the previous value, unless you changed it yourself. This prevents black rectangles caused by the renderer ending transparent rays too early; you do not need to change the smoke textures or alpha threshold.

## 8. Export and Validate

1. Save the edited `.blend` as the working copy. Re-import buildings with this version to capture the new state/container snapshots.
2. Choose an output folder outside the unpacked source assets. Source game files remain read only.
3. Keep **Model Type: Preserve / Auto** for imported buildings. It keeps their node layout, including unknown chunks. Explicit layouts cannot discard source nodes silently.
4. Enable **Export All SKA Actions** for edited animations. Prefix options update AnimationSet and EffectSet only for actions actually written. Referenced source SKAs remain dependencies when animations were not imported or exported.
5. Inspect `<building>.bmg-export.json`. `external_references` lists references not copied into the package; these may be installed-game construction/FX resources or missing assets. Review this list before sharing the export.
6. Re-import into a separate scene. Check S0/S2, ground decal, materials, animation references and building/state collision independently. Then verify placement, damage transitions, construction and playback in the Skylords Map Editor/in game.

Output contains `<building>.bmg`, `<building>_cellNNN_sID.drs`, optional `<building>_ground.drs`, DDS textures, available SKAs and local dependencies. This is an asset package for the installed game. It does not create a new database entity or a standalone map.

Validation failure leaves previous output files intact. Temporary objects/meshes/collections are removed without globally purging the artist's unused data blocks. Imported collision data stays preserved when collision import was disabled; editing loaded shapes regenerates that payload in game coordinates.

**Remaining preview boundary:** metadata preserves the engine's cell rotation/spacing/pivot rules, but complete viewport placement for all modular/shared-armature cases remains unfinished. Independently authoring a construction BMS or changing a debris XML graph is also outside this exporter. Automated Blender checks cover a new two-state building, Heal Well and Bandits Artillery; live engine playback remains to be checked.

## Related Guides

- [Object Creation Guide](object_creation_guide.md)
- [Unit Creation Guide](unit_creation_buide.md)
- [Advanced Shading Guide](advanced_shading_guide.md)
- [Advanced Locators Guide](advanced_locators_guide.md)
- [Advanced Abilities Guide](advanced_abilities_guide.md)
- [Advanced Effects Guide](advanced_effects_guide.md)
