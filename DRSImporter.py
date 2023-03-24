from typing import List
import os
import bpy
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from bpy_extras.image_utils import load_image
from bpy_extras.io_utils import unpack_list
from .DRSFile import DRS, CDspMeshFile, CSkSkeleton, CSkSkinInfo, BattleforgeMesh, Bone, CGeoMesh, MeshData, Face, Vertex, BoneVertex, MeshSetGrid
from .SKAFile import SKA

FPS = bpy.context.scene.render.fps

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
		self.BoneMatrix: Matrix
		self.Children: List[int]
		self.BindLoc: Vector
		self.BindRot: Quaternion

def InitSkeleton(SkeletonData: CSkSkeleton, Suffix: str = None) -> list[DRSBone]:
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
		# Make the 4th column negative to flip the Axis
		_Rot = Matrix((_Vector0.xyz, _Vector1.xyz, _Vector2.xyz))
		_Loc = _Rot @ (-1 * _Vector3.xyz)
		_BoneMatrix = Matrix.LocRotScale(_Loc, _Rot, Vector((1, 1, 1)))

		# Set Data
		BoneListItem: DRSBone = BoneList[BoneData.Identifier]
		BoneListItem.SKAIdentifier = BoneData.Version
		BoneListItem.Identifier = BoneData.Identifier
		BoneListItem.Name = BoneData.Name + (f"_{Suffix}" if Suffix else "")
		BoneListItem.BoneMatrix = _BoneMatrix

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

def CreateBoneTree(Armature: bpy.types.Armature, BoneList: list[DRSBone], BoneData: DRSBone):
	EditBone = Armature.edit_bones.new(BoneData.Name)
	EditBone.head = BoneData.BoneMatrix @ Vector((0, 0, 0))
	EditBone.tail = BoneData.BoneMatrix @ Vector((0, 1, 0))
	EditBone.length = 1 # TODO
	EditBone.align_roll(BoneData.BoneMatrix.to_3x3() @ Vector((0, 0, 1)))

	# Set the Parent
	if BoneData.Parent != -1:
		ParentBoneData: DRSBone = BoneList[BoneData.Parent]
		EditBone.parent = Armature.edit_bones[ParentBoneData.Name]

	for ChildBone in BoneList:
		if ChildBone.Parent == BoneData.Identifier:
			CreateBoneTree(Armature, BoneList, ChildBone)

def BuildSkeleton(Coll: bpy.types.Collection, BoneList: list[DRSBone], Armature: bpy.types.Armature, ArmatureObject):
	# Coll.objects.link(ArmatureObject)

	# Switch to edit mode
	bpy.context.view_layer.objects.active = ArmatureObject
	bpy.ops.object.mode_set(mode='EDIT')

	CreateBoneTree(Armature, BoneList, BoneList[0])

	bpy.ops.object.mode_set(mode='OBJECT')

	# Record bind pose transform to parent space
	# Used to set pose bones for animation
	for BoneData in BoneList:
		ArmaBone = Armature.bones[BoneData.Name]
		MatrixLocal = ArmaBone.matrix_local

		if ArmaBone.parent:
			MatrixLocal = ArmaBone.parent.matrix_local.inverted_safe() @ MatrixLocal

		BoneData.BindLoc = MatrixLocal.to_translation()
		BoneData.BindRot = MatrixLocal.to_quaternion()

def InitSkin(MeshFile: CDspMeshFile, SkinData: CSkSkinInfo, GeoMeshData: CGeoMesh) -> np.ndarray:
	VertexIndexMap = {tuple(Vector((vector.x, vector.y, vector.z))): i for i, vector in enumerate(GeoMeshData.Vertices)}
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
				VertexIndexFinal = VertexIndex
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

	return BoneWeightsPerMesh

