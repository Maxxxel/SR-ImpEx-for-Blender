from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack
from typing import BinaryIO, List, Optional, Tuple, Union

from sr_impex.definitions.base_types import Vector3


@dataclass(eq=False, repr=False)
class FloatStaticTrack:
    value: float = 0.0

    def read(self, file: BinaryIO) -> "FloatStaticTrack":
        self.value = unpack("f", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("f", self.value))

    def size(self) -> int:
        return 4


@dataclass(eq=False, repr=False)
class Vector3StaticTrack:
    value: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "Vector3StaticTrack":
        self.value = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.value.write(file)

    def size(self) -> int:
        return 12


@dataclass(eq=False, repr=False)
class StringStaticTrack:
    length: int = 0
    value: str = ""

    def read(self, file: BinaryIO) -> "StringStaticTrack":
        self.length = unpack("I", file.read(4))[0]
        self.value = file.read(self.length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.length))
        file.write(self.value.encode("utf-8"))

    def size(self) -> int:
        return 4 + self.length


@dataclass(eq=False, repr=False)
class Vector3OtherStaticTrack:
    value: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "Vector3OtherStaticTrack":
        self.value = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        self.value.write(file)

    def size(self) -> int:
        return 12


@dataclass(eq=False, repr=False)
class Static:
    header: int = 4166493980
    version: int = 1
    track_type: int = 0
    data_type_header: int = 0
    data: Union[FloatStaticTrack, Vector3StaticTrack, StringStaticTrack, Vector3OtherStaticTrack, None] = None

    def read(self, file: BinaryIO) -> "Static":
        (self.header, self.version, self.track_type, self.data_type_header) = unpack("IIII", file.read(16))
        assert self.header == 4166493980, f"Invalid Static header: {self.header}"
        assert self.version == 1, f"Unsupported Static version: {self.version}"
        if self.data_type_header == 0xF857A7F7:
            self.data = FloatStaticTrack().read(file)
        elif self.data_type_header == 0xF857A77C:
            self.data = Vector3StaticTrack().read(file)
        elif self.data_type_header == 0xF857A757:
            self.data = StringStaticTrack().read(file)
        elif self.data_type_header == 0xF857A747:
            self.data = Vector3OtherStaticTrack().read(file)
        else:
            raise ValueError(f"Unknown data type header: {self.data_type_header}")
        return self


@dataclass(eq=False, repr=False)
class TrackKeyframe:
    frame: float = 0.0
    data: Union[float, Vector3] = 0.0

    def size(self) -> int:
        if isinstance(self.data, float):
            return 8
        if isinstance(self.data, Vector3):
            return 16
        raise ValueError("Invalid data type for TrackKeyframe")


@dataclass(eq=False, repr=False)
class FloatKeyframe(TrackKeyframe):
    header: int = 0xF87EF70A
    start_control_point_header: int = 0xF87EFC95
    control_point_header: int = 0xF87EF7C9
    frame: float = 0.0
    data: float = 0.0

    def read(self, file: BinaryIO) -> "FloatKeyframe":
        (self.header,) = unpack("I", file.read(4))
        self.frame = unpack("f", file.read(4))[0]
        self.data = unpack("f", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("f", self.frame))
        file.write(pack("f", self.data))

    def size(self) -> int:
        return 12


@dataclass(eq=False, repr=False)
class Vector3Keyframe(TrackKeyframe):
    header: int = 0xF87E7EC7
    start_control_point_header: int = 0xF87E7C95
    control_point_header: int = 0xF87E7EC9
    frame: float = 0.0
    data: Vector3 = field(default_factory=Vector3)

    def read(self, file: BinaryIO) -> "Vector3Keyframe":
        (self.header,) = unpack("I", file.read(4))
        self.frame = unpack("f", file.read(4))[0]
        self.data = Vector3().read(file)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("f", self.frame))
        self.data.write(file)

    def size(self) -> int:
        return 20


