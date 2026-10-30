# Artist model pipeline

This is the starting point for making or editing Skylords Reborn assets with
SR-ImpEx in Blender 5. The plugin exports game data and supplies previews for
some of it; the Map Editor and game are still needed to validate runtime
behavior. Save a working `.blend`, keep original game files untouched, and
export to a separate folder.

## 1. Choose the asset and starting point

| Your goal | Start here | Output to check |
| --- | --- | --- |
| Static decoration or object | [Object Creation Guide](object_creation_guide.md) | DRS, texture files and any intended collision |
| Animated unit or rigged prop | [Unit Creation Guide](unit_creation_buide.md) | DRS, referenced SKA clips and textures |
| Building with damage states | [Building Creation Guide](building_creation_guide.md) | BMG, state DRS files, textures and referenced resources |
| Create or edit a standalone state-resource set | Choose **New BMS** or Open under **BMG Editor > BMS State Resources** | A BMS copy and its separately exported DRS/FX dependencies |

For an existing asset, import a comparable DRS or BMG with its resources in
place. Review the import dialog: **Clear Scene** can remove the current scene.
Save a copy before editing. For a new asset, use the scene or building setup in
the guide for that asset. The named collections select export contents;
parenting controls transforms. Inspect both when arranging a model.

## 2. Model, rig and animate

1. Put render meshes in the expected `Meshes_Collection`, create an active UV
   layer, and use a separate mesh for each intended exported material.
   Geometry, bounds, tangents and stream counts are generated on export.
2. For a rigged asset, use a deform armature and matching vertex groups. Review
   skinning with no more than four influences per vertex. Test poses throughout
   every clip, not just the rest pose. Select the skinned meshes in Object Mode
   and use **DRS Editor > Animation Set Editor > Skinning > Check Skin Weights** for a
   non-destructive summary before export.
3. Create actions on the deform rig. Use **DRS Editor > Animation Set Editor**
   to select an animation and edit its clip FPS, duration, loop and interpolation.
   Confirm the clip settings, then play or scrub to inspect motion. If a control
   rig, IK or constraints drive it, prepare keyed deform actions on a copy and
   verify the reimport: the exporter does not automatically bake the rig.
4. Configure and **Save** AnimationSet and EffectSet edits, and **Sync from
   Scene** after placing locator helpers. These are separate from Blender action
   keys. Referenced SKA clips must be included on export.

The selected clip's advanced settings can edit text markers and target IDs.
The importer also preserves tracks
whose bones are absent from the current skeleton. Event dispatch, target/morph
mapping and the special alpha track are not simulated as game behavior in
Blender. See the [Advanced Abilities Guide](advanced_abilities_guide.md)
before changing these advanced fields.

## 3. Set up materials and inspect the model

Select a render mesh and use **DRS Editor > Material Editor** to
create or upgrade its material and choose a handler. Assign the enabled maps
and review the flags. For the inspected Default material, parameter-map
channels are **R smoothness, G metalness, B flow mask or reflection input
depending on the shader variant, and A emissivity**. Other material handlers
may use different texture roles. Do not infer a map's meaning from its filename
alone. The [material workflow](material_artist_workflow.md) covers separate
maps, automatic flag calculation, texture conversion and all current limits.

For a compatible static **Textured** or **SimpleTextured** mesh, **Create SR
Vertex Colors** adds an editable `SR Color0` point attribute and enables the
material's vertex-color flag. Imported single-stream `0x28001` meshes retain
their color bytes. This stream has no normals; skinned and multi-stream
variants remain unsupported. Check the RGB interpretation in the Map Editor.

For a flow material, assign the relevant maps and parameters and **play or
scrub the timeline** to see the preview change. The timeline must advance;
a paused frame remains still. For a complete render setup in the current
scene, select a model mesh and click **DRS Editor > Render Setup > Add
Render**. Its Render collection supplies camera, lights, ground and world
settings for the whole visible model. For a camera refraction comparison, select the
model meshes and create a scene using **DRS Editor > Render Setup**.
After changing refracting objects, use **Refresh Screen Refraction Preview**
and render from the preview camera. This is a controlled approximation: the
engine's B-channel refraction blur, lighting and render ordering are not fully
recreated. Verify both effects in the Map Editor.

## 4. Add nonvisual resources and export

Add collision primitives only when appropriate for the export type, fit them
in Blender, then reimport and inspect their placement. Collision shapes do not
by themselves establish walkable bridges or gameplay rules. Place locators
for the roles required by a comparable asset; effects, sounds, projectile and
ability behavior depend on engine resources, not just helper positions.

Use the DRS export type appropriate to the target. For units, save metadata and
enable export of the referenced SKA actions when needed. For buildings, use
**BMG Editor > Building Authoring & Export** to create or edit states and
export the package; inspect its dependency manifest. For standalone BMS files,
the BMS panel edits references and can import a state DRS for visual editing,
but the BMS export does not package that DRS or its FX automatically. Set its
**Resource directory** and use **Check State Resources** to find local missing
references before delivery. Engine-resolved references may need a different
resource root; the check establishes local file availability only.

Unknown material records and source-only metadata can often be preserved;
they do not acquire a speculative visual effect in Blender. Some resource
classes and full multi-cell building preview are still incomplete. The
[advanced guides](advanced_abilities_guide.md) identifies the applicable preservation,
external file-tool or editor-test path for each family. A hex/template edit
should be made on a separate copy and followed by a fresh import and engine
test, since arbitrary values are not automatically validated by Blender.

## 5. Validate a fresh export

- Export to a new folder and review reported errors, filenames and referenced
  DRS, SKA, DDS and FX resources. Save the `.blend` separately.
- Import the exported result into a fresh scene and check geometry, UV seams,
  materials, weights, full animation ranges, locator positions and collision.
- For a building, check each state and the dependency manifest. Shared-armature
  multi-cell placement is not fully reproduced in the current Blender preview.
- Test the result in the Map Editor and, when appropriate, in game. Compare
  flow, refraction, animation events, collision and lighting against the
  intended behavior; a successful Blender render is not a runtime test.


### Edit an animation in one place

In **Animation Set Editor**, choose an ability and its animation variant. The
selected Action owns **Clip Settings**: frame rate, first frame, duration,
loop/clamp addressing and interpolation. **OK** automatically derives the clip range
from its existing keys; it does not move keys. With keys present, the first
frame and frame count are calculated and read-only. Without keys, the stored
range remains editable. Changing FPS changes playback
duration without resampling keys. Clip edits apply to this selected Action even
when a different animation is currently playing. Shared Actions share these
settings across all variants that reference them.

**Advanced SKA Data** is collapsed by default. It preserves and edits SKA text
events and Target IDs, but their practical authoring and target mapping are not
fully verified. Blender does not execute these engine events. These SKA events
are separate from AnimationSet spawn/cast markers. Debug View additionally shows
preserved tracks and version/completeness controls. Skin weight tools remain
under **Animation Set Editor > Skinning** when a skinned mesh is selected.
The separate SKA Editor panel has been removed. Restart Blender after updating.

AnimationSet **Play** respects the selected SKA's Loop/Clamp addressing: Loop
repeats the preview range; Clamp stops at its endpoint. In Start/Loop/End
previews, **Loop** repeats just that segment. Start, End, Cast, Resolve and
marker previews play once. Space remains Blender's global timeline playback.
