from typing import List
from mathutils import Vector, Matrix
from .FileIO import FileReader, FileWriter

class RootNodeInformation():
	"""Root Node Information"""
	def __init__(self) -> None:
		"""Root Node Constructor"""
		self.Zeroes: List[int]
		self.NegOne: int
		self.One: int
		self.NodeInformationCount: int
		self.Zero: int

	def Read(self, Buffer: FileReader) -> 'RootNodeInformation':
		"""Reads the Root Node Information from the buffer"""
		self.Zeroes = Buffer.ReadByte(16)
		self.NegOne = Buffer.ReadInt()
		self.One = Buffer.ReadInt()
		self.NodeInformationCount = Buffer.ReadInt()
		self.Zero = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'RootNodeInformation':
		"""Writes the Root Node Information to the buffer"""
		Buffer.WriteByte(self.Zeroes)
		Buffer.WriteInt(self.NegOne)
		Buffer.WriteInt(self.One)
		Buffer.WriteInt(self.NodeInformationCount)
		Buffer.WriteInt(self.Zero)
		return self

class NodeInformation():
	"""Node Information"""
	def __init__(self) -> None:
		"""Node Information Constructor"""
		self.Magic: int
		self.Identifier: int
		self.Offset: int
		self.NodeSize: int
		self.Spacer: List[int]

	def Read(self, Buffer: FileReader) -> 'NodeInformation':
		"""Reads the Node Information from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.Identifier = Buffer.ReadInt()
		self.Offset = Buffer.ReadInt()
		self.NodeSize = Buffer.ReadInt()
		self.Spacer = Buffer.ReadByte(16)
		return self

	def Write(self, Buffer: FileWriter) -> 'NodeInformation':
		"""Writes the Node Information to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteInt(self.Offset)
		Buffer.WriteInt(self.NodeSize)
		Buffer.WriteByte(self.Spacer)
		return self

class RootNode():
	"""Root Node"""
	def __init__(self) -> None:
		"""Root Node Constructor"""
		self.Identifier: int
		self.Unknown: int
		self.Length: int
		self.NodeName: str

	def Read(self, Buffer: FileReader) -> 'RootNode':
		"""Reads the Root Node from the buffer"""
		self.Identifier = Buffer.ReadInt()
		self.Unknown = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.NodeName = Buffer.ReadString(self.Length)
		return self

	def Write(self, Buffer: FileWriter) -> 'RootNode':
		"""Writes the Root Node to the buffer"""
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteInt(self.Unknown)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.NodeName)#
		return self

class Node():
	"""Node"""
	def __init__(self) -> None:
		"""Node Constructor"""
		self.InfoIndex: int
		self.Length: int
		self.Name: str
		self.Zero: int

	def Read(self, Buffer: FileReader) -> 'Node':
		"""Reads the Node from the buffer"""
		self.InfoIndex = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.Length)
		self.Zero = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'Node':
		"""Writes the Node to the buffer"""
		Buffer.WriteInt(self.InfoIndex)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.Zero)
		return self

class Face():
	"""Face"""
	def __init__(self) -> None:
		"""Face Constructor"""
		self.Indices: List[int]

	def Read(self, Buffer: FileReader) -> 'Face':
		"""Reads the Face from the buffer"""
		self.Indices = Buffer.ReadUShort(3)
		return self

	def Write(self, Buffer: FileWriter) -> 'Face':
		"""Writes the Face to the buffer"""
		Buffer.WriteUShort(self.Indices)
		return self

class Vertex():
	"""Vertex"""
	def __init__(self) -> None:
		"""Vertex Constructor"""
		self.Position: Vector
		self.Normal: Vector
		self.Texture: Vector
		self.Tangent: Vector
		self.Bitangent: Vector
		self.RawWeights: List[int]
		self.BoneIndices: List[int]

	def Read(self, Buffer: FileReader, Revision: int) -> 'Vertex':
		"""Reads the Vertex from the buffer"""
		if Revision == 133121:
			self.Position = Buffer.ReadVector3()
			self.Normal = Buffer.ReadVector3()
			self.Texture = Buffer.ReadVector2()
		elif Revision == 12288:
			self.Tangent = Buffer.ReadVector3()
			self.Bitangent = Buffer.ReadVector3()
		elif Revision == 12:
			self.RawWeights = Buffer.ReadByte(4)
			self.BoneIndices = Buffer.ReadByte(4)
		return self

	def Write(self, Buffer: FileWriter) -> 'Vertex':
		"""Writes the Vertex to the buffer"""
		Buffer.WriteVector3(self.Position)
		Buffer.WriteVector3(self.Normal)
		Buffer.WriteVector2(self.Texture)
		Buffer.WriteVector3(self.Tangent)
		Buffer.WriteVector3(self.Bitangent)
		Buffer.WriteByte(self.RawWeights)
		Buffer.WriteByte(self.BoneIndices)
		return self

class MeshData():
	"""Mesh Data"""
	def __init__(self) -> None:
		"""Mesh Data Constructor"""
		self.Revision: int
		self.VertexSize: int
		self.Vertices: List[Vertex]

	def Read(self, Buffer: FileReader, VertexCount: int) -> 'MeshData':
		"""Reads the Mesh Data from the buffer"""
		self.Revision = Buffer.ReadInt()
		self.VertexSize = Buffer.ReadInt()
		self.Vertices = [Vertex().Read(Buffer, self.Revision) for _ in range(VertexCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'MeshData':
		"""Writes the Mesh Data to the buffer"""
		Buffer.WriteInt(self.Revision)
		Buffer.WriteInt(self.VertexSize)
		for _Vertex in self.Vertices:
			_Vertex.Write(Buffer)
		return self

class Texture():
	"""Texture"""
	def __init__(self) -> None:
		"""Texture Constructor"""
		self.Identifier: int
		self.Length: int
		self.Name: str
		self.Spacer: int

	def Read(self, Buffer: FileReader) -> 'Texture':
		"""Reads the Texture from the buffer"""
		self.Identifier = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.Length)
		self.Spacer = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'Texture':
		"""Writes the Texture to the buffer"""
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.Spacer)
		return self

class Textures():
	"""Textures"""
	def __init__(self) -> None:
		"""Textures Constructor"""
		self.Length: int
		self.Textures: List[Texture]

	def Read(self, Buffer: FileReader) -> 'Textures':
		"""Reads the Textures from the buffer"""
		self.Length = Buffer.ReadInt()
		self.Textures = [Texture().Read(Buffer) for _ in range(self.Length)]
		return self

	def Write(self, Buffer: FileWriter) -> 'Textures':
		"""Writes the Textures to the buffer"""
		Buffer.WriteInt(self.Length)
		for _Texture in self.Textures:
			_Texture.Write(Buffer)
		return self

class Refraction():
	"""Refraction"""
	def __init__(self) -> None:
		"""Refraction Constructor"""
		self.Length: int
		self.Identifier: int
		self.RGB: List[float]

	def Read(self, Buffer: FileReader) -> 'Refraction':
		"""Reads the Refraction from the buffer"""
		self.Length = Buffer.ReadInt()
		if self.Length == 1:
			self.Identifier = Buffer.ReadInt()
			self.RGB = Buffer.ReadFloat(3)
		return self

	def Write(self, Buffer: FileWriter) -> 'Refraction':
		"""Writes the Refraction to the buffer"""
		Buffer.WriteInt(self.Length)
		if self.Length == 1:
			Buffer.WriteInt(self.Identifier)
			Buffer.WriteFloat(self.RGB)
		return self

