# CDspJointMap<a id="cdspjointmap"></a>

Maps **local bone indices** used within a mesh (`CDspMeshFile`) to the **global bone identifiers** defined in the skeleton (`CSkSkeleton`). This acts as a lookup table for skinning.

---
## Overview
- **Purpose:** Links the vertex weights (which refer to a small, mesh-specific set of bones) to the full skeleton's bone hierarchy. Essential for correct skinning deformation. 🦴
- **Where it appears:** Present in all model types (`AnimatedUnit`, `StaticObjectCollision`, `StaticObjectNoCollision`, `AnimatedObjectNoCollision`, `AnimatedObjectCollision`). Appears early in the `WriteOrder`.
- **Engine impact:** Directly used by the skinning system to apply bone transformations to vertices.

---
## Structure<a id="cdspjointmap-struct"></a>

| Field               | Type                | Description                                                                       |
| :------------------ | :------------------ | :-------------------------------------------------------------------------------- |
| `version`           | `int32`             | Format version, typically `1`.                                                    |
| `joint_group_count` | `int32`             | Number of joint groups (usually matches the number of meshes in `CDspMeshFile`). |
| `joint_groups`      | `List[JointGroup]` | List containing one group per mesh.                                               |

---
## JointGroup<a id="jointgroup"></a>

Contains the mapping for a single mesh.

| Field       | Type           | Description                                                                                                                                               |
| :---------- | :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `joint_count` | `int32`        | Number of joints (bones) referenced by this specific mesh.                                                                                                |
| `joints`    | `List[int16]` | Array mapping the mesh's *local* bone index (used in `MeshData` revision 12 `bone_indices`) to the *global* bone identifier (from `CSkSkeleton`). |

---
## Authoring & In-Game Behavior
- **Blender Workflow:** This block is created automatically by the exporter (`create_cdsp_joint_map` in `drs_utility.py`) when exporting a skinned mesh.
- **How it works:** When exporting, the tool gathers all unique bones that influence each mesh piece. It creates a compact list (`JointGroup.joints`) containing only the *global* IDs of those specific bones.
- **Vertex Weights:** The skinning data (`CSkSkinInfo` or `MeshData` revision 12) stores *local indices* (0, 1, 2...) referring to this `JointGroup.joints` list. The game engine uses this map to find the correct *global* bone ID from the local index during animation.
- **Root Reference (`root_ref`):** The exporter tracks which local index corresponds to the root bone (ID 0) and stores this information internally (`mesh_bone_data["root_ref"]`) to correctly update vertex weights that might reference the root bone implicitly. Artists don't need to manage this directly. ✅

---
## Validation Rules

| Rule                                    | Why                                               |
| :-------------------------------------- | :------------------------------------------------ |
| `version == 1`                          | Ensures the expected format.                      |
| `joint_group_count == len(joint_groups)` | Internal consistency.                             |
| `joint_count == len(joints)` for each group | Joint array must match its count.                 |
| Referenced global bone IDs exist in `CSkSkeleton` | Prevents mapping to non-existent bones.           |

---
## Cross-References
- **Header / Nodes:** Referenced via `NodeInformation` in the DRS header. See [Header](../drs/header.md#nodeinformation).
- **Mesh Data:** Corresponds to meshes in `CDspMeshFile`. See [CDspMeshFile](./cdspmeshfile.md).
- **Skinning Data:** Provides the global IDs for local indices used in `CSkSkinInfo` or `MeshData` (rev 12). See [CSkSkinInfo](./cskskininfo.md) and [CDspMeshFile](./cdspmeshfile.md#meshdata).
- **Skeleton:** Global bone identifiers come from `CSkSkeleton`. See [CSkSkeleton](./cskskeleton.md).

---
## Nice to know
- **Magic Value:** `CDspJointMap = -1340635850` (0xB016E536). See [Glossary → MagicValues](../glossary.md#magicvalues).
- Even static models often contain a `CDspJointMap`, sometimes empty or mapping just a root bone if they were derived from animated assets.