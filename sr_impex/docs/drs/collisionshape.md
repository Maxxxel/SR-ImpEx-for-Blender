# collisionShape
<a id="collisionshape"></a>

Holds a **set of simple collision volumes** (boxes, spheres, cylinders) used by **static objects** and some **animated objects (non-unit)** for hit checks, selection and placement.  
**Not used by units** (`AnimatedUnit`); those rely on other mechanisms.

---

## Overview

- **Purpose:** Fast, approximate collisions without per-triangle tests.
- **Where it shows up:** Present in *StaticObjectCollision* and *AnimatedObjectCollision* models; **absent** in *AnimatedUnit*.
- **Engine impact:** Cheap broad-phase tests. Triangle trees (e.g. `CGeoOBBTree`) may be consulted only if needed.

---

## Structure
<a id="collisionshape-struct"></a>

A compact header plus three counted arrays. There is **no** “CollisionPrimitive” union; shapes are stored by concrete type.

| Field            | Type    | Default | Description |
|------------------|---------|:------:|-------------|
| `version`        | `byte`  | `1`    | Format version. |
| `box_count`      | `uint`  | –      | Number of boxes. |
| `boxes`          | `BoxShape[box_count]` | – | See [BoxShape](#boxshape). |
| `sphere_count`   | `uint`  | –      | Number of spheres. |
| `spheres`        | `SphereShape[sphere_count]` | – | See [SphereShape](#sphereshape). |
| `cylinder_count` | `uint`  | –      | Number of cylinders. |
| `cylinders`      | `CylinderShape[cylinder_count]` | – | See [CylinderShape](#cylindershape). |

---

## BoxShape
<a id="boxshape"></a>

Rectangular volume with local transform + AABB extents.

| Field            | Type                              | Description |
|------------------|-----------------------------------|-------------|
| `coord_system`   | [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem) | Local basis and position; size is also described by the AABB corners. |
| `geo_aabox`      | [CGeoAABox](#cgeoaabox)           | Lower/upper corners in local space. |

### CGeoAABox
<a id="cgeoaabox"></a>

| Field               | Type                         | Description |
|---------------------|------------------------------|-------------|
| `lower_left_corner` | [Vector3](../drs/common.md#vector3) | One corner of the box. |
| `upper_right_corner`| [Vector3](../drs/common.md#vector3) | Opposite corner of the box. |

---

## SphereShape
<a id="sphereshape"></a>

| Field            | Type                              | Description |
|------------------|-----------------------------------|-------------|
| `coord_system`   | [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem) | Position (orientation irrelevant). |
| `geo_sphere`     | [CGeoSphere](#cgeosphere)         | Radius + center. |

### CGeoSphere
<a id="cgeosphere"></a>

| Field     | Type                         | Description |
|-----------|------------------------------|-------------|
| `radius`  | `float`                      | Sphere radius. |
| `center`  | [Vector3](../drs/common.md#vector3) | Center in local space (often 0,0,0). |

---

## CylinderShape
<a id="cylindershape"></a>

| Field            | Type                              | Description |
|------------------|-----------------------------------|-------------|
| `coord_system`   | [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem) | Local orientation and position. |
| `geo_cylinder`   | [CGeoCylinder](#cgeocylinder)     | Center, height, radius. |

### CGeoCylinder
<a id="cgeocylinder"></a>

| Field     | Type                         | Description |
|-----------|------------------------------|-------------|
| `center`  | [Vector3](../drs/common.md#vector3) | Cylinder center in local space. |
| `height`  | `float`                      | Height along the local up-axis. |
| `radius`  | `float`                      | Base radius. |

---

## Authoring & In-Game Behavior

- **Blender workflow:** Create dedicated collision objects (box/sphere/cylinder) and tag them; the exporter writes them into the respective arrays.
- **Transforms:** Collision boxes and cylinders support parenting to `GameOrientation`, correcting the viewport rotation, and applying that rotation before export. The exporter recovers their baked orientation from the mesh and removes the display-only `GameOrientation` transform. `CMatCoordinateSystem` stores rotation + position, while dimensions live in the geo structs.
- **Primitive geometry:** Keep boxes rectangular and cylinders circular with two parallel planar caps. Cylinder caps may be n-gons or triangulated; cap triangles are grouped by plane rather than mistaken for side walls. Arbitrarily deformed meshes, sheared boxes, and elliptical cylinders cannot be represented exactly by these primitives.
- **Scale interpretation:** The shared 3×3 storage has no separate scale field, but that does not prohibit scale inside its basis. Scaled bases are confirmed for OBB nodes; game-side acceptance of scaled collision bases remains unverified. Do not transfer OBB normalization/size rules to collision shapes automatically.
- **Usage pattern:** These primitives provide quick acceptance/rejection. If a model also has `CGeoOBBTree`, detailed triangle tests can follow.

---

## Validation Rules

| Rule                                           | Why |
|------------------------------------------------|-----|
| `version == 1`                                 | Confirms layout. |
| Counts match array lengths                     | Prevents read overruns. |
| Positive dimensions (radius/height/extents)    | Zero/negative sizes break tests. |
| Finite, nondegenerate basis and valid primitive dimensions | Check the resulting volume; game support for scaled collision bases is not established here. |

### Blender round-trip checks

From the repository root, run the regression scripts with Blender (not system Python):

```powershell
blender --background --factory-startup --python-exit-code 1 --python tests\blender_collision_box_roundtrip.py
blender --background --factory-startup --python-exit-code 1 --python tests\blender_collision_cylinder_roundtrip.py
```

The cylinder script optionally accepts `-- --drs-fixture "C:\path\source.drs"` to check a real asset's collision geometry and coordinate systems across repeated binary round trips. Fixtures are read only; the scripts never save over source assets.

---

## Performance Notes

- Spheres are the cheapest test, boxes next, cylinders slightly heavier.
- Keep the number of shapes minimal; a few well-placed volumes beat many tiny ones.

---

## Cross-References

- **Header / Nodes:** See [Header → NodeInformation](../drs/header.md#nodeinformation) for how this block is linked.
- **Glossary:** [MagicValues → `collisionShape`](../glossary.md#magicvalues) for the container-level magic ID.
- **Geometry:** Often paired with [CGeoOBBTree](./cgeoobbtree.md) and [CGeoMesh](./cgeomesh.md).
- **Common structs:** [CMatCoordinateSystem](../drs/common.md#cmatcoordinatesystem), [Vector3](../drs/common.md#vector3).

---

## Known Variants / Game Differences

- Current data uses the three concrete shape arrays shown above. No union/variant record is present.

---

## Nice to know

The node name is stored as **`collisionShape`** (lowercase **c**) in the hierarchy.
