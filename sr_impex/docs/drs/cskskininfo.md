# CSkSkinInfo <a id="csk-skininfo"></a>

---

## Overview

`CSkSkinInfo` defines how each vertex in a mesh is **influenced by bones** from the skeleton.  
It determines how meshes **deform** when animated. Each vertex stores a small list of bones and their respective weights.  
This block appears in **animated DRS assets** and is generated automatically when the model has an armature with vertex groups.

In the `WriteOrder` defined in `drs_definitions.py`, it appears for:
- `AnimatedUnit`
- `AnimatedObjectCollision`
- `AnimatedObjectNoCollision`

It is **not used** for static objects without a skeleton.

---

## Structure <a id="csk-skininfo-struct"></a>

| Field | Type | Description |
|------:|------|-------------|
| `version` | `int32` | Internal version number for the format. |
| `vertex_count` | `int32` | Number of vertices with weight data. |
| `vertex_data` | `List[VertexData]` | One entry per vertex, containing bone indices and weights. |

### VertexData
| Field | Type | Description |
|------:|------|-------------|
| `bone_indices` | `List[int]` | Bone IDs influencing this vertex. The IDs reference the bones from `CSkSkeleton`. |
| `weights` | `List[float]` | Normalized influence weights for each bone index (usually up to 4 per vertex). |

---

## Authoring & In-Game Behavior

When exporting from Blender, the `create_skin_info()` function in `drs_utility.py` gathers the skin data like this:

1. **Vertex Source:**  
   A unified list of all mesh vertices is created (from the exported mesh). Vertices are matched by **position** using rounding and KD-tree lookup to ensure each Blender vertex connects to the correct exported vertex.

2. **Bone Mapping:**  
   Blender’s vertex groups are matched to bones in the armature.  
   The mapping uses the bone names from `CSkSkeleton` to find the correct **bone ID**.  
   Each vertex group name must exactly match its bone name to export correctly.

3. **Weight Handling:**  
   Each vertex can store **up to 4 influences**. If more are found, only the 4 highest weights are kept.  
   Weights are then normalized to ensure their total equals 1.0.

4. **Import Behavior:**  
   When importing, the tool recreates vertex groups in Blender based on stored bone indices and weights, matching the bones from the linked skeleton.  
   Missing bones or mismatched names are skipped but logged for visibility.

In-game, this data ensures that mesh vertices follow the correct bones as they animate. Missing or invalid weights can cause visible stretching or collapsing of the model.

---

## Validation Rules

| Rule | Why it matters |
|------|----------------|
| Each vertex has ≤ 4 influences | Game engine expects a fixed small number for performance. |
| Weights per vertex sum to 1.0 | Prevents visual deformation errors. |
| Each bone index exists in `CSkSkeleton` | Ensures valid bone links for animation. |
| Vertex match succeeds during export | Prevents missing weight assignments. |

---

## Cross-References

- **Skeleton:** [`CSkSkeleton`](../drs/cskskeleton.md) — provides the bone hierarchy and IDs used here.  
- **Mesh:** [`CDspMeshFile`](../drs/cdspmeshfile.md) — contains the vertices that the weights are applied to.  
- **Joint Mapping:** [`CDspJointMap`](../drs/cdspjointmap.md) — connects mesh joints to the correct bones.  
- **Write Order:** Listed for animated objects in `drs_definitions.py`.

---

## Nice to know

- This block is written only when a mesh has **vertex groups** and a valid **armature**.  
- If bone names don’t match exactly between Blender and the skeleton, those weights are skipped and logged.  
- Removing unused vertex groups before export helps reduce unnecessary data and warnings.
