from math import pi
import random
from typing import Collection, List
import os
from os.path import dirname, realpath
import bpy
import bmesh
import hashlib
from mathutils import Euler, Vector, Matrix, Quaternion


from .drs_utility import create_static_mesh, create_material, create_action
from .ska_file import *
from .drs_definitions import *

from . drs_definitions import BattleforgeMesh

def ResetViewport() -> None:
	context = bpy.context
	if (context.screen is not None):
		for area in context.screen.areas:
			if (area is not None) and (area.type in ['IMAGE_EDITOR', 'VIEW_3D']):
				area.tag_redraw()

	context.view_layer.update()



class BoneWeight:
	def __init__(self, BoneIndices=None, BoneWeights=None):
		self.BoneIndices: List[int] = BoneIndices
		self.BoneWeights: List[float] = BoneWeights





def SetObject(Name: str, SuffixHash: str, Collection: bpy.types.LayerCollection, Armature: bpy.types.Armature = None) -> bpy.types.Object:
	Name = f"{Name}_{SuffixHash}"

	if Name in Collection.collection.objects:
		return Collection.collection.objects[Name]

	NewObject: bpy.types.Object = bpy.data.objects.new(Name, Armature)
	Collection.collection.objects.link(NewObject)
	return NewObject



def create_bone_tree(armature: bpy.types.Armature, bone_list: list[DRSBone], bone_data: DRSBone):
	EditBone = armature.edit_bones.new(bone_data.Name)
	EditBone.head = bone_data.BoneMatrix @ Vector((0, 0, 0))
	EditBone.tail = bone_data.BoneMatrix @ Vector((0, 1, 0))
	EditBone.length = 0.1
	EditBone.align_roll(bone_data.BoneMatrix.to_3x3() @ Vector((0, 0, 1)))

	# Set the Parent
	if bone_data.Parent != -1:
		ParentBoneData: DRSBone = bone_list[bone_data.Parent]
		EditBone.parent = armature.edit_bones[ParentBoneData.Name]

	for ChildBone in bone_list:
		if ChildBone.Parent == bone_data.Identifier:
			create_bone_tree(armature, bone_list, ChildBone)



def init_skin(mesh_file: CDspMeshFile, skin_data: CSkSkinInfo, geo_mesh_data: CGeoMesh) -> list[BoneWeight]:
	TotalVertexCount = sum(Mesh.VertexCount for Mesh in mesh_file.Meshes)
	BoneWeights = [BoneWeight() for _ in range(TotalVertexCount)]
	VertexPositions = [Vertex.Position.xyz for Mesh in mesh_file.Meshes for Vertex in Mesh.MeshData[0].Vertices]
	GeoMeshPositions = [Vertex.xyz for Vertex in geo_mesh_data.Vertices]

	for VertexIndex, VectorToCheck in enumerate(VertexPositions):
		j = GeoMeshPositions.index(VectorToCheck)
		BoneWeights[VertexIndex] = BoneWeight(skin_data.VertexData[j].BoneIndices, skin_data.VertexData[j].Weights)

	return BoneWeights



def create_skinned_mesh(mesh_file: CDspMeshFile, dir_name:str, base_name: str, mesh_object: bpy.types.Object, armature: object, bone_list: list[DRSBone], weight_list: List[BoneWeight], state: bool = False, override_name: str = None):
	for i in range(mesh_file.MeshCount):
		Offset = 0 if i == 0 else Offset + mesh_file.Meshes[i - 1].VertexCount
		BattleforgeMeshData: BattleforgeMesh = mesh_file.Meshes[i]
		MeshName = "MeshData_" + (override_name if override_name else (("State_" if state else "") + str(i)))
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
		if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]):
			NewMesh.use_auto_smooth = True

		UVList = [i for poly in NewMeshObject.data.polygons for vidx in poly.vertices for i in UVList[vidx]]
		NewMeshObject.data.uv_layers.new().data.foreach_set('uv', UVList)

		MaterialData = create_material(i, BattleforgeMeshData, dir_name, base_name)
		NewMeshObject.data.materials.append(MaterialData)
		NewMeshObject.parent = mesh_object

		for VertexIndex in range(Offset, Offset + BattleforgeMeshData.VertexCount):
			BoneWeightData = weight_list[VertexIndex]

			for _ in range(4):
				GroupID = BoneWeightData.BoneIndices[_]
				Weight = BoneWeightData.BoneWeights[_]
				VertexGroup = None

				if bone_list[GroupID].Name not in NewMeshObject.vertex_groups:
					VertexGroup = NewMeshObject.vertex_groups.new(name=bone_list[GroupID].Name)
				else:
					VertexGroup = NewMeshObject.vertex_groups[bone_list[GroupID].Name]

				VertexGroup.add([VertexIndex - Offset], Weight, 'ADD')

		Modifier = NewMeshObject.modifiers.new(type="ARMATURE", name='Armature')
		Modifier.object = armature
		bpy.context.collection.objects.link(NewMeshObject)

		# Ensure the parent-child relationship is established
		# NewMeshObject.matrix_parent_inverse = mesh_object.matrix_world.inverted()

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

