from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from sys import version
from typing import List, Union, BinaryIO, Optional
from mathutils import Vector, Matrix, Quaternion
from .file_io import FileReader, FileWriter


def unpack_data(file: BinaryIO, *formats: str) -> List[List[Union[float, int]]]:
    result = []
    for fmt in formats:
        result.append(list(unpack(fmt, file.read(calcsize(fmt)))))
    return result

ClassMagic = {
    "CSkSkeleton": 1558308612,
    "CDspMeshFile": 1314189598,
    "CGeoOBBTree": 1845540702,
    "CGdLocatorList": 281702437,
}

MagicValues = {
    "CDspJointMap": -1340635850,
    "CGeoMesh": 100449016,
    "CGeoOBBTree": -933519637,
    "CSkSkinInfo": -761174227,
    "CDspMeshFile": -1900395636,
    "DrwResourceMeta": -183033339,
    "collisionShape": 268607026,
    "CGeoPrimitiveContainer": 1396683476,
    "CSkSkeleton": -2110567991,
    "CDrwLocatorList": 735146985,
    "AnimationSet": -475734043,
    "AnimationTimings": -1403092629,
    "EffectSet": 688490554,
}

AnimationType = {
    "CastResolve": 0,
    "Spawn": 1,
    "Melee": 2,
    "Channel": 3,
    "ModeSwitch": 4,
    "WormMovement": 5,
}

LocatorClass = {
    0: "HealthBar",  # Health Bar placement offset
    1: "DestructiblePart",  # Static module for parts/destructibles
    2: "Construction",  # aka. PivotOffset internally; Construction pieces
    3: "Turret",  # Animated attached unit that will play its attack animations -> SKA
    4: "FxbIdle",  # aka. WormDecal internally, effects for when not moving, only worm uses this originally
    5: "Wheel",  # Animated attached unit that will play its idle and walk/run animations
    6: "StaticPerm",  # aka. FXNode internally; Building/Object permanent effects
    7: "Unknown7",  #
    8: "DynamicPerm",  # Unit permanent effects -> FXB
    9: "DamageFlameSmall",  # Building fire location from damage, plays effect_building_flame_small.fxb
    10: "DamageFlameSmallSmoke",  # Building fire location from damage, plays effect_building_flame_small_smoke.fxb
    11: "DamageFlameLarge",  # Building fire location from damage, plays effect_building_flame_large.fxb
    12: "DamageSmokeOnly",  # Building smoke location from damage, plays effect_building_flame_smoke.fxb
    13: "DamageFlameHuge",  # Building fire location from damage, plays effect_building_flame_huge.fxb
    14: "SpellCast",  # seemingly not used anymore
    15: "SpellHitAll",  # as above
    16: "Hit",  # Point of being hit by attacks/spells
    29: "Projectile_Spawn",  # Point to use attacks/spells from -> sometimes FXB
}

# Also Node Order
InformationIndices = {
    "AnimatedUnit": {  # AnimatedInteractableObjectNoCollisionWithEffects
        "CGeoMesh": 1,
        "CGeoOBBTree": 8,
        "CDspJointMap": 7,
        "CSkSkinInfo": 9,
        "CSkSkeleton": 4,
        "CDspMeshFile": 5,
        "CDrwLocatorList": 3,
        "DrwResourceMeta": 11,
        "AnimationSet": 10,
        "AnimationTimings": 6,
        "EffectSet": 2,
    },
    "StaticObjectCollision": {
        "CGeoMesh": 1,
        "CGeoOBBTree": 5,
        "CDspJointMap": 4,
        "CDspMeshFile": 3,
        "DrwResourceMeta": 6,
        "CGeoPrimitiveContainer": 2,
        "collisionShape": 7,
    },
    "StaticObjectNoCollision": {
        "CGeoMesh": 1,
        "CGeoOBBTree": 4,
        "CDspJointMap": 3,
        "CDspMeshFile": 2,
        "DrwResourceMeta": 5,
    },
    "AnimatedObjectNoCollision": {
        "CGeoMesh": 1,
        "CGeoOBBTree": 6,
        "CDspJointMap": 5,
        "CSkSkinInfo": 7,
        "CSkSkeleton": 2,
        "CDspMeshFile": 3,
        "DrwResourceMeta": 9,
        "AnimationSet": 8,
        "AnimationTimings": 4,
    },
    "AnimatedObjectCollision": {
        "CGeoMesh": 1,
        "CGeoOBBTree": 7,
        "CDspJointMap": 6,
        "CSkSkinInfo": 8,
        "CSkSkeleton": 3,
        "CDspMeshFile": 4,
        "DrwResourceMeta": 10,
        "AnimationSet": 9,
        "AnimationTimings": 5,
        "CGeoPrimitiveContainer": 2,
        "collisionShape": 11,
    },
}

WriteOrder = {
    "AnimatedUnit": [
        "CDspJointMap",
        "CSkSkinInfo",
        "CSkSkeleton",
        "CDspMeshFile",
        "CDrwLocatorList",
        "DrwResourceMeta",
        "CGeoOBBTree",
        "CGeoMesh",
        "AnimationSet",
        "AnimationTimings",
        "EffectSet",
    ],
    "StaticObjectCollision": [
        "CDspJointMap",
        "CDspMeshFile",
        "DrwResourceMeta",
        "CGeoPrimitiveContainer",
        "CGeoOBBTree",
        "CGeoMesh",
        "collisionShape",
    ],
    "StaticObjectNoCollision": [
        "CDspJointMap",
        "CDspMeshFile",
        "DrwResourceMeta",
        "CGeoOBBTree",
        "CGeoMesh",
    ],
    "AnimatedObjectNoCollision": [
        "CDspJointMap",
        "CSkSkinInfo",
        "CSkSkeleton",
        "CDspMeshFile",
        "DrwResourceMeta",
        "CGeoOBBTree",
        "CGeoMesh",
        "AnimationSet",
        "AnimationTimings",
    ],
    "AnimatedObjectCollision": [
        "CDspJointMap",
        "CSkSkinInfo",
        "CSkSkeleton",
        "CDspMeshFile",
        "DrwResourceMeta",
        "CGeoPrimitiveContainer",
        "CGeoOBBTree",
        "CGeoMesh",
        "AnimationSet",
        "AnimationTimings",
        "collisionShape",
    ],
}


@dataclass(eq=False, repr=False)
class RootNode:
    identifier: int = 0
    unknown: int = 0
    length: int = field(default=9, init=False)
    name: str = "root node"

    def read(self, file: BinaryIO) -> "RootNode":
        self.identifier, self.unknown, self.length = unpack("iii", file.read(12))
        self.name = file.read(self.length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack(
                f"iii{self.length}s",
                self.identifier,
                self.unknown,
                self.length,
                self.name.encode("utf-8"),
            )
        )

    def size(self) -> int:
        return calcsize(f"iii{self.length}s")


@dataclass(eq=False, repr=False)
class Node:
    info_index: int = 0
    length: int = field(default=0, init=False)
    name: str = ""
    zero: int = 0

    def __post_init__(self):
        self.length = len(self.name)

    def read(self, file: BinaryIO) -> "Node":
        self.info_index, self.length = unpack("ii", file.read(8))
        self.name = (
            unpack(f"{self.length}s", file.read(calcsize(f"{self.length}s")))[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.zero = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.info_index))
        file.write(pack("i", self.length))
        file.write(pack(f"{self.length}s", self.name.encode("utf-8")))
        file.write(pack("i", self.zero))

    def size(self) -> int:
        return 8 + calcsize(f"{self.length}s") + 4


@dataclass(eq=False, repr=False)
class RootNodeInformation:
    zeroes: List[int] = field(default_factory=lambda: [0] * 16)
    neg_one: int = -1
    one: int = 1
    node_information_count: int = 0
    zero: int = 0
    data_object: None = None  # Placeholder
    node_size: int = 0
    node_name = ""

    def read(self, file: BinaryIO) -> "RootNodeInformation":
        self.zeroes = unpack("16b", file.read(16))
        self.neg_one, self.one, self.node_information_count, self.zero = unpack(
            "iiii", file.read(16)
        )
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack(
                "16biiii",
                *self.zeroes,
                self.neg_one,
                self.one,
                self.node_information_count,
                self.zero,
            )
        )

    def size(self) -> int:
        return 32

    def update_offset(self, _: int) -> None:
        pass


@dataclass(eq=False, repr=False)
class NodeInformation:
    """Node Information"""

    magic: int = field(init=False)
    identifier: int = -1
    offset: int = -1
    node_size: int = field(init=False)
    uk1: int = 0
    linked_node: int = -1
    uk2: int = 0
    uk3: int = 0
    node_name: str = ""

    def __post_init__(self):
        self.magic = MagicValues.get(self.node_name) if self.node_name else 0

    def read(self, file: BinaryIO) -> "NodeInformation":
        self.magic, self.identifier, self.offset, self.node_size = unpack(
            "iiii", file.read(16)
        )
        self.uk1 = unpack("i", file.read(4))[0]
        self.linked_node = unpack("i", file.read(4))[0]
        self.uk2 = unpack("i", file.read(4))[0]
        self.uk3 = unpack("i", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack("iiii", self.magic, self.identifier, self.offset, self.node_size)
        )
        file.write(pack("i", self.uk1))
        file.write(pack("i", self.linked_node))
        file.write(pack("i", self.uk2))
        file.write(pack("i", self.uk3))

    def update_offset(self, offset: int) -> None:
        self.offset = offset

    def size(self) -> int:
        return calcsize("iiii16b")


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
        if (
            revision == 133121
            or revision == 134365185
            or revision == 536905729
            or revision == 134381569
        ):
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
            data = unpack_data(file, "fff", "ff", "4B")
            self.position, self.texture = data[0], data[1]
            self.normal = [0.0, 0.0, 0.0]
        return self

    def write(self, file: BinaryIO, revision: int) -> None:
        if (
            revision == 133121
            or revision == 134365185
            or revision == 536905729
            or revision == 134381569
        ):
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
class Face:
    indices: List[int] = field(default_factory=lambda: [0] * 3)

    def read(self, file: BinaryIO) -> "Face":
        self.indices = list(unpack("3H", file.read(6)))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("3H", *self.indices))

    def size(self) -> int:
        return 6


