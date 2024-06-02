from typing import List
from mathutils import Vector, Matrix

from .file_io import FileReader, FileWriter

# Create a enum or dictionary for the magic values
MagicValues = {
	"CDspJointMap": -1340635850,
	"CGeoMesh": 100449016,
	"CGeoOBBTree": -933519637,
	"CSkSkinInfo": -761174227,
	"CDspMeshFile": -1900395636,
	"DrwResourceMeta": -183033339,
	"collisionShape": 268607026,
	"CGeoPrimitiveContainer": 1396683476
}

AnimationType = {
	"CastResolve": 0,
	"Spawn": 1,
	"Melee": 2,
	"Channel": 3,
	"ModeSwitch": 4, 
	"WormMovement": 5,
}

class Vertex():
    """Vertex"""
    def __init__(self, Position = None, Normal = None, Texture = None, Tangent = None, Bitangent = None, RawWeights = None, BoneIndices = None) -> None:
        """Vertex Constructor"""
        self.Position: Vector = Position
        self.Normal: Vector = Normal
        self.Texture: Vector = Texture
        self.Tangent: Vector = Tangent
        self.Bitangent: Vector = Bitangent
        self.RawWeights: List[int] = RawWeights
        self.BoneIndices: List[int] = BoneIndices

    def Read(self, Buffer: FileReader, Revision: int) -> 'Vertex':
        """Reads the Vertex from the buffer"""
        match Revision:
            case 133121:
                self.Position = Buffer.ReadVector3()
                self.Normal = Buffer.ReadVector3()
                self.Texture = Buffer.ReadVector2()
            case 12288:
                self.Tangent = Buffer.ReadVector3()
                self.Bitangent = Buffer.ReadVector3()
            case 12:
                self.RawWeights = Buffer.ReadByte(4)
                self.BoneIndices = Buffer.ReadByte(4)

        return self

    def Write(self, Buffer: FileWriter) -> 'Vertex':
        """Writes the Vertex to the buffer"""
        if self.Position is not None:
            Buffer.WriteVector3(self.Position)
        if self.Normal is not None:
            Buffer.WriteVector3(self.Normal)
        if self.Texture is not None:
            Buffer.WriteVector2(self.Texture)
        if self.Tangent is not None:
            Buffer.WriteVector3(self.Tangent)
        if self.Bitangent is not None:
            Buffer.WriteVector3(self.Bitangent)
        if self.RawWeights is not None:
            Buffer.WriteByte(self.RawWeights)
        if self.BoneIndices is not None:
            Buffer.WriteByte(self.BoneIndices)

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

	def Size(self) -> int:
		"""Returns the size of the Mesh Data"""
		Size = 8
		Size += self.VertexSize * len(self.Vertices)
		return Size
      

class Texture():
	"""Texture"""
	def __init__(self) -> None:
		"""Texture Constructor"""
		self.Identifier: int
		self.Length: int
		self.Name: str
		self.Spacer: int = 0

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
		self.Length: int = 0
		self.Textures: List[Texture] = []

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


class Material():
	"""Material"""
	def __init__(self, index = None) -> None:
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

		if index is not None:
			if index == 0:
				self.Identifier = 1668510769
				self.Smoothness = 0
			elif index == 1:
				self.Identifier = 1668510770
				self.Metalness = 0
			elif index == 2:
				self.Identifier = 1668510771
				self.Reflectivity = 0
			elif index == 3:
				self.Identifier = 1668510772
				self.Emissivity = 0
			elif index == 4:
				self.Identifier = 1668510773
				self.RefractionScale = 1
			elif index == 5:
				self.Identifier = 1668510774
				self.DistortionMeshScale = 0
			elif index == 6:
				self.Identifier = 1935897704
				self.Scratch = 0
			elif index == 7:
				self.Identifier = 1668510775
				self.SpecularScale = 1.5
			elif index == 8:
				self.Identifier = 1668510776
				self.WindResponse = 0 # Needs to be updated
			elif index == 9:
				self.Identifier = 1668510777
				self.WindHeight = 0 # Needs to be updated
			elif index == 10:
				self.Identifier = 1935893623
				self.DepthWriteThreshold = 0.5
			elif index == 11:
				self.Identifier = 1668510785
				self.Saturation = 1.0


