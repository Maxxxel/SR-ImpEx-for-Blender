import bpy
import bmesh
import math
from typing import List
from mathutils import Euler, Vector, Matrix
from .DRSFile import DRS, CDspMeshFile, BattleforgeMesh, Face, EmptyString, LevelOfDetail, MeshData, Refraction, Vertex, Materials, Flow, CGeoMesh, CGeoOBBTree, DrwResourceMeta, CGeoPrimitiveContainer, JointGroup, CollisionShape, CylinderShape, CGeoCylinder, BoxShape, CGeoAABox, SphereShape, CGeoSphere, CMatCoordinateSystem

def ShowMessageBox(Message: str, Title: str = "Message Box", Icon: str = "INFO"):
	def DrawMessageBox(self, context):
		self.layout.label(text=Message)

	bpy.context.window_manager.popup_menu(DrawMessageBox, title=Title, icon=Icon)

def SearchForObject(ObjectName: str, Collection: bpy.types.Collection):
	for Object in Collection.objects:
		if Object.name.find(ObjectName) != -1:
			return Object

	for Coll in Collection.children:
		FoundObject = SearchForObject(ObjectName, Coll)
		if FoundObject is not None:
			return FoundObject

	return None

def GetBB(Object):
	BBMin = Vector((0, 0, 0))
	BBMax = Vector((0, 0, 0))

	if Object.type == "MESH":
		for _Vertex in Object.data.vertices:
			_Vertex = _Vertex.co

			if _Vertex.x < BBMin.x:
				BBMin.x = _Vertex.x
			if _Vertex.y < BBMin.y:
				BBMin.y = _Vertex.y
			if _Vertex.z < BBMin.z:
				BBMin.z = _Vertex.z
			if _Vertex.x > BBMax.x:
				BBMax.x = _Vertex.x
			if _Vertex.y > BBMax.y:
				BBMax.y = _Vertex.y
			if _Vertex.z > BBMax.z:
				BBMax.z = _Vertex.z

	return BBMin, BBMax

def GetSceneBB(Collection: bpy.types.Collection):
	BBMin = Vector((0, 0, 0))
	BBMax = Vector((0, 0, 0))

	for Object in Collection.objects:
		if Object.type == "MESH":
			BBMinObject, BBMaxObject = GetBB(Object)

			if BBMinObject.x < BBMin.x:
				BBMin.x = BBMinObject.x
			if BBMinObject.y < BBMin.y:
				BBMin.y = BBMinObject.y
			if BBMinObject.z < BBMin.z:
				BBMin.z = BBMinObject.z
			if BBMaxObject.x > BBMax.x:
				BBMax.x = BBMaxObject.x
			if BBMaxObject.y > BBMax.y:
				BBMax.y = BBMaxObject.y
			if BBMaxObject.z > BBMax.z:
				BBMax.z = BBMaxObject.z

	return BBMin, BBMax

