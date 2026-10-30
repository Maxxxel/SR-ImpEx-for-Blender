"""
Effect and sound class definitions for DRS files.

This module contains classes related to effect and sound data structures:
- Variant: Effect variant with weight and name
- Keyframe: Keyframe for skeletal effects with time, type, and variants
- SkelEff: Skeletal effect with keyframes
- SoundHeader: Sound header with volume and falloff parameters
- SoundHeader2: Alternative sound header with different parameter ordering
- SoundFile: Sound file reference with weight and header
- SoundContainer: Container for sound files with header
- AdditionalSoundContainer: Additional sound container with type
- EffectSet: Complete effect set with skeletal effects and sounds
"""
from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack
from typing import BinaryIO, List, Optional


def _read_text(owner, file: BinaryIO, field_name: str, length: int) -> str:
    """Keep source bytes for unchanged length-prefixed text, including NULs."""
    if length < 0:
        raise ValueError("Negative EffectSet string length")
    raw = file.read(length)
    if len(raw) != length:
        raise EOFError("Truncated EffectSet string")
    text = raw.decode("utf-8").strip("\x00")
    setattr(owner, "_original_" + field_name, (text, raw))
    return text


def _text_bytes(owner, field_name: str) -> bytes:
    text = getattr(owner, field_name)
    original = getattr(owner, "_original_" + field_name, None)
    if original is not None and original[0] == text:
        return original[1]
    return text.encode("utf-8")


@dataclass(eq=False, repr=False)
class Variant:
    weight: int = 0  # Byte
    length: int = 0  # Int
    name: str = ""  # CString split into length and name

    def read(self, file: BinaryIO) -> "Variant":
        self.weight = unpack("B", file.read(1))[0]
        self.length = unpack("i", file.read(4))[0]
        self.name = _read_text(self, file, "name", self.length)
        return self

    def write(self, file: BinaryIO) -> None:
        raw = _text_bytes(self, "name")
        self.length = len(raw)
        file.write(pack("B", self.weight))
        file.write(pack("i", self.length))
        file.write(raw)

    def size(self) -> int:
        return 5 + len(_text_bytes(self, "name"))


@dataclass(eq=False, repr=False)
class Keyframe:
    time: float = 0.0 # when to play [0 - 1]
    keyframe_type: int = 0 # 0 audio, 1 world FX, 2 linked FX, 3 persistent FX fade-out, 4 fade-in
    min_falloff: float = 0.0 #
    max_falloff: float = 0.0
    volume: float = 0.0
    pitch_shift_min: float = 0.0
    pitch_shift_max: float = 0.0
    offset: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0]) # Type 1: offset; types 3/4: X is fade seconds
    interruptable: int = 0 # 1 or 0
    condition: Optional[int] = -1  # v12 signed key selector; traced timeline dispatcher does not forward it to mode filtering
    variant_count: int = 0 # needs to be atleast 1
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
            self.condition = unpack("b", file.read(1))[0]
        else:
            self.condition = -1

        self.variant_count = unpack("i", file.read(4))[0]
        self.variants = [Variant().read(file) for _ in range(self.variant_count)]
        return self

    def write(self, file: BinaryIO, _type: int) -> None:
        self.variant_count = len(self.variants)
        # LoadVersion10 increments an 8-bit variant-loop counter (10c176d3).
        if self.variant_count > 255:
            raise ValueError("EffectSet events support at most 255 resource variants in the engine")
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

        if _type not in [10, 11]:
            file.write(pack("b", self.condition))

        file.write(pack("i", self.variant_count))
        for variant in self.variants:
            variant.write(file)

    def size(self, _type: int) -> int:
        size = 28 + 12 + 1
        if _type not in [10, 11]:
            size += 1
        size += 4
        for variant in self.variants:
            size += variant.size()
        return size


@dataclass(eq=False, repr=False)
class SkelEff:
    length: int = 0  # Int
    name: str = "" # needs to link to a SKA animation
    keyframe_count: int = 0 # need to be bigger than 0
    keyframes: List[Keyframe] = field(default_factory=list)

    def read(self, file: BinaryIO, _type: int) -> "SkelEff":
        self.length = unpack("i", file.read(4))[0]
        self.name = _read_text(self, file, "name", self.length)
        self.keyframe_count = unpack("i", file.read(4))[0]
        self.keyframes = [
            Keyframe().read(file, _type) for _ in range(self.keyframe_count)
        ]
        return self

    def write(self, file: BinaryIO, _type: int) -> None:
        raw = _text_bytes(self, "name")
        self.length = len(raw)
        self.keyframe_count = len(self.keyframes)
        file.write(pack("i", self.length))
        file.write(raw)
        file.write(pack("i", self.keyframe_count))
        for keyframe in self.keyframes:
            keyframe.write(file, _type)

    def size(self, _type: int) -> int:
        base = 8 + len(_text_bytes(self, "name"))
        for keyframe in self.keyframes:
            base += keyframe.size(_type)
        return base


