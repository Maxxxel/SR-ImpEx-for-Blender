from math import sqrt
from typing import List
import os
import bpy
import numpy as np
from mathutils import Vector, Matrix, Quaternion, Euler
from bpy_extras.image_utils import load_image
from bpy_extras.io_utils import unpack_list
from .DRSFile import DRS, CDspMeshFile, CSkSkeleton, CSkSkinInfo, BattleforgeMesh, Bone, CGeoMesh, MeshData, Face, Vertex, BoneVertex
from .SKAFile import SKA

def ResetViewport() -> None:
	for Area in bpy.context.screen.areas:
		if Area.type in ['IMAGE_EDITOR', 'VIEW_3D']:
			Area.tag_redraw()

class DRSBone():
	"""docstring for DRSBone"""
	def __init__(self) -> None:
		self.SKAIdentifier: int
		self.Identifier: int
		self.Name: str
		self.Parent: int = -1
		self.Scale: Vector
		self.Rotation: Quaternion
		self.Position: Vector
		self.PositionOrigin: Vector
		self.Children: List[int]

def InitSkeleton(SkeletonData: CSkSkeleton) -> list[DRSBone]:
	BoneList: list[DRSBone] = []

	# Init the Bone List
	for i in range(SkeletonData.BoneCount):
		BoneList.append(DRSBone())

	# Set the Bone Datap

	for i in range(SkeletonData.BoneCount):
		BoneData: Bone = SkeletonData.Bones[i]

		# Get the RootBone Vertices
		BoneVertices: List[BoneVertex] = SkeletonData.BoneMatrices[BoneData.Identifier].BoneVertices

		_Vector0 = Vector((BoneVertices[0].Position.x, BoneVertices[0].Position.y, BoneVertices[0].Position.z, BoneVertices[0].Parent))
		_Vector1 = Vector((BoneVertices[1].Position.x, BoneVertices[1].Position.y, BoneVertices[1].Position.z, BoneVertices[1].Parent))
		_Vector2 = Vector((BoneVertices[2].Position.x, BoneVertices[2].Position.y, BoneVertices[2].Position.z, BoneVertices[2].Parent))
		_Vector3 = Vector((BoneVertices[3].Position.x, BoneVertices[3].Position.y, BoneVertices[3].Position.z, BoneVertices[3].Parent))

		# Create the Bone Matrix
		# Mage the 4th column negative to flip the Axis
		_BoneMatrix = Matrix((
			(_Vector0.x, _Vector0.y, _Vector0.z, -1 * _Vector3.x),
			(_Vector1.x, _Vector1.y, _Vector1.z, -1 * _Vector3.y),
			(_Vector2.x, _Vector2.y, _Vector2.z, -1 * _Vector3.z),
			(0.0, 0.0, 0.0, 1.0)
		))

		# Set Data
		BoneListItem: DRSBone = BoneList[BoneData.Identifier]
		BoneListItem.SKAIdentifier = BoneData.Version
		BoneListItem.Identifier = BoneData.Identifier
		BoneListItem.Name = BoneData.Name
		BoneListItem.Scale: Vector = _BoneMatrix.to_scale()
		BoneListItem.PositionOrigin = BoneMatrix.to_translation()
		BoneListItem.Rotation = BoneMatrix.to_quaternion()
		BoneListItem.Rotation = Quaternion((BoneListItem.Rotation.w, BoneListItem.Rotation.x, BoneListItem.Rotation.y, BoneListItem.Rotation.z))
		# Transform the Bone Position
		_Position = (NewBone.RotationOrigin @ Quaternion((0.0, NewBone.PositionOrigin.x, NewBone.PositionOrigin.y, NewBone.PositionOrigin.z)) @ NewBone.RotationOrigin.conjugated())
		BoneListItem.Position = Vector((_Position.x, _Position.y, _Position.z))

		# Set the Bone Children
		BoneListItem.Children = BoneData.ChildCount

		# Set the Bones Children's Parent ID
		for j in range(BoneData.ChildCount):
			ChildID = BoneData.Children[j]
			BoneList[ChildID].Parent = BoneData.Identifier

	# Order the Bones by Parent ID
	BoneList.sort(key=lambda x: x.Identifier)

	# Return the BoneList
	return BoneList

