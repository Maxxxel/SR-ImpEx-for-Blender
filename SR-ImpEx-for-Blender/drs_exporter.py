import math
import os
import subprocess
from os.path import dirname, realpath
from typing import List, Tuple, Dict
from uu import Error
from typing import List, Tuple, Dict
from uu import Error
import bpy
import bmesh
from mathutils import Vector, Matrix

from .ska_file import *
from .drs_utility import *
from .drs_definitions import *

resource_dir = dirname(realpath(__file__)) + "/resources"

def show_message_box(msg: str, Title: str = "Message Box", Icon: str = "INFO") -> None:
	def DrawMessageBox(self, context):
		self.layout.label(text=msg)

	bpy.context.window_manager.popup_menu(DrawMessageBox, title=Title, icon=Icon)

def search_for_object(object_name: str, collection: bpy.types.Collection) -> bpy.types.Object | None:
	'''Search for an object in a collection and its children by name. Returns the object if found, otherwise None.'''
	for obj in collection.objects:
		if obj.name.find(object_name) != -1:
			return obj

	for coll in collection.children:
		found_object = search_for_object(object_name, coll)
		if found_object is not None:
			return found_object

	return None

def mirror_mesh_on_axis(obj, axis='y'):
	"""
	Mirror a mesh along a specified global axis using Blender's built-in operations and
	correctly handle normals.

	Parameters:
	obj (bpy.types.Object): The object to mirror.
	axis (str): Global axis to mirror along, should be 'x', 'y', or 'z'.
	"""
	print(f"Mirroring object {obj.name} along axis {axis}...")
	# Validate axis
	axis = axis.lower()
	if axis not in ['x', 'y', 'z']:
		raise ValueError("Invalid axis. Use 'x', 'y', or 'z'.")

	# Deselect all objects
	bpy.ops.object.select_all(action='DESELECT')

	# Select the object
	bpy.context.view_layer.objects.active = obj
	obj.select_set(True)

	# Ensure the object is selected
	if not obj.select_get():
		raise ValueError(f"Object {obj.name} could not be selected.")

	# Determine the constraint axis
	constraint_axis = {
		'x': (True, False, False),
		'y': (False, True, False),
		'z': (False, False, True)
	}[axis]

	# Apply the mirror transformation
	bpy.ops.object.mode_set(mode='OBJECT')  # Ensure in object mode
	bpy.ops.transform.mirror(
		orient_type='GLOBAL',
		orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
		orient_matrix_type='GLOBAL',
		constraint_axis=constraint_axis
	)

	# Optional: update mesh data
	obj.data.update()

def get_bb(obj) -> Tuple[Vector, Vector]:
	'''Get the Bounding Box of an Object. Returns the minimum and maximum Vector of the Bounding Box.'''
	bb_min = Vector((0, 0, 0))
	bb_max = Vector((0, 0, 0))

	if obj.type == "MESH":
		for _vertex in obj.data.vertices:
			_vertex = _vertex.co

			if _vertex.x < bb_min.x:
				bb_min.x = _vertex.x
			if _vertex.y < bb_min.y:
				bb_min.y = _vertex.y
			if _vertex.z < bb_min.z:
				bb_min.z = _vertex.z
			if _vertex.x > bb_max.x:
				bb_max.x = _vertex.x
			if _vertex.y > bb_max.y:
				bb_max.y = _vertex.y
			if _vertex.z > bb_max.z:
				bb_max.z = _vertex.z

	return bb_min, bb_max

def get_scene_bb(collection: bpy.types.Collection) -> Tuple[Vector, Vector]:
	'''Get the Bounding Box of the whole Scene. Returns the minimum and maximum Vector of the Bounding Box.'''
	bb_min = Vector((0, 0, 0))
	bb_max = Vector((0, 0, 0))

	for obj in collection.objects:
		if obj.type == "MESH":
			BBMinObject, BBMaxObject = get_bb(obj)

			if BBMinObject.x < bb_min.x:
				bb_min.x = BBMinObject.x
			if BBMinObject.y < bb_min.y:
				bb_min.y = BBMinObject.y
			if BBMinObject.z < bb_min.z:
				bb_min.z = BBMinObject.z
			if BBMaxObject.x > bb_max.x:
				bb_max.x = BBMaxObject.x
			if BBMaxObject.y > bb_max.y:
				bb_max.y = BBMaxObject.y
			if BBMaxObject.z > bb_max.z:
				bb_max.z = BBMaxObject.z

	return bb_min, bb_max

def create_cylinder(mesh: bpy.types.Mesh) -> CylinderShape:
	'''Create a Cylinder Shape from a Mesh Object.'''
	cylinder_shape = CylinderShape()
	cylinder_shape.CoordSystem = CMatCoordinateSystem()
	cylinder_shape.CoordSystem.Position = Vector((mesh.location.x, mesh.location.y - (mesh.dimensions.z / 2), mesh.location.z))
	rotation = mesh.rotation_euler.copy()
	rotation.x -= math.pi / 2
	cylinder_shape.CoordSystem.Matrix = Matrix.LocRotScale(None, rotation, None).to_3x3()
	cylinder_shape.CGeoCylinder = CGeoCylinder()
	cylinder_shape.CGeoCylinder.Radius = mesh.dimensions.x / 2
	cylinder_shape.CGeoCylinder.Height = mesh.dimensions.z
	cylinder_shape.CGeoCylinder.Center = Vector((0, 0, 0))

	return cylinder_shape

def create_box(mesh: bpy.types.Mesh) -> BoxShape:
	'''Create a Box Shape from a Mesh Object.'''
	box_shape = BoxShape()
	box_shape.CoordSystem = CMatCoordinateSystem()
	box_shape.CoordSystem.Position = Vector((mesh.location.x, mesh.location.y, mesh.location.z))
	rotation = mesh.rotation_euler.copy()
	rotation.x = -rotation.x
	rotation.y = -rotation.y
	rotation.z = -rotation.z
	box_shape.CoordSystem.Matrix = Matrix.LocRotScale(None, rotation, None).to_3x3()
	box_shape.CGeoAABox = CGeoAABox()
	box_shape.CGeoAABox.UpperRightCorner = Vector((mesh.dimensions.x / 2, mesh.dimensions.y / 2, mesh.dimensions.z / 2))
	box_shape.CGeoAABox.LowerLeftCorner = Vector((-mesh.dimensions.x / 2, -mesh.dimensions.y / 2, -mesh.dimensions.z / 2))

	return box_shape