@dataclass(repr=False)
class Vector4:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0
    xyz: Vector = field(default_factory=lambda: Vector((0, 0, 0)))

    def read(self, file: BinaryIO) -> "Vector4":
        self.x, self.y, self.z, self.w = unpack("4f", file.read(16))
        self.xyz = Vector((self.x, self.y, self.z))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("4f", self.x, self.y, self.z, self.w))

    def size(self) -> int:
        return 16


@dataclass(repr=False)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    xyz: Vector = field(default_factory=lambda: Vector((0, 0, 0)))

    def __post_init__(self):
        self.xyz = Vector((self.x, self.y, self.z))

    def read(self, file: BinaryIO) -> "Vector3":
        self.x, self.y, self.z = unpack("3f", file.read(12))
        self.xyz = Vector((self.x, self.y, self.z))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("3f", self.x, self.y, self.z))

    def size(self) -> int:
        return 12


@dataclass(eq=True, repr=False)
class Matrix4x4:
    matrix: tuple = ((0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0))

    def read(self, file: BinaryIO) -> "Matrix4x4":
        self.matrix = unpack("16f", file.read(64))
        return self

    def write(self, file: BinaryIO) -> None:
        # We have 4 Tuples of 4 floats
        for i in range(4):
            file.write(pack("4f", *self.matrix[i]))

    def size(self) -> int:
        return 64


@dataclass(eq=True, repr=False)
class Matrix3x3:
    matrix: tuple = ((0, 0, 0), (0, 0, 0), (0, 0, 0))
    math_matrix: Matrix = field(
        default_factory=lambda: Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
    )

    def read(self, file: BinaryIO) -> "Matrix3x3":
        self.matrix = unpack("9f", file.read(36))
        self.math_matrix = Matrix(
            (
                (self.matrix[0], self.matrix[1], self.matrix[2]),
                (self.matrix[3], self.matrix[4], self.matrix[5]),
                (self.matrix[6], self.matrix[7], self.matrix[8]),
            )
        )
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("9f", *self.matrix))

    def size(self) -> int:
        return 36


@dataclass(eq=True, repr=False)
class CMatCoordinateSystem:
    matrix: Matrix3x3 = field(default_factory=Matrix3x3)
    position: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "CMatCoordinateSystem":
        self.matrix = Matrix3x3().read(file)
        self.position = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.matrix.write(file)
        self.position.write(file)

    def size(self) -> int:
        return self.matrix.size() + self.position.size()


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
        file.write(pack("ii", self.revision, self.vertex_size))
        for i, vertex in enumerate(self.vertices):
            vertex.write(file, self.revision)

    def size(self) -> int:
        s = 8 + self.vertex_size * len(self.vertices)
        return s


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
        self.name = self.name.replace("building_nature_versatile_tower_", "")
        if len(self.name) > 63:
            self.name = str(hash(self.name))
            print(f"Hashed Bone Name: {self.name}")
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

    def write(self, file: BinaryIO) -> "BoneMatrix":
        for bone_vertex in self.bone_vertices:
            bone_vertex.write(file)
        return self

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
    super_parent: "Matrix4x4" = field(
        default_factory=lambda: Matrix4x4(
            ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        )
    )

    def read(self, file: BinaryIO) -> "CSkSkeleton":
        self.magic, self.version, self.bone_matrix_count = unpack("iii", file.read(12))
        self.bone_matrices = [
            BoneMatrix().read(file) for _ in range(self.bone_matrix_count)
        ]
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
    special: float = 16
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
            elif index == 12:
                self.identifier = 1936745324
                self.special = 16

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
        elif self.identifier == 1936745324:
            self.special = unpack("f", file.read(4))[0]
        else:
            self.unknown = unpack("f", file.read(4))[0]
            print(f"Unknown Material {self.identifier}: {self.unknown}")
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
        elif self.identifier == 1936745324:
            file.write(pack("f", self.special))
        else:
            file.write(pack("f", self.unknown))
            raise TypeError(f"Unknown Material {self.unknown}")
        return self

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
            print(f"Found {self.length} refraction values!!!")
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
        file.write(pack("ii", self.vertex_count, self.face_count))
        for face in self.faces:
            face.write(file)
        file.write(pack("B", self.mesh_count))
        for mesh_data in self.mesh_data:
            mesh_data.write(file)
        self.bounding_box_lower_left_corner.write(file)
        self.bounding_box_upper_right_corner.write(file)
        file.write(pack("=hi", self.material_id, self.material_parameters))

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
    mesh_count: int = 1
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
        elif self.magic == 1:
            self.bounding_box_lower_left_corner = Vector3().read(file)
            self.bounding_box_upper_right_corner = Vector3().read(file)
            self.meshes = [BattleforgeMesh().read(file)]
        else:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.magic))
        if self.magic == 1314189598:
            file.write(pack("ii", self.zero, self.mesh_count))
            self.bounding_box_lower_left_corner.write(file)
            self.bounding_box_upper_right_corner.write(file)

            for mesh in self.meshes:
                mesh.write(file)

            for point in self.some_points:
                point.write(file)
        else:
            raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")

    def size(self) -> int:
        size = 12  # Magic + Zero + MeshCount
        size += 12  # BoundingBox1
        size += 12  # BoundingBox2
        size += sum(point.size() for point in self.some_points)
        size += sum(mesh.size() for mesh in self.meshes)

        return size


@dataclass(eq=False, repr=False)
class OBBNode:
    oriented_bounding_box: CMatCoordinateSystem = field(
        default_factory=CMatCoordinateSystem
    )
    first_child_index: int = 0
    second_child_index: int = 0
    skip_pointer: int = 0
    node_depth: int = 0
    triangle_offset: int = 0
    total_triangles: int = 0

    def read(self, file: BinaryIO) -> "OBBNode":
        self.oriented_bounding_box = CMatCoordinateSystem().read(file)
        (
            self.first_child_index,
            self.second_child_index,
            self.skip_pointer,
            self.node_depth,
            self.triangle_offset,
            self.total_triangles,
        ) = unpack("4H2I", file.read(16))
        return self

    def write(self, file: BinaryIO) -> None:
        self.oriented_bounding_box.write(file)
        file.write(
            pack(
                "4H2I",
                self.first_child_index,
                self.second_child_index,
                self.skip_pointer,
                self.node_depth,
                self.triangle_offset,
                self.total_triangles,
            )
        )

    def size(self) -> int:
        return self.oriented_bounding_box.size() + 16


@dataclass(eq=False, repr=False)
class CGeoOBBTree:
    magic: int = 1845540702
    version: int = 3 # Can be 1 too
    matrix_count: int = 0
    obb_nodes: List[OBBNode] = field(default_factory=list)
    triangle_count: int = 0
    faces: List[Face] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CGeoOBBTree":
        self.magic, self.version = unpack("ii", file.read(8))
        if self.version == 1:
            print("Version 1 OBBTree found, not implemented yet.")
        elif self.version == 3:
            self.matrix_count = unpack("i", file.read(4))[0]
            self.obb_nodes = [OBBNode().read(file) for _ in range(self.matrix_count)]
            self.triangle_count = unpack("i", file.read(4))[0]
            self.faces = [Face().read(file) for _ in range(self.triangle_count)]
        else:
            raise TypeError(f"Unknown OBBTree Version {self.version}")
        
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("iii", self.magic, self.version, self.matrix_count))
        for obb_node in self.obb_nodes:
            obb_node.write(file)
        file.write(pack("i", self.triangle_count))
        for face in self.faces:
            face.write(file)

    def size(self) -> int:
        return (
            16
            + sum(obb_node.size() for obb_node in self.obb_nodes)
            + sum(face.size() for face in self.faces)
        )


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
    magic: int = 0
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


@dataclass(eq=False, repr=False)
class GDLocator:
    cmat_coordinate_system: CMatCoordinateSystem = field(
        default_factory=CMatCoordinateSystem
    )
    class_id: int = 0  # short
    sub_id: int = 0  # short

    def read(self, file: BinaryIO) -> "GDLocator":
        self.cmat_coordinate_system = CMatCoordinateSystem().read(file)
        self.class_id, self.sub_id = unpack("hh", file.read(4))
        return self

    def write(self, file: BinaryIO) -> None:
        self.cmat_coordinate_system.write(file)
        file.write(pack("hh", self.class_id, self.sub_id))

    def size(self) -> int:
        return self.cmat_coordinate_system.size() + 4

