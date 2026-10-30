# Static Object: from Blender to DRS

Export a rock, prop or other **non-animated object** with SR-ImpEx.
The plugin is already installed. This guide uses the current development build.
You do not need Animation Set, Effect Set or Locator settings for this workflow.

## 1. Choose your starting point

### A. Edit an existing DRS

1. Choose **File → Import → Battleforge Model (.drs/.bmg)** and open the `.drs`.
2. Keep its texture files beside it so the importer can find them.
3. Select the visible model mesh and make your changes.

The importer already creates the model structure, GameOrientation and materials.
**Do not run Set Up Model again.** Continue at [check your model](#3-check-your-model).

### B. Make a model from scratch

Model normally in Blender. The default cube is a valid starting point.
When you are ready, select the meshes that belong to your object, then follow step 2.

### C. Use a model from another program

Import it with Blender's normal importer, for example **File → Import → FBX** or **Wavefront OBJ**.
Select the meshes you want to export, then follow step 2.
You will replace their ordinary Blender materials in step 4.

For a static copy of a rigged model, first duplicate it and use **Object → Convert → Mesh**
on that copy to keep the visible pose. Keep your original rig separately.

## 2. Set up a new model

Skip this step for an imported DRS.

1. With your meshes selected, move the mouse over the **3D Viewport** and press **N**.
2. Open the **DRS Editor** tab on the right.
3. In **Model Setup**, click **Set Up Model**.
4. Choose **Static Object**, enter a name such as `object_stone_block`, and keep
   **Include Selected Meshes** enabled.
5. Leave **Collision Support** off unless you intend to add collision shapes. Confirm.

![Set up a static model from selected meshes](../assets/images/guides/static/setup.png)

This adds the model to your current scene and keeps the selected meshes in place.
It does not require a special Blender startup file or an Asset Browser library.

### GameOrientation and the model folders

Look at the **Outliner**, Blender's object list at the top right:

```text
DRSModel_object_stone_block
├── GameOrientation
└── Meshes_Collection
    └── Stone Block
```

**GameOrientation is a helper object** that converts between Blender and game coordinates.
Import and Set Up Model handle it for you. Leave its rotation and scale unchanged;
move or rotate your mesh when you want to change the model.

**Meshes_Collection** contains the visible meshes that the exporter includes.
The Outliner can show the same mesh under its collection and its parent; this is one object.
If you add another mesh later, move it into that collection and parent it to
GameOrientation: select the mesh, Shift-select GameOrientation, then
**Ctrl+P → Object (Keep Transform)**.

![The model structure and GameOrientation](../assets/images/guides/static/structure.png)

<span id="4-model-the-object"></span>

## 3. Check your model

- Use mesh objects. Convert text, curves or metaballs with **Object → Convert → Mesh**.
- Apply geometry modifiers such as Mirror or Bevel before export. Keep an editable copy.
- Give the mesh a UV map so Blender knows where to place its textures.
- Use one DRS material per mesh. For a foreign mesh with several materials,
  use **Edit Mode → P → By Material** to make separate pieces.
- Check size and facing against an imported game object if you have one available.

Already imported a DRS and only changed its shape? Keep its existing material and go to step 6.

## 4. Create a DRS material

Select a mesh and open **DRS Editor → Material Editor**.
Click **Create DRS Material**, or **Create / Upgrade DRS Material** for a mesh that already has a material.
Choose **Default** as the material type and keep **Artist View**.

An ordinary Blender material is not enough for DRS export.
The button creates the correct shader setup and keeps the old material available separately.
You do not need to append an old material from the plugin's asset library.

![Replace an ordinary Blender material](../assets/images/guides/static/foreign-material.png)

## 5. Load your textures

Open **Textures**. Click the **folder icon** beside the color-map slot and choose your image.
PNG and DDS are both supported; the exporter writes DDS files for the game.
Leave **Auto map flags** enabled.

| Texture | When to use it |
| --- | --- |
| Color map | The object's basic painted appearance. Start with this. |
| Normal map | Optional small surface details. |
| Parameter map | Optional surface properties such as shininess and emission. |

Imported DRS textures are assigned automatically when their files are found.
For foreign materials, check and reassign the images here; their original node connections may differ.

![Default material with a color texture assigned](../assets/images/guides/static/material.png)

Switch the viewport to **Material Preview** to see the texture.
For camera, lights and ground, use **DRS Editor → Render Setup → Add Render**.
This covers the whole model. Use **Rendered** shading or press **F12** for a camera render.

![The static object in a lit render setup](../assets/images/guides/static/render.png)

For leaves or fences, **EnableAlphaTest** cuts out pixels using a texture mask;
it does not create soft transparency. Other material features are explained in
the [Default Material Guide](material_artist_workflow.md).

<span id="8-create-collision-shapes"></span>

??? info "Optional: add simple collision shapes"
    If you enabled Collision Support during setup, put cubes, spheres or cylinders
    into **Boxes_Collection**, **Spheres_Collection** or **Cylinders_Collection**.
    Parent them to GameOrientation with **Object (Keep Transform)** and fit them to the object.
    Set **Object Properties → Viewport Display → Display As → Wire** to see the model through them.
    These helper shapes are not visible model meshes.

## 6. Export

1. Save your `.blend` file and select one mesh belonging to the model.
2. Open **DRS Editor → Model Setup → Export DRS**.
   **File → Export → Battleforge Object/Unit (.drs)** opens the same exporter.
3. Choose a separate output folder and a filename such as `object_stone_block.drs`.
4. Check **Static Object (no collision)**, or **Static Object (with collision)** if appropriate.
   The exporter suggests the type from your model.
5. Keep **Mip Maps → Auto** and the other defaults. Click **Export DRS**.

![The static-object export dialog](../assets/images/guides/static/export.png)

You can select the mesh; you do not need to select the root collection or move the 3D cursor.
Static export does not write SKA animations. Bounding boxes and the OBB tree are calculated automatically.

## 7. Check the exported copy

The output folder contains the `.drs` and its `.dds` textures. Keep them together.
Import the exported DRS into a fresh Blender scene and check its orientation, size and textures.
Then test it in the Skylords Map Editor.

If a texture is missing, check its slot in Material Editor and the export folder.
For unusual export settings or parenting issues, use the
[advanced object setup notes](object_setup_reference.md).