def create_sphere(mesh: bpy.types.Mesh) -> SphereShape:
	'''Create a Sphere Shape from a Mesh Object.'''
	sphere_shape = SphereShape()
	sphere_shape.CoordSystem = CMatCoordinateSystem()
	sphere_shape.CoordSystem.Position = Vector((mesh.location.x, mesh.location.y, mesh.location.z))
	sphere_shape.CoordSystem.Matrix = Matrix.Identity(3)
	sphere_shape.CGeoSphere = CGeoSphere()
	sphere_shape.CGeoSphere.Center = Vector((0, 0, 0))
	sphere_shape.CGeoSphere.Radius = mesh.dimensions.x / 2

	return sphere_shape

def create_obb_node(unique_mesh: bpy.types.Mesh) -> OBBNode:
	'''Create an OBB Node for the OBB Tree.'''
	obb_node = OBBNode()
	obb_node.NodeDepth = 0
	obb_node.CurrentTriangleCount = 0
	obb_node.MinimumTrianglesFound = len(unique_mesh.polygons)
	obb_node.Unknown1 = 0
	obb_node.Unknown2 = 0
	obb_node.Unknown3 = 0
	obb_node.OrientedBoundingBox = CMatCoordinateSystem()
	obb_node.OrientedBoundingBox.Position = Vector((0, 0, 0)) # We need to update this later as we need to calculate the center of the mesh
	obb_node.OrientedBoundingBox.Matrix = Matrix.Identity(3) # We need to update this later as we need to calculate the rotation of the mesh

	return obb_node

def create_unique_mesh(source_collection: bpy.types.Collection) -> bpy.types.Mesh:
	'''Create a Unique Mesh from a Collection of Meshes.'''
	bm: bmesh.types.BMesh = bmesh.new()

	# As we have a defined structure we need to find the CDspMeshFile object first
	if source_collection.objects is None:
		return None

	cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)

	if cdspmeshfile_object is None:
		return None
	
	# Fix if the object is the Mesh itself
	if cdspmeshfile_object.type == "MESH":
		bm.from_mesh(cdspmeshfile_object.data)
	else:
		# Now we can iterate over the Meshes
		for child in cdspmeshfile_object.children:
			if child.type == "MESH":
				bm.from_mesh(child.data)

	# Remove Duplicates
	bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

	# Create the new Mesh
	unique_mesh = bpy.data.meshes.new("unique_mesh")
	bm.to_mesh(unique_mesh)
	bm.free()

	return unique_mesh