@dataclass(eq=False, repr=False)
class CGdLocatorList:
    magic: int = 281702437
    version: int = 2
    length: int = 0
    gdlocators: List[GDLocator] = field(default_factory=list)
    
    def read(self, file: BinaryIO) -> "CGdLocatorList":
        self.magic, self.version = unpack("ii", file.read(8))
        if self.version == 2:
            self.length = unpack("i", file.read(4))[0]
            self.gdlocators = [GDLocator().read(file) for _ in range(self.length)]
        elif self.version == 1:
            pass # Nothing else
        else:
            print(f"\nnot implemented locator list version {self.version}\n")
        return self
    
    def write(self, file: BinaryIO) -> None:
        file.write(pack("ii", self.magic, self.version))
        if self.version == 2:
            file.write(pack("i", self.length))
            for locator in self.gdlocators:
                locator.write(file)

@dataclass(eq=False, repr=False)
class CGeoAABox:
    lower_left_corner: Vector3 = field(default_factory=Vector3)
    upper_right_corner: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "CGeoAABox":
        self.lower_left_corner = Vector3().read(file)
        self.upper_right_corner = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.lower_left_corner.write(file)
        self.upper_right_corner.write(file)

    def size(self) -> int:
        return self.lower_left_corner.size() + self.upper_right_corner.size()


@dataclass(eq=True, repr=False)
class BoxShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_aabox: CGeoAABox = field(default_factory=CGeoAABox)

    def read(self, file: BinaryIO) -> "BoxShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_aabox = CGeoAABox().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_aabox.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_aabox.size()


@dataclass(eq=True, repr=False)
class CGeoCylinder:
    center: Vector3 = field(default_factory=Vector3)
    height: float = 0.0
    radius: float = 0.0

    def read(self, file: BinaryIO) -> "CGeoCylinder":
        self.center = Vector3().read(file)
        self.height, self.radius = unpack("ff", file.read(8))
        return self

    def write(self, file: BinaryIO) -> None:
        self.center.write(file)
        file.write(pack("ff", self.height, self.radius))

    def size(self) -> int:
        return self.center.size() + 8


@dataclass(eq=True, repr=False)
class CylinderShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_cylinder: CGeoCylinder = field(default_factory=CGeoCylinder)

    def read(self, file: BinaryIO) -> "CylinderShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_cylinder = CGeoCylinder().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_cylinder.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_cylinder.size()


@dataclass(eq=True, repr=False)
class CGeoSphere:
    radius: float = 0.0
    center: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "CGeoSphere":
        self.radius = unpack("f", file.read(4))[0]
        self.center = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("f", self.radius))
        self.center.write(file)

    def size(self) -> int:
        return 4 + self.center.size()


@dataclass(eq=True, repr=False)
class SphereShape:
    coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
    geo_sphere: CGeoSphere = field(default_factory=CGeoSphere)

    def read(self, file: BinaryIO) -> "SphereShape":
        self.coord_system = CMatCoordinateSystem().read(file)
        self.geo_sphere = CGeoSphere().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.coord_system.write(file)
        self.geo_sphere.write(file)

    def size(self) -> int:
        return self.coord_system.size() + self.geo_sphere.size()


@dataclass(eq=True, repr=False)
class CollisionShape:
    version: int = 1
    box_count: int = 0
    boxes: List[BoxShape] = field(default_factory=list)
    sphere_count: int = 0
    spheres: List[SphereShape] = field(default_factory=list)
    cylinder_count: int = 0
    cylinders: List[CylinderShape] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "CollisionShape":
        self.version = unpack("B", file.read(1))
        self.box_count = unpack("I", file.read(4))[0]
        self.boxes = [BoxShape().read(file) for _ in range(self.box_count)]
        self.sphere_count = unpack("I", file.read(4))[0]
        self.spheres = [SphereShape().read(file) for _ in range(self.sphere_count)]
        self.cylinder_count = unpack("I", file.read(4))[0]
        self.cylinders = [
            CylinderShape().read(file) for _ in range(self.cylinder_count)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("B", self.version))
        file.write(pack("I", self.box_count))
        for box in self.boxes:
            box.write(file)

        file.write(pack("I", self.sphere_count))
        for sphere in self.spheres:
            sphere.write(file)

        file.write(pack("I", self.cylinder_count))
        for cylinder in self.cylinders:
            cylinder.write(file)

    def size(self) -> int:
        return (
            1
            + 12
            + sum(box.size() for box in self.boxes)
            + sum(sphere.size() for sphere in self.spheres)
            + sum(cylinder.size() for cylinder in self.cylinders)
        )


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

    def write(self, _: BinaryIO) -> "CGeoPrimitiveContainer":
        """Writes the CGeoPrimitiveContainer to the buffer"""
        pass

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

    def write(self, file: BinaryIO) -> "Constraint":
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
        return self

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

    def write(self, file: BinaryIO) -> "IKAtlas":
        """Writes the IKAtlas to the buffer"""
        file.write(pack("i", self.identifier))
        file.write(pack("h", self.version))
        if self.version >= 1:
            file.write(pack("ii", self.axis, self.chain_order))
            for constraint in self.constraints:
                constraint.write(file)
            if self.version >= 2:
                file.write(pack("h", self.purpose_flags))
        return self

    def size(self) -> int:
        """Returns the size of the IKAtlas"""
        base = 6
        if self.version >= 1:
            base += 8 + sum(constraint.size() for constraint in self.constraints)
            if self.version >= 2:
                base += 2
        return base


@dataclass(eq=False, repr=False)
class AnimationSetVariant:
    version: int = 7
    weight: int = 100
    length: int = 0
    file: str = ""
    start: float = 0.0
    end: float = 1.0
    allows_ik: int = 1
    force_no_blend: int = 0

    def read(self, file: BinaryIO) -> "AnimationSetVariant":
        """Reads the AnimationSetVariant from the buffer"""
        self.version = unpack("i", file.read(4))[0]
        self.weight = unpack("i", file.read(4))[0]
        self.length = unpack("i", file.read(4))[0]
        self.file = (
            unpack(f"{self.length}s", file.read(calcsize(f"{self.length}s")))[0]
            .decode("utf-8")
            .strip("\x00")
        )

        if self.version >= 4:
            self.start = unpack("f", file.read(4))[0]
            self.end = unpack("f", file.read(4))[0]
        if self.version >= 5:
            self.allows_ik = unpack("B", file.read(1))[0]
        if self.version >= 7:
            self.force_no_blend = unpack("B", file.read(1))[0]

        return self

    def write(self, file: BinaryIO) -> "AnimationSetVariant":
        """Writes the AnimationSetVariant to the buffer"""
        file.write(pack("i", self.version))
        file.write(pack("i", self.weight))
        file.write(pack("i", self.length))
        file.write(pack(f"{self.length}s", self.file.encode("utf-8")))
        if self.version >= 4:
            file.write(pack("ff", self.start, self.end))
        if self.version >= 5:
            file.write(pack("B", self.allows_ik))
        if self.version >= 7:
            file.write(pack("B", self.force_no_blend))
        return self

    def size(self) -> int:
        """Returns the size of the AnimationSetVariant"""
        base = 12 + self.length
        if self.version >= 4:
            base += 8
        if self.version >= 5:
            base += 1
        if self.version >= 7:
            base += 1
        return base


@dataclass(eq=False, repr=False)
class ModeAnimationKey:
    """ModeAnimationKey"""

    type: int = 6
    length: int = 11
    file: str = "Battleforge"
    unknown: int = 2
    unknown2: Union[List[int], int] = 3
    vis_job: int = 0
    unknown3: int = 3
    special_mode: int = 0  # SpecialMode
    variant_count: int = 1
    animation_set_variants: List[AnimationSetVariant] = field(default_factory=list)

    def read(self, file: BinaryIO, uk: int) -> "ModeAnimationKey":
        """Reads the ModeAnimationKey from the buffer"""
        if uk != 2:
            self.type = unpack("i", file.read(4))[0]
        else:
            self.type = 2
        self.length = unpack("i", file.read(4))[0]
        self.file = (
            unpack(f"{self.length}s", file.read(calcsize(f"{self.length}s")))[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.unknown = unpack("i", file.read(4))[0]
        if self.type == 1:
            self.unknown2 = list(unpack("24B", file.read(24)))
        elif self.type <= 5:
            self.unknown2 = unpack("i", file.read(4))[0]
            self.special_mode = unpack("h", file.read(2))[0]
        elif self.type == 6:
            self.unknown2 = unpack("i", file.read(4))[0]
            self.vis_job = unpack("h", file.read(2))[0]
            self.unknown3 = unpack("i", file.read(4))[0]
            self.special_mode = unpack("h", file.read(2))[0]
        self.variant_count = unpack("i", file.read(4))[0]
        self.animation_set_variants = [
            AnimationSetVariant().read(file) for _ in range(self.variant_count)
        ]
        return self

    def write(self, file: BinaryIO) -> "ModeAnimationKey":
        """Writes the ModeAnimationKey to the buffer"""
        file.write(pack("i", self.type))
        file.write(pack("i", self.length))
        file.write(pack(f"{self.length}s", self.file.encode("utf-8")))
        file.write(pack("i", self.unknown))
        if self.type == 1:
            file.write(pack("24B", *self.unknown2))
        elif self.type <= 5:
            file.write(pack("i", self.unknown2))
            file.write(pack("h", self.special_mode))
        elif self.type == 6:
            file.write(pack("i", self.unknown2))
            file.write(pack("h", self.vis_job))
            file.write(pack("i", self.unknown3))
            file.write(pack("h", self.special_mode))
        file.write(pack("i", self.variant_count))
        for animation_set_variant in self.animation_set_variants:
            animation_set_variant.write(file)
        return self

    def size(self) -> int:
        """Returns the size of the ModeAnimationKey"""
        base = 12 + self.length
        if self.type == 1:
            base += 24
        elif self.type <= 5:
            base += 6
        elif self.type == 6:
            base += 12
        base += 4
        for animation_set_variant in self.animation_set_variants:
            base += animation_set_variant.size()
        return base


@dataclass(eq=False, repr=False)
class AnimationMarker:
    """AnimationMarker"""

    is_spawn_animation: int = 0
    time: float = 0.0
    direction: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))
    position: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))

    def read(self, file: BinaryIO) -> "AnimationMarker":
        """Reads the AnimationMarker from the buffer"""
        self.is_spawn_animation = unpack("i", file.read(4))[0]  # 4 bytes
        self.time = unpack("f", file.read(4))[0]  # 4 bytes
        self.direction = Vector3().read(file)  # 12 bytes
        self.position = Vector3().read(file)  # 12 bytes
        return self

    def write(self, file: BinaryIO) -> "AnimationMarker":
        """Writes the AnimationMarker to the buffer"""
        file.write(pack("if", self.is_spawn_animation, self.time))
        self.direction.write(file)
        self.position.write(file)
        return self

    def size(self) -> int:
        """Returns the size of the AnimationMarker"""
        return 32


