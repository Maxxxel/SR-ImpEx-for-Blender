# CSkSkeleton<a id="cskskeleton"></a>

Stores the **bone hierarchy** (skeleton) used for animating skinned meshes. It defines the names, parent-child relationships, and bind-pose transformations for all bones. 🦴

---
## Overview
- **Purpose:** Defines the articulated structure (bones) that drives the deformation of animated characters and objects.
- **Where it appears:** Included in animated model types: `AnimatedUnit`, `AnimatedObjectNoCollision`, `AnimatedObjectCollision`. It's absent in static models. Appears after `CSkSkinInfo` in the `WriteOrder`.
- **Engine impact:** Forms the basis for skeletal animation playback. The number of bones and hierarchy depth can affect animation performance.

---
## Structure<a id="cskskeleton-struct"></a>

| Field             | Type                | Description                                                                                                                                                              |
| :---------------- | :------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `magic`           | `int32`             | Internal block identifier, should be `1558308612`.                                                                                                                        |
| `version`         | `int32`             | Format version, typically `3`.                                                                                                                                            |
| `bone_matrix_count` | `int32`             | Number of entries in `bone_matrices`. Should match `bone_count`.                                                                                                           |
| `bone_matrices`   | `List[BoneMatrix]` | Bind pose transformation data for each bone, **ordered sequentially by bone `identifier`** (0, 1, 2...). See [BoneMatrix](#bonematrix).                                     |
| `bone_count`      | `int32`             | Total number of bones in the skeleton.                                                                                                                                     |
| `bones`           | `List[Bone]`        | The list defining each bone's properties and hierarchy. **Note:** This list is **ordered by `Bone.version`**, *not* necessarily by bone `identifier`. See [Bone](#bone). |
| `super_parent`    | `Matrix4x4`         | Root transformation matrix, usually identity. See [Matrix4x4](../drs/common.md#matrix4x4).                                                                                  |

---
## BoneMatrix<a id="bonematrix"></a>

Contains bind pose data derived from four `BoneVertex` entries, effectively storing the bone's local transform relative to its parent (or world space for root bones).

| Field         | Type                 | Description                                    |
| :------------ | :------------------- | :--------------------------------------------- |
| `bone_vertices` | `List[BoneVertex]` | Four vertices defining the bone's orientation, position, and hierarchical links. Always 4 entries. See [BoneVertex](#bonevertex). |

---
## BoneVertex<a id="bonevertex"></a>

A helper structure within `BoneMatrix`. The `parent` field is key for linking within the skeleton's structure, particularly for the first two vertices.

| Field      | Type            | Description                                                                                          |
| :--------- | :-------------- | :--------------------------------------------------------------------------------------------------- |
| `position` | `Vector3`       | A 3D coordinate related to the bone's bind pose. See [Vector3](../drs/common.md#vector3).                 |
| `parent`   | `int32`         | Index linking to bone identifiers, **with specific meaning based on its index within `bone_vertices`**: |

**Specific `parent` field usage within `BoneMatrix.bone_vertices`:**

* `bone_vertices[0].parent`: Stores the **`identifier`** of this bone's **parent bone** in the hierarchy. For the root bone (identifier 0), this value is `-1`. This directly links a bone back to its parent.
* `bone_vertices[1].parent`: Stores the **`identifier`** of the **bone itself**. This acts as a self-reference.
* `bone_vertices[2].parent`: Hardcoded to `0` during export (`create_skeleton`). Its specific use in-game is unclear.
* `bone_vertices[3].parent`: Hardcoded to `0` during export (`create_skeleton`). Its specific use in-game is unclear.

---
## Bone<a id="bone"></a>

Defines a single bone in the skeleton hierarchy. Remember this list is ordered by `version`, not `identifier`.

| Field       | Type           | Description                                                                                                    |
| :---------- | :------------- | :------------------------------------------------------------------------------------------------------------- |
| `version`   | `uint32`       | Bone version/identifier, often derived from a hash or predefined list (`bone_versions.json`). **Used for sorting this list.** |
| `identifier`| `int32`        | Unique ID for this bone within the skeleton (0 for root, 1, 2...). Used by `CSkSkinInfo` and `CDspJointMap`. **Used for indexing `bone_matrices`.** |
| `name_length`| `int32`        | Length of the bone name string.                                                                                |
| `name`      | `string`       | Name of the bone (e.g., "Bip01_Head"). Limited to 63 characters by importer/exporter (hashes longer names). |
| `child_count`| `int32`        | Number of direct children this bone has.                                                                       |
| `children`  | `List[int32]` | List of `identifier` values for the children bones.                                                            |

---
## Authoring & In-Game Behavior
- **Blender Workflow:**
    - **Creation:** Created automatically during export (`create_skeleton` in `drs_utility.py`) from a Blender **Armature** object within the model's collection.
    - **Hierarchy:** The parent-child relationships in the Blender Armature directly define the `Bone.children` and the `BoneVertex[0].parent` links in the exported `CSkSkeleton`. The root bone in Blender (usually the one with no parent) becomes bone `identifier` 0.
    - **Bone Map:** The exporter generates a `bone_map` (`create_bone_map`) which assigns a unique sequential `identifier` (0, 1, 2...) to each bone based on traversing the hierarchy. This map is crucial for linking skin weights (`CSkSkinInfo`) and joint maps (`CDspJointMap`), and determines the order of the `bone_matrices` array.
    - **Bone Ordering:** The `bones` list itself is sorted based on the `Bone.version` field (potentially from `bone_versions.json` or a hash) before writing. The `bone_matrices` list remains ordered by the hierarchical `identifier`.
    - **Naming:** Bone names are taken directly from the Blender Armature. The importer/exporter enforces a 63-character limit; longer names might be hashed (`Bone.read` logic). Standard naming conventions (like "Bip01_...") are recommended.
    - **Bind Pose:** The `bone_matrices` are calculated from the bone's **Rest Pose** transforms in Blender (`armature_bone.matrix_local`).
- **Import:** When importing (`import_csk_skeleton`, `init_bones`), the `CSkSkeleton` data is used to reconstruct the Armature object in Blender, including bone names, hierarchy (`create_bone_tree` uses parent links), and setting the Rest Pose (`record_bind_pose`).

---
## Validation Rules

| Rule                                    | Why                                                          |
| :-------------------------------------- | :----------------------------------------------------------- |
| `magic == 1558308612`                   | Confirms block type.                                         |
| `version == 3`                          | Ensures expected format.                                     |
| `bone_matrix_count == bone_count`       | Each bone needs matrix data.                                 |
| `bone_count == len(bones)`              | Bone array must match its count.                             |
| Bone `identifier` values are unique and sequential (0 to `bone_count`-1) | Required for consistent indexing by other systems.           |
| Child indices in `Bone.children` are valid bone `identifier` values | Prevents broken hierarchy links.                             |
| `BoneVertex[0].parent` index is valid (`-1` or 0 to `bone_count`-1) | Ensures correct parent linking.                              |
| `BoneVertex[1].parent == Bone.identifier` | Consistency check for self-reference.                        |
| Bone names are unique and <= 63 chars     | Ensures correct mapping and avoids engine/tool limitations. |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Skinning Weights:** Provides the bone `identifier` values referenced by `CSkSkinInfo`. See [CSkSkinInfo](./cskskininfo.md).
- **Joint Map:** Provides the bone `identifier` values referenced by `CDspJointMap`. See [CDspJointMap](./cdspjointmap.md).
- **Common Structures:** Uses `Matrix4x4` and `Vector3`. See [Common Structures](../drs/common.md).

---
## Nice to know
- **Magic Value:** `CSkSkeleton = -2110567991` (0x823299C9). See [Glossary → MagicValues](../glossary.md#magicvalues).
- **Node Name:** The node is typically named `csk_skeleton` in the hierarchy during export.
- **Ordering Difference:** Be aware that the `bones` list is sorted by `version`, while `bone_matrices` are indexed by the sequential `identifier`. This means `bones[i].identifier` does not necessarily equal `i`.