def _read_entries_and_control_points(file: BinaryIO) -> Tuple[List[TrackKeyframe], List[TrackKeyframe]]:
    entries: List[TrackKeyframe] = []
    control_points: List[TrackKeyframe] = []
    current_header = unpack("I", file.peek(4))[0]

    if current_header == FloatKeyframe().header:
        while current_header == FloatKeyframe().header:
            keyframe = FloatKeyframe().read(file)
            entries.append(keyframe)
            current_header = unpack("I", file.peek(4))[0]

        control_data_header = unpack("I", file.read(4))[0]

        if control_data_header == FloatKeyframe().start_control_point_header:
            current_header = unpack("I", file.peek(4))[0]
            while current_header == FloatKeyframe().control_point_header:
                keyframe = FloatKeyframe().read(file)
                control_points.append(keyframe)
                current_header = unpack("I", file.peek(4))[0]

            end_control_point_header = unpack("I", file.read(4))[0]
            assert end_control_point_header == 0xF876AC3E, f"Invalid end control point header: {end_control_point_header}"
    elif current_header == Vector3Keyframe().header:
        while current_header == Vector3Keyframe().header:
            keyframe = Vector3Keyframe().read(file)
            entries.append(keyframe)
            current_header = unpack("I", file.peek(4))[0]

        control_data_header = unpack("I", file.read(4))[0]

        if control_data_header == Vector3Keyframe().start_control_point_header:
            current_header = unpack("I", file.peek(4))[0]
            while current_header == Vector3Keyframe().control_point_header:
                keyframe = Vector3Keyframe().read(file)
                control_points.append(keyframe)
                current_header = unpack("I", file.peek(4))[0]

            end_control_point_header = unpack("I", file.read(4))[0]
            assert end_control_point_header == 0xF876AC3E, f"Invalid end control point header: {end_control_point_header}"
    else:
        raise ValueError(f"Unknown keyframe header: {current_header}")

    return entries, control_points


@dataclass(eq=False, repr=False)
class Track:
    header: int = 0xF876AC30
    start_track_header: int = 0xF8575767
    version: int = 4
    track_type: int = 0
    length: float = 0.0
    track_dim: int = 0
    track_mode: int = 0
    interpolation_type: int = 0
    evaluation_type: int = 0
    entries: List[TrackKeyframe] = field(default_factory=list)
    control_points: List[TrackKeyframe] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "Track":
        (self.header, self.version, self.track_type) = unpack("III", file.read(12))
        assert self.header == 0xF876AC30, f"Invalid Track header: {self.header}"
        assert self.version == 4, f"Unsupported Track version: {self.version}"
        self.length = unpack("f", file.read(4))[0]
        (self.track_dim, self.track_mode, self.interpolation_type, self.evaluation_type) = unpack("IIII", file.read(16))
        self.entries, self.control_points = _read_entries_and_control_points(file)
        if len(self.entries) == 0:
            raise ValueError("Track must have at least one entry")
        return self


@dataclass(eq=False, repr=False)
class NodeLink:
    header: int = 0xF82D712E
    version: int = 0
    parent_length: int = 0
    parent: str = ""
    slot_length: int = 0
    slot: str = ""
    destination_slot_length: int = 0
    destination_slot: str = ""
    world: int = 0
    node: int = 0
    floor: int = 0
    aim: int = 0
    span: int = 0
    locator: int = 0

    def read(self, file: BinaryIO) -> "NodeLink":
        self.header = unpack("I", file.read(4))[0]
        assert self.header == 0xF82D712E, f"Invalid NodeLink header: {self.header}"
        version = unpack("I", file.read(4))[0]
        assert version in [1, 2, 3], f"Unsupported NodeLink version: {version}"
        parent_length = unpack("I", file.read(4))[0]
        self.parent = file.read(parent_length).decode("utf-8").strip("\x00")
        slot_length = unpack("I", file.read(4))[0]
        self.slot = file.read(slot_length).decode("utf-8").strip("\x00")
        destination_slot_length = unpack("I", file.read(4))[0]
        self.destination_slot = file.read(destination_slot_length).decode("utf-8").strip("\x00")
        (self.world, self.node, self.floor, self.aim, self.span) = unpack("IIIII", file.read(20))
        if version > 2:
            self.locator = unpack("I", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.parent_length))
        file.write(self.parent.encode("utf-8"))
        file.write(pack("I", self.slot_length))
        file.write(self.slot.encode("utf-8"))
        file.write(pack("I", self.destination_slot_length))
        file.write(self.destination_slot.encode("utf-8"))
        file.write(pack("IIIII", self.world, self.node, self.floor, self.aim, self.span))
        if self.version > 2:
            file.write(pack("I", self.locator))

    def size(self) -> int:
        size = 4 + 4 + 4 + self.parent_length + 4 + self.slot_length + 4 + self.destination_slot_length + 20
        if self.version > 2:
            size += 4
        return size


