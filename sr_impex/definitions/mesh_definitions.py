"""
Mesh-related class definitions for DRS files.

This module contains classes related to mesh data structures:
- Vertex: Vertex data with position, normal, texture coordinates, etc.
- VertexData: Vertex weight and bone index data
- MeshData: Mesh data with revision and vertices
- CGeoMesh: Geometric mesh with faces and vertices
- CDspMeshFile: Complete mesh file with bounding boxes
- BattleforgeMesh: Complete mesh with materials and textures
- Material support classes: Texture, Textures, Material, Materials, Refraction, LevelOfDetail, EmptyString, Flow
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List, Optional

from sr_impex.definitions.base_types import (
    Vector3,
    Vector4,
    Face,
)


def unpack_data(file: BinaryIO, *formats: str):
    """Unpack a sequence of format strings from the binary file."""
    return [list(unpack(fmt, file.read(calcsize(fmt)))) for fmt in formats]


def bounds_from_positions(positions):
    """Compute local bounds of positions, or a zero box for an empty mesh."""
    iterator = iter(positions)
    first = next(iterator, None)
    if first is None:
        return Vector3(0, 0, 0), Vector3(0, 0, 0)
    lo = [first.x, first.y, first.z]
    hi = lo.copy()
    for point in iterator:
        for index, value in enumerate((point.x, point.y, point.z)):
            lo[index] = min(lo[index], value)
            hi[index] = max(hi[index], value)
    return Vector3(*lo), Vector3(*hi)


def combined_mesh_bounds(meshes):
    """Compute the union of exported mesh bounds without forcing in the origin."""
    if not meshes:
        return Vector3(0, 0, 0), Vector3(0, 0, 0)
    lower = Vector3(*(min(getattr(mesh.bounding_box_lower_left_corner, axis) for mesh in meshes)
                      for axis in ('x', 'y', 'z')))
    upper = Vector3(*(max(getattr(mesh.bounding_box_upper_right_corner, axis) for mesh in meshes)
                      for axis in ('x', 'y', 'z')))
    return lower, upper


@dataclass(eq=False, repr=False)
class Vertex:
    position: Optional[List[float]] = field(default_factory=list)
    normal: Optional[List[float]] = field(default_factory=list)
    texture: Optional[List[float]] = field(default_factory=list)
    tangent: Optional[List[float]] = field(default_factory=list)
    bitangent: Optional[List[float]] = field(default_factory=list)
    raw_weights: Optional[List[int]] = field(default_factory=list)
    bone_indices: Optional[List[int]] = field(default_factory=list)
    diffuse: List[int] = field(default_factory=lambda: [0, 0, 0, 0])

    def read(self, file: BinaryIO, revision: int) -> "Vertex":
        if revision == 133121:
            data = unpack_data(file, "fff", "fff", "ff")
            self.position, self.normal, self.texture = data[0], data[1], data[2]
        elif revision == 12288:
            data = unpack_data(file, "fff", "fff")
            self.tangent, self.bitangent = data[0], data[1]
        elif revision == 2049:
            data = unpack_data(file, "fff", "fff")
            self.position, self.normal = data[0], data[1]
        elif revision == 12:
            data = unpack_data(file, "4B", "4B")
            self.raw_weights, self.bone_indices = data[0], data[1]
        elif revision == 163841:
            data = unpack_data(file, "fff", "4B", "ff")
            self.position, self.diffuse, self.texture = data[0], data[1], data[2]
            self.normal = [0.0, 0.0, 0.0]
        elif revision == 131073:
            data = unpack_data(file, "fff", "ff")
            self.position, self.texture = data[0], data[1]
            self.normal = [0.0, 0.0, 0.0]
        else:
            raise ValueError(f"Unsupported DRS vertex format: {revision}")
        return self

    def write(self, file: BinaryIO, revision: int) -> None:
        if revision == 133121:
            file.write(pack("fff", *self.position))
            file.write(pack("fff", *self.normal))
            file.write(pack("ff", *self.texture))
        elif revision == 12288:
            file.write(pack("fff", *self.tangent))
            file.write(pack("fff", *self.bitangent))
        elif revision == 2049:
            file.write(pack("fff", *self.position))
            file.write(pack("fff", *self.normal))
        elif revision == 12:
            file.write(pack("4B", *self.raw_weights))
            file.write(pack("4B", *self.bone_indices))
        elif revision == 163841:
            file.write(pack("fff", *self.position))
            file.write(pack("4B", *self.diffuse))
            file.write(pack("ff", *self.texture))
        elif revision == 131073:
            file.write(pack("fff", *self.position))
            file.write(pack("ff", *self.texture))
        else:
            raise ValueError(f"Unsupported DRS vertex format: {revision}")

    def size(self) -> int:
        if self.position:
            return 12
        if self.normal:
            return 12
        if self.texture:
            return 8
        if self.tangent:
            return 12
        if self.bitangent:
            return 12
        if self.raw_weights:
            return 4
        if self.bone_indices:
            return 4
        return 0

    def __repr__(self) -> str:
        return (
            f"Vertex(position={self.position}, normal={self.normal}, "
            f"texture={self.texture}, tangent={self.tangent}, "
            f"bitangent={self.bitangent}, raw_weights={self.raw_weights}, "
            f"bone_indices={self.bone_indices})"
        )


@dataclass(eq=False, repr=False)
class VertexData:
    weights: List[float] = field(default_factory=lambda: [0.0] * 4)
    bone_indices: List[int] = field(default_factory=lambda: [0] * 4)

    def read(self, file: BinaryIO) -> "VertexData":
        data = unpack("4f4i", file.read(32))
        self.weights, self.bone_indices = list(data[:4]), list(data[4:])
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("4f4i", *self.weights, *self.bone_indices))

    def size(self) -> int:
        return 32


@dataclass(eq=False, repr=False)
class CGeoMesh:
    magic: int = 1
    index_count: int = 0
    faces: List[Face] = field(default_factory=list)
    vertex_count: int = 0
    vertices: List[Vector4] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CGeoMesh":
        self.magic, self.index_count = unpack("ii", file.read(8))
        if self.index_count < 0 or self.index_count % 3:
            raise ValueError(f"CGeoMesh index count must be a non-negative multiple of 3, got {self.index_count}")
        self.faces = [Face().read(file) for _ in range(self.index_count // 3)]
        self.vertex_count = unpack("i", file.read(4))[0]
        for _ in range(self.vertex_count):
            x, y, z, w = unpack("4f", file.read(16))
            self.vertices.append(Vector4(x, y, z, w))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("ii", self.magic, self.index_count))
        for face in self.faces:
            face.write(file)
        file.write(pack("i", self.vertex_count))
        for vertex in self.vertices:
            vertex.write(file)

    def size(self) -> int:
        return 12 + 6 * len(self.faces) + 16 * len(self.vertices)


@dataclass(eq=False, repr=False)
class MeshData:
    revision: int = 0
    vertex_size: int = 0
    vertices: List[Vertex] = field(default_factory=list)

    def read(self, file: BinaryIO, vertex_count: int) -> "MeshData":
        self.revision, self.vertex_size = unpack("ii", file.read(8))
        expected_sizes = {133121: 32, 12288: 24, 2049: 24, 12: 8, 163841: 24, 131073: 20}
        expected = expected_sizes.get(self.revision)
        if expected is None:
            raise ValueError(f"Unsupported DRS vertex format: {self.revision}")
        if self.vertex_size != expected:
            raise ValueError(f"DRS vertex format {self.revision} expects stride {expected}, got {self.vertex_size}")
        self.vertices = [
            Vertex().read(file, self.revision) for _ in range(vertex_count)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        i = -1
        try:
            file.write(pack("ii", self.revision, self.vertex_size))
            for idx, vertex in enumerate(self.vertices):
                i = idx
                vertex.write(file, self.revision)
        except Exception as e:
            raise RuntimeError(
                f"Vertex write failed at index {i}, revision={self.revision}: {e}"
            ) from e


    def size(self) -> int:
        s = 8 + self.vertex_size * len(self.vertices)
        return s


@dataclass(eq=False, repr=False)
class Texture:
    identifier: int = 0
    length: int = field(default=0, init=False)
    name: str = ""
    spacer: int = 0
    _raw_name: bytes = field(default=b"", init=False, repr=False)
    _original_name: Optional[str] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.length = len(self.name.encode("utf-8"))

    @property
    def texture_bias(self) -> float:
        """Interpret the stored four-byte spacer as the engine's texture bias."""
        return unpack("=f", pack("=i", self.spacer))[0]

    @texture_bias.setter
    def texture_bias(self, value: float) -> None:
        self.spacer = unpack("=i", pack("=f", value))[0]

    def read(self, file: BinaryIO) -> "Texture":
        self.identifier, self.length = unpack("ii", file.read(8))
        self._raw_name = file.read(self.length)
        if len(self._raw_name) != self.length:
            raise EOFError("Truncated DRS texture name")
        self.name = self._raw_name.decode("utf-8").strip("\x00")
        self._original_name = self.name
        self.spacer = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        raw_name = self._name_bytes()
        self.length = len(raw_name)
        file.write(pack("ii", self.identifier, self.length))
        file.write(raw_name)
        file.write(pack("i", self.spacer))

    def size(self) -> int:
        return 12 + len(self._name_bytes())

    def _name_bytes(self) -> bytes:
        if self._original_name is not None and self.name == self._original_name:
            return self._raw_name
        return self.name.encode("utf-8")


