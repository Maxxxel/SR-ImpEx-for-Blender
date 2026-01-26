"""
OBB (Oriented Bounding Box) tree class definitions for DRS files.

This module contains classes related to OBB tree data structures:
- OBBNode: Individual oriented bounding box node with children and triangle info
- CGeoOBBTree: Complete OBB tree with nodes and face data
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack
from typing import BinaryIO, List

from sr_impex.definitions.base_types import (
    CMatCoordinateSystem,
    Face,
)


@dataclass(eq=False, repr=False)
class OBBNode:
    oriented_bounding_box: CMatCoordinateSystem = field(
        default_factory=CMatCoordinateSystem
    )
    first_child_index: int = 0
    second_child_index: int = 0
    skip_pointer: int = 0
    node_depth: int = 0
    triangle_offset: int = 0
    total_triangles: int = 0

    def read(self, file: BinaryIO) -> "OBBNode":
        self.oriented_bounding_box = CMatCoordinateSystem().read(file)
        (
            self.first_child_index,
            self.second_child_index,
            self.skip_pointer,
            self.node_depth,
            self.triangle_offset,
            self.total_triangles,
        ) = unpack("4H2I", file.read(16))
        return self

    def write(self, file: BinaryIO) -> None:
        self.oriented_bounding_box.write(file)
        file.write(
            pack(
                "4H2I",
                self.first_child_index,
                self.second_child_index,
                self.skip_pointer,
                self.node_depth,
                self.triangle_offset,
                self.total_triangles,
            )
        )

    def size(self) -> int:
        return self.oriented_bounding_box.size() + 16


@dataclass(eq=False, repr=False)
class CGeoOBBTree:
    magic: int = 1845540702
    version: int = 3
    matrix_count: int = 0
    obb_nodes: List[OBBNode] = field(default_factory=list)
    triangle_count: int = 0
    faces: List[Face] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CGeoOBBTree":
        self.magic, self.version, self.matrix_count = unpack("iii", file.read(12))
        self.obb_nodes = [OBBNode().read(file) for _ in range(self.matrix_count)]
        self.triangle_count = unpack("i", file.read(4))[0]
        self.faces = [Face().read(file) for _ in range(self.triangle_count)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("iii", self.magic, self.version, self.matrix_count))
        for obb_node in self.obb_nodes:
            obb_node.write(file)
        file.write(pack("i", self.triangle_count))
        for face in self.faces:
            face.write(file)

    def size(self) -> int:
        return (
            16
            + sum(obb_node.size() for obb_node in self.obb_nodes)
            + sum(face.size() for face in self.faces)
        )
