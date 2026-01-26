"""
Collision-related class definitions for DRS files.

This module contains classes related to collision shape data structures:
- CGeoAABox: Axis-aligned bounding box geometry
- BoxShape: Box collision shape with coordinate system
- CGeoCylinder: Cylinder geometry with center, height, and radius
- CylinderShape: Cylinder collision shape with coordinate system
- CGeoSphere: Sphere geometry with center and radius
- SphereShape: Sphere collision shape with coordinate system
- CollisionShape: Complete collision shape container with boxes, spheres, and cylinders
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack
from typing import BinaryIO, List

from sr_impex.definitions.base_types import (
    Vector3,
    CMatCoordinateSystem,
)


@dataclass(eq=True, repr=False)
class CGeoAABox:
    lower_left_corner: Vector3 = field(default_factory=Vector3)
    upper_right_corner: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "CGeoAABox":
        self.lower_left_corner = Vector3().read(file)
        self.upper_right_corner = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.lower_left_corner.write(file)
        self.upper_right_corner.write(file)

    def size(self) -> int:
        return self.lower_left_corner.size() + self.upper_right_corner.size()


@dataclass(eq=True, repr=False)
class BoxShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_aabox: CGeoAABox = field(default_factory=CGeoAABox)

    def read(self, file: BinaryIO) -> "BoxShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_aabox = CGeoAABox().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_aabox.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_aabox.size()


@dataclass(eq=True, repr=False)
class CGeoCylinder:
    center: Vector3 = field(default_factory=Vector3)
    height: float = 0.0
    radius: float = 0.0

    def read(self, file: BinaryIO) -> "CGeoCylinder":
        self.center = Vector3().read(file)
        self.height, self.radius = unpack("ff", file.read(8))
        return self

    def write(self, file: BinaryIO) -> None:
        self.center.write(file)
        file.write(pack("ff", self.height, self.radius))

    def size(self) -> int:
        return self.center.size() + 8


@dataclass(eq=True, repr=False)
class CylinderShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_cylinder: CGeoCylinder = field(default_factory=CGeoCylinder)

    def read(self, file: BinaryIO) -> "CylinderShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_cylinder = CGeoCylinder().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_cylinder.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_cylinder.size()


@dataclass(eq=True, repr=False)
class CGeoSphere:
    radius: float = 0.0
    center: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "CGeoSphere":
        self.radius = unpack("f", file.read(4))[0]
        self.center = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("f", self.radius))
        self.center.write(file)

    def size(self) -> int:
        return 4 + self.center.size()


@dataclass(eq=True, repr=False)
class SphereShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_sphere: CGeoSphere = field(default_factory=CGeoSphere)

    def read(self, file: BinaryIO) -> "SphereShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_sphere = CGeoSphere().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_sphere.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_sphere.size()


@dataclass(eq=True, repr=False)
class CollisionShape:
    version: int = 1
    box_count: int = 0
    boxes: List[BoxShape] = field(default_factory=list)
    sphere_count: int = 0
    spheres: List[SphereShape] = field(default_factory=list)
    cylinder_count: int = 0
    cylinders: List[CylinderShape] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CollisionShape":
        self.version = unpack("B", file.read(1))
        self.box_count = unpack("I", file.read(4))[0]
        self.boxes = [BoxShape().read(file) for _ in range(self.box_count)]
        self.sphere_count = unpack("I", file.read(4))[0]
        self.spheres = [SphereShape().read(file) for _ in range(self.sphere_count)]
        self.cylinder_count = unpack("I", file.read(4))[0]
        self.cylinders = [
            CylinderShape().read(file) for _ in range(self.cylinder_count)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("B", self.version))
        file.write(pack("I", self.box_count))
        for box in self.boxes:
            box.write(file)

        file.write(pack("I", self.sphere_count))
        for sphere in self.spheres:
            sphere.write(file)

        file.write(pack("I", self.cylinder_count))
        for cylinder in self.cylinders:
            cylinder.write(file)

    def size(self) -> int:
        return (
            1
            + 12
            + sum(box.size() for box in self.boxes)
            + sum(sphere.size() for sphere in self.spheres)
            + sum(cylinder.size() for cylinder in self.cylinders)
        )
