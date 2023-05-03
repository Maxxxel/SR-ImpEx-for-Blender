from math import pi
import random
from typing import List
import os
import bpy
import bmesh
import hashlib
from mathutils import Euler, Vector, Matrix, Quaternion
from bpy_extras.image_utils import load_image
from .DRSFile import DRS, CDspMeshFile, CSkSkeleton, CSkSkinInfo, BattleforgeMesh, Bone, CGeoMesh, Face, Vertex, BoneVertex, MeshSetGrid, BoxShape, SphereShape, CylinderShape, CGeoOBBTree, OBBNode
from .SKAFile import SKA

SCENECREATED = False

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

class BoneWeight:
	def __init__(self, BoneIndices=None, BoneWeights=None):
		self.BoneIndices: List[int] = BoneIndices
		self.BoneWeights: List[float] = BoneWeights

def GetCollectionRecursively(Name: str, Collection:bpy.types.LayerCollection = None) -> bpy.types.LayerCollection:
	if Name in Collection.children:
		return Collection.children[Name]

	for Child in Collection.children:
		Result = GetCollectionRecursively(Name, Child)
		if Result is not None:
			return Result

	return None

def SetCollection(Name: str, SuffixHash: str, Collection: bpy.types.LayerCollection) -> bpy.types.LayerCollection:
	Name = f"{Name}_{SuffixHash}"

	if Name in Collection.children:
		Root = Collection.children[Name]
	else:
		NewCollection: bpy.types.Collection = bpy.data.collections.new(Name)
		Collection.collection.children.link(NewCollection)
		Root = GetCollectionRecursively(Name, Collection)

	bpy.context.view_layer.active_layer_collection = Root
	return Root

def SetObject(Name: str, SuffixHash: str, Collection: bpy.types.LayerCollection, Armature: bpy.types.Armature = None) -> bpy.types.Object:
	Name = f"{Name}_{SuffixHash}"

	if Name in Collection.collection.objects:
		return Collection.collection.objects[Name]

	NewObject: bpy.types.Object = bpy.data.objects.new(Name, Armature)
	Collection.collection.objects.link(NewObject)
	return NewObject

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
		BoneListItem.Children = BoneData.Children

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

def BuildSkeleton(BoneList: list[DRSBone], Armature: bpy.types.Armature, ArmatureObject):
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

