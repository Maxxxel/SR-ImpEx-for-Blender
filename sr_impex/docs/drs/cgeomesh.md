# CGeoMesh
<a id="cgeomesh"></a>

Represents the **final triangle mesh after deduplication** — a compact list of faces and vertices used by other systems.  
This block itself contains **only indices and vertices (Vector4)**. UVs, normals, tangents, materials, LOD, etc. are defined in other classes (e.g. `CDspMeshFile`/`BattleforgeMesh`).

---

## Overview

- **Purpose:** Provide a clean, deduplicated triangle list for geometry consumers.
- **Where it shows up:** As a node referenced from the DRS header; used by systems that only need raw geometry.
- **Engine impact:** Only counts matter here (indices/vertices). Shading/material behavior is elsewhere.

---

## Structure
<a id="cgeomesh-struct"></a>

| Field          | Type            | Default | Description |
|----------------|-----------------|---------|-------------|
| `magic`        | `uint`          | `1`     | Constant identifier inside the block **(not** the `NodeInformation.magic`) |
| `index_count`  | `uint`          | `0`     | Number of face indices (`#faces * 3`) |
| `faces`        | `List[Face]`    | –       | Triangles (see [Face](../drs/common.md#face-struct), 3 × `ushort` indices) |
| `vertex_count` | `uint`          | –       | Number of vertices |
| `vertices`     | `List[Vector4]` | –       | See [Vector4 / Vertex4](../drs/common.md#vertex-struct), typically `w = 1.0` |

> For the node’s class tagging in the container, see **Glossary → MagicValues → `CGeoMesh`** (this is `NodeInformation.magic`, not the `magic` field above).

---

## Authoring & In-Game Behavior

- **What this block is / isn’t:**  
  `CGeoMesh` is a **raw triangle soup** with 16-bit indices and `Vector4` vertices. It does **not** carry normals, UVs, colors, tangents, materials, or LOD info.
- **Where materials/UVs live:**  
  Material assignment, textures, extra mesh params, and LOD handling are defined in higher-level mesh containers such as `CDspMeshFile` / `BattleforgeMesh`.
- **Blender workflow (practical tips):**
  - Ensure the exported mesh is **triangulated**; non-tris will be converted to triangle faces.
  - Keep vertex order stable to avoid index churn (helps diffs and downstream caches).
  - Apply transforms before export (rotation/scale) so the vertex data is already in the expected object space.

---

## Validation Rules

| Rule                               | Why it matters |
|------------------------------------|----------------|
| `magic == 1`                       | Confirms correct block type payload. |
| `index_count % 3 == 0`             | Must be triangles only. |
| `len(vertices) == vertex_count`    | Internal consistency. |
| `max(face indices) < vertex_count` | All indices must reference existing vertices. |
| `vertex_count ≤ 65,535`            | 16-bit index limit from `Face` definition. |

---

## Performance Notes

- This block is **minimal**: perf implications are proportional to `vertex_count` and `index_count` only.
- Bounding boxes, material batching, and LOD culling happen in other classes; `CGeoMesh` doesn’t include them.

---

## Cross-References

- **Header / Nodes:** See [Header → NodeInformation](../drs/header.md#nodeinformation) for how the node points to this payload.
- **Glossary:** [MagicValues → `CGeoMesh`](../glossary.md#magicvalues) for the container-level magic ID.
- **Common data:** [Face](../drs/common.md#face-struct), [Vector4](../drs/common.md#vertex-struct).
- **Related mesh containers:** [CDspMeshFile](../drs/cdspmeshfile.md)

---

## Known Variants / Game Differences

- None

---

## Nice to know

- `Vector4.w` is typically `1.0` and mainly exists for alignment/homogeneous math; importers often ignore it.
