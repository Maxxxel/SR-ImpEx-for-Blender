import os
from math import radians
import mathutils
import bmesh
import bpy
# from bpy_extras.image_utils import load_image
from mathutils import Matrix, Vector
from .drs_definitions import DRS, CDspMeshFile, CylinderShape, Face, BattleforgeMesh, DRSBone, CSkSkeleton, Bone, BoneVertex, BoxShape, SphereShape
from .drs_material import DRSMaterial

def debug_drs_file(filepath: str) -> 'DRS':
	# base_name = os.path.basename(filepath).split(".")[0]
	# dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)
	return drs_file

def load_drs(context: bpy.types.Context, filepath="", apply_transform=True, global_matrix=Matrix.Identity(4), import_collision_shape=False) -> None:
	base_name = os.path.basename(filepath).split(".")[0]
	dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)

	source_collection: bpy.types.Collection = bpy.data.collections.new("DRSModel_" + base_name + "_Type")
	context.collection.children.link(source_collection)

		# if drs_file.AnimationSet is not None:
		# 	for AnimationKey in drs_file.AnimationSet.ModeAnimationKeys:
		# 		for Variant in AnimationKey.AnimationSetVariants:
		# 			SKAFile: SKA = SKA().Read(os.path.join(dir_name, Variant.File))
		# 			create_animation(SKAFile, armature_object, bone_list, Variant.File)
	# else:

	# Layout
	# Static:
	# - Meshes
	# -- Materials
	# --- Textures

	# Skinned:
	# Armature
	# - Bones (CSkSkeleton) only one CSkSkeleton per DRS
	# - Meshes
	# -- Materials
	# --- Textures

	if drs_file.csk_skeleton is not None:
		# Create the Armature Data
		armature_data = bpy.data.armatures.new("CSkSkeleton")
		# Create the Armature Object and add the Armature Data to it
		armature_object: bpy.types.Object = bpy.data.objects.new("Armature", armature_data)
		# Link the Armature Object to the Source Collection
		source_collection.objects.link(armature_object)
		# Create the Skeleton
		bone_list = init_bones(drs_file.csk_skeleton)
		# Switch to Edit Mode and build the Skeleton
		context.view_layer.objects.active = armature_object
		bpy.ops.object.mode_set(mode='EDIT')
		# Create the Bone Tree
		create_bone_tree(armature_data, bone_list, bone_list[0])
		# Switch back to Object Mode
		bpy.ops.object.mode_set(mode='OBJECT')
		# Build the Skeleton
		build_skeleton(bone_list, armature_data)
		# Add the Animations to the Armature Object
		if drs_file.animation_set is not None:
			# Apply the Transformations to the Armature Object
			apply_transformations(armature_object, global_matrix, apply_transform)

	for i in range(drs_file.cdsp_mesh_file.mesh_count):
		# Create the Mesh Data
		mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, i, dir_name)
		# Create the Mesh Object and add the Mesh Data to it
		mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{i}", mesh_data)
		# Link the Mesh Object to the Source Collection
		source_collection.objects.link(mesh_object)
		# Check if the Mesh has a Skeleton and modify the Mesh Object accordingly
		if drs_file.csk_skeleton is not None:
			# Set the Armature Object as the Parent of the Mesh Object
			mesh_object.parent = armature_object
			# Add the Armature Modifier to the Mesh Object
			modifier = mesh_object.modifiers.new(type="ARMATURE", name='Armature')
			modifier.object = armature_object
		else:
			# Apply the Transformations to the Mesh Object when no Skeleton is present else we transform the armature
			apply_transformations(mesh_object, global_matrix, apply_transform)

	if drs_file.collision_shape is not None and import_collision_shape:
		for _ in range(drs_file.collision_shape.box_count):
			box_object = create_collision_shape_box_object(drs_file.collision_shape.boxes[_], _)
			source_collection.objects.link(box_object)
			apply_transformations(box_object, global_matrix, apply_transform)
			# TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
			box_object.location = (box_object.location.x, box_object.location.y, -box_object.location.z)

		for _ in range(drs_file.collision_shape.sphere_count):
			sphere_object = create_collision_shape_sphere_object(drs_file.collision_shape.spheres[_], _)
			source_collection.objects.link(sphere_object)
			apply_transformations(sphere_object, global_matrix, apply_transform)

		for _ in range(drs_file.collision_shape.cylinder_count):
			cylinder_object = create_collision_shape_cylinder_object(drs_file.collision_shape.cylinders[_], _)
			source_collection.objects.link(cylinder_object)
			apply_transformations(cylinder_object, global_matrix, apply_transform)

def apply_transformations(obj: bpy.types.Object, global_matrix: Matrix, apply_transform: bool) -> None:
	if apply_transform:
		obj.matrix_world = global_matrix @ obj.matrix_world
		obj.scale = (1, -1, 1)

