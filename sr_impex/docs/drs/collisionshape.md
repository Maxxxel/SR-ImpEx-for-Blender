# CollisionShape
<a id="collisionshape"></a>

Defines one or more simple **collision volumes** (boxes, spheres, cylinders) that describe the physical space of a static or animated object.  
Used mainly for hit detection, selection, and physics approximation.  
Each shape is positioned and rotated through its own [`CMatCoordinateSystem`](common.md#cmatcoordinatesystem).

---

## Overview

A `CollisionShape` block can include **multiple primitives** of different types:
- **BoxShape** – rectangular volumes (axis-aligned or oriented)
- **SphereShape** – spherical volumes
- **CylinderShape** – cylindrical volumes

All primitives are stored together in one structure along with their counts.

---

## General Structure

| Field | Type | Description |
|-------|------|-------------|
| `version` | byte | Format version (usually `1`). |
| `box_count` | uint | Number of box shapes. |
| `boxes` | List of [BoxShape](#boxshape) | Box-shaped volumes. |
| `sphere_count` | uint | Number of sphere shapes. |
| `spheres` | List of [SphereShape](#sphereshape) | Spherical volumes. |
| `cylinder_count` | uint | Number of cylinder shapes. |
| `cylinders` | List of [CylinderShape](#cylindershape) | Cylindrical volumes. |

---

## BoxShape
<a id="boxshape"></a>

Represents a **rectangular volume** in 3D space.  
Consists of an oriented transform and a size definition.

| Field | Type | Description |
|-------|------|-------------|
| `coord_system` | [CMatCoordinateSystem](common.md#cmatcoordinatesystem) | Orientation and position of the box. |
| `geo_aabox` | [CGeoAABox](#cgeoaabox) | Defines the box’s dimensions via lower and upper corners. |

**Usage**  
Used for most environment and structure collisions — simple and efficient for broad-phase physics.

---

## CGeoAABox
<a id="cgeoaabox"></a>

Defines the **axis-aligned bounding box** dimensions for a box shape.

| Field | Type | Description |
|-------|------|-------------|
| `lower_left_corner` | [Vector3](common.md#vector3) | One corner of the box. |
| `upper_right_corner` | [Vector3](common.md#vector3) | Opposite corner of the box. |

**Interpretation**  
Together, these corners define the local extents of the box relative to its coordinate system.

---

## SphereShape
<a id="sphereshape"></a>

Represents a **spherical collision volume**.

| Field | Type | Description |
|-------|------|-------------|
| `coord_system` | [CMatCoordinateSystem](common.md#cmatcoordinatesystem) | Position and orientation (only position is relevant). |
| `geo_sphere` | [CGeoSphere](#cgeosphere) | Radius and center of the sphere. |

### CGeoSphere
<a id="cgeosphere"></a>

| Field | Type | Description |
|-------|------|-------------|
| `radius` | float | Radius of the sphere. |
| `center` | [Vector3](common.md#vector3) | Sphere center (usually `(0,0,0)` in local space). |

---

## CylinderShape
<a id="cylindershape"></a>

Defines a **cylindrical collision volume**, useful for tall objects or units with circular bases.

| Field | Type | Description |
|-------|------|-------------|
| `coord_system` | [CMatCoordinateSystem](common.md#cmatcoordinatesystem) | Orientation and position of the cylinder. |
| `geo_cylinder` | [CGeoCylinder](#cgeocylinder) | Geometric data (center, height, radius). |

### CGeoCylinder
<a id="cgeocylinder"></a>

| Field | Type | Description |
|-------|------|-------------|
| `center` | [Vector3](common.md#vector3) | Central point of the cylinder. |
| `height` | float | Cylinder height along its local up-axis. |
| `radius` | float | Radius of the base circle. |

---

## Concept Summary

- Each primitive is defined **in its own local coordinate system**, enabling rotation and translation relative to the model.  
- Combined, all primitives form a **compound collision volume** approximating the full object shape.  
- The data structure focuses on **efficiency and simplicity**, not per-triangle accuracy.  
- Primarily used by static geometry or units where precise physics simulation is not needed.

---

## Cross-References
- See [CGeoMesh](cgeomesh.md) for visual geometry.  
- See [CMatCoordinateSystem](common.md#cmatcoordinatesystem) for how transformations are stored.  
- Glossary: [`MagicValues → collisionShape`](glossary.md#magicvalues)

--

## Nice to know

The node is saved as `collisionShape` with a lowercase c.