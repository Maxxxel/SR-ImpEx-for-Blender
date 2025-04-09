from typing import BinaryIO
from struct import calcsize, unpack, pack
from dataclasses import dataclass, field
from .file_io import FileReader


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
    stutter_mode: int = (
        0  # 0 for hit animations with just one keyframe per bone? 1 for for special moves of some models?
    )
    unused1: int = (
        0  # often 1 for hit animations and for type 6 it seems to be related to the animation duration and frame length
    )
    unused2: int = (
        0  # for type 7 it seems to be related to the animation duration and frame length
    )
    unused3: int = 0
    unused4: int = 0
    unused5: int = 0
    unused6: list[int] = field(default_factory=list)
    zeroes: list[int] = field(default_factory=list)

    def read(self, file_name: str) -> "SKA":
        reader = FileReader(file_name)
        self.magic = unpack("i", reader.read(calcsize("i")))[0]
        self.type = unpack("I", reader.read(calcsize("I")))[0]
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
            self.unused1 = unpack("i", reader.read(calcsize("i")))[0]
            if self.type == 7:
                self.unused2 = unpack("i", reader.read(calcsize("i")))[0]
            self.zeroes = [unpack("i", reader.read(calcsize("i")))[0] for _ in range(3)]
        else:
            print(f"Unknown SKA type: {self.type}.")
        return self

    def write(self, file_name: str) -> None:
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
                file.write(pack("i", self.unused1))
                if self.type == 7:
                    file.write(pack("i", self.unused2))
                for zero in self.zeroes:
                    file.write(pack("i", zero))
            else:
                print(f"Unknown SKA type: {self.type}.")
