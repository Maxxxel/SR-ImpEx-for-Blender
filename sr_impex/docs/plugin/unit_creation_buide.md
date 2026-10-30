# Unit Creation Guide

Create and export an animated unit with the SR-ImpEx Blender plugin. For static or animated props, use the [Object Guide](object_creation_guide.md).

For a new unit, use **DRS Editor → Model Setup → Set Up Model → Unit**.
Follow the [Object Guide](object_creation_guide.md) for shared mesh, UV and material setup.
Use **Animated Unit** as the export type for this workflow.

## Before You Start

A unit needs:

- a deform armature and its skeleton/rest pose;
- render meshes with an Armature modifier referencing that deform armature;
- vertex groups that match the intended deform bones, with valid skin weights;
- Blender actions and animation metadata appropriate to the target asset.

Each vertex can use up to `4` bone influences. On the temporary export copy,
the exporter excludes groups that do not match skeleton bones, keeps the four
strongest bone weights and normalizes their sum. The original Blender mesh and
its modifier-mask groups remain unchanged. Review export warnings: unweighted
vertices are not automatically assigned a guessed bone. Check deformation
after a fresh import, since limiting weights can change the result.

To check before exporting, select the skinned mesh or meshes in Object Mode
and choose **DRS Editor > Animation Set Editor > Skinning > Check Skin Weights**.
The panel reports vertices with no matching bone weights, more than four bone
influences, non-normalized bone weights and non-bone groups. Non-bone groups
may be intentional modifier masks; the export copy excludes them, but the
inspector does not remove or modify anything. The result is a snapshot: run
the check again after editing weights or changing the selection. After a
check, the **Unweighted**, **Over 4**, and **Unnormalized** buttons select the
matching vertices on the active skinned mesh and enter Edit Mode so you can
locate them. These buttons replace that mesh's current vertex selection and
deselect other meshes before entering Edit Mode, but do not alter weights.

The CGeo collision/query mesh welds coincident positions. If those positions
have different bone weights, its skin record can keep only one weight set; the
export log warns and retains the first weighted set. Make the corresponding
weights agree or separate the positions, then verify collision/query behavior
in the editor. Render meshes still have their own per-mesh skin streams.

Put the deform armature in a direct child collection named `Armature_Collection` and render meshes directly in `Meshes_Collection`. Start from an imported, compatible skeleton when possible; changing a skeleton/rest pose without checking the skin and animations can break their agreement.

### GO and rig relationships

> **Recommended practice:** Keep the armature and meshes in one consistent model coordinate convention. When using `GameOrientation` (GO), leave the armature under the model's helper and keep skinned meshes attached to their deform armature. Parenting before modeling is convenient, not a required order of operations.