@dataclass(eq=False, repr=False)
class Element:
    end_element_children_header = 0xF8E2DE2D
    node_link: NodeLink = field(default_factory=NodeLink)
    start_element_header = 0xF8E7EAA7
    version: int = 1
    name_length: int = 0
    name: str = ""
    element_type_header: int = 0
    end_element_header = 0xF8E75E2D
    static_tracks: List[Static] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    start_element_children_header = 0xF876E2D0
    parent: Optional["Element"] = field(default=None)
    children: List["Element"] = field(default_factory=list)

    def read(self, file: BinaryIO, parent: "Element", ignores: List[int], depth: int) -> "Element":
        self.node_link = NodeLink().read(file)
        start_element_header = unpack("I", file.read(4))[0]
        assert start_element_header == self.start_element_header, f"Invalid start element header: {start_element_header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Element version: {self.version}"
        self.name_length = unpack("I", file.read(4))[0]
        raw = file.read(self.name_length)
        try:
            self.name = raw.decode("utf-8").strip("\x00")
        except UnicodeDecodeError:
            self.name = raw.decode("latin-1").strip("\x00")
        self.element_type_header = unpack("I", file.peek(4))[0]
        header = self.element_type_header

        match header:
            case header if header in _element_type_map:
                element_class = _element_type_map[header]
                element_instance = element_class().read(file)
                setattr(self, element_class.__name__.lower(), element_instance)
            case _:
                raise ValueError(f"Unknown element type header: {self.element_type_header}")

        end_element_header = unpack("I", file.read(4))[0]
        assert end_element_header == self.end_element_header, f"Invalid end element header: {end_element_header}"

        track_counter = 0
        current_header = unpack("I", file.peek(4))[0]
        while current_header == Track().start_track_header:
            _ = unpack("I", file.read(4))[0]
            track_counter += 1
            current_header = unpack("I", file.peek(4))[0]

        if track_counter != 2 and self.element_type_header not in [0xF8A23E54, 0xF8534D4D]:
            raise ValueError(
                f"Element must have exactly 2 tracks, found {track_counter}. Element name: {self.name}, Type: {hex(self.element_type_header)}"
            )

        self.static_tracks = _read_static_tracks(file)
        self.tracks = _read_tracks(file)

        self.start_element_children_header = unpack("I", file.read(4))[0]
        assert self.start_element_children_header == 0xF876E2D0, f"Invalid start_element_children_header: {self.start_element_children_header}"

        if self.element_type_header == 0xF8EFFE37:
            ignores[depth] += 1

        parent.children.append(self)
        self.parent = parent
        next_parent: Optional[Element] = self
        depth += 1

        current_header = unpack("I", file.peek(4))[0]
        while current_header == Element.end_element_children_header:
            self.end_element_children_header = unpack("I", file.read(4))[0]
            if ignores[depth] > 0:
                ignores[depth] -= 1
            else:
                if next_parent is not None:
                    next_parent = next_parent.parent
                else:
                    if depth != 0:
                        raise ValueError("Element parent is None but depth is not zero")
                depth -= 1
            current_header = unpack("I", file.peek(4))[0]

        if depth == -1:
            return self

        return Element().read(file, next_parent, ignores, depth)


@dataclass(eq=False, repr=False)
class Light(Element):
    header: int = 0xF8716470
    range: int = 0
    radinace: float = 0.0

    def read(self, file: BinaryIO) -> "Light":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8716470, f"Invalid Light header: {self.header}"
        self.range = unpack("I", file.read(4))[0]
        self.radinace = unpack("f", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.range))
        file.write(pack("f", self.radinace))

    def size(self) -> int:
        return 12


