# CGeoOBBTree (Oriented Bounding Box Tree)
<a id="cgeoobb"></a>

Stores an **oriented bounding box hierarchy** (flat array of nodes) plus a compact **triangle list** for fast hit-tests, selection and simple collisions. Nodes are `OBBNode` structs with transform + child/skip indices and triangle span.

---

## Overview

- **Purpose:** Broad/narrow-phase acceleration for mesh intersection and selection.
- **Where it shows up:** Most renderable assets that need picking or collisions.
- **Engine impact:** Tighter boxes and fewer nodes = fewer tests and faster queries.

---

## Structure
<a id="cgeoobb-struct"></a>

| Field              | Type   | Default | Description |
|-------------------:|-------:|:-------:|-------------|
| `magic`            | `int32` | 1845540702 | Block signature (not NodeInformation.magic). |
| `version`          | `int32` | 3 | Current layout version. |
| `matrix_count`     | `int32` | – | Number of OBB nodes. |
| `obb_nodes`        | `array` | – | `matrix_count` × [OBBNode](#obbnode). |
| `triangle_count`   | `int32` | – | Number of triangles referenced by the tree. |
| `faces`            | `array` | – | `triangle_count` × `Face` (3×`uint16` indices). See [Face](../drs/common.md#face-struct). |

> Nodes are stored **contiguously**; parent/child relations are via indices into this array. Faces form one **global** list shared by all leaves. See shared structs in [Common](../drs/common.md).

---

## OBBNode
<a id="obbnode"></a>

| Field                    | Type                       | Bytes | Description |
|-------------------------|----------------------------|------:|-------------|
| `oriented_bounding_box` | `CMatCoordinateSystem`     | 48    | Rotation basis (`Matrix3x3`) + position (`Vector3`). No scale. |
| `first_child_index`     | `uint16`                   | 2     | Index into `obb_nodes`, or `0` if leaf. |
| `second_child_index`    | `uint16`                   | 2     | Index into `obb_nodes`, or `0` if leaf. |
| `skip_pointer`          | `uint16`                   | 2     | Index used to **skip** an entire subtree (stackless traversal). |
| `node_depth`            | `uint16`                   | 2     | Depth (root = 0). |
| `triangle_offset`       | `uint32`                   | 4     | Start into the global face list for this node’s span. |
| `total_triangles`       | `uint32`                   | 4     | Number of triangles covered by this node. |

**Leaf vs. Internal**
- **Leaf:** both child indices are `0`; triangles are defined by `triangle_offset` + `total_triangles`.
- **Internal:** child indices point to two nodes; triangle span may be `0` for non-leaves.

---

## Authoring & In-Game Behavior

- **What artists control:** The shape ultimately follows your exported mesh. Cleaner topology → tighter OBBs → fewer false hits.
- **Transforms:** Nodes store **rotation + position** only; **no scale**. Keep rotations valid (orthonormal-ish) to avoid degenerate boxes. See [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem).
- **Exporter note:** The plugin uses a newer OBB fitting that can produce **smaller boxes** than legacy data — that’s expected and good. 
- **Triangles:** The tree references the **same face list** (3×`uint16` indices). Respect 16-bit limits from [Face](../drs/common.md#face-struct).

---

## Validation Rules

| Rule | Why it matters |
|------|----------------|
| `magic == 1845540702`, `version == 3` | Confirms block layout.
| `matrix_count == len(obb_nodes)` | Node array integrity.
| Child/skip indices `< matrix_count` (or `0` for leaf) | Prevents OOB traversal.
| `triangle_offset + total_triangles ≤ triangle_count` | Valid leaf spans.
| Face indices `< vertex_count` (from the linked mesh) | Keeps references valid (16-bit).
| OBB basis ~orthonormal | Invalid bases break collision math.

---

## Performance Notes

- **Tighter OBBs** and balanced splits reduce tests.
- **Skip pointer** enables **stackless** traversal; big win in broad-phase pruning.
- Triangle list is shared → good cache behavior when testing neighboring leaves.

---

## Cross-References

- **Header link:** How the node points here → [Header → NodeInformation](../drs/header.md#nodeinformation).
- **Glossary:** [MagicValues → `CGeoOBBTree`](../glossary.md#magicvalues) for the container-level magic ID.
- **Common data:** [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem), [Vector3](../drs/common.md#vector3), [Matrix3x3](../drs/common.md#matrix3x3), [Face](../drs/common.md#face-struct).
- **Related geometry:** The faces come from your visual mesh; see [CGeoMesh](./cgeomesh.md).

---

## Known Variants / Game Differences

- Legacy data may have looser OBBs from older fitting routines; the block layout itself remains the same.

---

## Nice to know

- Nodes are laid out to favor **sequential reads** (CPU cache friendly). Leaves often cluster triangles from nearby space.
