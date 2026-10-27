# Advanced Effects Guide

Use `EffectSet` to schedule existing sound and visual-effect resources against skeletal animation clips. Complete the [Unit Creation Guide](unit_creation_buide.md) first; use the [Advanced Abilities Guide](advanced_abilities_guide.md) for Action mappings, markers, and cast/loop segmentation.

> **Scope:** this editor authors timed resource references in a DRS, not particle systems, sound files, projectile simulation, or gameplay abilities. It does not establish damage, cooldowns, targeting, or spell behavior. The BMG export path has unfinished animation/effect nodes; do not assume it exports the configuration described here.

> **Back up imported models before pressing Save.** The current EffectSet UI exposes only animation-keyed entries. Its Save operation rebuilds that subset and does not preserve imported impact/additional sound containers or all header/unknown data. See [round-trip limitations](#7-round-trip-limitations) before editing a working game asset.

## 1. Understand the Three Levels

| Level | Contents | Example authoring intent |
| --- | --- | --- |
| Effect entry | An Action / `.ska` reference plus keyframes | Events for the clip used by an existing Attack mapping |
| Keyframe | Normalized time, type, audio/spatial parameters, resource variants | A sound at the release pose |
| Variant | File reference and weight | Two alternative existing sounds for that one event |

These variants are independent of AnimationSet variants. One chooses a motion clip; the other supplies candidate resources for a scheduled event. If Attack has two different SKA clips, create/check an EffectSet entry for each clip that needs events. There is no automatic “apply this effect to every Attack variant” link.

An entry is keyed by the **animation filename**, not an ability label, Blender timeline marker, or locator name. Several visual jobs can refer to the same clip; EffectSet does not provide a separate per-ability selector for them.

Sources: [EffectSet editor state](../../blender/editors/effect_set_editor.py#L180), [binary Keyframe and SkelEff definitions](../../definitions/effect_definitions.py#L44).

## 2. Open the Correct Model's Data

Make the intended `DRSModel_*` root collection active and open **3D Viewport → Sidebar → DRS Editor → EffectSet**. The panel remains visible without a valid root, but shows a selection hint instead of data controls. Save pending edits before changing models, then use `Reset` to load the newly active root's stored state.

- **Save:** writes the working EffectSet state into the collection's `EffectSetJSON` property. It does not save the `.blend`, export the DRS, or write/copy resource files.
- **Reset:** reloads stored EffectSet data and discards unsaved panel changes.
- **Left-list `+` / `−`:** add/remove an Effect entry.
- **Action:** choose the animation associated with that entry. The dropdown draws from all Actions in the `.blend`; check that it belongs to the intended skeleton/model.
- **Keyframes `+` / `−`:** add/remove scheduled events. A newly added keyframe starts at `0`, defaults to **FX1**, and includes one empty resource variant.
- **Up/down arrows:** reorder keyframe records, not their time values. The editor does not automatically sort by Time.
- **Variants `+` / `−`:** add/remove candidates for the selected event; edit File and Weight below the list.

The Action label can be shortened for display; it is not a reliable preview of the exported filename. Imported entries also retain their original SKA name internally. See the Action-retargeting caveat below before changing an imported entry's dropdown.

Sources: [panel controls](../../blender/editors/effect_set_editor.py#L811), [add/save/reset operators](../../blender/editors/effect_set_editor.py#L600).

## 3. Select the Event Type and Resource

| Type shown in the UI | Stored value | Resource category |
| --- | --- | --- |
| `Audio (snr/wav)` | `0` | Existing `.snr` or `.wav` sound reference |
| `FX1 (fxb)` | `1` | Existing `.fxb` visual-effect reference |
| `FX2 (fxb)` | `2` | Existing `.fxb` visual-effect reference |
| `Permanent FX1 (fxb)` | `3` | Permanent-effect category, referencing an `.fxb` |
| `Permanent FX2 (fxb)` | `4` | Permanent-effect category, referencing an `.fxb` |

These keyframe types are separate from the type field in the format's **additional sound containers**. Research labels such as `StepSound` refer to that other structure, not to a selectable replacement for keyframe type `0`. The current panel does not author those containers; see [round-trip limitations](#7-round-trip-limitations).

The labels establish supported categories, not a complete explanation of the engine difference between FX1 and FX2 or permanent-effect lifetime/cleanup. Reuse a known working model's type when reproducing an existing effect. Do not infer that type `3` or `4` means a Blender loop or that the add-on simulates its persistence.

### File References and Paths

The **File (.fxb/.wav/.snr)** field is a plain string. Enter the resource reference expected by the game's content layout, following a comparable working asset's naming/path convention. For illustration, `example_attack.wav` or `example_release.fxb` are filenames only, not bundled resources or guaranteed game-valid assets.

- EffectSet export stores the resource string; it does not validate existence, enforce an extension, convert audio, or package the referenced resource.
- A local Windows path used while editing is not automatically rewritten into a deployable game-resource path. Do not leave an absolute workstation path unless the target workflow explicitly supports it.
- Preserve the spelling and relative subpath used by known working content. Confirm the files are installed where the game resolves those references.
- Keep animation `.ska` references separate from sound/FX File fields. The exporter's shared SKA naming map updates animation references, not the names of external `.fxb`/`.wav`/`.snr` resources.
- Export skips empty resource names. Fill at least one intended resource variant per event and remove empty test events rather than assuming they will produce useful output.

Sources: [type/file properties](../../blender/editors/effect_set_editor.py#L180), [resource serialization](../../blender/editors/effect_set_editor.py#L421), [shared SKA naming](../../utilities/helpers.py#L355).

### SNR/SNS Resources and Sound Registration

An `.snr` is not simply a WAV file with a different extension. EA AudioCore v0 headers describe the codec, channel configuration, sample rate, sample count, and loop metadata. Depending on the storage type, audio can be embedded in a RAM-style resource or use associated `.sns` stream data. Keep the resource set expected by the source asset; copying only the SNR header may omit the actual streamed audio.

For a header whose sample rate and sample count are understood, nominal duration is sample count divided by sample rate. File size is not a reliable substitute, and this audio duration is separate from EffectSet's normalized animation Time.

Research templates also describe a `soundpipeline.bin` sound registry containing name/hash and audio metadata. A historical comment claims unregistered sounds can crash the game, but that registration rule and failure mode are **not verified**. Treat it as an investigation point, not a confirmed engine requirement. This add-on does not create or update a sound-pipeline registry when saving EffectSet, and a file reference alone does not prove a custom sound is registered or usable.

Historical audio-inspection templates include codec-specific XAS assumptions and incomplete optional streaming/prefetch handling. They are not a general-purpose SNR encoder/decoder specification. The EffectSet UI's audio label does not imply that it can encode all listed EA codecs or convert arbitrary WAV files into game resources.

## 4. Align Sound and FX with the Clip

**Time (0..1) is normalized progress through the full clip**, not seconds, milliseconds, or a Blender frame index. For an event at elapsed time $t$ in a clip lasting $D$ seconds:

$$
\text{Time} = \frac{t}{D}
$$

For a two-second clip with an event at `0.8` seconds, enter `0.4`. For a five-second Spawn clip, `0.6` means **three seconds**, not `0.6` seconds.

AnimationSet marker Time is also normalized `0..1`. If the same full clip has an Attack marker at `0.4`, using `0.4` for a sound keyframe is a deliberate way to align them. **There is no live synchronization:** changing the marker does not move EffectSet keyframes, and changing an effect keyframe does not update animation timing metadata.

For a cast whose `Cast→Resolve` split is `0.35`, an event intended at that split uses `0.35` on that full clip. Do not renormalize it to the shorter preview segment. Imported clips can carry their own FPS/frame-length metadata, so verify clip duration through `Clip Timing...` in AnimationSet rather than relying only on the current scene's FPS.

### Example: Attack Release Sound

1. In AnimationSet, identify the Action used by the existing `Attack` mapping. Preview its selected variant and note the marker fraction at the desired contact/release pose.
2. In EffectSet, add a new entry and select that exact Action.
3. Add a keyframe and **change the default FX1 type to Audio**.
4. Set Time to the intended fraction, then enter a known working `.snr`/`.wav` reference in its first variant. Keep one variant at weight `100` while diagnosing timing.
5. Add a separate FX keyframe if a visual resource is also required. Use an appropriate known working FX type and `.fxb` reference; a single keyframe has only one type.
6. Save both editors, save the `.blend`, export the DRS/SKA files, and test in game. Repeat for every motion variant that needs its own event entry.

### Example: Spawn or Cast Cue

Use the Action from the existing Spawn or cast mapping, not an assumed ability-name match. Set the sound/FX keyframe at the desired normalized moment, checking a Spawn marker or cast split only as a visual reference. This schedules a cue; it does not determine when a unit becomes controllable, when damage resolves, or when a projectile spawns.

Sources: [Time property](../../blender/editors/effect_set_editor.py#L192), [AnimationSet marker and timing controls](../../blender/editors/animation_set_editor.py#L2453).

## 5. Review Parameters Without Guessing Their Semantics

| Field | Practical guidance |
| --- | --- |
| `Min Falloff`, `Max Falloff` | Stored falloff parameters. Use values from comparable working audio/effects; the add-on provides no distance preview or documented unit calibration. Keep a sensible minimum/maximum ordering. |
| `Volume` | Stored floating-point value, defaulting to `1` for newly added keyframes. No Blender audition is provided. Do not assume it is a decibel value. |
| `Pitch Min`, `Pitch Max` | Stored pitch-shift range. Preserve established values; the UI does not establish whether the engine interprets them as ratios, semitones, or another scale. |
| `Offset` | Stored XYZ offset. The format source itself marks its spatial interpretation as uncertain; it is not a bone picker or an automatic locator binding. Verify coordinate interpretation in game. |
| `Interruptable` | Stored boolean flag with this exact UI spelling. Engine interruption behavior is not simulated or fully explained by the editor. |
| `Condition` | An incompletely understood conditional field. Do not treat it as a gameplay rule editor; preservation is currently unreliable, as described below. |
| Variant `Weight` | Integer `0..255` in this panel, stored as an unsigned byte. There is no sum validation or normalization despite the `%` list label. |

For a simple two-resource example, `80` and `20` makes intent easy to read, but the panel does not prove exact engine probability semantics. Avoid all-zero sets and verify resource selection in game. Sound/FX weights here have a different UI range from AnimationSet's `0..100` motion weights.

Locators such as spell or projectile attachment points are a separate mechanism. Use the [Advanced Locators Guide](advanced_locators_guide.md) for the actual locator types and parenting controls. Do not assume that an EffectSet Offset or animation marker automatically attaches an FX resource to one of them.

Sources: [editable properties](../../blender/editors/effect_set_editor.py#L180), [binary parameter definitions and uncertainties](../../definitions/effect_definitions.py#L44).

## 6. Preview and Export Boundaries

### What Blender Does Not Preview

The registered EffectSet panel has **no sound audition, FX simulation, or effect-timing playback button**. A `Play (Anim Only)` operator exists in the source but is not included in this editor's registered class list or drawn controls; do not expect it as an available panel feature.

Use AnimationSet preview or normal Blender animation playback to inspect motion and note the intended pose/time. That confirms neither resource loading nor engine spatialization, pitch, volume, conditions, permanent-effect behavior, or gameplay synchronization. AnimationSet preview may also choose the control rig, whereas SKA export uses the deform armature; see the [export Action checklist](advanced_abilities_guide.md#7-prepare-the-actual-export-action).

### Export Checklist

1. Save the EffectSet editor and AnimationSet editor to the correct active root; save the `.blend` separately.
2. Use a DRS model type that supports the intended animated model. Animated Object exports intentionally remove non-Idle AnimationSet jobs and animation markers/timings; use Animated Unit for those richer unit mappings.
3. Ensure every required clip exists on disk. **Export All SKA Actions** exports saved AnimationSet references, not Actions appearing only in EffectSet or every Action in the `.blend`.
4. Choose the SKA prefix strategy deliberately. The shared map rewrites DRS AnimationSet, marker-set and EffectSet animation references consistently when they resolve to the same Action. Missing/ambiguous Action resolution can still produce mismatches; inspect the exported files.
5. Supply external sound/FX assets separately in the expected game-resource layout. This editor writes references, not the assets themselves.
6. Reimport a copy of the output, compare its event records with the source, then test audio/FX in the game. Keep the original input and `.blend` until the round trip is verified.

Sources: [unregistered animation-only operator and class list](../../blender/editors/effect_set_editor.py#L766), [EffectSet export](../../utilities/drs_utility.py#L5032), [referenced-only SKA export](../../utilities/drs_utility.py#L5060), [model-type filtering](../../utilities/drs_utility.py#L5374).

## 7. Round-Trip Limitations

These are current implementation boundaries, not settings that can be fixed by guessing different engine values:

- **Imported sound containers are not editable/preserved by panel Save.** Import conversion captures `impact_sounds` and `additional_sounds`, but the UI state and Save serializer only reconstruct `effects`. Save also reseeds header defaults/checksum rather than merging all imported metadata, despite comments suggesting preservation. Back up before saving an imported EffectSet containing these records.
- **Retargeting an imported entry can retain its old SKA reference.** Serialization prefers the imported hidden `raw_ska` over the current dropdown Action. To intentionally retarget using the UI, create a fresh entry with the intended Action and recreate its keyframes, then remove the old entry in a backup copy. Check the resulting reference after export.
- **Condition is not a reliable round-trip control.** The binary class reads/writes `condition`, but the editor's conversion helpers use `uk`. Imported non-default values may be lost and edits may not reach the binary field. The binary field is signed-byte data for applicable EffectSet types, while the UI permits values up to `255`; do not rely on the UI range as a format guarantee.
- **No automatic repair of resource references or timing.** Invalid names, empty variants, incorrect offsets and mistimed events are not diagnosed by a successful Save. Keyframe order is preserved as edited, not sorted by time.

Sources: [state-only serializer](../../blender/editors/effect_set_editor.py#L253), [header defaults](../../blender/editors/effect_set_editor.py#L109), [import conversion](../../blender/editors/effect_set_editor.py#L309), [export conversion](../../blender/editors/effect_set_editor.py#L421), [actual Condition field](../../definitions/effect_definitions.py#L44).

## 8. Troubleshooting

| Symptom | Checks |
| --- | --- |
| No sound/FX in Blender | Expected: the panel does not audition resources or simulate FX. Verify motion separately and test the exported content in game. |
| No event in game | Confirm the game uses that exact SKA, the entry has keyframes/nonempty resources, type matches resource category, edits were saved, and assets are deployed. |
| Sound at the wrong pose | Check normalized full-clip Time, clip duration/FPS metadata, and whether the marker/split changed independently. |
| Only one attack variant has effects | Add/check entries for all required SKA clips; motion and effect variants are separate. |
| New Action chosen but old clip still referenced | Imported `raw_ska` takes precedence; recreate the entry rather than trusting the dropdown alone. |
| SKA missing although EffectSet names it | Add the required motion mapping in AnimationSet, or export the clip separately. EffectSet-only references do not trigger automatic SKA output. |
| FX appears at an unexpected position | Compare Offset and the existing effect's own configuration; locator attachment and marker Position are separate mechanisms. Do not guess coordinate conventions. |
| Imported impact/extra sounds or Condition disappear | Current preservation limitations; restore the backup and use a workflow that retains those records. A UI Save is not a lossless pass-through. |

## Related Guides

- [Advanced Abilities Guide](advanced_abilities_guide.md): attack/cast labels, markers, segmented clips, deform-rig and naming checks.
- [Advanced Locators Guide](advanced_locators_guide.md): attachment and parenting details.
- [Unit Creation Guide](unit_creation_buide.md): the base unit workflow.
- [Building Creation Guide](building_creation_guide.md): building-specific scope and BMG export limitations.