@dataclass(eq=False, repr=False)
class StaticDecal(Element):
    header: int = 0xF85DECA7
    version: int = 1
    color_texture_length: int = 0
    color_texture: str = ""
    normal_texture_length: int = 0
    normal_texture: str = ""

    def read(self, file: BinaryIO) -> "StaticDecal":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF85DECA7, f"Invalid StaticDecal header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version in [1, 2], f"Unsupported StaticDecal version: {self.version}"
        self.color_texture_length = unpack("I", file.read(4))[0]
        self.color_texture = file.read(self.color_texture_length).decode("utf-8").strip("\x00")
        if self.version == 2:
            self.normal_texture_length = unpack("I", file.read(4))[0]
            self.normal_texture = file.read(self.normal_texture_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.color_texture_length))
        file.write(self.color_texture.encode("utf-8"))
        if self.version == 2:
            file.write(pack("I", self.normal_texture_length))
            file.write(self.normal_texture.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.color_texture_length + (8 + self.normal_texture_length if self.version == 2 else 0)


@dataclass(eq=False, repr=False)
class Sound(Element):
    header: int = 0xF850C5D0
    version: int = 1
    sound_file_length: int = 0
    sound_file: str = ""

    def read(self, file: BinaryIO) -> "Sound":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF850C5D0, f"Invalid Sound header: {self.header}"
        self.version = unpack("I", file.read(4))[0]
        assert self.version == 1, f"Unsupported Sound version: {self.version}"
        self.sound_file_length = unpack("I", file.read(4))[0]
        self.sound_file = file.read(self.sound_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.sound_file_length))
        file.write(self.sound_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.sound_file_length


@dataclass(eq=False, repr=False)
class Billboard(Element):
    header: int = 0xF88177BD
    version: int = 1
    texture_one_length: int = 0
    texture_one: str = ""
    texture_two_length: int = 0
    texture_two: str = ""

    def read(self, file: BinaryIO) -> "Billboard":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF88177BD, f"Invalid Billboard header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version in [1, 2], f"Unsupported Billboard version: {self.version}"
        self.texture_one_length = unpack("I", file.read(4))[0]
        self.texture_one = file.read(self.texture_one_length).decode("utf-8").strip("\x00")
        if self.version == 2:
            self.texture_two_length = unpack("I", file.read(4))[0]
            self.texture_two = file.read(self.texture_two_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.texture_one_length))
        file.write(self.texture_one.encode("utf-8"))
        if self.version == 2:
            file.write(pack("I", self.texture_two_length))
            file.write(self.texture_two.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.texture_one_length + (8 + self.texture_two_length if self.version == 2 else 0)


@dataclass(eq=False, repr=False)
class Emitter(Element):
    header: int = 0xF8E31777
    version: int = 1
    emitter_file_length: int = 0
    emitter_file: str = ""
    particle_count: int = 0

    def read(self, file: BinaryIO) -> "Emitter":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8E31777, f"Invalid Emitter header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Emitter version: {self.version}"
        self.emitter_file_length = unpack("I", file.read(4))[0]
        self.emitter_file = file.read(self.emitter_file_length).decode("utf-8").strip("\x00")
        self.particle_count = unpack("I", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.emitter_file_length))
        file.write(self.emitter_file.encode("utf-8"))
        file.write(pack("I", self.particle_count))

    def size(self) -> int:
        return 16 + self.emitter_file_length


@dataclass(eq=False, repr=False)
class CameraShake(Element):
    header: int = 0xF8C5AAEE
    version: int = 1

    def read(self, file: BinaryIO) -> "CameraShake":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8C5AAEE, f"Invalid CameraShake header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported CameraShake version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