def UpdateCDspMeshfile(SourceFile: DRS, SourceCollection: bpy.types.Collection):
	# We override the DRS Data with the Blender Data
	# As the Meshdata in the DRS File is well known, we can just use the Blender Data to recreate the Mesh(es)
	NewMeshData = CDspMeshFile()
	NewMeshData.Magic = 1314189598
	NewMeshData.Zero = 0
	NewMeshData.MeshCount = len([True for Object in SourceCollection.objects if Object.type == "MESH"])
	NewMeshData.SomePoints = [Vector((0, 0, 0, 0)) for i in range(3)]
	# We need to investigate the Bounding Box further, as it seems to be wrong
	NewMeshData.BoundingBoxLowerLeftCorner, NewMeshData.BoundingBoxUpperRightCorner = GetSceneBB(SourceCollection)
	print("Old BB: ", SourceFile.Mesh.BoundingBoxLowerLeftCorner, SourceFile.Mesh.BoundingBoxUpperRightCorner)
	print("New BB: ", NewMeshData.BoundingBoxLowerLeftCorner, NewMeshData.BoundingBoxUpperRightCorner)

	# Create the new Mesh Data
	NewMeshData.Meshes = []

	for Object in SourceCollection.objects:
		if Object.type == "MESH":
			# Set the Mesh active
			bpy.context.view_layer.objects.active = Object
			GroupNames = []
			if Object.vertex_groups is not None:
				for Group in Object.vertex_groups:
					GroupNames.append(Group.name)

			Mesh = Object.data
			Mesh.calc_tangents()

			NewMesh = BattleforgeMesh()
			NewMesh.VertexCount = len(Mesh.vertices)
			NewMesh.FaceCount = len(Mesh.polygons)
			NewMesh.Faces = []

			NewMesh.MeshCount = 3 if SourceCollection.objects[0].data.keys is not None else 2
			NewMesh.MeshData = []

			_Mesh0Data = MeshData()
			_Mesh0Data.Vertices = [Vertex() for i in range(NewMesh.VertexCount)]
			_Mesh0Data.Revision = 133121
			_Mesh0Data.VertexSize = 32

			_Mesh1Data = MeshData()
			_Mesh1Data.Vertices = [Vertex() for i in range(NewMesh.VertexCount)]
			_Mesh1Data.Revision = 12288
			_Mesh1Data.VertexSize = 24

			_Mesh2Data = MeshData()
			_Mesh2Data.Vertices = [Vertex() for i in range(NewMesh.VertexCount)]
			_Mesh2Data.Revision = 12
			_Mesh2Data.VertexSize = 8

			for _Face in Mesh.polygons:
				NewFace = Face()
				NewFace.Indices = []

				for LoopIndex in _Face.loop_indices:
					_Vertex = Mesh.loops[LoopIndex]
					Position = Mesh.vertices[_Vertex.vertex_index].co
					Normal = _Vertex.normal
					_UV = Mesh.uv_layers.active.data[LoopIndex].uv
					_UV.y = -_UV.y
					_Mesh0Data.Vertices[_Vertex.vertex_index] = (Vertex(Position=Position, Normal=Normal, Texture=_UV))

					if NewMesh.MeshCount > 1:
						Tangent = _Vertex.tangent
						Bitangent = _Vertex.bitangent_sign * Normal.cross(Tangent)
						_Mesh1Data.Vertices[_Vertex.vertex_index] = (Vertex(Tangent=Tangent, Bitangent=Bitangent))

						_BoneIndices = []
						_BoneWeights = []
						for GroupIndex, _ in enumerate(GroupNames):
							Weight = 0.0
							try:
								Weight = Mesh.vertices[_Vertex.vertex_index].groups[GroupIndex].weight
								Weight = int(Weight * 255)
								_BoneIndices.append(GroupIndex)
								_BoneWeights.append(Weight)
							except IndexError:
								while len(_BoneIndices) < 4:
									_BoneIndices.append(1)
									_BoneWeights.append(0)
								break
						
						_Mesh2Data.Vertices[_Vertex.vertex_index] = (Vertex(BoneIndices=_BoneIndices, RawWeights=_BoneWeights))

					NewFace.Indices.append(_Vertex.vertex_index)

				NewMesh.Faces.append(NewFace)

			NewMesh.MeshData.append(_Mesh0Data)
			NewMesh.MeshData.append(_Mesh1Data)
			NewMesh.MeshData.append(_Mesh2Data)

			# We need to investigate the Bounding Box further, as it seems to be wrong
			NewMesh.BoundingBoxLowerLeftCorner, NewMesh.BoundingBoxUpperRightCorner = GetBB(Object)
			NewMesh.MaterialID = 25702
			NewMesh.MaterialParameters = -86061050
			NewMesh.MaterialStuff = 0
			# Textures
			Ref = Refraction()
			Ref.Length = 1
			Ref.RGB = [0.0, 0.0, 0.0] # This value could've been edited in Blender so we need to update it
			NewMesh.Refraction = Ref
			NewMesh.Materials = Materials() # We cant edit that in Blender, so we set it to default
			NewMesh.LevelOfDetail = LevelOfDetail() # We don't need to update the LOD
			NewMesh.EmptyString = EmptyString() # We don't need to update the Empty String
			NewMesh.Flow = Flow() # We cant edit that in Blender, so we set it to default
			NewMeshData.Meshes.append(NewMesh)

	# Update the DRS File
	SourceFile.Mesh = NewMeshData

