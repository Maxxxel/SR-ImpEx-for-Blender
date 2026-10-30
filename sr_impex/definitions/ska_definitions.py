from typing import BinaryIO
from struct import calcsize, unpack, pack
from dataclasses import dataclass, field


@dataclass(eq=False, repr=False)
class SKAHeader:
    tick: int = 0  # uint
    interval: int = 0  # uint
    type: int = 0  # uint
    bone_id: int = 0  # uint

    def read(self, file: BinaryIO) -> "SKAHeader":
        self.tick = unpack("I", file.read(calcsize("I")))[0]
        self.interval = unpack("I", file.read(calcsize("I")))[0]
        self.type = unpack("I", file.read(calcsize("I")))[0]
        self.bone_id = unpack("I", file.read(calcsize("i")))[0]
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(pack("I", self.tick))
        file.write(pack("I", self.interval))
        file.write(pack("I", self.type))
        file.write(pack("I", self.bone_id))


@dataclass(eq=False, repr=False)
class SKAKeyframe:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0
    tan_x: float = 0.0
    tan_y: float = 0.0
    tan_z: float = 0.0
    tan_w: float = 0.0

    def read(self, file: BinaryIO) -> "SKAKeyframe":
        data = unpack("8f", file.read(calcsize("8f")))
        (
            self.x,
            self.y,
            self.z,
            self.w,
            self.tan_x,
            self.tan_y,
            self.tan_z,
            self.tan_w,
        ) = data
        return self

    def write(self, file: BinaryIO) -> None:
        file.write(
            pack(
                "8f",
                self.x,
                self.y,
                self.z,
                self.w,
                self.tan_x,
                self.tan_y,
                self.tan_z,
                self.tan_w,
            )
        )