class Material():
    """Material"""
    def __init__(self, index = None) -> None:
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

        if index is not None:
            match index:
                case 0:
                    self.Identifier = 1668510769
                    self.Smoothness = 0
                case 1:
                    self.Identifier = 1668510770
                    self.Metalness = 0
                case 2:
                    self.Identifier = 1668510771
                    self.Reflectivity = 0
                case 3:
                    self.Identifier = 1668510772
                    self.Emissivity = 0
                case 4:
                    self.Identifier = 1668510773
                    self.RefractionScale = 1
                case 5:
                    self.Identifier = 1668510774
                    self.DistortionMeshScale = 0
                case 6:
                    self.Identifier = 1935897704
                    self.Scratch = 0
                case 7:
                    self.Identifier = 1668510775
                    self.SpecularScale = 1.5
                case 8:
                    self.Identifier = 1668510776
                    self.WindResponse = 0 # Needs to be updated
                case 9:
                    self.Identifier = 1668510777
                    self.WindHeight = 0 # Needs to be updated
                case 10:
                    self.Identifier = 1935893623
                    self.DepthWriteThreshold = 0.5
                case 11:
                    self.Identifier = 1668510785
                    self.Saturation = 1.0

    def Read(self, Buffer: FileReader) -> 'Material':
        """Reads the Material from the buffer"""
        self.Identifier = Buffer.ReadInt()
        match self.Identifier:
            case 1668510769:
                self.Smoothness = Buffer.ReadFloat()
            case 1668510770:
                self.Metalness = Buffer.ReadFloat()
            case 1668510771:
                self.Reflectivity = Buffer.ReadFloat()
            case 1668510772:
                self.Emissivity = Buffer.ReadFloat()
            case 1668510773:
                self.RefractionScale = Buffer.ReadFloat()
            case 1668510774:
                self.DistortionMeshScale = Buffer.ReadFloat()
            case 1935897704:
                self.Scratch = Buffer.ReadFloat() # Only touch if ScratchMap is present
            case 1668510775:
                self.SpecularScale = Buffer.ReadFloat() # Reflectioness
            case 1668510776:
                self.WindResponse = Buffer.ReadFloat() # Wind Force 0 -> 0.1
            case 1668510777:
                self.WindHeight = Buffer.ReadFloat() # Wind Attack Height at maximum unit height
            case 1935893623:
                self.DepthWriteThreshold = Buffer.ReadFloat()
            case 1668510785:
                self.Saturation = Buffer.ReadFloat()

            case _:
                # Unknown Property, add to the list
                self.Unknown = Buffer.ReadFloat()
                raise TypeError("Unknown Material {}".format(self.Unknown))
        return self

    def Write(self, Buffer: FileWriter) -> 'Material':
        """Writes the Material to the buffer"""
        Buffer.WriteInt(self.Identifier)
        match self.Identifier:
            case 1668510769:
                Buffer.WriteFloat(self.Smoothness)
            case 1668510770:
                Buffer.WriteFloat(self.Metalness)
            case 1668510771:
                Buffer.WriteFloat(self.Reflectivity)
            case 1668510772:
                Buffer.WriteFloat(self.Emissivity)
            case 1668510773:
                Buffer.WriteFloat(self.RefractionScale)
            case 1668510774:
                Buffer.WriteFloat(self.DistortionMeshScale)
            case 1935897704:
                Buffer.WriteFloat(self.Scratch)
            case 1668510775:
                Buffer.WriteFloat(self.SpecularScale)
            case 1668510776:
                Buffer.WriteFloat(self.WindResponse)
            case 1668510777:
                Buffer.WriteFloat(self.WindHeight)
            case 1935893623:
                Buffer.WriteFloat(self.DepthWriteThreshold)
            case 1668510785:
                Buffer.WriteFloat(self.Saturation)

            case _:
                # Unknown Property, add to the list
                Buffer.WriteFloat(self.Unknown)
                raise TypeError("Unknown Material {}".format(self.Unknown))
        return self


class Materials():
	"""Materials"""
	def __init__(self) -> None:
		"""Materials Constructor"""
		self.Length: int = 12
		self.Materials: List[Material] = [Material(_) for _ in range(self.Length)]

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
	

class Refraction():
	"""Refraction"""
	def __init__(self) -> None:
		"""Refraction Constructor"""
		self.Length: int
		self.Identifier: int = 1668510769
		self.RGB: List[float] = [0, 0, 0]

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

