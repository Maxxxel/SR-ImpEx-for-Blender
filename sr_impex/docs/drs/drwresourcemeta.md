# DrwResourceMeta<a id="drwresourcemeta"></a>

Contains metadata about the DRS resource, specifically a version number and a hash string.

---
## Overview
- **Purpose:** Stores basic metadata, primarily a hash likely used for asset identification or version tracking.
- **Where it appears:** Present in all defined model types (`AnimatedUnit`, `StaticObjectCollision`, `StaticObjectNoCollision`, `AnimatedObjectNoCollision`, `AnimatedObjectCollision`). See `WriteOrder`.
- **Engine impact:** Likely used by the engine or tools for identifying or verifying the asset version. It doesn't directly affect rendering or gameplay mechanics visible to artists.

---
## Structure<a id="drwresourcemeta-struct"></a>

| Field     | Type     | Description                                                                                                |
| :-------- | :------- | :--------------------------------------------------------------------------------------------------------- |
| `version` | `int32`  | Format version number, typically `1`.                                                                        |
| `unknown` | `int32`  | An unknown integer value. Observed values include `0`, `1`, `2`, `3`. Default appears to be `1` for units. |
| `length`  | `int32`  | Length of the following `hash` string in bytes.                                                            |
| `hash`    | `string` | A string containing hash information (e.g., "sr-1234567890-0").                                             |

---
## Authoring & In-Game Behavior
- **Blender Workflow:** This block is generated automatically by the exporter (`save_drs` calls `DrwResourceMeta().write`). Artists do not directly edit this data in Blender.
- **Hash Generation:** The exporter currently generates a default hash string (""). The specific logic for generating meaningful hashes (like "sr-crc32-0") might reside elsewhere or in older toolchains. The importer (`DrwResourceMeta().read`) simply reads the existing hash from the file.
- **`unknown` field:** The purpose of this field is unclear.

---
## Validation Rules

| Rule           | Why                                             |
| :------------- | :---------------------------------------------- |
| `version == 1` | Confirms expected format.                       |
| `length` matches actual `hash` string length | Prevents reading incorrect data or buffer overflows. |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Glossary:** Contains the magic value. See [Glossary → MagicValues](../glossary.md#magicvalues).

---
## Nice to know
- **Magic Value:** `DrwResourceMeta = -183033339` (0xF518F885).
- Although present in all models, the actual *meaning* or *usage* of the hash string by the game engine isn't known. It likely serves as a unique identifier or checksum.