def create_static_mesh(mesh_file: CDspMeshFile, mesh_index: int, dir_name:str) -> bpy.types.Mesh:
	battleforge_mesh_data: BattleforgeMesh = mesh_file.meshes[mesh_index]
	# _name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
	mesh_data = bpy.data.meshes.new(f"MeshData_{mesh_index}")

	vertices = list()
	faces = list()
	normals = list()
	uv_list = list()

	for _ in range(battleforge_mesh_data.face_count):
		face: Face = battleforge_mesh_data.faces[_].indices
		faces.append([face[0], face[1], face[2]])

	for _ in range(battleforge_mesh_data.vertex_count):
		vertex = battleforge_mesh_data.mesh_data[0].vertices[_]
		vertices.append(vertex.position)
		normals.append(vertex.normal)
		# Negate the UVs Y Axis before adding them
		uv_list.append((vertex.texture[0], -vertex.texture[1]))

	mesh_data.from_pydata(vertices, [], faces)
	mesh_data.polygons.foreach_set('use_smooth', [True] * len(mesh_data.polygons))
	mesh_data.normals_split_custom_set_from_vertices(normals)
	if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]): # pylint: disable=unsubscriptable-object
		mesh_data.use_auto_smooth = True

	uv_list = [i for poly in mesh_data.polygons for vidx in poly.vertices for i in uv_list[vidx]]
	mesh_data.uv_layers.new().data.foreach_set('uv', uv_list)

	# Create the Material
	material_data = create_material(dir_name, mesh_index, battleforge_mesh_data)
	# Assign the Material to the Mesh
	mesh_data.materials.append(material_data)

	return mesh_data

def init_bones(skeleton_data: CSkSkeleton, suffix: str = None) -> list[DRSBone]:
	bone_list: list[DRSBone] = []

	# Init the Bone List with empty DRSBone Objects
	for i in range(skeleton_data.bone_count):
		bone_list.append(DRSBone())

	# Set the Bone Datapoints
	for i in range(skeleton_data.bone_count):
		bone_data: Bone = skeleton_data.bones[i]

		# Get the RootBone Vertices
		bone_vertices: list[BoneVertex] = skeleton_data.bone_matrices[bone_data.identifier].bone_vertices

		vec_0 = Vector((bone_vertices[0].position.x, bone_vertices[0].position.y, bone_vertices[0].position.z, bone_vertices[0].parent))
		vec_1 = Vector((bone_vertices[1].position.x, bone_vertices[1].position.y, bone_vertices[1].position.z, bone_vertices[1].parent))
		vec_2 = Vector((bone_vertices[2].position.x, bone_vertices[2].position.y, bone_vertices[2].position.z, bone_vertices[2].parent))
		vec_3 = Vector((bone_vertices[3].position.x, bone_vertices[3].position.y, bone_vertices[3].position.z, bone_vertices[3].parent))

		# Create the Bone Matrix
		# Make the 4th column negative to flip the Axis
		rotation = Matrix((vec_0.xyz, vec_1.xyz, vec_2.xyz))
		location = rotation @ (-1 * vec_3.xyz)
		bone_matrix = Matrix.LocRotScale(location, rotation, Vector((1, 1, 1)))

		# Set Data
		bone_list_item: DRSBone = bone_list[bone_data.identifier]
		bone_list_item.ska_identifier = bone_data.version
		bone_list_item.identifier = bone_data.identifier
		bone_list_item.name = bone_data.name + (f"_{suffix}" if suffix else "")
		bone_list_item.bone_matrix = bone_matrix

		# Set the Bone Children
		bone_list_item.children = bone_data.children

		# Set the Bones Children's Parent ID
		for j in range(bone_data.child_count):
			child_id = bone_data.children[j]
			bone_list[child_id].parent = bone_data.identifier

	# Order the Bones by Parent ID
	bone_list.sort(key=lambda x: x.identifier)

	# Return the BoneList
	return bone_list

def create_bone_tree(armature: bpy.types.Armature, bone_list: list[DRSBone], bone_data: DRSBone):
	edit_bone = armature.edit_bones.new(bone_data.name)
	edit_bone.head = bone_data.bone_matrix @ Vector((0, 0, 0))
	edit_bone.tail = bone_data.bone_matrix @ Vector((0, 1, 0))
	edit_bone.length = 0.1
	edit_bone.align_roll(bone_data.bone_matrix.to_3x3() @ Vector((0, 0, 1)))

	# Set the Parent
	if bone_data.parent != -1:
		parent_bone_data: DRSBone = bone_list[bone_data.parent]
		edit_bone.parent = armature.edit_bones[parent_bone_data.name]

	for child_bone in bone_list:
		if child_bone.parent == bone_data.identifier:
			create_bone_tree(armature, bone_list, child_bone)