class Material():
	"""Material"""
	def __init__(self) -> None:
		"""Material Constructor"""
		self.Identifier: int
		self.Smoothness: float
		self.Metalness: float
		self.Reflectivity: float
		self.Emissivity: float
		self.RefractionScale: float
		self.DistortionMeshScale: float
		self.Scratch: float
		self.SpecularScale: float
		self.WindResponse: float
		self.WindHeight: float
		self.DepthWriteThreshold: float
		self.Saturation: float
		self.Unknown: float

	def Read(self, Buffer: FileReader) -> 'Material':
		"""Reads the Material from the buffer"""
		self.Identifier = Buffer.ReadInt()
		if self.Identifier == 1668510769:
			self.Smoothness = Buffer.ReadFloat()
		elif self.Identifier == 1668510770:
			self.Metalness = Buffer.ReadFloat()
		elif self.Identifier == 1668510771:
			self.Reflectivity = Buffer.ReadFloat()
		elif self.Identifier == 1668510772:
			self.Emissivity = Buffer.ReadFloat()
		elif self.Identifier == 1668510773:
			self.RefractionScale = Buffer.ReadFloat()
		elif self.Identifier == 1668510774:
			self.DistortionMeshScale = Buffer.ReadFloat()
		elif self.Identifier == 1935897704:
			self.Scratch = Buffer.ReadFloat() # Only touch if ScratchMap is present
		elif self.Identifier == 1668510775:
			self.SpecularScale = Buffer.ReadFloat() # Reflectioness
		elif self.Identifier == 1668510776:
			self.WindResponse = Buffer.ReadFloat() # Wind Force 0 -> 0.1
		elif self.Identifier == 1668510777:
			self.WindHeight = Buffer.ReadFloat() # Wind Attack Height at maximum unit height
		elif self.Identifier == 1935893623:
			self.DepthWriteThreshold = Buffer.ReadFloat()
		elif self.Identifier == 1668510785:
			self.Saturation = Buffer.ReadFloat()
		else:
			# Unknown Property, add to the list
			self.Unknown = Buffer.ReadFloat()
			raise TypeError("Unknown Material {}".format(self.Unknown))
		return self

	def Write(self, Buffer: FileWriter) -> 'Material':
		"""Writes the Material to the buffer"""
		Buffer.WriteInt(self.Identifier)
		if self.Identifier == 1668510769:
			Buffer.WriteFloat(self.Smoothness)
		elif self.Identifier == 1668510770:
			Buffer.WriteFloat(self.Metalness)
		elif self.Identifier == 1668510771:
			Buffer.WriteFloat(self.Reflectivity)
		elif self.Identifier == 1668510772:
			Buffer.WriteFloat(self.Emissivity)
		elif self.Identifier == 1668510773:
			Buffer.WriteFloat(self.RefractionScale)
		elif self.Identifier == 1668510774:
			Buffer.WriteFloat(self.DistortionMeshScale)
		elif self.Identifier == 1935897704:
			Buffer.WriteFloat(self.Scratch)
		elif self.Identifier == 1668510775:
			Buffer.WriteFloat(self.SpecularScale)
		elif self.Identifier == 1668510776:
			Buffer.WriteFloat(self.WindResponse)
		elif self.Identifier == 1668510777:
			Buffer.WriteFloat(self.WindHeight)
		elif self.Identifier == 1935893623:
			Buffer.WriteFloat(self.DepthWriteThreshold)
		elif self.Identifier == 1668510785:
			Buffer.WriteFloat(self.Saturation)
		else:
			# Unknown Property, add to the list
			Buffer.WriteFloat(self.Unknown)
			raise TypeError("Unknown Material {}".format(self.Unknown))
		return self

class Materials():
	"""Materials"""
	def __init__(self) -> None:
		"""Materials Constructor"""
		self.Length: int
		self.Materials: List[Material]

	def Read(self, Buffer: FileReader) -> 'Materials':
		"""Reads the Materials from the buffer"""
		self.Length = Buffer.ReadInt()
		self.Materials = [Material().Read(Buffer) for _ in range(self.Length)]
		return self

	def Write(self, Buffer: FileWriter) -> 'Materials':
		"""Writes the Materials to the buffer"""
		Buffer.WriteInt(self.Length)
		for _Material in self.Materials:
			_Material.Write(Buffer)
		return self

class LevelOfDetail():
	"""LevelOfDetail"""
	def __init__(self) -> None:
		"""LevelOfDetail Constructor"""
		self.Length: int
		self.LODLevel: int

	def Read(self, Buffer: FileReader) -> 'LevelOfDetail':
		"""Reads the LevelOfDetail from the buffer"""
		self.Length = Buffer.ReadInt()
		if self.Length == 1:
			self.LODLevel = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'LevelOfDetail':
		"""Writes the LevelOfDetail to the buffer"""
		Buffer.WriteInt(self.Length)
		if self.Length == 1:
			Buffer.WriteInt(self.LODLevel)
		return self

class EmptyString():
	"""EmptyString"""
	def __init__(self) -> None:
		"""EmptyString Constructor"""
		self.Length: int
		self.UnknwonString: str

	def Read(self, Buffer: FileReader) -> 'EmptyString':
		"""Reads the EmptyString from the buffer"""
		self.Length = Buffer.ReadInt()
		self.UnknwonString = Buffer.ReadString(self.Length * 2)
		return self

	def Write(self, Buffer: FileWriter) -> 'EmptyString':
		"""Writes the EmptyString to the buffer"""
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.UnknwonString)
		return self

class Flow():
	"""Flow"""
	def __init__(self) -> None:
		"""Flow Constructor"""
		self.Length: int
		self.MaxFlowSpeedIdentifier: int
		self.MaxFlowSpeed: Vector
		self.MinFlowSpeedIdentifier: int
		self.MinFlowSpeed: Vector
		self.FlowSpeedChangeIdentifier: int
		self.FlowSpeedChange: Vector
		self.FlowScaleIdentifier: int
		self.FlowScale: Vector

	def Read(self, Buffer: FileReader) -> 'Flow':
		"""Reads the Flow from the buffer"""
		self.Length = Buffer.ReadInt()
		if self.Length == 4:
			self.MaxFlowSpeedIdentifier = Buffer.ReadInt()
			self.MaxFlowSpeed = Buffer.ReadVector4()
			self.MinFlowSpeedIdentifier = Buffer.ReadInt()
			self.MinFlowSpeed = Buffer.ReadVector4()
			self.FlowSpeedChangeIdentifier = Buffer.ReadInt()
			self.FlowSpeedChange = Buffer.ReadVector4()
			self.FlowScaleIdentifier = Buffer.ReadInt()
			self.FlowScale = Buffer.ReadVector4()
		return self

	def Write(self, Buffer: FileWriter) -> 'Flow':
		"""Writes the Flow to the buffer"""
		Buffer.WriteInt(self.Length)
		if self.Length == 4:
			Buffer.WriteInt(self.MaxFlowSpeedIdentifier)
			Buffer.WriteVector4(self.MaxFlowSpeed)
			Buffer.WriteInt(self.MinFlowSpeedIdentifier)
			Buffer.WriteVector4(self.MinFlowSpeed)
			Buffer.WriteInt(self.FlowSpeedChangeIdentifier)
			Buffer.WriteVector4(self.FlowSpeedChange)
			Buffer.WriteInt(self.FlowScaleIdentifier)
			Buffer.WriteVector4(self.FlowScale)
		return self

