# Advanced Shading Guide

Use this guide to prepare DRS materials, choose texture channels, and edit the material data written by the exporter. The same material workflow applies to static objects, units, and building meshes; their collection and animation setup is covered in the [creation guides](#related-guides).

> **Preview is not export.** The Blender shader previews selected DRS features. Export collects images, repacks parameter channels, and writes material flags, refraction color, flow vectors, and wind values. It does **not** bake an arbitrary Blender shader or guarantee identical in-game lighting, transparency, or animation.

## 1. Start with the DRS material layout

1. Use an imported DRS material as a reference, or assign the bundled **DRS Material** asset from the Asset Browser's **DRS_Material** catalog. Scene initialization registers the **Battleforge Assets** library; choose it or **All Libraries** in the browser.
2. Select your render mesh inside `Meshes_Collection`. The material panels also accept meshes in `GroundDecal_Collection`.
3. Open the **Shading** workspace and make the intended material the object's **active material**. The exporter reads that material, not a separate material for every face slot. Split objects when different exported materials are needed.
4. Assign images to the existing labeled texture nodes. Keep a valid active UV map on the mesh: export calculates tangents and reads those UVs.
5. In the 3D Viewport sidebar (`N`), open **DRS Editor → Material**. Use **Flags (bool_parameter)**, **Flow**, **Wind**, and **Cubemap Helper** for object-level settings.

Flags, flow, and wind belong to the **object**. Shader links and images belong to the **material**. If two meshes need independent previews or texture assignments, make their materials single-user before changing them.

### Names are part of the integration

Do not rename or replace the exporter-used nodes while reorganizing the graph:

- **DRS Shader** is the named **Principled BSDF** node, not the processing group.
- **AIO DRS Engine** is the group label; its node name is `DRS_Engine_Group` and its node-tree name is `AIO_DRS_Engine`.
- Keep the texture labels in the table below, plus **Separate Metallic**, **Separate Roughness**, **Separate Emission**, **Separate Flu Mask**, and **Refraction Color**.
- Keep **Apply Flu Mask** and **Mix Refraction Shader**: UI callbacks use those labels to enable or mute preview branches.

The runtime builder's layout is the reference if an older asset has different nodes. Merely renaming an unrelated shader does not reproduce its supported connections. See the [material builder](../../blender/drs_material.py).

## 2. Texture suffixes and channels

Suffixes identify the generated texture roles; the material's **node labels and assigned images** are also important for discovery. Renaming an image file alone does not enable its export.

| Suffix | Image node label | Verified use | Export condition / format |
|---|---|---|---|
| `_col` | **Color Map (_col)** | Color feeds base color and emission color. Alpha feeds the opacity preview when alpha test or decal mode is enabled. | Required image; DXT5 DDS. |
| `_nor` | **Normal Map (_nor)** | Color passes through Blender's Normal Map node. The importer sets **Non-Color**. | **Use Normal Map (Bit 17)**; DXT1 DDS. |
| `_par` | **Parameter Map (_par)** | **R = metallic, G = roughness, B = flu mask, A = emission strength**. The importer sets **Non-Color** and **Channel Packed** alpha. | **Use Parameter Map (Bit 16)**; repacked DXT5 DDS. |
| `_flu` | **Flu Map Layer 1**, **Flu Map Layer 2** | Tileable color image; import assigns the same sRGB image to both preview layers. | Bit 16 and a detected flu image; one DXT5 DDS, not two independent layer textures. |
| `_ref` | **Refraction Map (_ref)** | Color controls the internal refraction/transparent preview mix; alpha controls the final opaque/refraction mix. **Refraction Color** is a separate RGB value. Import sets the map to **Non-Color**. | Effective Bit 18 and a detected refraction image; DXT5 DDS. |
| `_env` | **Environment Cubemap (_env)** | Model-level image on the cubemap helper, not an ordinary mesh texture node. | **Use Env/Cube Map (Bit 18)** with an assigned helper image; DXT5 cubemap. |

The `_par` green channel is used directly as **roughness** in the Blender graph; it is not inverted into smoothness. The separate numeric `smoothness` entry in the DRS format is not this texture channel.

**Engine interpretation versus add-on convention:** the table documents the current Blender shader and exporter packing. Older research-template comments suggested red might be ambient occlusion, green specular, and blue roughness when no flu map is present. Those are historical hypotheses, not confirmed engine semantics. Keep the current channel layout; do not swap channels or label the old interpretation as verified without controlled in-game comparisons.

Likewise, historical Paint.NET notes recommending DXT3 for color or DXT1 for refraction are not the current export settings and do not establish an exclusive list of engine-supported DDS formats. The formats in the table describe what this add-on currently generates.

### Combined parameter map: recommended baseline

1. Prepare one RGBA image with the packing shown above. Preserve alpha: here it carries emission, not opacity.
2. Assign it to **Parameter Map (_par)**; use **Non-Color** and **Channel Packed** alpha when assigning a new image manually.
3. Leave the group's **Use Separate Maps** input off, and enable **Use Parameter Map (Bit 16)** in the sidebar.
4. Clear unused images from the **Separate …** nodes. Export prefers assigned separate metallic, roughness, and emission images over the combined image, even when **Use Separate Maps** is off in the preview.

A flu mask of zero selects the color-map side of the preview mix; a mask of one selects the animated flu-color side. Emission strength uses `_par` alpha, while the emission color comes from `_col`.

### Separate maps: channel-aware authoring

The graph exposes **Separate Maps (Artist Override)** and the **Use Separate Maps** group input. This input switches the **preview** between combined and separate sources; it is not a DRS flag and does not by itself select export sources.

The packing helper reads the following channels from its resolved images:

| Source | Channel copied into exported `_par` |
|---|---|
| Metallic source | Red → R |
| Roughness source | Green → G |
| Flu-mask source | Blue → B |
| Emission source | Alpha → A |

For RGB grayscale metallic or roughness images, put the intended value in all RGB channels. A separate RGBA emission image must carry the intended strength in **alpha**, not only in RGB. The separate preview inputs use the image's **Color** output, so an emission image whose RGB and alpha differ can preview differently from its export.

The packer accepts either one shared image for all resolved channels, or a distinct image for every supplied channel. Partially reused images mixed with different images are rejected. Distinct images must have identical width and height. Unresolved channels are filled with **0**, not the shader socket's preview default. The group's declared separate-input defaults are metallic `0`, roughness `0.8`, emission `0`, and flu mask `0`; linked nodes can override those preview defaults.

> **Current flu-mask limitation:** the standard export path first resolves the group's **Flu Mask** output by searching upstream for an image whose label contains `_par`. With the generated graph, this favors the combined parameter image; an image assigned only to **Separate Flu Mask** is not a reliable exported B source. For fluid materials, prefer a combined `_par` and check its blue channel after export. Do not assume the visible separate-mask preview proves it was written.

These are image-packing rules, not shader evaluation: procedural nodes, ramps, scalar defaults, and arbitrary graph edits are not baked into parameter textures. See [`create_mesh` and the packing helper](../../utilities/drs_utility.py).

## 3. Material flags: supported controls versus unknowns

Open **Material → Flags (bool_parameter)**. New object properties start with **Raw bool_parameter = 0**; imported objects are populated from their file. Prefer the labeled toggles over manual raw-integer edits, because the toggles also update the supported preview connections.

| UI control | Implemented Blender / export behavior |
|---|---|
| **Enable Alpha Test (Bit 0)** | Connects `_col` alpha to **DRS Shader** alpha; exported as a flag. |
| **Decal Mode (Bit 1)** | Also enables that alpha connection; exported as a flag. It does not create a decal mesh or projection setup. |
| **Use Parameter Map (Bit 16)** | Connects `_par` data for preview; gates `_par` and `_flu` export. |
| **Use Normal Map (Bit 17)** | Connects the normal texture for preview; gates `_nor` export. |
| **Use Refraction Map (Bit 18)** | Requires a loaded **Refraction Map (_ref)** image; enables the refraction preview branch. |
| **Use Env/Cube Map (Bit 18)** | Requires a loaded helper image; controls helper visibility and requests `_env` export. |
| **Disable Receive Shadows (Bit 20)** | Named flag stored for export; no corresponding Blender shadow-preview callback is implemented here. |
| **Enable SH Lighting (Bit 21)** | Named flag stored for export; no corresponding Blender lighting-preview callback is implemented here. |
| **Unknown Bitflag … (Bit N)** | Uninterpreted flags. Preserve known-good imported values rather than choosing bits from their names. |

With both alpha/decal flags off, the callback disconnects color alpha and sets preview alpha to 1. With either enabled, it uses the color image's **Straight** alpha mode. This is not evidence that every in-game alpha/decal rendering detail is reproduced.

The refraction and environment controls are **two sources for the same exported Bit 18**, not two independent file bits. Export recomputes that bit from enabled paths that actually have images; setting the raw integer alone cannot substitute for the required assets. The refraction-data writer then checks this effective bit, so an assigned `_ref` image can also be written when only the environment path enabled Bit 18. Clear an unused refraction image rather than relying solely on its preview toggle.

## 4. Normal maps

1. Assign the image to **Normal Map (_nor)** and use **Non-Color**.
2. Enable **Use Normal Map (Bit 17)** on each mesh that needs it.
3. Keep the generated connection through **AIO DRS Engine → Normal → DRS Shader** and keep a valid UV layout.

The exporter resolves an image rather than baking normal-processing nodes, then converts it to DXT1. No extra normal-channel inversion is performed by the shown material builder or packing path. If a source asset uses a different convention, compare against a working imported material instead of assuming a green-channel flip is required.

## 5. Refraction and environment cubemaps

### Refraction map and color

1. Load an image into **Refraction Map (_ref)** before enabling **Use Refraction Map (Bit 18)**. An enable attempt without an image is rejected with a notice.
2. Set the **Refraction Color** RGB node; the generated node defaults to white `(1, 1, 1)`.
3. Inspect the material in a shading mode that evaluates its nodes. The preview uses a glass/transparent branch, the parameter-map roughness, and the normal-map result. Enabling the branch also enables backface culling; disabling it mutes the branch and disables that culling setting.
4. Check the exported texture and RGB value after a round trip. Changing internal glass IOR, mix nodes, or other Blender-only settings does not serialize those shader edits into DRS.

The preview wiring establishes how Blender uses the map, not a complete specification of the game's refraction algorithm. When Bit 18 is inactive, export writes a zero refraction color. When active, it reads the labeled **Refraction Color** node; if that node cannot be found, the export fallback is black.

### Model-level environment helper

1. Select a mesh under the intended `DRSModel_<basename>` root and open **Material → Cubemap Helper**.
2. Click **Add Cubemap (Earth Base)**. This creates or resets `Environment_Collection` / `Environment_Cubemap` using the bundled earth cubemap when available. Check **Model Cubemap → Assigned**, not just that a helper object exists.
3. To use a custom image, select the helper and replace the image on **Environment Cubemap (_env)** in its material. Keep that node label/name and the helper collection intact. Re-select the render mesh afterward.
4. Enable **Use Env/Cube Map (Bit 18)** for each mesh that should request the model's cubemap. Adding the helper alone is not that per-mesh export request.
5. Use **Debug Export Cubemap** to check conversion independently. It writes a timestamped DDS to the add-on's `sr_impex/debug` folder; it is not a complete model export. **Remove Cubemap** removes the model helper, so check all dependent meshes afterward.

The export converter supports square-face **6×1 horizontal strips**, **1×6 vertical strips**, and a **4×3 cross**. Strip order is `+X, -X, +Y, -Y, +Z, -Z` (left-to-right or top-to-bottom). The cross uses this layout; each entry is one square tile:

| | Column 1 | Column 2 | Column 3 | Column 4 |
|---|---|---|---|---|
| Top | — | +Y | — | — |
| Middle | -X | +Z | +X | -Z |
| Bottom | — | -Y | — | — |

The helper's automatic preview UV layout supports **strips only**; a cross can be accepted by export without receiving a correct helper preview. The helper is a textured emission cube, not a Blender world-lighting or reflection-capture system. Do not judge in-game environment behavior from its visibility alone. Cubemap conversion requires the bundled `texconv.exe` and `texassemble.exe`.

## 6. Flu animation and Flow

1. Set up `_par` with a nonzero blue mask where flu color should appear and enable Bit 16.
2. Assign the **same tileable image** to **Flu Map Layer 1** and **Flu Map Layer 2**. The generated preview repeats the images and crossfades two animated coordinate layers; export selects one flu image, so different images in the two nodes are not a supported two-texture export setup.
3. Open **Material → Flow** and enable **Write Flow** when the four flow vectors should be written to the mesh material block.
4. Set the vectors using a working imported asset as a starting point. Play or scrub the timeline to inspect the preview, then reimport an export to check the stored values.

| Flow control | New-object default | What is verified |
|---|---|---|
| **Write Flow** | Off | Enables vector export; it is separate from the texture-enable flag. |
| **Max Flow Speed** | `(0, 0, 0, 0)` | Four stored components; XYZ feeds preview **MaxSpeed**. |
| **Min Flow Speed** | `(0, 0, 0, 0)` | XYZ feeds preview **MinSpeed**. |
| **Flow Speed Change** | `(0, 0, 0, 0)` | XYZ feeds preview **Frequency**. |
| **Flow Scale** | `(0, 0, 0, 0)` | XYZ feeds preview **Scale**, multiplying generated coordinates. |

The UI declares no extra min/max bounds for these vectors. All **four components** are exported when **Write Flow** is enabled, but the fourth component is not used by this preview. Its in-game meaning and the engine's units are not established here. The preview group interface starts with scale `(1, 1, 1)`, whereas object Flow properties start at zero; those are different defaults. A zero scale collapses the preview's spatial coordinate variation.

**Write Flow** gates serialization, not the shader's time driver. Conversely, Bit 16 gates `_par`/`_flu` texture export but does not automatically enable **Write Flow**. The preview's frame-driven oscillation is an approximation, not a measured copy of game timing.

## 7. Wind

Open **Material → Wind**. If the mesh has no generated wind modifier, click **Add Wind Modifier**; the controls remain disabled until a `WindEffect` Geometry Nodes modifier exists. Imported render meshes normally receive this modifier during material creation.

| Control | New-object default | Declared UI range / preview use |
|---|---|---|
| **Wind Response** | `0.0` | `0.0`–`0.1`; multiplies scene time before the preview's noise node. |
| **Wind Height** | `0.0` | No explicit min/max bounds; lower threshold for the preview's height falloff. |

The current preview measures **local Y**, uses the mesh's local Y bounding-box span for the falloff's upper endpoint, and offsets positions along **local X**. It is not a world-Z height slider. Recheck the preview after editing mesh orientation or dimensions. Keep the modifier's **Wind Response** and **Wind Height** node names if editing its graph.

Export stores these two object values in the material entries for wind response and wind height. It does not serialize the Geometry Nodes graph as an engine wind simulation. More generally, the exporter creates the numeric **Materials** block from defaults and overrides these wind entries; arbitrary Principled settings are not converted into the format's other numeric material parameters.

## 8. Export and verification checklist

- [ ] Each render mesh has the intended **active material**, a valid active UV map, and the expected DRS node layout.
- [ ] **Color Map (_col)** has a loaded image. Missing color data aborts mesh export; a flat Blender base color is not a replacement.
- [ ] Bit 16/17 and refraction/environment toggles match the images actually assigned. Clear stale separate-map images before using a combined `_par`.
- [ ] Parameter sources use a supported packing pattern and matching dimensions; emission is in alpha, and the exported blue flu mask is checked explicitly.
- [ ] Both flu preview layers use the same image. **Write Flow** is enabled only when its vectors should be written.
- [ ] Cubemap conversion succeeds, and required conversion executables remain in the add-on's resources folder.
- [ ] Export into a separate output folder, inspect the generated DDS files and warnings, then reimport the DRS into a separate scene to compare textures, flags, refraction RGB, flow vectors, and wind values.

The material exporter traverses supported image chains with a bounded search and role-label matching; it does not evaluate arbitrary node graphs. Prefer the generated layout to deep chains or renamed nodes. A file being created is not sufficient proof that every optional texture was exported: several missing-map and packing failures are reported without immediately aborting the whole model export.

## Troubleshooting

| Symptom | Checks |
|---|---|
| Material panels only show a selection notice | Select a **mesh** in `Meshes_Collection` or `GroundDecal_Collection`, not an armature, helper, or the root collection. |
| Mesh export stops at color-map setup | Check the active material, **DRS Shader** name, **Color Map (_col)** image and label, and its connection to base color. |
| `_par` is absent or differs from preview | Enable Bit 16; inspect separate-node overrides, source channels, dimensions, and mixed reused/distinct-image errors. Preview scalar defaults are not exported texture data. |
| Fluid color or mask disappears | Check Bit 16, both flu images, packed `_par` blue, and the separate-flu-mask limitation above. Toggle Bit 16 off/on after assigning images to refresh the mask preview callback. |
| Normal map is absent | Enable Bit 17; check **Normal Map (_nor)**, **Non-Color**, and the generated normal chain. |
| Refraction/environment toggle turns itself off | Assign the required image first. Check the sidebar notice and the helper's **Assigned** status. Raw Bit 18 alone is insufficient. |
| Cubemap conversion fails | Check layout dimensions, face order, the two bundled conversion tools, and the debug-export error log in `sr_impex/debug`. Cross preview UVs are not generated automatically. |
| Flow seems static or uniform | Check nonzero scale and speed values, timeline playback, and the flu mask. **Write Flow** controls export, not playback. |
| Wind controls are disabled or falloff seems wrong | Add the modifier, preserve its expected node names, and inspect local Y extent and **Wind Height**, not only world-space height. |
| Two objects' previews change together | Their material or processing node tree may be shared; inspect datablock users before making independent edits. |

## Implementation and format references

- [Material builder](../../blender/drs_material.py): `_build_aio_engine_group_internals`, `_link_material_nodes`, map setters, and wind preview creation.
- [Material/Flow/Wind editor](../../blender/editors/material_flow_editor.py): UI labels, property defaults/ranges, flag callbacks, and preview updates.
- [Cubemap editor](../../blender/editors/environment_cubemap_editor.py): helper controls and debug export.
- [Import/export integration](../../utilities/drs_utility.py): `create_material`, `setup_material_parameters`, `create_mesh`, `set_metallic_roughness_emission_map`, and cubemap conversion.
- [CDspMeshFile format](../drs/cdspmeshfile.md): [Materials](../drs/cdspmeshfile.md#materials), [Textures](../drs/cdspmeshfile.md#textures), [Refraction](../drs/cdspmeshfile.md#refraction), and [Flow](../drs/cdspmeshfile.md#flow) describe the stored blocks, not a complete engine shader specification.

## Related Guides

- Start with the [Object Creation Guide](object_creation_guide.md).
- For unit-specific export and animation setup, see the [Unit Creation Guide](unit_creation_buide.md).
- For building and state-based mesh setup, see the [Building Creation Guide](building_creation_guide.md).