def build_skeleton(bone_list: list[DRSBone], armature: bpy.types.Armature) -> None:
	# Record bind pose transform to parent space
	# Used to set pose bones for animation
	for bone_data in bone_list:
		armature_bone = armature.bones[bone_data.name]
		matrix_local = armature_bone.matrix_local

		if armature_bone.parent:
			matrix_local = armature_bone.parent.matrix_local.inverted_safe() @ matrix_local

		bone_data.bind_loc = matrix_local.to_translation()
		bone_data.bind_rot = matrix_local.to_quaternion()

def create_material(dir_name: str, mesh_index: int, mesh_data: BattleforgeMesh) -> bpy.types.Material:
	drs_material: 'DRSMaterial' = DRSMaterial(f"MaterialData_{mesh_index}")

	for texture in mesh_data.textures.textures:
		if texture.length > 0:
			match texture.identifier:
				case 1684432499:
					drs_material.set_color_map(texture.name, dir_name)
				case 1936745324:
					drs_material.set_parameter_map(texture.name, dir_name)
				case 1852992883:
					drs_material.set_normal_map(texture.name, dir_name)

	# Fluid is hard to add, prolly only as an hardcoded animation, there is no GIF support

	# Scratch

	# Environment can be ignored, its only used for Rendering

	# Refraction
	# for Tex in mesh_data.Textures.Textures:
	# 	if Tex.Identifier == 1919116143 and Tex.Length > 0:
	# 		RefractionMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
	# 		RefractionMapNode.location = Vector((-700.0, -900.0))
	# 		RefractionMapNode.image = load_image(os.path.basename(Tex.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
	# 		RefBSDF = NewMaterial.node_tree.nodes.new('ShaderNodeBsdfRefraction')
	# 		RefBSDF.location = Vector((-250.0, -770.0))
	# 		NewMaterial.node_tree.links.new(RefBSDF.inputs['Color'], RefractionMapNode.outputs['Color'])
	# 		MixNode = NewMaterial.node_tree.nodes.new('ShaderNodeMixShader')
	# 		MixNode.location = Vector((0.0, 200.0))
	# 		NewMaterial.node_tree.links.new(MixNode.inputs[1], RefBSDF.outputs[0])
	# 		NewMaterial.node_tree.links.new(MixNode.inputs[2], BSDF.outputs[0])
	# 		NewMaterial.node_tree.links.new(MixNode.outputs[0], NewMaterial.node_tree.nodes['Material Output'].inputs[0])
	# 		MixNodeAlpha = NewMaterial.node_tree.nodes.new('ShaderNodeMixRGB')
	# 		MixNodeAlpha.location = Vector((-250.0, -1120.0))
	# 		MixNodeAlpha.use_alpha = True
	# 		MixNodeAlpha.blend_type = 'SUBTRACT'
	# 		# Set the Factor to 0.2, so the Refraction is not too strong
	# 		MixNodeAlpha.inputs[0].default_value = 0.2
	# 		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[1], ColorMapNode.outputs['Alpha'])
	# 		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[2], RefractionMapNode.outputs['Alpha'])
	# 		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], MixNodeAlpha.outputs[0])
	# 	else:
	# 		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], ColorMapNode.outputs['Alpha'])

	# if mesh_data.Refraction.Length == 1:
	# 	_RGB = mesh_data.Refraction.RGB
		# What to do here?

	return drs_material.material

def create_collision_shape_box_object(box_shape: BoxShape, index: int) -> bpy.types.Object:
	# Extract the lower-left and upper-right corner coordinates
	llc = box_shape.geo_aabox.lower_left_corner  # Vector3
	urc = box_shape.geo_aabox.upper_right_corner  # Vector3

	# Ensure the coordinates are in the correct order
	x0, x1 = sorted((llc.x, urc.x))
	y0, y1 = sorted((llc.y, urc.y))
	z0, z1 = sorted((llc.z, urc.z))

	# Define the vertices of the box in local space
	vertices = [
		(x0, y0, z0),
		(x1, y0, z0),
		(x1, y1, z0),
		(x0, y1, z0),
		(x0, y0, z1),
		(x1, y0, z1),
		(x1, y1, z1),
		(x0, y1, z1)
	]

	# Define the faces of the box (each face is a list of four vertex indices)
	faces = [
		(0, 1, 2, 3),  # Bottom face
		(4, 5, 6, 7),  # Top face
		(0, 1, 5, 4),  # Front face
		(1, 2, 6, 5),  # Right face
		(2, 3, 7, 6),  # Back face
		(3, 0, 4, 7)   # Left face
	]

	# Create a new mesh and object for the box
	box_shape_mesh_data = bpy.data.meshes.new('CollisionBoxMesh')
	box_object = bpy.data.objects.new(f"CollisionBox_{index}", box_shape_mesh_data)

	# Create the mesh from the vertices and faces
	box_shape_mesh_data.from_pydata(vertices, [], faces)
	box_shape_mesh_data.update()

	rotation_matrix = box_shape.coord_system.matrix.matrix  # Matrix3x3
	position = box_shape.coord_system.position       # Vector3

	# Convert the rotation matrix to a Blender-compatible format
	rot_mat = mathutils.Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = mathutils.Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
	# Combine rotation and translation into a transformation matrix
	transform_matrix = rot_mat
	transform_matrix.translation = translation_vec

	# Assign the transformation matrix to the object's world matrix
	box_object.matrix_world = transform_matrix

	# Display the object as wired
	box_object.display_type = 'WIRE'

	return box_object