def CheckEquality(VectorA, VectorB) -> bool:
	Distance = (VectorA - VectorB).length

	if Distance < 0.0001:
		return True
	else:
		return False

def UpdateBoneChildren(Armature: bpy.types.Armature, BoneList: list[DRSBone], BoneData: Bone, Parent):
	# Loop boneList for children of bone indexed by parentID
	for ChildBone in BoneList:
		if ChildBone.Parent == BoneData.Identifier:
			# Create the new Bone
			NewBone = Armature.edit_bones.new(ChildBone.Name)
			NewBone.head = ChildBone.Position

			if Parent.tail == Vector() and CheckEquality(NewBone.head, Parent.head) is False:
				Parent.tail = ChildBone.Position

			if ChildBone.Children == 0:
				# Extend the childBones Tail in the same direction as the parent
				NewBone.tail = NewBone.head + (NewBone.head - Parent.head)

			# Set the Parent
			NewBone.parent = Parent

			# Set the EditBone
			ChildBone.EditBone = NewBone

			# Update the Bones Children
			UpdateBoneChildren(Armature, BoneList, ChildBone, NewBone)

def BuildSkeleton(BoneList: list[DRSBone], Armature: bpy.types.Armature, ArmatureObject):
	bpy.context.scene.collection.objects.link(ArmatureObject)

	# Switch to edit mode
	bpy.context.view_layer.objects.active = ArmatureObject
	bpy.ops.object.mode_set(mode='EDIT')

	# Start with the Root Bone at index 0
	RootBone: DRSBone = BoneList[0]
	NewBone = Armature.edit_bones.new(RootBone.Name)
	NewBone.head = RootBone.Position
	NewBone.tail = RootBone.Position + Vector((0.25, 0.0, 0.0))
	BoneList[0].EditBone = NewBone

	# Update the Bones Children
	UpdateBoneChildren(Armature, BoneList, RootBone, NewBone)

	bpy.ops.object.mode_set(mode='OBJECT')

def InitSkin(MeshFile: CDspMeshFile, SkinData: CSkSkinInfo, GeoMeshData: CGeoMesh) -> np.ndarray:
	# _vOff = 0
	VertexIndexMap = {tuple(vector): i for i, vector in enumerate(GeoMeshData.Vertices)}
	BoneWeightsPerMesh = {}

	for MeshIndex in range(MeshFile.MeshCount):
		BoneWeightsPerMesh[MeshIndex] = {}
		BoneWeights = {}
		Mesh: MeshData = MeshFile.Meshes[MeshIndex].MeshData[0]
		Len = len(Mesh.Vertices)

		for VertexIndex in range(Len):
			_Vertex = Mesh.Vertices[VertexIndex].Position

			if tuple(_Vertex) in VertexIndexMap:
				VertexIndexSkin = VertexIndexMap[tuple(_Vertex)]
				VertexWeightData = SkinData.VertexData[VertexIndexSkin]
				VertexIndexFinal = VertexIndex #+ vOff
				BoneIndices = VertexWeightData.BoneIndices
				Weights = VertexWeightData.Weights

				for i in range(len(BoneIndices)):
					BoneIndex = BoneIndices[i]
					Weight = Weights[i]

					if BoneIndex not in BoneWeights:
						BoneWeights[BoneIndex] = {}

					if Weight not in BoneWeights[BoneIndex]:
						BoneWeights[BoneIndex][Weight] = []

					BoneWeights[BoneIndex][Weight].append(VertexIndexFinal)

		BoneWeightsPerMesh[MeshIndex] = BoneWeights
		# _vOff += Len

	return BoneWeightsPerMesh