def CreateMaterial(i: int, BattleforgeMeshData: BattleforgeMesh, Dirname: str):
	NewMaterial = bpy.data.materials.new("Material_" + str(i))
	NewMaterial.blend_method = 'CLIP'
	NewMaterial.alpha_threshold = 0.6
	NewMaterial.show_transparent_back = False
	NewMaterial.use_nodes = True
	NewMaterial.node_tree.nodes['Material Output'].location = Vector((400.0, 0.0))	
	BSDF = NewMaterial.node_tree.nodes["Principled BSDF"]
	BSDF.location = Vector((0.0, 0.0))
	ColorMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
	ColorMapNode.location = Vector((-700.0, 0.0))

	# Add BaseColor Texture
	BaseColor = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1684432499)
	if BaseColor is not None:
		ColorMapNode.image: bpy.types.Image = load_image(os.path.basename(BaseColor.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		NewMaterial.node_tree.links.new(BSDF.inputs['Base Color'], ColorMapNode.outputs['Color'])

	# Add ParameterMap if present
	ParameterMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1936745324)
	if ParameterMap is not None:
		ParameterMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		ParameterMapNode.location = Vector((-700.0, -300.0))
		ParameterMapNode.image: bpy.types.Image = load_image(os.path.basename(ParameterMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		ParameterMapSeparateNode = NewMaterial.node_tree.nodes.new('ShaderNodeSeparateRGB')
		ParameterMapSeparateNode.location = Vector((-250.0, -450.0))
		NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Color'], ParameterMapSeparateNode.inputs['Image'])
		NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['R'], BSDF.inputs['Metallic'])
		NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['G'], BSDF.inputs['Roughness'])
		NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Alpha'], BSDF.inputs['Specular'])

	# Add NormalMap Texture if present
	NormalMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1852992883)
	if NormalMap is not None:
		NormalMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		NormalMapNode.location = Vector((-700.0, -600.0))
		NormalMapNode.image: bpy.types.Image = load_image(os.path.basename(NormalMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		NormalMapConvertNode = NewMaterial.node_tree.nodes.new('ShaderNodeNormalMap')
		NormalMapConvertNode.location = Vector((-250.0, -600.0))
		NewMaterial.node_tree.links.new(NormalMapNode.outputs['Color'], NormalMapConvertNode.inputs['Color'])
		NewMaterial.node_tree.links.new(NormalMapConvertNode.outputs['Normal'], BSDF.inputs['Normal'])

	# Fluid is hard to add, prolly only as an hardcoded animation, there is no GIF support

	# Scratch

	# Environment can be ignored, its only used for Rendering

	# Refraction
	RefractionMap = next(x for x in BattleforgeMeshData.Textures.Textures if x.Identifier == 1919116143)
	if RefractionMap is not None and RefractionMap.Length > 0:
		RefractionMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
		RefractionMapNode.location = Vector((-700.0, -900.0))
		RefractionMapNode.image: bpy.types.Image = load_image(os.path.basename(RefractionMap.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
		RefBSDF = NewMaterial.node_tree.nodes.new('ShaderNodeBsdfRefraction')
		RefBSDF.location = Vector((-250.0, -770.0))
		NewMaterial.node_tree.links.new(RefBSDF.inputs['Color'], RefractionMapNode.outputs['Color'])
		MixNode = NewMaterial.node_tree.nodes.new('ShaderNodeMixShader')
		MixNode.location = Vector((0.0, 200.0))
		NewMaterial.node_tree.links.new(MixNode.inputs[1], RefBSDF.outputs[0])
		NewMaterial.node_tree.links.new(MixNode.inputs[2], BSDF.outputs[0])
		NewMaterial.node_tree.links.new(MixNode.outputs[0], NewMaterial.node_tree.nodes['Material Output'].inputs[0])
		MixNodeAlpha = NewMaterial.node_tree.nodes.new('ShaderNodeMixRGB')
		MixNodeAlpha.location = Vector((-250.0, -1120.0))
		MixNodeAlpha.use_alpha = True
		MixNodeAlpha.blend_type = 'SUBTRACT'
		# Set the Factor to 0.2, so the Refraction is not too strong
		MixNodeAlpha.inputs[0].default_value = 0.2
		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[1], ColorMapNode.outputs['Alpha'])
		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[2], RefractionMapNode.outputs['Alpha'])
		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], MixNodeAlpha.outputs[0])
	else:
		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], ColorMapNode.outputs['Alpha'])

	return NewMaterial