@dataclass(eq=False, repr=False)
class EffectMesh(Element):
    header: int = 0xF83E5400
    version: int = 1
    mesh_file_length: int = 0
    mesh_file: str = ""

    def read(self, file: BinaryIO) -> "EffectMesh":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF83E5400, f"Invalid EffectMesh header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported EffectMesh version: {self.version}"
        self.mesh_file_length = unpack("I", file.read(4))[0]
        self.mesh_file = file.read(self.mesh_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.mesh_file_length))
        file.write(self.mesh_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.mesh_file_length


@dataclass(eq=False, repr=False)
class Effect(Element):
    header: int = 0xF8EFFE37
    version: int = 1
    effect_file_length: int = 0
    effect_file: str = ""
    embedded: int = 0
    length: float = 0.0

    def read(self, file: BinaryIO) -> "Effect":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8EFFE37, f"Invalid Effect header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Effect version: {self.version}"
        self.effect_file_length = unpack("I", file.read(4))[0]
        self.effect_file = file.read(self.effect_file_length).decode("utf-8").strip("\x00")
        self.embedded = unpack("I", file.read(4))[0]
        self.length = unpack("f", file.read(4))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.effect_file_length))
        file.write(self.effect_file.encode("utf-8"))
        file.write(pack("I", self.embedded))
        file.write(pack("f", self.length))

    def size(self) -> int:
        return 20 + self.effect_file_length


@dataclass(eq=False, repr=False)
class Trail(Element):
    header: int = 0xF878A175
    version: int = 1
    trail_file_length: int = 0
    trail_file: str = ""

    def read(self, file: BinaryIO) -> "Trail":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF878A175, f"Invalid Trail header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Trail version: {self.version}"
        self.trail_file_length = unpack("I", file.read(4))[0]
        self.trail_file = file.read(self.trail_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.trail_file_length))
        file.write(self.trail_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.trail_file_length


@dataclass(eq=False, repr=False)
class PhysicGroup(Element):
    header: int = 0xF8504752
    version: int = 1

    def read(self, file: BinaryIO) -> "PhysicGroup":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8504752, f"Invalid PhysicGroup header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported PhysicGroup version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


@dataclass(eq=False, repr=False)
class Physic(Element):
    header: int = 0xF8504859
    version: int = 1
    physic_file_length: int = 0
    physic_file: str = ""

    def read(self, file: BinaryIO) -> "Physic":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8504859, f"Invalid Physic header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Physic version: {self.version}"
        self.physic_file_length = unpack("I", file.read(4))[0]
        self.physic_file = file.read(self.physic_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.physic_file_length))
        file.write(self.physic_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.physic_file_length


@dataclass(eq=False, repr=False)
class Decal(Element):
    header: int = 0xF8DECA70
    version: int = 1
    decal_file_length: int = 0
    decal_file: str = ""

    def read(self, file: BinaryIO) -> "Decal":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8DECA70, f"Invalid Decal header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Decal version: {self.version}"
        self.decal_file_length = unpack("I", file.read(4))[0]
        self.decal_file = file.read(self.decal_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.decal_file_length))
        file.write(self.decal_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.decal_file_length


@dataclass(eq=False, repr=False)
class Force(Element):
    header: int = 0xF8466F72
    version: int = 1

    def read(self, file: BinaryIO) -> "Force":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8466F72, f"Invalid Force header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported Force version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


@dataclass(eq=False, repr=False)
class ForcePoint(Element):
    header: int = 0xF8504650
    version: int = 1

    def read(self, file: BinaryIO) -> "ForcePoint":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8504650, f"Invalid ForcePoint header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported ForcePoint version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


@dataclass(eq=False, repr=False)
class AnimatedMesh(Element):
    header: int = 0xF8A23E54
    version: int = 1
    mesh_file_length: int = 0
    mesh_file: str = ""
    animation_file_length: int = 0
    animation_file: str = ""

    def read(self, file: BinaryIO) -> "AnimatedMesh":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8A23E54, f"Invalid AnimatedMesh header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported AnimatedMesh version: {self.version}"
        self.mesh_file_length = unpack("I", file.read(4))[0]
        self.mesh_file = file.read(self.mesh_file_length).decode("utf-8").strip("\x00")
        self.animation_file_length = unpack("I", file.read(4))[0]
        self.animation_file = file.read(self.animation_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.mesh_file_length))
        file.write(self.mesh_file.encode("utf-8"))
        file.write(pack("I", self.animation_file_length))
        file.write(self.animation_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.mesh_file_length + 4 + self.animation_file_length


@dataclass(eq=False, repr=False)
class AnimatedMeshMaterial(Element):
    header: int = 0xF8534D4D
    version: int = 1
    mesh_material_file_length: int = 0
    mesh_material_file: str = ""

    def read(self, file: BinaryIO) -> "AnimatedMeshMaterial":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8534D4D, f"Invalid AnimatedMeshMaterial header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported AnimatedMeshMaterial version: {self.version}"
        self.mesh_material_file_length = unpack("I", file.read(4))[0]
        self.mesh_material_file = file.read(self.mesh_material_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.mesh_material_file_length))
        file.write(self.mesh_material_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.mesh_material_file_length


@dataclass(eq=False, repr=False)
class WaterDecal(Element):
    header: int = 0xF8ADECA7
    version: int = 1
    decal_file_length: int = 0
    decal_file: str = ""

    def read(self, file: BinaryIO) -> "WaterDecal":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF8ADECA7, f"Invalid WaterDecal header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported WaterDecal version: {self.version}"
        self.decal_file_length = unpack("I", file.read(4))[0]
        self.decal_file = file.read(self.decal_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.decal_file_length))
        file.write(self.decal_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.decal_file_length


@dataclass(eq=False, repr=False)
class SfpSystem(Element):
    header: int = 0xF85F6575
    version: int = 1
    system_file_length: int = 0
    system_file: str = ""

    def read(self, file: BinaryIO) -> "SfpSystem":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF85F6575, f"Invalid SfpSystem header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported SfpSystem version: {self.version}"
        self.system_file_length = unpack("I", file.read(4))[0]
        self.system_file = file.read(self.system_file_length).decode("utf-8").strip("\x00")
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))
        file.write(pack("I", self.system_file_length))
        file.write(self.system_file.encode("utf-8"))

    def size(self) -> int:
        return 12 + self.system_file_length


