from typing import List
from mathutils import Vector, Quaternion, Matrix

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

class RootNode():
	"""Root Node"""
	def __init__(self) -> None:
		"""Root Node Constructor"""
		self.Identifier: int = 0
		self.Unknown: int = 0
		self.Length: int = 9
		self.NodeName: str = "root name"

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
	def __init__(self, index: int = 0, name: str = "") -> None:
		"""Node Constructor"""
		self.InfoIndex: int = index
		self.Length: int = name and len(name) or 0
		self.Name: str = name or ""
		self.Zero: int = 0

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

	def Size(self) -> int:
		"""Returns the size of the Node"""
		return 12 + self.Length

class RootNodeInformation():
	"""Root Node Information"""
	def __init__(self) -> None:
		"""Root Node Constructor"""
		self.Zeroes: List[int] =[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # 16
		self.NegOne: int = -1 # 4
		self.One: int = 1 # 4
		self.NodeInformationCount: int = 0 # 4
		self.Zero: int = 0 # 4
		self.DataObject = None # 0

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

	def Size(self) -> int:
		"""Returns the size of the Root Node Information"""
		return 32
	
class NodeInformation():
	"""Node Information"""
	def __init__(self, Name: str = None, Identifier: int = -1, dataObject = None) -> None:
		"""Node Information Constructor"""
		global MagicValues
		self.Magic: int = MagicValues.get(Name, 0) or 0
		self.Identifier: int = Identifier or -1
		self.Offset: int = -1
		self.NodeSize: int = dataObject and dataObject.Size() or 0
		self.DataObject = dataObject
		self.Spacer: List[int] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

	def Read(self, Buffer: FileReader) -> 'NodeInformation':
		"""Reads the Node Information from the buffer"""
		self.Magic = Buffer.ReadInt() # 4
		self.Identifier = Buffer.ReadInt() # 4
		self.Offset = Buffer.ReadInt() # 4
		self.NodeSize = Buffer.ReadInt() # 4
		self.Spacer = Buffer.ReadByte(16) # 16
		return self

	def Write(self, Buffer: FileWriter) -> 'NodeInformation':
		"""Writes the Node Information to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.Identifier)
		Buffer.WriteInt(self.Offset)
		Buffer.WriteInt(self.NodeSize)
		Buffer.WriteByte(self.Spacer)
		return self
	
	def UpdateOffset(self, Offset: int) -> None:
		"""Updates the Offset of the Node Information"""
		self.Offset = Offset

	def Size(self) -> int:
		"""Returns the size of the Node Information"""
		return 32
	



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

class DRSBone():
	"""docstring for DRSBone"""
	def __init__(self) -> None:
		self.SKAIdentifier: int
		self.Identifier: int
		self.Name: str
		self.Parent: int = -1
		self.BoneMatrix: Matrix
		self.Children: List[int]
		self.BindLoc: Vector
		self.BindRot: Quaternion

class CSkSkeleton():
	"""CSkSkeleton"""
	def __init__(self) -> None:
		"""CSkSkeleton Constructor"""
		self.Magic: int = 1558308612
		self.Version: int = 3
		self.BoneMatrixCount: int
		self.BoneMatrices: List[BoneMatrix]
		self.BoneCount: int
		self.Bones: List[Bone]
		self.SuperParent: Matrix = Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))

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

	def Size(self) -> int:
		"""Returns the size of the CSkSkeleton"""
		add = 0
		for bone in self.Bones:
			add += 16 + 4 * bone.ChildCount + bone.NameLength
		return 80 + 64 * self.BoneMatrixCount + add

class AnimationSet():
	"""AnimationSet"""
	def __init__(self, animation_file_name: str = "") -> None:
		"""AnimationSet Constructor"""
		self.Length: int = 11
		self.Magic: str = "Battleforge"
		self.Version: int = 6
		# Is used by the game to determine the animation speed when walking/running
		self.DefaultRunSpeed: float = 4.8 # TODO: Add a way to show/edit this value in Blender
		self.DefaultWalkSpeed: float = 2.4 # TODO: Add a way to show/edit this value in Blender
		self.Revision: int = 6 # TODO: Is it all the time?
		self.ModeAnimationKeyCount: int = 1 # How many different animations are there?
		# TODO find out how often these values are used and for which object/unit/building types
		self.ModeChangeType: int = 0
		self.HoveringGround: int = 0
		self.FlyBankScale: float = 1 # Changes for flying units
		self.FlyAccelScale: float = 0 # Changes for flying units
		self.FlyHitScale: float = 1 # Changes for flying units
		self.AllignToTerrain: int = 0
		# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
		self.ModeAnimationKeys: List[ModeAnimationKey] = []
		if animation_file_name != "": # So we can still import original drs files
			# Assure the name end with '.ska'
			if not animation_file_name.endswith(".ska"):
				animation_file_name += ".ska"
			for _ in range(self.ModeAnimationKeyCount):
				self.ModeAnimationKeys.append(ModeAnimationKey(animation_file_name))
		self.HasAtlas: int = 1 # 1 or 2
		self.AtlasCount: int = 0 # Animated Objects: 0
		self.IKAtlases: List[IKAtlas] = []
		self.UKLen: int = 0 # TODO: Always 0?
		self.UKInts: List[int] = []
		self.Subversion: int = 2 # TODO: Always 2?
		self.AnimationMarkerCount: int = 0 # Animated Objects: 0
		self.AnimationMarkerSets: List[AnimationMarkerSet] = []
		self.Unknown: int # Not needed
		self.UnknownStructs: List[UnknownStruct] # Not needed

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

	def Size(self) -> int:
		"""Returns the size of the AnimationSet"""
		add = 0
		for Key in self.ModeAnimationKeys:
			add += Key.Size()
		return 62 + add
	





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


class DRS():
	"""DRS class"""
	def __init__(self) -> None:
		self.operator = None
		self.context = None
		self.keywords = None
		self.Magic: int = -981667554
		self.NumberOfModels: int = 1
		self.NodeInformationOffset: int = 41 # 20 cause of the header + 21 cause of the root node
		self.NodeHierarchyOffset: int = 20 # 20 cause of the header
		self.dataOffset: int = 41 + 32 # 32 cause of the root node information
		self.NodeCount: int = 1 # RootNode is always present
		self.Nodes: List[Node] = [RootNode()]
		self.NodeInformations: List[NodeInformation | NodeInformation] = [RootNodeInformation()]
		self.AnimationSetNode: Node = None
		self.CDspMeshFileNode: Node = None
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
		self.CDrwLocatorListNode: Node = None
		self.AnimationSet: AnimationSet = None
		self.CDspMeshFile: CDspMeshFile = None
		self.CGeoMesh: CGeoMesh = None
		self.CSkSkinInfo: CSkSkinInfo = None
		self.CSkSkeleton: CSkSkeleton = None
		# self.AnimationTimings: AnimationTimings = None
		self.Joints: CDspJointMap = None
		self.CGeoOBBTree: CGeoOBBTree = None
		self.DrwResourceMeta: DrwResourceMeta = None
		self.CGeoPrimitiveContainer: CGeoPrimitiveContainer = None
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
			elif _NodeInformation.Magic == 735146985: # CDrwLocatorList
				self.CDrwLocatorListNodeInformation = _NodeInformation
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
				self.CDspMeshFileNode = _Node
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
			elif _Node.Name == "CDrwLocatorList":
				self.CDrwLocatorListNode = _Node
			else:
				print("Unknown node name: {}".format(_Node.Name))

		if self.AnimationSetNode is not None:
			Reader.Seek(self.AnimationSetNodeInformation.Offset)
			self.AnimationSet = AnimationSet().Read(Reader)

		if self.CDspMeshFileNode is not None:
			Reader.Seek(self.CDspMeshFileNodeInformation.Offset)
			self.CDspMeshFile = CDspMeshFile().Read(Reader)

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

		if self.CGeoOBBTreeNode is not None:
			Reader.Seek(self.CGeoOBBTreeInformation.Offset)
			self.CGeoOBBTree = CGeoOBBTree().Read(Reader)

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

	def PushNode(self, name: str, dataObject):
		"""Pushes a new node to the DRS"""
		NewNode = Node(self.NodeCount, name)
		self.Nodes.append(NewNode)
		self.NodeInformationOffset += NewNode.Size()
		self.dataOffset += NewNode.Size()
		self.NodeInformations[0].NodeInformationCount += 1
		self.PushNodeInformation(name, self.NodeInformations[0].NodeInformationCount, dataObject)
		self.NodeCount += 1

	def PushNodeInformation(self, name: str, identifier: int, dataObject):
		"""Pushes a new node information to the DRS"""
		NewNodeInformation = NodeInformation(name, identifier, dataObject)
		self.NodeInformations.append(NewNodeInformation)
		self.dataOffset += NewNodeInformation.Size()

	def Save(self, FileName: str):
		"""Saves the DRS to the file"""
		# Open the file
		Writer = FileWriter(FileName +  "_new.drs")
		# Write the header
		Writer.WriteInt(self.Magic)
		Writer.WriteInt(self.NumberOfModels)
		Writer.WriteInt(self.NodeInformationOffset)
		Writer.WriteInt(self.NodeHierarchyOffset)
		Writer.WriteInt(self.NodeCount)
		# Write the nodes
		for _Node in self.Nodes:
			_Node.Write(Writer)
		# Write the node informations
		for _NodeInformation in self.NodeInformations:
			# Root Node Check, check if the _NodeInformation has a data object attribute
			if _NodeInformation.DataObject is None:
				# Root Node
				_NodeInformation.Write(Writer)
				continue
			_NodeInformation.UpdateOffset(self.dataOffset)
			self.dataOffset += _NodeInformation.NodeSize
			_NodeInformation.Write(Writer)
		# Write the data objects
		for _NodeInformation in self.NodeInformations:
			if _NodeInformation.DataObject is not None:
				_NodeInformation.DataObject.Write(Writer)

		# Close the file
		Writer.Close()

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