@dataclass(eq=False, repr=False)
class Textures:
    length: int = 0
    textures: List["Texture"] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "Textures":
        self.length = unpack("i", file.read(4))[0]
        self.textures = [Texture().read(file) for _ in range(self.length)]
        return self

    def write(self, file: BinaryIO) -> None:
        self.length = len(self.textures)
        file.write(pack("i", self.length))
        for texture in self.textures:
            texture.write(file)

    def size(self) -> int:
        return 4 + sum(texture.size() for texture in self.textures)


@dataclass(eq=False, repr=False)
class Material:
    identifier: int = 0
    smoothness: float = 0.0
    metalness: float = 0.0
    reflectivity: float = 0.0
    emissivity: float = 0.0
    refraction_scale: float = 0.0  # Default material registers range 0.0–10.0.
    distortion_mesh_scale: float = 0.0
    scratch: float = 0.0
    specular_scale: float = 0.0
    wind_response: float = 0.0
    wind_height: float = 0.0
    depth_write_threshold: float = 0.0
    saturation: float = 0.0
    unknown: float = 0.0
    unknown_bytes: bytes = b""

    def __init__(self, index: int = None) -> None:
        """Material Constructor"""
        if index is not None:
            if index == 0:
                self.identifier = 1668510769
                self.smoothness = 0
            elif index == 1:
                self.identifier = 1668510770
                self.metalness = 0
            elif index == 2:
                self.identifier = 1668510771
                self.reflectivity = 0
            elif index == 3:
                self.identifier = 1668510772
                self.emissivity = 0
            elif index == 4:
                self.identifier = 1668510773
                self.refraction_scale = 1
            elif index == 5:
                self.identifier = 1668510774
                self.distortion_mesh_scale = 0
            elif index == 6:
                self.identifier = 1935897704
                self.scratch = 0
            elif index == 7:
                self.identifier = 1668510775
                self.specular_scale = 1.5
            elif index == 8:
                self.identifier = 1668510776
                self.wind_response = 0  # Needs to be updated
            elif index == 9:
                self.identifier = 1668510777
                self.wind_height = 0  # Needs to be updated
            elif index == 10:
                self.identifier = 1935893623
                self.depth_write_threshold = 0.5
            elif index == 11:
                self.identifier = 1668510785
                self.saturation = 1.0

    def read(self, file: BinaryIO) -> "Material":
        """Reads the Material from the buffer"""
        self.identifier = unpack("i", file.read(4))[0]
        if self.identifier == 1668510769:
            self.smoothness = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510770:
            self.metalness = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510771:
            self.reflectivity = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510772:
            self.emissivity = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510773:
            self.refraction_scale = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510774:
            self.distortion_mesh_scale = unpack("f", file.read(4))[0]
        elif self.identifier == 1935897704:
            self.scratch = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510775:
            self.specular_scale = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510776:
            self.wind_response = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510777:
            self.wind_height = unpack("f", file.read(4))[0]
        elif self.identifier == 1935893623:
            self.depth_write_threshold = unpack("f", file.read(4))[0]
        elif self.identifier == 1668510785:
            self.saturation = unpack("f", file.read(4))[0]
        else:
            self.unknown_bytes = file.read(4)
            self.unknown = unpack("f", self.unknown_bytes)[0]
        return self

    def write(self, file: BinaryIO) -> None:
        """Writes the Material to the buffer"""
        file.write(pack("i", self.identifier))
        if self.identifier == 1668510769:
            file.write(pack("f", self.smoothness))
        elif self.identifier == 1668510770:
            file.write(pack("f", self.metalness))
        elif self.identifier == 1668510771:
            file.write(pack("f", self.reflectivity))
        elif self.identifier == 1668510772:
            file.write(pack("f", self.emissivity))
        elif self.identifier == 1668510773:
            file.write(pack("f", self.refraction_scale))
        elif self.identifier == 1668510774:
            file.write(pack("f", self.distortion_mesh_scale))
        elif self.identifier == 1935897704:
            file.write(pack("f", self.scratch))
        elif self.identifier == 1668510775:
            file.write(pack("f", self.specular_scale))
        elif self.identifier == 1668510776:
            file.write(pack("f", self.wind_response))
        elif self.identifier == 1668510777:
            file.write(pack("f", self.wind_height))
        elif self.identifier == 1935893623:
            file.write(pack("f", self.depth_write_threshold))
        elif self.identifier == 1668510785:
            file.write(pack("f", self.saturation))
        else:
            file.write(self.unknown_bytes if self.unknown_bytes else pack("f", self.unknown))

    def size(self) -> int:
        return 4 + 4


