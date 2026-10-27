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
- The 16-bit limit applies to **each stored vertex index**, not to the number of triangles. Count fields in the enclosing mesh blocks are separate 32-bit integers.

### Index Capacity Versus Exporter Limits

| Constraint | Description |
|-------------|-------------|
| `0 ≤ index ≤ 65,535` | Range of one unsigned 16-bit index. This can address 65,536 distinct zero-based vertex slots. |
| `index < vertex_count` | Every index must refer to an existing vertex. |
| `index_count = face_count * 3` | Each triangle consumes three indices; this does not make `index_count` a 16-bit field. |
| Exporter validation: at most `32,767` vertices | A separate implementation check on each render mesh and on the combined welded mesh, not a limit derived from the index field's width. |

There is **no supported deduction of a 21,845-triangle limit** from three `ushort` indices per face. Reusing vertices allows many triangles to reference the same vertex slots. No additional game-side triangle-count limit has been established here; a wider serialized count is not a guarantee that arbitrarily large meshes work in game.

Sources: [Face serialization](../../definitions/base_types.py#L60), [mesh definitions](../../definitions/mesh_definitions.py), [current vertex-count validation](../../utilities/drs_utility.py#L420).

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

A 3×3 **linear basis** stored as **9 floats** in **row-major** order. Its interpretation depends on the consuming block; it is not universally a unit-length rotation matrix.
Total size: **36 bytes**. 

| Row | Elements            | Type  | Bytes |
|-----|---------------------|-------|------:|
| 0   | `m00 m01 m02`       | float | 12    |
| 1   | `m10 m11 m12`       | float | 12    |
| 2   | `m20 m21 m22`       | float | 12    |

**Usage**  
Represents orientation in `CMatCoordinateSystem` and other transforms. Stored/serialized as 9 consecutive floats. 

**Constraints / Conventions**
- Check the consuming block before normalizing the basis. OBB nodes deliberately include box size in the matrix; normalizing those vectors would discard the dimensions.
- Scale behavior for other block types is not established by the shared storage layout alone. Preserve imported values rather than assuming either universal scale support or a universal prohibition.
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

Compact transform pairing a **linear basis** (`Matrix3x3`) with **position** (`Vector3`).
Total size: **48 bytes** (`36 + 12`). 

| Field     | Type         | Bytes | Description                     |
|-----------|--------------|------:|---------------------------------|
| `matrix`  | `Matrix3x3`  | 36    | Block-specific linear basis (row-major) |
| `position`| `Vector3`    | 12    | Translation (x, y, z)           |

**Usage**
- Core transform used by many blocks: `SLocator`, `OBBNode`, `BoxShape`, `CylinderShape`, `SphereShape`, etc.  
- Always serialized as 9 floats (matrix) followed by 3 floats (position). 

**Constraints / Conventions**
- There is no **separate** scale field, but the 3×3 matrix can encode scale. For OBB nodes, the exporter explicitly multiplies axes by their half-extents before serialization.
- Whether another consumer accepts scaled bases is a separate engine question; it remains unverified here for locators and collision primitives. Do not infer that any arbitrary Blender transform is supported in every block.
- See the [OBB notes](cgeoobbtree.md#obbnode) and the [OBB exporter](../../utilities/drs_utility.py#L3338) before interpreting axis lengths or changing normalization.
