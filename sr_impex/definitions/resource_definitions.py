"""
Resource and primitive container class definitions for DRS files.

This module contains classes related to resource metadata:
- DrwResourceMeta: Resource metadata with version, unknown field, and hash
- CGeoPrimitiveContainer: Empty primitive container class
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
    unknown: int = 1  # Units: 1, 0 - 3 are possible
    length: int = 0
    hash: str = ""

    def read(self, file: BinaryIO) -> "DrwResourceMeta":
        """Reads the DrwResourceMeta from the buffer"""
        self.version, self.unknown = unpack("2i", file.read(8))
        self.length = unpack("i", file.read(4))[0]
        self.hash = file.read(self.length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        """Writes the DrwResourceMeta to the buffer"""
        file.write(pack("i", self.version))
        file.write(pack("i", self.unknown))
        file.write(pack("i", self.length))
        file.write(self.hash.encode("utf-8"))

    def size(self) -> int:
        """Returns the size of the DrwResourceMeta"""
        return calcsize(f"2ii{self.length}s")


@dataclass(eq=False, repr=False)
class CGeoPrimitiveContainer:
    """CGeoPrimitiveContainer class"""

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
class IKAtlas:
    """IKAtlas"""

    identifier: int = 0  # BoneID
    version: int = 2
    axis: int = 2  # Always 2
    chain_order: int = 0  # Order of Execution in the Bone Chain
    constraints: List[Constraint] = field(default_factory=list)  # Always 3!
    purpose_flags: int = 0  # 1, 2, 3, 6, 7: mostly 3, but what is it used for?

    def read(self, file: BinaryIO) -> "IKAtlas":
        """Reads the IKAtlas from the buffer"""
        self.identifier = unpack("i", file.read(4))[0]
        self.version = unpack("h", file.read(2))[0]
        if self.version >= 1:
            self.axis, self.chain_order = unpack("ii", file.read(8))
            self.constraints = [Constraint().read(file) for _ in range(3)]
            if self.version >= 2:
                self.purpose_flags = unpack("h", file.read(2))[0]
        return self

    def write(self, file: BinaryIO):
        """Writes the IKAtlas to the buffer"""
        file.write(pack("i", self.identifier))
        file.write(pack("h", self.version))
        if self.version >= 1:
            file.write(pack("ii", self.axis, self.chain_order))
            for constraint in self.constraints:
                constraint.write(file)
            if self.version >= 2:
                file.write(pack("h", self.purpose_flags))

    def size(self) -> int:
        """Returns the size of the IKAtlas"""
        base = 6
        if self.version >= 1:
            base += 8 + sum(constraint.size() for constraint in self.constraints)
            if self.version >= 2:
                base += 2
        return base