@dataclass(eq=False, repr=False)
class Materials:
    length: int = 12
    materials: List["Material"] = field(
        default_factory=lambda: [Material(index) for index in range(12)]
    )

    def read(self, file: BinaryIO) -> "Materials":
        self.length = unpack("i", file.read(4))[0]
        self.materials = [Material().read(file) for _ in range(self.length)]
        return self

    def write(self, file: BinaryIO) -> None:
        self.length = len(self.materials)
        file.write(pack("i", self.length))
        for material in self.materials:
            material.write(file)

    def size(self) -> int:
        return 4 + sum(material.size() for material in self.materials)


@dataclass(eq=False, repr=False)
class Refraction:
    length: int = 0
    identifier: int = 1668510769
    rgb: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    entries: list[tuple[int, List[float]]] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "Refraction":
        self.length = unpack("i", file.read(4))[0]
        if self.length < 0:
            raise ValueError(f"Invalid refraction entry count: {self.length}")
        self.entries = []
        for _ in range(self.length):
            identifier = unpack("i", file.read(4))[0]
            rgb = list(unpack("3f", file.read(12)))
            self.entries.append((identifier, rgb))
        if self.entries:
            self.identifier, self.rgb = self.entries[-1][0], list(self.entries[-1][1])
        return self

    def write(self, file: BinaryIO) -> None:
        if self.length < 0:
            raise ValueError(f"Invalid refraction entry count: {self.length}")
        if self.length > 1 and len(self.entries) != self.length:
            raise ValueError("Refraction entry count does not match preserved entries")
        file.write(pack("i", self.length))
        for index in range(self.length):
            identifier, rgb = (self.identifier, self.rgb) if index == self.length - 1 else self.entries[index]
            file.write(pack("i", identifier))
            file.write(pack("3f", *rgb))

    def size(self) -> int:
        return 4 + 16 * self.length