Do not reparent every skinned mesh directly to GO just because a static mesh can be authored that way. Bone-attached locators also stay attached to bones. Avoid applying transforms to GO, the armature, or an existing bound rig as a blanket rotation fix; changes to a rig need animation and skin validation, not just a still-frame check. See [GameOrientation and adding meshes](object_creation_guide.md#where-to-put-your-meshes).

![Armature, skeleton, and skin overview](https://i.gyazo.com/883689b7da73bc1a30636faf6d42d121.png)

## 1. Set Up the Required Locators

A unit also uses locators.

![Locator overview](https://i.gyazo.com/5c17e19a5660a258d9ae6a575e3e11ff.png)

The following are common starting points, **not a universally enforced minimum set**. Match the needs of a comparable working unit and its gameplay resources. Add them through **DRS Editor > CDrwLocatorList** with the top-level `DRSModel_...` collection active:

- `HealthBar`: a health-bar/UI position, commonly left without a bone parent.
- `Hit`: a hit-related point; bone attachment depends on the asset.
- `Projectile_Spawn`: a projectile-origin position/orientation where the asset uses that role.

Adding a locator alone does not define a projectile, damage rule, or gameplay ability.

![Minimum locator setup](https://i.gyazo.com/24af20064e578abefbfbf9a788a30873.png)

Use this order to avoid losing locator placement:

1. **Add** an entry or choose an existing one, then set **Type**, **File** if needed, and **Parent**. A bone parent makes it follow that bone; an empty parent field is a model-root point.
2. Click **Update parent and remove transformations** to commit the metadata/attachment. **This resets position and rotation**, so do it before final placement, not after.
3. Move and rotate the scene locator to its intended point. Scrub an animation if it is bone-attached.
4. Make the model root active again and click **Sync from Scene**. This writes scene transforms/attachments into the model's saved locator data; it is not just a UI refresh.
5. Save the `.blend` file. Export reads the saved locator data, not an unsynchronized scene marker.

> **GO note:** A non-bone locator can use the model's GO convention; a bone locator must remain bone-local. The editor manages this distinction. Do not manually reparent every locator to GO or use the parent-reset button as a keep-transform operation.

See the [Advanced Locators Guide](advanced_locators_guide.md) for supported types, resource references, multiple-model selection, and the difference between changing metadata and syncing scene transforms.

## 2. Set Up Unit Animations

For the selected animation variant, **DRS Editor > Animation Set Editor**
provides Clip Settings and playback. Text events and Target IDs are in the
collapsed **Advanced SKA Data** section; their usage is not fully verified. **Play** sets
the Blender scene range and frame rate automatically; **OK** in Clip Settings automatically fits the stored clip
range to include the keyed subframes without moving keys. Review the range afterward, especially
when retiming an imported action. SKA text markers are separate from the
AnimationSet markers described below: neither event system is executed by the
Blender preview. See the [Advanced Abilities Guide](advanced_abilities_guide.md).

For cubic curves, SKA has one tangent per key while Blender can use different
incoming and outgoing handle slopes. Prefer aligned handles, and reimport the
exported clip to check motion between keys, especially after adjusting handle
lengths or using keys close together on subframes.

Use the animation modes required by the unit's existing gameplay setup.

The editor's initialization template provides a useful starting list, not an exporter-enforced guarantee that every unit needs exactly these animations:

- `Idle`
- `Walk`
- `Run`
- `Spawn`
- `HitFromBack`
- `Cheer/Emote`
- `HitFromFront`
- `Die`
- `HitFromLeft`
- `HitFromRight`
- `PushBackStandUp (Loop)`

Loop animations have three parts: start, loop, and end. The loop section should be the repeated part. A good example is a unit being pushed back continuously by wind and staying inside the same repeated motion.

There are more animation types available. Check the **Animation Set Editor** and a comparable working asset for the relevant set. Entries marked **Not yet Supported**, such as ModeSwitch, are not an authoring promise.

### Actions and saved metadata are separate

1. Create or import the Blender actions on the deform rig, then choose their references in the AnimationSet rows.
2. Use **Init → Unit** to add the Idle, Walk, Run, Spawn and Die starter mappings. Existing entries are kept unless you enable **Replace Existing Mappings**. Assign an Action to each entry you need.
3. Choose animation modes, variants, weights, and any markers, then click **Save** in the AnimationSet editor to persist them to the model collection.
4. Save the `.blend` file as well. **Reset** reloads saved metadata; it does not save pending edits.

An action existing in Blender's Action list does not mean it is referenced by the saved AnimationSet or will be included in `Export All SKA Actions`.

![Animation Set Editor](https://i.gyazo.com/973918d3bf7244dfcfdc5057d3266531.png)

## 3. Add Animation Variants

You can create multiple variants for the same animation and assign a weight to each one.

For example, if you want two idle animations and one should play most of the time, you can assign weights like this:

- default idle: `80`
- special idle: `20`

Using a total of `100` makes the intended weighting easy to review. The editor accepts individual values from `0` to `100`, but does not automatically normalize or validate the total.

Other important settings:

- `Allows IK`: enabled for new variants by default; metadata, not an IK-baking command.
- `Force No Blend`: disabled for new variants by default; preserve deliberate imported settings.

For a unit that uses melee attacks, configure the appropriate attack mode and marker relationship required by that asset. The add-on stores the animation/visual metadata; it does not create the gameplay ability itself.

## 4. Add Markers for Important Animations

Some animations, especially `Spawn` and `Attack`, need a marker.

Markers store an event position and normalized point in an animation. Assets can use them for spawn, attack, and other visual/gameplay timing, but the add-on does not validate when an external gameplay system makes a unit controllable or applies a hit.

**Marker Time is a fraction from `0` to `1`, not seconds or a frame number.** In a `5`-second clip, `0.6` means `3` seconds. To target `0.6` seconds in that clip, enter `0.12`.

Match the marker's animation type/visibility job to the intended mode and preview the relevant variant. Do not assume an identically named Blender action automatically creates that relationship. The editor derives timing metadata from the referenced clip and marker settings; the displayed millisecond timing fields are read-only.

![Marker timing example](https://i.gyazo.com/4d53b0c5410240c9561d1979442662d0.png)

Useful marker tools:

- `Display Marker`: previews the animation at the selected marker time
- `Play Marker`: plays the animation until the marker time so you can fine-tune the timing
- `XYZ`: sets the exact 3D marker position

Place the marker where the target asset expects the event position, such as a weapon or hand attachment point. Check its displayed position against the animated pose rather than only against the rest pose.

A marker and a `Projectile_Spawn` locator may use related positions, but they are separate data. Moving one does not automatically update the other; save AnimationSet edits and sync locator edits through their respective editors.

![Marker position example](https://i.gyazo.com/760291a354e81c46101851736776d15f.png)

For more animation types such as spell casting or ranged attacks, check the [Advanced Abilities Guide](advanced_abilities_guide.md).

## 5. Configure Basic Unit Settings

In the upper section of the unit editor, you can configure basic values such as walk speed, run speed, and additional settings for flying units.

Use the [Basics settings reference](advanced_abilities_guide.md#basics-motion-in-the-game) for walk/run reference speeds, terrain alignment and flight settings.

![Basic unit settings](https://i.gyazo.com/2d4d14f733d4b6047f402bdb4e0a6c2d.png)

## 6. Add Audio and Effects

`EffectSet` is used for sounds and effects. There is a separate [Advanced Effects Guide](advanced_effects_guide.md) for the full system.

For the basic workflow, it is enough to look at audio for `Attack` and `Spawn`.

![EffectSet audio example](https://i.gyazo.com/e66241d71fc57b9eae110f21753d8c31.png)

EffectSet **Time** also uses a normalized `0..1` range. Match the animation key and variant as well as the time when aligning a sound with a marker. `0.6` means 60% of the selected clip, not 0.6 seconds.

Use the EffectSet editor's **Save** to persist changes separately from the AnimationSet and locator data. Imported sound references are resource strings; the editor does not automatically package every referenced file or create a game sound bank.

For the exact fields, preview limits, sound types, and reference rules, use the [Advanced Effects Guide](advanced_effects_guide.md).

## 7. Export the Unit

Select a model mesh and choose **DRS Editor → Model Setup → Export DRS**.

1. Choose **Animated Unit**.
2. Enable **Export All SKA Actions** when you want the clips referenced by the **saved AnimationSet** written alongside the DRS. It does not mean every Blender action, and an EffectSet-only reference is not enough to select a clip.
3. Choose **Model Name Prefix** explicitly. The actual default is **No Prefix**. `Model Name Prefix`, `Folder Name Prefix`, and `Keep Existing Prefix` serve different naming workflows; verify the resulting names and saved references rather than renaming output files independently.
4. Leave **[DEBUG] Export SKA Tangents** enabled for Hermite tangent export unless you deliberately need a stepped/flat debugging comparison. It cannot repair missing keys or an unbaked control rig.
5. Use the ordinary UV, normal, triangulation, mip-map, and vertex-budget checks from the object guide.

> **Rig export limitation:** The writer exports the deform armature, not an armature whose name contains `Control_Rig`. It reads deform-bone location/quaternion F-curves and does not automatically bake constraints, IK, or NLA results. A successful control-rig preview is therefore not proof that the exported action contains the same motion. Prepare compatible keyed deform actions on a working copy and verify a fresh SKA import; do not destructively apply transforms or bake away the only copy of your rig.

![Animated export settings](https://i.gyazo.com/0c0baa604baf8b688dba0920f478c1af.png)

## 8. Final Export Result

A successful animated export produces the `.drs`, generated `.dds` maps, and the referenced `.ska` clips when action export is enabled. Check the message log and actual files; missing or unresolved action references must not be mistaken for a complete result.

### Animation round-trip checklist

- [ ] The deform armature, skin, and saved AnimationSet refer to the same model and skeleton.
- [ ] Weights were checked across representative poses, with no more than four influences per vertex.
- [ ] AnimationSet and EffectSet edits were saved; locator scene changes were synced.
- [ ] Required action references resolve, and exported filenames match the chosen prefix policy.
- [ ] Marker and sound times were interpreted as normalized fractions.
- [ ] The exported DRS and clips were imported in a separate scene using the same `Apply Transform` display setting.
- [ ] Animations were checked over their full duration, including looping and bone-attached locators, not just in a still pose.
- [ ] Final behavior was checked in game; preview playback does not prove an external ability or sound resource is configured.

If the mesh is rotated correctly but the animation is not, inspect the deform action, rest pose, and rig/export relationships before changing GO. If a marker or locator appears in Blender but is missing from the export, check the selected model type and the relevant editor's saved metadata.

## Related Guides

- [Object Guide](object_creation_guide.md)
- [Building Creation Guide](building_creation_guide.md)
- [Advanced Locators Guide](advanced_locators_guide.md)
- [Advanced Abilities Guide](advanced_abilities_guide.md)
- [Advanced Effects Guide](advanced_effects_guide.md)
- [Advanced Shading Guide](advanced_shading_guide.md)
- [Artist Material Workflow](material_artist_workflow.md)