def create_mesh(mesh: bpy.types.Mesh, mesh_index: int, model_name: str, filepath: str) -> BattleforgeMesh:
	'''Create a Battleforge Mesh from a Blender Mesh Object.'''
	mesh.data.calc_tangents()
	new_mesh = BattleforgeMesh()
	new_mesh.VertexCount = len(mesh.data.vertices)
	new_mesh.FaceCount = len(mesh.data.polygons)
	new_mesh.Faces = []

	new_mesh.MeshCount = 2
	new_mesh.MeshData = []

	_mesh_0_data = MeshData()
	_mesh_0_data.Vertices = [Vertex() for _ in range(new_mesh.VertexCount)]
	_mesh_0_data.Revision = 133121
	_mesh_0_data.VertexSize = 32

	_mesh_1_data = MeshData()
	_mesh_1_data.Vertices = [Vertex() for _ in range(new_mesh.VertexCount)]
	_mesh_1_data.Revision = 12288
	_mesh_1_data.VertexSize = 24

	for _face in mesh.data.polygons:
		new_face = Face()
		new_face.Indices = []

		for index in _face.loop_indices:
			vertex = mesh.data.loops[index]
			position = mesh.data.vertices[vertex.vertex_index].co
			normal = vertex.normal
			#TODO: Maybe we need to flip the Y value of the Normal as we convert from OpenGL to DirectX
			uv = mesh.data.uv_layers.active.data[index].uv.copy()
			uv.y = -uv.y
			_mesh_0_data.Vertices[vertex.vertex_index] = Vertex(Position=position, Normal=normal, Texture=uv)

			if new_mesh.MeshCount > 1:
				tangent = vertex.tangent
				bitangent = vertex.bitangent_sign * normal.cross(tangent)
				# Switch X and Y as the Tangent is flipped
				tangent = Vector((tangent.y, tangent.x, tangent.z))
				_mesh_1_data.Vertices[vertex.vertex_index] = Vertex(Tangent=tangent, Bitangent=bitangent)

			new_face.Indices.append(vertex.vertex_index)

		new_mesh.Faces.append(new_face)

	new_mesh.MeshData.append(_mesh_0_data)
	new_mesh.MeshData.append(_mesh_1_data)

	# We need to investigate the Bounding Box further, as it seems to be wrong
	new_mesh.BoundingBoxLowerLeftCorner, new_mesh.BoundingBoxUpperRightCorner = get_bb(mesh)
	new_mesh.MaterialID = 25702
	# Node Group for Access the Data
	MeshMaterial: bpy.types.Material = mesh.material_slots[0].material
	MaterialNodes: List[bpy.types.Node] = MeshMaterial.node_tree.nodes
	# Find the DRS Node
	for Node in MaterialNodes:
		if Node.type == "GROUP":
			if Node.node_tree.name.find("DRS") != -1:
				ColorMap = Node.inputs[0]
				# ColorAlpha = Node.inputs[1] # We don't need this
				NormalMap = Node.inputs[2]
				MetallicMap = Node.inputs[3]
				RoughnessMap = Node.inputs[4]
				EmissionMap = Node.inputs[5]
				ScratchMap = Node.inputs[6]
				DistortionMap = Node.inputs[7]
				RefractionMap = Node.inputs[8]
				# RefractionAlpha = Node.inputs[9] # We don't need this
				RefractionColor = Node.inputs[10]
				FluMap = Node.inputs[11]
				# FluAlpha = Node.inputs[12] # We don't need this
				break
	if FluMap is None or FluMap.is_linked is False:
		# -86061055: no MaterialStuff, no Fluid, no String, no LOD
		new_mesh.MaterialParameters = -86061055
	else:
		# -86061050: All Materials
		new_mesh.MaterialParameters = -86061050
		new_mesh.MaterialStuff = 0
		# Level of Detail
		new_mesh.LevelOfDetail = LevelOfDetail() # We don't need to update the LOD
		# Empty String
		new_mesh.EmptyString = EmptyString() # We don't need to update the Empty String
		# Flow
		new_mesh.Flow = Flow() # Maybe later we can add some flow data in blender

	# Individual Material Parameters depending on the MaterialID:
	new_mesh.BoolParameter = 0
	BoolParamBitFlag = 0
	# Textures
	new_mesh.Textures = Textures()
	# Check if the ColorMap exists
	if ColorMap is None:
		ValueError("The ColorMap Node is unset!")

	output_folder = os.path.dirname(filepath)

	if ColorMap.is_linked:
		new_mesh.Textures.Length+=1
		ColMapTexture = Texture()
		ColMapTexture.Name = model_name + "_" + str(mesh_index) + "_col"
		ColMapTexture.Length = ColMapTexture.Name.__len__()
		ColMapTexture.Identifier = 1684432499
		new_mesh.Textures.Textures.append(ColMapTexture)
		# Check ColorMap.links[0].from_node.image for the Image
		if ColorMap.links[0].from_node.type == "TEX_IMAGE":
			# Export the Image as a DDS File (DXT3)
			_Img = ColorMap.links[0].from_node.image
			
			if _Img is not None:
				_TempPath = bpy.path.abspath("//") + ColMapTexture.Name + ".png"
				_Img.file_format = "PNG"
				_Img.save(filepath=_TempPath)
				args = ["-ft", "dds", "-f", "DXT5", "-dx9", "-pow2", "-srgb", "-y", ColMapTexture.Name + ".dds", "-o", output_folder]
				subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)
				os.remove(_TempPath)
			else:
				ValueError("The ColorMap Texture is not an Image or the Image is None!")

	if NormalMap is not None and NormalMap.is_linked:
		new_mesh.Textures.Length+=1
		NorMapTexture = Texture()
		NorMapTexture.Name = model_name + "_" + str(mesh_index) + "_nor"
		NorMapTexture.Length = NorMapTexture.Name.__len__()
		NorMapTexture.Identifier = 1852992883
		new_mesh.Textures.Textures.append(NorMapTexture)
		BoolParamBitFlag += 100000000000000000
		# Check NormalMap.links[0].from_node.image for the Image
		if NormalMap.links[0].from_node.type == "TEX_IMAGE":
			# Export the Image as a DDS File (DXT1)
			_Img = NormalMap.links[0].from_node.image

			if _Img is not None:
				_TempPath = bpy.path.abspath("//") + NorMapTexture.Name + ".png"
				_Img.file_format = "PNG"
				_Img.save(filepath=_TempPath)
				args = ["-ft", "dds", "-f", "DXT1", "-dx9", "-pow2", "-srgb", "-at", "0.0", "-y", NorMapTexture.Name + ".dds", "-o", output_folder]
				subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)
				os.remove(_TempPath)
			else:
				ValueError("The NormalMap Texture is not an Image or the Image is None!")

	if (MetallicMap is not None and MetallicMap.is_linked) or (RoughnessMap is not None and RoughnessMap.is_linked) or (EmissionMap is not None and EmissionMap.is_linked):
		new_mesh.Textures.Length+=1
		MetMapTexture = Texture()
		MetMapTexture.Name = model_name + "_" + str(mesh_index) + "_par"
		MetMapTexture.Length = MetMapTexture.Name.__len__()
		MetMapTexture.Identifier = 1936745324
		new_mesh.Textures.Textures.append(MetMapTexture)
		BoolParamBitFlag += 10000000000000000
		# Par Map is a combination of Metallic, Roughness and Fluid Map and Emission Map. We need to combine them in an array and push them to the ImageToExport List
		img_R, img_G, img_A = None, None, None
		pixels_R, pixels_G, pixels_A = None, None, None

		if MetallicMap is not None and MetallicMap.is_linked:
			# This can either be a Map or a Separate RGB Node
			if MetallicMap.links[0].from_node.type == "SEPRGB" or MetallicMap.links[0].from_node.type == "SEPARATE_COLOR":
				# We ned to get the Input
				img_R = MetallicMap.links[0].from_node.inputs[0].links[0].from_node.image
				assert img_R is not None and img_R.type == "IMAGE"
				pixels_R = img_R.pixels[:]
			else:
				img_R = MetallicMap.links[0].from_node.image
				assert img_R is not None and img_R.pixels[:].__len__() > 0
				pixels_R = img_R.pixels[:]
		if RoughnessMap is not None and RoughnessMap.is_linked:
			# This can either be a Map or a Separate RGB Node
			if RoughnessMap.links[0].from_node.type == "SEPRGB" or RoughnessMap.links[0].from_node.type == "SEPARATE_COLOR":
				# We ned to get the Input
				img_G = RoughnessMap.links[0].from_node.inputs[0].links[0].from_node.image
				assert img_G is not None and img_G.type == "IMAGE"
				pixels_G = img_G.pixels[:]
			else:
				img_G = RoughnessMap.links[0].from_node.image
				assert img_G is not None and img_G.pixels[:].__len__() > 0
				pixels_G = img_G.pixels[:]
		if EmissionMap is not None and EmissionMap.is_linked:
			pass
		if EmissionMap is not None and EmissionMap.is_linked:
			# This can either be a Map or a Separate RGB Node
			if EmissionMap.links[0].from_node.type == "SEPRGB" or EmissionMap.links[0].from_node.type == "SEPARATE_COLOR":
				# We ned to get the Input
				img_A = EmissionMap.links[0].from_node.inputs[0].links[0].from_node.image
				assert img_A is not None and img_A.type == "IMAGE"
				pixels_A = img_A.pixels[:]
			else:
				img_A = EmissionMap.links[0].from_node.image
				assert img_A is not None and img_A.pixels[:].__len__() > 0
				pixels_A = img_A.pixels[:]
		
		# Get the Image Size by either the R, G or A Image
		if img_R is not None:
			Width = img_R.size[0]
			Height = img_R.size[1]
		elif img_G is not None:
			Width = img_G.size[0]
			Height = img_G.size[1]
		elif img_A is not None:
			Width = img_A.size[0]
			Height = img_A.size[1]
		else:
			ValueError("No Image found for the Parameter Map!")

		# Combine the Images
		new_img = bpy.data.images.new(name=MetMapTexture.Name, width=Width, height=Height, alpha=True, float_buffer=False)
		new_pixels = []

		for i in range(0, Width * Height * 4, 4):
			red_value = pixels_R[i] if pixels_R is not None else 0
			green_value = pixels_G[i + 1] if pixels_G is not None else 0
			# TODO: Fluid
			blue_value = 0
			alpha_value = pixels_A[i + 3] if pixels_A is not None else 0
			new_pixels.extend([red_value, green_value, blue_value, alpha_value])

		new_img.pixels = new_pixels
		new_img.file_format = "PNG"
		new_img.update()

		# Export the Image as a DDS File (DXT5)
		_TempPath = bpy.path.abspath("//") + MetMapTexture.Name + ".png"
		new_img.save(filepath=_TempPath)

		# convert the image to dds dxt5 by using texconv.exe in the resources folder
		args = ["-ft", "dds", "-f", "DXT5", "-dx9", "-bc", "d", "-pow2", "-y", MetMapTexture.Name + ".dds", "-o", output_folder]
		subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)

		# Remove the Temp File
		os.remove(_TempPath)

	# Set the Bool Parameter by a bin -> dec conversion
	new_mesh.BoolParameter = int(str(BoolParamBitFlag), 2)
	# Refraction
	Ref = Refraction()
	Ref.Length = 1
	Ref.RGB = list(RefractionColor.default_value)[:3]
	new_mesh.Refraction = Ref
	# Materials
	new_mesh.Materials = Materials() # Almost no material data is used in the game, so we set it to defaults

	return new_mesh

