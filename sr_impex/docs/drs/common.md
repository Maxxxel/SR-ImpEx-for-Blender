# Common Structures

Canonical definitions for small, frequently reused data structures across DRS classes.  
These structs are referenced by multiple classes such as `CGeoMesh`, `CGeoSubset`, and `CGeoMaterial`.

---

## Face
<a id="face-struct"></a>

A `Face` represents a **triangle** defined by **three 16-bit vertex indices** into a mesh’s `vertices` array.

| Field | Type | Description |
|------:|------|-------------|
| `i0`  | `ushort` | Index of first vertex (0-based) |
| `i1`  | `ushort` | Index of second vertex (0-based) |
| `i2`  | `ushort` | Index of third vertex (0-based) |

**Notes**
- Each face always references exactly **three vertices** — only triangles are supported.
- Because face indices are stored as `ushort`, both the **vertex index** and **face count** are constrained by 16-bit limits.

### Limits

| Constraint | Description |
|-------------|-------------|
| `vertex_count ≤ 65,535` | Maximum addressable vertex index (`ushort` limit) |
| `face_count ≤ 21,845` | Maximum number of triangles (`65,535 / 3 ≈ 21,845`) if fully packed |
| `index_count = face_count * 3` | Each face consumes three indices |

**Implications**
- A single mesh block can contain at most ~21 k triangles.
- Larger objects must be split into multiple mesh chunks.

---

## Vertex (Vector4)
<a id="vertex-struct"></a>

A `Vertex` used by many classes is a **4D float vector** where `w` is always `1.0`.

| Component | Type | Description |
|-----------:|------|-------------|
| `x` | `float` | X coordinate |
| `y` | `float` | Y coordinate |
| `z` | `float` | Z coordinate |
| `w` | `float` | Always `1.0` (homogeneous coordinate) |

**Notes**
- The extra component `w` exists for alignment and homogeneous transform support.
- Importers typically ignore `w` since it’s constant.

---

## Vector3
<a id="vector3"></a>

A 3D point or direction, stored as three **32-bit floats** (`x`, `y`, `z`).  
Total size: **12 bytes**. 

| Component | Type   | Bytes | Notes                    |
|-----------|--------|------:|--------------------------|
| `x`       | float  | 4     | little-endian IEEE-754   |
| `y`       | float  | 4     |                          |
| `z`       | float  | 4     |                          |

**Usage**  
Common across geometry and animation data (e.g., `CGeoAABox`, marker positions/directions, etc.). 

**Constraints / Conventions**
- Exactly 3 floats; no padding or `w` component.
- Coordinate meaning depends on the parent structure (position vs. direction). 


---

## Matrix3x3
<a id="matrix3x3"></a>

A 3×3 **orientation (rotation) matrix** stored as **9 floats** in **row-major** order.  
Total size: **36 bytes**. 

| Row | Elements            | Type  | Bytes |
|-----|---------------------|-------|------:|
| 0   | `m00 m01 m02`       | float | 12    |
| 1   | `m10 m11 m12`       | float | 12    |
| 2   | `m20 m21 m22`       | float | 12    |

**Usage**  
Represents orientation in `CMatCoordinateSystem` and other transforms. Stored/serialized as 9 consecutive floats. 

**Constraints / Conventions**
- Intended to be a rotation basis; normalization/orthogonality is expected by readers.  
- Serialization is strictly 9 floats; no implicit translation. 


---

## Matrix4x4
<a id="matrix4x4"></a>

A full **4×4 transform matrix** stored as **16 floats** in **row-major** order.  
Total size: **64 bytes**. 

| Row | Elements                    | Type  | Bytes |
|-----|-----------------------------|-------|------:|
| 0   | `m00 m01 m02 m03`           | float | 16    |
| 1   | `m10 m11 m12 m13`           | float | 16    |
| 2   | `m20 m21 m22 m23`           | float | 16    |
| 3   | `m30 m31 m32 m33`           | float | 16    |

**Usage**  
Used where a complete affine transform is required (e.g., skeleton super-parent). Written row by row. 

**Constraints / Conventions**
- 16 floats, no extra padding.  
- Meaning of the last column/row follows typical affine layout; specific interpretation depends on the consuming block. 


---

## CMatCoordinateSystem
<a id="cmatcoordinatesystem"></a>

Compact transform pairing **orientation** (`Matrix3x3`) with **position** (`Vector3`).  
Total size: **48 bytes** (`36 + 12`). 

| Field     | Type         | Bytes | Description                     |
|-----------|--------------|------:|---------------------------------|
| `matrix`  | `Matrix3x3`  | 36    | Rotation basis (row-major)      |
| `position`| `Vector3`    | 12    | Translation (x, y, z)           |

**Usage**
- Core transform used by many blocks: `SLocator`, `OBBNode`, `BoxShape`, `CylinderShape`, `SphereShape`, etc.  
- Always serialized as 9 floats (matrix) followed by 3 floats (position). 

**Constraints / Conventions**
- No scale component; scale is not supported.  
- Consumers assume the matrix encodes a valid rotation basis. 