@dataclass(eq=False, repr=False)
class SoundHeader:
    is_one: int = 0  # Legacy sound-header stream word; observed 1
    volume: float = 1.0
    min_falloff: float = 1.0
    max_falloff: float = 1.0
    pitch_shift_min: float = 1.0
    pitch_shift_max: float = 1.0

    def read(self, file: BinaryIO) -> "SoundHeader":
        self.is_one = unpack("h", file.read(2))[0]
        (
            self.min_falloff,
            self.max_falloff,
            self.volume,
            self.pitch_shift_min,
            self.pitch_shift_max,
        ) = unpack("fffff", file.read(20))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.is_one))
        file.write(pack("fffff", self.min_falloff, self.max_falloff, self.volume, self.pitch_shift_min, self.pitch_shift_max))

    def size(self) -> int:
        return 2 + 20


@dataclass(eq=False, repr=False)
class SoundHeader2:
    is_one: int = 0  # Legacy sound-file stream word; observed 1
    volume: float = 1.0
    pitch_shift_min: float = 1.0
    pitch_shift_max: float = 1.0
    min_falloff: float = 1.0
    max_falloff: float = 1.0

    def read(self, file: BinaryIO) -> "SoundHeader2":
        self.is_one = unpack("h", file.read(2))[0]
        (
            self.volume,
            self.pitch_shift_min,
            self.pitch_shift_max,
            self.min_falloff,
            self.max_falloff,
        ) = unpack("fffff", file.read(20))
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("h", self.is_one))
        file.write(pack("fffff", self.volume, self.pitch_shift_min, self.pitch_shift_max, self.min_falloff, self.max_falloff))

    def size(self) -> int:
        return 2 + 20


@dataclass(eq=False, repr=False)
class SoundFile:
    weight: int = 0  # byte
    sound_header: SoundHeader2 = field(default_factory=SoundHeader2)
    sound_file_name_length: int = 0  # Int
    sound_file_name: str = ""  # CString

    def read(self, file: BinaryIO) -> "SoundFile":
        self.weight = unpack("B", file.read(1))[0]
        self.sound_header = SoundHeader2().read(file)
        self.sound_file_name_length = unpack("i", file.read(4))[0]
        self.sound_file_name = _read_text(self, file, "sound_file_name", self.sound_file_name_length)
        return self

    def write(self, file: BinaryIO) -> None:
        raw = _text_bytes(self, "sound_file_name")
        self.sound_file_name_length = len(raw)
        file.write(pack("B", self.weight))
        self.sound_header.write(file)
        file.write(pack("i", self.sound_file_name_length))
        file.write(raw)

    def size(self) -> int:
        return 1 + self.sound_header.size() + 4 + len(_text_bytes(self, "sound_file_name"))