def CreateVert(column, row, size) -> tuple:
	""" Create a single vert """
	return (column * size, row * size, 0)

def CreateFace(column, row, rows) -> tuple:
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





def insert_keyframes(pose_bone: bpy.types.PoseBone, frame_data, frame: float, animation_type: int, bind_rot: Quaternion, bind_loc: Vector) -> None:
	if animation_type == 0:
		translation_vector = Vector((frame_data.x, frame_data.y, frame_data.z))
		translation_vector = bind_rot.conjugated() @ (translation_vector - bind_loc)
		pose_bone.location = translation_vector
		pose_bone.keyframe_insert(data_path='location', frame=frame)
	elif animation_type == 1:
		rotation_vector = Quaternion((-frame_data.w, frame_data.x, frame_data.y, frame_data.z))
		rotation_vector = bind_rot.conjugated() @ rotation_vector
		pose_bone.rotation_quaternion = rotation_vector
		pose_bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)

def add_animation_to_nla_track(armature_object, action):
	nla_tracks = armature_object.animation_data.nla_tracks
	new_track = nla_tracks.new()
	new_track.name = action.name
	new_strip = new_track.strips.new(action.name, 1, action)
	new_strip.name = action.name
	new_track.lock = True
	new_track.mute = False  # Set to False to enable playback

def create_animation(ska_file: SKA, armature_object, bone_list: list[DRSBone], animation_name: str):
	# Set the FPS to 60
	# bpy.context.scene.render.fps = 60
	fps = bpy.context.scene.render.fps
	duration_in_seconds = ska_file.AnimationData.Duration
	timings = ska_file.Times
	animation_frames = ska_file.KeyframeData
	animation_time_in_frames = duration_in_seconds * fps
	
	armature_object.animation_data_create()
	new_action = create_action(armature_object= armature_object, animation_name= animation_name, animation_time_in_frames= animation_time_in_frames, force_new= True, repeat= ska_file.AnimationData.Repeat)
	
	bpy.ops.object.mode_set(mode='POSE')
	bpy.context.scene.frame_start = 0
	
	for header_data in ska_file.Headers:
		bone_from_bone_list = next((bone for bone in bone_list if bone.SKAIdentifier == header_data.BoneId), None)
		if bone_from_bone_list is None:
			continue
	
		pose_bone = armature_object.pose.bones.get(bone_from_bone_list.Name)
		if pose_bone is None:
			continue
		
		for index in range(header_data.Tick, header_data.Tick + header_data.Interval):
			current_time_in_seconds = timings[index] * duration_in_seconds
			frame_data = animation_frames[index].VectorData
			current_frame = current_time_in_seconds * fps
			insert_keyframes(pose_bone, frame_data, current_frame, header_data.FrameType, bone_from_bone_list.BindRot, bone_from_bone_list.BindLoc)

	bpy.ops.object.mode_set(mode='OBJECT')
	add_animation_to_nla_track(armature_object, new_action)









def load_bmg(operator, context, filepath="", use_apply_transform=True, global_matrix=None, clear_scene=True):
	pass
# 	BaseName = os.path.basename(filepath).split(".")[0]
# 	HashOf5Letters = hashlib.shake_256(BaseName.encode()).hexdigest(5)
# 	HashOf5Letters = ''.join(random.sample(HashOf5Letters, len(HashOf5Letters)))
# 	DirName = os.path.dirname(filepath)
# 	DRSFile: DRS = DRS().Read(filepath)

# 	UnitCollection = SetCollection(BaseName, HashOf5Letters, bpy.context.view_layer.layer_collection)
# 	ModelDataCollection = SetCollection("ModelData", HashOf5Letters, UnitCollection)
# 	MeshSetGridCollection = SetCollection("MeshSetGrid", HashOf5Letters, ModelDataCollection)

# 	MeshGrid: MeshSetGrid = DRSFile.MeshSetGrid

# 	# Create new Grid Object
# 	# CreateGrid(MeshGrid, MeshSetGridCollection)

# 	if MeshGrid.GroundDecalLength > 0:
# 		GroundDecal: CDspMeshFile = DRS().Read(DirName + "\\" + MeshGrid.GroundDecal).CDspMeshFile
# 		GroundDecalObject = SetObject("GroundDecal", HashOf5Letters, MeshSetGridCollection)
# 		CreateStaticMesh(GroundDecal, DirName, GroundDecalObject, MeshSetGridCollection, State=False, OverrideName="GroundDecal")

# 	if DRSFile.CollisionShape is not None:
# 		CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, MeshSetGridCollection)
# 		CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