class LevelOfDetail():
	"""LevelOfDetail"""
	def __init__(self) -> None:
		"""LevelOfDetail Constructor"""
		self.Length: int = 1
		self.LODLevel: int = 2

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
		self.Length: int = 0
		self.UnknwonString: str = ""

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
		self.Length: int = 4
		self.MaxFlowSpeedIdentifier: int = 1668707377
		self.MaxFlowSpeed: Vector = Vector((0, 0, 0, 0))
		self.MinFlowSpeedIdentifier: int = 1668707378
		self.MinFlowSpeed: Vector = Vector((0, 0, 0, 0))
		self.FlowSpeedChangeIdentifier: int = 1668707379
		self.FlowSpeedChange: Vector = Vector((0, 0, 0, 0))
		self.FlowScaleIdentifier: int = 1668707380
		self.FlowScale: Vector = Vector((0, 0, 0, 0))

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
		self.VertexCount: int # 4
		self.FaceCount: int # 4
		self.Faces: List[Face] # 6 * FaceCount
		self.MeshCount: int # 1
		self.MeshData: List[MeshData]
		self.BoundingBoxLowerLeftCorner: Vector # 12
		self.BoundingBoxUpperRightCorner: Vector # 12
		self.MaterialID: int # 2
		self.MaterialParameters: int # 4
		self.MaterialStuff: int # 4
		self.BoolParameter: int # 4
		self.Textures: Textures # Individual Length
		self.Refraction: Refraction # 20
		self.Materials: Materials # 100
		self.LevelOfDetail: LevelOfDetail # 8 Only if MaterialParameters == -86061050
		self.EmptyString: EmptyString # 4 Only if MaterialParameters == -86061050
		self.Flow: Flow # 84 Only if MaterialParameters == -86061050

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
		elif self.MaterialParameters == -86061051:
			self.MaterialStuff = Buffer.ReadInt()
			self.BoolParameter = Buffer.ReadInt()
			self.Textures = Textures().Read(Buffer)
			self.Refraction = Refraction().Read(Buffer)
			self.Materials = Materials().Read(Buffer)
			self.LevelOfDetail = LevelOfDetail().Read(Buffer)
			self.EmptyString = EmptyString().Read(Buffer)
		elif self.MaterialParameters == -86061055:
			self.BoolParameter = Buffer.ReadInt()
			self.Textures = Textures().Read(Buffer)
			self.Refraction = Refraction().Read(Buffer)
			self.Materials = Materials().Read(Buffer)
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
		elif self.MaterialParameters == -86061055:
			Buffer.WriteInt(self.BoolParameter)
			self.Textures.Write(Buffer)
			self.Refraction.Write(Buffer)
			self.Materials.Write(Buffer)
		else:
			raise TypeError("Unknown MaterialParameters {}".format(self.MaterialParameters))
		return self

	def Size(self) -> int:
		"""Returns the size of the BattleforgeMesh"""
		Size = 8 # VertexCount + FaceCount
		for _ in self.Faces:
			Size += 6
		Size += 1 # MeshCount
		for Mesh in self.MeshData:
			Size += Mesh.Size()
		Size += 12 + 12 + 2 + 4 + 4 + 4
		for T in self.Textures.Textures:
			Size += 12 + T.Length
		Size += 20 + 100 + (self.MaterialParameters == -86061050 and 8 + 4 + 84 + 4 or 0)
		return Size


class CDspMeshFile():
	"""CDspMeshFile"""
	def __init__(self) -> None:
		"""CDspMeshFile Constructor"""
		self.Magic: int = 1314189598 # 4
		self.Zero: int = 0 # 4
		self.MeshCount: int = 0 # 4
		self.BoundingBoxLowerLeftCorner: Vector = Vector((0, 0, 0)) # 12
		self.BoundingBoxUpperRightCorner: Vector = Vector((0, 0, 0)) # 12
		self.Meshes: List[BattleforgeMesh] = []
		self.SomePoints: List[Vector] = [(0,0,0,1),(1,1,0,1),(0,0,1,1)] # 48

	def Read(self, Buffer: FileReader) -> 'CDspMeshFile':
		"""Reads the CDspMeshFile from the buffer"""
		self.Magic = Buffer.ReadInt() # 4
		if self.Magic == 1314189598:
			self.Zero = Buffer.ReadInt() # 4
			self.MeshCount = Buffer.ReadInt() # 4
			self.BoundingBoxLowerLeftCorner = Buffer.ReadVector3() # 12
			self.BoundingBoxUpperRightCorner = Buffer.ReadVector3() # 12
			self.Meshes = [BattleforgeMesh().Read(Buffer) for _ in range(self.MeshCount)]
			self.SomePoints = [Buffer.ReadVector4() for _ in range(3)] # 48
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

	def Size(self) -> int:
		"""Returns the size of the CDspMeshFile"""
		Size = 84 # Magic + Zero + MeshCount + BoundingBoxLowerLeftCorner + BoundingBoxUpperRightCorner
		for Mesh in self.Meshes:
			Size += Mesh.Size()
		return Size