@dataclass(eq=False, repr=False)
class SfpEmitter(Element):
    header: int = 0xF85F6E31
    version: int = 1

    def read(self, file: BinaryIO) -> "SfpEmitter":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF85F6E31, f"Invalid SfpEmitter header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported SfpEmitter version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


@dataclass(eq=False, repr=False)
class SfpForceField(Element):
    header: int = 0xF85F6FFD
    version: int = 1

    def read(self, file: BinaryIO) -> "SfpForceField":
        (self.header,) = unpack("I", file.read(4))
        assert self.header == 0xF85F6FFD, f"Invalid SfpForceField header: {self.header}"
        (self.version,) = unpack("I", file.read(4))
        assert self.version == 1, f"Unsupported SfpForceField version: {self.version}"
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.header))
        file.write(pack("I", self.version))

    def size(self) -> int:
        return 8


_element_type_map = {
    0xF8716470: Light,
    0xF85DECA7: StaticDecal,
    0xF850C5D0: Sound,
    0xF88177BD: Billboard,
    0xF8E31777: Emitter,
    0xF8C5AAEE: CameraShake,
    0xF83E5400: EffectMesh,
    0xF8EFFE37: Effect,
    0xF878A175: Trail,
    0xF8504752: PhysicGroup,
    0xF8504859: Physic,
    0xF8DECA70: Decal,
    0xF8466F72: Force,
    0xF8504650: ForcePoint,
    0xF8A23E54: AnimatedMesh,
    0xF8534D4D: AnimatedMeshMaterial,
    0xF8ADECA7: WaterDecal,
    0xF85F6575: SfpSystem,
    0xF85F6E31: SfpEmitter,
    0xF85F6FFD: SfpForceField,
}


def _read_static_tracks(file: BinaryIO) -> List[Static]:
    static_tracks: List[Static] = []
    current_header = unpack("I", file.peek(4))[0]
    while current_header == Static().header:
        static_track = Static().read(file)
        static_tracks.append(static_track)
        current_header = unpack("I", file.peek(4))[0]
    return static_tracks


def _read_tracks(file: BinaryIO) -> List[Track]:
    tracks: List[Track] = []
    current_header = unpack("I", file.peek(4))[0]
    while current_header == Track().header:
        track = Track().read(file)
        tracks.append(track)
        current_header = unpack("I", file.peek(4))[0]
    return tracks


@dataclass(eq=False, repr=False, init=True)
class SpecialEffect(Element):
    header: int = 0xF8AEADE7
    length: float = 0.0
    play_length: float = 0.0
    setup_file_name_length: int = 0
    setup_file_name: str = ""
    setup_source_id: int = 0
    setup_target_id: int = 0
    static_tracks: List[Static] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)



