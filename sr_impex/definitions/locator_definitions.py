"""
Locator class definitions for DRS files.

This module contains classes related to locator data structures:
- SLocator: Individual locator with position, class, bone, and filename
- CDrwLocatorList: Complete locator list container
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack
from typing import BinaryIO, List

from sr_impex.definitions.base_types import CMatCoordinateSystem
from sr_impex.definitions.enums import LocatorClass


@dataclass(eq=False, repr=False)
class SLocator:
    cmat_coordinate_system: CMatCoordinateSystem = field(
        default_factory=CMatCoordinateSystem
    )
    class_id: int = 0
    bone_id: int = 0
    file_name_length: int = 0
    file_name: str = ""
    uk_int: int = -1  # Compatibility field name: version-5 SubID.
    class_type: str = ""

    @property
    def sub_id(self) -> int:
        return self.uk_int

    @sub_id.setter
    def sub_id(self, value: int) -> None:
        self.uk_int = value

    def read(self, file: BinaryIO, version: int) -> "SLocator":
        self.cmat_coordinate_system = CMatCoordinateSystem().read(file)
        self.class_id, self.bone_id, self.file_name_length = unpack(
            "<iiI", file.read(12)
        )
        raw_name = file.read(self.file_name_length)
        if len(raw_name) != self.file_name_length:
            raise ValueError("Truncated locator filename")
        self.file_name = raw_name.decode("utf-8", errors="surrogateescape")
        # Get LocatorClass from ClassID
        self.class_type = LocatorClass.get(self.class_id, "Unknown")
        self.uk_int = unpack("<i", file.read(4))[0] if version == 5 else -1
        return self

    def write(self, file: BinaryIO, version: int = 5) -> None:
        raw_name = self.file_name.encode("utf-8", errors="surrogateescape")
        self.file_name_length = len(raw_name)
        self.cmat_coordinate_system.write(file)
        file.write(pack("<iiI", self.class_id, self.bone_id, self.file_name_length))
        file.write(raw_name)
        if version == 5:
            file.write(pack("<i", self.uk_int))

    def size(self, version: int = 5) -> int:
        return 60 + len(self.file_name.encode("utf-8", errors="surrogateescape")) + (4 if version == 5 else 0)


@dataclass(eq=False, repr=False)
class CDrwLocatorList:
    magic: int = 281702437
    version: int = 5
    length: int = 0
    slocators: List[SLocator] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CDrwLocatorList":
        self.magic, self.version, self.length = unpack("iii", file.read(12))
        if self.version not in (4, 5):
            raise ValueError(f"Unsupported locator list magic/version: {self.magic:#x}/{self.version}")
        self.slocators = [
            SLocator().read(file, self.version) for _ in range(self.length)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        if self.version not in (4, 5):
            raise ValueError(f"Unsupported locator list magic/version: {self.magic:#x}/{self.version}")
        self.length = len(self.slocators)
        file.write(pack("iii", self.magic, self.version, self.length))
        for locator in self.slocators:
            locator.write(file, self.version)

    def size(self) -> int:
        return 12 + sum(locator.size(self.version) for locator in self.slocators)