# 	if use_apply_transform:
# 		if MeshGrid.GroundDecalLength > 0:
# 			GroundDecalObject.matrix_world = global_matrix @ GroundDecalObject.matrix_world
# 			GroundDecalObject.scale = (1, -1, 1)

# 		if DRSFile.CollisionShape is not None:
# 			CollisionShapeObjectObject.matrix_world = global_matrix @ CollisionShapeObjectObject.matrix_world
# 			CollisionShapeObjectObject.scale = (1, -1, 1)

# 	MeshCounter = 0
# 	for MeshModule in MeshGrid.MeshModules:
# 		if MeshModule.HasMeshSet == 1:
# 			MeshGridModuleName = "MeshGridModule_" + str(MeshCounter)
# 			MeshGridModuleCollection = SetCollection(MeshGridModuleName, HashOf5Letters, ModelDataCollection)
# 			MeshCounter += 1

# 			for _ in range(MeshModule.StateBasedMeshSet.NumMeshStates):
# 				MeshState = MeshModule.StateBasedMeshSet.SMeshStates[_]
# 				MeshStateDRSFile: DRS = DRS().Read(DirName + "\\" + MeshState.DRSFile)
# 				StateName = MeshGridModuleName + "_State_" + str(MeshState.StateNum)
# 				StateCollection = SetCollection(StateName, HashOf5Letters, MeshGridModuleCollection)

# 				CGeoMeshObject = SetObject("CGeoMesh", HashOf5Letters, StateCollection)
# 				CreateCGeoMesh(MeshStateDRSFile.CGeoMesh, CGeoMeshObject, StateCollection)
# 				MeshObjectObject = SetObject("CDspMeshFile" + "_" + StateName, HashOf5Letters, StateCollection)

# 				if MeshStateDRSFile.CSkSkeleton is not None:
# 					Armature = bpy.data.armatures.new("CSkSkeleton" + "_" + StateName)
# 					ArmatureObject = SetObject("Armature" + "_" + StateName, HashOf5Letters, StateCollection, Armature)
# 					BoneList: list[DRSBone] = InitSkeleton(MeshStateDRSFile.CSkSkeleton)
# 					BuildSkeleton(BoneList, Armature, ArmatureObject)
# 					WeightList = InitSkin(MeshStateDRSFile.CDspMeshFile, MeshStateDRSFile.CSkSkinInfo, MeshStateDRSFile.CGeoMesh)
# 					MeshObjectObject.parent = ArmatureObject
# 					CreateSkinnedMesh(MeshStateDRSFile.CDspMeshFile, DirName, MeshObjectObject, StateCollection, ArmatureObject, BoneList, WeightList)

# 					# Seems like the MeshSetGrid holds some animations too... but why?
# 					# if DRSFile.AnimationSet is not None:
# 					# 	for AnimationKey in DRSFile.AnimationSet.ModeAnimationKeys:
# 					# 		for Variant in AnimationKey.AnimationSetVariants:
# 					# 			SKAFile: SKA = SKA().Read(os.path.join(DirName, Variant.File))
# 								# CreateAnimation(SKAFile, ArmatureObject, BoneList, Variant.File)

# 					if MeshStateDRSFile.AnimationSet is not None:
# 						for AnimationKey in MeshStateDRSFile.AnimationSet.ModeAnimationKeys:
# 							for Variant in AnimationKey.AnimationSetVariants:
# 								SKAFile: SKA = SKA().Read(os.path.join(DirName, Variant.File))
# 								CreateAnimation(SKAFile, ArmatureObject, BoneList, Variant.File)
# 				else:
# 					CreateStaticMesh(MeshStateDRSFile.CDspMeshFile, DirName, MeshObjectObject, StateCollection)

# 				if MeshStateDRSFile.CollisionShape is not None:
# 					StateCollisionShapeObjectObject = SetObject("CollisionShape" + "_" + StateName, HashOf5Letters, StateCollection)
# 					CreateCollisionShapes(MeshStateDRSFile.CollisionShape, StateCollisionShapeObjectObject)

# 				if use_apply_transform:
# 					if MeshStateDRSFile.CSkSkeleton is not None:
# 						ArmatureObject.matrix_world = global_matrix @ ArmatureObject.matrix_world
# 						ArmatureObject.scale = (1, -1, 1)
# 					else:
# 						MeshObjectObject.matrix_world = global_matrix @ MeshObjectObject.matrix_world
# 						MeshObjectObject.scale = (1, -1, 1)

# 					CGeoMeshObject.matrix_world = global_matrix @ CGeoMeshObject.matrix_world
# 					CGeoMeshObject.scale = (1, -1, 1)

# 					if MeshStateDRSFile.CollisionShape is not None:
# 						StateCollisionShapeObjectObject.matrix_world = global_matrix @ StateCollisionShapeObjectObject.matrix_world
# 						StateCollisionShapeObjectObject.scale = (1, -1, 1)

# 	ResetViewport()

# 	return {'FINISHED'}