@dataclass(eq=False, repr=False)
class LevelOfDetail:
    length: int = 1
    lod_level: int = 2
    levels: List[int] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "LevelOfDetail":
        self.length = unpack("i", file.read(4))[0]
        if self.length < 0:
            raise ValueError(f"Invalid level-of-detail entry count: {self.length}")
        self.levels = [unpack("i", file.read(4))[0] for _ in range(self.length)]
        if self.levels:
            self.lod_level = self.levels[-1]
        return self

    def write(self, file: BinaryIO) -> None:
        if self.length < 0:
            raise ValueError(f"Invalid level-of-detail entry count: {self.length}")
        if self.length > 1 and len(self.levels) != self.length:
            raise ValueError("Level-of-detail entry count does not match preserved entries")
        file.write(pack("i", self.length))
        for index in range(self.length):
            value = self.lod_level if index == self.length - 1 else self.levels[index]
            file.write(pack("i", value))

    def size(self) -> int:
        return 4 + 4 * self.length


@dataclass(eq=False, repr=False)
class EmptyString:
    """Legacy name for the count-prefixed material string parameter list."""
    length: int = 0
    entries: List[bytes] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "EmptyString":
        self.length = unpack("i", file.read(4))[0]
        if self.length < 0:
            raise ValueError(f"Invalid material string count: {self.length}")
        self.entries = []
        for _ in range(self.length):
            byte_length = unpack("i", file.read(4))[0]
            if byte_length < 0:
                raise ValueError(f"Invalid material string length: {byte_length}")
            value = file.read(byte_length)
            if len(value) != byte_length:
                raise EOFError("Truncated material string parameter")
            self.entries.append(value)
        return self

    def write(self, file: BinaryIO) -> None:
        self.length = len(self.entries)
        file.write(pack("i", self.length))
        for entry in self.entries:
            file.write(pack("i", len(entry)))
            file.write(entry)

    def size(self) -> int:
        return 4 + sum(4 + len(entry) for entry in self.entries)


