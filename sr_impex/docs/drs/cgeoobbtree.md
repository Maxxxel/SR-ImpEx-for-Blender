# CGeoOBBTree (Oriented Bounding Box Tree)
<a id="cgeoobb"></a>

Stores an **oriented bounding box hierarchy** for fast intersection/collision and a compact triangle index list. For export we use a newer OBB-fitting algorithm that can yield **smaller, tighter** boxes. 

---

## Overview

- **Purpose:** Spatial acceleration for meshes (broad-phase tests, selection, simple collisions).
- **Composition:** A flat array of OBB nodes that forms a binary tree + a triangle list.
- **Coordinate System:** Each node carries a `CMatCoordinateSystem` (rotation basis `Matrix3x3` + position `Vector3`). See [CMatCoordinateSystem](common.md#cmatcoordinatesystem). 

---

## CGeoOBBTree
<a id="cgeoobb-struct"></a>

| Field           | Type     | Bytes | Description |
|----------------|----------|------:|-------------|
| `magic`        | int32    | 4     | **1845540702** — structure magic (not NodeInformation magic). |
| `version`      | int32    | 4     | **3**. |
| `matrix_count` | int32    | 4     | Number of OBB nodes. |
| `obb_nodes`    | array    | var   | `matrix_count` × [OBBNode](#obbnode). |
| `triangle_count` | int32  | 4     | Number of triangles listed below. |
| `faces`        | array    | var   | `triangle_count` × `Face` (3×uint16 indices). See [Face](common.md#face-struct). |

**Notes**
- The node array is stored **contiguously**; parent/child relationships are defined by indices. 

---

## OBBNode
<a id="obbnode"></a>

| Field                    | Type                    | Bytes | Description |
|-------------------------|-------------------------|------:|-------------|
| `oriented_bounding_box` | `CMatCoordinateSystem`  | 48    | Node’s oriented box transform (rotation basis + center). |
| `first_child_index`     | uint16                  | 2     | Index into the node array, or `0` if leaf. |
| `second_child_index`    | uint16                  | 2     | Index into the node array, or `0` if leaf. |
| `skip_pointer`          | uint16                  | 2     | Index to **skip** an entire subtree during traversal. |
| `node_depth`            | uint16                  | 2     | Depth in the tree (root = 0). |
| `triangle_offset`       | uint32                  | 4     | Start index into the global triangle list for this node’s span. |
| `total_triangles`       | uint32                  | 4     | Number of triangles covered by this node (leaf usually > 0). |

**Leaf vs. Internal**
- **Leaf:** child indices are `0`; triangles are defined by `triangle_offset`+`total_triangles`.
- **Internal:** child indices point to two other nodes; triangle span can be 0 at internals (implementation-dependent). 

**Traversal Hints**
- **Bounding test first:** check the node’s oriented box; only descend if needed.
- **Skip pointer:** jump over a whole subtree when pruning (useful in stackless traversals).  
  (Exact usage is engine-dependent; the field is stored to support fast forward-jumps.) 

---

## Conventions & Constraints
- **Transform only:** `CMatCoordinateSystem` carries **rotation + position**; **no scale** is encoded. Consumers assume a **valid rotation basis**. See [Matrix3x3](common.md#matrix3x3). 
- **Indices:** Child pointers/skip pointer are array indices into `obb_nodes`. The tree is typically **binary** and stored in a layout that favors sequential reads.
- **Triangle list:** `faces` are shared globally for the whole tree; leaf nodes reference ranges via `triangle_offset`/`total_triangles`. `Face` = 3×uint16, 6 bytes each. 
- **Export note:** Our exporter may use a **newer OBB fitting** that yields tighter boxes than legacy data. That’s expected—and beneficial—for collision/selection.

---

## Cross-references
- Glossary: [`MagicValues → CGeoOBBTree`](glossary.md#magicvalues)  
- Common types: [`CMatCoordinateSystem`](common.md#cmatcoordinatesystem), [`Vector3`](common.md#vector3), [`Matrix3x3`](common.md#matrix3x3), [`Face`](common.md#face-struct)