def CreateCylinder(Mesh: bpy.types.Mesh) -> CylinderShape:
	_CylinderShape = CylinderShape()
	_CylinderShape.CoordSystem = CMatCoordinateSystem()
	_CylinderShape.CoordSystem.Position = Vector((Mesh.location.x, Mesh.location.y - (Mesh.dimensions.z / 2), Mesh.location.z))
	Rotation = Mesh.rotation_euler.copy()
	Rotation.x -= math.pi / 2
	_CylinderShape.CoordSystem.Matrix = Matrix.LocRotScale(None, Rotation, None).to_3x3()
	_CylinderShape.CGeoCylinder = CGeoCylinder()
	_CylinderShape.CGeoCylinder.Radius = Mesh.dimensions.x / 2
	_CylinderShape.CGeoCylinder.Height = Mesh.dimensions.z
	_CylinderShape.CGeoCylinder.Center = Vector((0, 0, 0))

	return _CylinderShape

def CreateBox(Mesh: bpy.types.Mesh) -> BoxShape:
	_BoxShape = BoxShape()
	_BoxShape.CoordSystem = CMatCoordinateSystem()
	_BoxShape.CoordSystem.Position = Vector((Mesh.location.x, Mesh.location.y, Mesh.location.z))
	Rotation = Mesh.rotation_euler.copy()
	Rotation.x = -Rotation.x
	Rotation.y = -Rotation.y
	Rotation.z = -Rotation.z
	_BoxShape.CoordSystem.Matrix = Matrix.LocRotScale(None, Rotation, None).to_3x3()
	_BoxShape.CGeoAABox = CGeoAABox()
	_BoxShape.CGeoAABox.UpperRightCorner = Vector((Mesh.dimensions.x / 2, Mesh.dimensions.y / 2, Mesh.dimensions.z / 2))
	_BoxShape.CGeoAABox.LowerLeftCorner = Vector((-Mesh.dimensions.x / 2, -Mesh.dimensions.y / 2, -Mesh.dimensions.z / 2))

	return _BoxShape

def CreateSphere(Mesh: bpy.types.Mesh) -> SphereShape:
	_SphereShape = SphereShape()
	_SphereShape.CoordSystem = CMatCoordinateSystem()
	_SphereShape.CoordSystem.Position = Vector((Mesh.location.x, Mesh.location.y, Mesh.location.z))
	_SphereShape.CoordSystem.Matrix = Matrix.Identity(3)
	_SphereShape.CGeoSphere = CGeoSphere()
	_SphereShape.CGeoSphere.Center = Vector((0, 0, 0))
	_SphereShape.CGeoSphere.Radius = Mesh.dimensions.x / 2

	return _SphereShape

def CreateUniqueMesh(SourceCollection: bpy.types.Collection) -> bpy.types.Mesh:
	BM: bmesh.types.BMesh = bmesh.new()

	# As we have a defined structure we need to find the CDspMeshFile Object first
	if SourceCollection.objects is None:
		return None

	CDspMeshFileObject = SearchForObject("CDspMeshFile", SourceCollection)


	if CDspMeshFileObject is None:
		return None

	# Now we can iterate over the Meshes
	for Child in CDspMeshFileObject.children:
		if Child.type == "MESH":
			BM.from_mesh(Child.data)

	# Remove Duplicates
	bmesh.ops.remove_doubles(BM, verts=BM.verts, dist=0.0001)

	# Create the new Mesh
	UniqueMesh = bpy.data.meshes.new("UniqueMesh")
	BM.to_mesh(UniqueMesh)
	BM.free()

	return UniqueMesh