@dataclass(eq=False, repr=False)
class AnimationMarkerSet:
    """AnimationMarkerSet"""

    anim_id: int = 0
    length: int = 0
    name: str = ""
    animation_marker_id: int = 0  # uint
    marker_count: int = 1  # Always 1
    animation_markers: List[AnimationMarker] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "AnimationMarkerSet":
        """Reads the AnimationMarkerSet from the buffer"""
        self.anim_id = unpack("i", file.read(4))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = (
            unpack(f"{self.length}s", file.read(calcsize(f"{self.length}s")))[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.animation_marker_id = unpack("I", file.read(4))[0]
        self.marker_count = unpack("i", file.read(4))[0]
        self.animation_markers = [
            AnimationMarker().read(file) for _ in range(self.marker_count)
        ]
        return self

    def write(self, file: BinaryIO) -> "AnimationMarkerSet":
        """Writes the AnimationMarkerSet to the buffer"""
        file.write(pack("ii", self.anim_id, self.length))
        file.write(pack(f"{self.length}s", self.name.encode("utf-8")))
        file.write(pack("Ii", self.animation_marker_id, self.marker_count))
        for animation_marker in self.animation_markers:
            animation_marker.write(file)
        return self

    def size(self) -> int:
        """Returns the size of the AnimationMarkerSet"""
        return (
            16
            + self.length
            + sum(
                animation_marker.size() for animation_marker in self.animation_markers
            )
        )


@dataclass(eq=False, repr=False)
class UnknownStruct2:
    """UnknownStruct2"""

    unknown_ints: List[int] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "UnknownStruct2":
        """Reads the UnknownStruct2 from the buffer"""
        self.unknown_ints = [unpack("i", file.read(4))[0] for _ in range(5)]
        return self

    def write(self, file: BinaryIO) -> "UnknownStruct2":
        """Writes the UnknownStruct2 to the buffer"""
        for unknown_int in self.unknown_ints:
            file.write(pack("i", unknown_int))
        return self

    def size(self) -> int:
        """Returns the size of the UnknownStruct2"""
        return 20


@dataclass(eq=False, repr=False)
class UnknownStruct:
    """UnknownStruct"""

    unknown: int = 0
    length: int = 0
    name: str = ""
    unknown2: int = 0
    unknown3: int = 0
    unknown_structs: List[UnknownStruct2] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "UnknownStruct":
        """Reads the UnknownStruct from the buffer"""
        self.unknown = unpack("i", file.read(4))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = (
            unpack(f"{self.length}s", file.read(calcsize(f"{self.length}s")))[0]
            .decode("utf-8")
            .strip("\x00")
        )
        self.unknown2 = unpack("i", file.read(4))[0]
        self.unknown3 = unpack("i", file.read(4))[0]
        self.unknown_structs = [
            UnknownStruct2().read(file) for _ in range(self.unknown3)
        ]
        return self

    def write(self, file: BinaryIO) -> "UnknownStruct":
        """Writes the UnknownStruct to the buffer"""
        file.write(pack("ii", self.unknown, self.length))
        file.write(pack(f"{self.length}s", self.name.encode("utf-8")))
        file.write(pack("ii", self.unknown2, self.unknown3))
        for unknown_struct2 in self.unknown_structs:
            unknown_struct2.write(file)
        return self

    def size(self) -> int:
        """Returns the size of the UnknownStruct"""
        return (
            16
            + self.length
            + sum(unknown_struct2.size() for unknown_struct2 in self.unknown_structs)
        )


@dataclass(eq=False, repr=False)
class AnimationSet:
    """AnimationSet"""

    length: int = 11
    magic: str = "Battleforge"
    version: int = 6
    default_run_speed: float = 4.8  # TODO: Add a way to show/edit this value in Blender
    # TODO: Add a way to show/edit this value in Blender
    default_walk_speed: float = 2.3
    revision: int = 0  # 0 For Animated Objects
    # TODO find out how often these values are used and for which object/unit/building types
    mode_change_type: int = 0
    hovering_ground: int = 0
    fly_bank_scale: float = 1  # Changes for flying units
    fly_accel_scale: float = 0  # Changes for flying units
    fly_hit_scale: float = 1  # Changes for flying units
    allign_to_terrain: int = 0
    mode_animation_key_count: int = 0  # How many different animations are there?
    mode_animation_keys: List[ModeAnimationKey] = field(default_factory=list)
    has_atlas: int = 1  # 1 or 2
    atlas_count: int = 0  # Animated Objects: 0
    ik_atlases: List[IKAtlas] = field(default_factory=list)
    uk_len: int = 0
    uk_ints: List[int] = field(default_factory=list)
    subversion: int = 2
    animation_marker_count: int = 0  # Animated Objects: 0
    animation_marker_sets: List[AnimationMarkerSet] = field(default_factory=list)
    unknown: int = 0  # Not needed
    unknown_structs: List[UnknownStruct] = field(default_factory=list)  # Not needed
    data_object: str = None  # Placeholder for the animation name

    def read(self, file: BinaryIO) -> "AnimationSet":
        """Reads the AnimationSet from the buffer"""
        self.length = unpack("i", file.read(4))[0]
        self.magic = (
            unpack("11s", file.read(calcsize("11s")))[0].decode("utf-8").strip("\x00")
        )
        self.version = unpack("i", file.read(4))[0]
        self.default_run_speed = unpack("f", file.read(4))[0]
        self.default_walk_speed = unpack("f", file.read(4))[0]

        if self.version == 2:
            self.mode_animation_key_count = unpack("i", file.read(4))[0]
        else:
            self.revision = unpack("i", file.read(4))[0]

        if self.version >= 6:
            if self.revision >= 2:
                self.mode_change_type = unpack("B", file.read(1))[0]
                self.hovering_ground = unpack("B", file.read(1))[0]

            if self.revision >= 5:
                self.fly_bank_scale = unpack("f", file.read(4))[0]
                self.fly_accel_scale = unpack("f", file.read(4))[0]
                self.fly_hit_scale = unpack("f", file.read(4))[0]

            if self.revision >= 6:
                self.allign_to_terrain = unpack("B", file.read(1))[0]

        uk: int = 0

        if self.version == 2:
            uk = unpack("i", file.read(4))[0]
        else:
            self.mode_animation_key_count = unpack("i", file.read(4))[0]

        self.mode_animation_keys = [
            ModeAnimationKey().read(file, uk)
            for _ in range(self.mode_animation_key_count)
        ]

        if self.version >= 3:
            self.has_atlas = unpack("h", file.read(2))[0]

            if self.has_atlas >= 1:
                self.atlas_count = unpack("i", file.read(4))[0]
                self.ik_atlases = [
                    IKAtlas().read(file) for _ in range(self.atlas_count)
                ]

            if self.has_atlas >= 2:
                self.uk_len = unpack("i", file.read(4))[0]
                self.uk_ints = list(
                    unpack(f"{self.uk_len}i", file.read(calcsize(f"{self.uk_len}i")))
                )

        if self.version >= 4:
            self.subversion = unpack("h", file.read(2))[0]

            if self.subversion == 2:
                self.animation_marker_count = unpack("i", file.read(4))[0]
                self.animation_marker_sets = [
                    AnimationMarkerSet().read(file)
                    for _ in range(self.animation_marker_count)
                ]
            elif self.subversion == 1:
                self.unknown = unpack("i", file.read(4))[0]
                self.unknown_structs = [
                    UnknownStruct().read(file) for _ in range(self.unknown)
                ]

        return self

    def write(self, file: BinaryIO) -> "AnimationSet":
        """Writes the AnimationSet to the buffer"""
        file.write(pack("i", self.length))
        file.write(pack("11s", self.magic.encode("utf-8")))
        file.write(pack("i", self.version))
        file.write(pack("ff", self.default_run_speed, self.default_walk_speed))

        if self.version == 2:
            file.write(pack("i", self.mode_animation_key_count))
        else:
            file.write(pack("i", self.revision))

        if self.version >= 6:
            if self.revision >= 2:
                file.write(pack("BB", self.mode_change_type, self.hovering_ground))
            if self.revision >= 5:
                file.write(
                    pack(
                        "fff",
                        self.fly_bank_scale,
                        self.fly_accel_scale,
                        self.fly_hit_scale,
                    )
                )
            if self.revision >= 6:
                file.write(pack("B", self.allign_to_terrain))

        if self.version == 2:
            file.write(pack("i", 0))
        else:
            file.write(pack("i", self.mode_animation_key_count))

        for mode_animation_key in self.mode_animation_keys:
            mode_animation_key.write(file)

        if self.version >= 3:
            file.write(pack("h", self.has_atlas))

            if self.has_atlas >= 1:
                file.write(pack("i", self.atlas_count))
                for ik_atlas in self.ik_atlases:
                    ik_atlas.write(file)

            if self.has_atlas >= 2:
                file.write(pack("i", self.uk_len))
                for uk_int in self.uk_ints:
                    file.write(pack("i", uk_int))

        if self.version >= 4:
            file.write(pack("h", self.subversion))

            if self.subversion == 2:
                file.write(pack("i", self.animation_marker_count))
                for animation_marker_set in self.animation_marker_sets:
                    animation_marker_set.write(file)
            elif self.subversion == 1:
                file.write(pack("i", self.unknown))
                for unknown_struct in self.unknown_structs:
                    unknown_struct.write(file)

        return self

    def size(self) -> int:
        """Returns the size of the AnimationSet"""
        base = 27 + 4 + 4

        if self.version >= 6:
            if self.revision >= 2:
                base += 2
            if self.revision >= 5:
                base += 12
            if self.revision >= 6:
                base += 1

        for mode_animation_key in self.mode_animation_keys:
            base += mode_animation_key.size()

        if self.version >= 3:
            base += 2
            if self.has_atlas >= 1:
                base += 4 + sum(ik_atlas.size() for ik_atlas in self.ik_atlases)
            if self.has_atlas >= 2:
                base += 4 + 4 * len(self.uk_ints)

        if self.version >= 4:
            base += 2
            if self.subversion == 2:
                base += 4 + sum(
                    animation_marker_set.size()
                    for animation_marker_set in self.animation_marker_sets
                )
            elif self.subversion == 1:
                base += 4 + sum(
                    unknown_struct.size() for unknown_struct in self.unknown_structs
                )

        return base


@dataclass(eq=False, repr=False)
class Timing:
    cast_ms: int = 0  # Int
    resolve_ms: int = 0  # Int
    direction: Vector = Vector((0.0, 0.0, 1.0))  # Vector
    animation_marker_id: int = 0  # UInt

    def read(self, file: BinaryIO) -> "Timing":
        """Reads the Timing from the buffer"""
        self.cast_ms = unpack("i", file.read(4))[0]
        self.resolve_ms = unpack("i", file.read(4))[0]
        self.direction = Vector(unpack("fff", file.read(12)))
        self.animation_marker_id = unpack("I", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> "Timing":
        """Writes the Timing to the buffer"""
        file.write(pack("i", self.cast_ms))
        file.write(pack("i", self.resolve_ms))
        file.write(pack("fff", *self.direction))
        file.write(pack("I", self.animation_marker_id))
        return self

    def size(self) -> int:
        """Returns the size of the Timing"""
        return calcsize("iifffi")


@dataclass(eq=False, repr=False)
class TimingVariant:
    # Byte. The weight of this variant. The higher the weight, the more likely it is to be chosen.
    weight: int = 0
    variant_index: int = 0  # Byte.
    # Short. The number of Timings for this Variant. Most of the time, this is 1.
    timing_count: int = 0
    timings: List[Timing] = field(default_factory=list)

    def read(self, file: BinaryIO, animation_timing_version: int) -> "TimingVariant":
        """Reads the TimingVariant from the buffer"""
        self.weight = unpack("B", file.read(1))[0]
        if animation_timing_version == 4:
            self.variant_index = unpack("B", file.read(1))[0]
        self.timing_count = unpack("H", file.read(2))[0]
        self.timings = [Timing().read(file) for _ in range(self.timing_count)]
        return self

    def write(self, file: BinaryIO, animation_timing_version: int) -> "TimingVariant":
        """Writes the TimingVariant to the buffer"""
        file.write(pack("B", self.weight))
        if animation_timing_version == 4:
            file.write(pack("B", self.variant_index))
        file.write(pack("H", self.timing_count))
        for timing in self.timings:
            timing.write(file)
        return self

    def size(self, animation_timing_version: int) -> int:
        """Returns the size of the TimingVariant"""
        if animation_timing_version == 4:
            return 4 + sum(timing.size() for timing in self.timings)
        return 3 + sum(timing.size() for timing in self.timings)


@dataclass(eq=False, repr=False)
class AnimationTiming:
    animation_type: int = AnimationType["CastResolve"]  # int
    animation_tag_id: int = 0
    is_enter_mode_animation: int = 0  # Short. This is 1 most of the time.
    # Short. The number of Animations for this Type/TagID combination.
    variant_count: int = 0
    timing_variants: List[TimingVariant] = field(default_factory=list)

    def read(self, file: BinaryIO, animation_timing_version: int) -> "AnimationTiming":
        """Reads the AnimationTiming from the buffer"""
        self.animation_type = unpack("i", file.read(4))[0]
        if animation_timing_version in [2, 3, 4]:
            self.animation_tag_id = unpack("i", file.read(4))[0]
            self.is_enter_mode_animation = unpack("h", file.read(2))[0]
        self.variant_count = unpack("H", file.read(2))[0]
        self.timing_variants = [
            TimingVariant().read(file, animation_timing_version)
            for _ in range(self.variant_count)
        ]
        return self

    def write(self, file: BinaryIO, animation_timing_version: int) -> "AnimationTiming":
        """Writes the AnimationTiming to the buffer"""
        file.write(pack("i", self.animation_type))
        if animation_timing_version in [2, 3, 4]:
            file.write(pack("i", self.animation_tag_id))
            file.write(pack("h", self.is_enter_mode_animation))
        file.write(pack("H", self.variant_count))
        for variant in self.timing_variants:
            variant.write(file, animation_timing_version)
        return self

    def size(self, animation_timing_version: int) -> int:
        """Returns the size of the AnimationTiming"""
        if animation_timing_version in [2, 3, 4]:
            return 12 + sum(
                variant.size(animation_timing_version)
                for variant in self.timing_variants
            )
        return 6 + sum(
            variant.size(animation_timing_version) for variant in self.timing_variants
        )


@dataclass(eq=False, repr=False)
class StructV3:
    length: int = 1  # Int
    unknown: List[int] = field(default_factory=lambda: [0, 0])  # Ints

    def read(self, file: BinaryIO) -> "StructV3":
        """Reads the StructV3 from the buffer"""
        self.length = unpack("i", file.read(4))[0]
        self.unknown = [unpack("i", file.read(4))[0] for _ in range(2)]
        return self

    def write(self, file: BinaryIO) -> "StructV3":
        """Writes the StructV3 to the buffer"""
        file.write(pack("i", self.length))
        file.write(pack(f"{2}i", *self.unknown))

    def size(self) -> int:
        """Returns the size of the StructV3"""
        return 4 + 8 * self.length


@dataclass(eq=False, repr=False)
class AnimationTimings:
    magic: int = 1650881127  # int
    version: int = 4  # Short. 3 or 4
    # Short. Only used if there are multiple Animations.
    animation_timing_count: int = 0
    animation_timings: List[AnimationTiming] = field(default_factory=list)
    struct_v3: StructV3 = StructV3()

    def read(self, file: BinaryIO) -> "AnimationTimings":
        self.magic = unpack("i", file.read(4))[0]
        self.version = unpack("h", file.read(2))[0]
        self.animation_timing_count = unpack("h", file.read(2))[0]
        self.animation_timings = [
            AnimationTiming().read(file, self.version)
            for _ in range(self.animation_timing_count)
        ]
        self.struct_v3 = StructV3().read(file)
        return self

    def write(self, file: BinaryIO) -> "AnimationTimings":
        """Writes the AnimationTimings to the buffer"""
        file.write(pack("i", self.magic))
        file.write(pack("h", self.version))
        file.write(pack("h", self.animation_timing_count))
        for animation_timing in self.animation_timings:
            animation_timing.write(file, self.version)
        self.struct_v3.write(file)
        return self

    def size(self) -> int:
        """Returns the size of the AnimationTimings"""
        return (
            8
            + sum(
                animation_timing.size(self.version)
                for animation_timing in self.animation_timings
            )
            + self.struct_v3.size()
        )


@dataclass(eq=False, repr=False)
class Variant:
    weight: int = 0  # Byte
    length: int = 0  # Int
    name: str = ""  # CString split into length and name

    def read(self, file: BinaryIO) -> "Variant":
        self.weight = unpack("B", file.read(1))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = file.read(self.length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("B", self.weight))
        file.write(pack("i", self.length))
        file.write(self.name.encode("utf-8"))

    def size(self) -> int:
        return 5 + self.length


@dataclass(eq=False, repr=False)
class Keyframe:
    time: float = 0.0
    keyframe_type: int = 0
    min_falloff: float = 0.0
    max_falloff: float = 0.0
    volume: float = 0.0
    pitch_shift_min: float = 0.0
    pitch_shift_max: float = 0.0
    offset: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # Vector3
    interruptable: int = 0
    uk: Optional[int] = None  # Only if type != 10 and type != 11
    variant_count: int = 0
    variants: List[Variant] = field(default_factory=list)

    def read(self, file: BinaryIO, _type: int) -> "Keyframe":
        (
            self.time,
            self.keyframe_type,
            self.min_falloff,
            self.max_falloff,
            self.volume,
            self.pitch_shift_min,
            self.pitch_shift_max,
        ) = unpack("fifffff", file.read(28))
        self.offset = list(unpack("3f", file.read(12)))
        self.interruptable = unpack("B", file.read(1))[0]

        if _type not in [10, 11]:
            self.uk = unpack("B", file.read(1))[0]

        self.variant_count = unpack("i", file.read(4))[0]
        self.variants = [Variant().read(file) for _ in range(self.variant_count)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack(
                "fifffff",
                self.time,
                self.keyframe_type,
                self.min_falloff,
                self.max_falloff,
                self.volume,
                self.pitch_shift_min,
                self.pitch_shift_max,
            )
        )
        file.write(pack("3f", *self.offset))
        file.write(pack("B", self.interruptable))

        if self.uk is not None:
            file.write(pack("B", self.uk))

        file.write(pack("i", self.variant_count))
        for variant in self.variants:
            variant.write(file)

    def size(self) -> int:
        size = 28 + 12 + 1
        if self.uk is not None:
            size += 1
        size += 4
        for variant in self.variants:
            size += variant.size()
        return size


@dataclass(eq=False, repr=False)
class SkelEff:
    length: int = 0  # Int
    name: str = ""  # CString split into length and name
    keyframe_count: int = 0
    keyframes: List[Keyframe] = field(default_factory=list)

    def read(self, file: BinaryIO, _type: int) -> "SkelEff":
        self.length = unpack("i", file.read(4))[0]
        self.name = file.read(self.length).decode("utf-8").strip("\x00")
        self.keyframe_count = unpack("i", file.read(4))[0]
        self.keyframes = [
            Keyframe().read(file, _type) for _ in range(self.keyframe_count)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("i", self.length))
        file.write(self.name.encode("utf-8"))
        file.write(pack("i", self.keyframe_count))
        for keyframe in self.keyframes:
            keyframe.write(file)

    def size(self) -> int:
        base = 8 + self.length
        for keyframe in self.keyframes:
            base += keyframe.size()
        return base


@dataclass
class SthSound:
    sth_sound_file: int = 0  # byte
    unknown: int = 0  # short
    unknown_list: List[int] = field(
        default_factory=list, metadata={"size": 5}
    )  # 5 ints
    lenght: int = 0  # int
    file_name: str = ""  # CString split into length and name

    def read(self, file: BinaryIO) -> "SthSound":
        self.sth_sound_file = unpack("B", file.read(1))[0]
        self.unknown = unpack("h", file.read(2))[0]
        self.unknown_list = list(unpack("5i", file.read(20)))
        self.lenght = unpack("i", file.read(4))[0]
        self.file_name = file.read(self.lenght).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("B", self.sth_sound_file))
        file.write(pack("h", self.unknown))
        file.write(pack("5i", *self.unknown_list))
        file.write(pack("i", self.lenght))
        file.write(self.file_name.encode("utf-8"))

    def size(self) -> int:
        return 23 + self.lenght


@dataclass(eq=False, repr=False)
class UKS2:
    unknown: int = 0  # short
    unknown_list: List[int] = field(
        default_factory=list, metadata={"size": 5}
    )  # 5 ints
    unknown_2: int = 0  # short
    lenght: int = 0  # short
    sth_sound: List[SthSound] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "UKS2":
        self.unknown = unpack("h", file.read(2))[0]
        self.unknown_list = list(unpack("5i", file.read(20)))
        self.unknown_2 = unpack("h", file.read(2))[0]
        self.lenght = unpack("h", file.read(2))[0]
        self.sth_sound = [SthSound().read(file) for _ in range(self.lenght)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.unknown))
        file.write(pack("5i", *self.unknown_list))
        file.write(pack("h", self.unknown_2))
        file.write(pack("h", self.lenght))
        for sth_sound in self.sth_sound:
            sth_sound.write(file)

    def size(self) -> int:
        return 26 + sum(sth_sound.size() for sth_sound in self.sth_sound)


@dataclass(eq=False, repr=False)
class UKS1:
    unknown: int = 0  # short
    unknown_list: List[int] = field(
        default_factory=list, metadata={"size": 5}
    )  # 5 ints
    unknown_2: int = 0  # short
    length: int = 0  # short
    unknown_structs: List[UKS2] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "UKS1":
        self.unknown = unpack("h", file.read(2))[0]
        self.unknown_list = list(unpack("5i", file.read(20)))
        self.unknown_2 = unpack("h", file.read(2))[0]
        self.length = unpack("h", file.read(2))[0]
        self.unknown_structs = [UKS2().read(file) for _ in range(self.length)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.unknown))
        file.write(pack("5i", *self.unknown_list))
        file.write(pack("h", self.unknown_2))
        file.write(pack("h", self.length))
        for unknown_struct in self.unknown_structs:
            unknown_struct.write(file)

    def size(self) -> int:
        return 26 + sum(
            unknown_struct.size() for unknown_struct in self.unknown_structs
        )