def create_collision_shape_cylinder_object(cylinder_shape: CylinderShape, index: int) -> bpy.types.Object:
	cylinder_shape_mesh_data = bpy.data.meshes.new('CollisionCylinderMesh')
	cylinder_object = bpy.data.objects.new(f"CollisionCylinder_{index}", cylinder_shape_mesh_data)

	bm = bmesh.new() # pylint: disable=E1111
	segments = 32
	radius = cylinder_shape.geo_cylinder.radius
	depth = cylinder_shape.geo_cylinder.height

	rotation_matrix = cylinder_shape.coord_system.matrix.matrix  # Matrix3x3
	position = cylinder_shape.coord_system.position # Vector3

	# Convert the rotation matrix to a Blender-compatible format
	rot_mat = mathutils.Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = mathutils.Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
	transform_matrix = rot_mat
	# We need to rotate the cylinder by 90 degrees cause the cylinder is always created along the z axis, but we need it along the y axis for imported models
	rot_mat = mathutils.Matrix.Rotation(radians(90), 4, 'X')
	transform_matrix = rot_mat @ transform_matrix
	# Combine rotation and translation into a transformation matrix
	transform_matrix.translation = translation_vec
	# Add half the height to the translation to center the cylinder
	transform_matrix.translation.y += depth / 2

	# Create the cylinder using bmesh
	bmesh.ops.create_cone(
		bm,
		cap_ends=True,
		cap_tris=False,
		segments=segments,
		radius1=radius,  # Diameter at the bottom
		radius2=radius,  # Diameter at the top (same for cylinder)
		depth=depth,
		matrix=transform_matrix,
		calc_uvs=False
	)

	# Finish up, write the bmesh into the mesh
	bm.to_mesh(cylinder_shape_mesh_data)
	bm.free()

	# Display the object as wired
	cylinder_object.display_type = 'WIRE'

	return cylinder_object

def create_collision_shape_sphere_object(sphere_shape: SphereShape, index: int) -> bpy.types.Object:
	sphere_shape_mesh_data = bpy.data.meshes.new('CollisionSphereMesh')
	sphere_object = bpy.data.objects.new(f"CollisionSphere_{index}", sphere_shape_mesh_data)

	bm = bmesh.new() # pylint: disable=E1111
	segments = 32
	radius = sphere_shape.geo_sphere.radius
	# center = sphere_shape.geo_sphere.center # should always be (0, 0, 0) so we ignore it

	rotation_matrix = sphere_shape.coord_system.matrix.matrix  # Matrix3x3
	position = sphere_shape.coord_system.position # Vector3

	# Convert the rotation matrix to a Blender-compatible format
	rot_mat = mathutils.Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = mathutils.Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
	# Combine rotation and translation into a transformation matrix
	transform_matrix = rot_mat
	transform_matrix.translation = translation_vec

	# Create the sphere using bmesh
	bmesh.ops.create_uvsphere(
		bm,
		u_segments=segments,
		v_segments=segments,
		radius=radius,
		matrix=transform_matrix,
		calc_uvs=False
	)

	# Finish up, write the bmesh into the mesh
	bm.to_mesh(sphere_shape_mesh_data)
	bm.free()

	# Display the object as wired
	sphere_object.display_type = 'WIRE'

	return sphere_object

# def create_action(armature_object: bpy.types.Object, animation_name: str, animation_time_in_frames: int, force_new: bool = True, repeat: bool = False):
# 	armature_action = None
# 	if (force_new == False):
# 		armature_action = bpy.data.actions.new(name=animation_name)
# 	else:
# 		action = bpy.data.actions.get(animation_name)
# 		if (action is not None):
# 			armature_action = (bpy.data.get(animation_name) is None)

# 	armature_action.use_frame_range = True
# 	armature_action.frame_range = (0, animation_time_in_frames)
# 	armature_action.frame_start = 0
# 	armature_action.frame_end = animation_time_in_frames
# 	armature_action.use_cyclic = repeat

# 	bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, animation_time_in_frames)
# 	armature_object.animation_data.action = armature_action
# 	return armature_action