class BattleforgeMesh():
	"""BattleforgeMesh"""
	def __init__(self) -> None:
		"""BattleforgeMesh Constructor"""
		self.VertexCount: int
		self.FaceCount: int
		self.Faces: List[Face]
		self.MeshCount: int
		self.MeshData: List[MeshData]
		self.BoundingBoxLowerLeftCorner: Vector
		self.BoundingBoxUpperRightCorner: Vector
		self.MaterialID: int
		self.MaterialParameters: int
		self.MaterialStuff: int
		self.BoolParameter: int
		self.Textures: Textures
		self.Refraction: Refraction
		self.Materials: Materials
		self.LevelOfDetail: LevelOfDetail
		self.EmptyString: EmptyString
		self.Flow: Flow

	def Read(self, Buffer: FileReader) -> 'BattleforgeMesh':
		"""Reads the BattleforgeMesh from the buffer"""
		self.VertexCount = Buffer.ReadInt()
		self.FaceCount = Buffer.ReadInt()
		self.Faces = [Face().Read(Buffer) for _ in range(self.FaceCount)]
		self.MeshCount = Buffer.ReadByte()
		self.MeshData = [MeshData().Read(Buffer, self.VertexCount) for _ in range(self.MeshCount)]
		self.BoundingBoxLowerLeftCorner = Buffer.ReadVector3()
		self.BoundingBoxUpperRightCorner = Buffer.ReadVector3()
		self.MaterialID = Buffer.ReadShort()
		self.MaterialParameters = Buffer.ReadInt()
		if self.MaterialParameters == -86061050:
			self.MaterialStuff = Buffer.ReadInt()
			self.BoolParameter = Buffer.ReadInt()
			self.Textures = Textures().Read(Buffer)
			self.Refraction = Refraction().Read(Buffer)
			self.Materials = Materials().Read(Buffer)
			self.LevelOfDetail = LevelOfDetail().Read(Buffer)
			self.EmptyString = EmptyString().Read(Buffer)
			self.Flow = Flow().Read(Buffer)
		else:
			raise TypeError("Unknown MaterialParameters {}".format(self.MaterialParameters))
		return self

	def Write(self, Buffer: FileWriter) -> 'BattleforgeMesh':
		"""Writes the BattleforgeMesh to the buffer"""
		Buffer.WriteInt(self.VertexCount)
		Buffer.WriteInt(self.FaceCount)
		for _Face in self.Faces:
			_Face.Write(Buffer)
		Buffer.WriteByte(self.MeshCount)
		for _MeshData in self.MeshData:
			_MeshData.Write(Buffer)
		Buffer.WriteVector3(self.BoundingBoxLowerLeftCorner)
		Buffer.WriteVector3(self.BoundingBoxUpperRightCorner)
		Buffer.WriteShort(self.MaterialID)
		Buffer.WriteInt(self.MaterialParameters)
		if self.MaterialParameters == -86061050:
			Buffer.WriteInt(self.MaterialStuff)
			Buffer.WriteInt(self.BoolParameter)
			self.Textures.Write(Buffer)
			self.Refraction.Write(Buffer)
			self.Materials.Write(Buffer)
			self.LevelOfDetail.Write(Buffer)
			self.EmptyString.Write(Buffer)
			self.Flow.Write(Buffer)
		else:
			raise TypeError("Unknown MaterialParameters {}".format(self.MaterialParameters))
		return self

class CDspMeshFile():
	"""CDspMeshFile"""
	def __init__(self) -> None:
		"""CDspMeshFile Constructor"""
		self.Magic: int
		self.Zero: int
		self.MeshCount: int
		self.BoundingBoxLowerLeftCorner: Vector
		self.BoundingBoxUpperRightCorner: Vector
		self.Meshes: List[BattleforgeMesh]
		self.SomePoints: List[Vector]

	def Read(self, Buffer: FileReader) -> 'CDspMeshFile':
		"""Reads the CDspMeshFile from the buffer"""
		self.Magic = Buffer.ReadInt()
		if self.Magic == 1314189598:
			self.Zero = Buffer.ReadInt()
			self.MeshCount = Buffer.ReadInt()
			self.BoundingBoxLowerLeftCorner = Buffer.ReadVector3()
			self.BoundingBoxUpperRightCorner = Buffer.ReadVector3()
			self.Meshes = [BattleforgeMesh().Read(Buffer) for _ in range(self.MeshCount)]
			self.SomePoints = [Buffer.ReadVector4() for _ in range(3)]
		else:
			raise TypeError("This Mesh has the wrong Magic Value: {}".format(self.Magic))
		return self

	def Write(self, Buffer: FileWriter) -> 'CDspMeshFile':
		"""Writes the CDspMeshFile to the buffer"""
		Buffer.WriteInt(self.Magic)
		if self.Magic == 1314189598:
			Buffer.WriteInt(self.Zero)
			Buffer.WriteInt(self.MeshCount)
			Buffer.WriteVector3(self.BoundingBoxLowerLeftCorner)
			Buffer.WriteVector3(self.BoundingBoxUpperRightCorner)
			for Mesh in self.Meshes:
				Mesh.Write(Buffer)
			for Point in self.SomePoints:
				Buffer.WriteVector4(Point)
		else:
			raise TypeError("This Mesh has the wrong Magic Value: {}".format(self.Magic))
		return self

class SMeshState():
	"""SMeshState"""
	def __init__(self) -> None:
		"""SMeshState Constructor"""
		self.StateNum: int
		self.HasFiles: int
		self.UKFileLength: int
		self.UKFile: str
		self.DRSFileLength: int
		self.DRSFile: str

	def Read(self, Buffer: FileReader) -> 'SMeshState':
		"""Reads the SMeshState from the buffer"""
		self.StateNum = Buffer.ReadInt()
		self.HasFiles = Buffer.ReadShort()
		if self.HasFiles == 1:
			self.UKFileLength = Buffer.ReadInt()
			self.UKFile = Buffer.ReadString(self.UKFileLength)
			self.DRSFileLength = Buffer.ReadInt()
			self.DRSFile = Buffer.ReadString(self.DRSFileLength)
		return self

	def Write(self, Buffer: FileWriter) -> 'SMeshState':
		"""Writes the SMeshState to the buffer"""
		Buffer.WriteInt(self.StateNum)
		Buffer.WriteShort(self.HasFiles)
		if self.HasFiles == 1:
			Buffer.WriteInt(self.UKFileLength)
			Buffer.WriteString(self.UKFile)
			Buffer.WriteInt(self.DRSFileLength)
			Buffer.WriteString(self.DRSFile)
		return self

class DestructionState():
	"""DestructionState"""
	def __init__(self) -> None:
		"""DestructionState Constructor"""
		self.StateNum: int
		self.FileNameLength: int
		self.FileName: str

	def Read(self, Buffer: FileReader) -> 'DestructionState':
		"""Reads the DestructionState from the buffer"""
		self.StateNum = Buffer.ReadInt()
		self.FileNameLength = Buffer.ReadInt()
		self.FileName = Buffer.ReadString(self.FileNameLength)
		return self

	def Write(self, Buffer: FileWriter) -> 'DestructionState':
		"""Writes the DestructionState to the buffer"""
		Buffer.WriteInt(self.StateNum)
		Buffer.WriteInt(self.FileNameLength)
		Buffer.WriteString(self.FileName)
		return self

class StateBasedMeshSet():
	"""StateBasedMeshSet"""
	def __init__(self) -> None:
		"""StateBasedMeshSet Constructor"""
		self.UKShort: int
		self.UKInt: int
		self.NumMeshStates: int
		self.SMeshStates: List[SMeshState]
		self.NumDestructionStates: int
		self.DestructionStates: List[DestructionState]

	def Read(self, Buffer: FileReader) -> 'StateBasedMeshSet':
		"""Reads the StateBasedMeshSet from the buffer"""
		self.UKShort = Buffer.ReadShort()
		self.UKInt = Buffer.ReadInt()
		self.NumMeshStates = Buffer.ReadInt()
		self.SMeshStates = [SMeshState().Read(Buffer) for _ in range(self.NumMeshStates)]
		self.NumDestructionStates = Buffer.ReadInt()
		self.DestructionStates = [DestructionState().Read(Buffer) for _ in range(self.NumDestructionStates)]
		return self

	def Write(self, Buffer: FileWriter) -> 'StateBasedMeshSet':
		"""Writes the StateBasedMeshSet to the buffer"""
		Buffer.WriteShort(self.UKShort)
		Buffer.WriteInt(self.UKInt)
		Buffer.WriteInt(self.NumMeshStates)
		for MeshState in self.SMeshStates:
			MeshState.Write(Buffer)
		Buffer.WriteInt(self.NumDestructionStates)
		for _DestructionState in self.DestructionStates:
			_DestructionState.Write(Buffer)
		return self

class MeshGridModule():
	"""MeshGridModule"""
	def __init__(self) -> None:
		"""MeshGridModule Constructor"""
		self.UKShort: int
		self.HasMeshSet: int
		self.StateBasedMeshSet: StateBasedMeshSet

	def Read(self, Buffer: FileReader) -> 'MeshGridModule':
		"""Reads the MeshGridModule from the buffer"""
		self.UKShort = Buffer.ReadShort()
		self.HasMeshSet = Buffer.ReadByte()
		if self.HasMeshSet == 1:
			self.StateBasedMeshSet = StateBasedMeshSet().Read(Buffer)
		return self

	def Write(self, Buffer: FileWriter) -> 'MeshGridModule':
		"""Writes the MeshGridModule to the buffer"""
		Buffer.WriteShort(self.UKShort)
		Buffer.WriteByte(self.HasMeshSet)
		if self.HasMeshSet == 1:
			self.StateBasedMeshSet.Write(Buffer)
		return self

