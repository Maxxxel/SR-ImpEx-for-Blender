# Advanced Abilities Guide

Configure attack, casting, and channeling **animation metadata** after completing the [Unit Creation Guide](unit_creation_buide.md). For timed audio and visual resources, use the [Advanced Effects Guide](advanced_effects_guide.md); for attachment points, use the [Advanced Locators Guide](advanced_locators_guide.md).

> **Scope:** an entry called an “Ability” in this editor maps a visual job to an animation. It does not create a gameplay ability, projectile behavior, damage, targeting rules, cooldown, or resource cost. Those must already be configured in the game's data. The workflows below concern **DRS** export; BMG animation/effect export is incomplete and is not an equivalent route.

## 1. Know Which Data You Are Editing

| Data | What it contains | Where it is authored |
| --- | --- | --- |
| Blender Action / `.ska` | Bone motion and clip timing | Action Editor; `Clip Timing...` for timing metadata |
| `AnimationSet` | Visual job (`vis_job`), mode, weighted Action variants, clip segments, markers | `AnimationSet Editor` |
| `AnimationTimings` | Timing category/tag, variant index, millisecond timings, direction, marker reference | Generated through the editor's per-variant `Timing` section |
| `EffectSet` | Audio/FX references scheduled against a named SKA clip | `EffectSet` panel |
| Locators | Model or bone attachment points | `CDrwLocatorList Editor` |

An animation marker, a locator, and an EffectSet keyframe are separate records. Matching their time or position does **not** automatically link them or create an in-game event.

### Templates Are Not Universal Requirements

`Init` populates the catalog's base template: `Idle`, `Walk`, `Run`, `Spawn`, `HitFromBack`, `Cheer / Emote`, `HitFromFront`, `Die`, `HitFromLeft`, `HitFromRight`, and `PushBackStandUp` (Start/Loop/End). This is a useful starting point for many units, not an exporter-enforced checklist for every model. Choose mappings required by the existing unit/game configuration; do not add empty entries just to match this list.

An animated prop may need only `Idle`. The **Animated Object** DRS export types retain only visual job `0` (Idle) and remove animation markers and timings. Use **Animated Unit** when the exported model needs attack/cast mappings and their timing data.

