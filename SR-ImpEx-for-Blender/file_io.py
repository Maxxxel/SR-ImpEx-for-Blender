"""A class for reading binary data from a file """
from typing import List, Union
from struct import unpack as Unpack, pack as Pack
from mathutils import Vector, Matrix, Quaternion

class FileReader:
	"""A class for reading binary data from a file"""
	def __init__(self, FileName: str):
		"""Initializes the FileReader class"""
		self.Buffer = open(FileName, "rb")

	def Seek(self, Offset: int, Origin: int = 0):
		"""Seeks to a position in the buffer"""
		self.Buffer.seek(Offset, Origin)

	def ReadInt(self, n: int = 1) -> Union[int, List[int]]:
		"""Reads n 32-bit integers from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}i", self.Buffer.read(n * 4))
		return Value[0] if n == 1 else list(Value)

	def ReadUInt(self, n: int = 1) -> Union[int, List[int]]:
		"""Reads n 32-bit unsigned integers from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}I", self.Buffer.read(n * 4))
		return Value[0] if n == 1 else list(Value)

	def ReadFloat(self, n: int = 1) -> Union[float, List[float]]:
		"""Reads n 32-bit floats from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}f", self.Buffer.read(n * 4))
		return Value[0] if n == 1 else list(Value)

	def ReadShort(self, n: int = 1) -> Union[int, List[int]]:
		"""Reads n 16-bit integers from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}h", self.Buffer.read(n * 2))
		return Value[0] if n == 1 else list(Value)

	def ReadUShort(self, n: int = 1) -> Union[int, List[int]]:
		"""Reads n 16-bit unsigned integers from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}H", self.Buffer.read(n * 2))
		return Value[0] if n == 1 else list(Value)

	def ReadString(self, n: int = 1) -> str:
		"""Reads n bytes from the buffer and returns them as a string"""
		return Unpack(f"{n}s", self.Buffer.read(n))[0].decode("UTF-8")

	def ReadByte(self, n: int = 1) -> Union[int, List[int]]:
		"""Reads n bytes from the buffer and returns them as a list or a single Value if n is 1"""
		Value = Unpack(f"{n}B", self.Buffer.read(n))
		return Value[0] if n == 1 else list(Value)

	def ReadVector2(self) -> Vector:
		"""Reads 2 32-bit floats from the buffer and returns them as a Vector"""
		return Vector((self.ReadFloat(), self.ReadFloat()))

	def ReadVector3(self) -> Vector:
		"""Reads 3 32-bit floats from the buffer and returns them as a Vector"""
		return Vector((self.ReadFloat(), self.ReadFloat(), self.ReadFloat()))

	def ReadVector4(self) -> Vector:
		"""Reads 4 32-bit floats from the buffer and returns them as a Vector"""
		return Vector((self.ReadFloat(), self.ReadFloat(), self.ReadFloat(), self.ReadFloat()))

	def ReadMatrix3x3(self) -> Matrix:
		"""Reads 9 32-bit floats from the buffer and returns them as a Matrix"""
		return Matrix([self.ReadVector3(), self.ReadVector3(), self.ReadVector3()])

	def ReadMatrix4x4(self) -> Matrix:
		"""Reads 16 32-bit floats from the buffer and returns them as a Matrix"""
		return Matrix([self.ReadVector4(), self.ReadVector4(), self.ReadVector4(), self.ReadVector4()])

	def ReadQuaternion(self) -> Quaternion:
		"""Reads 4 32-bit floats from the buffer and returns them as a Quaternion"""
		return Quaternion([self.ReadFloat(), self.ReadFloat(), self.ReadFloat(), self.ReadFloat()])

class FileWriter:
	"""A class for writing binary data to a file"""
	def __init__(self, FileName: str):
		"""Initializes the FileWriter class"""
		self.Buffer = open(FileName, "wb")

	def WriteInt(self, Value: Union[int, List[int]]):
		"""Writes a 32-bit integer to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("i"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("i", Value))

	def WriteUInt(self, Value: Union[int, List[int]]):
		"""Writes a 32-bit unsigned integer to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("I"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("I", Value))

	def WriteFloat(self, Value: Union[float, List[float]]):
		"""Writes a 32-bit float to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("f"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("f", Value))

	def WriteShort(self, Value: Union[int, List[int]]):
		"""Writes a 16-bit integer to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("h"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("h", Value))

	def WriteUShort(self, Value: Union[int, List[int]]):
		"""Writes a 16-bit unsigned integer to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("H"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("H", Value))

	def WriteString(self, Value: str):
		"""Writes a string to the buffer"""
		self.Buffer.write(Pack(str(len(Value)) + "s", Value.encode("UTF-8")))

	def WriteByte(self, Value: Union[int, List[int]]):
		"""Writes a byte to the buffer"""
		if isinstance(Value, list):
			self.Buffer.write(Pack("B"*len(Value), *Value))
		else:
			self.Buffer.write(Pack("B", Value))

	def WriteVector2(self, Value: Vector):
		"""Writes a Vector to the buffer"""
		self.WriteFloat(Value[0])
		self.WriteFloat(Value[1])

	def WriteVector3(self, Value: Vector):
		"""Writes a Vector to the buffer"""
		self.WriteFloat(Value[0])
		self.WriteFloat(Value[1])
		self.WriteFloat(Value[2])

	def WriteVector4(self, Value: Vector):
		"""Writes a Vector to the buffer"""
		self.WriteFloat(Value[0])
		self.WriteFloat(Value[1])
		self.WriteFloat(Value[2])
		self.WriteFloat(Value[3])
		
	def WriteMatrix3x3(self, Value: Matrix):
		"""Writes a Matrix to the buffer"""
		self.WriteVector3(Value[0])
		self.WriteVector3(Value[1])
		self.WriteVector3(Value[2])

	def WriteMatrix4x4(self, Value: Matrix):
		"""Writes a Matrix to the buffer"""
		self.WriteVector4(Value[0])
		self.WriteVector4(Value[1])
		self.WriteVector4(Value[2])
		self.WriteVector4(Value[3])

	def WriteQuaternion(self, Value: Quaternion):
		"""Writes a Quaternion to the buffer"""
		self.WriteFloat(Value[0])
		self.WriteFloat(Value[1])
		self.WriteFloat(Value[2])
		self.WriteFloat(Value[3])

	def Close(self):
		"""Closes the buffer"""
		self.Buffer.close()