class CMatCoordinateSystem():
	"""CMatCoordinateSystem"""
	def __init__(self) -> None:
		"""CMatCoordinateSystem Constructor"""
		self.Matrix: Matrix
		self.Position: Vector

	def Read(self, Buffer: FileReader) -> 'CMatCoordinateSystem':
		"""Reads the CMatCoordinateSystem from the buffer"""
		self.Matrix = Buffer.ReadMatrix3x3()
		self.Position = Buffer.ReadVector3()
		return self

	def Write(self, Buffer: FileWriter) -> 'CMatCoordinateSystem':
		"""Writes the CMatCoordinateSystem to the buffer"""
		Buffer.WriteMatrix4x4(self.Matrix)
		Buffer.WriteVector3(self.Position)
		return self

class SLocator():
	"""SLocator"""
	def __init__(self) -> None:
		"""SLocator Constructor"""
		self.CMatCoordinateSystem: CMatCoordinateSystem
		self.Class: int
		self.SubID: int
		self.FileNameLength: int
		self.FileName: str
		self.UKInt: int

	def Read(self, Buffer: FileReader, Version: int) -> 'SLocator':
		"""Reads the SLocator from the buffer"""
		self.CMatCoordinateSystem = CMatCoordinateSystem().Read(Buffer)
		self.Class = Buffer.ReadInt()
		self.SubID = Buffer.ReadInt()
		self.FileNameLength = Buffer.ReadInt()
		self.FileName = Buffer.ReadString(self.FileNameLength)
		if Version == 5:
			self.UKInt = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'SLocator':
		"""Writes the SLocator to the buffer"""
		self.CMatCoordinateSystem.Write(Buffer)
		Buffer.WriteInt(self.Class)
		Buffer.WriteInt(self.SubID)
		Buffer.WriteInt(self.FileNameLength)
		Buffer.WriteString(self.FileName)
		Buffer.WriteInt(self.UKInt)
		return self

class CDrwLocatorList():
	"""CDrwLocatorList"""
	def __init__(self) -> None:
		"""CDrwLocatorList Constructor"""
		self.Magic: int
		self.Version: int
		self.Length: int
		self.SLocators: List[SLocator]

	def Read(self, Buffer: FileReader) -> 'CDrwLocatorList':
		"""Reads the CDrwLocatorList from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.Version = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.SLocators = [SLocator().Read(Buffer, self.Version) for _ in range(self.Length)]
		return self

	def Write(self, Buffer: FileWriter) -> 'CDrwLocatorList':
		"""Writes the CDrwLocatorList to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.Length)
		for Locator in self.SLocators:
			Locator.Write(Buffer)
		return self

class CGeoAABox():
	"""CGeoAABox"""
	def __init__(self) -> None:
		"""CGeoAABox Constructor"""
		self.LowerLeftCorner: Vector
		self.UpperRightCorner: Vector

	def Read(self, Buffer: FileReader) -> 'CGeoAABox':
		"""Reads the CGeoAABox from the buffer"""
		self.LowerLeftCorner = Buffer.ReadVector3()
		self.UpperRightCorner = Buffer.ReadVector3()
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoAABox':
		"""Writes the CGeoAABox to the buffer"""
		Buffer.WriteVector3(self.LowerLeftCorner)
		Buffer.WriteVector3(self.UpperRightCorner)
		return self

class Box():
	"""Box"""
	def __init__(self) -> None:
		"""Box Constructor"""
		self.CoordSystem: CMatCoordinateSystem
		self.CGeoAABox: CGeoAABox

	def Read(self, Buffer: FileReader) -> 'Box':
		"""Reads the Box from the buffer"""
		self.CoordSystem = CMatCoordinateSystem().Read(Buffer)
		self.CGeoAABox = CGeoAABox().Read(Buffer)
		return self

	def Write(self, Buffer: FileWriter) -> 'Box':
		"""Writes the Box to the buffer"""
		self.CoordSystem.Write(Buffer)
		self.CGeoAABox.Write(Buffer)
		return self

class CGeoCylinder():
	"""CGeoCylinder"""
	def __init__(self) -> None:
		"""CGeoCylinder Constructor"""
		self.Center: Vector
		self.Height: float
		self.Radius: float

	def Read(self, Buffer: FileReader) -> 'CGeoCylinder':
		"""Reads the CGeoCylinder from the buffer"""
		self.Center = Buffer.ReadVector3()
		self.Height = Buffer.ReadFloat()
		self.Radius = Buffer.ReadFloat()
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoCylinder':
		"""Writes the CGeoCylinder to the buffer"""
		Buffer.WriteVector3(self.Center)
		Buffer.WriteFloat(self.Height)
		Buffer.WriteFloat(self.Radius)
		return self

class CGeoSphere():
	"""CGeoSphere"""
	def __init__(self) -> None:
		"""CGeoSphere Constructor"""
		self.Radius: float
		self.Center: Vector

	def Read(self, Buffer: FileReader) -> 'CGeoSphere':
		"""Reads the CGeoSphere from the buffer"""
		self.Radius = Buffer.ReadFloat()
		self.Center = Buffer.ReadVector3()
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoSphere':
		"""Writes the CGeoSphere to the buffer"""
		Buffer.WriteFloat(self.Radius)
		Buffer.WriteVector3(self.Center)
		return self