def create_cgeo_mesh(unique_mesh: bpy.types.Mesh) -> CGeoMesh:
	'''Create a CGeoMesh from a Blender Mesh Object.'''
	_cgeo_mesh = CGeoMesh()
	_cgeo_mesh.IndexCount = len(unique_mesh.polygons) * 3
	_cgeo_mesh.VertexCount = len(unique_mesh.vertices)
	_cgeo_mesh.Faces = []
	_cgeo_mesh.Vertices = []

	for _face in unique_mesh.polygons:
		new_face = Face()
		new_face.Indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
		_cgeo_mesh.Faces.append(new_face)

	for _vertex in unique_mesh.vertices:
		_cgeo_mesh.Vertices.append(Vector((_vertex.co.x, _vertex.co.y, _vertex.co.z, 1.0)))

	return _cgeo_mesh

def create_cgeo_obb_tree(unique_mesh: bpy.types.Mesh) -> CGeoOBBTree:
	'''Create a CGeoOBBTree from a Blender Mesh Object.'''
	_cgeo_obb_tree = CGeoOBBTree()
	_cgeo_obb_tree.TriangleCount = len(unique_mesh.polygons)
	_cgeo_obb_tree.Faces = []

	for _face in unique_mesh.polygons:
		new_face = Face()
		new_face.Indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
		_cgeo_obb_tree.Faces.append(new_face)

	_cgeo_obb_tree.MatrixCount = 0
	_cgeo_obb_tree.OBBNodes = []

	for _ in range(_cgeo_obb_tree.MatrixCount):
		_cgeo_obb_tree.OBBNodes.append(create_obb_node(unique_mesh))

	return _cgeo_obb_tree

def create_cdsp_meshfile(source_collection: bpy.types.Collection, model_name: str, filepath: str) -> CDspMeshFile:
	'''Create a CDspMeshFile from a Collection of Meshes.'''
	cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)
	_cdsp_meshfile = CDspMeshFile()
	_cdsp_meshfile.MeshCount = 0

	# Check if the CDspMeshFile Object is a Mesh Object
	if cdspmeshfile_object.type == "MESH":
		_cdsp_meshfile.MeshCount += 1
		_cdsp_meshfile.Meshes.append(create_mesh(cdspmeshfile_object, _cdsp_meshfile.MeshCount, model_name, filepath))
	else:
		for child in cdspmeshfile_object.children:
			if child.type == "MESH":
				_cdsp_meshfile.MeshCount += 1
				_cdsp_meshfile.Meshes.append(create_mesh(child, _cdsp_meshfile.MeshCount, model_name, filepath))

	_cdsp_meshfile.BoundingBoxLowerLeftCorner = Vector((0, 0, 0))
	_cdsp_meshfile.BoundingBoxUpperRightCorner = Vector((0, 0, 0))

	for _mesh in _cdsp_meshfile.Meshes:
		_cdsp_meshfile.BoundingBoxLowerLeftCorner.x = min(_cdsp_meshfile.BoundingBoxLowerLeftCorner.x, _mesh.BoundingBoxLowerLeftCorner.x)
		_cdsp_meshfile.BoundingBoxLowerLeftCorner.y = min(_cdsp_meshfile.BoundingBoxLowerLeftCorner.y, _mesh.BoundingBoxLowerLeftCorner.y)
		_cdsp_meshfile.BoundingBoxLowerLeftCorner.z = min(_cdsp_meshfile.BoundingBoxLowerLeftCorner.z, _mesh.BoundingBoxLowerLeftCorner.z)

		_cdsp_meshfile.BoundingBoxUpperRightCorner.x = max(_cdsp_meshfile.BoundingBoxUpperRightCorner.x, _mesh.BoundingBoxUpperRightCorner.x)
		_cdsp_meshfile.BoundingBoxUpperRightCorner.y = max(_cdsp_meshfile.BoundingBoxUpperRightCorner.y, _mesh.BoundingBoxUpperRightCorner.y)
		_cdsp_meshfile.BoundingBoxUpperRightCorner.z = max(_cdsp_meshfile.BoundingBoxUpperRightCorner.z, _mesh.BoundingBoxUpperRightCorner.z)

	return _cdsp_meshfile

def create_cdsp_jointmap(source_collection: bpy.types.Collection) -> Tuple[CDspJointMap, dict]:
	'''Create a CDspJointMap. If empty is True, the CDspJointMap will be empty.'''
	if source_collection is None:
		return CDspJointMap(), {}
	else:
		_bone_map = {}
		_joint_map = CDspJointMap()
		# Get the CDspMeshFile Object
		cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)
		# Loop the MeshData
		for child in cdspmeshfile_object.children:
			if child.type == "MESH":
				_joint_map.JointGroupCount += 1
				# Get the Vertex Groups
				_vertex_groups = child.vertex_groups
				# Init the Bone ID Counter
				_bone_id = 0
				# Init the temp JointGroups List
				_temp_joint_group = []
				# Loop the Vertex Groups
				for _vertex_group in _vertex_groups:
					# Get the Bone from the Vertex Group
					_bone_Name = _vertex_group.name
					_temp_joint_group.append(_bone_id)
					_bone_map[_bone_Name] = _bone_id
					_bone_id += 1
				_joint_map.JointGroups.append(_temp_joint_group)
		return _joint_map, _bone_map

def create_csk_skin_info(source_collection: bpy.types.Collection, unique_mesh: bpy.types.Mesh) -> CSkSkinInfo:
	_csk_skin_info = CSkSkinInfo()
	
	_csk_skin_info.VertexCount = len(unique_mesh.vertices)
	# Each Vertex has 4 Weights and 4 Bone Indices
	_csk_skin_info.VertexData = []
	for _ in range(_csk_skin_info.VertexCount):
		_vertex = unique_mesh.vertices[_]
		_vertex_data = VertexData()
		_vertex_data.BoneIndices = [0, 0, 0, 0]
		_vertex_data.Weights = [0.0, 0.0, 0.0, 0.0]
		for i, _group in enumerate(_vertex.groups):
			_vertex_data.BoneIndices[i] = _group.group
			_vertex_data.Weights[i] = _group.weight
		_csk_skin_info.VertexData.append(_vertex_data)
	return _csk_skin_info