def CreateMesh(MeshFile: CDspMeshFile, Collection: bpy.types.Collection, Dirname: str, Armature: bpy.types.Armature = None, BoneList: list[DRSBone] = None, WeightList: np.ndarray = None, State: bool = False, OverrideName: str = None):
	# Loop through the Meshes with an Index
	for i in range(MeshFile.MeshCount):
		# Set the Offset to 0 for the first Mesh and add the Mesh Size to the Offset for the next Mesh
		Offset = 0 if i == 0 else Offset + MeshFile.Meshes[i - 1].VertexCount

		# Get the Mesh
		BattleforgeMeshData: BattleforgeMesh = MeshFile.Meshes[i]

		# Mesh Name
		MeshName = "Mesh_" + (OverrideName if OverrideName else (("State_" if State else "") + str(i)))

		# Create the Mesh
		NewMesh = bpy.data.meshes.new(MeshName)

		# Create the Container
		NewMeshObject = bpy.data.objects.new(MeshName, NewMesh)

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

		if Armature is not None:
			if WeightList is not None and BoneList is not None:
				# Add the Skin
				for GroupID, WeightData in WeightList[i].items():
					GroupName = BoneList[GroupID].Name
					NewMeshObject.vertex_groups.new(name=GroupName)

					for Weight, VertexIndices  in WeightData.items():
						NewMeshObject.vertex_groups[GroupName].add(VertexIndices, Weight, 'REPLACE')

			# Link the Object to the armature
			NewMeshObject.parent = Armature

			# Add a Modifier to the Object
			Modifier = NewMeshObject.modifiers.new(type="ARMATURE", name='Armature')
			Modifier.object = Armature

		# Set the Material to the Mesh
		NewMeshObject.data.materials.append(MaterialData)

		# Link the Object to the Collection
		Collection.objects.link(NewMeshObject)

def CreateAnimation(SkaFile: SKA, ArmatureObject, BoneList: list[DRSBone], AnimationName: str):
	DurationInSeconds: float = SkaFile.AnimationData.Duration
	Timings: List[float] = SkaFile.Times
	AnimationFrames = SkaFile.KeyframeData
	AnimationTimeInFrames: int = round(DurationInSeconds * FPS)

	# Create the Animation Data
	ArmatureObject.animation_data_create()

	# Create the Action
	NewAction = bpy.data.actions.new(name=AnimationName)

	# Set the Length of the Action
	NewAction.use_frame_range = True

	NewAction.frame_range = (0, AnimationTimeInFrames)
	NewAction.frame_start = 0
	NewAction.frame_end = AnimationTimeInFrames
	NewAction.use_cyclic = SkaFile.AnimationData.Repeat == 1
	bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, AnimationTimeInFrames)

	# Link the Action to the Armature
	ArmatureObject.animation_data.action = NewAction

	# Go into Pose Mode
	bpy.ops.object.mode_set(mode='POSE')

	# Set the Start of the Animation
	bpy.context.scene.frame_start = 0

	# Loop through the Header Data
	for HeaderData in SkaFile.Headers:
		SKABoneId: int = HeaderData.BoneId
		AnimationType: int = HeaderData.FrameType
		StartIndex: int = HeaderData.Tick
		NumberOfSteps: int = HeaderData.Interval
		BoneFromBoneList: DRSBone = next((Bone for Bone in BoneList if Bone.SKAIdentifier == SKABoneId), None)

		if BoneFromBoneList is None:
			# Animation files are used for multiple models, so some bones might not be used in the current model
			continue

		PoseBoneFromArmature: bpy.types.PoseBone = ArmatureObject.pose.bones.get(BoneFromBoneList.Name)

		if PoseBoneFromArmature is None:
			# Some Bones are duplicated in the Animation files, so we can skip them as Blender deletes them
			continue

		for Index in range(StartIndex, StartIndex + NumberOfSteps):
			CurrentTimeInSeconds: float = Timings[Index] * DurationInSeconds
			FrameData = AnimationFrames[Index].VectorData
			CurrentFrame: int = round(CurrentTimeInSeconds * FPS)

			if AnimationType == 0:
				# Translation
				TranslationVector = Vector((FrameData.x, FrameData.y, FrameData.z))
				# Relative to the bind pose
				TranslationVector = BoneFromBoneList.BindRot.conjugated() @ (TranslationVector - BoneFromBoneList.BindLoc)
				PoseBoneFromArmature.location = TranslationVector
				PoseBoneFromArmature.keyframe_insert(data_path='location', frame=CurrentFrame)
			elif AnimationType == 1:
				# Rotation
				RotationVector = Quaternion((-FrameData.w, FrameData.x, FrameData.y, FrameData.z))
				# Relative to the bind pose
				RotationVector = BoneFromBoneList.BindRot.conjugated() @ RotationVector
				PoseBoneFromArmature.rotation_quaternion = RotationVector
				PoseBoneFromArmature.keyframe_insert(data_path='rotation_quaternion', frame=CurrentFrame)

	# Go back to Object Mode
	bpy.ops.object.mode_set(mode='OBJECT')

	# Push action to an NLA track to save it
	NewTrack = ArmatureObject.animation_data.nla_tracks.new(prev=None)
	NewTrack.name = NewAction.name
	NewTrack.strips.new(NewAction.name, 1, NewAction)
	NewTrack.lock = True
	NewTrack.mute = True