class CollisionShape():
	"""CollisionShape"""
	def __init__(self) -> None:
		"""CollisionShape Constructor"""
		self.Version: int
		self.BoxCount: int
		self.Boxes: List[Box]
		self.SphereCount: int
		self.Spheres: List[CGeoSphere]
		self.CylinderCount: int
		self.Cylinders: List[CGeoCylinder]

	def Read(self, Buffer: FileReader) -> 'CollisionShape':
		"""Reads the CollisionShape from the buffer"""
		self.Version = Buffer.ReadByte()
		self.BoxCount = Buffer.ReadInt()
		self.Boxes = [Box().Read(Buffer) for _ in range(self.BoxCount)]
		self.SphereCount = Buffer.ReadInt()
		self.Spheres = [CGeoSphere().Read(Buffer) for _ in range(self.SphereCount)]
		self.CylinderCount = Buffer.ReadInt()
		self.Cylinders = [CGeoCylinder().Read(Buffer) for _ in range(self.CylinderCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'CollisionShape':
		"""Writes the CollisionShape to the buffer"""
		Buffer.WriteByte(self.Version)
		Buffer.WriteInt(self.BoxCount)
		for _Box in self.Boxes:
			_Box.Write(Buffer)
		Buffer.WriteInt(self.SphereCount)
		for Sphere in self.Spheres:
			Sphere.Write(Buffer)
		Buffer.WriteInt(self.CylinderCount)
		for Cylinder in self.Cylinders:
			Cylinder.Write(Buffer)
		return self

class BoneVertex():
	"""BoneVertex"""
	def __init__(self) -> None:
		"""BoneVertex Constructor"""
		self.Position: Vector
		self.Parent: int

	def Read(self, Buffer: FileReader) -> 'BoneVertex':
		"""Reads the BoneVertex from the buffer"""
		self.Position = Buffer.ReadVector3()
		self.Parent = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'BoneVertex':
		"""Writes the BoneVertex to the buffer"""
		Buffer.WriteVector3(self.Position)
		Buffer.WriteInt(self.Parent)
		return self

class BoneMatrix():
	"""BoneMatrix"""
	def __init__(self) -> None:
		"""BoneMatrix Constructor"""
		self.BoneVertices: List[BoneVertex]

	def Read(self, Buffer: FileReader) -> 'BoneMatrix':
		"""Reads the BoneMatrix from the buffer"""
		self.BoneVertices = [BoneVertex().Read(Buffer) for _ in range(4)]
		return self

	def Write(self, Buffer: FileWriter) -> 'BoneMatrix':
		"""Writes the BoneMatrix to the buffer"""
		for _BoneVertex in self.BoneVertices:
			_BoneVertex.Write(Buffer)
		return self

class Bone():
	"""Bone"""
	def __init__(self) -> None:
		"""Bone Constructor"""
		self.Version: int
		self.Identifier: int
		self.NameLength: int
		self.Name: str
		self.ChildCount: int
		self.Children: List[int]

	def Read(self, Buffer: FileReader) -> 'Bone':
		"""Reads the Bone from the buffer"""
		self.Version = Buffer.ReadInt()
		self.Identifier = Buffer.ReadInt()
		self.NameLength = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.NameLength)
		self.ChildCount = Buffer.ReadInt()
		self.Children = [Buffer.ReadInt() for _ in range(self.ChildCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'Bone':
		"""Writes the Bone to the buffer"""
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteInt(self.NameLength)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.ChildCount)
		for Child in self.Children:
			Buffer.WriteInt(Child)
		return self

class CSkSkeleton():
	"""CSkSkeleton"""
	def __init__(self) -> None:
		"""CSkSkeleton Constructor"""
		self.Magic: int
		self.Version: int
		self.BoneMatrixCount: int
		self.BoneMatrices: List[BoneMatrix]
		self.BoneCount: int
		self.Bones: List[Bone]
		self.SuperParent: Vector

	def Read(self, Buffer: FileReader) -> 'CSkSkeleton':
		"""Reads the CSkSkeleton from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.Version = Buffer.ReadInt()
		self.BoneMatrixCount = Buffer.ReadInt()
		self.BoneMatrices = [BoneMatrix().Read(Buffer) for _ in range(self.BoneMatrixCount)]
		self.BoneCount = Buffer.ReadInt()
		self.Bones = [Bone().Read(Buffer) for _ in range(self.BoneCount)]
		self.SuperParent = Buffer.ReadVector4()
		return self

	def Write(self, Buffer: FileWriter) -> 'CSkSkeleton':
		"""Writes the CSkSkeleton to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.BoneMatrixCount)
		for _BoneMatrix in self.BoneMatrices:
			_BoneMatrix.Write(Buffer)
		Buffer.WriteInt(self.BoneCount)
		for _Bone in self.Bones:
			_Bone.Write(Buffer)
		Buffer.WriteVector4(self.SuperParent)
		return self

class JointGroup():
	"""JointGroup"""
	def __init__(self) -> None:
		"""JointGroup Constructor"""
		self.JointCount: int
		self.Joints: List[int]

	def Read(self, Buffer: FileReader) -> 'JointGroup':
		"""Reads the JointGroup from the buffer"""
		self.JointCount = Buffer.ReadInt()
		self.Joints = [Buffer.ReadInt() for _ in range(self.JointCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'JointGroup':
		"""Writes the JointGroup to the buffer"""
		Buffer.WriteInt(self.JointCount)
		for Joint in self.Joints:
			Buffer.WriteInt(Joint)
		return self

class CDspJointMap():
	"""CDspJointMap"""
	def __init__(self) -> None:
		"""CDspJointMap Constructor"""
		self.Version: int
		self.JointGroupCount: int
		self.JointGroups: List[JointGroup]

	def Read(self, Buffer: FileReader) -> 'CDspJointMap':
		"""Reads the CDspJointMap from the buffer"""
		self.Version = Buffer.ReadInt()
		self.JointGroupCount = Buffer.ReadInt()
		self.JointGroups = [JointGroup().Read(Buffer) for _ in range(self.JointGroupCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'CDspJointMap':
		"""Writes the CDspJointMap to the buffer"""
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.JointGroupCount)
		for _JointGroup in self.JointGroups:
			_JointGroup.Write(Buffer)
		return self

class VertexData():
	"""VertexData"""
	def __init__(self) -> None:
		"""VertexData Constructor"""
		self.Weights: list[float] = []
		self.BoneIndices: list[int] = []

	def Read(self, Buffer: FileReader) -> 'VertexData':
		"""Reads the VertexData from the buffer"""
		self.Weights = [Buffer.ReadFloat() for _ in range(4)]
		self.BoneIndices = [Buffer.ReadInt() for _ in range(4)]
		return self

	def Write(self, Buffer: FileWriter) -> 'VertexData':
		"""Writes the VertexData to the buffer"""
		for Weight in self.Weights:
			Buffer.WriteFloat(Weight)
		for BoneIndex in self.BoneIndices:
			Buffer.WriteInt(BoneIndex)
		return self

class CSkSkinInfo():
	"""CSkSkinInfo"""
	def __init__(self) -> None:
		"""CSkSkinInfo Constructor"""
		self.Version: int
		self.VertexCount: int
		self.VertexData: List[VertexData]

	def Read(self, Buffer: FileReader) -> 'CSkSkinInfo':
		"""Reads the CSkSkinInfo from the buffer"""
		self.Version = Buffer.ReadInt()
		self.VertexCount = Buffer.ReadInt()
		self.VertexData = [VertexData().Read(Buffer) for _ in range(self.VertexCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'CSkSkinInfo':
		"""Writes the CSkSkinInfo to the buffer"""
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.VertexCount)
		for _VertexData in self.VertexData:
			_VertexData.Write(Buffer)
		return self

class CGeoMesh():
	"""CGeoMesh"""
	def __init__(self) -> None:
		"""CGeoMesh Constructor"""
		self.Magic: int
		self.IndexCount: int
		self.Faces: List[Face]
		self.VertexCount: int
		self.Vertices: List[Vector]
		self.Unknown: float

	def Read(self, Buffer: FileReader) -> 'CGeoMesh':
		"""Reads the CGeoMesh from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.IndexCount = Buffer.ReadInt()
		self.Faces = [Face().Read(Buffer) for _ in range(int(self.IndexCount / 3))]
		self.VertexCount = Buffer.ReadInt()
		self.Vertices = [Buffer.ReadVector4() for _ in range(self.VertexCount)]
		self.Unknown = Buffer.ReadFloat()
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoMesh':
		"""Writes the CGeoMesh to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.IndexCount)
		for _Face in self.Faces:
			_Face.Write(Buffer)
		Buffer.WriteInt(self.VertexCount)
		for _Vertex in self.Vertices:
			Buffer.WriteVector4(_Vertex)
		Buffer.WriteFloat(self.Unknown)
		return self

class AnimationSetVariant():
	"""AnimationSetVariant"""
	def __init__(self) -> None:
		"""AnimationSetVariant Constructor"""
		self.Unknown: int
		self.Weight: int
		self.Length: int
		self.File: str
		self.Start: float
		self.End: float
		self.AllowsIK: bool
		self.Unknown2: bool

	def Read(self, Buffer: FileReader) -> 'AnimationSetVariant':
		"""Reads the AnimationSetVariant from the buffer"""
		self.Unknown = Buffer.ReadInt()
		self.Weight = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.File = Buffer.ReadString(self.Length)

		if self.Unknown >= 4:
			self.Start = Buffer.ReadFloat()
			self.End = Buffer.ReadFloat()

		if self.Unknown >= 5:
			self.AllowsIK = Buffer.ReadByte()

		if self.Unknown >= 7:
			self.Unknown2 = Buffer.ReadByte()

		return self

	def Write(self, Buffer: FileWriter) -> 'AnimationSetVariant':
		"""Writes the AnimationSetVariant to the buffer"""
		Buffer.WriteInt(self.Unknown)
		Buffer.WriteInt(self.Weight)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.File)
		Buffer.WriteFloat(self.Start)
		Buffer.WriteFloat(self.End)
		Buffer.WriteByte(self.AllowsIK)
		Buffer.WriteByte(self.Unknown2)
		return self

class ModeAnimationKey():
	"""ModeAnimationKey"""
	def __init__(self) -> None:
		"""ModeAnimationKey Constructor"""
		self.Type: int
		self.Length: int
		self.File: str
		self.Unknown: int
		self.Unknown2: List[int]
		self.VariantCount: int
		self.AnimationSetVariants: List[AnimationSetVariant]

	def Read(self, Buffer: FileReader, UK: int) -> 'ModeAnimationKey':
		"""Reads the ModeAnimationKey from the buffer"""
		if UK != 2:
			self.Type = Buffer.ReadInt()
		else:
			self.Type = 2
		self.Length = Buffer.ReadInt()
		self.File = Buffer.ReadString(self.Length)
		self.Unknown = Buffer.ReadInt()
		if self.Type == 1:
			self.Unknown2 = [Buffer.ReadByte() for _ in range(24)]
		elif self.Type <= 5:
			self.Unknown2 = [Buffer.ReadByte() for _ in range(6)]
		elif self.Type == 6:
			self.Unknown2 = [Buffer.ReadByte() for _ in range(12)]
		self.VariantCount = Buffer.ReadInt()
		self.AnimationSetVariants = [AnimationSetVariant().Read(Buffer) for _ in range(self.VariantCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'ModeAnimationKey':
		"""Writes the ModeAnimationKey to the buffer"""
		Buffer.WriteInt(self.Type)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.File)
		Buffer.WriteInt(self.Unknown)
		for Unknown2 in self.Unknown2:
			Buffer.WriteByte(Unknown2)
		Buffer.WriteInt(self.VariantCount)
		for _AnimationSetVariant in self.AnimationSetVariants:
			_AnimationSetVariant.Write(Buffer)
		return self

class Constraint():
	"""Constraint"""
	def __init__(self) -> None:
		"""Constraint Constructor"""
		self.Revision: int
		self.LeftAngle: float
		self.RightAngle: float
		self.LeftDampStart: float
		self.RightDamStart: float
		self.DampRatio: float

	def Read(self, Buffer: FileReader) -> 'Constraint':
		"""Reads the Constraint from the buffer"""
		self.Revision = Buffer.ReadShort()
		if self.Revision == 1:
			self.LeftAngle = Buffer.ReadFloat()
			self.RightAngle = Buffer.ReadFloat()
			self.LeftDampStart = Buffer.ReadFloat()
			self.RightDamStart = Buffer.ReadFloat()
			self.DampRatio = Buffer.ReadFloat()
		return self

	def Write(self, Buffer: FileWriter) -> 'Constraint':
		"""Writes the Constraint to the buffer"""
		Buffer.WriteShort(self.Revision)
		Buffer.WriteFloat(self.LeftAngle)
		Buffer.WriteFloat(self.RightAngle)
		Buffer.WriteFloat(self.LeftDampStart)
		Buffer.WriteFloat(self.RightDamStart)
		Buffer.WriteFloat(self.DampRatio)
		return self

class IKAtlas():
	"""IKAtlas"""
	def __init__(self) -> None:
		"""IKAtlas Constructor"""
		self.Identifier: int
		self.Version: int
		self.Axis: int
		self.ChainOrder: int
		self.Constraints: List[Constraint]
		self.PurposeFlags: int

	def Read(self, Buffer: FileReader) -> 'IKAtlas':
		"""Reads the IKAtlas from the buffer"""
		self.Identifier = Buffer.ReadInt()
		self.Version = Buffer.ReadShort()
		if self.Version >= 1:
			self.Axis = Buffer.ReadInt()
			self.ChainOrder = Buffer.ReadInt()
			self.Constraints = [Constraint().Read(Buffer) for _ in range(3)]
			if self.Version >= 2:
				self.PurposeFlags = Buffer.ReadShort()
		return self

	def Write(self, Buffer: FileWriter) -> 'IKAtlas':
		"""Writes the IKAtlas to the buffer"""
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteShort(self.Version)
		Buffer.WriteInt(self.Axis)
		Buffer.WriteInt(self.ChainOrder)
		for _Constraint in self.Constraints:
			_Constraint.Write(Buffer)
		Buffer.WriteShort(self.PurposeFlags)
		return self

class AnimationMarker():
	"""AnimationMarker"""
	def __init__(self) -> None:
		"""AnimationMarker Constructor"""
		self.Class: int
		self.Time: float
		self.Direction: Vector
		self.Position: Vector

	def Read(self, Buffer: FileReader) -> 'AnimationMarker':
		"""Reads the AnimationMarker from the buffer"""
		self.Class = Buffer.ReadInt()
		self.Time = Buffer.ReadFloat()
		self.Direction = Buffer.ReadVector3()
		self.Position = Buffer.ReadVector3()
		return self

	def Write(self, Buffer: FileWriter) -> 'AnimationMarker':
		"""Writes the AnimationMarker to the buffer"""
		Buffer.WriteInt(self.Class)
		Buffer.WriteFloat(self.Time)
		Buffer.WriteVector3(self.Direction)
		Buffer.WriteVector3(self.Position)
		return self

class AnimationMarkerSet():
	"""AnimationMarkerSet"""
	def __init__(self) -> None:
		"""AnimationMarkerSet Constructor"""
		self.AnimID: int
		self.Length: int
		self.Name: str
		self.AnimationMarkerID: int
		self.MarkerCount: int
		self.AnimationMarkers: List[AnimationMarker]

	def Read(self, Buffer: FileReader) -> 'AnimationMarkerSet':
		"""Reads the AnimationMarkerSet from the buffer"""
		self.AnimID = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.Length)
		self.AnimationMarkerID = Buffer.ReadInt()
		self.MarkerCount = Buffer.ReadInt()
		self.AnimationMarkers = [AnimationMarker().Read(Buffer) for _ in range(self.MarkerCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'AnimationMarkerSet':
		"""Writes the AnimationMarkerSet to the buffer"""
		Buffer.WriteInt(self.AnimID)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.AnimationMarkerID)
		Buffer.WriteInt(self.MarkerCount)
		for _AnimationMarker in self.AnimationMarkers:
			_AnimationMarker.Write(Buffer)
		return self

class UnknownStruct2():
	"""UnknownStruct2"""
	def __init__(self) -> None:
		"""UnknownStruct2 Constructor"""
		self.UnknownInts: List[int]

	def Read(self, Buffer: FileReader) -> 'UnknownStruct2':
		"""Reads the UnknownStruct2 from the buffer"""
		self.UnknownInts = [Buffer.ReadInt() for _ in range(5)]
		return self

	def Write(self, Buffer: FileWriter) -> 'UnknownStruct2':
		"""Writes the UnknownStruct2 to the buffer"""
		for UnknownInt in self.UnknownInts:
			Buffer.WriteInt(UnknownInt)
		return self

class UnknownStruct():
	"""UnknownStruct"""
	def __init__(self) -> None:
		"""UnknownStruct Constructor"""
		self.Unknown: int
		self.Length: int
		self.Name: str
		self.Unknown2: int
		self.Unknown3: int
		self.UnknownStructs: List[UnknownStruct2]

	def Read(self, Buffer: FileReader) -> 'UnknownStruct':
		"""Reads the UnknownStruct from the buffer"""
		self.Unknown = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.Length)
		self.Unknown2 = Buffer.ReadInt()
		self.Unknown3 = Buffer.ReadInt()
		self.UnknownStructs = [UnknownStruct2().Read(Buffer) for _ in range(self.Unknown3)]
		return self

	def Write(self, Buffer: FileWriter) -> 'UnknownStruct':
		"""Writes the UnknownStruct to the buffer"""
		Buffer.WriteInt(self.Unknown)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.Unknown2)
		Buffer.WriteInt(self.Unknown3)
		for _UnknownStruct2 in self.UnknownStructs:
			_UnknownStruct2.Write(Buffer)
		return self

class AnimationSet():
	"""AnimationSet"""
	def __init__(self) -> None:
		"""AnimationSet Constructor"""
		self.Length: int
		self.Magic: str
		self.Version: int
		self.DefaultRunSpeed: float
		self.DefaultWalkSpeed: float
		self.ModeAnimationKeyCount: int
		self.Revision: int
		self.ModeChangeType: int
		self.HoveringGround: int
		self.FlyBankScale: float
		self.FlyAccelScale: float
		self.FlyHitScale: float
		self.AllignToTerrain: int
		self.ModeAnimationKeys: List[ModeAnimationKey]
		self.HasAtlas: int
		self.AtlasCount: int
		self.IKAtlases: List[IKAtlas]
		self.UKLen: int
		self.UKInts: List[int]
		self.Subversion: int
		self.AnimationMarkerCount: int
		self.AnimationMarkerSets: List[AnimationMarkerSet]
		self.Unknown: int
		self.UnknownStructs: List[UnknownStruct]

	def Read(self, Buffer: FileReader) -> 'AnimationSet':
		"""Reads the AnimationSet from the buffer"""
		self.Length = Buffer.ReadInt()
		self.Magic = Buffer.ReadString(self.Length)
		self.Version = Buffer.ReadInt()
		self.DefaultRunSpeed = Buffer.ReadFloat()
		self.DefaultWalkSpeed = Buffer.ReadFloat()

		if self.Version == 2:
			self.ModeAnimationKeyCount = Buffer.ReadInt()
		else:
			self.Revision = Buffer.ReadInt()

		if self.Version >= 6:
			if self.Revision >= 2:
				self.ModeChangeType = Buffer.ReadByte()
				self.HoveringGround = Buffer.ReadByte()

			if self.Revision >= 5:
				self.FlyBankScale = Buffer.ReadFloat()
				self.FlyAccelScale = Buffer.ReadFloat()
				self.FlyHitScale = Buffer.ReadFloat()

			if self.Revision >= 6:
				self.AllignToTerrain = Buffer.ReadByte()

		UK:int = 0

		if self.Version == 2:
			UK = Buffer.ReadInt()
		else:
			self.ModeAnimationKeyCount = Buffer.ReadInt()

		self.ModeAnimationKeys = [ModeAnimationKey().Read(Buffer, UK) for _ in range(self.ModeAnimationKeyCount)]

		if self.Version >= 3:
			self.HasAtlas = Buffer.ReadShort()

			if self.HasAtlas >= 1:
				self.AtlasCount = Buffer.ReadInt()
				self.IKAtlases = [IKAtlas().Read(Buffer) for _ in range(self.AtlasCount)]

			if self.HasAtlas >= 2:
				self.UKLen = Buffer.ReadInt()
				self.UKInts = [Buffer.ReadInt() for _ in range(self.UKLen * 3)]

		if self.Version >= 4:
			self.Subversion = Buffer.ReadShort()

			if self.Subversion == 2:
				self.AnimationMarkerCount = Buffer.ReadInt()
				self.AnimationMarkerSets = [AnimationMarkerSet().Read(Buffer) for _ in range(self.AnimationMarkerCount)]
			elif self.Subversion == 1:
				self.Unknown = Buffer.ReadInt()
				self.UnknownStructs = [UnknownStruct().Read(Buffer) for _ in range(self.Unknown)]

		return self

	def Write(self, Buffer: FileWriter) -> 'AnimationSet':
		"""Writes the AnimationSet to the buffer"""
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Magic)
		Buffer.WriteInt(self.Version)
		Buffer.WriteFloat(self.DefaultRunSpeed)
		Buffer.WriteFloat(self.DefaultWalkSpeed)

		if self.Version == 2:
			Buffer.WriteInt(self.ModeAnimationKeyCount)
		else:
			Buffer.WriteInt(self.Revision)

		if self.Version >= 6:
			if self.Revision >= 2:
				Buffer.WriteByte(self.ModeChangeType)
				Buffer.WriteByte(self.HoveringGround)

			if self.Revision >= 5:
				Buffer.WriteFloat(self.FlyBankScale)
				Buffer.WriteFloat(self.FlyAccelScale)
				Buffer.WriteFloat(self.FlyHitScale)

			if self.Revision >= 6:
				Buffer.WriteByte(self.AllignToTerrain)

		if self.Version == 2:
			Buffer.WriteInt(0)
		else:
			Buffer.WriteInt(self.ModeAnimationKeyCount)

		for _ModeAnimationKey in self.ModeAnimationKeys:
			_ModeAnimationKey.Write(Buffer)

		if self.Version >= 3:
			Buffer.WriteShort(self.HasAtlas)

			if self.HasAtlas >= 1:
				Buffer.WriteInt(self.AtlasCount)
				for _IKAtlas in self.IKAtlases:
					_IKAtlas.Write(Buffer)

			if self.HasAtlas >= 2:
				Buffer.WriteInt(self.UKLen)
				for UKInt in self.UKInts:
					Buffer.WriteInt(UKInt)

		if self.Version >= 4:
			Buffer.WriteShort(self.Subversion)

			if self.Subversion == 2:
				Buffer.WriteInt(self.AnimationMarkerCount)
				for _AnimationMarkerSet in self.AnimationMarkerSets:
					_AnimationMarkerSet.Write(Buffer)
			elif self.Subversion == 1:
				Buffer.WriteInt(self.Unknown)
				for _UnknownStruct in self.UnknownStructs:
					_UnknownStruct.Write(Buffer)

		return self

class MeshSetGrid():
	"""MeshSetGrid class"""
	def __init__(self) -> None:
		self.Revision: int
		self.GridWidth: int
		self.GridHeight: int
		self.NameLength: int
		self.Name: str
		self.UUIDLength: int
		self.UUID: str
		self.GridRotation: int
		self.GroundDecalLength: int
		self.GroundDecal: str
		self.UKString0Length: int
		self.UKString0: str
		self.UKString1Length: int
		self.UKString1: str
		self.ModuleDistance: float
		self.IsCenterPivoted: int
		self.MeshModules: List[MeshGridModule]

	def Read(self, Buffer: FileReader) -> 'MeshSetGrid':
		"""Reads the MeshSetGrid from the buffer"""
		self.Revision = Buffer.ReadShort()
		self.GridWidth = Buffer.ReadByte()
		self.GridHeight = Buffer.ReadByte()
		self.NameLength = Buffer.ReadInt()
		self.Name = Buffer.ReadString(self.NameLength)
		self.UUIDLength = Buffer.ReadInt()
		self.UUID = Buffer.ReadString(self.UUIDLength)
		self.GridRotation = Buffer.ReadShort()
		self.GroundDecalLength = Buffer.ReadInt()
		self.GroundDecal = Buffer.ReadString(self.GroundDecalLength)
		self.UKString0Length = Buffer.ReadInt()
		self.UKString0 = Buffer.ReadString(self.UKString0Length)
		self.UKString1Length = Buffer.ReadInt()
		self.UKString1 = Buffer.ReadString(self.UKString1Length)
		self.ModuleDistance = Buffer.ReadFloat()
		self.IsCenterPivoted = Buffer.ReadByte()
		self.MeshModules = [MeshGridModule().Read(Buffer) for _ in range((self.GridWidth * 2 + 1) * (self.GridHeight * 2 + 1))]
		return self

	def Write(self, Buffer: FileWriter) -> 'MeshSetGrid':
		"""Writes the MeshSetGrid to the buffer"""
		Buffer.WriteShort(self.Revision)
		Buffer.WriteByte(self.GridWidth)
		Buffer.WriteByte(self.GridHeight)
		Buffer.WriteInt(self.NameLength)
		Buffer.WriteString(self.Name)
		Buffer.WriteInt(self.UUIDLength)
		Buffer.WriteString(self.UUID)
		Buffer.WriteShort(self.GridRotation)
		Buffer.WriteInt(self.GroundDecalLength)
		Buffer.WriteString(self.GroundDecal)
		Buffer.WriteInt(self.UKString0Length)
		Buffer.WriteString(self.UKString0)
		Buffer.WriteInt(self.UKString1Length)
		Buffer.WriteString(self.UKString1)
		Buffer.WriteFloat(self.ModuleDistance)
		Buffer.WriteByte(self.IsCenterPivoted)
		for MeshModule in self.MeshModules: MeshModule.Write(Buffer)
		return self

class DRS:
	"""DRS class"""
	def __init__(self) -> None:
		self.Magic: int = -1
		self.NumberOfModels: int = -1
		self.NodeInformationOffset: int = -1
		self.NodeHierarchyOffset: int = -1
		self.NodeCount: int = -1
		self.RootNodeInformation: RootNodeInformation = None
		self.AnimationSetNodeInformation: NodeInformation = None
		self.CDspMeshFileNodeInformation: NodeInformation = None
		self.CGeoMeshFileNodeInformation: NodeInformation = None
		self.CSkSkinInfoFileNodeInformation: NodeInformation = None
		self.CSkSkeletonFileNodeInformation: NodeInformation = None
		self.AnimationTimingsInformation: NodeInformation = None
		self.JointNodeInformation: NodeInformation = None
		self.CGeoOBBTreeInformation: NodeInformation = None
		self.DrwResourceMetaInformation: NodeInformation = None
		self.CGeoPrimitiveContainerNodeInformation: NodeInformation = None
		self.CollisionShapeNodeInformation: NodeInformation = None
		self.EffectSetNodeInformation: NodeInformation = None
		self.MeshSetGridNodeInformation: NodeInformation = None
		self.RootNode: RootNode = None
		self.AnimationSetNode: Node = None
		self.MeshNode: Node = None
		self.CGeoMeshNode: Node = None
		self.CSkSkinInfoNode: Node = None
		self.CSkSkeletonNode: Node = None
		self.AnimationTimingsNode: Node = None
		self.JointMapNode: Node = None
		self.CGeoOBBTreeNode: Node = None
		self.DrwResourceMetaNode: Node = None
		self.CGeoPrimitiveContainerNode: Node = None
		self.CollisionShapeNode: Node = None
		self.EffectSetNode: Node = None
		self.MeshSetGridNode: Node = None
		self.AnimationSet: AnimationSet = None
		self.Mesh: CDspMeshFile = None
		self.CGeoMesh: CGeoMesh = None
		self.CSkSkinInfo: CSkSkinInfo = None
		self.CSkSkeleton: CSkSkeleton = None
		# self.AnimationTimings: AnimationTimings = None
		self.Joints: CDspJointMap = None
		# self.CGeoOBBTree: CGeoOBBTree = None
		# self.DrwResourceMeta: DrwResourceMeta = None
		# self.CGeoPrimitiveContainer: CGeoPrimitiveContainer = None
		self.CollisionShape: CollisionShape = None
		# self.EffectSet: EffectSet = None
		self.MeshSetGrid: MeshSetGrid = None

	def Read(self, FileName: str) -> 'DRS':
		"""Reads the DRS from the file"""
		Reader = FileReader(FileName)
		self.Magic = Reader.ReadInt()
		self.NumberOfModels = Reader.ReadInt()
		self.NodeInformationOffset = Reader.ReadInt()
		self.NodeHierarchyOffset = Reader.ReadInt()
		self.NodeCount = Reader.ReadInt()

		if self.Magic != -981667554 or self.NodeCount < 1:
			raise TypeError("This is not a valid file. Magic: {}, NodeCount: {}".format(self.Magic, self.NodeCount))

		Reader.Seek(self.NodeInformationOffset)
		self.RootNodeInformation = RootNodeInformation().Read(Reader)

		for _ in range(self.NodeCount - 1):
			_NodeInformation = NodeInformation().Read(Reader)

			if _NodeInformation.Magic == -475734043: # AnimationSet
				self.AnimationSetNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == -1900395636: # CDspMeshFile
				self.CDspMeshFileNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == 100449016: # CGeoMesh
				self.CGeoMeshFileNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == -761174227: # CSkSkinInfo
				self.CSkSkinInfoFileNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == -2110567991: # CSkSkeleton
				self.CSkSkeletonFileNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == -1403092629: # AnimationTimings
				self.AnimationTimingsInformation = _NodeInformation
			elif _NodeInformation.Magic == -1340635850: # JointMap
				self.JointNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == -933519637: # OBBTree
				self.CGeoOBBTreeInformation = _NodeInformation
			elif _NodeInformation.Magic == -183033339: # drwResourceMeta
				self.DrwResourceMetaInformation = _NodeInformation
			elif _NodeInformation.Magic == 1396683476: # CGeoPrimitiveContainer
				self.CGeoPrimitiveContainerNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == 268607026: # collisionShape
				self.CollisionShapeNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == 688490554: # EffectSet
				self.EffectSetNodeInformation = _NodeInformation
			elif _NodeInformation.Magic == 154295579: # MeshSetgrid
				self.MeshSetGridNodeInformation = _NodeInformation
			else:
				print("Unknown NodeInformation Magic: {}".format(_NodeInformation.Magic))

		Reader.Seek(self.NodeHierarchyOffset)
		self.RootNode = RootNode().Read(Reader)

		for _ in range(self.NodeCount - 1):
			_Node = Node().Read(Reader)

			# Compare the node's name to the node information's name
			if _Node.Name == "AnimationSet":
				self.AnimationSetNode = _Node
			elif _Node.Name == "CDspMeshFile":
				self.MeshNode = _Node
			elif _Node.Name == "CGeoMesh":
				self.CGeoMeshNode = _Node
			elif _Node.Name == "CSkSkinInfo":
				self.CSkSkinInfoNode = _Node
			elif _Node.Name == "CSkSkeleton":
				self.CSkSkeletonNode = _Node
			elif _Node.Name == "AnimationTimings":
				self.AnimationTimingsNode = _Node
			elif _Node.Name == "CDspJointMap":
				self.JointMapNode = _Node
			elif _Node.Name == "CGeoOBBTree":
				self.CGeoOBBTreeNode = _Node
			elif _Node.Name == "DrwResourceMeta":
				self.DrwResourceMetaNode = _Node
			elif _Node.Name == "CGeoPrimitiveContainer":
				self.CGeoPrimitiveContainerNode = _Node
			elif _Node.Name == "collisionShape":
				self.CollisionShapeNode = _Node
			elif _Node.Name == "EffectSet":
				self.EffectSetNode = _Node
			elif _Node.Name == "MeshSetGrid":
				self.MeshSetGridNode = _Node
			else:
				print("Unknown node name: {}".format(_Node.Name))

		if self.AnimationSetNode is not None:
			Reader.Seek(self.AnimationSetNodeInformation.Offset)
			self.AnimationSet = AnimationSet().Read(Reader)

		if self.MeshNode is not None:
			Reader.Seek(self.CDspMeshFileNodeInformation.Offset)
			self.Mesh = CDspMeshFile().Read(Reader)

		if self.CGeoMeshNode is not None:
			Reader.Seek(self.CGeoMeshFileNodeInformation.Offset)
			self.CGeoMesh = CGeoMesh().Read(Reader)

		if self.CSkSkinInfoNode is not None:
			Reader.Seek(self.CSkSkinInfoFileNodeInformation.Offset)
			self.CSkSkinInfo = CSkSkinInfo().Read(Reader)

		if self.CSkSkeletonNode is not None:
			Reader.Seek(self.CSkSkeletonFileNodeInformation.Offset)
			self.CSkSkeleton = CSkSkeleton().Read(Reader)

		# if self.AnimationTimingsNode is not None:
		# 	Reader.Seek(self.AnimationTimingsInformation.Offset)
		# 	self.AnimationTimings = AnimationTimings().Read(Reader)

		# if self.JointMapNode is not None:
		# 	Reader.Seek(self.JointNodeInformation.Offset)
		# 	self.Joints = CDspJointMap().Read(Reader)

		# if self.CGeoOBBTreeNode is not None:
		# 	Reader.Seek(self.CGeoOBBTreeInformation.Offset)
		# 	self.CGeoOBBTree = CGeoOBBTree().Read(Reader)

		# if self.DrwResourceMetaNode is not None:
		# 	Reader.Seek(self.DrwResourceMetaInformation.Offset)
		# 	self.DrwResourceMeta = DrwResourceMeta().Read(Reader)

		# if self.CGeoPrimitiveContainerNode is not None:
		# 	Reader.Seek(self.CGeoPrimitiveContainerNodeInformation.Offset)
		# 	self.CGeoPrimitiveContainer = CGeoPrimitiveContainer().Read(Reader)

		if self.CollisionShapeNode is not None:
			Reader.Seek(self.CollisionShapeNodeInformation.Offset)
			self.CollisionShape = CollisionShape().Read(Reader)

		# if self.EffectSetNode is not None:
		# 	Reader.Seek(self.EffectSetNodeInformation.Offset)
		# 	self.EffectSet = EffectSet().Read(Reader)

		if self.MeshSetGridNode is not None:
			Reader.Seek(self.MeshSetGridNodeInformation.Offset)
			self.MeshSetGrid = MeshSetGrid().Read(Reader)

		return self

	def Write(self, FileName: str):
		"""Writes the DRS to the file"""