def InitSkin(MeshFile: CDspMeshFile, SkinData: CSkSkinInfo, GeoMeshData: CGeoMesh) -> list[BoneWeight]:
	TotalVertexCount = sum(Mesh.VertexCount for Mesh in MeshFile.Meshes)
	BoneWeights = [BoneWeight() for i in range(TotalVertexCount)]
	VertexPositions = [Vertex.Position.xyz for Mesh in MeshFile.Meshes for Vertex in Mesh.MeshData[0].Vertices]
	GeoMeshPositions = [Vertex.xyz for Vertex in GeoMeshData.Vertices]

	for VertexIndex, VectorToCheck in enumerate(VertexPositions):
		j = GeoMeshPositions.index(VectorToCheck)
		BoneWeights[VertexIndex] = BoneWeight(SkinData.VertexData[j].BoneIndices, SkinData.VertexData[j].Weights)

	return BoneWeights

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
	for Tex in BattleforgeMeshData.Textures.Textures:
		if Tex.Identifier == 1684432499:
			ColorMapNode.image: bpy.types.Image = load_image(os.path.basename(Tex.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
			NewMaterial.node_tree.links.new(BSDF.inputs['Base Color'], ColorMapNode.outputs['Color'])

	# Add ParameterMap if present
	for Tex in BattleforgeMeshData.Textures.Textures:
		if Tex.Identifier == 1936745324:
			ParameterMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
			ParameterMapNode.location = Vector((-700.0, -300.0))
			ParameterMapNode.image: bpy.types.Image = load_image(os.path.basename(Tex.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
			ParameterMapSeparateNode = NewMaterial.node_tree.nodes.new('ShaderNodeSeparateRGB')
			ParameterMapSeparateNode.location = Vector((-250.0, -450.0))
			NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Color'], ParameterMapSeparateNode.inputs['Image'])
			NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['R'], BSDF.inputs['Metallic'])
			NewMaterial.node_tree.links.new(ParameterMapSeparateNode.outputs['G'], BSDF.inputs['Roughness'])
			NewMaterial.node_tree.links.new(ParameterMapNode.outputs['Alpha'], BSDF.inputs['Specular'])

	# Add NormalMap Texture if present
	for Tex in BattleforgeMeshData.Textures.Textures:
		if Tex.Identifier == 1852992883:
			NormalMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
			NormalMapNode.location = Vector((-700.0, -600.0))
			NormalMapNode.image: bpy.types.Image = load_image(os.path.basename(Tex.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
			NormalMapConvertNode = NewMaterial.node_tree.nodes.new('ShaderNodeNormalMap')
			NormalMapConvertNode.location = Vector((-250.0, -600.0))
			NewMaterial.node_tree.links.new(NormalMapNode.outputs['Color'], NormalMapConvertNode.inputs['Color'])
			NewMaterial.node_tree.links.new(NormalMapConvertNode.outputs['Normal'], BSDF.inputs['Normal'])

	# Fluid is hard to add, prolly only as an hardcoded animation, there is no GIF support

	# Scratch

	# Environment can be ignored, its only used for Rendering

	# Refraction
	for Tex in BattleforgeMeshData.Textures.Textures:
		if Tex.Identifier == 1919116143 and Tex.Length > 0:
			RefractionMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
			RefractionMapNode.location = Vector((-700.0, -900.0))
			RefractionMapNode.image: bpy.types.Image = load_image(os.path.basename(Tex.Name + ".dds"), Dirname, check_existing=True, place_holder=False, recursive=False)
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

	if BattleforgeMeshData.Refraction.Length == 1:
		_RGB = BattleforgeMeshData.Refraction.RGB
		# What to do here?

	return NewMaterial

def CreateSkinnedMesh(MeshFile: CDspMeshFile, DirName:str, MeshObjectObject: bpy.types.Object, Collection: bpy.types.LayerCollection, Armature: object, BoneList: list[DRSBone], WeightList: List[BoneWeight], State: bool = False, OverrideName: str = None):
	for i in range(MeshFile.MeshCount):
		Offset = 0 if i == 0 else Offset + MeshFile.Meshes[i - 1].VertexCount
		BattleforgeMeshData: BattleforgeMesh = MeshFile.Meshes[i]
		MeshName = "Mesh_" + (OverrideName if OverrideName else (("State_" if State else "") + str(i)))
		NewMesh = bpy.data.meshes.new(MeshName)
		NewMeshObject = bpy.data.objects.new(MeshName, NewMesh)

		Faces = list()
		Vertices = list()
		Normals = list()
		UVList = list()

		for _ in range(BattleforgeMeshData.FaceCount):
			_Face: Face = BattleforgeMeshData.Faces[_].Indices
			Faces.append([_Face[0], _Face[1], _Face[2]])

		for _ in range(BattleforgeMeshData.VertexCount):
			_Vertex: Vertex = BattleforgeMeshData.MeshData[0].Vertices[_]
			Vertices.append(_Vertex.Position)
			Normals.append(_Vertex.Normal)
			# Negate the UVs Y Axis before adding them
			UVList.append((_Vertex.Texture[0], -_Vertex.Texture[1]))

		NewMesh.from_pydata(Vertices, [], Faces)
		NewMesh.polygons.foreach_set('use_smooth', [True] * len(NewMesh.polygons))
		NewMesh.normals_split_custom_set_from_vertices(Normals)
		NewMesh.use_auto_smooth = True

		UVList = [i for poly in NewMeshObject.data.polygons for vidx in poly.vertices for i in UVList[vidx]]
		NewMeshObject.data.uv_layers.new().data.foreach_set('uv', UVList)

		MaterialData = CreateMaterial(i, BattleforgeMeshData, DirName)
		NewMeshObject.data.materials.append(MaterialData)
		NewMeshObject.parent = MeshObjectObject

		for VertexIndex in range(Offset, Offset + BattleforgeMeshData.VertexCount):
			BoneWeightData = WeightList[VertexIndex]

			for _ in range(4):
				GroupID = BoneWeightData.BoneIndices[_]
				Weight = BoneWeightData.BoneWeights[_]
				VertexGroup = None

				if BoneList[GroupID].Name not in NewMeshObject.vertex_groups:
					VertexGroup = NewMeshObject.vertex_groups.new(name=BoneList[GroupID].Name)
				else:
					VertexGroup = NewMeshObject.vertex_groups[BoneList[GroupID].Name]

				VertexGroup.add([VertexIndex - Offset], Weight, 'ADD')

		Modifier = NewMeshObject.modifiers.new(type="ARMATURE", name='Armature')
		Modifier.object = Armature
		Collection.collection.objects.link(NewMeshObject)

def CreateStaticMesh(MeshFile: CDspMeshFile, DirName:str, MeshObjectObject: bpy.types.Object, Collection: bpy.types.LayerCollection, State: bool = False, OverrideName: str = None):
	for i in range(MeshFile.MeshCount):
		BattleforgeMeshData: BattleforgeMesh = MeshFile.Meshes[i]
		MeshName = "Mesh_" + (OverrideName if OverrideName else (("State_" if State else "") + str(i)))
		NewMesh = bpy.data.meshes.new(MeshName)
		NewMeshObject = bpy.data.objects.new(MeshName, NewMesh)

		Faces = list()
		Vertices = list()
		Normals = list()
		UVList = list()

		for _ in range(BattleforgeMeshData.FaceCount):
			_Face: Face = BattleforgeMeshData.Faces[_].Indices
			Faces.append([_Face[0], _Face[1], _Face[2]])

		for _ in range(BattleforgeMeshData.VertexCount):
			_Vertex: Vertex = BattleforgeMeshData.MeshData[0].Vertices[_]
			Vertices.append(_Vertex.Position)
			Normals.append(_Vertex.Normal)
			# Negate the UVs Y Axis before adding them
			UVList.append((_Vertex.Texture[0], -_Vertex.Texture[1]))

		NewMesh.from_pydata(Vertices, [], Faces)
		NewMesh.polygons.foreach_set('use_smooth', [True] * len(NewMesh.polygons))
		NewMesh.normals_split_custom_set_from_vertices(Normals)
		NewMesh.use_auto_smooth = True

		UVList = [i for poly in NewMeshObject.data.polygons for vidx in poly.vertices for i in UVList[vidx]]
		NewMeshObject.data.uv_layers.new().data.foreach_set('uv', UVList)

		MaterialData = CreateMaterial(i, BattleforgeMeshData, DirName)
		NewMeshObject.data.materials.append(MaterialData)
		NewMeshObject.parent = MeshObjectObject
		Collection.collection.objects.link(NewMeshObject)

def CreateAnimation(SkaFile: SKA, ArmatureObject, BoneList: list[DRSBone], AnimationName: str):
	FPS = bpy.context.scene.render.fps
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

def CreateBattleforgeScene():
	global SCENECREATED

	if SCENECREATED is False:
		SetCollection("ShaderData", "AllModels", bpy.context.view_layer.layer_collection)
		bpy.ops.object.light_add(type='SUN', location=(1500, 2700, 1000), radius=10)
		Sun = bpy.context.active_object
		Sun.data.color = (1, 0.9, 0.7)
		Sun.data.energy = 3

		SCENECREATED = True

def CreateCollisionBoxes(_Box: BoxShape, Parent: bpy.types.Object):
	# Contains rotation and scale. Is a row major 3x3 matrix
	Mat = _Box.CoordSystem.Matrix
	Pos = _Box.CoordSystem.Position
	Mat4x4 = Mat.to_4x4()
	Mat4x4.translation = Pos
	CornerA = _Box.CGeoAABox.LowerLeftCorner
	CornerB = _Box.CGeoAABox.UpperRightCorner
	Rotation = Mat4x4.to_euler()
	Rotation = Vector((Rotation.x, Rotation.y, Rotation.z)) # Blender uses a different rotation order?
	ScaleTest = Mat4x4.to_scale()
	if ScaleTest != Vector((1, 1, 1)):
		print("Warning: Scale is not 1 for Box Collision Shape!")
	Scale = Vector((abs(CornerA.x - CornerB.x), abs(CornerA.y - CornerB.y), abs(CornerA.z - CornerB.z)))

	bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, location=Pos, rotation=Rotation, scale=Scale)
	Box = bpy.context.active_object
	Box.name = "CollisionShape Box"
	Box.data.name = "Box"
	Box.parent = Parent
	Box.display_type = 'WIRE'

def CreateCollisionSpheres(_Sphere: SphereShape, Parent: bpy.types.Object):
	# Contains rotation and scale. Is a row major 3x3 matrix
	Mat = _Sphere.CoordSystem.Matrix
	Pos = _Sphere.CoordSystem.Position
	Mat4x4 = Mat.to_4x4()
	Mat4x4.translation = Pos
	Radius = _Sphere.CGeoSphere.Radius
	Center = _Sphere.CGeoSphere.Center # Always Zero vector!
	bpy.ops.mesh.primitive_uv_sphere_add(radius=Radius, location=Center, rotation=Mat4x4.to_euler())
	Sphere = bpy.context.active_object
	Sphere.name = "CollisionShape Sphere"
	Sphere.data.name = "Sphere"
	Sphere.parent = Parent
	Sphere.location = Pos
	Sphere.display_type = 'WIRE'

def CreateCollisionCylinders(_Cylinder: CylinderShape, Index: int, Parent: bpy.types.Object):
	Mat = _Cylinder.CoordSystem.Matrix
	Pos = _Cylinder.CoordSystem.Position
	Mat4x4 = Mat.to_4x4()
	Mat4x4.translation = Pos
	Rotation = Mat4x4.to_euler()
	Rotation.x += pi / 2 # We need to rotate the cylinder by 90 degrees cause the cylinder is always created along the z axis, but we need it along the y axis for imported models
	Radius = _Cylinder.CGeoCylinder.Radius
	Center = _Cylinder.CGeoCylinder.Center

	bpy.ops.mesh.primitive_cylinder_add(radius=Radius, location=Center, rotation=Rotation, scale=Mat4x4.to_scale())
	Cylinder = bpy.context.active_object
	Cylinder.name = "CollisionShape Cylinder #" + str(Index)
	Cylinder.data.name = "Cylinder #" + str(Index)
	Cylinder.location = Vector((Pos.x, Pos.y + (_Cylinder.CGeoCylinder.Height / 2), Pos.z ))
	Cylinder.dimensions.z = _Cylinder.CGeoCylinder.Height
	Cylinder.parent = Parent
	Cylinder.display_type = 'WIRE'
	bpy.ops.object.select_all(action='DESELECT')

def CreateCollisionShapes(CollisionShapes, Parent: bpy.types.Object):
	for _ in range(CollisionShapes.BoxCount):
		CreateCollisionBoxes(CollisionShapes.Boxes[_], Parent)

	for _ in range(CollisionShapes.SphereCount):
		CreateCollisionSpheres(CollisionShapes.Spheres[_], Parent)

	for _ in range(CollisionShapes.CylinderCount):
		CreateCollisionCylinders(CollisionShapes.Cylinders[_], _, Parent)

def CreateVert(column, row, size):
	""" Create a single vert """
	return (column * size, row * size, 0)

def CreateFace(column, row, rows):
	""" Create a single face """
	return (column* rows + row, (column + 1) * rows + row, (column + 1) * rows + 1 + row, column * rows + 1 + row)

def CreateGrid(MeshGrid: MeshSetGrid, Collection: bpy.types.LayerCollection):
	_Mesh = bpy.data.meshes.new("Grid")
	_BM = bmesh.new()
	bmesh.ops.create_grid(_BM, x_segments=MeshGrid.GridWidth * 2 + 1, y_segments=MeshGrid.GridHeight * 2 + 1, size=MeshGrid.ModuleDistance * 0.5 * (MeshGrid.GridWidth * 2 + 1))
	bmesh.ops.delete(_BM, geom=_BM.faces, context="FACES_ONLY")
	_BM.to_mesh(_Mesh)
	GridObject = SetObject("MeshGrid", "Data", Collection, _Mesh)
	# Rotate the grid 90 degrees around the x axis
	GridObject.rotation_euler = Euler((pi / 2, 0, 0), 'XYZ')

def CreateCGeoMesh(GeoMesh: CGeoMesh, GeoMeshObject: bpy.types.Object, Collection: bpy.types.LayerCollection):
	NewMesh = bpy.data.meshes.new("Mesh_CGeo")
	NewMeshObject = bpy.data.objects.new("Mesh_CGeo", NewMesh)

	Faces = list()
	Vertices = list()

	for _ in range(int(GeoMesh.IndexCount / 3)):
		_Face: Face = GeoMesh.Faces[_].Indices
		Faces.append((_Face[0], _Face[1], _Face[2]))

	for _ in range(GeoMesh.VertexCount):
		_Vertex: Vector = GeoMesh.Vertices[_]
		Vertices.append((_Vertex.x, _Vertex.y, _Vertex.z))

	NewMesh.from_pydata(Vertices, [], Faces)
	NewMeshObject.parent = GeoMeshObject
	NewMeshObject.display_type = 'WIRE'
	Collection.collection.objects.link(NewMeshObject)

def CreateCGeoOBBTree(GeoOBB: CGeoOBBTree, GeoMesh: CGeoMesh, GeoOBBObject: bpy.types.Object, Collection: bpy.types.LayerCollection):
	for _ in range(GeoOBB.MatrixCount):
		_OBBNode: OBBNode = GeoOBB.OBBNodes[_]
		NewOBBMesh = bpy.data.meshes.new("Mesh_OBB_" + str(_OBBNode.NodeDepth))
		OBBDepthNodeObject = SetObject("OBB_" + str(_OBBNode.NodeDepth), "", Collection, NewOBBMesh)

		Faces = list()
		Vertices = list()

		for _ in range(_OBBNode.CurrentTriangleCount, _OBBNode.CurrentTriangleCount + _OBBNode.MinimumTrianglesFound):
			_Face: Face = GeoOBB.Faces[_].Indices
			Faces.append((_Face[0], _Face[1], _Face[2]))

		for _ in range(GeoMesh.VertexCount):
			_Vertex: Vector = GeoMesh.Vertices[_]
			Vertices.append((_Vertex.x, _Vertex.y, _Vertex.z))

		NewOBBMesh.from_pydata(Vertices, [], Faces)
		OBBDepthNodeObject.parent = GeoOBBObject
		OBBDepthNodeObject.display_type = 'WIRE'

		# Now the 1x1x1 cube
		Mat = _OBBNode.OrientedBoundingBox.Matrix
		Pos = _OBBNode.OrientedBoundingBox.Position
		Mat4x4 = Mat.to_4x4()
		Mat4x4.translation = Pos
		Rotation = Mat4x4.to_euler()
		Rotation.y += pi / 2
		# Rotation = Vector((-Rotation.x, -Rotation.y, -Rotation.z)) # Blender uses a different rotation order?
		Scale = Mat4x4.to_scale()
		Scale.x *= 2
		Scale.y *= 2
		Scale.z *= 2

		bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, location=Pos, rotation=Rotation, scale=Scale)
		Box = bpy.context.active_object
		Box.name = "OBB Box" + str(_OBBNode.NodeDepth)
		Box.data.name = "OBB Box Mesh" + str(_OBBNode.NodeDepth)
		Box.parent = OBBDepthNodeObject

def ClearBlenderScene():
	global SCENECREATED
	# Set the Active Object to None
	bpy.context.view_layer.objects.active = None

	# Clear the Scene
	bpy.ops.object.select_all(action='SELECT')

	# Remove all Objects
	bpy.ops.object.delete(use_global=False)

	# Remove all Collections
	for Collection in bpy.data.collections:
		bpy.data.collections.remove(Collection)

	SCENECREATED = False

def LoadDRS(operator, context, filepath="", UseApplyTransform=True, GlobalMatrix=None, ClearScene=True):
	BaseName = os.path.basename(filepath).split(".")[0]
	HashOf5Letters = hashlib.shake_256(BaseName.encode()).hexdigest(5)
	HashOf5Letters = ''.join(random.sample(HashOf5Letters, len(HashOf5Letters)))
	DirName = os.path.dirname(filepath)

	if ClearScene:
		ClearBlenderScene()

	CreateBattleforgeScene()
	DRSFile: DRS = DRS().Read(filepath)

	UnitCollection = SetCollection(BaseName, HashOf5Letters, bpy.context.view_layer.layer_collection)
	ModelDataCollection = SetCollection("ModelData", HashOf5Letters, UnitCollection)
	CGeoMeshObject = SetObject("CGeoMesh", HashOf5Letters, ModelDataCollection)
	CreateCGeoMesh(DRSFile.CGeoMesh, CGeoMeshObject, ModelDataCollection)
	MeshObjectObject = SetObject("CDspMeshFile", HashOf5Letters, ModelDataCollection)

	if DRSFile.CSkSkeleton is not None:
		Armature = bpy.data.armatures.new("CSkSkeleton")
		ArmatureObject = SetObject("Armature", HashOf5Letters, ModelDataCollection, Armature)
		BoneList: list[DRSBone] = InitSkeleton(DRSFile.CSkSkeleton)
		BuildSkeleton(BoneList, Armature, ArmatureObject)
		WeightList = InitSkin(DRSFile.CDspMeshFile, DRSFile.CSkSkinInfo, DRSFile.CGeoMesh)
		MeshObjectObject.parent = ArmatureObject
		CreateSkinnedMesh(DRSFile.CDspMeshFile, DirName, MeshObjectObject, ModelDataCollection, ArmatureObject, BoneList, WeightList)

		if DRSFile.AnimationSet is not None:
			for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
				for Variant in AnimationKey.AnimationSetVariants:
					SKAFile: SKA = SKA().Read(os.path.join(DirName, Variant.File))
					CreateAnimation(SKAFile, ArmatureObject, BoneList, Variant.File)
	else:
		# CGeoOBBTreeMeshObject = SetObject("CGeoOBBTreeMesh", HashOf5Letters, ModelDataCollection)
		# CreateCGeoOBBTree(DRSFile.CGeoOBBTree, DRSFile.CGeoMesh, CGeoOBBTreeMeshObject, ModelDataCollection)
		CreateStaticMesh(DRSFile.CDspMeshFile, DirName, MeshObjectObject, ModelDataCollection)

	if DRSFile.CollisionShape is not None:
		CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, ModelDataCollection)
		CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

	if UseApplyTransform:
		if DRSFile.CSkSkeleton is not None:
			ArmatureObject.matrix_world = GlobalMatrix @ ArmatureObject.matrix_world
			ArmatureObject.scale = (1, -1, 1)
		else:
			MeshObjectObject.matrix_world = GlobalMatrix @ MeshObjectObject.matrix_world
			MeshObjectObject.scale = (1, -1, 1)

		CGeoMeshObject.matrix_world = GlobalMatrix @ CGeoMeshObject.matrix_world
		CGeoMeshObject.scale = (1, -1, 1)

		if DRSFile.CollisionShape is not None:
			CollisionShapeObjectObject.matrix_world = GlobalMatrix @ CollisionShapeObjectObject.matrix_world
			CollisionShapeObjectObject.scale = (1, -1, 1)

	ResetViewport()

def LoadBMG(operator, context, filepath="", UseApplyTransform=True, GlobalMatrix=None, ClearScene=True):
	BaseName = os.path.basename(filepath).split(".")[0]
	HashOf5Letters = hashlib.shake_256(BaseName.encode()).hexdigest(5)
	HashOf5Letters = ''.join(random.sample(HashOf5Letters, len(HashOf5Letters)))
	DirName = os.path.dirname(filepath)

	if ClearScene:
		ClearBlenderScene()

	CreateBattleforgeScene()
	DRSFile: DRS = DRS().Read(filepath)

	UnitCollection = SetCollection(BaseName, HashOf5Letters, bpy.context.view_layer.layer_collection)
	ModelDataCollection = SetCollection("ModelData", HashOf5Letters, UnitCollection)
	MeshSetGridCollection = SetCollection("MeshSetGrid", HashOf5Letters, ModelDataCollection)

	MeshGrid: MeshSetGrid = DRSFile.MeshSetGrid

	# Create new Grid Object
	# CreateGrid(MeshGrid, MeshSetGridCollection)

	if MeshGrid.GroundDecalLength > 0:
		GroundDecal: CDspMeshFile = DRS().Read(DirName + "\\" + MeshGrid.GroundDecal).CDspMeshFile
		GroundDecalObject = SetObject("GroundDecal", HashOf5Letters, MeshSetGridCollection)
		CreateStaticMesh(GroundDecal, DirName, GroundDecalObject, MeshSetGridCollection, State=False, OverrideName="GroundDecal")

	if DRSFile.CollisionShape is not None:
		CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, MeshSetGridCollection)
		CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

	if UseApplyTransform:
		if MeshGrid.GroundDecalLength > 0:
			GroundDecalObject.matrix_world = GlobalMatrix @ GroundDecalObject.matrix_world
			GroundDecalObject.scale = (1, -1, 1)

		if DRSFile.CollisionShape is not None:
			CollisionShapeObjectObject.matrix_world = GlobalMatrix @ CollisionShapeObjectObject.matrix_world
			CollisionShapeObjectObject.scale = (1, -1, 1)

	MeshCounter = 0
	for MeshModule in MeshGrid.MeshModules:
		if MeshModule.HasMeshSet == 1:
			MeshGridModuleName = "MeshGridModule_" + str(MeshCounter)
			MeshGridModuleCollection = SetCollection(MeshGridModuleName, HashOf5Letters, ModelDataCollection)
			MeshCounter += 1

			for _ in range(MeshModule.StateBasedMeshSet.NumMeshStates):
				MeshState = MeshModule.StateBasedMeshSet.SMeshStates[_]
				MeshStateDRSFile: DRS = DRS().Read(DirName + "\\" + MeshState.DRSFile)
				StateName = MeshGridModuleName + "_State_" + str(MeshState.StateNum)
				StateCollection = SetCollection(StateName, HashOf5Letters, MeshGridModuleCollection)

				CGeoMeshObject = SetObject("CGeoMesh", HashOf5Letters, StateCollection)
				CreateCGeoMesh(MeshStateDRSFile.CGeoMesh, CGeoMeshObject, StateCollection)
				MeshObjectObject = SetObject("CDspMeshFile" + "_" + StateName, HashOf5Letters, StateCollection)

				if MeshStateDRSFile.CSkSkeleton is not None:
					Armature = bpy.data.armatures.new("CSkSkeleton" + "_" + StateName)
					ArmatureObject = SetObject("Armature" + "_" + StateName, HashOf5Letters, StateCollection, Armature)
					BoneList: list[DRSBone] = InitSkeleton(MeshStateDRSFile.CSkSkeleton)
					BuildSkeleton(BoneList, Armature, ArmatureObject)
					WeightList = InitSkin(MeshStateDRSFile.CDspMeshFile, MeshStateDRSFile.CSkSkinInfo, MeshStateDRSFile.CGeoMesh)
					MeshObjectObject.parent = ArmatureObject
					CreateSkinnedMesh(MeshStateDRSFile.CDspMeshFile, DirName, MeshObjectObject, StateCollection, ArmatureObject, BoneList, WeightList)

					# Seems like the MeshSetGrid holds some animations too... but why?
					# if DRSFile.AnimationSet is not None:
					# 	for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
					# 		for Variant in AnimationKey.AnimationSetVariants:
					# 			SKAFile: SKA = SKA().Read(os.path.join(DirName, Variant.File))
								# CreateAnimation(SKAFile, ArmatureObject, BoneList, Variant.File)

					if MeshStateDRSFile.AnimationSet is not None:
						for AnimationKey in MeshStateDRSFile.AnimationSet.ModeAnimationKeys:
							for Variant in AnimationKey.AnimationSetVariants:
								SKAFile: SKA = SKA().Read(os.path.join(DirName, Variant.File))
								CreateAnimation(SKAFile, ArmatureObject, BoneList, Variant.File)
				else:
					CreateStaticMesh(MeshStateDRSFile.CDspMeshFile, DirName, MeshObjectObject, StateCollection)

				if MeshStateDRSFile.CollisionShape is not None:
					StateCollisionShapeObjectObject = SetObject("CollisionShape" + "_" + StateName, HashOf5Letters, StateCollection)
					CreateCollisionShapes(MeshStateDRSFile.CollisionShape, StateCollisionShapeObjectObject)

				if UseApplyTransform:
					if MeshStateDRSFile.CSkSkeleton is not None:
						ArmatureObject.matrix_world = GlobalMatrix @ ArmatureObject.matrix_world
						ArmatureObject.scale = (1, -1, 1)
					else:
						MeshObjectObject.matrix_world = GlobalMatrix @ MeshObjectObject.matrix_world
						MeshObjectObject.scale = (1, -1, 1)

					CGeoMeshObject.matrix_world = GlobalMatrix @ CGeoMeshObject.matrix_world
					CGeoMeshObject.scale = (1, -1, 1)

					if MeshStateDRSFile.CollisionShape is not None:
						StateCollisionShapeObjectObject.matrix_world = GlobalMatrix @ StateCollisionShapeObjectObject.matrix_world
						StateCollisionShapeObjectObject.scale = (1, -1, 1)

	ResetViewport()

	return {'FINISHED'}