def CreateCGeoMesh(UniqueMesh: bpy.types.Mesh) -> CGeoMesh:
	_CGeoMesh = CGeoMesh()
	_CGeoMesh.IndexCount = len(UniqueMesh.polygons) * 3
	_CGeoMesh.VertexCount = len(UniqueMesh.vertices)
	_CGeoMesh.Faces = []
	_CGeoMesh.Vertices = []

	for _Face in UniqueMesh.polygons:
		NewFace = Face()
		NewFace.Indices = [_Face.vertices[0], _Face.vertices[1], _Face.vertices[2]]
		_CGeoMesh.Faces.append(NewFace)

	for _Vertex in UniqueMesh.vertices:
		_CGeoMesh.Vertices.append(Vector((_Vertex.co.x, _Vertex.co.y, _Vertex.co.z, 1.0)))

	return _CGeoMesh

def CreateCGeoOBBTree() -> CGeoOBBTree:
	return CGeoOBBTree()

def CreateCDspMeshFile() -> CDspMeshFile:
	pass

def CreateJointGroup(Empty = True) -> JointGroup:
	if Empty:
		return JointGroup()
	else:
		pass

def CreateDrwResourceMeta() -> DrwResourceMeta:
	return DrwResourceMeta()

def CreateCGeoPrimitiveContainer() -> CGeoPrimitiveContainer:
	return CGeoPrimitiveContainer()

def CreateCollisionShape(SourceCollection: bpy.types.Collection) -> CollisionShape:
	_CollisionShape = CollisionShape()
	CollisionShapeObject = SearchForObject("CollisionShape", SourceCollection)

	if CollisionShapeObject is None:
		return None

	for Child in CollisionShapeObject.children:
		if Child.type == "MESH":
			if Child.name.find("Cylinder") != -1:
				_CollisionShape.CylinderCount += 1
				_CollisionShape.Cylinders.append(CreateCylinder(Child))
			elif Child.name.find("Sphere") != -1:
				_CollisionShape.SphereCount += 1
				_CollisionShape.Spheres.append(CreateSphere(Child))
			elif Child.name.find("Box") != -1:
				_CollisionShape.BoxCount += 1
				_CollisionShape.Boxes.append(CreateBox(Child))

def ExportSkinnedMesh(operator, context, filepath: str, SourceCollection: bpy.types.Collection):
	pass

def ExportStaticObject(operator, context, filepath: str, SourceCollection: bpy.types.Collection):
	# We need to set the world matrix correctly for Battleforge Game Engine -> Matrix.Identity(4)
	# To do....

	# Create the DRS File
	NewDRSFile: DRS = DRS()
	# CGeoMesh
	_UniqueMesh = CreateUniqueMesh(SourceCollection) # Works perfectly fine
	if _UniqueMesh is None:
		ShowMessageBox("Could not create Unique Mesh from Collection, as no CDspMeshFile was found!", "Error", "ERROR")
		return {"CANCELLED"}

	_CGeoMesh: CGeoMesh = CreateCGeoMesh(_UniqueMesh) # Works perfectly fine
	# CGeoOBBTree
	_CGeoOBBTree: CGeoOBBTree = CreateCGeoOBBTree() # Maybe not needed
	# CDspMeshFile
	_CDspMeshFile: CDspMeshFile = CreateCDspMeshFile()
	# JointGroup
	_JointGroup: JointGroup = CreateJointGroup() # Not needed for static objects
	# drwResourceMeta
	_DrwResourceMeta: DrwResourceMeta = CreateDrwResourceMeta() # Dunno if needed
	# CGeoPrimitiveContainer
	_CGeoPrimitiveContainer: CGeoPrimitiveContainer = CreateCGeoPrimitiveContainer() # Always empty
	# CollisionShape
	_CollisionShape: CollisionShape = CreateCollisionShape(SourceCollection)
	if _CollisionShape is None:
		ShowMessageBox("Could not create CollisionShape from Collection, as no CollisionShape was found!", "Error", "ERROR")
		return {"CANCELLED"}

	# Update the DRS File
	NewDRSFile.CGeoMesh = _CGeoMesh
	NewDRSFile.CGeoOBBTree = _CGeoOBBTree
	NewDRSFile.CDspMeshFile = _CDspMeshFile
	NewDRSFile.Joints = _JointGroup
	NewDRSFile.DrwResourceMeta = _DrwResourceMeta
	NewDRSFile.CGeoPrimitiveContainer = _CGeoPrimitiveContainer
	NewDRSFile.CollisionShape = _CollisionShape