def CreateMaterial(i: int, BattleforgeMeshData: BattleforgeMesh, Dirname: str):
	NewMaterial = bpy.data.materials.new("Material_" + str(i))
	NewMaterial.blend_method = "BLEND"
	NewMaterial.show_transparent_back = False
	NewMaterial.use_nodes = True

	# Add BaseColor Texture
	BSDF = NewMaterial.node_tree.nodes["Principled BSDF"]
	BaseColor = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1684432499)
	bpy.data.textures.new(name="_col", type='IMAGE')
	Image = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
	Image.image: Image = load_image(os.path.basename(BaseColor.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
	NewMaterial.node_tree.links.new(BSDF.inputs['Base Color'], Image.outputs['Color'])

	# Add NormalMap Texture if present
	NormalMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1852992883)
	if NormalMap is not None:
		NormalMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		NormalMapNode.image: Image = load_image(os.path.basename(NormalMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		NormalMapConvertNode = NewMaterial.node_tree.nodes.new('ShaderNodeNormalMap')
		NewMaterial.node_tree.links.new(NormalMapNode.outputs['Color'], NormalMapConvertNode.inputs['Color'])
		NewMaterial.node_tree.links.new(NormalMapConvertNode.outputs['Normal'], BSDF.inputs['Normal'])

	# Add ParameterMap if present
	ParameterMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1936745324)
	if ParameterMap is not None:
		ParameterMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		ParameterMapNode.image: Image = load_image(os.path.basename(ParameterMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		ParameterMapSeparateNode = NewMaterial.node_tree.nodes.new('ShaderNodeSeparateRGB')
		NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Color'], ParameterMapSeparateNode.inputs['Image'])
		NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['R'], BSDF.inputs['Metallic'])
		NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['G'], BSDF.inputs['Roughness'])
		NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Alpha'], BSDF.inputs['Specular'])

	# Fluid is hard to add, prolly only as an hardcoded animation, there is no GIF support

	# Scratch

	# Environment can be ignored, its only used for Rendering

	# Refraction
	RefractionMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1919116143)
	if RefractionMap is not None and RefractionMap.Length > 0:
		RefractionMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		RefractionMapNode.image: Image = load_image(os.path.basename(RefractionMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		RefBSDF = NewMaterial.node_tree.nodes.new('ShaderNodeBsdfRefraction')
		NewMaterial.node_tree.links.new(RefBSDF.inputs['Color'], RefractionMapNode.outputs['Color'])
		MixNode = NewMaterial.node_tree.nodes.new('ShaderNodeMixShader')
		NewMaterial.node_tree.links.new(MixNode.inputs[1], RefBSDF.outputs[0])
		NewMaterial.node_tree.links.new(MixNode.inputs[2], BSDF.outputs[0])
		NewMaterial.node_tree.links.new(MixNode.outputs[0], NewMaterial.node_tree.nodes['Material Output'].inputs[0])
		MixNodeAlpha = NewMaterial.node_tree.nodes.new('ShaderNodeMixRGB')
		MixNodeAlpha.use_alpha = True
		MixNodeAlpha.blend_type = 'SUBTRACT'
		# Set the Factor to 0.2, so the Refraction is not too strong
		MixNodeAlpha.inputs[0].default_value = 0.2
		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[1], Image.outputs['Alpha'])
		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[2], RefractionMapNode.outputs['Alpha'])
		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], MixNodeAlpha.outputs[0])
	else:
		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], Image.outputs['Alpha'])

	return NewMaterial