@dataclass(eq=False, repr=False)
class UKS3:
    unknown: int = 0  # short
    unknown_list: List[int] = field(
        default_factory=list, metadata={"size": 5}
    )  # 5 ints
    unknown_2: int = 0  # short
    lenght: int = 0  # short
    sth_sound: List[SthSound] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "UKS3":
        self.unknown = unpack("h", file.read(2))[0]
        self.unknown_list = list(unpack("5i", file.read(20)))
        self.unknown_2 = unpack("h", file.read(2))[0]
        self.lenght = unpack("h", file.read(2))[0]
        self.sth_sound = [SthSound().read(file) for _ in range(self.lenght)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.unknown))
        file.write(pack("5i", *self.unknown_list))
        file.write(pack("h", self.unknown_2))
        file.write(pack("h", self.lenght))
        for sth_sound in self.sth_sound:
            sth_sound.write(file)

    def size(self) -> int:
        return 26 + sum(sth_sound.size() for sth_sound in self.sth_sound)


@dataclass(eq=False, repr=False)
class EffectSet:
    type: int = 12  # Short
    checksum_length: int = 0  # Int
    checksum: str = ""  # CString split into length and name
    length: int = 0
    skel_effekts: List[SkelEff] = field(default_factory=list)
    unknown: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0]
    )  # Vector3
    length4: int = 0  # short
    unknown4: List[UKS3] = field(default_factory=list)
    lenght3: int = 0  # short
    unknown3: List[UKS1] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "EffectSet":
        self.type = unpack("h", file.read(2))[0]
        self.checksum_length = unpack("i", file.read(4))[0]
        self.checksum = file.read(self.checksum_length).decode("utf-8").strip("\x00")

        if self.type in [10, 11, 12]:
            if self.type == 10:
                self.unknown = list(unpack("5f", file.read(20)))

            self.length = unpack("i", file.read(4))[0]
            self.skel_effekts = [
                SkelEff().read(file, self.type) for _ in range(self.length)
            ]
            self.length4 = unpack("h", file.read(2))[0]
            self.unknown4 = [UKS3().read(file) for _ in range(self.length4)]
            self.lenght3 = unpack("h", file.read(2))[0]
            self.unknown3 = [UKS1().read(file) for _ in range(self.lenght3)]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.type))
        file.write(pack("i", self.checksum_length))
        file.write(self.checksum.encode("utf-8"))
        if self.type in [10, 11, 12]:
            if self.type == 10:
                file.write(pack("5f", *self.unknown))
            file.write(pack("i", self.length))
            for skel_eff in self.skel_effekts:
                skel_eff.write(file)
            file.write(pack("h", self.length4))
            for unknown in self.unknown4:
                unknown.write(file)
            file.write(pack("h", self.lenght3))
            for unknown in self.unknown3:
                unknown.write(file)

    def size(self) -> int:
        base = 6 + self.checksum_length
        if self.type in [10, 11, 12]:
            if self.type == 10:
                base += 20
            base += 4
            for skel_eff in self.skel_effekts:
                base += skel_eff.size()
            base += 2
            for unknown in self.unknown4:
                base += unknown.size()
            base += 2
            for unknown in self.unknown3:
                base += unknown.size()
        return base