def _read_element(file: BinaryIO, parent: Optional[Element] = None) -> Optional[Element]:
    current_header = unpack("I", file.peek(4))[0]
    if current_header != Element.end_element_children_header:
        depth = 1
        ignores = [0] * 16
        return Element().read(file, parent, ignores, depth)
    return None


@dataclass(eq=False, repr=False)
class FxMaster:
    version: int = 1
    magic: int = 4172197351
    revision: int = 2
    name_length: int = 0
    name: str = ""
    length: float = 0.0
    setup_file_name_length: int = 0
    setup_file_name: str = ""
    setup_source_id: int = 0
    setup_target_id: int = 0
    play_length: float = 0.0
    unknown_zero_1: int = 0
    unknown_zero_2: int = 0
    header_one: int = 4166473575
    header_two: int = 4166473575
    static_tracks: List[Static] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    start_element_children_header: int = 0xF876E2D0
    end_element_children_header: int = 0xF8E2DE2D
    special_effect: SpecialEffect = field(default_factory=SpecialEffect)

    def read(self, file: BinaryIO) -> "FxMaster":
        (self.version, self.magic, self.revision) = unpack("III", file.read(12))
        assert self.version == 1, f"Unsupported FxMaster version: {self.version}"
        assert self.magic == 4172197351, f"Invalid FxMaster magic: {self.magic}"
        assert self.revision == 2, f"Unsupported FxMaster revision: {self.revision}"
        self.name_length = unpack("I", file.read(4))[0]
        self.name = file.read(self.name_length).decode("utf-8").strip("\x00")
        self.length = unpack("f", file.read(4))[0]
        self.setup_file_name_length = unpack("I", file.read(4))[0]
        self.setup_file_name = file.read(self.setup_file_name_length).decode("utf-8").strip("\x00")
        (self.setup_source_id, self.setup_target_id) = unpack("ii", file.read(8))
        self.play_length = unpack("f", file.read(4))[0]
        (self.unknown_zero_1, self.unknown_zero_2) = unpack("II", file.read(8))
        assert self.unknown_zero_1 == 0, f"Expected unknown_zero_1 to be 0, got {self.unknown_zero_1}"
        assert self.unknown_zero_2 == 0, f"Expected unknown_zero_2 to be 0, got {self.unknown_zero_2}"
        (self.header_one, self.header_two) = unpack("II", file.read(8))
        assert self.header_one == 4166473575, f"Invalid header_one: {self.header_one}"
        assert self.header_two == 4166473575, f"Invalid header_two: {self.header_two}"
        self.static_tracks = _read_static_tracks(file)
        self.tracks = _read_tracks(file)
        self.start_element_children_header = unpack("I", file.read(4))[0]
        assert self.start_element_children_header == 0xF876E2D0, f"Invalid start_element_children_header: {self.start_element_children_header}"
        self.special_effect = SpecialEffect()
        _read_element(file, self.special_effect)
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("III", self.version, self.magic, self.revision))
        file.write(pack("I", self.name_length))
        file.write(self.name.encode("utf-8"))
        file.write(pack("f", self.length))
        file.write(pack("I", self.setup_file_name_length))
        file.write(self.setup_file_name.encode("utf-8"))
        file.write(pack("ii", self.setup_source_id, self.setup_target_id))
        file.write(pack("f", self.play_length))
        file.write(pack("II", self.unknown_zero_1, self.unknown_zero_2))
        file.write(pack("II", self.header_one, self.header_two))
        for static_track in self.static_tracks:
            static_track.write(file)
        for track in self.tracks:
            track.write(file)
        file.write(pack("I", self.start_element_children_header))
        file.write(pack("I", self.end_element_children_header))
        # Elements currently omitted; implement when writing FX trees is needed.

    def size(self) -> int:
        size = 12 + 4 + self.name_length + 4 + 4 + self.setup_file_name_length + 8 + 4 + 8 + 8 + 4 + 4
        for static_track in self.static_tracks:
            size += static_track.size()
        for track in self.tracks:
            size += track.size()
        return size
