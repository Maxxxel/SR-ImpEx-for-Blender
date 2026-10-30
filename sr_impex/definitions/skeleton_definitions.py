"""
Skeleton and bone-related class definitions for DRS files.

This module contains classes related to skeleton/bone data structures:
- Bone: Individual bone with hierarchy information
- BoneMatrix: Matrix of bone vertices
- BoneVertex: Vertex with bone parent information
- DRSBone: Blender-specific bone representation
- BoneWeight: Bone weight data
- CSkSkeleton: Complete skeleton with bones and matrices
- CSkSkinInfo: Skin info with vertex weight data
- CDspJointMap: Joint mapping information
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List

from mathutils import Matrix, Quaternion, Vector

from sr_impex.definitions.base_types import (
    Vector3,
    Matrix4x4,
)
from sr_impex.definitions.mesh_definitions import VertexData


@dataclass(eq=False, repr=False)
class Bone:
    version: int = 0  # uint32 joint lookup key, not a format version
    identifier: int = 0
    name_length: int = field(default=0, init=False)
    name: str = ""
    child_count: int = 0
    children: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.name_length = len(self.name.encode("utf-8", errors="surrogateescape"))

    def read(self, file: BinaryIO) -> "Bone":
        self.version, self.identifier, self.name_length = unpack("<IiI", file.read(12))
        raw_name = file.read(self.name_length)
        if len(raw_name) != self.name_length:
            raise ValueError("Truncated skeleton bone name")
        # Names are length-delimited engine bytes. Blender aliases belong in the UI layer.
        self.name = raw_name.decode("utf-8", errors="surrogateescape")
        self.child_count = unpack("<I", file.read(4))[0]
        self.children = list(
            unpack(f"<{self.child_count}i", file.read(calcsize(f"<{self.child_count}i")))
        )
        return self

    def write(self, file: BinaryIO) -> None:
        raw_name = self.name.encode("utf-8", errors="surrogateescape")
        if self.child_count != len(self.children):
            raise ValueError("Skeleton bone child count does not match children")
        self.name_length = len(raw_name)
        file.write(pack("<IiI", self.version, self.identifier, self.name_length))
        file.write(raw_name)
        file.write(pack("<I", self.child_count))
        file.write(pack(f"<{self.child_count}i", *self.children))

    def size(self) -> int:
        return 16 + len(self.name.encode("utf-8", errors="surrogateescape")) + 4 * len(self.children)


@dataclass(eq=False, repr=False)
class BoneMatrix:
    bone_vertices: List["BoneVertex"] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "BoneMatrix":
        self.bone_vertices = [BoneVertex().read(file) for _ in range(4)]
        return self

    def write(self, file: BinaryIO):
        for bone_vertex in self.bone_vertices:
            bone_vertex.write(file)

    def size(self) -> int:
        return sum(bv.size() for bv in self.bone_vertices)


@dataclass(eq=False, repr=False)
class BoneVertex:
    """One joint row: xyz plus a non-float word. Only row 0 stores a parent.

    Row 1 stores the sorted joint-metadata index. Rows 2/3 are preserved raw
    auxiliary words, not additional parents or homogeneous matrix components.
    """
    position: "Vector3" = field(default_factory=Vector3)
    parent: int = 0

    def read(self, file: BinaryIO) -> "BoneVertex":
        self.position = Vector3().read(file)
        self.parent = unpack("<i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        self.position.write(file)
        file.write(pack("<i", self.parent))

    def size(self) -> int:
        return self.position.size() + 4


class DRSBone:
    """docstring for DRSBone"""

    def __init__(self) -> None:
        self.ska_identifier: int
        self.identifier: int
        self.name: str
        self.parent: int = -1
        self.bone_matrix: Matrix
        self.children: List[int]
        self.bind_loc: Vector
        self.bind_rot: Quaternion


class BoneWeight:
    def __init__(self, indices=None, weights=None):
        self.indices: List[int] = indices
        self.weights: List[float] = weights


@dataclass(eq=False, repr=False)
class CSkSkeleton:
    magic: int = 1558308612
    version: int = 3
    bone_matrix_count: int = 0
    bone_matrices: List[BoneMatrix] = field(default_factory=list)
    bone_count: int = 0
    bones: List[Bone] = field(default_factory=list)
    super_parent: Matrix4x4 = field(
        default_factory=lambda: Matrix4x4(
            ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        )
    )

    def read(self, file: BinaryIO) -> "CSkSkeleton":
        self.magic, self.version, self.bone_matrix_count = unpack("<III", file.read(12))
        if self.magic != 0x5CE1E704:
            raise ValueError(f"Invalid CSkSkeleton magic 0x{self.magic:08x}")
        if self.version not in (2, 3):
            raise ValueError(f"Unsupported CSkSkeleton version {self.version}; expected 2 or 3")
        self.bone_matrices = [BoneMatrix().read(file) for _ in range(self.bone_matrix_count)]
        self.bone_count = unpack("<I", file.read(4))[0]
        self.bones = [Bone().read(file) for _ in range(self.bone_count)]
        self.super_parent = (Matrix4x4().read(file) if self.version == 3 else
                             Matrix4x4(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
        self.validate()
        return self

    def validate(self) -> None:
        n = self.bone_matrix_count
        if n != len(self.bone_matrices) or self.bone_count != len(self.bones) or n != self.bone_count:
            raise ValueError("Skeleton joint/matrix counts do not match")
        keys = [bone.version for bone in self.bones]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("Skeleton joint keys must be unique and sorted as uint32")
        if sorted(bone.identifier for bone in self.bones) != list(range(n)):
            raise ValueError("Skeleton joint indices must cover 0..joint_count-1")
        parents_from_children = {}
        for bone in self.bones:
            if bone.child_count != len(bone.children):
                raise ValueError("Skeleton bone child count does not match children")
            for child in bone.children:
                if not 0 <= child < n or child in parents_from_children:
                    raise ValueError("Skeleton child index is invalid or has multiple parents")
                parents_from_children[child] = bone.identifier
        for index, matrix in enumerate(self.bone_matrices):
            if len(matrix.bone_vertices) != 4:
                raise ValueError("Skeleton joint record requires four xyz/word rows")
            parent = matrix.bone_vertices[0].parent
            reverse = matrix.bone_vertices[1].parent
            if parent < -1 or parent >= index:
                raise ValueError("Skeleton parents must precede children, or be -1 for a root")
            if parent != parents_from_children.get(index, -1):
                raise ValueError("Skeleton matrix parents disagree with metadata children")
            if not 0 <= reverse < n or self.bones[reverse].identifier != index:
                raise ValueError("Skeleton matrix metadata index does not point back to its joint")

    def write(self, file: BinaryIO) -> None:
        if self.magic != 0x5CE1E704 or self.version not in (2, 3):
            raise ValueError("Unsupported CSkSkeleton header")
        self.validate()
        file.write(pack("<III", self.magic, self.version, self.bone_matrix_count))
        for bone_matrix in self.bone_matrices:
            bone_matrix.write(file)
        file.write(pack("<I", self.bone_count))
        for bone in self.bones:
            bone.write(file)
        if self.version == 3:
            self.super_parent.write(file)

    def size(self) -> int:
        return (
            16
            + sum(bone_matrix.size() for bone_matrix in self.bone_matrices)
            + sum(bone.size() for bone in self.bones)
            + (self.super_parent.size() if self.version == 3 else 0)
        )


@dataclass(eq=False, repr=False)
class CSkSkinInfo:
    version: int = 1
    vertex_count: int = 0
    vertex_data: List[VertexData] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CSkSkinInfo":
        self.version, self.vertex_count = unpack("ii", file.read(8))
        self.vertex_data = [VertexData().read(file) for _ in range(self.vertex_count)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("ii", self.version, self.vertex_count))
        for vertex in self.vertex_data:
            vertex.write(file)

    def size(self) -> int:
        return 8 + sum(vd.size() for vd in self.vertex_data)


@dataclass(eq=False, repr=False)
class JointGroup:
    joint_count: int = 0
    joints: List[int] = field(default_factory=list)  # short

    def read(self, file: BinaryIO) -> "JointGroup":
        self.joint_count = unpack("i", file.read(4))[0]
        for _ in range(self.joint_count):
            self.joints.append(unpack("h", file.read(2))[0])
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.joint_count))
        for joint in self.joints:
            file.write(pack("h", joint))

    def size(self) -> int:
        return 4 + 2 * len(self.joints)


@dataclass(eq=False, repr=False)
class CDspJointMap:
    version: int = 1
    joint_group_count: int = 0
    joint_groups: List[JointGroup] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CDspJointMap":
        self.version = unpack("i", file.read(4))[0]
        self.joint_group_count = unpack("i", file.read(4))[0]
        self.joint_groups = [
            JointGroup().read(file) for _ in range(self.joint_group_count)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("ii", self.version, self.joint_group_count))
        for joint_group in self.joint_groups:
            joint_group.write(file)

    def size(self) -> int:
        return 8 + sum(joint_group.size() for joint_group in self.joint_groups)
