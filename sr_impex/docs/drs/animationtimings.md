# AnimationTimings<a id="animationtimings"></a>

Stores millisecond timing values grouped by animation category, tag, and variant. The serialized fields are known; their exact engine interpretation is not universally established for every animation type.

---
## Overview
- **Purpose:** Associates timing values and optional marker references with animation categories and tags. Do not assume `cast_ms` and `resolve_ms` are two universal absolute event timestamps.
- **Where it appears:** Included in animated model types that typically perform actions: `AnimatedUnit`, `AnimatedObjectNoCollision`, `AnimatedObjectCollision`. See `WriteOrder`.
- **Engine impact:** Used by the gameplay systems (e.g., combat, abilities) to synchronize actions and effects precisely with the visual animation playback. Incorrect timings can lead to abilities feeling laggy or effects appearing at the wrong moment.

---
## Structure<a id="animationtimings-struct"></a>

| Field                    | Type                       | Description                                                                                                   |
| :----------------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------ |
| `magic`                  | `int32`                    | Internal block identifier, should be `1650881127`.                                                            |
| `version`                | `int16`                    | Format version, typically `4` (can also be `3` in older data). Controls structure interpretation.             |
| `animation_timing_count` | `int16`                    | Number of `AnimationTiming` entries in the list.                                                              |
| `animation_timings`      | `List[AnimationTiming]`    | List of timing definitions, grouped by animation type and tag ID. See [AnimationTiming](#animationtiming).    |
| `struct_v3`              | `StructV3`                 | An additional structure at the end, purpose unclear. See [StructV3](#structv3).                               |

---
## AnimationTiming<a id="animationtiming"></a>

Groups timing variants for a specific type of animation and tag.

| Field                   | Type                     | Description                                                                                                                                           |
| :---------------------- | :----------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `animation_type`        | `int32`                  | Category of animation this timing applies to (e.g., `0`=CastResolve, `1`=Spawn, `2`=Melee). See `AnimationType` in `drs_definitions.py` / Glossary. |
| `animation_tag_id`      | `int32`                  | (Optional, `version >= 2`) Identifier likely linking this timing to a specific ability or action variant.                                             |
| `is_enter_mode_animation` | `int16`                  | (Optional, `version >= 2`) Flag, often `1`. Purpose unclear, possibly related to state transitions.                                                 |
| `variant_count`         | `int16`                  | Number of timing variants defined for this type/tag combination.                                                                                      |
| `timing_variants`       | `List[TimingVariant]`    | List of actual timing data variants. See [TimingVariant](#timingvariant).                                                                             |

---
## TimingVariant<a id="timingvariant"></a>

Defines one possible set of timings for an `AnimationTiming` entry, often weighted.

| Field          | Type             | Description                                                                                             |
| :------------- | :--------------- | :------------------------------------------------------------------------------------------------------ |
| `weight`       | `uint8`          | Likelihood of this variant being chosen (e.g., `100`).                                                  |
| `variant_index`| `uint8`          | (Optional, `version == 4`) Index for this specific variant.                                             |
| `timing_count` | `uint16`         | Number of `Timing` entries in this variant (often just `1`).                                            |
| `timings`      | `List[Timing]`   | List containing the actual millisecond timings and related data. See [Timing](#timing).                 |

---
## Timing<a id="timing"></a>

Specifies the core timing data in milliseconds, along with direction and a marker link.

| Field                 | Type       | Description                                                                                                                                        |
| :-------------------- | :--------- | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cast_ms`             | `int32`    | Stored millisecond value. The current editor derives it from the clip duration multiplied by a marker/split fraction. |
| `resolve_ms`          | `int32`    | Stored millisecond value. The current editor uses the stored resolve duration or the full referenced clip duration; this does not prove the engine treats it as an impact timestamp. |
| `direction`           | `Vector3`  | Direction vector associated with the timing event. See [Vector3](../drs/common.md#vector3).                                                         |
| `animation_marker_id` | `uint32`   | ID linking this timing event back to a specific marker defined in the `AnimationSet`. See [AnimationMarkerSet](../drs/animationset.md#animationmarkerset). |

---
## StructV3<a id="structv3"></a>

An unclear structure appearing at the end of the `AnimationTimings` block.

| Field     | Type           | Description                     |
| :-------- | :------------- | :------------------------------ |
| `length`  | `int32`        | Count, usually `1`.             |
| `unknown` | `List[int32]` | List of 2 unknown integers.     |

---
## Authoring & In-Game Behavior
- **Blender Workflow:**
    - **Animation Set Editor:** Timings are managed exclusively through the **Animation Set Editor** UI panel, specifically in the "Timings" section. Artists define entries based on `Animation Type` (CastResolve, Melee, etc.) and `Tag ID`.
    - **Editing:** The per-variant Timing section exposes the category/tag and related settings. Displayed millisecond timing values are read-only; adjust the referenced clip metadata and the marker/cast-to-resolve fraction instead. See the [Advanced Abilities Guide](../plugin/advanced_abilities_guide.md#5-place-markers-and-understand-time-units).
    - **JSON Blob:** Like `AnimationSet` data, the timings configuration is stored in the **JSON blob** (`ANIM_BLOB_KEY`) attached to the main model collection (under the `"timings"` key). This blob is the authoritative source for export.
    - **Export (`create_animation_timings`):** The exporter reads the `"timings"` list from the JSON blob and reconstructs the `AnimationTimings` structure, including all substructures, based on the editor's data (`blob_to_animationtimings`). If no timings are defined in the blob, this block might be skipped during export (depending on model type requirements).
    - **Import (`animtimings_to_blob`):** The importer reads the `AnimationTimings` block, converts it to the JSON list format, and stores it within the main animation blob (`ANIM_BLOB_KEY`) on the collection. The editor UI then loads this data.
- **Current serialization:** The editor's [timing serializer](../../blender/editors/animation_set_editor.py#L1748) uses a stored positive `resolve_ms` when available, otherwise derives the full clip duration in milliseconds. It calculates `cast_ms` from that duration and the marker or cast-to-resolve fraction. This is the implemented authoring convention, not independent proof of every game-side timing rule.

### Research Notes Are Not Confirmed Engine Limits

Historical binary-template comments suggest game logic may quantize timing to 100-ms ticks, Spawn may need at least 200 ms, and entries after the sixth may be ignored. They also describe `resolve_ms` for CastResolve as a phase duration rather than a full-clip duration. These observations have **not been verified** and must not be presented as format guarantees or used to add silent clamping/truncation.

The distinction matters: the current editor's full-duration serialization and the historical phase-duration hypothesis are not interchangeable. Preserve a known working asset, compare exported values, and verify actual behavior in game before changing either interpretation. Template notes about tag IDs or hardcoded exceptions likewise need confirmation before becoming authoring rules.

---
## Validation Rules

| Rule                               | Why                                                                              |
| :--------------------------------- | :------------------------------------------------------------------------------- |
| `magic == 1650881127`              | Confirms correct block type.                                                     |
| `version` is supported (e.g., 3, 4)  | Ensures correct structure interpretation (presence of `animation_tag_id`, etc.). |
| Counts match list lengths          | Prevents read errors and ensures data integrity.                                   |
| Timing values checked against the target type and source asset | No universal endpoint/phase-duration rule is established here; avoid inventing validation from the field names. |
| Marker references resolve when that linkage is used | Match the relevant `AnimationMarkerSet`; not every tag-based record necessarily uses a marker link. |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Animation Set:** Works in conjunction with `AnimationSet`, particularly linking via `Timing.animation_marker_id`. See [AnimationSet](./animationset.md).
- **Animation Types:** The `animation_type` values are defined in `drs_definitions.py` (e.g., `AnimationType['Melee'] = 2`). See [Glossary](../glossary.md) (once added).
- **Common Structures:** Uses `Vector3`. See [Common Structures](../drs/common.md#vector3).

---
## Nice to know
- **Magic Value:** `AnimationTimings = -1403092629` (0xAC5E916B). See [Glossary → MagicValues](../glossary.md#magicvalues).
- **Editor is Key:** Timings are complex and directly tied to gameplay feel. Accurate configuration via the Animation Set Editor is crucial.
- **Animated Object Fix:** For non-unit animated objects (`AnimatedObjectNoCollision`, `AnimatedObjectCollision`), the exporter forces `version = 3` and removes all timing entries, as these object types typically don't use them.