def create_csk_skeleton(source_collection: bpy.types.Collection, bone_map: dict) -> CSkSkeleton:
	_csk_skeleton = CSkSkeleton()
	armature_object = search_for_object("CSkSkeleton", source_collection)
	_csk_skeleton.BoneCount = len(armature_object.data.bones)
	_csk_skeleton.BoneMatrixCount = len(armature_object.data.bones)
	_csk_skeleton.BoneMatrices = []
	_csk_skeleton.Bones = []

	for blender_bone in armature_object.data.bones:
		_bone = Bone()
		_bone.Name = blender_bone.name
		_bone.NameLength = blender_bone.name.__len__()
		_bone.Identifier = bone_map.get(blender_bone.name)
		_bone.Version = hash(blender_bone.name)
		_bone.ChildCount = len(blender_bone.children)
		_bone.Children = []
		for _child in blender_bone.children:
			_bone.Children.append(bone_map.get(_child.name))
		_csk_skeleton.Bones.append(_bone)

		_bone_matrix = BoneMatrix()
		_bone_matrix.BoneVertices = []
		_bone_parent = blender_bone.parent
		_blender_bone_matrix = blender_bone.matrix_local
		_Rot = _blender_bone_matrix.to_3x3()
		_Loc = _blender_bone_matrix.to_translation()
		_Vector3 = -(_Rot.inverted() @ _Loc)
		_Vector0 = _Rot.col[0]
		_Vector1 = _Rot.col[1]
		_Vector2 = _Rot.col[2]

		for _ in range(4):
			_bone_vertex = BoneVertex()
			if _ == 0:
				_bone_vertex.Parent = bone_map.get(_bone_parent.name) if _bone_parent is not None else -1
				_bone_vertex.Position = Vector((_Vector0.x, _Vector1.x, _Vector2.x))
			elif _ == 1:
				_bone_vertex.Parent = bone_map.get(blender_bone.name)
				_bone_vertex.Position = Vector((_Vector0.y, _Vector1.y, _Vector2.y))
			elif _ == 2:
				_bone_vertex.Parent = 0
				_bone_vertex.Position = Vector((_Vector0.z, _Vector1.z, _Vector2.z))
			elif _ == 3:
				_bone_vertex.Parent = 0
				_bone_vertex.Position = Vector((_Vector3.x, _Vector3.y, _Vector3.z))
			_bone_matrix.BoneVertices.append(_bone_vertex)
		_csk_skeleton.BoneMatrices.append(_bone_matrix)

	return _csk_skeleton

def create_drw_resource_meta() -> DrwResourceMeta:
	'''Create a DrwResourceMeta.'''
	return DrwResourceMeta()

def create_cgeo_primitive_container() -> CGeoPrimitiveContainer:
	'''Create a CGeoPrimitiveContainer.'''
	return CGeoPrimitiveContainer()

def create_collision_shape(source_collection: bpy.types.Collection) -> CollisionShape:
	'''Create a Collision Shape from a Collection of Meshes.'''
	_collision_shape = CollisionShape()
	collision_shape_object = search_for_object("CollisionShape", source_collection)

	if collision_shape_object is None:
		return None

	for child in collision_shape_object.children:
		if child.type == "MESH":
			if child.name.find("Cylinder") != -1:
				_collision_shape.CylinderCount += 1
				_collision_shape.Cylinders.append(create_cylinder(child))
			elif child.name.find("Sphere") != -1:
				_collision_shape.SphereCount += 1
				_collision_shape.Spheres.append(create_sphere(child))
			elif child.name.find("Box") != -1:
				_collision_shape.BoxCount += 1
				_collision_shape.Boxes.append(create_box(child))

	return _collision_shape

def get_bone_keyframe_data(nla_strip: bpy.types.NlaStrip) -> Dict:
	action = nla_strip.action
	if not action:
		raise ValueError("No action associated with the NLA strip")
	
	bone_keyframes = {}
	max_frame = max(keyframe.co[0] for fcurve in action.fcurves for keyframe in fcurve.keyframe_points)
	
	for fcurve in action.fcurves:
		data_path = fcurve.data_path
		if 'pose.bones' not in data_path:
			continue
		
		# Extract the bone name and the property (location, rotation)
		path_elements = data_path.split('"')
		bone_name = path_elements[1]
		property_name = path_elements[2].split('.')[-1]
		
		if bone_name not in bone_keyframes:
			bone_keyframes[bone_name] = {
				'frames': set(),
				'location': {},
				'rotation': {}
			}
		
		# Get the keyframe points
		for keyframe in fcurve.keyframe_points:
			frame = keyframe.co[0]
			value = keyframe.co[1]
			bone_keyframes[bone_name]['frames'].add(frame)
			
			if 'location' in property_name:
				if frame not in bone_keyframes[bone_name]['location']:
					bone_keyframes[bone_name]['location'][frame] = [None, None, None]
				index = fcurve.array_index
				bone_keyframes[bone_name]['location'][frame][index] = value
			
			if 'rotation' in property_name:
				if frame not in bone_keyframes[bone_name]['rotation']:
					bone_keyframes[bone_name]['rotation'][frame] = [None, None, None, None]
				index = fcurve.array_index
				bone_keyframes[bone_name]['rotation'][frame][index] = value
	
	# Convert the sets to sorted lists and normalize frame times
	result = {}
	for bone_name, data in bone_keyframes.items():
		frames = sorted(list(data['frames']))
		result[bone_name] = {
			'number_of_frames_affecting_this_bone': len(frames),
			'affected_times': [frame / max_frame for frame in frames],
			'location': [data['location'][frame] for frame in frames if frame in data['location']],
			'rotation': [data['rotation'][frame] for frame in frames if frame in data['rotation']]
		}
	
	return result

def get_bone_keyframe_data2(action_name: str) -> Dict:
	action: bpy.types.Action = bpy.data.actions.get(action_name)
	if not action:
		raise ValueError(f"Action '{action_name}' not found")
	
	bone_keyframes = {}
	max_frame = max(keyframe.co[0] for fcurve in action.fcurves for keyframe in fcurve.keyframe_points)
	test = bpy.data.actions[action_name].groups
	print(test)
	for g in test:
		print(f"Group: {g.name}")
	group: bpy.types.ActionGroup
	for group in action.groups:
		bone_name = group.name
		bone_keyframes[bone_name] = {
			'frames': set(),
			'location': {},
			'rotation': {}
		}

		for channel in group.channels:
			data_path = channel.data_path
			property_name = data_path.split('.')[-1]

			for keyframe in channel.keyframe_points:
				frame = keyframe.co[0]
				value = keyframe.co[1]
				bone_keyframes[bone_name]['frames'].add(frame)

				if 'location' in property_name:
					if frame not in bone_keyframes[bone_name]['location']:
						bone_keyframes[bone_name]['location'][frame] = [None, None, None]
					index = channel.array_index
					bone_keyframes[bone_name]['location'][frame][index] = value

				if 'rotation' in property_name:
					if frame not in bone_keyframes[bone_name]['rotation']:
						bone_keyframes[bone_name]['rotation'][frame] = [None, None, None, None]
					index = channel.array_index
					bone_keyframes[bone_name]['rotation'][frame][index] = value

	# Convert the sets to sorted lists and normalize frame times
	result = {}
	for bone_name, data in bone_keyframes.items():
		frames = sorted(list(data['frames']))
		result[bone_name] = {
			'number_of_frames_affecting_this_bone': len(frames),
			'affected_times': [frame / max_frame for frame in frames],
			'location': [data['location'][frame] for frame in frames if frame in data['location']],
			'rotation': [data['rotation'][frame] for frame in frames if frame in data['rotation']]
		}
	
	return result

