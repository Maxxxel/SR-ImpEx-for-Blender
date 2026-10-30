"""
Animation class definitions for DRS files.

This module contains classes related to animation data structures:
- AnimationSetVariant: Variant of an animation set with weight and file reference
- ModeAnimationKey: Animation key for different modes with variants
- AnimationMarker: Single animation marker with time and position
- AnimationMarkerSet: Set of animation markers
- LegacyAnimationMarker: Version-1 marker class, time and direction
- LegacyAnimationMarkerGroup: Version-1 animation/CRC marker group
- AnimationSet: Complete animation set with modes, markers, and IK atlases
- Timing: Animation timing information with cast and resolve times
- TimingVariant: Variant of timing with weight
- AnimationTiming: Complete animation timing with variants
- StructV3: Unknown structure version 3
- AnimationTimings: Container for animation timings
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import BinaryIO, List, Union

from mathutils import Vector

from sr_impex.definitions.base_types import Vector3
from sr_impex.definitions.resource_definitions import IKAtlas
from sr_impex.definitions.enums import AnimationType


def _read_text(owner, file: BinaryIO, field_name: str, length: int) -> str:
    if length < 0:
        raise ValueError("Negative animation string length")
    raw = file.read(length)
    if len(raw) != length:
        raise EOFError("Truncated animation string")
    value = raw.decode("utf-8").strip("\x00")
    setattr(owner, "_original_" + field_name, (value, raw))
    return value


def _text_bytes(owner, field_name: str) -> bytes:
    value = getattr(owner, field_name)
    original = getattr(owner, "_original_" + field_name, None)
    return original[1] if original is not None and original[0] == value else value.encode("utf-8")


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
        self.file = _read_text(self, file, "file", self.length)

        if self.version >= 4:
            self.start = unpack("f", file.read(4))[0]
            self.end = unpack("f", file.read(4))[0]
        if self.version >= 5:
            self.allows_ik = unpack("B", file.read(1))[0]
        if self.version >= 7:
            self.force_no_blend = unpack("B", file.read(1))[0]

        return self

    def write(self, file: BinaryIO):
        """Writes the AnimationSetVariant to the buffer"""
        raw = _text_bytes(self, "file")
        self.length = len(raw)
        file.write(pack("i", self.version))
        file.write(pack("i", self.weight))
        file.write(pack("i", self.length))
        file.write(raw)
        if self.version >= 4:
            file.write(pack("ff", self.start, self.end))
        if self.version >= 5:
            file.write(pack("B", self.allows_ik))
        if self.version >= 7:
            file.write(pack("B", self.force_no_blend))

    def size(self) -> int:
        """Returns the size of the AnimationSetVariant"""
        base = 12 + len(_text_bytes(self, "file"))
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
    unknown: int = 2  # Saved key-value count
    unknown2: Union[List[int], int] = 3  # First value type; v1 has an opaque payload instead
    vis_job: int = 0
    unknown3: int = 3  # Second value type in v6; 3 denotes a 16-bit value
    special_mode: int = 0  # SpecialMode
    variant_count: int = 1
    animation_set_variants: List[AnimationSetVariant] = field(default_factory=list)

    @property
    def key_value_count(self) -> int:
        return self.unknown

    @key_value_count.setter
    def key_value_count(self, value: int) -> None:
        self.unknown = value

    @property
    def first_value_type(self):
        return self.unknown2

    @first_value_type.setter
    def first_value_type(self, value) -> None:
        self.unknown2 = value

    @property
    def second_value_type(self) -> int:
        return self.unknown3

    @second_value_type.setter
    def second_value_type(self, value: int) -> None:
        self.unknown3 = value

    def read(self, file: BinaryIO, uk: int) -> "ModeAnimationKey":
        """Reads the ModeAnimationKey from the buffer"""
        if uk != 2:
            self.type = unpack("i", file.read(4))[0]
        else:
            self.type = 2
        self.length = unpack("i", file.read(4))[0]
        if self.type not in (1, 2, 3, 4, 5, 6):
            raise ValueError(f"Unsupported ModeAnimationKey version: {self.type}")
        self.file = _read_text(self, file, "file", self.length)
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

    def write(self, file: BinaryIO):
        """Writes the ModeAnimationKey to the buffer"""
        raw = _text_bytes(self, "file")
        self.length = len(raw)
        self.variant_count = len(self.animation_set_variants)
        file.write(pack("i", self.type))
        file.write(pack("i", self.length))
        file.write(raw)
        file.write(pack("i", self.unknown))
        if self.type == 1:
            if not isinstance(self.unknown2, list):
                raise TypeError("ModeAnimationKey.type==1 expects unknown2 as list")
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

    def size(self) -> int:
        """Returns the size of the ModeAnimationKey"""
        base = 12 + len(_text_bytes(self, "file"))
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

    is_spawn_animation: int = 0  # Marker class; compatibility name, not a bool
    time: float = 0.0  # Normalized clip fraction in the timing generation path
    direction: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))
    position: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))

    def read(self, file: BinaryIO) -> "AnimationMarker":
        """Reads the AnimationMarker from the buffer"""
        self.is_spawn_animation = unpack("i", file.read(4))[0]  # 4 bytes
        self.time = unpack("f", file.read(4))[0]  # 4 bytes
        self.direction = Vector3().read(file)  # 12 bytes
        self.position = Vector3().read(file)  # 12 bytes
        return self

    def write(self, file: BinaryIO) :
        """Writes the AnimationMarker to the buffer"""
        file.write(pack("if", self.is_spawn_animation, self.time))
        self.direction.write(file)
        self.position.write(file)

    def size(self) -> int:
        """Returns the size of the AnimationMarker"""
        return 32


@dataclass(eq=False, repr=False)
class AnimationMarkerSet:
    """AnimationMarkerSet"""

    anim_id: int = 0  # Animation/job selector in SAnimIDFile
    length: int = 0
    name: str = ""
    animation_marker_id: int = 0  # uint32 animation CRC component of SAnimIDFile
    marker_count: int = 1
    animation_markers: List[AnimationMarker] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "AnimationMarkerSet":
        """Reads the AnimationMarkerSet from the buffer"""
        self.anim_id = unpack("i", file.read(4))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = _read_text(self, file, "name", self.length)
        self.animation_marker_id = unpack("I", file.read(4))[0]
        self.marker_count = unpack("i", file.read(4))[0]
        self.animation_markers = [
            AnimationMarker().read(file) for _ in range(self.marker_count)
        ]
        return self

    def write(self, file: BinaryIO):
        """Writes the AnimationMarkerSet to the buffer"""
        raw = _text_bytes(self, "name")
        self.length = len(raw)
        self.marker_count = len(self.animation_markers)
        file.write(pack("ii", self.anim_id, self.length))
        file.write(raw)
        file.write(pack("Ii", self.animation_marker_id, self.marker_count))
        for animation_marker in self.animation_markers:
            animation_marker.write(file)

    def size(self) -> int:
        """Returns the size of the AnimationMarkerSet"""
        return (
            16
            + len(_text_bytes(self, "name"))
            + sum(
                animation_marker.size() for animation_marker in self.animation_markers
            )
        )


@dataclass(eq=False, repr=False)
class LegacyAnimationMarker:
    """Marker-stream v1 record: class, normalized time and three direction floats.

    Raw words retain exact source float bits; ``UnknownStruct2`` is an alias.
    """

    unknown_ints: List[int] = field(default_factory=lambda: [0] * 5)

    @property
    def marker_class(self) -> int:
        return self.unknown_ints[0] & 0xffffffff

    @marker_class.setter
    def marker_class(self, value: int) -> None:
        self.unknown_ints[0] = unpack("<i", pack("<I", value))[0]

    @property
    def time(self) -> float:
        return unpack("<f", pack("<i", self.unknown_ints[1]))[0]

    @time.setter
    def time(self, value: float) -> None:
        self.unknown_ints[1] = unpack("<i", pack("<f", value))[0]

    @property
    def direction(self) -> tuple[float, float, float]:
        return unpack("<3f", pack("<3i", *self.unknown_ints[2:5]))

    @direction.setter
    def direction(self, value) -> None:
        self.unknown_ints[2:5] = unpack("<3i", pack("<3f", *value))

    def read(self, file: BinaryIO) -> "UnknownStruct2":
        """Reads the UnknownStruct2 from the buffer"""
        self.unknown_ints = [unpack("i", file.read(4))[0] for _ in range(5)]
        return self

    def write(self, file: BinaryIO):
        """Writes the legacy marker while retaining its source word patterns."""
        if len(self.unknown_ints) != 5:
            raise ValueError("A legacy animation marker requires five raw words")
        for unknown_int in self.unknown_ints:
            file.write(pack("i", unknown_int))

    def size(self) -> int:
        """Returns the size of the UnknownStruct2"""
        return 20


UnknownStruct2 = LegacyAnimationMarker


@dataclass(eq=False, repr=False)
class LegacyAnimationMarkerGroup:
    """Marker-stream v1 group; ``UnknownStruct`` remains a compatibility alias."""

    unknown: int = 0
    length: int = 0
    name: str = ""
    unknown2: int = 0
    unknown3: int = 0
    unknown_structs: List[UnknownStruct2] = field(default_factory=list)

    @property
    def anim_id(self) -> int:
        return self.unknown

    @anim_id.setter
    def anim_id(self, value: int) -> None:
        self.unknown = value

    @property
    def animation_crc(self) -> int:
        return self.unknown2 & 0xffffffff

    @animation_crc.setter
    def animation_crc(self, value: int) -> None:
        self.unknown2 = unpack("<i", pack("<I", value))[0]

    @property
    def animation_markers(self) -> List[LegacyAnimationMarker]:
        return self.unknown_structs

    @animation_markers.setter
    def animation_markers(self, value) -> None:
        self.unknown_structs = list(value)

    def read(self, file: BinaryIO) -> "UnknownStruct":
        """Reads the UnknownStruct from the buffer"""
        self.unknown = unpack("i", file.read(4))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = _read_text(self, file, "name", self.length)
        self.unknown2 = unpack("i", file.read(4))[0]
        self.unknown3 = unpack("i", file.read(4))[0]
        self.unknown_structs = [
            UnknownStruct2().read(file) for _ in range(self.unknown3)
        ]
        return self

    def write(self, file: BinaryIO):
        """Writes the UnknownStruct to the buffer"""
        raw = _text_bytes(self, "name")
        self.length = len(raw)
        self.unknown3 = len(self.unknown_structs)
        file.write(pack("ii", self.unknown, self.length))
        file.write(raw)
        file.write(pack("ii", self.unknown2, self.unknown3))
        for unknown_struct2 in self.unknown_structs:
            unknown_struct2.write(file)

    def size(self) -> int:
        """Returns the size of the UnknownStruct"""
        return (
            16
            + len(_text_bytes(self, "name"))
            + sum(unknown_struct2.size() for unknown_struct2 in self.unknown_structs)
        )


UnknownStruct = LegacyAnimationMarkerGroup


@dataclass(eq=False, repr=False)
class AnimationSet:
    """AnimationSet"""

    length: int = 11
    magic: str = "Battleforge"
    version: int = 6
    default_run_speed: float = 4.8  # Default values observed in source files
    default_walk_speed: float = 2.3
    revision: int = 0  # 0 For Animated Objects
    # Runtime unit-motion attributes; field names retained for compatibility.
    mode_change_type: int = 0  # PartialModeChange boolean; compatibility name
    hovering_ground: int = 0
    fly_bank_scale: float = 2.0  # CVisAnimationSet constructor default
    fly_accel_scale: float = 0.4  # CVisAnimationSet constructor default
    fly_hit_scale: float = 1  # Changes for flying units
    allign_to_terrain: int = 0
    mode_animation_key_count: int = 0  # How many different animations are there?
    mode_animation_keys: List[ModeAnimationKey] = field(default_factory=list)
    has_atlas: int = 2  # 1 or 2
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

    @property
    def partial_mode_change(self) -> int:
        return self.mode_change_type

    @partial_mode_change.setter
    def partial_mode_change(self, value: int) -> None:
        self.mode_change_type = value

    @property
    def joint_transform_scales(self) -> List[tuple[int, float, float]]:
        """IK tail entries in file order: joint index, transScale, rotScale."""
        return [(self.uk_ints[i], unpack("f", pack("i", self.uk_ints[i + 1]))[0],
                 unpack("f", pack("i", self.uk_ints[i + 2]))[0])
                for i in range(0, len(self.uk_ints), 3)]

    @property
    def ik_atlas_version(self) -> int:
        return self.has_atlas

    @ik_atlas_version.setter
    def ik_atlas_version(self, value: int) -> None:
        self.has_atlas = value

    @property
    def ik_transform_count(self) -> int:
        return self.uk_len

    @property
    def marker_set_version(self) -> int:
        return self.subversion

    @marker_set_version.setter
    def marker_set_version(self, value: int) -> None:
        self.subversion = value

    @property
    def legacy_marker_sets(self) -> List[LegacyAnimationMarkerGroup]:
        return self.unknown_structs

    @legacy_marker_sets.setter
    def legacy_marker_sets(self, value) -> None:
        self.unknown_structs = list(value)

    def read(self, file: BinaryIO) -> "AnimationSet":
        """Reads the AnimationSet from the buffer"""
        self.length = unpack("i", file.read(4))[0]
        self.magic = _read_text(self, file, "magic", self.length)
        self.version = unpack("i", file.read(4))[0]
        if self.version not in (1, 2, 3, 4, 5, 6):
            raise ValueError(f"Unsupported AnimationSet version: {self.version}")
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

        if self.version != 2:
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
                # Each CSkIKAtlas::SJointTransform is a joint index and two
                # float32 words (transScale, rotScale), not a single integer.
                words = 3 * self.uk_len
                self.uk_ints = list(unpack(f"{words}i", file.read(4 * words)))

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

    def write(self, file: BinaryIO):
        """Writes the AnimationSet to the buffer"""
        if self.version not in (1, 2, 3, 4, 5, 6):
            raise ValueError(f"Unsupported AnimationSet version: {self.version}")
        raw = _text_bytes(self, "magic")
        self.length = len(raw)
        self.mode_animation_key_count = len(self.mode_animation_keys)
        self.atlas_count = len(self.ik_atlases)
        self.animation_marker_count = len(self.animation_marker_sets)
        self.unknown = len(self.unknown_structs)
        file.write(pack("i", self.length))
        file.write(raw)
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

        if self.version != 2:
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
                if len(self.uk_ints) % 3:
                    raise ValueError("IK transform entries require joint/rotation/translation word triples")
                self.uk_len = len(self.uk_ints) // 3
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


    def size(self) -> int:
        """Returns the size of the AnimationSet"""
        base = (20 if self.version == 2 else 24) + len(_text_bytes(self, "magic"))

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
    cast_ms: int = 0  # Event/action offset in milliseconds (legacy name)
    resolve_ms: int = 0  # Total animation duration in traced paths (legacy name)
    direction: Vector = Vector((0.0, 0.0, 1.0))  # Vector
    animation_marker_id: int = 0  # Animation file-base CRC, not an arbitrary marker ID

    @property
    def animation_crc(self) -> int:
        return self.animation_marker_id

    @animation_crc.setter
    def animation_crc(self, value: int) -> None:
        self.animation_marker_id = value

    def read(self, file: BinaryIO) -> "Timing":
        """Reads the Timing from the buffer"""
        self.cast_ms = unpack("i", file.read(4))[0]
        self.resolve_ms = unpack("i", file.read(4))[0]
        self.direction = Vector(unpack("fff", file.read(12)))
        self.animation_marker_id = unpack("I", file.read(4))[0]
        return self

    def write(self, file: BinaryIO):
        """Writes the Timing to the buffer"""
        file.write(pack("i", self.cast_ms))
        file.write(pack("i", self.resolve_ms))
        file.write(pack("fff", *self.direction))
        file.write(pack("I", self.animation_marker_id))

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
        self.timing_count = len(self.timings)
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
    is_enter_mode_animation: int = 0  # uint16 mode selector; legacy name, not bool
    # Short. The number of Animations for this Type/TagID combination.
    variant_count: int = 0
    timing_variants: List[TimingVariant] = field(default_factory=list)

    @property
    def mode_change_type(self) -> int:
        return self.is_enter_mode_animation

    @mode_change_type.setter
    def mode_change_type(self, value: int) -> None:
        self.is_enter_mode_animation = value

    def read(self, file: BinaryIO, animation_timing_version: int) -> "AnimationTiming":
        """Reads the AnimationTiming from the buffer"""
        self.animation_type = unpack("i", file.read(4))[0]
        if animation_timing_version in [2, 3, 4]:
            self.animation_tag_id = unpack("i", file.read(4))[0]
            self.is_enter_mode_animation = unpack("H", file.read(2))[0]
        self.variant_count = unpack("H", file.read(2))[0]
        self.timing_variants = [
            TimingVariant().read(file, animation_timing_version)
            for _ in range(self.variant_count)
        ]
        return self

    def write(self, file: BinaryIO, animation_timing_version: int) -> "AnimationTiming":
        """Writes the AnimationTiming to the buffer"""
        self.variant_count = len(self.timing_variants)
        file.write(pack("i", self.animation_type))
        if animation_timing_version in [2, 3, 4]:
            file.write(pack("i", self.animation_tag_id))
            file.write(pack("H", self.is_enter_mode_animation))
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
    """Version-3/4 special attributes; legacy raw-word interface retained.

    Each pair in ``unknown`` is an int32 attribute ID and the raw int32 bits of
    its float32 value. Keeping raw words preserves unknown IDs and float bits.
    """
    length: int = 1  # Int
    unknown: List[int] = field(default_factory=lambda: [0, 0])  # Ints

    def read(self, file: BinaryIO) -> "StructV3":
        """Reads the StructV3 from the buffer"""
        self.length = unpack("I", file.read(4))[0]
        self.unknown = [unpack("i", file.read(4))[0] for _ in range(2 * self.length)]
        return self

    @property
    def attributes(self) -> List[tuple[int, float]]:
        """Decoded ID/value pairs; the engine currently accepts attribute ID 0."""
        return [(self.unknown[i], unpack("f", pack("i", self.unknown[i + 1]))[0])
                for i in range(0, len(self.unknown), 2)]

    def write(self, file: BinaryIO):
        """Writes the StructV3 to the buffer"""
        if len(self.unknown) % 2:
            raise ValueError("AnimationTimings attributes require ID/value word pairs")
        self.length = len(self.unknown) // 2
        file.write(pack("I", self.length))
        file.write(pack(f"{len(self.unknown)}i", *self.unknown))

    def size(self) -> int:
        """Returns the size of the StructV3"""
        if len(self.unknown) % 2:
            raise ValueError("AnimationTimings attributes require ID/value word pairs")
        return 4 + 4 * len(self.unknown)


@dataclass(eq=False, repr=False)
class AnimationTimings:
    magic: int = 1650881127  # int
    version: int = 4  # Short. 3 or 4
    # Short. Only used if there are multiple Animations.
    animation_timing_count: int = 0
    animation_timings: List[AnimationTiming] = field(default_factory=list)
    struct_v3: StructV3 = field(default_factory=StructV3)

    def read(self, file: BinaryIO) -> "AnimationTimings":
        self.magic = unpack("i", file.read(4))[0]
        self.version = unpack("h", file.read(2))[0]
        if self.version not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported AnimationTimings version: {self.version}")
        self.animation_timing_count = unpack("H", file.read(2))[0]
        self.animation_timings = [
            AnimationTiming().read(file, self.version)
            for _ in range(self.animation_timing_count)
        ]
        self.struct_v3 = StructV3().read(file) if self.version >= 3 else StructV3(0, [])
        return self

    def write(self, file: BinaryIO):
        """Writes the AnimationTimings to the buffer"""
        if self.version not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported AnimationTimings version: {self.version}")
        self.animation_timing_count = len(self.animation_timings)
        file.write(pack("i", self.magic))
        file.write(pack("h", self.version))
        file.write(pack("H", self.animation_timing_count))
        for animation_timing in self.animation_timings:
            animation_timing.write(file, self.version)
        if self.version >= 3:
            self.struct_v3.write(file)

    def size(self) -> int:
        """Returns the size of the AnimationTimings"""
        return (
            8
            + sum(
                animation_timing.size(self.version)
                for animation_timing in self.animation_timings
            )
            + (self.struct_v3.size() if self.version >= 3 else 0)
        )
