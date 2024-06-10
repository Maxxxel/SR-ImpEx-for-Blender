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

AnimationType = {
	"CastResolve": 0,
	"Spawn": 1,
	"Melee": 2,
	"Channel": 3,
	"ModeSwitch": 4, 
	"WormMovement": 5,
}


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


class CGeoMesh():
	"""CGeoMesh"""
	def __init__(self) -> None:
		"""CGeoMesh Constructor"""
		self.Magic: int = 1
		self.IndexCount: int
		self.Faces: List[Face]
		self.VertexCount: int
		self.Vertices: List[Vector]

	def Read(self, Buffer: FileReader) -> 'CGeoMesh':
		"""Reads the CGeoMesh from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.IndexCount = Buffer.ReadInt()
		self.Faces = [Face().Read(Buffer) for _ in range(int(self.IndexCount / 3))]
		self.VertexCount = Buffer.ReadInt()
		self.Vertices = [Buffer.ReadVector4() for _ in range(self.VertexCount)]

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

		return self

	def Size(self) -> int:
		"""Returns the size of the CGeoMesh"""
		return 12 + 6 * len(self.Faces) + 16 * len(self.Vertices)
	

class CSkSkinInfo():
	"""CSkSkinInfo"""
	def __init__(self) -> None:
		"""CSkSkinInfo Constructor"""
		self.Version: int = 1
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
	
	def Size(self) -> int:
		"""Returns the size of the CSkSkinInfo"""
		return 8 + 32 * self.VertexCount
	

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
	

class ModeAnimationKey():
	"""ModeAnimationKey"""
	def __init__(self, animation_file_name: str = "") -> None:
		"""ModeAnimationKey Constructor"""
		self.Type: int = 6 # TODO: Is this always 6?
		self.Length: int = 11
		self.File: str = "Battleforge"
		self.Unknown: int = 2 # TODO: Is this always 2?
		self.Unknown2: int = 3 # TODO: Is this always 3?
		self.VisJob: int = 0 # Short. 0 for Animated Objects else it can be used to link this animation key to an animation tag ID from the AnimationTimings
		self.Unknown3: int = 3 # TODO: Is this always 3?
		self.Unknown4: int = 0 # Short. TODO: Is this always 0?
		self.VariantCount: int = 1 # 1 for animated objects, units can have more variants per animation if needed.
		self.AnimationSetVariants: List[AnimationSetVariant] = []
		if animation_file_name != "":
			for _ in range(self.VariantCount):
				self.AnimationSetVariants.append(AnimationSetVariant(animation_file_name=animation_file_name))

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
			self.Unknown2 = Buffer.ReadInt()
			self.VisJob = Buffer.ReadShort()
			self.Unknown3 = Buffer.ReadInt()
			self.Unknown4 = Buffer.ReadShort()
		self.VariantCount = Buffer.ReadInt()
		self.AnimationSetVariants = [AnimationSetVariant().Read(Buffer) for _ in range(self.VariantCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'ModeAnimationKey':
		"""Writes the ModeAnimationKey to the buffer"""
		Buffer.WriteInt(self.Type)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.File)
		Buffer.WriteInt(self.Unknown)
		Buffer.WriteInt(self.Unknown2)
		Buffer.WriteShort(self.VisJob)
		Buffer.WriteInt(self.Unknown3)
		Buffer.WriteShort(self.Unknown4)
		Buffer.WriteInt(self.VariantCount)
		for _AnimationSetVariant in self.AnimationSetVariants:
			_AnimationSetVariant.Write(Buffer)
		return self
	
	def Size(self) -> int:
		"""Returns the size of the ModeAnimationKey"""
		add = 0
		for Variant in self.AnimationSetVariants:
			add += Variant.Size()
		return 39 + add
	

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
	

class AnimationSetVariant():
	"""AnimationSetVariant"""
	def __init__(self, weight: int = 100, animation_file_name: str = "") -> None:
		"""AnimationSetVariant Constructor"""
		self.Version: int = 7 # 6 or 7
		self.Weight: int = weight # Maximum 100 in sum for all Variants
		self.Length: int = len(animation_file_name)
		self.File: str = animation_file_name
		self.Start: float = 0 # TODO: Sometimes it isnt 0, why?
		self.End: float = 1 # TODO: always 1?
		self.AllowsIK: int = 1 # TODO: Most of the time 1?
		self.Unknown2: int = 0 # TODO: Most of the time 0?

	def Read(self, Buffer: FileReader) -> 'AnimationSetVariant':
		"""Reads the AnimationSetVariant from the buffer"""
		self.Version = Buffer.ReadInt()
		self.Weight = Buffer.ReadInt()
		self.Length = Buffer.ReadInt()
		self.File = Buffer.ReadString(self.Length)

		if self.Version >= 4:
			self.Start = Buffer.ReadFloat()
			self.End = Buffer.ReadFloat()

		if self.Version >= 5:
			self.AllowsIK = Buffer.ReadByte()

		if self.Version >= 7:
			self.Unknown2 = Buffer.ReadByte()

		return self

	def Write(self, Buffer: FileWriter) -> 'AnimationSetVariant':
		"""Writes the AnimationSetVariant to the buffer"""
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.Weight)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.File)
		Buffer.WriteFloat(self.Start)
		Buffer.WriteFloat(self.End)
		Buffer.WriteByte(self.AllowsIK)
		Buffer.WriteByte(self.Unknown2)
		return self

	def Size(self) -> int:
		"""Returns the size of the AnimationSetVariant"""
		return 21 + self.Length


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
		self.CDspMeshFileData: CDspMeshFile = None
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
		self.IsSkinned: bool = False

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
				self.IsSkinned = True
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
			self.CDspMeshFileData = CDspMeshFile().Read(Reader)

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





class OBBNode():
	"""OBBNode class"""
	def __init__(self) -> None:
		"""Initializes the OBBNode"""
		self.OrientedBoundingBox: CMatCoordinateSystem
		self.Unknown1: int
		self.Unknown2: int
		self.Unknown3: int
		self.NodeDepth: int
		self.CurrentTriangleCount: int
		self.MinimumTrianglesFound: int

	def Read(self, Buffer: FileReader) -> 'OBBNode':
		"""Reads the OBBNode from the buffer"""
		self.OrientedBoundingBox = CMatCoordinateSystem().Read(Buffer)
		self.Unknown1 = Buffer.ReadUShort()
		self.Unknown2 = Buffer.ReadUShort()
		self.Unknown3 = Buffer.ReadUShort()
		self.NodeDepth = Buffer.ReadUShort()
		self.CurrentTriangleCount = Buffer.ReadInt()
		self.MinimumTrianglesFound = Buffer.ReadInt()
		return self

	def Write(self, Buffer: FileWriter) -> 'OBBNode':
		"""Writes the OBBNode to the buffer"""
		self.OrientedBoundingBox.Write(Buffer)
		Buffer.WriteInt(self.Unknown1)
		Buffer.WriteInt(self.Unknown2)
		Buffer.WriteInt(self.Unknown3)
		Buffer.WriteInt(self.NodeDepth)
		Buffer.WriteInt(self.CurrentTriangleCount)
		Buffer.WriteInt(self.MinimumTrianglesFound)
		return self

class CGeoOBBTree():
	"""CGeoOBBTree class"""
	def __init__(self) -> None:
		"""Initializes the CGeoOBBTree"""
		self.Magic: int = 1845540702
		self.Version: int = 3
		self.MatrixCount: int = 0
		self.OBBNodes: List[OBBNode] = []
		self.TriangleCount: int = 0
		self.Faces: List[Face] = []

	def Read(self, Buffer: FileReader) -> 'CGeoOBBTree':
		"""Reads the CGeoOBBTree from the buffer"""
		self.Magic = Buffer.ReadInt()
		self.Version = Buffer.ReadInt()
		self.MatrixCount = Buffer.ReadInt()
		self.OBBNodes = [OBBNode().Read(Buffer) for _ in range(self.MatrixCount)]
		self.TriangleCount = Buffer.ReadInt()
		self.Faces = [Face().Read(Buffer) for _ in range(self.TriangleCount)]
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoOBBTree':
		"""Writes the CGeoOBBTree to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteInt(self.Version)
		Buffer.WriteInt(self.MatrixCount)
		if self.MatrixCount > 0:
			for _OBBNode in self.OBBNodes:
				_OBBNode.Write(Buffer)
		Buffer.WriteInt(self.TriangleCount)
		for _Face in self.Faces: _Face.Write(Buffer)
		return self

	def Size(self) -> int:
		"""Returns the size of the CGeoOBBTree"""
		return 16 + 24 * len(self.OBBNodes) + 6 * len(self.Faces)
	

