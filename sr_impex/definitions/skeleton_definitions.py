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
    version: int = 0  # uint
    identifier: int = 0
    name_length: int = field(default=0, init=False)
    name: str = ""
    child_count: int = 0
    children: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.name_length = len(self.name)

    def read(self, file: BinaryIO) -> "Bone":
        self.version = unpack("I", file.read(4))[0]
        self.identifier = unpack("i", file.read(4))[0]
        self.name_length = unpack("i", file.read(4))[0]
        self.name = (
            unpack(f"{self.name_length}s", file.read(calcsize(f"{self.name_length}s")))[
                0
            ]
            .decode("utf-8")
            .strip("\x00")
        )
        # Bone Name Fixes
        self.name = self.name.replace("building_bandits_air_defense_launcher_", "")
        self.name = self.name.replace("building_frost_fortress_", "")
        self.name = self.name.replace("building_twilight_XL_spawn_shell_", "")
        
        if self.name.startswith("building_nature_versatile_tower_"):
            self.name = self.name.replace("building_nature_versatile_tower_", "")
            if "|" in self.name:
                # Check if the name contains "_jnt1"
                contains_jnt1 = "_jnt1" in self.name
                self.name = self.name.split("|")[-1]
                if contains_jnt1:
                    self.name = self.name.replace("_jnt", "_end")

        if len(self.name) > 63:
            print(f"Falling back to hashed bone name for bone {self.name} due to length > 63")
            self.name = str(hash(self.name))
        self.child_count = unpack("i", file.read(4))[0]
        self.children = list(
            unpack(f"{self.child_count}i", file.read(calcsize(f"{self.child_count}i")))
        )
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.version))
        file.write(pack("i", self.identifier))
        file.write(pack("i", self.name_length))
        file.write(pack(f"{self.name_length}s", self.name.encode("utf-8")))
        file.write(pack("i", self.child_count))
        file.write(pack(f"{self.child_count}i", *self.children))

    def size(self) -> int:
        return 12 + self.name_length + 4 + calcsize(f"{self.child_count}i")


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
    position: "Vector3" = field(default_factory=Vector3)
    parent: int = 0

    def read(self, file: BinaryIO) -> "BoneVertex":
        self.position = Vector3().read(file)
        self.parent = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        self.position.write(file)
        file.write(pack("i", self.parent))

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
        self.magic, self.version, self.bone_matrix_count = unpack("iii", file.read(12))
        self.bone_matrices = [BoneMatrix().read(file) for _ in range(self.bone_matrix_count)]
        self.bone_count = unpack("i", file.read(4))[0]
        self.bones = [Bone().read(file) for _ in range(self.bone_count)]
        self.super_parent = Matrix4x4().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("iii", self.magic, self.version, self.bone_matrix_count))
        for bone_matrix in self.bone_matrices:
            bone_matrix.write(file)
        file.write(pack("i", self.bone_count))
        for bone in self.bones:
            bone.write(file)
        self.super_parent.write(file)

    def size(self) -> int:
        return (
            16
            + sum(bone_matrix.size() for bone_matrix in self.bone_matrices)
            + sum(bone.size() for bone in self.bones)
            + self.super_parent.size()
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