@dataclass(eq=False, repr=False)
class Flow:
    length: int = 4
    max_flow_speed_identifier: int = 1668707377
    max_flow_speed: Vector4 = field(default_factory=Vector4)
    min_flow_speed_identifier: int = 1668707378
    min_flow_speed: Vector4 = field(default_factory=Vector4)
    flow_speed_change_identifier: int = 1668707379
    flow_speed_change: Vector4 = field(default_factory=Vector4)
    flow_scale_identifier: int = 1668707380
    flow_scale: Vector4 = field(default_factory=Vector4)
    entries: list[tuple[int, Vector4]] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "Flow":
        self.length = unpack("i", file.read(4))[0]
        if self.length < 0:
            raise ValueError(f"Invalid flow entry count: {self.length}")
        self.entries = []
        names = {1668707377: 'max_flow_speed', 1668707378: 'min_flow_speed',
                 1668707379: 'flow_speed_change', 1668707380: 'flow_scale'}
        for _ in range(self.length):
            identifier = unpack("i", file.read(4))[0]
            value = Vector4().read(file)
            self.entries.append((identifier, value))
            if identifier in names:
                setattr(self, names[identifier] + '_identifier', identifier)
                setattr(self, names[identifier], value)
        return self

    def write(self, file: BinaryIO) -> None:
        if self.length < 0:
            raise ValueError(f"Invalid flow entry count: {self.length}")
        if self.entries:
            if len(self.entries) != self.length:
                raise ValueError("Flow entry count does not match preserved entries")
            names = {1668707377: 'max_flow_speed', 1668707378: 'min_flow_speed',
                     1668707379: 'flow_speed_change', 1668707380: 'flow_scale'}
            ids = [identifier for identifier, _ in self.entries]
            entries = [(identifier, getattr(self, names[identifier])
                        if identifier in names and ids.count(identifier) == 1 else value)
                       for identifier, value in self.entries]
        elif self.length == 4:
            entries = [(self.max_flow_speed_identifier, self.max_flow_speed),
                       (self.min_flow_speed_identifier, self.min_flow_speed),
                       (self.flow_speed_change_identifier, self.flow_speed_change),
                       (self.flow_scale_identifier, self.flow_scale)]
        elif self.length == 0:
            entries = []
        else:
            raise ValueError("Flow entries are required for this count")
        file.write(pack("i", self.length))
        for identifier, value in entries:
            file.write(pack("i", identifier))
            value.write(file)

    def size(self) -> int:
        return 4 + 20 * self.length