class JointGroup():
	"""JointGroup"""
	def __init__(self) -> None:
		"""JointGroup Constructor"""
		self.JointCount: int = 0
		self.Joints: List[int] = [] # Sorted by Bone Identifier Appearance in the Skeleton.Bones List

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
		self.Version: int = 1
		self.JointGroupCount: int = 0
		self.JointGroups: List[JointGroup] = []

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

	def Size(self) -> int:
		"""Returns the size of the CDspJointMap"""
		return 8 # For now, as we dont have JointGroups yet
	

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
		Buffer.WriteMatrix3x3(self.Matrix)
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

class BoxShape():
	"""Box"""
	def __init__(self) -> None:
		"""Box Constructor"""
		self.CoordSystem: CMatCoordinateSystem
		self.CGeoAABox: CGeoAABox

	def Read(self, Buffer: FileReader) -> 'BoxShape':
		"""Reads the Box from the buffer"""
		self.CoordSystem = CMatCoordinateSystem().Read(Buffer)
		self.CGeoAABox = CGeoAABox().Read(Buffer)
		return self

	def Write(self, Buffer: FileWriter) -> 'BoxShape':
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

class CylinderShape():
	"""Cylinder"""
	def __init__(self) -> None:
		"""Cylinder Constructor"""
		self.CoordSystem: CMatCoordinateSystem
		self.CGeoCylinder: CGeoCylinder

	def Read(self, Buffer: FileReader) -> 'CylinderShape':
		"""Reads the Cylinder from the buffer"""
		self.CoordSystem = CMatCoordinateSystem().Read(Buffer)
		self.CGeoCylinder = CGeoCylinder().Read(Buffer)
		return self

	def Write(self, Buffer: FileWriter) -> 'CylinderShape':
		"""Writes the Cylinder to the buffer"""
		self.CoordSystem.Write(Buffer)
		self.CGeoCylinder.Write(Buffer)
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

