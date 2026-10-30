# Static Object: from Blender to DRS

Export a rock, prop or other **non-animated object** with SR-ImpEx.

## 1. Choose your starting point

### A. Edit an existing DRS

1. Put the `.drs` and its textures in the same folder.
2. Choose **File → Import → Battleforge Model (.drs/.bmg)** and open the `.drs`.
3. Select the visible model mesh and make your changes.

Continue at [step 3](#3-check-your-model). Skip Set Up Model.

### B. Make a model from scratch

Create your model in Blender. Select its meshes, then follow step 2.

### C. Use a model from another program

Import the model with Blender. Select its meshes, then follow step 2.

??? tip "Using a rigged model as a static object"
    Duplicate the meshes and convert the copies to meshes in the desired pose.
    Continue with these copies.

## 2. Set up a new model

Skip this step for an imported DRS.

1. Select your model meshes.
2. Open **DRS Editor → Model Setup → Set Up Model**.
3. Choose **Static Object**, enter a name such as `object_stone_block`, and keep
   **Include Selected Meshes** enabled.
4. Leave **Collision Support** off for now and click **OK**.

![Set up a static model from selected meshes](../assets/images/guides/static/setup.png)

### Where to put your meshes

Your model's structure in the Outliner:

```text
DRSModel_object_stone_block
├── GameOrientation
└── Meshes_Collection
    └── Stone Block
```

!!! info "GameOrientation — your model's parent object"
    **GameOrientation** keeps your model aligned with the game. Import and
    Set Up Model create it for you.

    - Move, rotate and resize your **meshes**. Leave GameOrientation unchanged.
    - Keep the meshes in **Meshes_Collection** and parented to this model's GameOrientation.
    - Moving a mesh into the collection does not parent it.

??? tip "Advanced: add another mesh"
    Move the new mesh into this model's **Meshes_Collection** and parent it to
    **GameOrientation** using **Object (Keep Transform)**.

    Use the GameOrientation from the same model. Keep existing rigged meshes
    attached to their armature.

![The model structure and GameOrientation](../assets/images/guides/static/structure.png)

<span id="4-model-the-object"></span>

## 3. Check your model

- Use UV-mapped meshes with geometry modifiers applied.
- Use one DRS material per mesh. Separate multi-material meshes by material.
- Check size and facing against an imported game object if you have one available.

Already imported a DRS and only changed its shape? Keep its existing material and go to step 6.

??? tip "Advanced: large models and export errors"
    - Keep each mesh and the combined model below **32,767 exported vertices**.
      Leave room for extra vertices at UV seams.
    - If you reach the limit, reduce the geometry or export smaller, separate DRS objects.
    - Apply geometry modifiers on a copy before exporting. Keep the editable original.
    - If export fails, read the add-on log and fix the reported object first.

## 4. Create a DRS material

Select a mesh and open **DRS Editor → Material Editor**.
Click **Create DRS Material**, or **Create / Upgrade DRS Material** for a mesh that already has a material.
Choose **Default** as the material type and keep **Artist View**.

![Replace an ordinary Blender material](../assets/images/guides/static/foreign-material.png)

## 5. Load your textures

1. Open **Textures**.
2. Click the **folder icon** beside **ColorMap** and choose your PNG or DDS color texture.
3. If you have a normal map, load it into **NormalMap**.
4. Leave **Auto map flags** enabled.

For an imported DRS, keep the assigned textures or replace the ones you want to change.
For a foreign model, load its textures here.

![Default material with a color texture assigned](../assets/images/guides/static/material.png)

Check the result in **Material Preview**.
For a lit preview, use **DRS Editor → Render Setup → Add Render**.

![The static object in a lit render setup](../assets/images/guides/static/render.png)

For cut-out leaves or fences, enable **EnableAlphaTest** under **Material Flags**.
See the [Default Material Guide](material_artist_workflow.md) for more material options.

<span id="8-create-collision-shapes"></span>

??? info "Optional: add simple collision shapes"
    Enable **Collision Support** in step 2 if your object needs collision.

    1. Add cubes, spheres or cylinders and fit them around your model.
    2. Move them into **Boxes_Collection**, **Spheres_Collection** or **Cylinders_Collection**.
    3. Parent them to **GameOrientation** using **Object (Keep Transform)**.
    4. Set the collision helpers to **Wire** display.

    Keep boxes rectangular, spheres round and cylinders circular. Avoid bevels and shear.
    After export, reimport with collision shapes enabled and check their fit.

## 6. Export

1. Select a mesh belonging to the model.
2. Open **DRS Editor → Model Setup → Export DRS**.
3. Choose a separate output folder and a filename such as `object_stone_block.drs`.
4. Check **Static Object (no collision)**, or **Static Object (with collision)** if appropriate.
5. Keep **Mip Maps → Auto** and the other defaults. Click **Export DRS**.

![The static-object export dialog](../assets/images/guides/static/export.png)

??? tip "Advanced: export options"
    For extra mesh controls, open **Advanced Mesh Settings** in the export window.

    | Option | Setting |
    | --- | --- |
    | Split Mesh by UV Islands | Keep enabled unless you have prepared the splits yourself. |
    | Flip Normals | Use only to correct confirmed inside-out faces. |
    | Auto-fix Quad Faces | Keep enabled to export quads as triangles. |
    | Mip Maps | Keep **Auto**. Change only to limit the exported mip levels. |
    | Keep Debug Collection | Enable to inspect the prepared export copy. |

## 7. Check the exported copy

1. Keep the exported `.drs` and `.dds` textures together in the output folder.
2. Import the DRS into a fresh Blender scene. Check its orientation, size and textures.
3. Test it in the Skylords Map Editor.

If a texture is missing, check its slot in Material Editor and the export folder.
