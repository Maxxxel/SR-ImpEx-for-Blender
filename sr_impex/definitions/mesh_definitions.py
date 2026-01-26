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


@dataclass(eq=False, repr=False)
class Vertex:
    position: Optional[List[float]] = field(default_factory=list)
    normal: Optional[List[float]] = field(default_factory=list)
    texture: Optional[List[float]] = field(default_factory=list)
    tangent: Optional[List[float]] = field(default_factory=list)
    bitangent: Optional[List[float]] = field(default_factory=list)
    raw_weights: Optional[List[int]] = field(default_factory=list)
    bone_indices: Optional[List[int]] = field(default_factory=list)

    def read(self, file: BinaryIO, revision: int) -> "Vertex":
        if revision == 133121:
            data = unpack_data(file, "fff", "fff", "ff")
            self.position, self.normal, self.texture = data[0], data[1], data[2]
        elif revision == 12288 or revision == 2049:
            data = unpack_data(file, "fff", "fff")
            self.tangent, self.bitangent = data[0], data[1]
        elif revision == 12:
            data = unpack_data(file, "4B", "4B")
            self.raw_weights, self.bone_indices = data[0], data[1]
        elif revision == 163841:
            data = unpack_data(file, "fff", "ff", "4B")
            self.position, self.texture = data[0], data[1]
            self.normal = [0.0, 0.0, 0.0]
        return self

    def write(self, file: BinaryIO, revision: int) -> None:
        if revision == 133121:
            file.write(pack("fff", *self.position))
            file.write(pack("fff", *self.normal))
            file.write(pack("ff", *self.texture))
        elif revision == 12288 or revision == 2049:
            file.write(pack("fff", *self.tangent))
            file.write(pack("fff", *self.bitangent))
        elif revision == 12:
            file.write(pack("4B", *self.raw_weights))
            file.write(pack("4B", *self.bone_indices))
        elif revision == 163841:
            file.write(pack("fff", *self.position))
            file.write(pack("ff", *self.texture))
            # Normal is zeroed out

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

    def __post_init__(self):
        self.length = len(self.name)

    def read(self, file: BinaryIO) -> "Texture":
        self.identifier, self.length = unpack("ii", file.read(8))
        self.name = file.read(self.length).decode("utf-8").strip("\x00")
        self.spacer = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("ii", self.identifier, self.length))
        file.write(self.name.encode("utf-8"))
        file.write(pack("i", self.spacer))

    def size(self) -> int:
        return 8 + self.length + 4


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
    refraction_scale: float = 0.0  # 0.0 - 1.0 -> Dont know when to use
    distortion_mesh_scale: float = 0.0
    scratch: float = 0.0
    specular_scale: float = 0.0
    wind_response: float = 0.0
    wind_height: float = 0.0
    depth_write_threshold: float = 0.0
    saturation: float = 0.0
    unknown: float = 0.0

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
            self.unknown = unpack("f", file.read(4))[0]
            raise TypeError(f"Unknown Material {self.unknown}")
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
            file.write(pack("f", self.unknown))
            raise TypeError(f"Unknown Material {self.unknown}")

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

    def read(self, file: BinaryIO) -> "Refraction":
        self.length = unpack("i", file.read(4))[0]
        if self.length == 1:
            self.identifier = unpack("i", file.read(4))[0]
            self.rgb = list(unpack("3f", file.read(12)))
        elif self.length > 1:
            for _ in range(self.length):
                self.identifier = unpack("i", file.read(4))[0]
                self.rgb = list(unpack("3f", file.read(12)))
            # print(f"Found {self.length} refraction values!!!")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.length))
        if self.length == 1:
            file.write(pack("i", self.identifier))
            file.write(pack("3f", *self.rgb))

    def size(self) -> int:
        size = 4
        if self.length == 1:
            size += 4 + 12
        return size


@dataclass(eq=False, repr=False)
class LevelOfDetail:
    length: int = 1
    lod_level: int = 2

    def read(self, file: BinaryIO) -> "LevelOfDetail":
        self.length = unpack("i", file.read(4))[0]
        if self.length == 1:
            self.lod_level = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.length))
        if self.length == 1:
            file.write(pack("i", self.lod_level))

    def size(self) -> int:
        size = 4
        if self.length == 1:
            size += 4
        return size


@dataclass(eq=False, repr=False)
class EmptyString:
    length: int = 0
    unknown_string: str = ""

    def read(self, file: BinaryIO) -> "EmptyString":
        self.length = unpack("i", file.read(4))[0]
        self.unknown_string = unpack(
            f"{self.length * 2}s", file.read(calcsize(f"{self.length * 2}s"))
        )[0].decode("utf-8")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack(
                f"i{self.length * 2}s", self.length, self.unknown_string.encode("utf-8")
            )
        )

    def size(self) -> int:
        return calcsize(f"i{self.length * 2}s")


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

    def read(self, file: BinaryIO) -> "Flow":
        self.length = unpack("i", file.read(4))[0]
        if self.length == 4:
            self.max_flow_speed_identifier = unpack("i", file.read(4))[0]
            self.max_flow_speed = Vector4().read(file)
            self.min_flow_speed_identifier = unpack("i", file.read(4))[0]
            self.min_flow_speed = Vector4().read(file)
            self.flow_speed_change_identifier = unpack("i", file.read(4))[0]
            self.flow_speed_change = Vector4().read(file)
            self.flow_scale_identifier = unpack("i", file.read(4))[0]
            self.flow_scale = Vector4().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.length))
        if self.length == 4:
            file.write(pack("i", self.max_flow_speed_identifier))
            self.max_flow_speed.write(file)
            file.write(pack("i", self.min_flow_speed_identifier))
            self.min_flow_speed.write(file)
            file.write(pack("i", self.flow_speed_change_identifier))
            self.flow_speed_change.write(file)
            file.write(pack("i", self.flow_scale_identifier))
            self.flow_scale.write(file)

    def size(self) -> int:
        size = 4
        if self.length == 4:
            size += (
                16
                + self.max_flow_speed.size()
                + self.min_flow_speed.size()
                + self.flow_speed_change.size()
                + self.flow_scale.size()
            )
        return size


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
            elif self.material_parameters == -86061051:
                file.write(pack("ii", self.material_stuff, self.bool_parameter))
                self.textures.write(file)
                self.refraction.write(file)
                self.materials.write(file)
                self.level_of_detail.write(file)
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
        elif self.material_parameters == -86061051:
            size += 8  # MaterialStuff + BoolParameter
            size += self.textures.size()
            size += self.refraction.size()
            size += self.materials.size()
            size += self.level_of_detail.size()
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
        self.magic = unpack("i", file.read(4))[0]
        if self.magic == 1314189598:
            self.zero, self.mesh_count = unpack("ii", file.read(8))
            self.bounding_box_lower_left_corner = Vector3().read(file)
            self.bounding_box_upper_right_corner = Vector3().read(file)
            self.meshes = [BattleforgeMesh().read(file) for _ in range(self.mesh_count)]
            self.some_points = [Vector4().read(file) for _ in range(3)]
        else:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")
        return self

    def write(self, file: BinaryIO) -> None:
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
                for point in self.some_points:
                    point.write(file)
            except Exception as exc:
                raise TypeError("Error writing some_points") from exc
        else:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")

    def size(self) -> int:
        size = 12  # Magic + Zero + MeshCount
        size += 12  # BoundingBox1
        size += 12  # BoundingBox2
        size += sum(point.size() for point in self.some_points)
        size += sum(mesh.size() for mesh in self.meshes)

        return size