class SphereShape():
	"""CGeoSphere"""
	def __init__(self) -> None:
		"""CGeoSphere Constructor"""
		self.CoordSystem: CMatCoordinateSystem
		self.CGeoSphere: CGeoSphere

	def Read(self, Buffer: FileReader) -> 'CGeoSphere':
		"""Reads the CGeoSphere from the buffer"""
		self.CoordSystem = CMatCoordinateSystem().Read(Buffer)
		self.CGeoSphere = CGeoSphere().Read(Buffer)
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoSphere':
		"""Writes the CGeoSphere to the buffer"""
		self.CoordSystem.Write(Buffer)
		self.CGeoSphere.Write(Buffer)
		return self

class CollisionShape():
	"""CollisionShape"""
	def __init__(self) -> None:
		"""CollisionShape Constructor"""
		self.Version: int = 1
		self.BoxCount: int = 0
		self.Boxes: List[BoxShape] = []
		self.SphereCount: int = 0
		self.Spheres: List[SphereShape] = []
		self.CylinderCount: int = 0
		self.Cylinders: List[CylinderShape] = []

	def Read(self, Buffer: FileReader) -> 'CollisionShape':
		"""Reads the CollisionShape from the buffer"""
		# Some Files have a different Layout. Needs Investigation, we dont import These Values anyway!
		# self.Version = Buffer.ReadByte()
		# self.BoxCount = Buffer.ReadInt()
		# self.Boxes = [BoxShape().Read(Buffer) for _ in range(self.BoxCount)]
		# self.SphereCount = Buffer.ReadInt()
		# self.Spheres = [SphereShape().Read(Buffer) for _ in range(self.SphereCount)]
		# self.CylinderCount = Buffer.ReadInt()
		# self.Cylinders = [CylinderShape().Read(Buffer) for _ in range(self.CylinderCount)]
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

	def Size(self) -> int:
		"""Returns the size of the CollisionShape"""
		return 68 * self.CylinderCount + 72 * self.BoxCount + 64 * self.SphereCount + 13























