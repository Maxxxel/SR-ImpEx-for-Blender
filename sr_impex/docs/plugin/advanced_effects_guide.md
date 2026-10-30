# Advanced Effects Guide

Use **Effect Set Editor** to attach existing effects and sounds to a model's animations. Create new effect assets in the external Effect Editor.

For building damage, use **BMG Editor â†’ Building Editor â†’ Build Damage Preview**. Its Damage slider combines mesh states, scratch, destruction debris and FX. See [building damage preview](building_creation_guide.md#preview-damage-and-destruction).

## 1. Set Up the Asset Library

Open **Edit â†’ Preferences â†’ Add-ons â†’ SR ImpEx**.

- Set **Skylords Reborn Folder** to your game installation.
- Optionally set **Effects Folder** to a loose effect library, such as `Mods/Unpack/bf1/gfx/effects`. Use this to preview your own assets before installing them.

Choose the game installation folder containing `base/pak`, rather than the `pak` folder itself. Both library paths are saved automatically and restored after Blender restarts, even when Blender's automatic preference saving is off. Leave the optional Effects Folder empty if you only use game assets.

The add-on also keeps a shared settings copy outside Blender's version-specific profile. It can recover the paths when that profile is reset or replaced. Clearing a path deliberately clears the saved value too.

The library reads existing files. It prefers loose assets and can find effects and sounds in the game's current PAK archives. It does not modify the game files.

The first search builds a file index and saves it in your user cache. It is reused across models and Blender restarts. Searches and preview builds check file-system metadata: changed folders are scanned again, and changed PAK directories are read again. Unchanged archives are not unpacked or reindexed. All current archives in `base/pak` are eligible, including building assets.

**Refresh Effect Library** forces a fresh index if needed. Corrupt or outdated cache data is rebuilt automatically. The cache contains filenames and archive locations; textures, meshes and sounds are loaded only when needed.

## 2. Add an Animation Event

1. Select a mesh belonging to your imported model.
2. Open **DRS Editor â†’ Effect Set Editor**.
3. Add an entry and choose its **Action**. Each entry belongs to one SKA animation.
4. Add a keyframe and choose its **Type** below.
5. Set **Time (0..1)**: `0` is the clip's start, `0.5` its middle and `1` its end.
6. Add a resource variant. Open **Effect Selector**, search by name, and click **Use Resource**. You can also enter the filename directly.
7. Keep one variant at **Chance 100%** while testing.
8. Click **Save**, then save your `.blend` separately.

Changing the Action retargets the entry. Imported sound containers and header data are retained when you save, although the panel does not yet let you edit every sound container.

**Group** filters the shared resource picker using name/path hints such as Fire/Smoke, Water/Ice, Persistent/Ambient and Buildings/Destruction. Resources can belong to several groups. Choose **All Resources** when unsure. The same picker and preview library are available in [Locator Editor](advanced_locators_guide.md#choose-and-preview-an-effect).

### Choose the Event Type

| Type | Use |
| --- | --- |
| Sound | Play a sound resource. |
| World FX | Spawn an effect at the model's position at that moment, with an offset. |
| Linked FX | Use an effect whose setup follows source/target nodes. Attachment depends on the effect itself. |
| Fade Out Persistent FX | Fade an existing locator effect with the matching resource name. |
| Fade In Persistent FX | Fade an existing locator effect with the matching resource name back in. |

Fade events operate on an existing effect; they do not spawn another copy. Their **Fade Duration (s)** controls how long the fade takes.

For ordinary events, **Offset** adjusts placement. It does not select a bone or replace a locator. Reuse a working model/effect setup when you need a particular attachment behavior.

### Resource Variants

Variants are alternative resources for the same event, not simultaneous layers. For two alternatives, use chances such as `80` and `20`, totaling **100**. The engine does not scale these numbers automatically: `4 / 3 / 3` means **90% silence or no effect**, while `40 / 30 / 30` always selects one. The panel shows the unused chance. **Normalize to 100%** scales the current proportions when you want an event every time; imported values stay unchanged until you edit them. Avoid totals above 100, which can make later variants unreachable.

To play two effects or sounds together, create **two events at the same Time**, each with its own resource variant.

## 3. Check the Resource

Open **Effect Selector**. Search at the top or choose a category on the left. Categories such as Fire, Water and Buildings are hints from filenames, not engine effect types.

Select a resource and click **Preview** to audition it on the model. The existing FX preview is paused during the audition and restored when you close the selector. **Cancel** keeps your original resource; **Use Resource** puts the selection in the editable filename field. Save the EffectSet or locator separately to include it in export.

Sound events show audio resources instead of FXB files. Missing or ambiguous references produce an error when previewing.

### Play the Effects in Blender

In **Object Mode**, click **Update Preview**, then press **Space** to play the normal scene timeline. Choose an animation entry to preview its scheduled effects. Persistent building/unit locator effects can also be previewed when there is no animation entry. Rebuild after the current render finishes.

- **Audio** includes sound cues. Multiple cues can overlap. Sound-set loops repeat through the preview range.
- **Engine Chances** uses the saved chances. The preview makes repeatable random choices without adding an exported seed setting.
- **Selected Variant** auditions the highlighted variant of the highlighted event, even if its chance is zero. Other events keep their normal chances. This changes only the preview.
- **Clear Preview** removes generated effects and their audio strips for this model. It leaves your model and unrelated audio alone.
- **Live Update** is on by default. After the first **Update Preview**, changes to the selected clip, event timing, volume, pitch, FX offset or variants update automatically after a short pause in editing. Playback stays running at its current frame. Large effects can pause briefly while rebuilding; updates wait until rendering finishes. **Clear Preview** stops live rebuilding. Rebuild the preview after reopening a saved `.blend`.

A clip without assigned effects is normal: the preview reports this as information. The same applies when Audio is off for a sound-only clip, or when the preview picks the unused part of the event's chances. Missing files and effects without supported preview components remain errors; the message names the resource, and the model's **Effect Preview Report** in Blender's Text Editor contains details. A persistent locator effect does not need an imported Action unless you also preview timed animation events.

For sound events, **Pitch Min/Max** are rate shifts: `0` leaves playback unchanged, `0.1` adds 10%, and `-0.1` subtracts 10%. The preview picks a repeatable value between them. Both pitch and sound duration change. Values must produce a positive playback rate to be previewed.

Controls marked **Export Only** are saved for the game but do not affect the Blender preview: falloff needs positional audio, Interruptible needs gameplay animation interruptions, and Stored Condition is retained without a verified filtering effect in this timeline path. Editing these fields does not rebuild the preview. Use the Map Editor to check gameplay-dependent behavior.

Generated previews live outside the model's export collection. They are not exported as extra meshes. Do not edit those generated objects; edit the model's EffectSet or the original effect in the external Effect Editor.

Switching to another model or importing a new model stops the previous model's preview audio. Sound strips you added yourself are kept. Build the selected model's preview again to hear its effects.

Cycles transparency depth is adjusted automatically for overlapping effect sprites, and restored when the last preview is cleared. Very dense overlaps can reach Blender's hard limit; the preview report lists this case. This setting fixes early ray termination without changing the material's transparency.

Legacy flame emitters, including Firedancer's head and hands, use smooth transparency automatically in EEVEE. They should look like soft overlapping flames rather than a cloud of dotted pixels during playback. After updating the add-on, click **Update Preview** to rebuild older preview materials. The source textures and exported effects stay unchanged.

### What You Can Check

| Part of the effect | Blender preview |
| --- | --- |
| Lights, billboards and nested effects | Placement, animation, color and opacity. Light brightness is approximate. |
| Effect meshes | Geometry and the supported DRS material shading. Animated effect meshes also play their SKA through the effect's animation curve. Default refraction meshes sample the background in camera renders and follow the FX fade. The viewport uses a simpler refraction shader. |
| Material animation | Supported scalar and color curves drive the existing material preview. Parameters without a visual route are listed in the report. |
| SFP particles | Starting colors, size, lifetime, rotation, weighted atlas tiles and render ramps. Particles keep their placement at emission and use the stored mass and system damping. Counts, random sampling and reduced motion caches remain bounded approximations. |
| Legacy emitters and satellites | Legacy emitters use traced particle motion, color, opacity, size and supported blend controls. Each component follows its own activation window. Distortion-only particles do not produce colored flames; their heat haze is not reproduced. Scene fog and satellite-specific motion remain incomplete. |
| SFP force fields | Cached attraction, inner/outer sphere boundaries, distortion, uniform drift and vortex motion. The random generator and integration are preview substitutes. |
| Trails | A ribbon from cached attachment motion, with start/end width, lifetime and fade. Spline interpolation, trail ramps and distortion are not reproduced. |
| Audio | Overlapping cues, sound-set loops and pitch variation, and effect volume curves. Spatial falloff and changing pitch during a cue are not reproduced. |
| Persistent locator effects | Named source-bone attachments and fade events. The special Health Bar and Projectile Spawn source slots use model locators; when several match, the preview uses the first. Advanced source/target links still need an engine comparison. |
| Terrain decals | A subdivided surface follows the cached scene terrain. Static decals can also project onto stationary model surfaces. Projection and shading remain approximations of the game. |
| Water decals | Animated 3D DDS texture slices follow the effect's animation-time curve. Placement uses a flat water surface; scene waves, fog and shadow variants are not reproduced. |
| Physics pieces | Cached falling, force, mass, torque and collision motion. Box-based inertia/contact proxies substitute for the game's collision shapes and solver. |
| Physics groups and point forces | Ground offsets, within-group collisions, and attraction/repulsion through range and power curves. |
| Legacy wind Force nodes | Retained in the resource report; they do not drive the preview simulation yet. |
| Camera shake | Reported without moving the artist's camera. |

Additive, screen, multiply and alpha blending have separate preview paths. Premultiplied alpha and blends that depend on the already rendered background remain approximations.

Effects with glow automatically receive a separate render pass and Blender bloom. No extra artist controls are needed. The preview copies your compositor and restores the original when cleared; a replacement you select yourself is kept. Set up your render before clicking **Update Preview**. Blender's bloom shape and brightness differ from the game, so check the final glow in the Map Editor.

Water volume textures are decoded when the preview is built. Playback and scrubbing reuse cached slices. Large volumes use fewer slices to bound memory; the report lists this reduction. Ordinary 2D water textures use a static fallback. Water lighting is approximate.

To preview terrain contacts, place a terrain mesh outside the model's export collection, then click **Update Preview**. The preview snapshots visible environment meshes without changing them. Without an environment surface, physics and terrain decals use a flat ground plane at the model origin. Static decals can project onto stationary model surfaces; animated figures are excluded to prevent stretched projections. Rebuild after changing the environment geometry.

Physics uses the traced default gravity and force scaling, but its box inertia and collision response differ from the game. Check final contacts, stacking, advanced links and unsupported shader behavior in the Map Editor. Continue editing the effect itself in the external Effect Editor; the Blender tools edit the model's EffectSet references and timing.

SFP particles, trails, force fields and physics cache motion when you click **Update Preview**. Rebuild after changing the model animation. Playback and scrubbing reuse that cache. Unchanged decal projections are reused too. Long clips or large particle systems use reduced sampling to keep memory use bounded. A model preview is capped at 8,192 particle sprites and 64 simulated debris pieces; the report tells you when a limit reduces the preview.

SFP flames that produce no glow use smooth transparency automatically. Emitters that produce glow keep the separate glow pass. These choices come from the effect data and need no artist controls. Rebuild older previews after updating the add-on.

For refraction meshes inside effects, click **Update Preview**, use **Add Render** if your model has no camera or lights, then press **F12**. The render automatically uses the refraction texture to distort the background, including the effect's animated fade. The normal viewport still uses a simpler glass-like shader. A visible background makes the distortion easier to judge. The extra render passes take more render time and are removed with **Clear Preview**; the previous compositor is preserved. Only the frontmost distortion surface is sampled, and the texture's blur/mip control is not reproduced. Compare overlapping haze and final lighting with the Map Editor.

Check **Effect Preview Report** in Blender's Text Editor for the selected assets' limits. Always test the exported result in the Map Editor; the Blender preview is not yet a visual match for every effect type.

A successful inspection confirms that the file can be read. It does not prove that every dependency is installed or that the effect will attach correctly in game.

## 4. Export and Test

1. Save EffectSet and AnimationSet changes, then save the `.blend`.
2. Export the model and its required SKA clips. An EffectSet reference alone does not export its SKA; add the appropriate AnimationSet mapping or export that clip separately.
3. Install any custom effect, texture and sound assets separately. The DRS stores references; it does not bundle them.
4. Reimport a copy of the export and check its entries. Then test it in the Map Editor.

## Common Problems

| Problem | Check |
| --- | --- |
| No effect visible in Blender | Click Update Preview, check the resource paths and current animation time, then read Effect Preview Report for missing dependencies or unsupported components. |
| Resource not found | Check the library folders and filename. A sound may reference an XML sound set or require an SNR/SNS pair. |
| Resource name is ambiguous | Use a unique resource name or remove duplicate test assets from your configured library. |
| Event happens at the wrong pose | Time is a fraction of the entire clip, not seconds or a frame number. |
| Only one animation variant has an effect | Add entries for each SKA clip that needs the event. |
| Fade does nothing | Confirm that an existing persistent locator effect uses that resource name. |

For animation mappings, see the [Advanced Abilities Guide](advanced_abilities_guide.md). For effect attachment points, see the [Advanced Locators Guide](advanced_locators_guide.md).
