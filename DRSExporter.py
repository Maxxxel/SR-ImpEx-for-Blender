import bpy
import bmesh
from typing import List
from mathutils import Vector, Matrix
from .DRSFile import DRS, CDspMeshFile, BattleforgeMesh, Face, EmptyString, LevelOfDetail, MeshData, Refraction, Vertex, Materials, Flow, CGeoMesh, CGeoOBBTree, CDspJointMap, DrwResourceMeta, CGeoPrimitiveContainer

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

def CreateUniqueMesh(SourceCollection: bpy.types.Collection, ExportCollection: bpy.types.Collection) -> bpy.types.Mesh:
	BM: bmesh.types.BMesh = bmesh.new()
	DEBUG_TOTAL_VERTICES = 0

	# Loop through all Objects and find the Meshes
	for Object in SourceCollection.objects:
		if Object.type == "MESH":
			BM.from_mesh(Object.data)
			DEBUG_TOTAL_VERTICES += len(Object.data.vertices)

	# Remove Duplicates
	bmesh.ops.remove_doubles(BM, verts=BM.verts, dist=0.0001)

	# Create the new Mesh
	UniqueMesh = bpy.data.meshes.new("UniqueMesh")
	BM.to_mesh(UniqueMesh)
	BM.free()

	# Link the new Mesh to the Collection
	NewMeshObject = bpy.data.objects.new("UniqueMesh", UniqueMesh)
	ExportCollection.objects.link(NewMeshObject)

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

def SaveDRS(operator, context, filepath="", LoadedDRSModels=None, EditModel=True):
	if EditModel is False:
		# Create a new Export Collection we will delete later
		ExportCollection: bpy.types.Collection = bpy.data.collections.new("ExportCollection")
		bpy.context.scene.collection.children.link(ExportCollection)

		NewFile: DRS = DRS()

		# What we need in every DRS File: CGeoMesh, CGeoOBBTree (empty), CDspJointMap, CDspMeshFile, DrwResourceMeta
		# What we need in skinned DRS Files: CSkSkinInfo, CSkSkeleton, AnimationSet, AnimationTimings
		# Models with Effects: EffectSet
		# Static Objects need: CGeoPrimitiveContainer (empty), CollisionShape
		# Destructable Objects need: StateBasedMeshSet, MeshSetGrid

		# Get Selected Colelction
		SourceCollection: bpy.types.Collection = bpy.context.view_layer.active_layer_collection.collection

		# Unique Mesh
		UniqueMesh = CreateUniqueMesh(SourceCollection, ExportCollection)

		# CGeoMesh
		_CGeoMesh = CreateCGeoMesh(UniqueMesh)
		NewFile.CGeoMesh = _CGeoMesh

		# CGeoOBBTree
		# Find out if needed and if so how its created
		NewFile.CGeoOBBTree = CGeoOBBTree()

		# CDspJointMap
		# Find out if needed and if so how its created
		NewFile.CDspJointMap = CDspJointMap()

		# CSkSkinInfo
		# Ignore for now

		# CSkSkeleton
		# Ignore for now

		# CDspMeshFile
		_CDspMeshFile = CDspMeshFile()

		# CDrwLocatorList if skinned unit
		# Ignore for now

		# DrwResourceMeta if static
		_DrwResourceMeta = DrwResourceMeta()

		# AnimationSet if skinned
		# Ignore for now

		# AnimationTimings if skinned
		# Ignore for now

		# EffectSet if skinned
		# Ignore for now

		# CGeoPrimitiveContainer if static
		_CGeoPrimitiveContainer = CGeoPrimitiveContainer()

		# CollisionShape if static
	elif LoadedDRSModels is not None:
		# If we only Edit the Model(s) we keep the whole structures and only update the neccecary parts
		for LoadedDRSModel in LoadedDRSModels:
			LoadedDRSModel = LoadedDRSModel[0]
			SourceFile: DRS = LoadedDRSModel[1]
			SourceCollection: bpy.types.Collection = LoadedDRSModel[2]
			SourceUsedTransform: bool = LoadedDRSModel[3]

			# Set the current Collection as Active
			bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[SourceCollection.name]

			# Set the Active Object to the first Object in the Collection
			bpy.context.view_layer.objects.active = SourceCollection.objects[0]

			# Switch to Edit Mode
			bpy.ops.object.mode_set(mode='EDIT')

			# If the Source Mesh has been transformed, we need to revert the transformation before we can export it
			# Set the Global Matrix
			if SourceUsedTransform:
				# Get the Armature Object if it exists
				ArmatureObject = None

				for Object in SourceCollection.objects:
					if Object.type == "ARMATURE":
						ArmatureObject = Object
						break
				if ArmatureObject is not None:
					ArmatureObject.matrix_world = Matrix.Identity(4)
				else:
					for Object in SourceCollection.objects:
						Object.matrix_world = Matrix.Identity(4)

			# Update the Meshes
			UpdateCDspMeshfile(SourceFile, SourceCollection)
	else:
		return {'CANCELLED'}
