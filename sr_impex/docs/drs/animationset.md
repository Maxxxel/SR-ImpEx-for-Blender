# AnimationSet<a id="animationset"></a>

Defines the collection of animations available to a model, linking specific game states or actions (like "idle", "walk", "attack") to animation files (`.ska`). It also includes parameters controlling animation playback behavior and Inverse Kinematics (IK). 🎬

---
## Overview
- **Purpose:** Manages all skeletal animations for a unit or animated object, defining which `.ska` file plays for which action, and includes settings like default movement speeds and IK constraints.
- **Where it appears:** Included in animated model types: `AnimatedUnit`, `AnimatedObjectNoCollision`, `AnimatedObjectCollision`. See `WriteOrder`.
- **Engine impact:** Crucial for animation playback. Contains default speeds used by movement logic, IK constraints for targeting/aiming, and links to the actual animation data.

---
## Structure<a id="animationset-struct"></a>

| Field                       | Type                        | Description                                                                                             |
| :-------------------------- | :-------------------------- | :------------------------------------------------------------------------------------------------------ |
| `length`                    | `int32`                     | Length of the `magic` string (always 11).                                                              |
| `magic`                     | `string`                    | Magic identifier string, always "Battleforge".                                                         |
| `version`                   | `int32`                     | Format version, typically `6`.                                                                          |
| `default_run_speed`         | `float`                     | Default movement speed when running.                                                                    |
| `default_walk_speed`        | `float`                     | Default movement speed when walking.                                                                    |
| `revision`                  | `int32`                     | Sub-version or revision number, often `0` for objects, higher for units (e.g., `6`). Controls optional fields. |
| `mode_change_type`          | `uint8`                     | (Optional, `revision >= 2`) Unknown flag related to mode changes.                                       |
| `hovering_ground`           | `uint8`                     | (Optional, `revision >= 2`) Flag related to hovering units.                                             |
| `fly_bank_scale`            | `float`                     | (Optional, `revision >= 5`) Scale factor for banking during flight.                                     |
| `fly_accel_scale`           | `float`                     | (Optional, `revision >= 5`) Scale factor for acceleration during flight.                                |
| `fly_hit_scale`             | `float`                     | (Optional, `revision >= 5`) Scale factor related to being hit during flight.                            |
| `allign_to_terrain`         | `uint8`                     | (Optional, `revision >= 6`) Flag to align the model to terrain slope.                                   |
| `mode_animation_key_count`  | `int32`                     | Number of animation keys defined.                                                                       |
| `mode_animation_keys`       | `List[ModeAnimationKey]`    | List of keys linking game states/actions to animation variants. See [ModeAnimationKey](#modeanimationkey). |
| `has_atlas`                 | `int16`                     | (Optional, `version >= 3`) Flag indicating presence of IK data (0, 1, or 2).                             |
| `atlas_count`               | `int32`                     | (Optional, `has_atlas >= 1`) Number of IK Atlas entries.                                                |
| `ik_atlases`                | `List[IKAtlas]`             | (Optional, `has_atlas >= 1`) List of Inverse Kinematics constraints per bone. See [IKAtlas](#ikatlas).    |
| `uk_len`                    | `int32`                     | (Optional, `has_atlas >= 2`) Length of `uk_ints` array.                                                 |
| `uk_ints`                   | `List[int32]`               | (Optional, `has_atlas >= 2`) Unknown integer array.                                                     |
| `subversion`                | `int16`                     | (Optional, `version >= 4`) Sub-version controlling marker/unknown struct presence. Typically `2`.      |
| `animation_marker_count`    | `int32`                     | (Optional, `subversion == 2`) Number of animation marker sets.                                          |
| `animation_marker_sets`     | `List[AnimationMarkerSet]` | (Optional, `subversion == 2`) Data linking animation events to specific points in time/space. See [AnimationMarkerSet](#animationmarkerset). |
| `unknown`                   | `int32`                     | (Optional, `subversion == 1`) Count for `unknown_structs`.                                              |
| `unknown_structs`           | `List[UnknownStruct]`       | (Optional, `subversion == 1`) Unknown structure list. See [UnknownStruct](#unknownstruct).              |

---
## ModeAnimationKey<a id="modeanimationkey"></a>

Links a game state/action (identified by `file`, often conceptually like "Idle" or "Attack") to one or more animation variants (`.ska` files).

| Field                    | Type                            | Description                                                                                                                                                                                              |
| :----------------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `type`                   | `int32`                         | Internal type identifier (often `6`).                                                                                                                                                                   |
| `length`                 | `int32`                         |Length of the `magic` string (always 11).                                                                                                                                                           |
| `file`                   | `string`                        | Always "Battleforge".                              |
| `unknown`                | `int32`                         | Unknown integer.                                                                                                                                                                                         |
| `unknown2`               | `List[uint8]` or `int32`        | Varies based on `type`. Often a single `int32`.                                                                                                                                                          |
| `vis_job`                | `int16` (If `type == 6`)        | Related to visual state or job type. Export filter in `create_animation_set` removes keys where `vis_job != 0` for non-unit types.                                              |
| `unknown3`               | `int32` (If `type == 6`)        | Unknown integer.                                                                                                                                                                                         |
| `special_mode`           | `int16` (If `type <= 5` or `6`) | Identifier for a special animation mode or state.                                                                                                                                                        |
| `variant_count`          | `int32`                         | Number of animation variants associated with this key.                                                                                                                                                   |
| `animation_set_variants` | `List[AnimationSetVariant]`   | List of variants, each pointing to a `.ska` file and defining playback parameters. See [AnimationSetVariant](#animationsetvariant). A key must have at least one valid variant to be saved during export. |

---
## AnimationSetVariant<a id="animationsetvariant"></a>

Defines a single animation file (`.ska`) that can be played for a `ModeAnimationKey`, along with playback settings.

| Field            | Type     | Description                                                                                                   |
| :--------------- | :------- | :------------------------------------------------------------------------------------------------------------ |
| `version`        | `int32`  | Format version for this variant structure, typically `7`.                                                     |
| `weight`         | `int32`  | Likelihood of this variant being chosen if multiple exist for a key (e.g., 100).                             |
| `length`         | `int32`  | Length of the animation `file` name string.                                                                   |
| `file`           | `string` | Path to the `.ska` animation file (relative to the DRS). Must end with `.ska`.                                |
| `start`          | `float`  | (Optional, `version >= 4`) Start time within the `.ska` file (normalized 0.0-1.0 or actual seconds?).        |
| `end`            | `float`  | (Optional, `version >= 4`) End time within the `.ska` file (normalized 0.0-1.0 or actual seconds?).          |
| `allows_ik`      | `uint8`  | (Optional, `version >= 5`) Flag indicating if Inverse Kinematics can be applied during this animation (0 or 1). |
| `force_no_blend` | `uint8`  | (Optional, `version >= 7`) Flag to prevent blending into/out of this animation (0 or 1).                      |

---
## IKAtlas<a id="ikatlas"></a>

Defines Inverse Kinematics constraints for a specific bone.

| Field           | Type                 | Description                                                                                   |
| :-------------- | :------------------- | :-------------------------------------------------------------------------------------------- |
| `identifier`    | `int32`              | Bone ID (from `CSkSkeleton`) that these constraints apply to.                                 |
| `version`       | `int16`              | Format version, typically `2`.                                                                |
| `axis`          | `int32`              | (Optional, `version >= 1`) Axis identifier, usually `2`.                                      |
| `chain_order`   | `int32`              | (Optional, `version >= 1`) Order of evaluation within an IK chain.                            |
| `constraints`   | `List[Constraint]` | (Optional, `version >= 1`) List of three constraints (one for each axis: X, Y, Z). See [Constraint](#constraint). |
| `purpose_flags` | `int16`              | (Optional, `version >= 2`) Flags indicating the purpose or usage context of these constraints. |

---
## Constraint<a id="constraint"></a>

Specifies rotational limits and damping for a single axis of a bone within an `IKAtlas`. Angles are stored in radians.

| Field            | Type    | Description                                                     |
| :--------------- | :------ | :-------------------------------------------------------------- |
| `revision`       | `int16` | Format revision, typically `1`.                                 |
| `left_angle`     | `float` | (Optional, `revision == 1`) Minimum rotation angle (radians). |
| `right_angle`    | `float` | (Optional, `revision == 1`) Maximum rotation angle (radians). |
| `left_damp_start`| `float` | (Optional, `revision == 1`) Angle where damping starts (min side). |
| `right_damp_start`| `float` | (Optional, `revision == 1`) Angle where damping starts (max side). |
| `damp_ratio`     | `float` | (Optional, `revision == 1`) Damping factor (0.0 to 1.0).        |

---
## AnimationMarkerSet<a id="animationmarkerset"></a>

Groups animation markers (events) related to a specific animation file.

| Field                 | Type                       | Description                                                                              |
| :-------------------- | :------------------------- | :--------------------------------------------------------------------------------------- |
| `anim_id`             | `int32`                    | Identifier for the animation this marker set belongs to.              |
| `length`              | `int32`                    | Length of the `name` string.                                                             |
| `name`                | `string`                   | Name of the associated animation file (e.g., "skel_human_idle1.ska").                   |
| `animation_marker_id` | `uint32`                   | Unique ID for this marker set.                                                           |
| `marker_count`        | `int32`                    | Number of markers in this set (typically `1`).                                            |
| `animation_markers`   | `List[AnimationMarker]` | List containing the actual marker event data. Usually only one marker per set. See [AnimationMarker](#animationmarker). |

---
## AnimationMarker<a id="animationmarker"></a>

Defines a specific event point within an animation, including time, position, and direction.

| Field                | Type       | Description                                                                   |
| :------------------- | :--------- | :---------------------------------------------------------------------------- |
| `is_spawn_animation` | `int32`    | Flag indicating if this marker relates to a spawn animation (0 or 1).         |
| `time`               | `float`    | Time point within the animation where the event occurs (likely in seconds). |
| `direction`          | `Vector3`  | Direction vector associated with the event. See [Vector3](../drs/common.md#vector3). |
| `position`           | `Vector3`  | Position vector associated with the event. See [Vector3](../drs/common.md#vector3). |

---
## UnknownStruct<a id="unknownstruct"></a> (Appears if `subversion == 1`)

An undocumented structure.

| Field           | Type                     | Description                             |
| :-------------- | :----------------------- | :-------------------------------------- |
| `unknown`       | `int32`                  | Unknown integer.                        |
| `length`        | `int32`                  | Length of the `name` string.            |
| `name`          | `string`                 | Unknown string.                         |
| `unknown2`      | `int32`                  | Unknown integer.                        |
| `unknown3`      | `int32`                  | Count for `unknown_structs` list.       |
| `unknown_structs` | `List[UnknownStruct2]` | List of nested unknown structures. See [UnknownStruct2](#unknownstruct2). |

---
## UnknownStruct2<a id="unknownstruct2"></a> (Appears if `subversion == 1`)

A nested undocumented structure within `UnknownStruct`.

| Field         | Type           | Description             |
| :------------ | :------------- | :---------------------- |
| `unknown_ints`| `List[int32]` | Array of 5 unknown integers. |

---
## Authoring & In-Game Behavior
- **Blender Workflow:**
    - **Animation Set Editor:** The primary way to manage `AnimationSet` data is through the dedicated **Animation Set Editor** UI panel in the addon. This editor stores the configuration in a **JSON blob** (`ANIM_BLOB_KEY`) attached to the main model collection.
    - **JSON Blob:** This blob holds lists for `mode_keys` (linking conceptual names like "Idle" to `.ska` files and variants) and `marker_sets` (defining animation events). It also stores top-level parameters like default speeds and IK flags. The blob is the **authoritative source** during export.
    - **Export (`create_animation_set`):** The exporter reads the JSON blob from the collection. It reconstructs the `AnimationSet` structure, including `ModeAnimationKey`, `AnimationSetVariant`, `AnimationMarkerSet`, and `AnimationMarker` objects based on the blob data.
        - `.ska` File Links: The `AnimationSetVariant.file` field is populated from the blob. The exporter ensures it ends with `.ska`.
        - IK Constraints: `IKAtlas` and `Constraint` data is gathered directly from `LIMIT_ROTATION` constraints on the Armature's Pose Bones in Blender (`collect_ik_atlases_from_blender`).
    - **Import (`persist_animset_blob_on_collection`):** The importer reads the `AnimationSet` from the DRS file, converts it into the JSON blob format (`animset_to_blob`), and stores this blob on the imported model's collection. The Animation Set Editor UI then reads from this blob. IK constraints are applied to the Armature's Pose Bones (`import_animation_ik_atlas`).
- **In-Game Function:** The game engine uses `AnimationSet` to know which `.ska` animation to play based on the unit's current state (idle, walking, attacking, etc.). It uses the default speeds for movement calculations, applies IK constraints for aiming or foot placement, and triggers events based on `AnimationMarker` data.

---
## Validation Rules

| Rule                                         | Why                                                                 |
| :------------------------------------------- | :------------------------------------------------------------------ |
| `magic == "Battleforge"` and `length == 11`  | Confirms block identity.                                            |
| `version` is supported (e.g., 6)           | Ensures correct reading of optional fields based on `version`/`revision`. |
| Counts (`mode_animation_key_count`, etc.) match list lengths | Prevents read errors and ensures data integrity.                    |
| `AnimationSetVariant.file` points to existing `.ska` files | Required for animations to play correctly.                          |
| `IKAtlas.identifier` refers to a valid bone ID in `CSkSkeleton` | IK constraints must apply to existing bones.                        |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Skeleton:** Uses bone identifiers from `CSkSkeleton` for IK constraints. See [CSkSkeleton](./cskskeleton.md).
- **Animation Timings:** Works alongside `AnimationTimings` which defines timing details for certain animation types. See [AnimationTimings](./animationtimings.md).
- **Animation Data:** Links to external `.ska` files containing the actual animation curves.
- **Animation Set Editor:** Interacts with the JSON blob (`ANIM_BLOB_KEY`) managed by the editor panel.

---
## Nice to know
- **Magic Value:** `AnimationSet = -475734043` (0xE3A63FE5). See [Glossary → MagicValues](../glossary.md#magicvalues).
- **Blob is King:** Edits made directly to Blender Actions or Armature constraints (other than IK limits) might not be reflected on export unless the Animation Set Editor blob is updated accordingly. The blob stored on the collection is the primary source of truth for export.
- **Animated Object Filter:** For `AnimatedObjectCollision` / `AnimatedObjectNoCollision` types, the exporter filters out `ModeAnimationKey` entries where `vis_job` is not `0`.