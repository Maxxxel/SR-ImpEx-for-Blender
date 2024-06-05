from typing import List
from mathutils import Vector, Matrix
from .file_io import FileReader, FileWriter

from . drs_definitions import CDspMeshFile, MagicValues, Vertex, Face, AnimationType
























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
		self.Version = Buffer.ReadByte()
		self.BoxCount = Buffer.ReadInt()
		self.Boxes = [BoxShape().Read(Buffer) for _ in range(self.BoxCount)]
		self.SphereCount = Buffer.ReadInt()
		self.Spheres = [SphereShape().Read(Buffer) for _ in range(self.SphereCount)]
		self.CylinderCount = Buffer.ReadInt()
		self.Cylinders = [CylinderShape().Read(Buffer) for _ in range(self.CylinderCount)]
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