def VerifyModels(SourceCollection: bpy.types.Collection):
	UnifiedMesh: bmesh.types.BMesh = bmesh.new()

	for Object in SourceCollection.objects:
		if Object.type == "MESH":
			if len(Object.data.vertices) > 32767:
				ShowMessageBox("Mesh {} has more than 32767 Vertices. This is not supported by the game.".format(Object.name), "Error", "ERROR")
				return False
			UnifiedMesh.from_mesh(Object.data)

	UnifiedMesh.verts.ensure_lookup_table()
	UnifiedMesh.verts.index_update()
	bmesh.ops.remove_doubles(UnifiedMesh, verts=UnifiedMesh.verts, dist=0.0001)

	if len(UnifiedMesh.verts) > 32767:
		ShowMessageBox("The unified Mesh has more than 32767 Vertices. This is not supported by the game.", "Error", "ERROR")
		return False

	UnifiedMesh.free()

	return True

def SaveDRS(operator, context, filepath="", ExportSelection: bool = True):
	# Get the right Collection
	SourceCollection: bpy.types.Collection = None

	if ExportSelection:
		SourceCollection: bpy.types.Collection = context.collection
	else:
		SourceCollection: bpy.types.Collection = context.view_layer.active_layer_collection.collection

	if not VerifyModels(SourceCollection):
		return {"CANCELLED"}

	IsStateBased: bool = False # Also means save as *.bmg file
	IsSkinnedMesh: bool = False

	for Object in SourceCollection.objects:
		if Object.type == "ARMATURE":
			IsSkinnedMesh = True
		if Object.type == "MESH" and Object.name.startswith("MeshGridModule_"):
			IsStateBased = True

	if not IsSkinnedMesh and not IsStateBased:
		ExportStaticObject(operator, context, filepath, SourceCollection)

	# 	# What we need in every DRS File: CGeoMesh, CGeoOBBTree (empty), CDspJointMap, CDspMeshFile, DrwResourceMeta
	# 	# What we need in skinned DRS Files: CSkSkinInfo, CSkSkeleton, AnimationSet, AnimationTimings
	# 	# Models with Effects: EffectSet
	# 	# Static Objects need: CGeoPrimitiveContainer (empty), CollisionShape
	# 	# Destructable Objects need: StateBasedMeshSet, MeshSetGrid

	# 	# CollisionShape if static
	# elif LoadedDRSModels is not None:
	# 	# If we only Edit the Model(s) we keep the whole structures and only update the neccecary parts
	# 	for LoadedDRSModel in LoadedDRSModels:
	# 		LoadedDRSModel = LoadedDRSModel[0]
	# 		SourceFile: DRS = LoadedDRSModel[1]
	# 		SourceCollection: bpy.types.Collection = LoadedDRSModel[2]
	# 		SourceUsedTransform: bool = LoadedDRSModel[3]

	# 		# Set the current Collection as Active
	# 		bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[SourceCollection.name]

	# 		# Set the Active Object to the first Object in the Collection
	# 		bpy.context.view_layer.objects.active = SourceCollection.objects[0]

	# 		# Switch to Edit Mode
	# 		bpy.ops.object.mode_set(mode='EDIT')

	# 		# If the Source Mesh has been transformed, we need to revert the transformation before we can export it
	# 		# Set the Global Matrix
	# 		if SourceUsedTransform:
	# 			# Get the Armature Object if it exists
	# 			ArmatureObject = None

	# 			for Object in SourceCollection.objects:
	# 				if Object.type == "ARMATURE":
	# 					ArmatureObject = Object
	# 					break
	# 			if ArmatureObject is not None:
	# 				ArmatureObject.matrix_world = Matrix.Identity(4)
	# 			else:
	# 				for Object in SourceCollection.objects:
	# 					Object.matrix_world = Matrix.Identity(4)

	# 		# Update the Meshes
	# 		UpdateCDspMeshfile(SourceFile, SourceCollection)