@dataclass(eq=False, repr=False)
class BattleforgeMesh:
    vertex_count: int = 0
    face_count: int = 0
    faces: List[Face] = field(default_factory=list)
    mesh_count: int = 0
    mesh_data: List[MeshData] = field(default_factory=list)
    bounding_box_lower_left_corner: Vector3 = field(default_factory=Vector3)
    bounding_box_upper_right_corner: Vector3 = field(default_factory=Vector3)
    material_id: int = 0
    material_parameters: int = 0
    material_stuff: int = 0
    bool_parameter: int = 0
    textures: Textures = field(default_factory=Textures)
    refraction: Refraction = field(default_factory=Refraction)
    materials: Materials = field(default_factory=Materials)
    level_of_detail: LevelOfDetail = field(default_factory=LevelOfDetail)
    empty_string: EmptyString = field(default_factory=EmptyString)
    flow: Flow = field(default_factory=Flow)

    def read(self, file: BinaryIO) -> "BattleforgeMesh":
        self.vertex_count, self.face_count = unpack("ii", file.read(8))
        if self.vertex_count < 0 or self.face_count < 0:
            raise ValueError("Mesh vertex and face counts must be non-negative")
        self.faces = [Face().read(file) for _ in range(self.face_count)]
        self.mesh_count = unpack("B", file.read(1))[0]
        self.mesh_data = [
            MeshData().read(file, self.vertex_count) for _ in range(self.mesh_count)
        ]
        self.bounding_box_lower_left_corner = Vector3().read(file)
        self.bounding_box_upper_right_corner = Vector3().read(file)
        self.material_id, self.material_parameters = unpack("=hi", file.read(6))

        if self.material_parameters == -86061050:
            self.material_stuff, self.bool_parameter = unpack("ii", file.read(8))
            self.textures.read(file)
            self.refraction.read(file)
            self.materials.read(file)
            self.level_of_detail.read(file)
            self.empty_string.read(file)
            self.flow.read(file)
        elif (
            self.material_parameters == -86061051
            or self.material_parameters == -86061052
        ):
            self.material_stuff, self.bool_parameter = unpack("ii", file.read(8))
            self.textures.read(file)
            self.refraction.read(file)
            self.materials.read(file)
            self.level_of_detail.read(file)
            self.empty_string.read(file)
        elif self.material_parameters == -86061053:
            self.bool_parameter = unpack("i", file.read(4))[0]
            self.textures.read(file)
            self.refraction.read(file)
            self.materials.read(file)
            self.level_of_detail.read(file)
            self.empty_string.read(file)
        elif self.material_parameters == -86061054:
            self.bool_parameter = unpack("i", file.read(4))[0]
            self.textures.read(file)
            self.refraction.read(file)
            self.materials.read(file)
            self.level_of_detail.read(file)
        elif self.material_parameters == -86061055:
            self.bool_parameter = unpack("i", file.read(4))[0]
            self.textures.read(file)
            self.refraction.read(file)
            self.materials.read(file)
        else:
            raise TypeError(f"Unknown MaterialParameters {self.material_parameters}")
        return self

    def write(self, file: BinaryIO) -> None:
        if self.vertex_count < 0 or self.face_count < 0:
            raise ValueError("Mesh vertex and face counts must be non-negative")
        if self.face_count != len(self.faces):
            raise ValueError("Mesh face count does not match faces")
        if self.mesh_count != len(self.mesh_data):
            raise ValueError("Mesh stream count does not match vertex streams")
        if any(len(stream.vertices) != self.vertex_count for stream in self.mesh_data):
            raise ValueError("Mesh vertex stream count does not match vertex count")
        if any(len(face.indices) != 3 for face in self.faces):
            raise ValueError("Mesh faces must contain exactly three indices")
        try:
            file.write(pack("ii", self.vertex_count, self.face_count))
        except Exception as e:
            raise TypeError(
                f"Error writing BattleforgeMesh vertex_count {self.vertex_count} or face_count {self.face_count}: {e}"
            ) from e

        for face in self.faces:
            face.write(file)

        try:
            file.write(pack("B", self.mesh_count))
        except Exception as e:
            raise TypeError(f"Error writing BattleforgeMesh mesh_count {self.mesh_count}: {e}") from e

        try:
            for mesh_data in self.mesh_data:
                mesh_data.write(file)
        except Exception as e:
            raise TypeError(f"Error writing BattleforgeMesh mesh data: {e}") from e

        try:
            self.bounding_box_lower_left_corner.write(file)
            self.bounding_box_upper_right_corner.write(file)
        except Exception as e:
            raise TypeError(f"Error writing BattleforgeMesh bounding boxes: {e}") from e

        try:
            file.write(pack("=hi", self.material_id, self.material_parameters))
        except Exception as e:
            raise TypeError(
                f"Error writing BattleforgeMesh material_id {self.material_id} or material_parameters {self.material_parameters}"
            ) from e

        try:
            if self.material_parameters == -86061050:
                file.write(pack("ii", self.material_stuff, self.bool_parameter))
                self.textures.write(file)
                self.refraction.write(file)
                self.materials.write(file)
                self.level_of_detail.write(file)
                self.empty_string.write(file)
                self.flow.write(file)
            elif self.material_parameters in (-86061051, -86061052):
                file.write(pack("ii", self.material_stuff, self.bool_parameter))
                self.textures.write(file)
                self.refraction.write(file)
                self.materials.write(file)
                self.level_of_detail.write(file)
                self.empty_string.write(file)
            elif self.material_parameters in (-86061053, -86061054):
                file.write(pack("i", self.bool_parameter))
                self.textures.write(file)
                self.refraction.write(file)
                self.materials.write(file)
                self.level_of_detail.write(file)
                if self.material_parameters == -86061053:
                    self.empty_string.write(file)
            elif self.material_parameters == -86061055:
                file.write(pack("i", self.bool_parameter))
                self.textures.write(file)
                self.refraction.write(file)
                self.materials.write(file)
            else:
                raise TypeError(f"Unknown MaterialParameters {self.material_parameters}")
        except Exception as e:
            raise TypeError(f"Error writing BattleforgeMesh material data: {e}") from e

    def size(self) -> int:
        size = 8  # VertexCount + FaceCount
        size += 1  # MeshCount
        size += 24  # BoundingBox1 + BoundingBox2
        size += 2  # MaterialID
        size += 4  # MaterialParameters
        size += sum(face.size() for face in self.faces)
        size += sum(mesh_data.size() for mesh_data in self.mesh_data)

        if self.material_parameters == -86061050:
            size += 8  # MaterialStuff + BoolParameter
            size += self.textures.size()
            size += self.refraction.size()
            size += self.materials.size()
            size += self.level_of_detail.size()
            size += self.empty_string.size()
            size += self.flow.size()
        elif self.material_parameters in (-86061051, -86061052):
            size += 8  # MaterialStuff + BoolParameter
            size += self.textures.size()
            size += self.refraction.size()
            size += self.materials.size()
            size += self.level_of_detail.size()
            size += self.empty_string.size()
        elif self.material_parameters in (-86061053, -86061054):
            size += 4 + self.textures.size() + self.refraction.size() + self.materials.size()
            size += self.level_of_detail.size()
            if self.material_parameters == -86061053:
                size += self.empty_string.size()
        elif self.material_parameters == -86061055:
            size += 4  # BoolParameter
            size += self.textures.size()
            size += self.refraction.size()
            size += self.materials.size()

        return size