Sources: [ability catalog](../../definitions/abilities.py), [editor initialization](../../blender/editors/animation_set_editor.py#L1818), [DRS model-type filtering](../../utilities/drs_utility.py#L5374).

## 2. Work Safely in the AnimationSet Editor

Make the intended `DRSModel_*` root collection active, then open **3D Viewport → Sidebar → DRS Editor → AnimationSet Editor**. When switching between models, save the current model's edits first and use `Reset` to load the newly active model's stored data.

| Control | Actual behavior |
| --- | --- |
| `Init` | Clears the current editor list, then creates the base template. It is not a harmless refresh. |
| `Remove All` | Clears the working list. Save afterward only if that removal is intended. |
| `Save` | Writes working state to the active collection's `AnimationSetJSON`; does not export files or save the `.blend`. |
| `Reset` | Reloads the active collection's stored data, discarding unsaved editor changes. |
| `Mode` | Filters entries by mode. Labels include `Base`, `Special`, `Rest`, and `Rest->Base` when present. |
| `Add Ability…` | Adds catalog components in the current mode; existing `(vis_job, mode)` pairs are not added twice. |
| Ability-row minus button | Removes that mode-key entry. Grouped rows should be checked carefully after removal. |
| Variant `+` / `−` | Adds/removes variants of the selected entry. |

Save a backup before editing imported metadata: the editor reconstructs its supported schema, not every possible unknown field in an original file.

Source: [editor controls and persistence](../../blender/editors/animation_set_editor.py).

## 3. Choose an Existing Visual Mapping

Use the catalog label matching the model's existing game-side behavior. These are actual catalog entries, not new gameplay ability definitions:

| Catalog label | Visual-job components | Timing category / tag |
| --- | --- | --- |
| `Attack` | `MeleeAttack` (`8`); catalog describes it as melee **or ranged** | `Melee` / `0`; marker required by the catalog |
| `Special Melee Attack Ground` | `SpecialMeleeAttack` (`15`) | `Melee` / `114`; marker required |
| `Special Melee Attack Air` | `SpecialMeleeAttackAir` (`16`) | `Melee` / `115`; marker required |
| `Cast (Ground Only)` | `CastGround` (`18`), `CastResolve` (`19`) | `CastResolve` / `0` |
| `Cast (Ground & Air)` | Ground `18`/`19`, Air `22`/`21` | `CastResolve` / `0`; catalog requires identical ground/air timings |
| `PreparedSalvo` | Ground `185`/`186`, Air `187`/`188` | `CastResolve` / `54` |
| `SpecialRangedAir` | Cast `316`, Resolve `317` | `CastResolve` / `148` |
| `Harpoon` | Cast `321`, Resolve `322` | `CastResolve` / `150` |
| `Heal Channel` | Start `177`, Loop `178`, End `179` | `Channel` / `48` |

There is no generic catalog entry named `Ranged Attack`. A regular ranged model can use the existing `Attack` visual job; a specialized model may use one of the named cast/resolve mappings. The timing label `Melee` on `Attack` is not a gameplay switch that makes an attack melee.

Ground-only and ground/air cast entries share visual-job IDs, so they are not independent sets of interchangeable slots. Display labels are inferred from the catalog's ID map and can resolve to the shared ground/air label after reloading.

**Mode switching is not a supported recipe.** The catalog explicitly calls its entry `ModeSwitch (Not yet Supported)`. `SwitchToSpecial` and `SwitchToNormal` are internal component roles sharing job `7`, not independent supported animation types. Although `ModeSwitch` exists in the timing-category enum, that alone does not implement a complete transition workflow. Preserve known working data rather than treating the presence of a label as proof of support.

Sources: [catalog labels, IDs and tags](../../definitions/abilities.py), [timing-category enum](../../definitions/enums.py#L21), [ID-based grouping](../../blender/editors/animation_set_editor.py#L154).

## 4. Assign and Check Every Variant

1. Add the matching catalog entry in the intended mode.
2. Select a variant and choose its **Action**. The dropdown includes Actions from the entire `.blend`, not only the current model. Its shortened display label is not necessarily its datablock name or exported filename.
3. Give each intended variant a weight. `80` and `20` is a useful two-variant convention. Animation weights are individually limited to `0..100` in this UI, but the editor does **not** normalize their sum or reject totals other than `100`. Do not assume a particular engine selection algorithm from the percentage display alone.
4. Review `Allows IK` and `Force No Blend`. New variants default to enabled and disabled respectively; they are metadata flags, not Blender rigging or baking commands. Keep established imported settings unless a deliberate change is needed.
5. Preview **each** variant. `Play` uses the selected variant, not a weighted random sample.

A variant with `<None>`/an empty Action is skipped when constructing the exported AnimationSet. Merely creating an Action or NLA strip does not add it to an ability mapping.

Sources: [variant properties and UI](../../blender/editors/animation_set_editor.py#L1186), [variant export filtering](../../utilities/drs_utility.py#L4736).

## 5. Place Markers and Understand Time Units

The catalog enables the `Marker` section for `Spawn`, `Attack`, and selected special mappings. Casting entries normally use `Cast→Resolve` instead; a marker section is not available for every ability.

| Control | Meaning in the current editor |
| --- | --- |
| `Time` | Fraction of the full Action, `0..1`; **not seconds or a Blender frame number** |
| `Is Spawn Animation` | Stored marker flag; seeded for Spawn, not a general gameplay activation toggle |
| `Position` | Stored XYZ event position; choose it against the pose at the marker time |
| `Direction` | Stored direction vector; also orients the display arrow |
| `Play Marker` | Plays from the Action's start to the normalized marker time |
| `Display Marker` | Assigns the Action, jumps to the marker pose, and shows its arrow in `DRSMarkers` |

For a five-second clip, marker `0.6` is at **three seconds**. To place an event at `0.6` seconds in that clip, use `0.12`. EffectSet keyframe times use the same normalized `0..1` convention, so matching fractions aligns the scheduled moments only when both refer to the same full clip.

Keep these editor units separate from unverified game-tick behavior. Historical notes about 100-ms quantization, a 200-ms Spawn minimum, a six-entry limit, and resolve-phase duration are **research hypotheses**, not confirmed authoring rules. See [AnimationTimings research status](../drs/animationtimings.md#research-notes-are-not-confirmed-engine-limits) before interpreting exported millisecond fields.

For a weapon or hand event, inspect the pose with `Display Marker`, then edit the marker's numeric Position/Direction. Markers are not bone-bound locators, and dragging the helper arrow is not a supported “sync back” workflow: the stored UI values remain authoritative. A marker can be near a projectile attachment point, but neither creates nor automatically links that locator. Retain imported armature/locator parenting; do not reparent bones or locators just to match the helper arrow.

### Generated Millisecond Timings

The `Timing` section shows read-only `Type`, `Tag ID`, `Is Enter Mode`, `VariantIndex`, `Cast (ms)`, `Duration (ms)`, `Used FPS`, and `MarkerID`; its Direction remains editable. Change clip timing and the normalized marker/split controls rather than attempting to type new millisecond values.

For timing recomputation, the editor uses the Action's `frame_length` and `original_fps` when available, otherwise its frame-range span and effective scene FPS (`fps / fps_base`). In this implementation:

- `Duration (ms)` / exported `resolve_ms` is the **full clip duration**.
- Exported `cast_ms` is that duration multiplied by marker Time, or by `Cast→Resolve` when no marker is present.

These are the add-on's calculations, not proof that a specific game-side damage/projectile event uses either field in a particular way. Some older format documentation describes different meanings and editable timing fields; the current editor code is authoritative for these controls.

Sources: [marker controls and timing display](../../blender/editors/animation_set_editor.py#L2453), [timing recomputation](../../blender/editors/animation_set_editor.py#L1119), [timing serialization](../../blender/editors/animation_set_editor.py#L1750), [binary marker fields](../../definitions/animation_definitions.py#L170).

## 6. Cast/Resolve and Start/Loop/End Workflows

### Cast or Ranged Release Example

1. Use the existing model's mapping: for example `Attack` for its regular attack or `Cast (Ground Only)` for an existing generic cast hook.
2. Assign the full clip, including preparation and follow-through.
3. For `Attack`, set marker Time at the visual release/contact pose. For a cast pair, set `Cast→Resolve` at the transition you want to inspect.
4. Use `Play Cast` and `Play Resolve` to inspect the two ranges of the selected full Action. Resolve rows are hidden in the main ability list.
5. Configure the required locator separately, then add audio/FX keyframes to the corresponding clip in [EffectSet](advanced_effects_guide.md).
6. Save, export, and test in the game configuration that actually invokes this visual job. A plausible preview does not create a functioning spell or projectile.

Action selection is propagated between corresponding Cast/Resolve entries. Ground and air channels are separate; explicitly verify their clips and matching timings rather than assuming one edit updates both.

### Loop Set Example

For `PushBackStandUp`, `Heal Channel`, or another catalog Start/Loop/End group, the UI shows one **Loop Set** row. Use a full clip with a preparation, repeatable middle, and exit. Set `Start.end` and `Loop.end`, then inspect the `Start`, `Loop`, and `End` preview buttons. Selecting an Action propagates the same variant index's file across the group.

**Range caveat:** linked Action selection and preview buttons are not a guarantee that every hidden component's exported Start/End values have been synchronized. Current drawing logic updates only the first Start/Loop variants' ranges, and cast previews compute their Resolve range separately. Reimport and check the exported component ranges, especially End/Resolve and additional variants, before relying on segmented playback.

Sources: [cast and loop previews](../../blender/editors/animation_set_editor.py#L314), [linked Action assignment](../../blender/editors/animation_set_editor.py#L960).

## 7. Prepare the Actual Export Action

A **control rig** is an authoring aid; the **deform/game armature** supplies the exported skeleton and motion. The preview helpers can prefer an armature named `Control_Rig`, while the SKA exporter explicitly excludes armatures containing that name. Successful control-rig playback therefore does not prove that the export Action contains usable deform-bone motion.

The SKA writer reads the selected Action's bone **location and quaternion rotation F-curves**. It does not bake evaluated IK/constraints, the NLA stack, Euler rotation, or scale into motion automatically. Bake/convert the intended final motion onto the deform armature's bones before export when the source relies on those systems. Preserve the existing skeleton/rest-pose relationships and bone names; the writer derives bone IDs from known names or its fallback name hash.

Prefer zero-based clip keyframes for new work: SKA sample times are calculated from absolute keyframe numbers divided by clip length, without subtracting an arbitrary Action start offset. A clip moved to a later timeline position can preview correctly yet export shifted times.

Use `Clip Timing...` to inspect or set per-Action FPS/duration metadata. The dialog offers fixed-frame FPS retiming, duration-to-FPS calculation, FPS/duration-to-frame-length calculation, and scene fallback. These operations set timing metadata; they do not rescale or bake the Action's F-curves. Imported `frame_length`, `original_fps`, and `original_duration` can override later scene changes, so review them after changing a clip's length. Preview can also change scene FPS and timeline limits.

Sources: [preview armature lookup](../../blender/editors/animation_set_editor.py#L1295), [export armature lookup](../../utilities/ska_utility.py#L61), [SKA writer](../../utilities/ska_utility.py#L325), [Clip Timing dialog](../../blender/editors/animation_set_editor.py#L2182).

### SKA Metadata Is Not an AnimationSet Mode

The full track/keyframe path in the current [SKA reader/writer](../../definitions/ska_definitions.py) is implemented for file types **6 and 7**. [New SKA exports](../../utilities/ska_utility.py#L657) are generated as **type 7**; a research template describing types 2–5 does not establish equivalent add-on support for them.

- Track headers distinguish **position (`0`)** from **quaternion rotation (`1`)** and bind tracks to skeleton bone IDs. Renaming a clip does not retarget its skeleton.
- Each keyframe stores four values and four tangent components. This layout is not a generic export path for arbitrary Blender scale, Euler, or constraint animation.
- Both supported layouts store duration, repeat/stutter metadata, frame length, and trailing integers; type 7 includes an extra integer before frame length. Do not assign guessed meanings to unknown fields. This is not a lossless byte-for-byte rewrite: the current exporter generates three trailing zeros, so keep the original clip as a reference.
- The writer uses the Action's `repeat` value when present, otherwise `0`, and its `stutter_mode` when present, otherwise `2`. These file-level settings are distinct from AnimationSet's Start/Loop/End clip ranges.
- Historical notes call frame length “unused” or describe particular stutter values as smooth. Those engine effects remain unverified. The add-on still uses frame-length/FPS metadata for timing calculations; do not discard it or treat it as a guaranteed in-game speed control. Use `Clip Timing...` and round-trip the result.

## 8. Save, Export, and Round-Trip Check

1. Inspect every mapping/variant and its timing section, then click **Save** in both AnimationSet and EffectSet. Save the `.blend` too.
2. Export a DRS as **Animated Unit** for these unit visual mappings.
3. Enable **Export All SKA Actions** when new SKA files are needed. Despite its name, this exports clips referenced in the saved AnimationSet blob, **not every Action in the file**. An EffectSet-only Action reference does not by itself schedule an SKA export. Unresolved Actions can be skipped.
4. Choose **Model Name Prefix** deliberately: `No Prefix`, `Model Name Prefix`, `Folder Name Prefix`, or `Keep Existing Prefix`. The DRS dialog currently defaults to **No Prefix**, not Model Name Prefix. The naming map rewrites AnimationSet, marker-set and EffectSet animation references together, replacing spaces and resolving filename collisions; check actual output names rather than predicting them from dropdown labels.
5. For smooth keyed motion, review **[DEBUG] Export SKA Tangents** (enabled by default in DRS export). The standalone SKA exporter selects one Action and has its own `Export Tangents` toggle, defaulting to off. Tangents cannot recover missing/baked-out motion.
6. Reimport the output into a clean test scene and compare clips, mapping IDs, variants, ranges, timing values, marker position/direction, and effects against the source. Finally verify the game-side behavior with its existing ability definitions.

### Troubleshooting Checklist

| Symptom | Check first |
| --- | --- |
| No attack/cast mappings after export | Animated Unit type, correct active root, editor Save, nonempty Action assignments; Animated Object intentionally filters these out. |
| Missing or incorrect SKA | Saved AnimationSet references, actual Action names, output prefix, ambiguous/truncated names, and exported files. The resolver can fall back to similar prefixes. |
| Motion works only on the control rig | Bake deform-bone location/quaternion channels; the writer does not export the evaluated rig/NLA result. |
| Wrong speed or shifted release | Per-Action timing metadata, effective FPS, zero-based keyframes, normalized Time versus seconds, and full-clip versus segment timing. |
| Loop/resolve replays the wrong part | Reimport and inspect all hidden component ranges and variant indices; preview splits alone are insufficient. |
| Marker display is right but game event is wrong | Compare exported marker IDs to `AnimationTimings` references and confirm the game actually invokes the intended job/tag. Marker-set IDs are regenerated on Save separately from timing IDs; do not assume those links round-trip unchanged. |
| Existing data changes after Save | Work on a copy; schema reconstruction is not lossless preservation of unknown fields or unsupported mappings. |

Sources: [referenced-only SKA export](../../utilities/drs_utility.py#L5060), [export naming](../../utilities/helpers.py#L355), [DRS export options](../../__init__.py#L430), [Action resolver](../../utilities/drs_resolvers.py#L32), [marker/timing serialization](../../blender/editors/animation_set_editor.py#L1649).

## Related Reading

- [Advanced Effects Guide](advanced_effects_guide.md): audio/FX configuration and preservation caveats.
- [Advanced Locators Guide](advanced_locators_guide.md): attachment types and bone relationships.
- [Unit Creation Guide](unit_creation_buide.md): shared unit setup, without repeating it here.
- [AnimationSet format](../drs/animationset.md) and [AnimationTimings format](../drs/animationtimings.md): binary structure references; consult the source links above for current UI behavior.