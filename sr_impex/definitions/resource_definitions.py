"""
Resource and primitive container class definitions for DRS files.

This module contains classes related to resource metadata:
- DrwResourceMeta: Versioned resource class and authoring identifier string
- CGeoPrimitiveContainer: Empty DRS parent for the collisionShape child payload
- Constraint: Bone constraint with angle and damping parameters
- IKAtlas: IK constraint atlas
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List


@dataclass(eq=False, repr=False)
class DrwResourceMeta:
    version: int = 1
    unknown: int = 1  # Compatibility name for CDrwResource::GetClass() value.
    length: int = 0
    hash: str = ""

    @property
    def resource_class(self) -> int:
        return self.unknown

    @resource_class.setter
    def resource_class(self, value: int) -> None:
        self.unknown = value

    def read(self, file: BinaryIO) -> "DrwResourceMeta":
        """Reads the DrwResourceMeta from the buffer"""
        self.version = unpack("<I", file.read(4))[0]
        if self.version not in (0, 1):
            raise ValueError(f"Unsupported DrwResourceMeta version {self.version}")
        self.unknown = unpack("<I", file.read(4))[0] if self.version == 1 else 0
        self.length = unpack("<I", file.read(4))[0]
        raw = file.read(self.length)
        if len(raw) != self.length:
            raise ValueError("Truncated DrwResourceMeta identifier")
        self.hash = raw.decode("utf-8", errors="surrogateescape")
        return self

    def write(self, file: BinaryIO) -> None:
        """Writes the DrwResourceMeta to the buffer"""
        if self.version not in (0, 1):
            raise ValueError(f"Unsupported DrwResourceMeta version {self.version}")
        raw = self.hash.encode("utf-8", errors="surrogateescape")
        self.length = len(raw)
        file.write(pack("<I", self.version))
        if self.version == 1:
            file.write(pack("<I", self.unknown))
        file.write(pack("<I", self.length))
        file.write(raw)

    def size(self) -> int:
        """Returns the size of the DrwResourceMeta"""
        return (12 if self.version == 1 else 8) + len(self.hash.encode("utf-8", errors="surrogateescape"))


@dataclass(eq=False, repr=False)
class CGeoPrimitiveContainer:
    """Zero-byte parent node; collisionShape holds the serialized primitives.

    The runtime CGeoPrimitiveContainer is not empty: it owns box/sphere/cylinder
    arrays. DRS NodeInformation must link this parent to the collisionShape child.
    """

    def read(self, _: BinaryIO) -> "CGeoPrimitiveContainer":
        """Reads the CGeoPrimitiveContainer from the buffer"""
        # Add code here if you need to read specific data for this class
        return self

    def write(self, _: BinaryIO) -> None:
        """Writes the CGeoPrimitiveContainer to the buffer (no payload)."""

    def size(self) -> int:
        """Returns the size of the CGeoPrimitiveContainer"""
        return 0


@dataclass(eq=False, repr=False)
class Constraint:
    """Constraint
    Default: <Constraint index="0" RightAngle="360.00000000" RightDampStart="360.00000000" LeftAngle="-360.00000000" LeftDampStart="-360.00000000" DampRatio="0.00000000" />
    Custom:  <Constraint index="1" RightAngle="35.00000000" RightDampStart="35.00000000" LeftAngle="-35.00000000" LeftDampStart="-35.00000000" DampRatio="0.00000000" />
    Default: <Constraint index="2" RightAngle="360.00000000" RightDampStart="360.00000000" LeftAngle="-360.00000000" LeftDampStart="-360.00000000" DampRatio="0.00000000" />
    """

    # Values are saved in RAD but are DEG
    revision: int = 1  # verified
    left_angle: float = -6.283185
    right_angle: float = 6.283185
    left_damp_start: float = -6.283185
    right_damp_start: float = 6.283185
    damp_ratio: float = 0.0  # 0 mostly, ranges from 0 to 1

    def read(self, file: BinaryIO) -> "Constraint":
        """Reads the Constraint from the buffer"""
        self.revision = unpack("h", file.read(2))[0]
        if self.revision == 1:
            (
                self.left_angle,
                self.right_angle,
                self.left_damp_start,
                self.right_damp_start,
                self.damp_ratio,
            ) = unpack("5f", file.read(20))
        return self

    def write(self, file: BinaryIO):
        """Writes the Constraint to the buffer"""
        file.write(pack("h", self.revision))
        if self.revision == 1:
            file.write(
                pack(
                    "5f",
                    self.left_angle,
                    self.right_angle,
                    self.left_damp_start,
                    self.right_damp_start,
                    self.damp_ratio,
                )
            )

    def size(self) -> int:
        """Returns the size of the Constraint"""
        base = 2
        if self.revision == 1:
            base += 20
        return base


@dataclass(eq=False, repr=False)
class IKJointConstraint:
    """One CSkIKJointConstraint entry, prefixed by its skeleton joint index.

    ``IKAtlas`` remains a compatibility alias; the actual atlas is the outer
    version/count container in AnimationSet.
    """

    identifier: int = 0  # Skeleton joint index, not the CRC animation joint key
    version: int = 2
    axis: int = 2  # Always 2
    chain_order: int = 0  # Order of Execution in the Bone Chain
    constraints: List[Constraint] = field(default_factory=list)  # Always 3!
    purpose_flags: int = 0  # 1, 2, 3, 6, 7: mostly 3, but what is it used for?

    @property
    def joint_index(self) -> int:
        return self.identifier

    @joint_index.setter
    def joint_index(self, value: int) -> None:
        self.identifier = value

    def read(self, file: BinaryIO) -> "IKAtlas":
        """Reads the IKAtlas from the buffer"""
        self.identifier = unpack("i", file.read(4))[0]
        self.version = unpack("h", file.read(2))[0]
        if self.version >= 1:
            self.axis, self.chain_order = unpack("ii", file.read(8))
            self.constraints = [Constraint().read(file) for _ in range(3)]
            if self.version >= 2:
                self.purpose_flags = unpack("H", file.read(2))[0]
        return self

    def write(self, file: BinaryIO):
        """Writes the IKAtlas to the buffer"""
        if self.version >= 1 and len(self.constraints) != 3:
            raise ValueError("An IK joint constraint requires exactly three axis constraints")
        file.write(pack("i", self.identifier))
        file.write(pack("h", self.version))
        if self.version >= 1:
            file.write(pack("ii", self.axis, self.chain_order))
            for constraint in self.constraints:
                constraint.write(file)
            if self.version >= 2:
                file.write(pack("H", self.purpose_flags))

    def size(self) -> int:
        """Returns the size of the IKAtlas"""
        base = 6
        if self.version >= 1:
            base += 8 + sum(constraint.size() for constraint in self.constraints)
            if self.version >= 2:
                base += 2
        return base


IKAtlas = IKJointConstraint
