from typing import List
from mathutils import Vector
from .FileIO import FileReader, FileWriter

class SKAHeader:
	"""A class for storing keyframe data"""
	def __init__(self) -> None:
		"""Initializes the SKAHeader class"""
		self.Tick: int
		self.Interval: int
		self.FrameType: int
		self.BoneId: int

	def Read(self, Buffer: FileReader) -> "SKAHeader":
		"""Reads the SKAHeader class"""
		self.Tick = Buffer.ReadUInt()
		self.Interval = Buffer.ReadUInt()
		self.FrameType = Buffer.ReadUInt()
		self.BoneId = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> "SKAHeader":
		"""Writes the SKAHeader class"""
		Buffer.WriteUInt(self.Tick)
		Buffer.WriteUInt(self.Interval)
		Buffer.WriteUInt(self.FrameType)
		Buffer.WriteInt(self.BoneId)
		return self

class SKAKeyframe:
	"""A class for storing keyframe data"""
	def __init__(self) -> None:
		"""Initializes the SKAKeyframe class"""
		self.VectorData: Vector
		self.CurveData: Vector

	def Read(self, Buffer: FileReader) -> "SKAKeyframe":
		"""Reads the SKAKeyframe class"""
		self.VectorData = Buffer.ReadVector4()
		self.CurveData = Buffer.ReadVector4()
		return self

	def Write(self, Buffer: FileWriter) -> "SKAKeyframe":
		"""Writes the SKAKeyframe class"""
		Buffer.WriteVector4(self.VectorData)
		Buffer.WriteVector4(self.CurveData)
		return self

class SKAAnimationData:
	"""A class for storing animation data"""
	def __init__(self) -> None:
		"""Initializes the SKAAnimationData class"""
		self.Duration: float
		self.Repeat: int
		self.StutterMode: int
		self.UnusedItSeems: int
		self.UnusedItTwo: int
		self.Zeroes: List[int]

	def Read(self, Buffer: FileReader, Type: int) -> "SKAAnimationData":
		"""Reads the SKAAnimationData class"""
		self.Duration = Buffer.ReadFloat()
		self.Repeat = Buffer.ReadInt()
		self.StutterMode = Buffer.ReadInt()
		self.UnusedItSeems = Buffer.ReadInt()
		if Type == 6:
			self.UnusedItTwo = Buffer.ReadInt()
		self.Zeroes = Buffer.ReadInt(3)
		return self

	def Write(self, Buffer: FileWriter) -> "SKAAnimationData":
		"""Writes the SKAAnimationData class"""
		Buffer.WriteFloat(self.Duration)
		Buffer.WriteInt(self.Repeat)
		Buffer.WriteInt(self.StutterMode)
		Buffer.WriteInt(self.UnusedItSeems)
		Buffer.WriteInt(self.UnusedItTwo)
		Buffer.WriteInt(self.Zeroes)
		return self

class SKA:
	"""A class for parsing SKA files"""
	def __init__(self) -> None:
		"""Initializes the SKA class"""
		self.Magic: int
		self.Type: int
		self.Length: int
		self.Headers: List[SKAHeader]
		self.Length6: int
		self.Times: List[float]
		self.KeyframeData: List[SKAKeyframe]
		self.AnimationData: SKAAnimationData

	def Read(self, FileName: str) -> "SKA":
		"""Reads the SKA file"""
		Reader = FileReader(FileName)
		self.Magic = Reader.ReadInt()
		self.Type = Reader.ReadUInt()
		if self.Type < 6 or self.Type > 7:
			print("SKAParser: Invalid SKA file type ({}).".format(self.Type))
			return
		self.Length = Reader.ReadInt()
		self.Headers: List[SKAHeader] = [SKAHeader().Read(Reader) for _ in range(self.Length)]
		self.Length6 = Reader.ReadInt()
		self.Times = Reader.ReadFloat(self.Length6)
		self.KeyframeData: List[SKAKeyframe] = [SKAKeyframe().Read(Reader) for _ in range(self.Length6)]
		self.AnimationData: SKAAnimationData = SKAAnimationData().Read(Reader, self.Type)
		if self.AnimationData is None:
			print("SKAParser: Invalid SKA file type ({}).".format(self.Type))
			return
		return self

	def Write(self, FileName: str) -> "SKA":
		"""Writes the SKA file"""
		Writer = FileWriter(FileName)
		Writer.WriteInt(self.Magic)
		Writer.WriteUInt(self.Type)
		Writer.WriteInt(self.Length)
		for Header in self.Headers:
			Header.Write(Writer)
		Writer.WriteInt(self.Length6)
		Writer.WriteFloat(self.Times)
		for Keyframe in self.KeyframeData:
			Keyframe.Write(Writer)
		self.AnimationData.Write(Writer)
		return self