def CreateMesh(MeshFile: CDspMeshFile, Collection: bpy.types.Collection, WeightList: np.ndarray, BoneList: list[DRSBone], Armature: bpy.types.Armature, Dirname: str):
	# Loop through the Meshes with an Index
	for i in range(MeshFile.MeshCount):
		# Set the Offset to 0 for the first Mesh and add the Mesh Size to the Offset for the next Mesh
		Offset = 0 if i == 0 else Offset + MeshFile.Meshes[i - 1].VertexCount

		# Get the Mesh
		BattleforgeMeshData: BattleforgeMesh = MeshFile.Meshes[i]

		# Create the Mesh
		NewMesh = bpy.data.meshes.new("Mesh_" + str(i))

		# Create the Container
		NewMeshObject = bpy.data.objects.new("Mesh_" + str(i), NewMesh)

		# Create the Faces
		Faces = list()

		# Loop through the Faces
		for _ in range(BattleforgeMeshData.FaceCount):
			_Face: Face = BattleforgeMeshData.Faces[_].Indices
			Faces.append([_Face[0], _Face[1], _Face[2]])

		# Create the Vertices, Normals and UVs
		Vertices = list()
		Normals = list()
		UVList = list()

		# Loop through the Vertices
		for _ in range(BattleforgeMeshData.VertexCount):
			_Vertex: Vertex = BattleforgeMeshData.MeshData[0].Vertices[_]
			Vertices.append(_Vertex.Position)
			Normals.append(_Vertex.Normal)
			# Negate the UVs Y Axis before adding them
			UVList.append((_Vertex.Texture[0], -1 * _Vertex.Texture[1]))

		# Add the Vertices and Faces to the Mesh
		NewMesh.from_pydata(Vertices, [], Faces)

		# Add the Normals and UVs to the Mesh
		NewMesh.vertices.foreach_set('normal', unpack_list(Normals))
		UVList = [i for poly in NewMeshObject.data.polygons for vidx in poly.vertices for i in UVList[vidx]]
		NewMeshObject.data.uv_layers.new().data.foreach_set('uv', UVList)

		# Create the Material
		MaterialData = CreateMaterial(i, BattleforgeMeshData, Dirname)

		# Add the Skin
		for GroupID, WeightData in WeightList[i].items():
			GroupName = BoneList[GroupID].Name
			NewMeshObject.vertex_groups.new(name=GroupName)

			for Weight, VertexIndices  in WeightData.items():
				NewMeshObject.vertex_groups[GroupName].add(VertexIndices, Weight, 'ADD')

		# Set the Material to the Mesh
		NewMeshObject.data.materials.append(MaterialData)

		# Link the Object to the armature
		NewMeshObject.parent = Armature

		# Add a Modifier to the Object
		Modifier = NewMeshObject.modifiers.new(type="ARMATURE", name='Armature')
		Modifier.object = Armature

		# Link the Object to the Collection
		Collection.objects.link(NewMeshObject)

def CreateAnimation(SkaFile: SKA, Armature: bpy.types.Armature, ArmatureObject, BoneList: list[DRSBone], SkeletonData: CSkSkeleton, AnimationFileName: str):
	pass

