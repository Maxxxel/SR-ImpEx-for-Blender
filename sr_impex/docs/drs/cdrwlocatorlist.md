# CDrwLocatorList<a id="cdrwlocatorlist"></a>

Stores a list of **locators**, which are points of interest on a model used for attaching effects, modules, or defining gameplay-relevant positions (like health bars or projectile origins). 📍

---
## Overview
- **Purpose:** Defines attachment points and functional locations on animated units or buildings.
- **Where it appears:** Primarily used in `AnimatedUnit` models (`WriteOrder`). Static and simpler animated objects usually don't have this block.
- **Engine impact:** Used at runtime to spawn effects (`.fxb` files), attach other models (like turrets or destructible parts via `.module` files), position UI elements (health bars), and define interaction points (hit locations, projectile spawns).

---
## Structure<a id="cdrwlocatorlist-struct"></a>

| Field     | Type              | Description                                                          |
| :-------- | :---------------- | :------------------------------------------------------------------- |
| `magic`   | `int32`           | Internal block identifier, should be `281702437`.                    |
| `version` | `int32`           | Format version (e.g., `5`). Determines if `uk_int` in `SLocator` exists. |
| `length`  | `int32`           | Number of locators in the list.                                      |
| `slocators` | `List[SLocator]` | The actual list of locator entries. See [SLocator](#slocator).      |

---
## SLocator<a id="slocator"></a>

Defines a single locator point.

| Field                   | Type                       | Description                                                                                                                                                             |
| :---------------------- | :------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cmat_coordinate_system`| `CMatCoordinateSystem`     | Local transformation (rotation + position) relative to its parent (world or bone). See [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem).                 |
| `class_id`              | `int32`                    | Type identifier determining the locator's function (e.g., `0` for HealthBar, `3` for Turret, `8` for DynamicPerm effects). See [LocatorClass](../glossary.md#locatorclass) dictionary for full list. |
| `bone_id`               | `int32`                    | Identifier of the bone this locator is attached to (from `CSkSkeleton`). If `-1`, it's attached to the object's root (world space relative to the model origin).      |
| `file_name_length`      | `int32`                    | Length of the `file_name` string.                                                                                                                                       |
| `file_name`             | `string`                   | Associated file path (e.g., an effect `.fxb` or module `.module`/`.bms`/`.drs`) used by this locator, if applicable. Can be empty.                                   |
| `uk_int`                | `int32`                    | Unknown integer, present only if `CDrwLocatorList.version` is `5` or higher. Often `-1`.                                                                              |
| `class_type`            | `string` (derived)         | Human-readable type derived from `class_id` during import/export (e.g., "HealthBar", "Turret"). Not stored in the file.                                                  |

---
## Authoring & In-Game Behavior
- **Blender Workflow:**
    - **Representation:** Locators are typically represented as **Empty** objects in Blender. Their name often reflects their type (e.g., `Locator_HealthBar`, `Locator_Turret`).
    - **Locator Editor:** The addon provides a dedicated **Locator Editor** UI. This editor stores the locator data (type, bone attachment, file name) in a **JSON blob** (`BLOB_KEY`) attached to the main model collection. This blob is the **authoritative source** during export.
    - **Export (`create_cdrw_locator_list`):** The exporter reads the JSON blob from the collection. If the blob is missing or invalid, it tries to reconstruct locators by scanning for Empty objects named `Locator_*` or objects with a `UID_KEY` custom property.
    - **Transformation:**
        - If a locator is parented to a **Bone** in Blender (`parent_type == 'BONE'`), its local transform relative to that bone is stored. `SLocator.bone_id` is set to the bone's identifier from `CSkSkeleton`.
        - If not parented to a bone, its **world space transform** (relative to the `GameOrientation` empty, if present, otherwise relative to the Blender world origin) is stored, and `SLocator.bone_id` is set to `-1`.
    - **Import (`process_slocator_import`):** The importer creates Blender Empties (or loads linked models for types like `DestructiblePart`, `Wheel`) based on the `SLocator` data. If `bone_id` is valid, it parents the Empty to the corresponding bone in the Armature. Otherwise, it places the Empty in world space. A unique ID (`UID_KEY`) is stored on the created objects to link them back to the editor data.
- **In-Game Function:** The `class_id` tells the game engine what to do at the locator's position and orientation. For example, attach a turret model, spawn a projectile effect, or place the unit's health bar offset.

---
## Validation Rules

| Rule                               | Why                                                                 |
| :--------------------------------- | :------------------------------------------------------------------ |
| `magic == 281702437`               | Confirms correct block type.                                        |
| `version` is supported (e.g., 5) | Ensures correct reading of `SLocator` fields like `uk_int`.         |
| `length == len(slocators)`         | Internal consistency.                                               |
| `bone_id` is valid (`-1` or exists in `CSkSkeleton`) | Prevents attaching locators to non-existent bones.                  |
| `file_name_length` matches actual string length | Prevents read errors.                                               |
| `cmat_coordinate_system` is valid (orthonormal rotation) | Ensures correct orientation in-game.                                |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Skeleton:** Uses `bone_id` values which are identifiers defined in `CSkSkeleton`. See [CSkSkeleton](./cskskeleton.md).
- **Common Structures:** Uses `CMatCoordinateSystem`. See [Common Structures](../drs/common.md#cmatcoordinatesystem).
- **Locator Classes:** See [LocatorClass](../glossary.md#locatorclass) dictionary for full list. 
- **Locator Editor:** Interacts with the JSON blob managed by the Locator Editor panel.

---
## Nice to know
- **Magic Value:** `CDrwLocatorList = 735146985` (0x2BD8B3E9). See [Glossary → MagicValues](../glossary.md#magicvalues).
- **Editor is Key:** For reliable export, always use the Locator Editor UI panel to manage locators rather than relying solely on Blender object naming and parenting, as the JSON blob takes precedence.