@dataclass(eq=False, repr=False)
class SMeshState:
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

    def write(self, file: BinaryIO) -> "SMeshState":
        pass


@dataclass(eq=False, repr=False)
class DestructionState:
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


@dataclass(eq=False, repr=False)
class StateBasedMeshSet:
    uk: int = 1  # Short # Depends on the Type i guess
    uk2: int = 11  # Int # Depends on the type i guess
    num_mesh_states: int = 1  # Int Always needs one
    mesh_states: List[SMeshState] = field(default_factory=list)
    num_destruction_states: int = 1  # Int
    destruction_states: List[DestructionState] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "StateBasedMeshSet":
        """Reads the StateBasedMeshSet from the buffer"""
        self.uk = unpack("h", file.read(2))[0]
        self.uk2 = unpack("i", file.read(4))[0]
        self.num_mesh_states = unpack("i", file.read(4))[0]
        self.mesh_states = [
            SMeshState().read(file) for _ in range(self.num_mesh_states)
        ]
        self.num_destruction_states = unpack("i", file.read(4))[0]
        self.destruction_states = [
            DestructionState().read(file) for _ in range(self.num_destruction_states)
        ]
        return self

    def write(self, file: BinaryIO) -> "StateBasedMeshSet":
        pass


@dataclass(eq=False, repr=False)
class MeshGridModule:
    uk: int = 0  # Short
    has_mesh_set: int = 0  # Byte
    state_based_mesh_set: StateBasedMeshSet = None

    def read(self, file: BinaryIO) -> "MeshGridModule":
        """Reads the MeshGridModule from the buffer"""
        self.uk = unpack("h", file.read(2))[0]
        self.has_mesh_set = unpack("B", file.read(1))[0]
        if self.has_mesh_set:
            self.state_based_mesh_set = StateBasedMeshSet().read(file)
        return self

    def write(self, file: BinaryIO) -> "MeshGridModule":
        pass