def LoadDRS(operator, context, filepath="", UseApplyTransform=True, GlobalMatrix=None, ClearScene=True, EditModel=True):
	BaseName = os.path.basename(filepath).split(".")[0]
	Dirname = os.path.dirname(filepath)

	# Clear the Scene and all Data and Collections
	if ClearScene:
		# Clear the Scene
		bpy.ops.object.select_all(action='SELECT')

		# Remove all Objects
		bpy.ops.object.delete(use_global=False)

		# Remove all Collections
		for Collection in bpy.data.collections:
			bpy.data.collections.remove(Collection)

	# Read the DRS File
	DRSFile: DRS = DRS().Read(filepath)

	# Create a Collection DRS Model(s) in current Scene Collection if not already existing
	if "DRS Model(s)" in bpy.data.collections:
		Collection = bpy.data.collections["DRS Model(s)"]
	else:
		Collection = bpy.data.collections.new("DRS Model(s)")

	bpy.context.scene.collection.children.link(Collection)

	# Create an Armature Collection/Obj and add it to the Scene Collection
	Armature = bpy.data.armatures.new("CSkSkeleton")
	ArmatureObject = bpy.data.objects.new(BaseName, Armature)
	Collection.objects.link(ArmatureObject)

	# Load the Skeleton file and init the Bone List, then build the Skeleton
	BoneList: list[DRSBone] = InitSkeleton(DRSFile.CSkSkeleton)
	BuildSkeleton(BoneList, Armature, ArmatureObject)

	# Load the Skin and init the Weight List
	WeightList = InitSkin(DRSFile.Mesh, DRSFile.CSkSkinInfo, DRSFile.CGeoMesh)

	# Create the Meshes
	CreateMesh(DRSFile.Mesh, Collection, WeightList, BoneList, ArmatureObject, Dirname)

	# Create the Animations
	Test = False
	for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
		for Variant in AnimationKey.AnimationSetVariants:
			if Test:
				break
			_SKAFile: SKA = SKA().Read(os.path.join(Dirname, Variant.File))
			CreateAnimation(_SKAFile, Armature, ArmatureObject, BoneList, DRSFile.CSkSkeleton, Variant.File)
			Test = True

	# Set the Global Matrix
	if UseApplyTransform:
		ArmatureObject.matrix_world = GlobalMatrix

	# Unlink the Armature from the Scene Collection
	bpy.context.scene.collection.objects.unlink(ArmatureObject)

	# Reset the Viewport
	ResetViewport()

	return {'FINISHED'}

# def LoadBMG(operator, context, filepath="", use_apply_transform=True, global_matrix=None):
	# dirname = os.path.dirname(filepath)
	# os_delimiter = os.sep
	# MeshCollection = []

	# # Parse the DRS File
	# DRSFile: MeshSetGrid = DRSParser().Parse(filepath)._MeshSetGrid

	# # Create a Collection
	# CollectionName = filepath.split(os_delimiter)[-1]
	# MainCollection = Collection(CollectionName)

	# # Get the Ground Decal and add it
	# if DRSFile.GroundDecalLength > 0:
	#     GroundDecal: CDspMeshFile = DRSParser().Parse(dirname + "\\" + DRSFile.GroundDecal)._CDspMeshFile

	#     for i in range(GroundDecal.MeshCount):
	#         SourceMesh: BattleforgeMesh = GroundDecal.Meshes[i]
	#         AddMesh(MeshCollection, MainCollection, SourceMesh, i, use_apply_transform, global_matrix, dirname, "GroundDecal")

	# # Get the different States and add them
	# for i in range(DRSFile.MeshModules.__len__()):
	#     MeshModule: MeshGridModule = DRSFile.MeshModules[i]

	#     if MeshModule.HasMeshSet == 1:
	#         for j in range(MeshModule.StateBasedMeshSet.NumMeshStates):
	#             SMesh: SMeshState = MeshModule.StateBasedMeshSet.SMeshStates[j]
	#             SourceFile = DRSParser().Parse(dirname + "\\" + SMesh.DRSFile)
	#             MeshState: CDspMeshFile = SourceFile._CDspMeshFile
	#             Skeleton: CSkSkeleton = SourceFile._CSkSkeleton

	#             # Add the Scene BoundingBox
	#             AddSceneBB(MainCollection, MeshState, use_apply_transform, global_matrix)

	#             # Add the Skeleton
	#             if Skeleton is not None:
	#                 CreateSkeleton(MainCollection, Skeleton)

	#                 if use_apply_transform:
	#                     CreateSkeleton(MainCollection, Skeleton, use_apply_transform, global_matrix)

	#             # Add the Meshes
	#             for k in range(MeshState.MeshCount):
	#                 SourceMesh: BattleforgeMesh = MeshState.Meshes[k]
	#                 AddMesh(MeshCollection, MainCollection, SourceMesh, MeshCollection.__len__(), use_apply_transform, global_matrix, dirname, "MeshState_{}".format(SMesh.StateNum))

	# return {'WORK IN PROGRESS'}