class Timing():
	'''Timing'''
	def __init__(self) -> None:
		'''Timing Constructor'''
		self.CastMs: int # Int
		self.ResolveMs: int # Int
		self.UK1: float # Float
		self.UK2: float # Float
		self.UK3: float # Float
		self.AnimationMarkerID: int # Int
		# NOTICE:
		# When tying the visual animation to the game logic,
		# the castMs/resolveMs seem to get converted into game ticks by simply dividing them by 100.
		# So while the visual part of the animation is handled in milliseconds,
		# the maximum precision for the game logic is in deciseconds/game ticks.
		#
		# Meaning of the variables below:
		# For type Spawn:
		# castMs is the duration it will take until the unit can be issued commands or lose damage immunity
		# If castMs is for zero game ticks (< 100), then the animation is skipped entirely.
		# If castMs is for exactly one game tick (100-199), it seems to bug out.
		# Therefore the minimum value here should be 200, if you wish to play a spawn animation.
		# resolveMs is the duration the spawn animation will play out for in total.
		# This should match the total time from the .ska file, otherwise it looks weird.
		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
		#
		# For type CastResolve:
		# castMs is the duration it will take the unit to start casting its ability (can still be aborted)
		# If castMs is for zero game ticks (< 100), then the ability skips the cast stage
		# and instantly moves onto the resolve stage.
		# resolveMs is the duration it will take the unit to finish casting its ability (cannot be aborted)
		# It seems the stage cannot be skipped and uses a minimum duration of 1 game tick,
		# even if a value < 100 is specified.
		# The animation is automatically slowed down/sped up based on these timings.
		# The total time from the .ska file is ignored.
		#
		# For type ModeSwitch:
		# castMs is the duration it will take the unit to start its mode switch animation.
		# If castMs is for zero game ticks (< 100), then the mode switch is done instantly
		# and also does not interrupt movement. During castMs, any commands are blocked.
		# resolveMs seems to be ignored here. The unit can be issued new commands after the cast time.
		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
		#
		# For type Melee/WormMovement No experiments conducted yet.
		#  castMs;
		#  resolveMs;
		# at uk1;
		# at uk2;
		# 
		# Can be used to link an AnimationMarkerSet to a timing.
		# Relevant field: AnimationMarkerSet.animationMarkerID
		#
		# Seems to be often used for Spawn animations.
		# In cases where e.g. the animationTagID is used,
		# the animationMarkerID usually not referenced anywhere.

class TimingVariant():
	'''TimingVariant'''
	def __init__(self) -> None:
		'''TimingVariant Constructor'''
		self.Weight: int # Byte. The weight of this variant. The higher the weight, the more likely it is to be chosen.
		self.VariantIndex: int # Byte.
		self.TimingCount: int # Short. The number of Timings for this Variant. Most of the time, this is 1.
		self.Timings: List[Timing]

class AnimationTiming():
	'''AnimationTiming'''
	def __init__(self) -> None:
		'''AnimationTiming Constructor'''
		self.AnimationType: int = AnimationType['CastResolve']
		self.AnimationTagID: int = 0
		self.IsEnterModeAnimation: int = 0 # Short. This is 1 most of the time.
		self.VariantCount: int # Short. The number of Animations for this Type/TagID combination.
		self.TimingVariants: List[TimingVariant]