@dataclass(eq=False, repr=False)
class CDspMeshFile:
    magic: int = 1314189598
    zero: int = 0
    legacy_header: bool = False
    mesh_count: int = 0
    bounding_box_lower_left_corner: Vector3 = field(
        default_factory=lambda: Vector3(0, 0, 0)
    )
    bounding_box_upper_right_corner: Vector3 = field(
        default_factory=lambda: Vector3(0, 0, 0)
    )
    meshes: List[BattleforgeMesh] = field(default_factory=list)
    some_points: List[Vector4] = field(
        default_factory=lambda: [
            Vector4(0, 0, 0, 1),
            Vector4(1, 1, 0, 1),
            Vector4(0, 0, 1, 1),
        ]
    )

    def read(self, file: BinaryIO) -> "CDspMeshFile":
        first = unpack("i", file.read(4))[0]
        self.legacy_header = first != 1314189598
        if not self.legacy_header:
            self.magic = first
            self.zero, self.mesh_count = unpack("ii", file.read(8))
        else:
            self.zero, self.mesh_count = -1, first
        if self.mesh_count < 0:
            raise ValueError(f"Invalid CDspMeshFile mesh count: {self.mesh_count}")
        self.bounding_box_lower_left_corner = Vector3().read(file)
        self.bounding_box_upper_right_corner = Vector3().read(file)
        self.meshes = [BattleforgeMesh().read(file) for _ in range(self.mesh_count)]
        if self.zero >= 0:
            self.some_points = [Vector4().read(file) for _ in range(3)]
        else:
            self.some_points = [Vector4(0, 0, 0, 1), Vector4(1, 0, 0, 1), Vector4(0, 0, 1, 1)]
        return self

    def write(self, file: BinaryIO) -> None:
        if self.mesh_count < 0 or self.mesh_count != len(self.meshes):
            raise ValueError("CDspMeshFile mesh count does not match meshes")
        if self.legacy_header:
            if self.zero != -1:
                raise ValueError("A legacy CDspMeshFile header has implicit version -1")
            file.write(pack("i", self.mesh_count))
            self.bounding_box_lower_left_corner.write(file)
            self.bounding_box_upper_right_corner.write(file)
            for mesh in self.meshes:
                mesh.write(file)
            return
        try:
            file.write(pack("i", self.magic))
        except Exception as exc:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}") from exc

        if self.magic == 1314189598:
            try:
                file.write(pack("ii", self.zero, self.mesh_count))
            except Exception as exc:
                raise TypeError(
                    f"This Mesh has the wrong Mesh Count: {self.mesh_count}"
                ) from exc
            try:
                self.bounding_box_lower_left_corner.write(file)
            except Exception as exc:
                raise TypeError("Error writing bounding_box_lower_left_corner") from exc

            try:
                self.bounding_box_upper_right_corner.write(file)
            except Exception as exc:
                raise TypeError("Error writing bounding_box_upper_right_corner") from exc

            for mesh in self.meshes:
                mesh.write(file)

            try:
                if self.zero >= 0:
                    if len(self.some_points) != 3:
                        raise ValueError("CDspMeshFile requires three points for version >= 0")
                    for point in self.some_points:
                        point.write(file)
            except Exception as exc:
                raise TypeError("Error writing some_points") from exc
        else:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")

    def size(self) -> int:
        size = 4 if self.legacy_header else 12  # Legacy count, or magic + version + count
        size += 12  # BoundingBox1
        size += 12  # BoundingBox2
        if not self.legacy_header and self.zero >= 0:
            size += sum(point.size() for point in self.some_points)
        size += sum(mesh.size() for mesh in self.meshes)

        return size