def create_new_ska_animation(animation: bpy.types.NlaTrack) -> SKA:
	nla_strip: bpy.types.NlaStrip = animation.strips[0]
	fps = bpy.context.scene.render.fps
	ska_animation = SKA()
	# Setup the Animation Data
	ska_animation.AnimationData = SKAAnimationData()
	ska_animation.AnimationData.Duration = (nla_strip.frame_end - nla_strip.frame_start) / fps
	# ska_animation.AnimationData.UnusedItTwo = 0 # by default, but maybe we need to change it?

	ska_animation.Times = []
	ska_animation.KeyframeData = []
	ska_animation.Headers = []

	# Get Keyframes
	keyframes = get_bone_keyframe_data(nla_strip)
	keyframes_2 = get_bone_keyframe_data2(nla_strip.action.name)
	current_frame = 0

	# Loop over the Keyframes
	for bone_name, data in keyframes.items():
		# Create two new SKAHeader Objects for the Location and Rotation
		header_location = SKAHeader()
		header_location.FrameType = 0
		header_location.BoneId = hash(bone_name)
		header_location.Tick = current_frame
		header_location.Interval = max(len(data['location']), 1)
		current_frame += header_location.Interval
		# Loop the Location Data
		if len(data['location']) > 0:
			for location_data in data['location']:
				header_location_keyyframe = SKAKeyframe()
				header_location_keyyframe.VectorData = location_data
				ska_animation.KeyframeData.append(header_location_keyyframe)
		else:
			Error("No Location Data found for Bone: " + bone_name)

		header_rotation = SKAHeader()
		header_rotation.FrameType = 1
		header_rotation.BoneId = hash(bone_name)
		header_rotation.Tick = current_frame
		header_rotation.Interval = max(len(data['rotation']), 1)
		current_frame += header_rotation.Interval
		# Loop the Rotation Data
		if len(data['rotation']) > 0:
			for rotation_data in data['rotation']:
				header_rotation_keyframe = SKAKeyframe()
				header_rotation_keyframe.CurveData = rotation_data
				ska_animation.KeyframeData.append(header_rotation_keyframe)
		else:
			Error("No Rotation Data found for Bone: " + bone_name)

		# Add the Headers to the SKA Object
		ska_animation.Headers.append(header_location)
		ska_animation.Headers.append(header_rotation)

	ska_animation.Length = current_frame
		
	return ska_animation

def set_origin_to_world_origin(source_collection: bpy.types.Collection) -> None:
	for obj in source_collection.objects:
		if obj.type == "MESH":
			# Set the object's active scene to the current scene
			bpy.context.view_layer.objects.active = obj
			# Select the object
			obj.select_set(True)
			# Set the origin to the world origin (0, 0, 0)
			bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
			# Deselect the object
			obj.select_set(False)
	# Move the cursor back to the world origin
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)

def export_static_object(operator, context, filepath: str, source_collection: bpy.types.Collection, use_apply_transform: bool) -> None:
	'''Export a Static Object to a DRS File.'''
	# TODO: We need to set the world matrix correctly for Battleforge Game Engine -> Matrix.Identity(4)
 
	# Model Name COmes right after the DRSModel_ Prefix and before the _Static Suffix
	model_name = source_collection.name[source_collection.name.find("DRSModel_") + 9:source_collection.name.find("_Static")]
	# Create an empty DRS File
	new_drs_file: DRS = DRS()

	# First we need to set the origin of all meshes to the center of the scene
	set_origin_to_world_origin(source_collection)
 
	if use_apply_transform:
		# Get CDspMeshFile Object
		cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)
		# Apply the Transformation to the CDspMeshFile Object
		for child in cdspmeshfile_object.children:
			if child.type == "MESH":
				mirror_mesh_on_axis(child, axis='y')

		# Get the CollisionShape Object
		collision_shape_object = search_for_object("CollisionShape", source_collection)
		
		if collision_shape_object is not None:
			# Apply the Transformation to the CollisionShape Object
			for child in collision_shape_object.children:
				if child.type == "MESH":
					mirror_mesh_on_axis(child, axis='y')

	unique_mesh = create_unique_mesh(source_collection) # Works perfectly fine
	if unique_mesh is None:
		show_message_box("Could not create Unique Mesh from Collection, as no CDspMeshFile was found!", "Error", "ERROR")
		return {"CANCELLED"}

	# CGeoMesh
	_cgeo_mesh: CGeoMesh = create_cgeo_mesh(unique_mesh) # Works perfectly fine
	new_drs_file.PushNode("CGeoMesh", _cgeo_mesh)
	# CGeoOBBTree
	_cgeo_obb_tree: CGeoOBBTree = create_cgeo_obb_tree(unique_mesh) # Maybe not needed??? We use a simple apporach for now with just one OBBNode, which is the whole mesh
	new_drs_file.PushNode("CGeoOBBTree", _cgeo_obb_tree)
	# CDspJointMap
	_cdsp_jointmap, _ = create_cdsp_jointmap() # Not needed for static objects, means we can leave it empty
	new_drs_file.PushNode("CDspJointMap", _cdsp_jointmap)
	# CDspMeshFile
	_cdsp_meshfile: CDspMeshFile = create_cdsp_meshfile(source_collection, model_name, filepath) # Works perfectly fine
	new_drs_file.PushNode("CDspMeshFile", _cdsp_meshfile)
	# drwResourceMeta
	_drw_resource_meta: DrwResourceMeta = create_drw_resource_meta() # Dunno if needed or how to create it
	new_drs_file.PushNode("DrwResourceMeta", _drw_resource_meta)
	# CollisionShape
 	# TODO: check if it is exported correctly
	_collision_shape: CollisionShape = create_collision_shape(source_collection) # Works perfectly fine
	if _collision_shape is not None:
		new_drs_file.PushNode("collisionShape", _collision_shape)
	# CGeoPrimitiveContainer
	_cgeo_primitive_container: CGeoPrimitiveContainer = create_cgeo_primitive_container() # Always empty
	new_drs_file.PushNode("CGeoPrimitiveContainer", _cgeo_primitive_container)

	# Save the DRS File
	new_drs_file.Save(filepath)