@dataclass(eq=False, repr=False)
class SoundContainer:
    sound_header: SoundHeader = field(default_factory=SoundHeader)
    uk_index: int = 0  # uint16: special-event selector, or inner sound-layer threshold
    nbr_sound_variations: int = 0  # short
    sound_files: List[SoundFile] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "SoundContainer":
        self.sound_header = SoundHeader().read(file)
        self.uk_index = unpack("H", file.read(2))[0]
        self.nbr_sound_variations = unpack("H", file.read(2))[0]
        self.sound_files = [
            SoundFile().read(file) for _ in range(self.nbr_sound_variations)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        self.nbr_sound_variations = len(self.sound_files)
        self.sound_header.write(file)
        file.write(pack("H", self.uk_index))
        file.write(pack("H", self.nbr_sound_variations))
        for sound_file in self.sound_files:
            sound_file.write(file)

    def size(self) -> int:
        base = self.sound_header.size() + 2 + 2
        for sound_file in self.sound_files:
            base += sound_file.size()
        return base


@dataclass(eq=False, repr=False)
class AdditionalSoundContainer:
    sound_header: SoundHeader = field(default_factory=SoundHeader)
    sound_type: int = 0  # uint16 outer sound-layer category; separate domain from event types
    nbr_sound_variations: int = 0  # short
    sound_containers: List[SoundContainer] = field(default_factory=list)

    def read(self, file: BinaryIO) -> "AdditionalSoundContainer":
        self.sound_header = SoundHeader().read(file)
        self.sound_type = unpack("H", file.read(2))[0]
        self.nbr_sound_variations = unpack("H", file.read(2))[0]
        self.sound_containers = [
            SoundContainer().read(file) for _ in range(self.nbr_sound_variations)
        ]
        return self

    def write(self, file: BinaryIO) -> None:
        self.nbr_sound_variations = len(self.sound_containers)
        self.sound_header.write(file)
        file.write(pack("H", self.sound_type))
        file.write(pack("H", self.nbr_sound_variations))
        for sound_container in self.sound_containers:
            sound_container.write(file)

    def size(self) -> int:
        base = self.sound_header.size() + 2 + 2
        for sound_container in self.sound_containers:
            base += sound_container.size()
        return base


@dataclass(eq=False, repr=False)
class EffectSet:
    type: int = 12  # Short
    checksum_length: int = 0  # Int
    checksum: str = ""
    length: int = 0
    skel_effekts: List[SkelEff] = field(default_factory=list)
    unknown: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0]
    )  # Version-10-only legacy header, five words; not a Vector3
    number_impact_sounds: int = 0  # short
    impact_sounds: List[SoundContainer] = field(default_factory=list)
    number_additional_sounds: int = 0  # short
    additional_sounds: List[AdditionalSoundContainer] = field(default_factory=list)

    @property
    def version(self) -> int:
        return self.type

    @version.setter
    def version(self, value: int) -> None:
        self.type = value

    @property
    def uuid(self) -> str:
        return self.checksum

    @uuid.setter
    def uuid(self, value: str) -> None:
        self.checksum = value

    @property
    def legacy_v10_header(self) -> List[float]:
        return self.unknown

    @legacy_v10_header.setter
    def legacy_v10_header(self, value) -> None:
        self.unknown = list(value)

    def read(self, file: BinaryIO) -> "EffectSet":
        self.type = unpack("h", file.read(2))[0]
        if self.type not in (10, 11, 12):
            raise ValueError(f"Unsupported EffectSet version: {self.type}; refusing a partial parse")
        self.checksum_length = unpack("i", file.read(4))[0]
        self.checksum = _read_text(self, file, "checksum", self.checksum_length)

        if self.type in [10, 11, 12]:
            if self.type == 10:
                self.unknown = list(unpack("5f", file.read(20)))

            self.length = unpack("i", file.read(4))[0]
            self.skel_effekts = [
                SkelEff().read(file, self.type) for _ in range(self.length)
            ]
            self.number_impact_sounds = unpack("H", file.read(2))[0]
            self.impact_sounds = [
                SoundContainer().read(file) for _ in range(self.number_impact_sounds)
            ]
            self.number_additional_sounds = unpack("H", file.read(2))[0]
            self.additional_sounds = [
                AdditionalSoundContainer().read(file)
                for _ in range(self.number_additional_sounds)
            ]
        return self

    def write(self, file: BinaryIO) -> None:
        if self.type not in (10, 11, 12):
            raise ValueError(f"Unsupported EffectSet version: {self.type}; refusing a partial export")
        raw = _text_bytes(self, "checksum")
        self.checksum_length = len(raw)
        self.length = len(self.skel_effekts)
        self.number_impact_sounds = len(self.impact_sounds)
        self.number_additional_sounds = len(self.additional_sounds)
        file.write(pack("h", self.type))
        file.write(pack("i", self.checksum_length))
        file.write(raw)
        if self.type in [10, 11, 12]:
            if self.type == 10:
                file.write(pack("5f", *self.unknown))
            file.write(pack("i", self.length))
            for skel_eff in self.skel_effekts:
                skel_eff.write(file, self.type)
            file.write(pack("H", self.number_impact_sounds))
            for impact_sound in self.impact_sounds:
                impact_sound.write(file)
            file.write(pack("H", self.number_additional_sounds))
            for additional_sound in self.additional_sounds:
                additional_sound.write(file)

    def size(self) -> int:
        if self.type not in (10, 11, 12):
            raise ValueError(f"Unsupported EffectSet version: {self.type}; refusing a partial size")
        base = 6 + len(_text_bytes(self, "checksum"))
        if self.type in [10, 11, 12]:
            if self.type == 10:
                base += 20
            base += 4
            for skel_eff in self.skel_effekts:
                base += skel_eff.size(self.type)
            base += 2
            for impact_sound in self.impact_sounds:
                base += impact_sound.size()
            base += 2
            for additional_sound in self.additional_sounds:
                base += additional_sound.size()
        return base
