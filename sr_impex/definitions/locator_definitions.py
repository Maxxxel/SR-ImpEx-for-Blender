"""
Locator class definitions for DRS files.

This module contains classes related to locator data structures:
- SLocator: Individual locator with position, class, bone, and filename
- CDrwLocatorList: Complete locator list container
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
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
    uk_int: int = -1
    class_type: str = ""

    def read(self, file: BinaryIO, version: int) -> "SLocator":
        self.cmat_coordinate_system = CMatCoordinateSystem().read(file)
        self.class_id, self.bone_id, self.file_name_length = unpack(
            "iii", file.read(12)
        )
        self.file_name = (
            unpack(
                f"{self.file_name_length}s",
                file.read(calcsize(f"{self.file_name_length}s")),
            )[0]
            .decode("utf-8")
            .strip("\x00")
        )
        # Get LocatorClass from ClassID
        self.class_type = LocatorClass.get(self.class_id, "Unknown")
        if version == 5:
            self.uk_int = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        self.cmat_coordinate_system.write(file)
        file.write(
            pack(
                f"iii{self.file_name_length}s",
                self.class_id,
                self.bone_id,
                self.file_name_length,
                self.file_name.encode("utf-8"),
            )
        )
        if hasattr(self, "uk_int"):
            file.write(pack("i", self.uk_int))

    def size(self) -> int:
        size = self.cmat_coordinate_system.size() + calcsize(
            f"iii{self.file_name_length}s"
        )
        if hasattr(self, "uk_int"):
            size += 4
        return size


@dataclass(eq=False, repr=False)
class CDrwLocatorList:
    magic: int = 281702437
    version: int = 0
    length: int = 0
    slocators: List[SLocator] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CDrwLocatorList":
        self.magic, self.version, self.length = unpack("iii", file.read(12))
        self.slocators = [
            SLocator().read(file, self.version) for _ in range(self.length)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("iii", self.magic, self.version, self.length))
        for locator in self.slocators:
            locator.write(file)

    def size(self) -> int:
        return 12 + sum(locator.size() for locator in self.slocators)