def export_skinned_object(operator, context, filepath: str, source_collection: bpy.types.Collection, use_apply_transform: bool) -> None:
	# TODO: We need to set the world matrix correctly for Battleforge Game Engine -> Matrix.Identity(4)
 
	# Model Name COmes right after the DRSModel_ Prefix and before the _Static Suffix
	model_name = source_collection.name[source_collection.name.find("DRSModel_") + 9:source_collection.name.find("_Skinned")]
	# Create an empty DRS File
	new_drs_file: DRS = DRS()

	# First we need to set the origin of all meshes to the center of the scene
	set_origin_to_world_origin(source_collection)
 
	if use_apply_transform:
		# Get CDspMeshFile Object
		cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)
		# Apply the Transformation to the CDspMeshFile Object
		for child in cdspmeshfile_object.children:
			if child.type == "MESH":
				mirror_mesh_on_axis(child, axis='y')

		# Get the CollisionShape Object
		collision_shape_object = search_for_object("CollisionShape", source_collection)
		
		if collision_shape_object is not None:
			# Apply the Transformation to the CollisionShape Object
			for child in collision_shape_object.children:
				if child.type == "MESH":
					mirror_mesh_on_axis(child, axis='y')

	unique_mesh = create_unique_mesh(source_collection) # Works perfectly fine
	if unique_mesh is None:
		show_message_box("Could not create Unique Mesh from Collection, as no CDspMeshFile was found!", "Error", "ERROR")
		return {"CANCELLED"}

	# CGeoMesh
	_cgeo_mesh: CGeoMesh = create_cgeo_mesh(unique_mesh) # Works perfectly fine
	new_drs_file.PushNode("CGeoMesh", _cgeo_mesh)
	# CGeoOBBTree
	_cgeo_obb_tree: CGeoOBBTree = create_cgeo_obb_tree(unique_mesh) # Maybe not needed??? We use a simple apporach for now with just one OBBNode, which is the whole mesh
	new_drs_file.PushNode("CGeoOBBTree", _cgeo_obb_tree)
	# CDspJointMap
	_cdsp_jointmap, bone_map = create_cdsp_jointmap(source_collection)
	new_drs_file.PushNode("CDspJointMap", _cdsp_jointmap)
	# CSkSkinInfo
	_csk_skin_info: CSkSkinInfo = create_csk_skin_info(source_collection, unique_mesh)
	new_drs_file.PushNode("CSkSkinInfo", _csk_skin_info)
	# CSkSkeleton
	_csk_skeleton: CSkSkeleton = create_csk_skeleton(source_collection, bone_map)
	new_drs_file.PushNode("CSkSkeleton", _csk_skeleton)
	# CDspMeshFile
	_cdsp_meshfile: CDspMeshFile = create_cdsp_meshfile(source_collection, model_name, filepath) # Works perfectly fine
	new_drs_file.PushNode("CDspMeshFile", _cdsp_meshfile)
	# drwResourceMeta
	_drw_resource_meta: DrwResourceMeta = create_drw_resource_meta() # Dunno if needed or how to create it
	new_drs_file.PushNode("DrwResourceMeta", _drw_resource_meta)
	# CollisionShape
 	# TODO: check if it is exported correctly
	_collision_shape: CollisionShape = create_collision_shape(source_collection) # Works perfectly fine
	if _collision_shape is not None:
		new_drs_file.PushNode("collisionShape", _collision_shape)
	# CGeoPrimitiveContainer
	_cgeo_primitive_container: CGeoPrimitiveContainer = create_cgeo_primitive_container() # Always empty
	new_drs_file.PushNode("CGeoPrimitiveContainer", _cgeo_primitive_container)
	
	# Should work for single-animated objects/props
	_animation_timings: AnimationTimings = AnimationTimings()
	new_drs_file.PushNode("AnimationTimings", _animation_timings)

	# Get the Animation Data
	animations = []
	armature_object = search_for_object("CSkSkeleton", source_collection)
	if armature_object is not None:
		animations = armature_object.animation_data.nla_tracks

	# For now only one animation is supported
	if len(animations) > 1:
		show_message_box("Currently only one animation is supported!", "Error", "ERROR")
		return {"CANCELLED"}
	# Should work for animated objects
	_animation_set: AnimationSet = AnimationSet(animations[0].name)
	new_drs_file.PushNode("AnimationSet", _animation_set)
	
	# Save the animation as SKA File
	ska_animation: SKA = create_new_ska_animation(animations[0])
	ska_animation.Save(filepath)

	# Save the DRS File
	new_drs_file.Save(filepath)

def verify_models(source_collection: bpy.types.Collection):
	'''Check if the Models are valid for the game. This includes the following checks:
	- Check if the Meshes have more than 32767 Vertices'''
	unified_mesh: bmesh.types.BMesh = bmesh.new()

	for obj in source_collection.objects:
		if obj.type == "MESH":
			if len(obj.data.vertices) > 32767:
				show_message_box("Mesh {} has more than 32767 Vertices. This is not supported by the game.".format(obj.name), "Error", "ERROR")
				return False
			unified_mesh.from_mesh(obj.data)

	unified_mesh.verts.ensure_lookup_table()
	unified_mesh.verts.index_update()
	bmesh.ops.remove_doubles(unified_mesh, verts=unified_mesh.verts, dist=0.0001)

	if len(unified_mesh.verts) > 32767:
		show_message_box("The unified Mesh has more than 32767 Vertices. This is not supported by the game.", "Error", "ERROR")
		return False

	unified_mesh.free()

	return True

def triangulate(source_collection: bpy.types.Collection) -> None:
	# Get the CDspMeshFile Object
	cdspmeshfile_object = search_for_object("CDspMeshFile", source_collection)

	for child in cdspmeshfile_object.children:
		if child.type == "MESH":
			bpy.context.view_layer.objects.active = child
			bpy.ops.object.mode_set(mode='EDIT')
			bm = bmesh.from_edit_mesh(child.data)

			non_tri_faces = [f for f in bm.faces if len(f.verts) > 3]
			if non_tri_faces:
				bmesh.ops.triangulate(bm, faces=non_tri_faces)
				bmesh.update_edit_mesh(child.data)

			bpy.ops.object.mode_set(mode='OBJECT')