def LoadDRS(operator, context, filepath="", UseApplyTransform=True, GlobalMatrix=None, ClearScene=True, EditModel=True):
	BaseName = os.path.basename(filepath).split(".")[0]
	Dirname = os.path.dirname(filepath)

	# Clear the Scene and all Data and Collections
	if ClearScene:
		# Set the Active Object to None
		bpy.context.view_layer.objects.active = None

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
	if "DRS Model(s)" not in bpy.data.collections:
		Collection = bpy.data.collections.new("DRS Model(s)")
		bpy.context.scene.collection.children.link(Collection)

	Collection = bpy.data.collections.new(BaseName)
	bpy.context.scene.collection.children.link(Collection)

	BoneList = None
	WeightList = None
	ArmatureObject = None
	if DRSFile.CSkSkeleton is not None:
		# Create an Armature Collection/Obj and add it to the Scene Collection
		Armature = bpy.data.armatures.new("CSkSkeleton")
		ArmatureObject = bpy.data.objects.new(BaseName, Armature)
		Collection.objects.link(ArmatureObject)

		# Load the Skeleton file and init the Bone List, then build the Skeleton
		BoneList: list[DRSBone] = InitSkeleton(DRSFile.CSkSkeleton)
		BuildSkeleton(Collection, BoneList, Armature, ArmatureObject)

		# Load the Skin and init the Weight List
		WeightList = InitSkin(DRSFile.Mesh, DRSFile.CSkSkinInfo, DRSFile.CGeoMesh)

	# Create the Meshes
	CreateMesh(DRSFile.Mesh, Collection, Dirname, ArmatureObject, BoneList, WeightList)

	if DRSFile.AnimationSet is not None:
		# Create the Animations
		for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
			for Variant in AnimationKey.AnimationSetVariants:
				_SKAFile: SKA = SKA().Read(os.path.join(Dirname, Variant.File))
				CreateAnimation(_SKAFile, ArmatureObject, BoneList, Variant.File)

	# Set the Global Matrix
	if UseApplyTransform:
		if ArmatureObject is not None:
			ArmatureObject.matrix_world = GlobalMatrix
		else:
			for Object in Collection.objects:
				Object.matrix_world = GlobalMatrix

	# if ArmatureObject is not None:
		# Unlink the Armature from the Scene Collection
		# bpy.context.scene.collection.objects.unlink(ArmatureObject)

	# Reset the Viewport
	ResetViewport()

	return {'FINISHED'}