class StructV3():
	'''StructV3'''
	def __init__(self) -> None:
		'''StructV3 Constructor'''
		self.Length: int = 1
		self.Unknown: List[int] = [0, 0]

	def Write(self, Buffer: FileWriter) -> 'StructV3':
		'''Writes the StructV3 to the buffer'''
		Buffer.WriteInt(self.Length)
		for Unknown in self.Unknown:
			Buffer.WriteInt(Unknown)
		return self
	
	def Size(self) -> int:
		"""Returns the size of the ModeAnimationKey"""
		add = 0
		for Variant in self.AnimationSetVariants:
			add += Variant.Size()
		return 39 + add
	
	def Size(self) -> int:
		'''Returns the size of the StructV3'''
		return 12

class AnimationTimings():
	"""AnimationTimings"""
	def __init__(self):
		"""AnimationTimings Constructor"""
		self.Magic: int = 1650881127
		self.Version: int = 4 # Short. 3 or 4
		self.AnimationTimingCount: int = 0 # Short. Only used if there are multiple Animations.
		self.AnimationTimings: List[AnimationTiming]
		self.StructV3: StructV3 = StructV3()

	def Write(self, Buffer: FileWriter) -> 'AnimationTimings':
		"""Writes the AnimationTimings to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteShort(self.Version)
		Buffer.WriteShort(self.AnimationTimingCount)
		if self.AnimationTimingCount > 0:
			# TODO
			pass
		self.StructV3.Write(Buffer)
		return self
	
	def Size(self) -> int:
		"""Returns the size of the AnimationTimings"""
		return 8 + self.StructV3.Size()

	def Size(self) -> int:
		"""Returns the size of the AnimationSet"""
		add = 0
		for Key in self.ModeAnimationKeys:
			add += Key.Size()
		return 62 + add

class Timing():
	'''Timing'''
	def __init__(self) -> None:
		'''Timing Constructor'''
		self.CastMs: int # Int
		self.ResolveMs: int # Int
		self.UK1: float # Float
		self.UK2: float # Float
		self.UK3: float # Float
		self.AnimationMarkerID: int # Int
		# NOTICE:
		# When tying the visual animation to the game logic,
		# the castMs/resolveMs seem to get converted into game ticks by simply dividing them by 100.
		# So while the visual part of the animation is handled in milliseconds,
		# the maximum precision for the game logic is in deciseconds/game ticks.
		#
		# Meaning of the variables below:
		# For type Spawn:
		# castMs is the duration it will take until the unit can be issued commands or lose damage immunity
		# If castMs is for zero game ticks (< 100), then the animation is skipped entirely.
		# If castMs is for exactly one game tick (100-199), it seems to bug out.
		# Therefore the minimum value here should be 200, if you wish to play a spawn animation.
		# resolveMs is the duration the spawn animation will play out for in total.
		# This should match the total time from the .ska file, otherwise it looks weird.
		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
		#
		# For type CastResolve:
		# castMs is the duration it will take the unit to start casting its ability (can still be aborted)
		# If castMs is for zero game ticks (< 100), then the ability skips the cast stage
		# and instantly moves onto the resolve stage.
		# resolveMs is the duration it will take the unit to finish casting its ability (cannot be aborted)
		# It seems the stage cannot be skipped and uses a minimum duration of 1 game tick,
		# even if a value < 100 is specified.
		# The animation is automatically slowed down/sped up based on these timings.
		# The total time from the .ska file is ignored.
		#
		# For type ModeSwitch:
		# castMs is the duration it will take the unit to start its mode switch animation.
		# If castMs is for zero game ticks (< 100), then the mode switch is done instantly
		# and also does not interrupt movement. During castMs, any commands are blocked.
		# resolveMs seems to be ignored here. The unit can be issued new commands after the cast time.
		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
		#
		# For type Melee/WormMovement No experiments conducted yet.
		#  castMs;
		#  resolveMs;
		# at uk1;
		# at uk2;
		# 
		# Can be used to link an AnimationMarkerSet to a timing.
		# Relevant field: AnimationMarkerSet.animationMarkerID
		#
		# Seems to be often used for Spawn animations.
		# In cases where e.g. the animationTagID is used,
		# the animationMarkerID usually not referenced anywhere.

class TimingVariant():
	'''TimingVariant'''
	def __init__(self) -> None:
		'''TimingVariant Constructor'''
		self.Weight: int # Byte. The weight of this variant. The higher the weight, the more likely it is to be chosen.
		self.VariantIndex: int # Byte.
		self.TimingCount: int # Short. The number of Timings for this Variant. Most of the time, this is 1.
		self.Timings: List[Timing]

class AnimationTiming():
	'''AnimationTiming'''
	def __init__(self) -> None:
		'''AnimationTiming Constructor'''
		self.AnimationType: int = AnimationType['CastResolve']
		self.AnimationTagID: int = 0
		self.IsEnterModeAnimation: int = 0 # Short. This is 1 most of the time.
		self.VariantCount: int # Short. The number of Animations for this Type/TagID combination.
		self.TimingVariants: List[TimingVariant]

class StructV3():
	'''StructV3'''
	def __init__(self) -> None:
		'''StructV3 Constructor'''
		self.Length: int = 1
		self.Unknown: List[int] = [0, 0]

	def Write(self, Buffer: FileWriter) -> 'StructV3':
		'''Writes the StructV3 to the buffer'''
		Buffer.WriteInt(self.Length)
		for Unknown in self.Unknown:
			Buffer.WriteInt(Unknown)
		return self
	
	def Size(self) -> int:
		'''Returns the size of the StructV3'''
		return 12

class AnimationTimings():
	"""AnimationTimings"""
	def __init__(self):
		"""AnimationTimings Constructor"""
		self.Magic: int = 1650881127
		self.Version: int = 4 # Short. 3 or 4
		self.AnimationTimingCount: int = 0 # Short. Only used if there are multiple Animations.
		self.AnimationTimings: List[AnimationTiming]
		self.StructV3: StructV3 = StructV3()

	def Write(self, Buffer: FileWriter) -> 'AnimationTimings':
		"""Writes the AnimationTimings to the buffer"""
		Buffer.WriteInt(self.Magic)
		Buffer.WriteShort(self.Version)
		Buffer.WriteShort(self.AnimationTimingCount)
		if self.AnimationTimingCount > 0:
			# TODO
			pass
		self.StructV3.Write(Buffer)
		return self
	
	def Size(self) -> int:
		"""Returns the size of the AnimationTimings"""
		return 8 + self.StructV3.Size()

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





class DrwResourceMeta():
	"""DrwResourceMeta class"""
	def __init__(self) -> None:
		"""Initializes the DrwResourceMeta"""
		self.Unknown: List[int] = [0, 0]
		self.Length: int = 0
		self.Hash: str = ""

	def Read(self, Buffer: FileReader) -> 'DrwResourceMeta':
		"""Reads the DrwResourceMeta from the buffer"""
		self.Unknown = [Buffer.ReadInt() for _ in range(2)]
		self.Length = Buffer.ReadInt()
		self.Hash = Buffer.ReadString(32)
		return self

	def Write(self, Buffer: FileWriter) -> 'DrwResourceMeta':
		"""Writes the DrwResourceMeta to the buffer"""
		for _Unknown in self.Unknown: Buffer.WriteInt(_Unknown)
		Buffer.WriteInt(self.Length)
		Buffer.WriteString(self.Hash)
		return self

	def Size(self) -> int:
		"""Returns the size of the DrwResourceMeta"""
		return 12 + self.Length

class CGeoPrimitiveContainer():
	"""CGeoPrimitiveContainer class"""
	def __init__(self) -> None:
		"""Initializes the CGeoPrimitiveContainer"""
		pass

	def Read(self, Buffer: FileReader) -> 'CGeoPrimitiveContainer':
		"""Reads the CGeoPrimitiveContainer from the buffer"""
		return self

	def Write(self, Buffer: FileWriter) -> 'CGeoPrimitiveContainer':
		"""Writes the CGeoPrimitiveContainer to the buffer"""
		return self

	def Size(self) -> int:
		"""Returns the size of the CGeoPrimitiveContainer"""
		return 0