def duplicate_collection_hierarchy(source_collection, parent_collection=None, link_to_scene=True):
	# Create a new collection with a modified name
	new_collection = bpy.data.collections.new(name=source_collection.name + "_Copy")
	if link_to_scene:
		bpy.context.scene.collection.children.link(new_collection)
	if parent_collection:
		parent_collection.children.link(new_collection)

	# Dictionary to keep track of old to new object mappings
	old_to_new_objs = {}

	# Function to duplicate object with hierarchy
	def duplicate_obj(obj, parent_obj):
		# Duplicate the object and its data
		new_obj = obj.copy()
		if obj.data:
			new_obj.data = obj.data.copy()

		# Append '_copy' to the duplicated object's name
		new_obj.name += "_Copy"
		if new_obj.data and hasattr(new_obj.data, 'name'):
			new_obj.data.name += "_Copy"

		# Unlink the new object from all current collections it's linked to
		for col in new_obj.users_collection:
			col.objects.unlink(new_obj)
		
		# Link the new object only to the new collection
		new_collection.objects.link(new_obj)
		old_to_new_objs[obj] = new_obj

		# Set the parent if it's already duplicated
		if parent_obj is not None and parent_obj in old_to_new_objs:
			new_obj.parent = old_to_new_objs[parent_obj]

	# Sort objects by their depth in the hierarchy
	def sort_objects_by_hierarchy(objects):
		obj_depth = {}
		def assign_depth(obj, depth=0):
			if obj in obj_depth:
				return obj_depth[obj]
			if obj.parent is None or obj.parent not in objects:
				obj_depth[obj] = depth
				return depth
			obj_depth[obj] = assign_depth(obj.parent, depth + 1) + 1
			return obj_depth[obj]

		# Assign depth to all objects
		for obj in objects:
			if obj not in obj_depth:
				assign_depth(obj)

		# Return objects sorted by their depth
		return sorted(objects, key=lambda o: obj_depth[o])

	# Sort and then duplicate objects
	sorted_objects = sort_objects_by_hierarchy(list(source_collection.objects))
	for obj in sorted_objects:
		duplicate_obj(obj, obj.parent)

	# Set the new collection as active if linking to the scene
	if link_to_scene:
		bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[new_collection.name]

	# Recursively duplicate child collections and their objects
	for child_col in source_collection.children:
		duplicate_collection_hierarchy(child_col, parent_collection=new_collection, link_to_scene=False)

	return new_collection

def split_meshes_by_uv_islands(source_collection: bpy.types.Collection) -> None:
	'''Split the Meshes by UV Islands.'''
	for obj in source_collection.objects:
		if obj.type == "MESH":
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='EDIT')
			bm = bmesh.from_edit_mesh(obj.data)
			# old seams
			old_seams = [e for e in bm.edges if e.seam]
			# unmark
			for e in old_seams:
				e.seam = False
			# mark seams from uv islands
			bpy.ops.mesh.select_all(action='SELECT')
			bpy.ops.uv.select_all(action='SELECT')
			bpy.ops.uv.seams_from_islands()
			seams = [e for e in bm.edges if e.seam]
			# split on seams
			bmesh.ops.split_edges(bm, edges=seams)
			# re instate old seams.. could clear new seams.
			for e in old_seams:
				e.seam = True
			bmesh.update_edit_mesh(obj.data)
			bpy.ops.object.mode_set(mode='OBJECT')

def save_drs(operator, context, filepath="", use_apply_transform=True, split_mesh_by_uv_islands=False, keep_debug_collections=False):
	'''Save the DRS File.'''
	# Get the right Collection
	source_collection: bpy.types.Collection = None
	# The Collection has the Name: DRSModel_Name
	for coll in bpy.data.collections:
		if coll.name.find("DRSModel_") != -1:
			source_collection = coll
			break

	if source_collection is None:
		show_message_box("No DRSModel Collection found!", "Error", "ERROR")
		return {"CANCELLED"}
	
	# We dont want to modify the original Collection so we create a copy
	source_collection = duplicate_collection_hierarchy(source_collection)
	
	# Be sure that there are only triangles in the Meshes
	triangulate(source_collection)

	# Verify the Models
	if not verify_models(source_collection):
		return {"CANCELLED"}
	
	# Split the Meshes by UV Islands
	if split_mesh_by_uv_islands:
		split_meshes_by_uv_islands(source_collection)

	# What we need in every DRS File (*created by this sript): CGeoMesh*, CGeoOBBTree (empty)*, CDspJointMap*, CDspMeshFile, DrwResourceMeta*
	# What we need in skinned DRS Files: CSkSkinInfo, CSkSkeleton, AnimationSet, AnimationTimings
	# Models with Effects: EffectSet
	# Static Objects need: CGeoPrimitiveContainer (empty), CollisionShape
	# Destructable Objects need: StateBasedMeshSet, MeshSetGrid

	# Check the model's type, based on the Collection's name: DRSModel_Name_Type
	# Type can be: Static for now (later we can add Skinned, Destructable, Effect, etc.)
	if source_collection.name.find("Static") != -1:
		export_static_object(operator, context, filepath, source_collection, use_apply_transform)
	elif source_collection.name.find("Skinned") != -1:
		export_skinned_object(operator, context, filepath, source_collection, use_apply_transform)

	# Remove the copied Collection
	if not keep_debug_collections:
		bpy.data.collections.remove(source_collection)

	return {"FINISHED"}

	# 	# CollisionShape if static
	# elif LoadedDRSModels is not None:
	# 	# If we only Edit the Model(s) we keep the whole structures and only update the neccecary parts
	# 	for LoadedDRSModel in LoadedDRSModels:
	# 		LoadedDRSModel = LoadedDRSModel[0]
	# 		source_file: DRS = LoadedDRSModel[1]
	# 		source_collection: bpy.types.Collection = LoadedDRSModel[2]
	# 		SourceUsedTransform: bool = LoadedDRSModel[3]

	# 		# Set the current Collection as Active
	# 		bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[source_collection.name]

	# 		# Set the Active object to the first object in the Collection
	# 		bpy.context.view_layer.objects.active = source_collection.objects[0]

	# 		# Switch to Edit Mode
	# 		bpy.ops.object.mode_set(mode='EDIT')

	# 		# If the Source Mesh has been transformed, we need to revert the transformation before we can export it
	# 		# Set the Global Matrix
	# 		if SourceUsedTransform:
	# 			# Get the Armature object if it exists
	# 			ArmatureObject = None

	# 			for object in source_collection.objects:
	# 				if object.type == "ARMATURE":
	# 					ArmatureObject = object
	# 					break
	# 			if ArmatureObject is not None:
	# 				ArmatureObject.matrix_world = Matrix.Identity(4)
	# 			else:
	# 				for object in source_collection.objects:
	# 					object.matrix_world = Matrix.Identity(4)

	# 		# Update the Meshes
	# 		update_cdspmeshfile(source_file, source_collection)
