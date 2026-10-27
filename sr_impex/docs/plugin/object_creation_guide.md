# Object Creation Guide

This guide walks through creating a new object from scratch for the SR-ImpEx Blender plugin.

## Before You Start

1. Install and enable the add-on in Blender, then save a working `.blend` file.
2. Decide whether to modify an imported model or start from scratch. This guide covers a new **static object**; importing a similar existing asset is useful when you need a reference for size, materials, or collision.
3. For a rigged object or unit, continue with the [Unit Creation Guide](unit_creation_buide.md). For building states and mesh grids, use the [Building Creation Guide](building_creation_guide.md).
4. Keep original game assets separate from your export folder. Test exports should never overwrite your only source copy.

> **Two different hierarchies:** Collections determine what the exporter includes. Object parents determine coordinate space. Moving a mesh into a collection does **not** parent it to `GameOrientation` (GO). Using the model's GO is recommended for consistent viewport authoring, but parenting before modeling is a convenience, not a required order of operations.

## 1. Create a New BattleForge Scene

Go to `File > Import > New Battleforge Scene`.

![New Battleforge Scene menu](https://i.gyazo.com/7a12d05f3036e9e530b126c40f79a620.png)

A file browser window will open. You can ignore that part for now and instead use the options in the right-hand sidebar.

Select the object type you want to generate. For this tutorial, choose `Static Object`.

Enable **Collision Support** if you plan to export a collision-enabled object type. This creates the collision **collections**, not fitted collision meshes; those are added in [step 8](#8-create-collision-shapes).

For this tutorial, enable it so the full workflow is covered. Use a comparable game asset to decide whether collision is appropriate for your object. Adding collision volumes is not, by itself, a complete definition of game-side interaction or pathing behavior.

![New scene settings](https://i.gyazo.com/72fb110174d2554689b44fafe3b81af0.png)

## 2. Understand the Collection Hierarchy

This creates a full collection hierarchy in the Blender Outliner.

![Generated collection hierarchy](https://i.gyazo.com/295777e47296cb85568f5f83c6853ef2.png)

The most important collections are:

| Collection | What belongs here |
|---|---|
| `DRSModel_object_CHANGENAME` | Model root. Replace `CHANGENAME` with your model name, keeping the `DRSModel_` prefix. |
| `Meshes_Collection` | Visible model meshes, directly in this collection. |
| `CollisionShapes_Collection` | Container for the three collision subcollections. |
| `Boxes_Collection` | Rectangular box collision meshes. |
| `Spheres_Collection` | Sphere collision meshes. |
| `Cylinders_Collection` | Circular cylinder collision meshes. |

`GameOrientation` is an **Empty object** in the model root, not another collection. The exporter uses the collection hierarchy to find meshes and collision shapes; do not replace the named collections with arbitrary folders.

> Tip: You can delete the default Blender collection with the camera and light, or leave it outside the model root. Keep helper objects and unrelated test meshes out of the export collections.

## 3. Understand GameOrientation (Recommended Practice)

The game and Blender use different coordinate conventions. `GameOrientation` (GO) is the model's coordinate-conversion helper; its transform includes a rotation **and a mirror**. It is not a second mesh or an ordinary placement control.

> **Good practice, not a mandatory modeling order:** For a fresh primitive, parenting to the model's GO before fitting it makes the viewport workflow easier. You can also model first, parent later, correct the visible rotation, and apply the mesh rotation. The important check is the exported result, not when you created the parent relationship.

For the recommended workflow:

1. Add a mesh and place it directly in `Meshes_Collection`.
2. In **Object Properties > Relations > Parent**, choose this model's `GameOrientation` Empty. With multiple models loaded, check the model root rather than choosing another model's similarly named helper.
3. Shape and position the geometry in Edit Mode. Object Mode rotation/scale can also be baked into a standalone mesh with `Ctrl+A > Rotation & Scale` when needed.

If you parent an already modeled object, its viewport orientation can change. Correct the **mesh**, not GO. Blender's **Keep Transform** parenting also creates a parent-inverse transform, so it is not identical to simply selecting a parent in Relations. Applying object rotation does not remove a parent inverse.

For ordinary render meshes, baked rotation is part of the exported vertex data; do not assume every unapplied Object Mode transform or arbitrary parent chain is exported just because it looks correct in Blender. See the round-trip check in [step 10](#10-final-export-result-and-round-trip-check).

Leave an imported model's existing hierarchy intact unless you intentionally need to change it. In particular, do not reset GO or apply its transform to every child to make its transform fields look tidy. Rigged meshes and bone-attached locators follow their existing armature relationships; see the [Unit Creation Guide](unit_creation_buide.md) and [Advanced Locators Guide](advanced_locators_guide.md).

![Parent to GameOrientation](https://i.gyazo.com/2329989dfc1ed6674796ccbd2dd35479.png)

## 4. Model the Object

Create and sculpt your object as needed. The artistic modeling process is outside this guide, but these export requirements matter:

- **Use real mesh data.** Convert non-mesh objects and bake geometry-changing modifiers on a working copy when their result needs to be exported. Do not assume the viewport's evaluated modifier result is the stored mesh.
- **Create a UV map.** The exporter reads the active UV layer and calculates tangents. A textured material alone is not a substitute for UVs.
- **Keep the render geometry triangulated.** `Auto-fix Quad Faces` can triangulate the export copy; clean up problematic faces before export rather than relying on a visual preview alone.
- **Watch vertex counts.** Validation rejects a mesh with more than `32,767` vertices, and also checks the combined, welded render mesh against that limit. UV splitting can duplicate vertices, so leave headroom.
- **Use the intended material on each exported mesh.** Do not assume several material slots on one object become separate game materials; use separate mesh objects for independently configured materials.
- **Check scale and forward direction against an existing asset.** A correctly shaded Blender viewport does not establish the model's in-game scale or orientation.

## 5. Assign the DRS Material

Once you are happy with the shape, the next step is setting up the material.

Change an editor area's type to **Asset Browser**. Choose the **Battleforge Assets** library (registered by scene initialization), or **All Libraries**, then open the **DRS_Material** catalog and drag **DRS Material** onto the mesh.

Make it the mesh's **active material**. Use one intended exported material per mesh, and preserve the generated node names/labels: the exporter reads supported parts of this layout rather than baking any arbitrary Blender shader. A loaded **Color Map (_col)** image and a valid active UV map are part of the basic export setup.

If the asset library is missing, check **Edit > Preferences > File Paths > Asset Libraries** for the bundled library, or start from an imported DRS material. See the [Advanced Shading Guide](advanced_shading_guide.md#1-start-with-the-drs-material-layout) for the supported node layout and material-sharing caveats.

![Assign the DRS Material asset](https://i.gyazo.com/5d47abf2d2eb795a46e6172283df3c34.png)

## 6. Set Up Textures

Open the `Shading` workspace, select your model, and use the shader editor to assign the textures.

Start with the supported texture roles:

| Role | Usual suffix | Important distinction |
|---|---|---|
| Color | `_col` | Required color image; alpha is used by supported transparency modes. |
| Normal | `_nor` | Use a data/non-color image and enable its material flag. |
| Packed parameters | `_par` | **R metallic, G roughness, B flu mask, A emission strength**. Alpha here is not color-map opacity. |
| Flu color | `_flu` | Used with the `_par` mask and optional Flow metadata. |
| Refraction | `_ref` | Has its own preview/flag setup and RGB refraction value. |
| Environment | `_env` | Model-level cubemap helper, not an ordinary per-mesh color slot. |

A matching filename suffix alone does not enable a map: assign it to the supported node and check the corresponding material controls. For packing rules, separate-map overrides, color spaces, flu animation, and environment/refraction caveats, use the [Advanced Shading Guide](advanced_shading_guide.md).

![Texture setup in the shader editor](https://i.gyazo.com/4631e2b1bec4bcf3521a9698a083b32a.png)

## 7. Open the DRS Editor Panel

Select the **render mesh** to edit its material properties, open the 3D Viewport sidebar (`N`), and choose **DRS Editor > Material**. The material panels are object-level controls; selecting only a root collection or collision helper is not the same context.

For this tutorial, the most important sections are:

- `Flags (bool_parameter)`
- `Wind`

Other metadata editors and export selection use the active `DRSModel_...` root collection. If several models are loaded, check both the active mesh and model root before editing.

![DRS Editor panel](https://i.gyazo.com/5a0ed6083341350722c55ad18b4a79fa.png)

### Material Flags

This section lets you enable important material features such as:

- Alpha test
- Parameter map usage for metallic, roughness, and emission
- Normal map usage

If you use any of those texture maps, make sure the corresponding flags are enabled.

### Wind

These object properties are exported as wind material values; the Geometry Nodes modifier supplies a Blender preview.

- `Wind Height`: Lower threshold for the preview's height falloff; defaults to `0`.
- `Wind Response`: Defaults to `0`, with a UI range of `0` to `0.1`.

If the mesh has no generated wind modifier, click **Add Wind Modifier** first. Play the timeline to preview it. The current preview uses the mesh's **local Y** for its height calculation, not world Z, so review it after changing mesh orientation or dimensions.

The preview does not guarantee identical game wind behavior, and its modifier is not exported as an engine node graph. See [Advanced Shading Guide > Wind](advanced_shading_guide.md#7-wind).

## 8. Create Collision Shapes

If your object needs collision, this is the final setup step before export.

Use simple meshes in the matching subcollection; the **collection**, not the object's name, selects the exported primitive type:

| Primitive | Collection | Keep this geometry |
|---|---|---|
| Cube/box | `Boxes_Collection` | A rectangular box with perpendicular axes and planar faces. |
| Sphere | `Spheres_Collection` | A round sphere. An ellipsoid cannot be represented exactly by a single sphere. |
| Cylinder | `Cylinders_Collection` | A circular cylinder with two parallel planar caps. Caps may be n-gons or triangles. |

> **GO reminder:** As with visible meshes in [step 3](#3-understand-gameorientation-recommended-practice), using the same model's GO is good practice when fitting new collision shapes. Collection membership alone does not establish that relationship. Parenting before modeling is optional: you can create and fit a shape first, parent it later, correct its viewport rotation, and apply that rotation to the collision mesh. Do not rotate GO to correct only one shape.

A practical workflow is:

1. Add the primitive and move it into its matching collision collection.
2. If using GO, choose this model's helper under **Object Properties > Relations > Parent**.
3. Position and size the shape against the visible model. If parenting changed its appearance, correct the mesh's rotation; `Ctrl+A > Rotation` can bake that correction.
4. Set **Object Properties > Viewport Display > Display As > Wire** to make fitting easier.
5. Repeat with additional shapes only where they improve the approximation.

One to five shapes is often a useful starting point, not a format limit. These are collision volumes, not extra render meshes: keep them out of `Meshes_Collection` and avoid bevels, sculpted surfaces, or sheared shapes that no longer describe the selected primitive. A sphere has only one radius, and a cylinder has one radius plus a height; non-uniform scaling must not turn them into ellipsoids or elliptical cylinders if you expect an exact fit.

Export and re-import a test after fitting. Check the collision shape's **position, tilt, height, and radius**, not just whether it is present. See the [collision format notes](../drs/collisionshape.md) for representation limits.

![Box collision example](https://i.gyazo.com/d7360e19510ed4d43be6cdddb4493d1d.png)

![Sphere collision example](https://i.gyazo.com/4902c0ed50dc313ec54a29ad8925ca39.png)

![Cylinder collision example](https://i.gyazo.com/3b020102c078e4db5276e7db9474c375.png)

## 9. Export the Object

Make the **root `DRSModel_...` collection active** in the Outliner, not just a mesh, collision subcollection, or `Meshes_Collection`. Then choose **File > Export > Battleforge Object/Unit (.drs)**. Menu text also includes the add-on version.

Before exporting, save the `.blend` file and place the 3D cursor at world origin (`Shift+S > Cursor to World Origin`); the export preparation uses the cursor when setting mesh origins. Choose a separate test folder.

| Setting | For this static-object example |
|---|---|
| `Model Type` | Choose `Static Object (with collision)` when you populated the collision collections, otherwise `Static Object (no collision)`. Collision-enabled export requires collision data. |
| `Split Mesh by UV Islands` | Enabled by default. Keep it on unless you have a specific reason to manage UV splits yourself. |
| `Flip Normals` | Off by default. Use it for a confirmed winding/normal problem, not as a fix for a misplaced or rotated object. |
| `Auto-fix Quad Faces` | Enabled by default; triangulates the export copy. |
| `Mip Maps` | `Auto` is the default. Numeric choices cap the mip count per image; see the [Advanced Shading Guide](advanced_shading_guide.md). |
| `Export All SKA Actions` | Not needed for this static object; disable it. |
| `Model Name Prefix` | Affects SKA names, not static mesh orientation. Not needed here. |
| `[DEBUG] Export SKA Tangents` | Not relevant to a static object. |
| `Keep Debug Collection` | Leave off for normal export; keeps the export copy for diagnosis when enabled. |

The importer's `Apply Transform` option and Blender's `Ctrl+A` are different operations. There is no general DRS export checkbox that promises to bake every object's parent hierarchy.

![Export settings](https://i.gyazo.com/a25ba88c9b08f6078542dda31ece4f7e.png)

## 10. Final Export Result and Round-Trip Check

After exporting, you should find the final `.drs` file together with the generated `.dds` textures for the maps you used. Read the add-on's message log if export fails; a Blender preview alone does not establish a successful file export.

![Export result files](https://i.gyazo.com/adfbae27fbe9fd4379b5feb1ad45d9c4.png)

### Before considering the object finished

- [ ] The root retains its `DRSModel_` prefix, and render meshes/collision meshes are in their correct collections.
- [ ] Render meshes have an active UV map and a supported DRS material.
- [ ] The selected model type matches the presence or absence of collision shapes.
- [ ] The exported file and referenced textures exist in the test folder.
- [ ] A fresh import matches the source model's scale and orientation, and all collision shapes fit correctly.

To check a round trip:

1. Open a separate Blender file, or explicitly disable **Clear Scene** when importing into the current scene; that import option is enabled by default.
2. Import the exported `.drs` with **Import Collision Shape** enabled.
3. Use the **same `Apply Transform` import setting** for both sides of a comparison. Different display-axis settings can make identical data look rotated.
4. Compare mesh silhouette, textures, collision position, and primitive dimensions. Avoid rotating only a GO helper just to line up two test copies.
5. If the first round trip matches, export/import the test again to check that rotations or offsets do not accumulate.
6. Validate the result in game as well. Blender previews do not reproduce every shader or gameplay behavior.

### Common problems

| Symptom | Check first |
|---|---|
| Export says the selected collection is invalid | Make the `DRSModel_...` root active, not a child collection. |
| A mesh does not export | Put the mesh directly in `Meshes_Collection`; check its UVs, material, and vertex count. |
| A mesh looks right in Blender but exports rotated | Check baked mesh data, unapplied object transforms, parent inverses, and the import display-axis setting; do not change GO blindly. |
| Collision is missing or has the wrong type | Check `Model Type` and the box/sphere/cylinder subcollection, not just object names or viewport visibility. |
| A cylinder changes size or tilt | Keep it circular and capped, and compare a fresh round trip before adding more shape edits. |
| Surface looks inside-out | Inspect face orientation and normals; use `Flip Normals` only after confirming the issue. |
| Textures or packed channels look wrong | Check the [Advanced Shading Guide](advanced_shading_guide.md). |
