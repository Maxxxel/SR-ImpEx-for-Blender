"""
Grid and mesh module class definitions for BMG files.

This module contains classes related to grid-based building mesh layouts:
- SMeshState: State-based mesh state containing DRS file references
- StateTransition: Effect associated with entering a destination state
- StateBasedMeshSet: Set of mesh states and destruction states
- MeshGridModule: Individual module in a mesh grid
- MeshSetGrid: Grid-based mesh set for building layouts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List

from sr_impex.definitions.locator_definitions import CDrwLocatorList


def _read_text(owner, file: BinaryIO, name: str, length: int) -> str:
    if length < 0:
        raise ValueError("Negative mesh-set string length")
    raw = file.read(length)
    if len(raw) != length:
        raise EOFError("Truncated mesh-set string")
    text = raw.decode("utf8").strip("\x00")
    setattr(owner, "_original_" + name, (text, raw))
    return text


def _text_bytes(owner, name: str) -> bytes:
    text = getattr(owner, name)
    original = getattr(owner, "_original_" + name, None)
    return original[1] if original is not None and original[0] == text else text.encode("utf8")


@dataclass(eq=False, repr=False)
class SMeshState:
    """State ID plus versioned state FX/resource pair; old field names retained."""
    state_num: int = 0  # uint32 map key, not necessarily list index
    has_files: int = 0  # uint16 record revision: only 1 stores the two strings
    uk_file_length: int = 0
    uk_file: str = ""  # GetFxOfState; independent from transition FX
    drs_file_length: int = 0  # Int
    drs_file: str = ""  # String

    state_id = property(lambda self: self.state_num, lambda self, value: setattr(self, "state_num", value))
    version = property(lambda self: self.has_files, lambda self, value: setattr(self, "has_files", value))
    fx_file = property(lambda self: self.uk_file, lambda self, value: setattr(self, "uk_file", value))
    resource_file = property(lambda self: self.drs_file, lambda self, value: setattr(self, "drs_file", value))

    def read(self, file: BinaryIO) -> "SMeshState":
        """Reads the SMeshState from the buffer"""
        self.state_num = unpack("I", file.read(4))[0]
        self.has_files = unpack("H", file.read(2))[0]
        self.uk_file = self.drs_file = ""
        self.uk_file_length = self.drs_file_length = 0
        self.__dict__.pop("_original_uk_file", None)
        self.__dict__.pop("_original_drs_file", None)
        if self.has_files == 1:
            self.uk_file_length = unpack("i", file.read(4))[0]
            self.uk_file = _read_text(self, file, "uk_file", self.uk_file_length)
            self.drs_file_length = unpack("i", file.read(4))[0]
            self.drs_file = _read_text(self, file, "drs_file", self.drs_file_length)
        return self

    def write(self, file: BinaryIO):
        file.write(pack("<IH", self.state_num, self.has_files))
        if self.has_files == 1:
            fx = _text_bytes(self, "uk_file")
            resource = _text_bytes(self, "drs_file")
            self.uk_file_length, self.drs_file_length = len(fx), len(resource)
            file.write(pack("i", self.uk_file_length))
            file.write(fx)
            file.write(pack("i", self.drs_file_length))
            file.write(resource)

    def size(self) -> int:
        size = 6
        if self.has_files == 1:
            size += 8 + len(_text_bytes(self, "uk_file")) + len(_text_bytes(self, "drs_file"))
        return size


@dataclass(eq=False, repr=False)
class StateTransition:
    """Effect triggered on entry to a destination state; no source-state field."""
    state_num: int = 0  # uint32 destination-state map key
    file_name_length: int = 0  # Int
    file_name: str = ""  # String

    target_state = property(lambda self: self.state_num, lambda self, value: setattr(self, "state_num", value))
    fx_file = property(lambda self: self.file_name, lambda self, value: setattr(self, "file_name", value))

    def read(self, file: BinaryIO) -> "StateTransition":
        """Reads the DestructionState from the buffer"""
        self.state_num = unpack("I", file.read(4))[0]
        self.file_name_length = unpack("i", file.read(4))[0]
        self.file_name = _read_text(self, file, "file_name", self.file_name_length)
        return self

    def write(self, file: BinaryIO):
        raw = _text_bytes(self, "file_name")
        self.file_name_length = len(raw)
        file.write(pack("I", self.state_num))
        file.write(pack("i", self.file_name_length))
        file.write(raw)

    def size(self) -> int:
        return 8 + len(_text_bytes(self, "file_name"))


DestructionState = StateTransition  # Compatibility with existing imports/artist metadata.


@dataclass(eq=False, repr=False)
class StateBasedMeshSet:
    """Set of mesh states and destruction states"""
    version: int = 1  # uint16 stream revision
    revision: int = 10  # uint32 EDrwMeshSetType, not a revision
    num_mesh_states: int = 1  # uint32; writer derives the count, including zero
    mesh_states: List[SMeshState] = field(default_factory=list)
    num_destruction_states: int = 1  # Int
    destruction_states: List[DestructionState] = field(default_factory=list)

    stream_revision = property(lambda self: self.version, lambda self, value: setattr(self, "version", value))
    mesh_set_type = property(lambda self: self.revision, lambda self, value: setattr(self, "revision", value))
    transitions = property(lambda self: self.destruction_states,
        lambda self, value: setattr(self, "destruction_states", list(value)))

    def read(self, file: BinaryIO) -> "StateBasedMeshSet":
        """Reads the StateBasedMeshSet from the buffer"""
        self.version = unpack("H", file.read(2))[0]
        if self.version != 1:
            raise ValueError(f"Unsupported StateBasedMeshSet stream revision: {self.version}")
        self.revision = unpack("I", file.read(4))[0]
        self.num_mesh_states = unpack("I", file.read(4))[0]
        self.mesh_states = [
            SMeshState().read(file) for _ in range(self.num_mesh_states)
        ]
        self.num_destruction_states = unpack("I", file.read(4))[0]
        self.destruction_states = [
            DestructionState().read(file) for _ in range(self.num_destruction_states)
        ]
        return self

    def write(self, file: BinaryIO):
        if self.version != 1:
            raise ValueError(f"Unsupported StateBasedMeshSet stream revision: {self.version}")
        self.num_mesh_states = len(self.mesh_states)
        self.num_destruction_states = len(self.destruction_states)
        file.write(pack("<HII", self.version, self.revision, self.num_mesh_states))
        for mesh_state in self.mesh_states:
            mesh_state.write(file)
        file.write(pack("I", self.num_destruction_states))
        for destruction_state in self.destruction_states:
            destruction_state.write(file)

    def size(self) -> int:
        if self.version != 1:
            raise ValueError(f"Unsupported StateBasedMeshSet stream revision: {self.version}")
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
    rotation: int = 0  # uint16 degrees; global grid rotation is signed instead
    has_mesh_set: int = 0  # Byte
    state_based_mesh_set: StateBasedMeshSet = None

    def read(self, file: BinaryIO) -> "MeshGridModule":
        """Reads the MeshGridModule from the buffer"""
        self.rotation = unpack("H", file.read(2))[0]
        self.has_mesh_set = unpack("B", file.read(1))[0]
        self.state_based_mesh_set = None
        if self.has_mesh_set:
            self.state_based_mesh_set = StateBasedMeshSet().read(file)
        return self

    def write(self, file: BinaryIO):
        if self.has_mesh_set and self.state_based_mesh_set is None:
            raise ValueError("Populated grid cell has no StateBasedMeshSet")
        file.write(pack("H", self.rotation))
        file.write(pack("B", self.has_mesh_set))
        if self.has_mesh_set:
            self.state_based_mesh_set.write(file)

    def size(self) -> int:
        if self.has_mesh_set and self.state_based_mesh_set is None:
            raise ValueError("Populated grid cell has no StateBasedMeshSet")
        size = 3
        if self.has_mesh_set:
            size += self.state_based_mesh_set.size()
        return size


@dataclass(eq=False, repr=False)
class MeshSetGrid:
    """Grid-based mesh set for building layouts"""
    revision: int = 5  # uint16 stream revision; only 5 loads this body
    grid_width: int = 1  # uint8 half-extent; expanded side is 2 * value + 1
    grid_height: int = 1  # uint8 half-extent
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
    uk_string1: str = ""  # GetDestructionEffectFn; separate from DebrisEffect
    module_distance: float = 2  # Float
    is_center_pivoted: int = 1  # Nonzero: shared-origin geometry, cell offset used for effects
    mesh_modules: List[MeshGridModule] = field(default_factory=list)
    cdrw_locator_list: CDrwLocatorList = field(default_factory=CDrwLocatorList)

    destruction_effect = property(lambda self: self.uk_string1,
        lambda self, value: setattr(self, "uk_string1", value))
    debris_effect = property(lambda self: self.effect_gen_debris,
        lambda self, value: setattr(self, "effect_gen_debris", value))

    @property
    def expanded_width(self) -> int:
        return (2 * self.grid_width + 1) & 0xff

    @property
    def expanded_height(self) -> int:
        return (2 * self.grid_height + 1) & 0xff

    def _validate_export(self) -> None:
        if self.revision != 5:
            raise ValueError(f"Unsupported MeshSetGrid revision: {self.revision}")
        if not (0 <= self.grid_width <= 127 and 0 <= self.grid_height <= 127):
            raise ValueError("MeshSetGrid half-extents must be 0..127 to avoid engine byte wrapping")
        if self.grid_width != self.grid_height:
            raise ValueError("Rectangular MeshSetGrid export is unsafe with the engine's width-stride indexing")
        expected = self.expanded_width * self.expanded_height
        if len(self.mesh_modules) != expected:
            raise ValueError(f"MeshSetGrid needs {expected} cells, got {len(self.mesh_modules)}")
        if self.cdrw_locator_list is None:
            raise ValueError("MeshSetGrid needs its trailing locator list, including an empty one")

    def cell_placement(self, index: int) -> dict:
        """Engine-local placement before the parent grid's signed yaw rotation."""
        self._validate_export()
        if not 0 <= index < len(self.mesh_modules):
            raise IndexError(index)
        outer, inner = divmod(index, self.expanded_width)
        offset = ((outer - self.grid_width) * self.module_distance, 0.0,
                  (inner - self.grid_width) * self.module_distance)
        if self.is_center_pivoted:
            return {"translation": (0.0, 0.0, 0.0), "rotation_degrees": 0,
                    "effect_offset": offset}
        return {"translation": offset, "rotation_degrees": self.mesh_modules[index].rotation,
                "effect_offset": (0.0, 0.0, 0.0)}

    def read(self, file: BinaryIO) -> "MeshSetGrid":
        """Reads the MeshSetGrid from the buffer"""
        self.revision = unpack("H", file.read(2))[0]
        if self.revision != 5:
            raise ValueError(f"Unsupported MeshSetGrid revision: {self.revision}")
        self.grid_width = unpack("B", file.read(1))[0]
        self.grid_height = unpack("B", file.read(1))[0]
        self.name_length = unpack("i", file.read(4))[0]
        self.name = _read_text(self, file, "name", self.name_length)
        self.uuid_length = unpack("i", file.read(4))[0]
        self.uuid = _read_text(self, file, "uuid", self.uuid_length)
        self.grid_rotation = unpack("h", file.read(2))[0]
        self.ground_decal_length = unpack("i", file.read(4))[0]
        self.ground_decal = _read_text(self, file, "ground_decal", self.ground_decal_length)
        self.effect_gen_debris_length = unpack("i", file.read(4))[0]
        self.effect_gen_debris = _read_text(self, file, "effect_gen_debris", self.effect_gen_debris_length)
        self.uk_string1_length = unpack("i", file.read(4))[0]
        self.uk_string1 = _read_text(self, file, "uk_string1", self.uk_string1_length)
        self.module_distance = unpack("f", file.read(4))[0]
        self.is_center_pivoted = unpack("B", file.read(1))[0]
        self.mesh_modules = [
            MeshGridModule().read(file)
            for _ in range(self.expanded_width * self.expanded_height)
        ]
        self.cdrw_locator_list = CDrwLocatorList().read(file)
        return self

    def write(self, file: BinaryIO):
        self._validate_export()
        for name in ("name", "uuid", "ground_decal", "effect_gen_debris", "uk_string1"):
            setattr(self, name + "_length", len(_text_bytes(self, name)))
        file.write(pack("H", self.revision))
        file.write(pack("B", self.grid_width))
        file.write(pack("B", self.grid_height))
        file.write(pack("i", self.name_length))
        file.write(_text_bytes(self, "name"))
        file.write(pack("i", self.uuid_length))
        file.write(_text_bytes(self, "uuid"))
        file.write(pack("h", self.grid_rotation))
        file.write(pack("i", self.ground_decal_length))
        file.write(_text_bytes(self, "ground_decal"))
        file.write(pack("i", self.effect_gen_debris_length))
        file.write(_text_bytes(self, "effect_gen_debris"))
        file.write(pack("i", self.uk_string1_length))
        file.write(_text_bytes(self, "uk_string1"))
        file.write(pack("f", self.module_distance))
        file.write(pack("B", self.is_center_pivoted))
        for module in self.mesh_modules:
            module.write(file)
        self.cdrw_locator_list.write(file)

    def size(self) -> int:
        self._validate_export()
        size = 31 + sum(len(_text_bytes(self, name)) for name in
            ("name", "uuid", "ground_decal", "effect_gen_debris", "uk_string1"))
        for module in self.mesh_modules:
            size += module.size()
        size += self.cdrw_locator_list.size()
        return size