def LoadBMG(operator, context, filepath="", UseApplyTransform=True, GlobalMatrix=None, ClearScene=True, EditModel=True):
	BaseName = os.path.basename(filepath).split(".")[0]
	Dirname = os.path.dirname(filepath)

	# Clear the Scene and all Data and Collections
	if ClearScene:
		# Set the Active Object to None
		bpy.context.view_layer.objects.active = None

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
	if "DRS Model(s)" not in bpy.data.collections:
		Collection = bpy.data.collections.new("DRS Model(s)")
		bpy.context.scene.collection.children.link(Collection)

	Collection = bpy.data.collections.new(BaseName)
	bpy.context.scene.collection.children.link(Collection)

	# Get MeshSetGrid
	MeshGrid: MeshSetGrid = DRSFile.MeshSetGrid

	# Get the Ground Decal and add it
	if MeshGrid.GroundDecalLength > 0:
		GroundDecal: CDspMeshFile = DRS().Read(Dirname + "\\" + MeshGrid.GroundDecal).Mesh
		CreateMesh(GroundDecal, Collection, Dirname, None, None, None, False, "GroundDecal")

		# Set the Global Matrix
		if UseApplyTransform:
			Collection.objects["Mesh_GroundDecal"].matrix_world = GlobalMatrix

	# Now we need to get the different Meshes of each State
	# The use the same Names for Bones and Stuff, but we dont do that, we will add a prefix to the Name
	for MeshModule in MeshGrid.MeshModules:
		if MeshModule.HasMeshSet == 1:
			for _ in range(MeshModule.StateBasedMeshSet.NumMeshStates):
				MeshState = MeshModule.StateBasedMeshSet.SMeshStates[_]
				SourceFile = DRS().Read(Dirname + "\\" + MeshState.DRSFile)
				StateMesh: CDspMeshFile = SourceFile.Mesh
				StateName = "State_" + str(MeshState.StateNum)

				# Create a new Collection for the State and add it to the Scene Collection
				StateCollection = bpy.data.collections.new(StateName)
				Collection.children.link(StateCollection)

				ArmatureObject = None
				BoneList = None
				WeightList = None

				if SourceFile.CSkSkeleton is not None:
					# Create an Armature Collection/Obj and add it to the Scene Collection
					Armature = bpy.data.armatures.new("CSkSkeleton" + "_" + StateName)
					ArmatureObject = bpy.data.objects.new(BaseName + "_" + StateName, Armature)
					StateCollection.objects.link(ArmatureObject)

					# Load the Skeleton file and init the Bone List, then build the Skeleton
					BoneList: list[DRSBone] = InitSkeleton(SourceFile.CSkSkeleton, StateName)
					BuildSkeleton(StateCollection, BoneList, Armature, ArmatureObject)

					# Load the Skin and init the Weight List
					WeightList = InitSkin(SourceFile.Mesh, SourceFile.CSkSkinInfo, SourceFile.CGeoMesh)

					if DRSFile.AnimationSet is not None:
						# Create the Animations
						for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
							for Variant in AnimationKey.AnimationSetVariants:
								_SKAFile: SKA = SKA().Read(os.path.join(Dirname, Variant.File))
								CreateAnimation(_SKAFile, ArmatureObject, BoneList, Variant.File)

				CreateMesh(StateMesh, StateCollection, Dirname, ArmatureObject, BoneList, WeightList, True, StateName)

				# Set the Global Matrix
				if UseApplyTransform:
					if ArmatureObject is not None:
						ArmatureObject.matrix_world = GlobalMatrix
					else:
						for Object in StateCollection.objects:
							Object.matrix_world = GlobalMatrix

	# Reset the Viewport
	ResetViewport()

	return {'FINISHED'}