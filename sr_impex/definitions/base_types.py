from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List, Union
from mathutils import Vector, Matrix

from sr_impex.definitions.enums import MagicValues


class ExportError(RuntimeError):
    """Unified export error that bubbles up to the operator/UI."""



@contextmanager
def error_context(ctx: str):
    """Attach human-readable context to any exception and re-raise as ExportError."""
    try:
        yield
    except ExportError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ExportError(f"{ctx}: {exc}") from exc


def _wrap_write_method(cls):
    """Wrap cls.write(self, file, ...) so any exception becomes ExportError with class/name context."""
    original = getattr(cls, "write", None)
    if not callable(original):
        return

    def wrapped(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        except ExportError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            ident = None
            for attr in ("name", "id", "mesh_name", "material_name"):
                if hasattr(self, attr):
                    ident = getattr(self, attr)
                    if ident:
                        break
            extra = f" name={ident}" if ident else ""
            raise ExportError(f"{cls.__name__}.write failed{extra}: {exc}") from exc

    setattr(cls, "write", wrapped)


def _auto_wrap_all_write_methods(module_globals: dict):
    """Find all classes defined in this module and wrap their write methods."""
    for _name, obj in list(module_globals.items()):
        if isinstance(obj, type) and hasattr(obj, "write") and callable(getattr(obj, "write")):
            _wrap_write_method(obj)


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
        for i in range(4):
            file.write(pack("4f", *self.matrix[i]))

    def size(self) -> int:
        return 64


@dataclass(eq=True, repr=False)
class Matrix3x3:
    matrix: tuple = ((0, 0, 0), (0, 0, 0), (0, 0, 0))
    math_matrix: Matrix = field(default_factory=lambda: Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0))))

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
    data_object: None = None
    node_size: int = 0
    node_name: str = ""

    def read(self, file: BinaryIO) -> "RootNodeInformation":
        self.zeroes = unpack("16b", file.read(16))
        self.neg_one, self.one, self.node_information_count, self.zero = unpack("iiii", file.read(16))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("16biiii", *self.zeroes, self.neg_one, self.one, self.node_information_count, self.zero))

    def size(self) -> int:
        return 32

    def update_offset(self, _: int) -> None:  # pragma: no cover - compatibility hook
        pass


@dataclass(eq=False, repr=False)
class NodeInformation:
    magic: int = field(init=False)
    identifier: int = -1
    offset: int = -1
    node_size: int = field(init=False)
    spacer: List[int] = field(default_factory=lambda: [0] * 16)
    node_name: str = ""

    def __post_init__(self):
        self.magic = MagicValues.get(self.node_name) if self.node_name else 0

    def read(self, file: BinaryIO) -> "NodeInformation":
        self.magic, self.identifier, self.offset, self.node_size = unpack("iiii", file.read(16))
        self.spacer = unpack("16b", file.read(16))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("iiii", self.magic, self.identifier, self.offset, self.node_size))
        file.write(pack("16b", *self.spacer))

    def update_offset(self, offset: int) -> None:
        self.offset = offset

    def size(self) -> int:
        return calcsize("iiii16b")


@dataclass(eq=False, repr=False)
class BaseContainer:
    """Base class for DRS, BMG, FXB file formats sharing common packaging structure."""

    operator: object = None
    context: object = None
    keywords: object = None
    magic: int = -981667554
    number_of_models: int = 1
    node_information_offset: int = 20
    node_hierarchy_offset: int = 20
    data_offset: int = 20
    node_count: int = 1
    nodes: List[Union[RootNode, Node]] = field(default_factory=lambda: [RootNode()])
    node_informations: List[Union[NodeInformation, RootNodeInformation]] = field(default_factory=lambda: [RootNodeInformation()])
    model_type: str = None
