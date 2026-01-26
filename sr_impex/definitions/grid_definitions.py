"""
Grid and mesh module class definitions for BMG files.

This module contains classes related to grid-based building mesh layouts:
- SMeshState: State-based mesh state containing DRS file references
- DestructionState: Destruction state referencing destruction mesh files
- StateBasedMeshSet: Set of mesh states and destruction states
- MeshGridModule: Individual module in a mesh grid
- MeshSetGrid: Grid-based mesh set for building layouts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List

from sr_impex.definitions.locator_definitions import CDrwLocatorList


@dataclass(eq=False, repr=False)
class SMeshState:
    """State-based mesh state containing DRS file references"""
    state_num: int = 0  # Int Always 0
    has_files: int = 0  # Short Always 1
    uk_file_length: int = 0  # Int Always 0
    uk_file: str = ""  # String Always ""
    drs_file_length: int = 0  # Int
    drs_file: str = ""  # String

    def read(self, file: BinaryIO) -> "SMeshState":
        """Reads the SMeshState from the buffer"""
        self.state_num = unpack("i", file.read(4))[0]
        self.has_files = unpack("h", file.read(2))[0]
        if self.has_files:
            self.uk_file_length = unpack("i", file.read(4))[0]
            self.uk_file = (
                unpack(
                    f"{self.uk_file_length}s",
                    file.read(calcsize(f"{self.uk_file_length}s")),
                )[0]
                .decode("utf-8")
                .strip("\x00")
            )
            self.drs_file_length = unpack("i", file.read(4))[0]
            self.drs_file = (
                unpack(
                    f"{self.drs_file_length}s",
                    file.read(calcsize(f"{self.drs_file_length}s")),
                )[0]
                .decode("utf-8")
                .strip("\x00")
            )
        return self

    def write(self, file: BinaryIO):
        file.write(pack("i", self.state_num))
        file.write(pack("h", self.has_files))
        if self.has_files:
            file.write(pack("i", self.uk_file_length))
            file.write(self.uk_file.encode("utf-8"))
            file.write(pack("i", self.drs_file_length))
            file.write(self.drs_file.encode("utf-8"))

    def size(self) -> int:
        size = 6
        if self.has_files:
            size += 4 + self.uk_file_length + 4 + self.drs_file_length
        return size


@dataclass(eq=False, repr=False)
class DestructionState:
    """Destruction state referencing destruction mesh files"""
    state_num: int = 0  # Int
    file_name_length: int = 0  # Int
    file_name: str = ""  # String

    def read(self, file: BinaryIO) -> "DestructionState":
        """Reads the DestructionState from the buffer"""
        self.state_num = unpack("i", file.read(4))[0]
        self.file_name_length = unpack("i", file.read(4))[0]
        self.file_name = (
            unpack(
                f"{self.file_name_length}s",
                file.read(calcsize(f"{self.file_name_length}s")),
            )[0]
            .decode("utf-8")
            .strip("\x00")
        )
        return self

    def write(self, file: BinaryIO):
        file.write(pack("i", self.state_num))
        file.write(pack("i", self.file_name_length))
        file.write(self.file_name.encode("utf-8"))

    def size(self) -> int:
        return 8 + self.file_name_length


@dataclass(eq=False, repr=False)
class StateBasedMeshSet:
    """Set of mesh states and destruction states"""
    version: int = 1  # Short
    revision: int = 10  # Int
    num_mesh_states: int = 1  # Int Always needs one
    mesh_states: List[SMeshState] = field(default_factory=list)
    num_destruction_states: int = 1  # Int
    destruction_states: List[DestructionState] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "StateBasedMeshSet":
        """Reads the StateBasedMeshSet from the buffer"""
        self.version = unpack("h", file.read(2))[0]
        self.revision = unpack("i", file.read(4))[0]
        self.num_mesh_states = unpack("i", file.read(4))[0]
        self.mesh_states = [
            SMeshState().read(file) for _ in range(self.num_mesh_states)
        ]
        self.num_destruction_states = unpack("i", file.read(4))[0]
        self.destruction_states = [
            DestructionState().read(file) for _ in range(self.num_destruction_states)
        ]
        return self

    def write(self, file: BinaryIO):
        file.write(pack("h", self.version))
        file.write(pack("i", self.revision))
        file.write(pack("i", self.num_mesh_states))
        for mesh_state in self.mesh_states:
            mesh_state.write(file)
        file.write(pack("i", self.num_destruction_states))
        for destruction_state in self.destruction_states:
            destruction_state.write(file)

    def size(self) -> int:
        size = 6 + 4
        for mesh_state in self.mesh_states:
            size += mesh_state.size()
        size += 4
        for destruction_state in self.destruction_states:
            size += destruction_state.size()
        return size


@dataclass(eq=False, repr=False)
class MeshGridModule:
    """Individual module in a mesh grid"""
    rotation: int = 0  # Short
    has_mesh_set: int = 0  # Byte
    state_based_mesh_set: StateBasedMeshSet = None

    def read(self, file: BinaryIO) -> "MeshGridModule":
        """Reads the MeshGridModule from the buffer"""
        self.rotation = unpack("h", file.read(2))[0]
        self.has_mesh_set = unpack("B", file.read(1))[0]
        if self.has_mesh_set:
            self.state_based_mesh_set = StateBasedMeshSet().read(file)
        return self

    def write(self, file: BinaryIO):
        file.write(pack("h", self.rotation))
        file.write(pack("B", self.has_mesh_set))
        if self.has_mesh_set:
            self.state_based_mesh_set.write(file)

    def size(self) -> int:
        size = 3
        if self.has_mesh_set:
            size += self.state_based_mesh_set.size()
        return size


@dataclass(eq=False, repr=False)
class MeshSetGrid:
    """Grid-based mesh set for building layouts"""
    revision: int = 5  # Short
    grid_width: int = 1  # Byte
    grid_height: int = 1  # Byte
    name_length: int = 0  # Int
    name: str = ""  # String
    uuid_length: int = 0  # Int
    uuid: str = ""  # String
    grid_rotation: int = 0  # Short
    ground_decal_length: int = 0  # Int
    ground_decal: str = ""  # String
    effect_gen_debris_length: int = 0  # Int
    effect_gen_debris: str = ""  # String to XML file. Only used by some fire and nature buildings
    uk_string1_length: int = 0  # Int
    uk_string1: str = ""  # String
    module_distance: float = 2  # Float
    is_center_pivoted: int = 1  # Byte
    mesh_modules: List[MeshGridModule] = field(default_factory=list)
    cdrw_locator_list: CDrwLocatorList = None

    def read(self, file: BinaryIO) -> "MeshSetGrid":
        """Reads the MeshSetGrid from the buffer"""
        self.revision = unpack("h", file.read(2))[0]
        self.grid_width = unpack("B", file.read(1))[0]
        self.grid_height = unpack("B", file.read(1))[0]
        self.name_length = unpack("i", file.read(4))[0]
        self.name = (
            unpack(f"{self.name_length}s", file.read(calcsize(f"{self.name_length}s")))[
                0
            ]
            .decode("utf-8")
            .strip("\x00")
        )
        self.uuid_length = unpack("i", file.read(4))[0]
        self.uuid = (
            unpack(f"{self.uuid_length}s", file.read(calcsize(f"{self.uuid_length}s")))[
                0
            ]
            .decode("utf-8")
            .strip("\x00")
        )
        self.grid_rotation = unpack("h", file.read(2))[0]
        self.ground_decal_length = unpack("i", file.read(4))[0]
        self.ground_decal = (
            unpack(
                f"{self.ground_decal_length}s",
                file.read(calcsize(f"{self.ground_decal_length}s")),
            )[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.effect_gen_debris_length = unpack("i", file.read(4))[0]
        self.effect_gen_debris = (
            unpack(
                f"{self.effect_gen_debris_length}s",
                file.read(calcsize(f"{self.effect_gen_debris_length}s")),
            )[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.uk_string1_length = unpack("i", file.read(4))[0]
        self.uk_string1 = (
            unpack(
                f"{self.uk_string1_length}s",
                file.read(calcsize(f"{self.uk_string1_length}s")),
            )[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.module_distance = unpack("f", file.read(4))[0]
        self.is_center_pivoted = unpack("B", file.read(1))[0]
        self.mesh_modules = [
            MeshGridModule().read(file)
            for _ in range((self.grid_width * 2 + 1) * (self.grid_height * 2 + 1))
        ]
        self.cdrw_locator_list = CDrwLocatorList().read(file)
        return self

    def write(self, file: BinaryIO):
        file.write(pack("h", self.revision))
        file.write(pack("B", self.grid_width))
        file.write(pack("B", self.grid_height))
        file.write(pack("i", self.name_length))
        file.write(self.name.encode("utf-8"))
        file.write(pack("i", self.uuid_length))
        file.write(self.uuid.encode("utf-8"))
        file.write(pack("h", self.grid_rotation))
        file.write(pack("i", self.ground_decal_length))
        file.write(self.ground_decal.encode("utf-8"))
        file.write(pack("i", self.effect_gen_debris_length))
        file.write(self.effect_gen_debris.encode("utf-8"))
        file.write(pack("i", self.uk_string1_length))
        file.write(self.uk_string1.encode("utf-8"))
        file.write(pack("f", self.module_distance))
        file.write(pack("B", self.is_center_pivoted))
        for module in self.mesh_modules:
            module.write(file)
        self.cdrw_locator_list.write(file)

    def size(self) -> int:
        size = (
            2 + 1 + 1 + 4 + self.name_length + 4 + self.uuid_length +
            2 + 4 + self.ground_decal_length + 4 + self.effect_gen_debris_length +
            4 + self.uk_string1_length + 4 + 1
        )
        for module in self.mesh_modules:
            size += module.size()
        size += self.cdrw_locator_list.size()
        return size
