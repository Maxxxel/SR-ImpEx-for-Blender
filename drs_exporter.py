import math
import os
import subprocess
from os.path import dirname, realpath
from typing import List, Tuple
import bpy
import bmesh
from mathutils import Vector, Matrix
from numpy import mat, rot90
from .drs_file import DRS, CDspMeshFile, BattleforgeMesh, Face, EmptyString, LevelOfDetail, MeshData, Refraction, Textures, Texture, Vertex, Materials, Flow, CGeoMesh, CGeoOBBTree, DrwResourceMeta, CGeoPrimitiveContainer, CDspJointMap, CollisionShape, CylinderShape, CGeoCylinder, BoxShape, CGeoAABox, SphereShape, CGeoSphere, CMatCoordinateSystem, OBBNode

resource_dir = dirname(realpath(__file__)) + "/resources"

def show_message_box(msg: str, Title: str = "Message Box", Icon: str = "INFO") -> None:
	def DrawMessageBox(self, context):
		self.layout.label(text=msg)

	bpy.context.window_manager.popup_menu(DrawMessageBox, title=Title, icon=Icon)

def ResetViewport() -> None:
	for Area in bpy.context.screen.areas:
		if Area.type in ['IMAGE_EDITOR', 'VIEW_3D']:
			Area.tag_redraw()

	bpy.context.view_layer.update()

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
	Mirror a mesh along a specified axis and correctly handle normals.
	
	Parameters:
	obj (bpy.types.Object): The object to mirror.
	axis (str): Axis to mirror along, should be 'x', 'y', or 'z'.
	"""
	# Validate axis
	axis = axis.lower()
	if axis not in ['x', 'y', 'z']:
		raise ValueError("Invalid axis. Use 'x', 'y', or 'z'.")
	
	# Get the mesh from the object
	me = obj.data
	# Calculate split normals
	me.calc_normals_split()
	me.use_auto_smooth = True
	
	# Axis indices map to coordinates (x, y, z) -> (0, 1, 2)
	axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
	
	# Prepare to store mirrored split normals
	mirror_split_normals = []
	
	# Iterate over polygons to modify normals
	for poly in me.polygons:
		reverse_normals_indices = [poly.loop_indices[0]] + [i for i in reversed(poly.loop_indices[1:])]
		for i in reverse_normals_indices:
			loop = me.loops[i]
			normal = list(loop.normal)
			normal[axis_idx] *= -1  # Mirror normal on the specified axis
			mirror_split_normals.append(tuple(normal))
	
	# Mirror vertices along the specified axis
	for v in me.vertices:
		co = list(v.co)
		co[axis_idx] *= -1  # Multiply coordinate on axis by -1
		v.co = tuple(co)
	
	# Apply the mirrored normals
	me.flip_normals()
	me.normals_split_custom_set(mirror_split_normals)
	me.update()

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
	new_mesh.MaterialParameters = -86061050
	new_mesh.MaterialStuff = 0
	new_mesh.BoolParameter = 0
	BoolParamBitFlag = 0
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
	# Textures
	new_mesh.Textures = Textures()
	# Check if the ColorMap exists
	if ColorMap is None:
		ValueError("The ColorMap Node is unset!")

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
			created = False
			
			if _Img is not None:
				_TempPath = bpy.path.abspath("//") + ColMapTexture.Name + ".png"
				_Img.file_format = "PNG"
				_Img.save(filepath=_TempPath)

				# convert the image to dds dxt3 by using texconv.exe in the resources folder
				output_folder = os.path.dirname(filepath)
				# TODO: If Alpha is connected, we need to use DXT5 instead of DXT1
				args = ["-ft", "dds", "-f", "DXT5", "-dx9", "-pow2", "-srgb", "-y", ColMapTexture.Name + ".dds", "-o", output_folder]
				subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)
				# Remove the Temp File
				os.remove(_TempPath)

				# Remove the Image
				if created:
					bpy.data.images.remove(_Img)
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

				# convert the image to dds dxt1 by using texconv.exe in the resources folder
				output_folder = os.path.dirname(filepath)
				args = ["-ft", "dds", "-f", "DXT1", "-dx9", "-pow2", "-srgb", "-at", "0.0", "-y", NorMapTexture.Name + ".dds", "-o", output_folder]
				subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)

				# Remove the Temp File
				os.remove(_TempPath)

				# Remove the Image
				bpy.data.images.remove(_Img)
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
		output_folder = os.path.dirname(filepath)
		args = ["-ft", "dds", "-f", "BC3_UNORM_SRGB", "-dx9", "-bc", "d", "-pow2", "-y", MetMapTexture.Name + ".dds", "-o", output_folder]
		subprocess.run([resource_dir + "/texconv.exe", _TempPath] + args, check=False)

		# Remove the Temp File
		os.remove(_TempPath)

		# Remove the Image
		bpy.data.images.remove(new_img)

	# Set the Bool Parameter by a bin -> dec conversion
	new_mesh.BoolParameter = int(str(BoolParamBitFlag), 2)
	# Refraction
	Ref = Refraction()
	Ref.Length = 1
	Ref.RGB = list(RefractionColor.default_value)[:3]
	new_mesh.Refraction = Ref
	# Materials
	new_mesh.Materials = Materials() # Almost no material data is used in the game, so we set it to defaults
	# Level of Detail
	new_mesh.LevelOfDetail = LevelOfDetail() # We don't need to update the LOD
	# Empty String
	new_mesh.EmptyString = EmptyString() # We don't need to update the Empty String
	# Flow
	new_mesh.Flow = Flow() # Maybe later we can add some flow data in blender

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

def create_cdsp_jointmap(empty = True) -> CDspJointMap:
	'''Create a CDspJointMap. If empty is True, the CDspJointMap will be empty.'''
	if empty:
		return CDspJointMap()
	else:
		pass

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

def export_static_object(operator, context, filepath: str, source_collection: bpy.types.Collection, use_apply_transform: bool, global_matrix: Matrix) -> None:
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
	_cdsp_jointmap: CDspJointMap = create_cdsp_jointmap() # Not needed for static objects, means we can leave it empty
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
		
		# Keep track of the object's parent (if it has one)
		if parent_obj is not None and parent_obj in old_to_new_objs:
			new_obj.parent = old_to_new_objs[parent_obj]

		# Link the new object only to the new collection
		new_collection.objects.link(new_obj)
		old_to_new_objs[obj] = new_obj

	# Check if the parent is in the same source collection
	def is_parent_in_source_collection(obj):
		return obj.parent.name in [o.name for o in source_collection.objects] if obj.parent else False

	# Iterate through all objects in the collection and duplicate them
	for obj in source_collection.objects:
		duplicate_obj(obj, obj.parent if is_parent_in_source_collection(obj) else None)

	# Set the new collection as active if linking to the scene
	if link_to_scene:
		bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[new_collection.name]

	# Recursively duplicate child collections and their objects
	for child_col in source_collection.children:
		duplicate_collection_hierarchy(child_col, parent_collection=new_collection, link_to_scene=False)

	return new_collection

def save_drs(operator, context, filepath="", use_apply_transform=True, keep_debug_collections=False, global_matrix=None):
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

	# What we need in every DRS File (*created by this sript): CGeoMesh*, CGeoOBBTree (empty)*, CDspJointMap*, CDspMeshFile, DrwResourceMeta*
	# What we need in skinned DRS Files: CSkSkinInfo, CSkSkeleton, AnimationSet, AnimationTimings
	# Models with Effects: EffectSet
	# Static Objects need: CGeoPrimitiveContainer (empty), CollisionShape
	# Destructable Objects need: StateBasedMeshSet, MeshSetGrid

	# Check the model's type, based on the Collection's name: DRSModel_Name_Type
	# Type can be: Static for now (later we can add Skinned, Destructable, Effect, etc.)
	if source_collection.name.find("Static") != -1:
		export_static_object(operator, context, filepath, source_collection, use_apply_transform, global_matrix)

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
