# CDspMeshFile
<a id="cdspmeshfile"></a>

Top-level **mesh container** used in DRS files.  
It wraps one or more `BattleforgeMesh` entries and includes a file-level bounding box and three trailing points.  
The **NodeInformation.magic** for this class is `CDspMeshFile = -1900395636 (0x8EDCF4A4)`.  
Inside the payload, the internal block header uses `magic = 1314189598`.

---

## Overview

- **Purpose:** Holds one or more renderable mesh blocks (`BattleforgeMesh`) in a single DRS entry.  
- **Where it shows up:** Used in any mesh-based model (static objects, animated geometry).  
- **Engine impact:** Provides vertex and face data, material links, and LOD information for visual rendering.

---

## Structure
<a id="cdspmeshfile-struct"></a>

| Field | Type | Description |
|------:|------|-------------|
| `magic` | `int32` | Must be `1314189598`. |
| `zero` | `int32` | Always `0`. |
| `mesh_count` | `int32` | Number of contained meshes. |
| `bounding_box_lower_left_corner` | [Vector3](../drs/common.md#vector3) | Global AABB min. |
| `bounding_box_upper_right_corner` | [Vector3](../drs/common.md#vector3) | Global AABB max. |
| `meshes` | `BattleforgeMesh[mesh_count]` | Mesh entries. |
| `some_points` | `Vector4[3]` | Three 4D vectors stored at the end. |

---

## BattleforgeMesh
<a id="battleforgemesh"></a>

A single mesh entry with faces, vertex data, bounding box, and material information.

| Field | Type | Description |
|------:|------|-------------|
| `vertex_count` | `int32` | Number of vertices. |
| `face_count` | `int32` | Number of triangles. |
| `faces` | `Face[face_count]` | List of triangles (3×`uint16` indices). |
| `mesh_count` | `uint8` | Number of vertex streams. |
| `mesh_data` | `MeshData[mesh_count]` | Vertex streams. |
| `bounding_box_lower_left_corner` | [Vector3](../drs/common.md#vector3) | Local AABB min. |
| `bounding_box_upper_right_corner` | [Vector3](../drs/common.md#vector3) | Local AABB max. |
| `material_id` | `int16` | Material index. |
| `material_parameters` | `int32` | Switch controlling extra trailing blocks. |

### Conditional trailing blocks

Depending on `material_parameters`, additional structures follow:

- **When `-86061050`:**
  - `material_stuff:int32`, `bool_parameter:int32`
  - `textures`
  - `refraction`
  - `materials`
  - `level_of_detail`
  - `empty_string`
  - `flow`

- **When `-86061051`:**
  - `material_stuff:int32`, `bool_parameter:int32`
  - `textures`
  - `refraction`
  - `materials`
  - `level_of_detail`
  - `empty_string`

- **When `-86061055`:**
  - `bool_parameter:int32`
  - `textures`
  - `refraction`
  - `materials`

Unknown values cause the reader to abort.

---

## MeshData
<a id="meshdata"></a>

A single vertex stream.

| Field | Type | Description |
|------:|------|-------------|
| `revision` | `int32` | Stream revision. |
| `vertex_size` | `int32` | Size of each vertex (in bytes). |
| `vertices` | `byte[vertex_size × vertex_count]` | Raw vertex data. |

The vertex layout depends on `revision`.

---

## Materials
<a id="materials"></a>

Contains numeric material parameters such as smoothness, reflectivity, or refraction scale.

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | Number of material entries. |
| `materials` | `Material[length]` | Material list. |

### Material
| Field | Type | Description |
|------:|------|-------------|
| `identifier` | `int32` | Parameter ID (e.g. smoothness, metalness, etc.). |
| `value` | `float` | Parameter value. |

Known identifiers:
- 1668510769 → smoothness  
- 1668510770 → metalness  
- 1668510771 → reflectivity  
- 1668510772 → emissivity  
- 1668510773 → refraction_scale  
- 1668510774 → distortion_mesh_scale  
- 1935897704 → scratch  
- 1668510775 → specular_scale  
- 1668510776 → wind_response  
- 1668510777 → wind_height  
- 1935893623 → depth_write_threshold  
- 1668510785 → saturation

---

## Textures
<a id="textures"></a>

List of texture references.

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | Number of textures. |
| `textures` | `Texture[length]` | Texture entries. |

### Texture
| Field | Type | Description |
|------:|------|-------------|
| `identifier` | `int32` | Texture slot/type ID. |
| `length` | `int32` | String length. |
| `name` | `byte[length]` | Texture name (UTF-8). |
| `spacer` | `int32` | Stored value after the string. |

---

## Refraction
<a id="refraction"></a>

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | Entry count. |
| If `length == 1` | | One tuple of `identifier:int32` + 3×`float` color. |
| If `length > 1` | | Reader loops over all entries, writer only supports one. |

---

## LevelOfDetail
<a id="levelofdetail"></a>

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | Expected to be 1. |
| `lod_level` | `int32` | LOD level. |

---

## EmptyString
<a id="emptystring"></a>

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | String length. |
| `data` | `byte[length * 2]` | Raw UTF-8/UTF-16 data. |

---

## Flow
<a id="flow"></a>

Optional vector block (present when `material_parameters == -86061050`).

| Field | Type | Description |
|------:|------|-------------|
| `length` | `int32` | Number of entries (commonly 4). |
| `entries` | `FlowEntry[length]` | Each entry is `identifier:int32` + `Vector4`. |

---

## Validation Rules

| Rule | Why it matters |
|------|----------------|
| `magic == 1314189598` | Confirms valid block header. |
| `mesh_count == len(meshes)` | Internal consistency. |
| Non-negative vertex/face counts | Prevents buffer errors. |
| AABB min < max | Ensures valid bounding box. |
| Material/texture arrays use matching lengths | Prevents offset mismatches. |

---

## Cross-References

- **Header link:** See [Header → NodeInformation](../drs/header.md#nodeinformation) for how this block appears in DRS tables.  
- **Common structures:** [Vector3](../drs/common.md#vector3), [Vector4](../drs/common.md#vertex-struct), [Face](../drs/common.md#face-struct).  
- **Related blocks:** [CGeoMesh](./cgeomesh.md) for raw geometry, [CollisionShape](./collisionshape.md) for collision data.

---

## Nice to know

- The three trailing `Vector4` points at the end of the file are always written and read back, even if their purpose isn’t fully clear.  
- The exporter and importer expect matching `material_parameters` constants; unknown ones will throw an exception.