@dataclass(eq=False, repr=False)
class MeshSetGrid:
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
    uk_string0_length: int = 0  # Int
    uk_string0: str = ""  # String
    uk_string1_length: int = 0  # Int
    uk_string1: str = ""  # String
    module_distance: float = 2  # Float
    is_center_pivoted: int = 0  # Byte
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
        self.uk_string0_length = unpack("i", file.read(4))[0]
        self.uk_string0 = (
            unpack(
                f"{self.uk_string0_length}s",
                file.read(calcsize(f"{self.uk_string0_length}s")),
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

    def write(self, file: BinaryIO) -> "MeshSetGrid":
        pass


@dataclass(eq=False, repr=False)
class PlacementShape:
    size: int = 660 # Only for debugging purpose the whole size of the test file's class
    
    def read(self, file: BinaryIO) -> "PlacementShape":
        """Reads the PlacementShape from the buffer"""
        file.read(self.size)  # Just read the whole class for now
        return self

@dataclass(eq=False, repr=False)
class DRS:
    operator: object = None
    context: object = None
    keywords: object = None
    magic: int = -981667554
    number_of_models: int = 1
    node_information_offset: int = 20
    node_hierarchy_offset: int = 20
    data_offset: int = 20  # 20 = Default Data Offset
    node_count: int = 1
    nodes: List[Node] = field(default_factory=lambda: [RootNode()])
    node_informations: List[Union[NodeInformation, RootNodeInformation]] = field(
        default_factory=lambda: [RootNodeInformation()]
    )
    animation_set_node: Node = None
    cdsp_mesh_file_node: Node = None
    cgeo_mesh_node: Node = None
    csk_skin_info_node: Node = None
    csk_skeleton_node: Node = None
    animation_timings_node: Node = None
    cdsp_joint_map_node: Node = None
    cgeo_obb_tree_node: Node = None
    drw_resource_meta_node: Node = None
    cgeo_primitive_container_node: Node = None
    collision_shape_node: Node = None
    effect_set_node: Node = None
    cdrw_locator_list_node: Node = None
    animation_set: AnimationSet = None
    cdsp_mesh_file: CDspMeshFile = None
    cgeo_mesh: CGeoMesh = None
    csk_skin_info: CSkSkinInfo = None
    csk_skeleton: CSkSkeleton = None
    cdsp_joint_map: CDspJointMap = None
    cgeo_obb_tree: CGeoOBBTree = None
    drw_resource_meta: DrwResourceMeta = None
    cgeo_primitive_container: CGeoPrimitiveContainer = None
    collision_shape: CollisionShape = None
    cdrw_locator_list: CDrwLocatorList = None
    effect_set: EffectSet = None
    animation_timings: AnimationTimings = None
    placement_shape_node: Node = None
    placement_shape: PlacementShape = None
    model_type: str = None

    def __post_init__(self):
        self.nodes = [RootNode()]
        if self.model_type is not None:
            model_struct = InformationIndices[self.model_type]
            # Prefill the node_informations with the RootNodeInformation and empty NodeInformations
            self.node_informations = [
                RootNodeInformation(node_information_count=len(model_struct))
            ]
            self.node_count = len(model_struct) + 1
            for _ in range(len(model_struct)):
                self.node_informations.append(NodeInformation())

            for index, (node_name, info_index) in enumerate(model_struct.items()):
                node = Node(info_index, node_name)
                self.nodes.append(node)
                node_info = NodeInformation(identifier=index + 1, node_name=node_name)
                # Fix for missing node_size as size is 0 and not Note for CGeoPrimitiveContainer
                if node_name == "CGeoPrimitiveContainer":
                    node_info.node_size = 0
                self.node_informations[info_index] = node_info

    def push_node_infos(self, class_name: str, data_object: object):
        # Get the right node from self.node_informations
        for node_info in self.node_informations:
            if node_info.node_name == class_name:
                node_info.data_object = data_object
                node_info.node_size = data_object.size()
                break

    def update_offsets(self):
        for node_name in WriteOrder[self.model_type]:
            # get the right node_infortmation froms self.node_informations
            node_information = next(
                (
                    node_info
                    for node_info in self.node_informations
                    if node_info.node_name == node_name
                ),
                None,
            )
            node_information.offset = self.data_offset
            self.data_offset += node_information.node_size

    def read_v2(self, file_name: str) -> "DRS":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiiI", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        # Read Node Informations
        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)
        
        node_information_map = {
            -475734043: "animation_set_node",
            -1900395636: "cdsp_mesh_file_node",
            100449016: "cgeo_mesh_node",
            -761174227: "csk_skin_info_node",
            -2110567991: "csk_skeleton_node",
            -1403092629: "animation_timings_node",
            -1340635850: "cdsp_joint_map_node",
            -933519637: "cgeo_obb_tree_node",
            -183033339: "drw_resource_meta_node",
            1396683476: "cgeo_primitive_container_node",
            268607026: "collision_shape_node",
            688490554: "effect_set_node",
            735146985: "cdrw_locator_list_node",
            -196433635: "gd_locator_list_node",  # Not yet implemented
            -1424862619: "fx_master_node",  # Not yet implemented
            -1746446328: "placement_shape_node",  # Not yet implemented
            -1058658465: "unknown_node",  # Not yet implemented
            -1967569622: "unknown_node_2",  # Not yet implemented
        }
        
        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            # Check if the node_info is in the node_information_map
            if node_info.magic in node_information_map:
                setattr(self, node_information_map[node_info.magic], node_info)
                self.node_informations.append(node_info)
            else:
                raise TypeError(f"Unknown Node: {node_info.magic}")
        
        # Read Node Hierarchy
        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)
        
        node_map = {
            "AnimationSet": "animation_set_node",
            "CDspMeshFile": "cdsp_mesh_file_node",
            "CGeoMesh": "cgeo_mesh_node",
            "CSkSkinInfo": "csk_skin_info_node",
            "CSkSkeleton": "csk_skeleton_node",
            "AnimationTimings": "animation_timings_node",
            "CDspJointMap": "cdsp_joint_map_node",
            "CGeoOBBTree": "cgeo_obb_tree_node",
            "DrwResourceMeta": "drw_resource_meta_node",
            "CGeoPrimitiveContainer": "cgeo_primitive_container_node",
            "collisionShape": "collision_shape_node",
            "EffectSet": "effect_set_node",
            "CDrwLocatorList": "cdrw_locator_list_node",
            "CGdLocatorList": "gd_locator_list_node",  # Not yet implemented
            "FxMaster": "fx_master_node",  # Not yet implemented
            "placementShape": "placement_shape_node",  # Not yet implemented
        }
        
        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            self.nodes.append(node)
            
        # Read Nodes, not by their Type but simply by their offset and size from node_informations
        for node in self.nodes:
            if not hasattr(node, "info_index"):
                # Root Node has no info_index
                continue

            node_info = self.node_informations[node.info_index]
            if node_info is None:
                raise TypeError(f"Node {node.name} not found")
            
            if node_info.node_size == 0:
                if node_info.linked_node > 0:
                    print(f"- Node {node.name} has size 0, but is linked to node index {node_info.linked_node}. Trying to read linked node.")
                    right_node_info = self.node_informations[node_info.linked_node]
                    print(f"- Linked node is {right_node_info.node_name} with size {right_node_info.node_size} at offset {right_node_info.offset}.")
                    node_info.offset = right_node_info.offset
                    node_info.node_size = right_node_info.node_size
                else:
                    print(f"- Node {node.name} has size 0, skipping...")
                    continue

            # node_info_type = node_information_map.get(node_info.magic, None)
            reader.seek(node_info.offset)
            node_magic = reader.read(4)
            node_magic_int = unpack("i", node_magic)[0]
            # Find note Type by ClassMagic str:int
            node_type = None
            for node_name, nodemagic in ClassMagic.items():
                if node_magic_int == int(nodemagic):
                    node_type = node_name
                    break
            
            internal_node_name = node_map.get(node.name, None)
            if internal_node_name is None:
                print(f"- Node {node.name} not found in node_map, skipping...")
                continue
            
            internal_node_name = internal_node_name.replace("_node", "")
            reader.seek(node_info.offset)
            if node.name != node_type:
                if node_type is None:
                    print(f"- Unknown Node Type with Magic {node_magic_int} at offset {node_info.offset}. Trying to parse as {node.name}.")
                    # Try to parse the Node as the expected type
                    try:
                        setattr(self, internal_node_name, globals()[node.name]().read(reader))
                        print("-- Successfully read node:", node.name)
                    except Exception as e:
                        print(f"-- Failed to read node {node.name} at offset {node_info.offset}. Error: {e}. Trying as CGeoMesh.")
                        reader.seek(node_info.offset)
                        try:
                            setattr(self, internal_node_name, globals()["CGeoMesh"]().read(reader))
                            print("--- Successfully read node as CGeoMesh.")
                        except Exception as e2:
                            print(f"--- Failed to read node as CGeoMesh. Error: {e2}. Skipping node.")
                else:
                    print(f"- Node type mismatch for node {node.name} at offset {node_info.offset}. Expected {node.name}, but got {node_type}. Parsing as {node_type}.")
                    # Parse the Node with the correct type
                    setattr(self, internal_node_name, globals()[node_type]().read(reader))
                    print("-- Successfully read fixed node:", node.name + " as " + node_type)
            else:
                # Parse the Node normally
                setattr(self, internal_node_name, globals()[node.name]().read(reader))
                print("- Successfully read node:", node.name)
                
        reader.close()
        return self


    def read(self, file_name: str) -> "DRS":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiiI", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        # Read Node Informations
        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)

        node_information_map = {
            -475734043: "animation_set_node",
            -1900395636: "cdsp_mesh_file_node",
            100449016: "cgeo_mesh_node",
            -761174227: "csk_skin_info_node",
            -2110567991: "csk_skeleton_node",
            -1403092629: "animation_timings_node",
            -1340635850: "cdsp_joint_map_node",
            -933519637: "cgeo_obb_tree_node",
            -183033339: "drw_resource_meta_node",
            1396683476: "cgeo_primitive_container_node",
            268607026: "collision_shape_node",
            688490554: "effect_set_node",
            735146985: "cdrw_locator_list_node",
            -196433635: "gd_locator_list_node",  # Not yet implemented
            -1424862619: "fx_master_node",  # Not yet implemented
            -1746446328: "placement_shape_node",  # Not yet implemented
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            # Check if the node_info is in the node_information_map
            if node_info.magic in node_information_map:
                setattr(self, node_information_map[node_info.magic], node_info)
                self.node_informations.append(node_info)
            else:
                raise TypeError(f"Unknown Node: {node_info.magic}")

        # Read Node Hierarchy
        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)

        node_map = {
            "AnimationSet": "animation_set_node",
            "CDspMeshFile": "cdsp_mesh_file_node",
            "CGeoMesh": "cgeo_mesh_node",
            "CSkSkinInfo": "csk_skin_info_node",
            "CSkSkeleton": "csk_skeleton_node",
            "AnimationTimings": "animation_timings_node",
            "CDspJointMap": "cdsp_joint_map_node",
            "CGeoOBBTree": "cgeo_obb_tree_node",
            "DrwResourceMeta": "drw_resource_meta_node",
            "CGeoPrimitiveContainer": "cgeo_primitive_container_node",
            "collisionShape": "collision_shape_node",
            "EffectSet": "effect_set_node",
            "CDrwLocatorList": "cdrw_locator_list_node",
            "CGdLocatorList": "gd_locator_list_node",  # Not yet implemented
            "FxMaster": "fx_master_node",  # Not yet implemented
            "placementShape": "placement_shape_node",  # Not yet implemented
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            # Check if the node is in the node_map
            if node.name in node_map:
                # collisionShape is a special case, as its first letter is lowercase
                val = node_map[node.name]
                if val == "collisionShape":
                    val = "CollisionShape"
                if val == "placementShape":
                    val = "PlacementShape"
                setattr(self, val, node)
                self.nodes.append(node)
            else:
                raise TypeError(f"Unknown Node: {node.name}")

        for node in self.nodes:
            if not hasattr(node, "info_index"):
                # Root Node has no info_index
                continue

            node_info = self.node_informations[node.info_index]
            if node_info is None:
                raise TypeError(f"Node {node.name} not found")

            reader.seek(node_info.offset)
            node_name = node_map.get(node.name, None).replace("_node", "")
            if node_map is None:
                raise TypeError(f"Node {node.name} not found in node_map")
            # CollisionShape is a special case, as its first letter is lowercase
            val = node.name
            if val == "collisionShape":
                val = "CollisionShape"
            if val == "placementShape":
                val = "PlacementShape"

            setattr(self, node_name, globals()[val]().read(reader))

        reader.close()
        return self

    def save(self, file_name: str):
        writer = FileWriter(file_name)

        for node_info in self.node_informations:
            self.node_information_offset += node_info.node_size
        self.node_hierarchy_offset = (
            self.node_information_offset + 32 + (self.node_count - 1) * 32
        )
        writer.write(
            pack(
                "iiiiI",
                self.magic,
                self.number_of_models,
                self.node_information_offset,
                self.node_hierarchy_offset,
                self.node_count,
            )
        )

        # Write Data Packets (in correct Order)
        for node_name in WriteOrder[self.model_type]:
            # get the right node from self.node_informations
            node_information = next(
                (
                    node_info
                    for node_info in self.node_informations
                    if node_info.node_name == node_name
                ),
                None,
            )

            if node_name != "CGeoPrimitiveContainer":
                node_information.data_object.write(writer)

        # Write Node Informations
        for node_info in self.node_informations:
            node_info.write(writer)

        # Write Node Hierarchy
        for node in self.nodes:
            node.write(writer)

        writer.close()


@dataclass(eq=False, repr=False)
class BMS:
    magic: int = -981667554
    number_of_models: int = 1
    node_information_offset: int = -1
    node_hierarchy_offset: int = -1
    node_count: int = 1
    root_node: RootNode = RootNode()
    node_informations: List[NodeInformation] = field(
        default_factory=lambda: [RootNodeInformation()]
    )
    nodes: List[Node] = field(default_factory=lambda: [RootNode()])
    state_based_mesh_set_node: NodeInformation = None
    state_based_mesh_set: StateBasedMeshSet = None
    animation_set: AnimationSet = None  # Fake Object

    def read(self, file_name: str) -> "BMS":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiii", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)

        node_information_map = {
            120902304: "state_based_mesh_set_node",
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            setattr(self, node_information_map.get(node_info.magic, ""), node_info)

        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)

        reader.seek(self.node_hierarchy_offset)
        node_map = {
            "StateBasedMeshSet": "state_based_mesh_set_node",
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            setattr(self, node_map.get(node.name, ""), node)

        for key, value in node_map.items():
            # remove _node from the value
            node_info: NodeInformation = getattr(self, value, None)
            index = value.replace("_node", "")
            if node_info is not None:
                reader.seek(node_info.offset)
                setattr(self, index, globals()[key]().read(reader))

        reader.close()
        return self


@dataclass(eq=False, repr=False)
class BMG:
    operator: object = None
    context: object = None
    keywords: object = None
    magic: int = -981667554
    number_of_models: int = 1
    node_information_offset: int = 20
    node_hierarchy_offset: int = 20
    data_offset: int = 20  # 20 = Default Data Offset
    node_count: int = 1
    nodes: List[Node] = field(default_factory=lambda: [RootNode()])
    node_informations: List[Union[NodeInformation, RootNodeInformation]] = field(
        default_factory=lambda: [RootNodeInformation()]
    )
    animation_set_node: Node = None
    animation_timings_node: Node = None
    cgeo_primitive_container_node: Node = None
    collision_shape_node: Node = None
    effect_set_node: Node = None
    animation_set: AnimationSet = None
    mesh_set_grid_node: Node = None
    cgeo_primitive_container: CGeoPrimitiveContainer = None
    collision_shape: CollisionShape = None
    effect_set: EffectSet = None
    animation_timings: AnimationTimings = None
    mesh_set_grid: MeshSetGrid = None
    model_type: str = None

    def read(self, file_name: str) -> "BMG":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiiI", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        # Read Node Informations
        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)

        node_information_map = {
            154295579: "mesh_set_grid_node",
            -475734043: "animation_set_node",
            -1403092629: "animation_timings_node",
            1396683476: "cgeo_primitive_container_node",
            268607026: "collision_shape_node",
            688490554: "effect_set_node",
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            # Check if the node_info is in the node_information_map
            if node_info.magic in node_information_map:
                setattr(self, node_information_map[node_info.magic], node_info)
                self.node_informations.append(node_info)
            else:
                raise TypeError(f"Unknown Node: {node_info.magic}")

        # Read Node Hierarchy
        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)

        node_map = {
            "AnimationSet": "animation_set_node",
            "AnimationTimings": "animation_timings_node",
            "CGeoPrimitiveContainer": "cgeo_primitive_container_node",
            "collisionShape": "collision_shape_node",
            "EffectSet": "effect_set_node",
            "MeshSetGrid": "mesh_set_grid_node",
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            # Check if the node is in the node_map
            if node.name in node_map:
                # collisionShape is a special case, as its first letter is lowercase
                val = node_map[node.name]
                if val == "collisionShape":
                    val = "CollisionShape"
                setattr(self, val, node)
                self.nodes.append(node)
            else:
                raise TypeError(f"Unknown Node: {node.name}")

        for node in self.nodes:
            if not hasattr(node, "info_index"):
                # Root Node has no info_index
                continue

            node_info = self.node_informations[node.info_index]
            if node_info is None:
                raise TypeError(f"Node {node.name} not found")

            reader.seek(node_info.offset)
            node_name = node_map.get(node.name, None).replace("_node", "")
            if node_map is None:
                raise TypeError(f"Node {node.name} not found in node_map")
            # CollisionShape is a special case, as its first letter is lowercase
            val = node.name
            if val == "collisionShape":
                val = "CollisionShape"

            setattr(self, node_name, globals()[val]().read(reader))

        reader.close()
        return self