@dataclass(eq=False, repr=False)
class SKA:
    magic: int = -1491828473
    type: int = 0  # uint
    header_count: int = 0
    headers: list[SKAHeader] = field(default_factory=list)
    time_count: int = 0
    times: list[float] = field(default_factory=list)
    keyframes: list[SKAKeyframe] = field(default_factory=list)
    duration: float = 0.0
    repeat: int = 0
    stutter_mode: int = 0  # Engine tangent mode: 0 hold, 1 linear, 2 cubic.
    unused1: int = 0  # Version 7 completeness; exact semantics are unresolved.
    unused2: int = (
        0  # for type 7 it seems to be related to the animation duration and frame length
    )
    unused3: int = 0
    unused4: int = 0
    unused5: int = 0
    unused6: list[int] = field(default_factory=list)
    frame_length: int = 0  # Engine NumKeyframes, present in versions 6 and 7.
    zeroes: list[int] = field(default_factory=list)
    target_ids: list[int] = field(default_factory=list)
    text_markers: list[bytes] = field(default_factory=list)  # 8 bytes each: float time, uint16 offset and length.
    annotation_bytes: bytes = b""

    def read(self, file_name: str) -> "SKA":
        with open(file_name, "rb") as reader:
            self.magic = unpack("i", reader.read(calcsize("i")))[0]
            self.type = unpack("I", reader.read(calcsize("I")))[0]
            if self.magic != -1491828473:
                raise ValueError('Invalid SKA magic')
            if self.type not in (6,7):
                raise ValueError('Only SKA versions 6 and 7 are implemented; older versions require a separate converter')
            if self.type == 2:
                # pylint: disable=unused-variable
                unused1 = unpack("i", reader.read(calcsize("i")))[0]
            elif self.type == 3:
                unused1 = unpack("i", reader.read(calcsize("i")))[0]
                # pylint: disable=unused-variable
                unused2 = unpack("i", reader.read(calcsize("i")))[0]
            elif self.type == 4:
                unused1 = unpack("i", reader.read(calcsize("i")))[0]
                unused2 = unpack("i", reader.read(calcsize("i")))[0]
                # pylint: disable=unused-variable
                unused3 = unpack("i", reader.read(calcsize("i")))[0]
                # pylint: disable=unused-variable
                unsued4 = unpack("i", reader.read(calcsize("i")))[0]
            elif self.type == 5:
                unused1 = unpack("i", reader.read(calcsize("i")))[0]
                unused2 = unpack("i", reader.read(calcsize("i")))[0]
                unused3 = unpack("i", reader.read(calcsize("i")))[0]
                unsued4 = unpack("i", reader.read(calcsize("i")))[0]
                # pylint: disable=unused-variable
                unused5 = unpack("i", reader.read(calcsize("i")))[0]
                # pylint: disable=unused-variable
                unused6 = [
                    unpack("i", reader.read(calcsize("i")))[0] for _ in range(unused5)
                ]
            elif self.type == 6 or self.type == 7:
                self.header_count = unpack("i", reader.read(calcsize("i")))[0]
                self.headers = [SKAHeader().read(reader) for _ in range(self.header_count)]
                self.time_count = unpack("i", reader.read(calcsize("i")))[0]
                self.times = [
                    unpack("f", reader.read(calcsize("f")))[0]
                    for _ in range(self.time_count)
                ]
                self.keyframes = [
                    SKAKeyframe().read(reader) for _ in range(self.time_count)
                ]
                self.duration = unpack("f", reader.read(calcsize("f")))[0]
                self.repeat = unpack("i", reader.read(calcsize("i")))[0]
                self.stutter_mode = unpack("i", reader.read(calcsize("i")))[0]
                if self.type == 7:
                    self.unused1 = unpack("i", reader.read(calcsize("i")))[0]
                self.frame_length = unpack("i", reader.read(calcsize("i")))[0]
                target_count = unpack("<I", reader.read(4))[0]
                self.target_ids = [unpack("<I", reader.read(4))[0] for _ in range(target_count)]
                marker_count = unpack("<I", reader.read(4))[0]
                self.text_markers = []
                for _ in range(marker_count):
                    marker = reader.read(8)
                    if len(marker) != 8:
                        raise EOFError("Truncated SKA text marker")
                    self.text_markers.append(marker)
                annotation_length = unpack("<I", reader.read(4))[0]
                self.annotation_bytes = reader.read(annotation_length)
                if len(self.annotation_bytes) != annotation_length:
                    raise EOFError("Truncated SKA annotation text")
                self.zeroes = [0, 0, 0] if not (target_count or marker_count or annotation_length) else []
            else:
                print(f"Unknown SKA type: {self.type}.")
        return self

    def write(self, file_name: str) -> None:
        # Validate before opening a destination: a malformed event must not
        # truncate an artist's previous animation export.
        import math
        if self.type not in (6,7):raise ValueError('Only SKA 6/7 export is implemented')
        self.header_count,self.time_count=len(self.headers),len(self.times)
        if len(self.keyframes)!=self.time_count:raise ValueError('SKA time/keyframe count mismatch')
        if any(h.tick<0 or h.interval<0 or h.tick+h.interval>self.time_count for h in self.headers):
            raise ValueError('SKA header references keyframes outside the arrays')
        if not math.isfinite(self.duration) or self.duration<0:raise ValueError('Invalid SKA duration')
        if any(len(m)!=8 for m in self.text_markers):raise ValueError('SKA text markers must contain exactly 8 bytes')
        for raw in self.text_markers:
            time,offset,length=unpack('<fHH',raw)
            if offset+length>len(self.annotation_bytes):raise ValueError('SKA marker points outside annotation buffer')
        with open(file_name, "wb") as file:
            file.write(pack("i", self.magic))
            file.write(pack("I", self.type))
            if self.type == 2:
                file.write(pack("i", self.unused1))
            elif self.type == 3:
                file.write(pack("i", self.unused1))
                file.write(pack("i", self.unused2))
            elif self.type == 4:
                file.write(pack("i", self.unused1))
                file.write(pack("i", self.unused2))
                file.write(pack("i", self.unused3))
                file.write(pack("i", self.unused4))
            elif self.type == 5:
                file.write(pack("i", self.unused1))
                file.write(pack("i", self.unused2))
                file.write(pack("i", self.unused3))
                file.write(pack("i", self.unused4))
                file.write(pack("i", len(self.unused6)))
                for unused in self.unused6:
                    file.write(pack("i", unused))
            elif self.type == 6 or self.type == 7:
                file.write(pack("i", self.header_count))
                for header in self.headers:
                    header.write(file)
                file.write(pack("i", self.time_count))
                for time in self.times:
                    file.write(pack("f", time))
                for keyframe in self.keyframes:
                    keyframe.write(file)
                file.write(pack("f", self.duration))
                file.write(pack("i", self.repeat))
                file.write(pack("i", self.stutter_mode))
                if self.type == 7:
                    file.write(pack("i", self.unused1))
                file.write(pack("i", self.frame_length))
                file.write(pack("<I", len(self.target_ids)))
                for target_id in self.target_ids:
                    file.write(pack("<I", target_id))
                file.write(pack("<I", len(self.text_markers)))
                for marker in self.text_markers:
                    if len(marker) != 8:
                        raise ValueError("SKA text markers must contain exactly 8 bytes")
                    file.write(marker)
                file.write(pack("<I", len(self.annotation_bytes)))
                file.write(self.annotation_bytes)
            else:
                print(f"Unknown SKA type: {self.type}.")
