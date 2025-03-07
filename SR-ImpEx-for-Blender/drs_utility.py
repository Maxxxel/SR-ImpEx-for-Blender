import os
from os.path import dirname, realpath
from math import radians
import time
import subprocess
from collections import  defaultdict
from typing import Tuple, List
from mathutils import Matrix, Vector, Quaternion
# pylint: disable=fixme, import-error
import bpy
from bpy_extras.io_utils import axis_conversion
import bmesh
import xml.etree.ElementTree as ET

from .drs_definitions import DRS, BMS, CDspMeshFile, CylinderShape, Face, BattleforgeMesh, DRSBone, CSkSkeleton, Bone, BoneVertex, BoxShape, MeshGridModule, SLocator, SphereShape, CSkSkinInfo, CGeoAABox, CGeoMesh, BoneWeight, CGeoOBBTree, OBBNode, CMatCoordinateSystem, CDspJointMap, MeshData, StateBasedMeshSet, Vertex, LevelOfDetail, EmptyString, Flow, Textures, Texture, Refraction, Materials, DrwResourceMeta, JointGroup, Vector3, Vector4, InformationIndices, WriteOrder, CollisionShape
from .drs_material import DRSMaterial
from .ska_definitions import SKA, SKAKeyframe

resource_dir = dirname(realpath(__file__)) + "/resources"
messages = []

def show_message_box(message = "", title = "Message Box", icon = 'INFO', final = False):
	global messages
	# We store the messages in a list to display them all at once
	if message != "":
		messages.append((message, title, icon))

	if final:
		# Display messages using the operator defined in __init__.py
		final_message: str = ""
		for message in messages:
			final_message += f"{message[1]}: {message[0]}\n"
		bpy.ops.my_category.show_messages('INVOKE_DEFAULT', messages=final_message)

def find_or_create_collection(source_collection: bpy.types.Collection, collection_name: str) -> bpy.types.Collection:
	collection = source_collection.children.get(collection_name)
	if collection is None:
		collection = bpy.data.collections.new(collection_name)
		source_collection.children.link(collection)

	return collection

def apply_transformations(obj: bpy.types.Object, global_matrix: Matrix, apply_transform: bool, edit_scale=True) -> None:
	if apply_transform:
		obj.matrix_world = global_matrix @ obj.matrix_world
		if edit_scale:
			obj.scale = (1, -1, 1)

def mirror_object_by_vector(obj, vector):
	"""
	Mirrors an object across a vector.

	:param obj: The object to mirror.
	:param vector: The vector to mirror across (mathutils.Vector).
	"""
	# Normalize the vector to create a plane of reflection
	vector = vector.normalized()

	# Create the reflection matrix
	reflection_matrix = Matrix((
		(1 - 2 * vector.x ** 2, -2 * vector.x * vector.y, -2 * vector.x * vector.z, 0),
		(-2 * vector.x * vector.y, 1 - 2 * vector.y ** 2, -2 * vector.y * vector.z, 0),
		(-2 * vector.x * vector.z, -2 * vector.y * vector.z, 1 - 2 * vector.z ** 2, 0),
		(0, 0, 0, 1)
	))

	# Apply the reflection matrix to the object's transformation
	obj.matrix_world = reflection_matrix @ obj.matrix_world

def create_static_mesh(mesh_file: CDspMeshFile, mesh_index: int) -> bpy.types.Mesh:
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

		vec_0 = Vector((bone_vertices[0].position.x, bone_vertices[0].position.y, bone_vertices[0].position.z))
		vec_1 = Vector((bone_vertices[1].position.x, bone_vertices[1].position.y, bone_vertices[1].position.z))
		vec_2 = Vector((bone_vertices[2].position.x, bone_vertices[2].position.y, bone_vertices[2].position.z))
		vec_3 = Vector((bone_vertices[3].position.x, bone_vertices[3].position.y, bone_vertices[3].position.z))

		# Get the Location of the Bone and flip the Z-Axis
		location = -vec_3
		# # Get the Rotation of the Bone
		rotation = Matrix((vec_0, vec_1, vec_2))
		# # Get the Scale of the Bone
		scale = Vector((1, 1, 1))
		# # Set the Bone Matrix
		location = rotation @ location
		bone_matrix = Matrix.LocRotScale(location, rotation, scale)

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

	# Go through the Bone List find the bones without a parent
	for bone in bone_list:
		if bone.parent == -1 and bone.identifier != 0:
			bone.parent = 0
			print(f"Bone {bone.name} has no parent, setting it to the root bone.")

	# Return the BoneList
	return bone_list

def record_bind_pose(bone_list: list[DRSBone], armature: bpy.types.Armature) -> None:
	# Record bind pose transform to parent space
	# Used to set pose bones for animation
	for bone_data in bone_list:
		armature_bone: bpy.types.Bone = armature.bones[bone_data.name]
		matrix_local = armature_bone.matrix_local

		if armature_bone.parent:
			matrix_local = armature_bone.parent.matrix_local.inverted_safe() @ matrix_local

		bone_data.bind_loc = matrix_local.to_translation()
		bone_data.bind_rot = matrix_local.to_quaternion()

def create_bone_tree(armature_data: bpy.types.Armature, bone_list: list[DRSBone], bone_data: DRSBone):
	edit_bones = armature_data.edit_bones
	edit_bone = edit_bones.new(bone_data.name)
	armature_data.display_type = 'STICK'
	edit_bone.head = bone_data.bone_matrix @ Vector((0, 0, 0))
	edit_bone.tail = bone_data.bone_matrix @ Vector((0, 1, 0))
	edit_bone.length = 0.1
	edit_bone.align_roll(bone_data.bone_matrix.to_3x3() @ Vector((0, 0, 1)))

	# Set the parent bone
	if bone_data.parent != -1:
		parent_bone_name = bone_list[bone_data.parent].name
		edit_bone.parent = armature_data.edit_bones.get(parent_bone_name)

	# Recursively create child bones
	for child_bone in [b for b in bone_list if b.parent == bone_data.identifier]:
		create_bone_tree(armature_data, bone_list, child_bone)

def create_material(dir_name: str, mesh_index: int, mesh_data: BattleforgeMesh, base_name: str) -> bpy.types.Material:
	drs_material: 'DRSMaterial' = DRSMaterial(f"MaterialData_{base_name}_{mesh_index}")

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
	# 		refraction_mapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
	# 		refraction_mapNode.location = Vector((-700.0, -900.0))
	# 		refraction_mapNode.image = load_image(os.path.basename(Tex.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
	# 		RefBSDF = NewMaterial.node_tree.nodes.new('ShaderNodeBsdfRefraction')
	# 		RefBSDF.location = Vector((-250.0, -770.0))
	# 		NewMaterial.node_tree.links.new(RefBSDF.inputs['Color'], refraction_mapNode.outputs['Color'])
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
	# 		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[1], color_mapNode.outputs['Alpha'])
	# 		NewMaterial.node_tree.links.new(MixNodeAlpha.inputs[2], refraction_mapNode.outputs['Alpha'])
	# 		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], MixNodeAlpha.outputs[0])
	# 	else:
	# 		NewMaterial.node_tree.links.new(BSDF.inputs['Alpha'], color_mapNode.outputs['Alpha'])

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
	rot_mat = Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
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
	rot_mat = Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
	transform_matrix = rot_mat
	# We need to rotate the cylinder by 90 degrees cause the cylinder is always created along the z axis, but we need it along the y axis for imported models
	rot_mat = Matrix.Rotation(radians(90), 4, 'X')
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
	rot_mat = Matrix((
		(rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], 0.0),
		(rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], 0.0),
		(rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], 0.0),
		(				0.0,                0.0,                0.0, 1.0)
	))

	# Create a translation vector
	translation_vec = Vector((position.x, position.y, position.z)) # in Battleforge the Y-Axis is Up, but we do that later when we apply the global matrix
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

def get_bone_fcurves(action: bpy.types.Action, pose_bone: bpy.types.PoseBone) -> dict[str, bpy.types.FCurve]:
	fcurves = {}
	data_path_prefix = f'pose.bones["{pose_bone.name}"].'

	# Location F-Curves (x, y, z)
	for i, axis in enumerate('xyz'):
		fcurve = action.fcurves.new(data_path=data_path_prefix + 'location', index=i)
		fcurves[f'location_{axis}'] = fcurve

	# Rotation F-Curves (quaternion w, x, y, z)
	for i, axis in enumerate('wxyz'):
		fcurve = action.fcurves.new(data_path=data_path_prefix + 'rotation_quaternion', index=i)
		fcurves[f'rotation_{axis}'] = fcurve

	return fcurves

def insert_keyframes(fcurves: dict[str, bpy.types.FCurve], frame_data: SKAKeyframe, frame: int, animation_type: int, bind_rot: Quaternion, bind_loc: Vector) -> None:
	if animation_type == 0:
		# Location
		translation_vector = bind_rot.conjugated() @ (Vector((frame_data.x, frame_data.y, frame_data.z)) - bind_loc)
		for axis, value in zip('xyz', translation_vector):
			fcurve = fcurves[f'location_{axis}']
			kp = fcurve.keyframe_points.insert(frame, value)
			kp.interpolation = 'BEZIER'
			# Set tangent handles using tan_data
			# if tan_data is not None:
			# 	set_keyframe_tangent(kp, tan_data.get(axis))
	elif animation_type == 1:
		# Rotation
		rotation_quaternion = bind_rot.conjugated() @ Quaternion((-frame_data.w, frame_data.x, frame_data.y, frame_data.z))
		for axis, value in zip('wxyz', rotation_quaternion):
			fcurve = fcurves[f'rotation_{axis}']
			kp = fcurve.keyframe_points.insert(frame, value)
			kp.interpolation = 'BEZIER'
			# Set tangent handles using tan_data
			# if tan_data is not None:
			# 	set_keyframe_tangent(kp, tan_data.get(axis))

def add_animation_to_nla_track(armature_object: bpy.types.Object, action: bpy.types.Action) -> None:
	new_track = armature_object.animation_data.nla_tracks.new()
	new_track.name = action.name
	new_strip = new_track.strips.new(action.name, 0, action)
	new_strip.name = action.name
	new_strip.repeat = True
	new_track.lock, new_track.mute = False, False

def create_action(armature_object: bpy.types.Object, animation_name: str, repeat: bool = False) -> bpy.types.Action:
	armature_action = bpy.data.actions.new(name=animation_name)
	armature_action.use_cyclic = repeat
	armature_object.animation_data.action = armature_action
	return armature_action

def create_animation(ska_file: SKA, armature_object: bpy.types.Object, bone_list: list[DRSBone], animation_name: str):
	fps = bpy.context.scene.render.fps

	armature_object.animation_data_create()
	new_action = create_action(armature_object, animation_name, repeat=ska_file.repeat)

	# Prepare F-Curves for all bones
	bone_fcurves_map: dict[str, bpy.types.FCurve] = {}

	for bone in bone_list:
		pose_bone = armature_object.pose.bones.get(bone.name)
		if pose_bone:
			bone_fcurves_map[bone.ska_identifier] = get_bone_fcurves(new_action, pose_bone)
		else:
			show_message_box(f"Bone {bone.name} not found in armature.", "Warning", 'WARNING')

	for header_data in ska_file.headers:
		fcurves = bone_fcurves_map.get(header_data.bone_id)
		bone = next((b for b in bone_list if b.ska_identifier == header_data.bone_id), None)
		if not fcurves or not bone:
			continue

		bind_rot = bone.bind_rot
		bind_loc = bone.bind_loc
		header_type = header_data.type

		for idx in range(header_data.tick, header_data.tick + header_data.interval):
			frame_data = ska_file.keyframes[idx]
			frame = ska_file.times[idx] * ska_file.duration * fps

			# Extract tan data for the current keyframe
			# tan_data = None

			# if use_animation_smoothing:
			# 	tan_data = {
			# 		'x': frame_data.tan_x,
			# 		'y': frame_data.tan_y,
			# 		'z': frame_data.tan_z,
			# 		'w': frame_data.tan_w,
			# 	}

			insert_keyframes(fcurves, frame_data, frame, header_type, bind_rot, bind_loc)
	add_animation_to_nla_track(armature_object, new_action)

def create_bone_weights(mesh_file: CDspMeshFile, skin_data: CSkSkinInfo, geo_mesh_data: CGeoMesh) -> list[BoneWeight]:
	total_vertex_count = sum(mesh.vertex_count for mesh in mesh_file.meshes)
	bone_weights = [BoneWeight() for _ in range(total_vertex_count)]
	vertex_positions = [vertex.position for mesh in mesh_file.meshes for vertex in mesh.mesh_data[0].vertices]
	geo_mesh_positions = [[vertex.x, vertex.y, vertex.z] for vertex in geo_mesh_data.vertices]

	for index, check in enumerate(vertex_positions):
		j = geo_mesh_positions.index(check)
		bone_weights[index] = BoneWeight(skin_data.vertex_data[j].bone_indices, skin_data.vertex_data[j].weights)

	return bone_weights

def import_state_based_mesh_set(state_based_mesh_set: StateBasedMeshSet, source_collection: bpy.types.Collection, dir_name: str, bmg_file: DRS, global_matrix: Matrix, apply_transform: bool, import_collision_shape: bool, import_animation: bool, fps_selection: str, import_debris: bool, base_name: str, armature_object: bpy.types.Object, bone_list: list[DRSBone], slocator: SLocator = None, prefix: str = "") -> None:
	# Get individual mesh states
	for mesh_set in state_based_mesh_set.mesh_states:
		if mesh_set.has_files:
			# Create a new Collection for the State
			state_collection_name = f"{prefix}Mesh_State_{mesh_set.state_num}"
			state_collection = find_or_create_collection(source_collection, state_collection_name)
			# Load the DRS Files
			drs_file: DRS = DRS().read(os.path.join(dir_name, mesh_set.drs_file))

			if drs_file.csk_skeleton is not None and armature_object is None:
				# Create the Armature Data
				armature_data: bpy.types.Armature = bpy.data.armatures.new("CSkSkeleton")
				# Create the Armature Object and add the Armature Data to it
				armature_object: bpy.types.Object = bpy.data.objects.new("Armature", armature_data)
				# Link the Armature Object to the Source Collection
				source_collection.objects.link(armature_object)
				# Create the Skeleton
				bone_list = init_bones(drs_file.csk_skeleton)
				# Directly set armature data to edit mode
				bpy.context.view_layer.objects.active = armature_object
				bpy.ops.object.mode_set(mode='EDIT')
				# Create the Bone Tree without using bpy.ops or context
				create_bone_tree(armature_data, bone_list, bone_list[0])
				# Restore armature data mode to OBJECT
				bpy.ops.object.mode_set(mode='OBJECT')
				record_bind_pose(bone_list, armature_data)
				# Add the Animations to the Armature Object
				if bmg_file.animation_set is not None:
					# Apply the Transformations to the Armature Object
					apply_transformations(armature_object, global_matrix, apply_transform)

			if drs_file.csk_skin_info is not None:
				# Create the Bone Weights
				bone_weights = create_bone_weights(drs_file.cdsp_mesh_file, drs_file.csk_skin_info, drs_file.cgeo_mesh)

			# Create a Mesh Collection to store the Mesh Objects
			mesh_collection: bpy.types.Collection = bpy.data.collections.new("Meshes_Collection")
			state_collection.children.link(mesh_collection)
			for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
				offset = 0 if mesh_index == 0 else drs_file.cdsp_mesh_file.meshes[mesh_index - 1].vertex_count
				# Create the Mesh Data
				mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)
				# Create the Mesh Object and add the Mesh Data to it
				mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{mesh_index}", mesh_data)
				# Add the Bone Weights to the Mesh Object
				if drs_file.csk_skin_info is not None:
					cdsp_mesh_file_data = drs_file.cdsp_mesh_file.meshes[mesh_index]
					# Dictionary to store bone groups and weights
					bone_vertex_dict = {}
					# Iterate over vertices and collect them by group_id and weight
					for vidx in range(offset, offset + cdsp_mesh_file_data.vertex_count):
						bone_weight_data = bone_weights[vidx]

						for _ in range(4):  # Assuming 4 weights per vertex
							group_id = bone_weight_data.indices[_]
							weight = bone_weight_data.weights[_]

							if weight > 0:  # Only consider non-zero weights
								if group_id not in bone_vertex_dict:
									bone_vertex_dict[group_id] = {}

								if weight not in bone_vertex_dict[group_id]:
									bone_vertex_dict[group_id][weight] = []

								bone_vertex_dict[group_id][weight].append(vidx - offset)
					# Now process each bone group and add all the vertices in a single call
					for group_id, weight_data in bone_vertex_dict.items():
						bone_name = bone_list[group_id].name

						# Create or retrieve the vertex group for the bone
						if bone_name not in mesh_object.vertex_groups:
							vertex_group = mesh_object.vertex_groups.new(name=bone_name)
						else:
							vertex_group = mesh_object.vertex_groups[bone_name]

						# Add vertices with the same weight in one call
						for weight, vertex_indices in weight_data.items():
							vertex_group.add(vertex_indices, weight, 'ADD')
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
				if slocator is not None:
					location = (slocator.cmat_coordinate_system.position.x, slocator.cmat_coordinate_system.position.y, slocator.cmat_coordinate_system.position.z)
					rotation = slocator.cmat_coordinate_system.matrix.matrix
					rotation_matrix = [list(rotation[i:i+3]) for i in range(0, len(rotation), 3)]
					transposed_rotation = Matrix(rotation_matrix).transposed()
					# Create a new Matrix with the Location and Rotation
					local_matrix = Matrix.Translation(location) @ transposed_rotation.to_4x4()
					# Apply the Local Matrix to the Mesh Object
					if apply_transform:
						mesh_object.matrix_world = global_matrix @ local_matrix
						mirror_object_by_vector(mesh_object, Vector((0, 0, 1)))
					else:
						mesh_object.matrix_world = local_matrix
				# Create the Material Data
				material_data = create_material(dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name)
				# Assign the Material to the Mesh
				mesh_data.materials.append(material_data)
				# Link the Mesh Object to the Source Collection
				mesh_collection.objects.link(mesh_object)

			if drs_file.collision_shape is not None and import_collision_shape:
				# Create a Collision Shape Collection to store the Collision Shape Objects
				collision_shape_collection: bpy.types.Collection = bpy.data.collections.new("CollisionShapes_Collection")
				state_collection.children.link(collision_shape_collection)
				# Create a Box Collection to store the Box Objects
				box_collection: bpy.types.Collection = bpy.data.collections.new("Boxes_Collection")
				collision_shape_collection.children.link(box_collection)
				for _ in range(drs_file.collision_shape.box_count):
					box_object = create_collision_shape_box_object(drs_file.collision_shape.boxes[_], _)
					box_collection.objects.link(box_object)
					apply_transformations(box_object, global_matrix, apply_transform)
					# TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
					box_object.location = (box_object.location.x, box_object.location.y, -box_object.location.z)

				# Create a Sphere Collection to store the Sphere Objects
				sphere_collection: bpy.types.Collection = bpy.data.collections.new("Spheres_Collection")
				collision_shape_collection.children.link(sphere_collection)
				for _ in range(drs_file.collision_shape.sphere_count):
					sphere_object = create_collision_shape_sphere_object(drs_file.collision_shape.spheres[_], _)
					sphere_collection.objects.link(sphere_object)
					apply_transformations(sphere_object, global_matrix, apply_transform)

				# Create a Cylinder Collection to store the Cylinder Objects
				cylinder_collection: bpy.types.Collection = bpy.data.collections.new("Cylinders_Collection")
				collision_shape_collection.children.link(cylinder_collection)
				for _ in range(drs_file.collision_shape.cylinder_count):
					cylinder_object = create_collision_shape_cylinder_object(drs_file.collision_shape.cylinders[_], _)
					cylinder_collection.objects.link(cylinder_object)
					apply_transformations(cylinder_object, global_matrix, apply_transform)

			if bmg_file.animation_set is not None and armature_object is not None and import_animation:
				# Set the FPS for the Animation
				bpy.context.scene.render.fps = int(fps_selection)
				bpy.ops.object.mode_set(mode='POSE')
				for animation_key in bmg_file.animation_set.mode_animation_keys:
					for variant in animation_key.animation_set_variants:
						ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
						create_animation(ska_file, armature_object, bone_list, variant.file)

	# Get individual desctruction States
	if import_debris:
		for destruction_state in state_based_mesh_set.destruction_states:
			state_collection_name = f"{prefix}Destruction_State_{destruction_state.state_num}"
			state_collection = find_or_create_collection(source_collection, state_collection_name)
			# Load the XML File
			xml_file_path = os.path.join(dir_name, destruction_state.file_name)
			# Read the file without any imports
			with open(xml_file_path, 'r', encoding='utf-8') as file:
				xml_file = file.read()
			# Parse the XML File
			xml_root = ET.fromstring(xml_file)
			for element in xml_root.findall(".//Element[@type='PhysicObject']"):
				resource = element.attrib.get("resource")
				name = element.attrib.get("name")
				if resource and name:
					drs_file: DRS = DRS().read(os.path.join(dir_name, "meshes", resource))
					for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
						# Create the Mesh Data
						mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)
						# Create the Mesh Object and add the Mesh Data to it
						mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{name}", mesh_data)
						apply_transformations(mesh_object, global_matrix, apply_transform)
						# Create the Material Data
						material_data = create_material(dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name + "_" + name)
						# Assign the Material to the Mesh
						mesh_data.materials.append(material_data)
						# Link the Mesh Object to the Source Collection
						state_collection.objects.link(mesh_object)

def import_mesh_set_grid(bmg_file: DRS, source_collection: bpy.types.Collection, dir_name: str, base_name: str, global_matrix: Matrix, apply_transform: bool, import_collision_shape: bool, import_animation: bool, fps_selection: str, import_debris: bool, armature_object: bpy.types.Object = None, bone_list: list[DRSBone] = None) -> None:
	for module in bmg_file.mesh_set_grid.mesh_modules:
		if module.has_mesh_set:
			import_state_based_mesh_set(module.state_based_mesh_set, source_collection, dir_name, bmg_file, global_matrix, apply_transform, import_collision_shape, import_animation, fps_selection, import_debris, base_name, armature_object, bone_list)

def import_csk_skeleton(source_collection: bpy.types.Collection, drs_file: DRS) -> Tuple[bpy.types.Object, list[DRSBone]]:
	# Create the Armature Data
	armature_data: bpy.types.Armature = bpy.data.armatures.new("CSkSkeleton")
	# Create the Armature Object and add the Armature Data to it
	armature_object: bpy.types.Object = bpy.data.objects.new("Armature", armature_data)
	# Link the Armature Object to the Source Collection
	source_collection.objects.link(armature_object)
	# Create the Skeleton
	bone_list = init_bones(drs_file.csk_skeleton)
	# Directly set armature data to edit mode
	bpy.context.view_layer.objects.active = armature_object
	bpy.ops.object.mode_set(mode='EDIT')
	# Create the Bone Tree without using bpy.ops or context
	create_bone_tree(armature_data, bone_list, bone_list[0])
	# Restore armature data mode to OBJECT
	bpy.ops.object.mode_set(mode='OBJECT')
	record_bind_pose(bone_list, armature_data)
	return armature_object, bone_list

def import_collision_shapes(source_collection: bpy.types.Collection, drs_file: DRS, global_matrix: Matrix, apply_transform: bool) -> None:
	# Create a Collision Shape Collection to store the Collision Shape Objects
	collision_shape_collection: bpy.types.Collection = bpy.data.collections.new("CollisionShapes_Collection")
	source_collection.children.link(collision_shape_collection)
	# Create a Box Collection to store the Box Objects
	box_collection: bpy.types.Collection = bpy.data.collections.new("Boxes_Collection")
	collision_shape_collection.children.link(box_collection)
	for _ in range(drs_file.collision_shape.box_count):
		box_object = create_collision_shape_box_object(drs_file.collision_shape.boxes[_], _)
		box_collection.objects.link(box_object)
		apply_transformations(box_object, global_matrix, apply_transform)
		# TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
		box_object.location = (box_object.location.x, box_object.location.y, -box_object.location.z)

	# Create a Sphere Collection to store the Sphere Objects
	sphere_collection: bpy.types.Collection = bpy.data.collections.new("Spheres_Collection")
	collision_shape_collection.children.link(sphere_collection)
	for _ in range(drs_file.collision_shape.sphere_count):
		sphere_object = create_collision_shape_sphere_object(drs_file.collision_shape.spheres[_], _)
		sphere_collection.objects.link(sphere_object)
		apply_transformations(sphere_object, global_matrix, apply_transform)

	# Create a Cylinder Collection to store the Cylinder Objects
	cylinder_collection: bpy.types.Collection = bpy.data.collections.new("Cylinders_Collection")
	collision_shape_collection.children.link(cylinder_collection)
	for _ in range(drs_file.collision_shape.cylinder_count):
		cylinder_object = create_collision_shape_cylinder_object(drs_file.collision_shape.cylinders[_], _)
		cylinder_collection.objects.link(cylinder_object)
		apply_transformations(cylinder_object, global_matrix, apply_transform)

def import_cdsp_mesh_file(mesh_index: int, mesh_file: CDspMeshFile) -> Tuple[bpy.types.Object, bpy.types.Mesh]:
	# Create the Mesh Data
	mesh_data = create_static_mesh(mesh_file, mesh_index)
	# Create the Mesh Object and add the Mesh Data to it
	mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{mesh_index}", mesh_data)

	return mesh_object, mesh_data

def add_skin_weights_to_mesh(mesh_object: bpy.types.Object, bone_list: list[DRSBone], bone_weights: list[BoneWeight], offset: int, cdsp_mesh_file_data: BattleforgeMesh) -> None:
	# Dictionary to store bone groups and weights
	bone_vertex_dict = {}
	# Iterate over vertices and collect them by group_id and weight
	for vidx in range(offset, offset + cdsp_mesh_file_data.vertex_count):
		bone_weight_data = bone_weights[vidx]

		for _ in range(4): # Assuming 4 weights per vertex
			group_id = bone_weight_data.indices[_]
			weight = bone_weight_data.weights[_]

			if weight > 0: # Only consider non-zero weights
				if group_id not in bone_vertex_dict:
					bone_vertex_dict[group_id] = {}

				if weight not in bone_vertex_dict[group_id]:
					bone_vertex_dict[group_id][weight] = []

				bone_vertex_dict[group_id][weight].append(vidx - offset)
	# Now process each bone group and add all the vertices in a single call
	for group_id, weight_data in bone_vertex_dict.items():
		bone_name = bone_list[group_id].name

		# Create or retrieve the vertex group for the bone
		if bone_name not in mesh_object.vertex_groups:
			vertex_group = mesh_object.vertex_groups.new(name=bone_name)
		else:
			vertex_group = mesh_object.vertex_groups[bone_name]

		# Add vertices with the same weight in one call
		for weight, vertex_indices in weight_data.items():
			vertex_group.add(vertex_indices, weight, 'ADD')

def load_drs(context: bpy.types.Context, filepath="", apply_transform=True, global_matrix=Matrix.Identity(4), import_collision_shape=False, fps_selection=30, import_animation=True, import_debris=False, import_construction=False, import_modules=True) -> None:
 	# reset messages
	global messages
	messages = []
	# Load time measurement
	start_time = time.time()
	base_name = os.path.basename(filepath).split(".")[0]
	dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)

	source_collection: bpy.types.Collection = bpy.data.collections.new("DRSModel_" + base_name)
	context.collection.children.link(source_collection)

	# Create the Armature Object if a Skeleton is present
	if drs_file.csk_skeleton is not None:
		armature_object, bone_list = import_csk_skeleton(source_collection, drs_file)
		# Add the Animations to the Armature Object
		if drs_file.animation_set is not None:
			# Apply the Transformations to the Armature Object
			apply_transformations(armature_object, global_matrix, apply_transform)

	# Create the Skin Weights
	if drs_file.csk_skin_info is not None:
		bone_weights = create_bone_weights(drs_file.cdsp_mesh_file, drs_file.csk_skin_info, drs_file.cgeo_mesh)

	# Create a Mesh Collection to store the Mesh Objects
	mesh_collection: bpy.types.Collection = bpy.data.collections.new("Meshes_Collection")
	source_collection.children.link(mesh_collection)
	# Create the Mesh Objects
	for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
		offset = 0 if mesh_index == 0 else drs_file.cdsp_mesh_file.meshes[mesh_index - 1].vertex_count
		mesh_object, mesh_data = import_cdsp_mesh_file(mesh_index, drs_file.cdsp_mesh_file)
		# Add the Bone Weights to the Mesh Object
		if drs_file.csk_skin_info is not None:
			add_skin_weights_to_mesh(mesh_object, bone_list, bone_weights, offset, drs_file.cdsp_mesh_file.meshes[mesh_index])
		# Check if the Mesh has a Skeleton and modify the Mesh Object accordingly
		if drs_file.csk_skeleton is not None:
			mesh_object.parent = armature_object
			modifier = mesh_object.modifiers.new(type="ARMATURE", name='Armature')
			modifier.object = armature_object
		else:
			# Apply the Transformations to the Mesh Object when no Skeleton is present else we transform the armature
			apply_transformations(mesh_object, global_matrix, apply_transform)
		# Create the Material Data
		material_data = create_material(dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name)
		# Assign the Material to the Mesh
		mesh_data.materials.append(material_data)
		# Link the Mesh Object to the Source Collection
		mesh_collection.objects.link(mesh_object)

	# Create the Collision Shape Objects
	if drs_file.collision_shape is not None and import_collision_shape:
		import_collision_shapes(source_collection, drs_file, global_matrix, apply_transform)

	# Create the Animation Objects
	if drs_file.animation_set is not None and armature_object is not None and import_animation:
		# Set the FPS for the Animation
		bpy.context.scene.render.fps = int(fps_selection)
		bpy.ops.object.mode_set(mode='POSE')
		for animation_key in drs_file.animation_set.mode_animation_keys:
			for variant in animation_key.animation_set_variants:
				ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
				create_animation(ska_file, armature_object, bone_list, variant.file)

	if import_modules and drs_file.cdrw_locator_list is not None:
		for slocator in drs_file.cdrw_locator_list.slocators:
			if slocator.file_name_length > 0:
				if slocator.class_type == "Module1":
					module_collection = find_or_create_collection(source_collection, "Modules1")
					# Load the BMS Files (replace.module with .bms)
					module_file_name = slocator.file_name.replace(".module", ".bms")
					module: BMS = BMS().read(os.path.join(dir_name, module_file_name))
					module_name = slocator.class_type + "_" + str(slocator.sub_id)
					import_state_based_mesh_set(module.state_based_mesh_set, module_collection, dir_name, drs_file, global_matrix, apply_transform, import_collision_shape, import_animation, fps_selection, import_debris, module_name, armature_object, bone_list, slocator, "Module_1_")
				elif slocator.class_type == "Module2":
					module_collection = find_or_create_collection(source_collection, "Modules2")
					# Load the BMS Files (replace.module with .bms)
					module_file_name = slocator.file_name.replace(".module", ".bms")
					module: BMS = BMS().read(os.path.join(dir_name, module_file_name))
					module_name = slocator.class_type + "_" + str(slocator.sub_id)
					import_state_based_mesh_set(module.state_based_mesh_set, module_collection, dir_name, drs_file, global_matrix, apply_transform, import_collision_shape, import_animation, fps_selection, import_debris, module_name, armature_object, bone_list, slocator, "Module_2_")

	# Return to the Object Mode
	bpy.ops.object.mode_set(mode='OBJECT')

	# Print the Time Measurement
	show_message_box(f"Imported {base_name} in {time.time() - start_time:.2f} seconds.", "Import Time", 'INFO', True)
	# Show the Messages
	return {'FINISHED'}

def load_bmg(context: bpy.types.Context, filepath="", apply_transform=True, global_matrix=Matrix.Identity(4), import_collision_shape=False, fps_selection=30, import_animation=True, import_debris=True, import_construction=True, import_modules=False) -> None:
	dir_name = os.path.dirname(filepath)
	base_name = os.path.basename(filepath).split(".")[0]
	source_collection: bpy.types.Collection = bpy.data.collections.new("DRSModel_" + base_name)
	context.collection.children.link(source_collection)
	bmg_file: DRS = DRS().read(filepath)

	# Models share the same Skeleton Files, so we only need to create one Armature
	armature_object = None
	bone_list = None

	# Ground Decal
	if bmg_file.mesh_set_grid.ground_decal is not None:
		# Decal Collection
		ground_decal_collection: bpy.types.Collection = bpy.data.collections.new("GroundDecal_Collection")
		source_collection.children.link(ground_decal_collection)
		# Load the DRS Files
		ground_decal: DRS = DRS().read(os.path.join(dir_name, bmg_file.mesh_set_grid.ground_decal))
		# Load the Meshes
		for mesh_index in range(ground_decal.cdsp_mesh_file.mesh_count):
			offset = 0 if mesh_index == 0 else ground_decal.cdsp_mesh_file.meshes[mesh_index - 1].vertex_count
			# Create the Mesh Data
			mesh_data = create_static_mesh(ground_decal.cdsp_mesh_file, mesh_index)
			# Create the Mesh Object and add the Mesh Data to it
			mesh_object: bpy.types.Object = bpy.data.objects.new(f"GroundDecal{mesh_index}", mesh_data)
			apply_transformations(mesh_object, global_matrix, apply_transform)
			# Create the Material Data
			material_data = create_material(dir_name, mesh_index, ground_decal.cdsp_mesh_file.meshes[mesh_index], "GroundDecal")
			# Assign the Material to the Mesh
			mesh_data.materials.append(material_data)
			# Link the Mesh Object to the Source Collection
			ground_decal_collection.objects.link(mesh_object)

	# Collision Shape
	if bmg_file.collision_shape is not None and import_collision_shape:
		# Create a Collision Shape Collection to store the Collision Shape Objects
		collision_shape_collection: bpy.types.Collection = bpy.data.collections.new("CollisionShapes_Collection")
		source_collection.children.link(collision_shape_collection)
		# Create a Box Collection to store the Box Objects
		box_collection: bpy.types.Collection = bpy.data.collections.new("Boxes_Collection")
		collision_shape_collection.children.link(box_collection)
		for _ in range(bmg_file.collision_shape.box_count):
			box_object = create_collision_shape_box_object(bmg_file.collision_shape.boxes[_], _)
			box_collection.objects.link(box_object)
			apply_transformations(box_object, global_matrix, apply_transform)
			# TODO: WORKAROUND: Make the Box's Z-Location negative to flip the Axis
			box_object.location = (box_object.location.x, box_object.location.y, -box_object.location.z)

		# Create a Sphere Collection to store the Sphere Objects
		sphere_collection: bpy.types.Collection = bpy.data.collections.new("Spheres_Collection")
		collision_shape_collection.children.link(sphere_collection)
		for _ in range(bmg_file.collision_shape.sphere_count):
			sphere_object = create_collision_shape_sphere_object(bmg_file.collision_shape.spheres[_], _)
			sphere_collection.objects.link(sphere_object)
			apply_transformations(sphere_object, global_matrix, apply_transform)

		# Create a Cylinder Collection to store the Cylinder Objects
		cylinder_collection: bpy.types.Collection = bpy.data.collections.new("Cylinders_Collection")
		collision_shape_collection.children.link(cylinder_collection)
		for _ in range(bmg_file.collision_shape.cylinder_count):
			cylinder_object = create_collision_shape_cylinder_object(bmg_file.collision_shape.cylinders[_], _)
			cylinder_collection.objects.link(cylinder_object)
			apply_transformations(cylinder_object, global_matrix, apply_transform)

	# Import Mesh Set Grid
	if bmg_file.mesh_set_grid is not None:
		import_mesh_set_grid(bmg_file, source_collection, dir_name, base_name, global_matrix, apply_transform, import_collision_shape, import_animation, fps_selection, import_debris, armature_object, bone_list)

	# Import Construction
	if import_construction:
		slocator_collection: bpy.types.Collection = bpy.data.collections.new(f"SLocators")
		source_collection.children.link(slocator_collection)
		for slocator in bmg_file.mesh_set_grid.cdrw_locator_list.slocators:
			if slocator.file_name_length > 0 and slocator.class_type == "Construction":
				# We need to move two directory up to find the construction folder
				construction_dir = os.path.join(dir_name, "..", "..", "construction")
				# Check for file ending (DRS or BMS)
				if slocator.file_name.endswith(".bms"):
					bms_file: BMS = BMS().read(os.path.join(construction_dir, slocator.file_name))
					module_name = slocator.class_type + "_" + str(slocator.sub_id)
					import_state_based_mesh_set(bms_file.state_based_mesh_set, slocator_collection, construction_dir, bms_file, global_matrix, apply_transform, import_collision_shape, import_animation, fps_selection, import_debris, module_name, armature_object, bone_list, slocator, "Construction_")
				elif slocator.file_name.endswith(".drs"):
					drs_file: DRS = DRS().read(os.path.join(construction_dir, slocator.file_name))
					for mesh_index in range(drs_file.cdsp_mesh_file.mesh_count):
						# Create the Mesh Data
						mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, mesh_index)
						# Create the Mesh Object and add the Mesh Data to it
						mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{slocator.class_type}", mesh_data)
						# Apply the Transformations to the Mesh Object
						apply_transformations(mesh_object, global_matrix, apply_transform)
						# We need to move and rotate the construction objects prior to applying the global matrix
						location = (slocator.cmat_coordinate_system.position.x, slocator.cmat_coordinate_system.position.y, slocator.cmat_coordinate_system.position.z)
						rotation = slocator.cmat_coordinate_system.matrix.matrix
						rotation_matrix = [list(rotation[i:i+3]) for i in range(0, len(rotation), 3)]
						transposed_rotation = Matrix(rotation_matrix).transposed()
						# Create a new Matrix with the Location and Rotation
						local_matrix = Matrix.Translation(location) @ transposed_rotation.to_4x4()
						# Apply the Local Matrix to the Mesh Object
						if apply_transform:
							mesh_object.matrix_world = global_matrix @ local_matrix
							mirror_object_by_vector(mesh_object, Vector((0, 0, 1)))
						else:
							mesh_object.matrix_world = local_matrix
						# Create the Material Data
						material_data = create_material(construction_dir, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index], base_name + "_Construction_" + str(mesh_index))
						# Assign the Material to the Mesh
						mesh_data.materials.append(material_data)
						# Link the Mesh Object to the Source Collection
						slocator_collection.objects.link(mesh_object)
				else:
					show_message_box(f"Construction file {slocator.file_name} has an unsupported file ending.", "Error", 'ERROR')

	# Return to the Object Mode
	if bpy.context.object:
		if bpy.context.object.mode == 'EDIT':
			bpy.ops.object.mode_set(mode='OBJECT')
		elif bpy.context.object.mode == 'POSE':
			bpy.ops.object.mode_set(mode='OBJECT')

	return {'FINISHED'}

def triangulate(meshes_collection: bpy.types.Collection) -> None:
	for obj in meshes_collection.objects:
		if obj.type == 'MESH':
			# Select the object
			me = obj.data

			# Get a BMesh representation
			bm = bmesh.new() # pylint: disable=E1111
			bm.from_mesh(me)

			# Triangulate the mesh
			bmesh.ops.triangulate(bm, faces=bm.faces[:]) # pylint: disable=E1111, E1120
			# V2.79 : bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method=0, ngon_method=0)

			# Finish up, write the bmesh back to the mesh
			bm.to_mesh(me)
			bm.free()

def verify_mesh_vertex_count(meshes_collection: bpy.types.Collection) -> bool:
	'''Check if the Models are valid for the game. This includes the following checks:
	- Check if the Meshes have more than 32767 Vertices'''
	unified_mesh: bmesh.types.BMesh = bmesh.new()

	for obj in meshes_collection.objects:
		if obj.type == "MESH":
			if len(obj.data.vertices) > 32767:
				show_message_box("One Mesh has more than 32767 Vertices. This is not supported by the game.", "Error", 'ERROR')
				return False
			unified_mesh.from_mesh(obj.data)

	unified_mesh.verts.ensure_lookup_table()
	unified_mesh.verts.index_update()
	bmesh.ops.remove_doubles(unified_mesh, verts=unified_mesh.verts, dist=0.0001)

	if len(unified_mesh.verts) > 32767:
		show_message_box("The unified Mesh has more than 32767 Vertices. This is not supported by the game.", "Error", 'ERROR')
		return False

	unified_mesh.free()

	return True

def split_meshes_by_uv_islands(meshes_collection: bpy.types.Collection) -> None:
	'''Split the Meshes by UV Islands.'''
	for obj in meshes_collection.objects:
		if obj.type == "MESH":
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='EDIT')
			bm = bmesh.from_edit_mesh(obj.data) # pylint: disable=E1111
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
			bmesh.ops.split_edges(bm, edges=seams) # pylint: disable=E1120
			# re instate old seams.. could clear new seams.
			for e in old_seams:
				e.seam = True
			bmesh.update_edit_mesh(obj.data)
			bpy.ops.object.mode_set(mode='OBJECT')

def set_origin_to_world_origin(meshes_collection: bpy.types.Collection) -> None:
	for obj in meshes_collection.objects:
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

def create_unified_mesh(meshes_collection: bpy.types.Collection) -> bpy.types.Mesh:
	'''Create a unified Mesh from a Collection of Meshes.'''
	if len(meshes_collection.objects) == 1:
		return meshes_collection.objects[0].data

	bm: bmesh.types.BMesh = bmesh.new()

	for mesh in meshes_collection.objects:
		if mesh.type == "MESH":
			bm.from_mesh(mesh.data)

	# Count Faces and Vertices before removing doubles
	face_count = len(bm.faces)
	vertex_count = len(bm.verts)

	# Remove Duplicates by lowest possible float
	bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

	# Create the new Mesh
	unified_mesh = bpy.data.meshes.new("unified_mesh")
	bm.to_mesh(unified_mesh)
	bm.free()

	# Count Faces and Vertices after removing doubles
	face_count_after = len(unified_mesh.polygons)
	vertex_count_after = len(unified_mesh.vertices)

	# Show the Message Box
	show_message_box(f"Unified Mesh has {face_count_after} Faces and {vertex_count_after} Vertices after removing duplicates. The original Mesh had {face_count} Faces and {vertex_count} Vertices.", "Unified Mesh", 'INFO')

	return unified_mesh

def create_cgeo_mesh(unique_mesh: bpy.types.Mesh) -> CGeoMesh:
	'''Create a CGeoMesh from a Blender Mesh Object.'''
	_cgeo_mesh = CGeoMesh()
	_cgeo_mesh.index_count = len(unique_mesh.polygons) * 3
	_cgeo_mesh.vertex_count = len(unique_mesh.vertices)
	_cgeo_mesh.faces = []
	_cgeo_mesh.vertices = []

	for _face in unique_mesh.polygons:
		new_face = Face()
		new_face.indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
		_cgeo_mesh.faces.append(new_face)

	for _vertex in unique_mesh.vertices:
		_cgeo_mesh.vertices.append(Vector4(_vertex.co.x, _vertex.co.y, _vertex.co.z, 1.0))

	return _cgeo_mesh

def create_obb_node(unique_mesh: bpy.types.Mesh) -> OBBNode:
	'''Create an OBB Node for the OBB Tree.'''
	obb_node = OBBNode()
	obb_node.node_depth = 0
	obb_node.current_triangle_count = 0
	obb_node.minimum_triangles_found = len(unique_mesh.polygons)
	obb_node.unknown1 = 0
	obb_node.unknown2 = 0
	obb_node.unknown3 = 0
	obb_node.oriented_bounding_box = CMatCoordinateSystem()
	obb_node.oriented_bounding_box.position = Vector((0, 0, 0)) # TODO: We need to update this later as we need to calculate the center of the mesh
	obb_node.oriented_bounding_box.matrix = Matrix.Identity(3) # TODO: We need to update this later as we need to calculate the rotation of the mesh

	return obb_node

def create_cgeo_obb_tree(unique_mesh: bpy.types.Mesh) -> CGeoOBBTree:
	'''Create a CGeoOBBTree from a Blender Mesh Object.'''
	_cgeo_obb_tree = CGeoOBBTree()
	_cgeo_obb_tree.triangle_count = len(unique_mesh.polygons)
	_cgeo_obb_tree.faces = []

	for _face in unique_mesh.polygons:
		new_face = Face()
		new_face.indices = [_face.vertices[0], _face.vertices[1], _face.vertices[2]]
		_cgeo_obb_tree.faces.append(new_face)

	_cgeo_obb_tree.matrix_count = 0
	_cgeo_obb_tree.obb_nodes = []

	for _ in range(_cgeo_obb_tree.matrix_count):
		_cgeo_obb_tree.obb_nodes.append(create_obb_node(unique_mesh))

	return _cgeo_obb_tree

def create_cdsp_joint_map(meshes_collection: bpy.types.Collection) -> Tuple[CDspJointMap, dict]:
	'''Create a CDspJointMap. If empty is True, the CDspJointMap will be empty.'''
	_bone_map = {}
	_joint_map = CDspJointMap()

	# Loop the meshes
	for child in meshes_collection.objects:
		if child.type == "MESH":
			# Get the Vertex Groups
			_vertex_groups = child.vertex_groups

			if len(_vertex_groups) == 0:
				break
			_joint_map.joint_group_count += 1
			# Init the Bone ID Counter
			_bone_id = 0
			# Init the temp JointGroups List
			_temp_joint_group = JointGroup() # Check this!
			# Loop the Vertex Groups
			for _vertex_group in _vertex_groups:
				# Get the Bone from the Vertex Group
				_bone_Name = _vertex_group.name
				_temp_joint_group.joint_count += 1
				_temp_joint_group.joints.append(_bone_id)
				_bone_map[_bone_Name] = _bone_id
				_bone_id += 1
			_joint_map.joint_groups.append(_temp_joint_group)
	return _joint_map, _bone_map

def get_bb(obj) -> Tuple[Vector3, Vector3]:
	'''Get the Bounding Box of an Object. Returns the minimum and maximum Vector of the Bounding Box.'''
	bb_min = Vector3(0, 0, 0)
	bb_max = Vector3(0, 0, 0)

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

def set_color_map(color_map: bpy.types.Node, new_mesh: BattleforgeMesh, mesh_index: int, model_name: str, folder_path: str) -> bool:
	if color_map is None:
		show_message_box("The color_map is None. Please check the Material Node.", "Error", 'ERROR')
		return False

	if color_map.is_linked:
		new_mesh.textures.length += 1
		color_map_texture = Texture()
		color_map_texture.name = model_name + "_" + str(mesh_index) + "_col"
		color_map_texture.length = color_map_texture.name.__len__()
		color_map_texture.identifier = 1684432499
		new_mesh.textures.textures.append(color_map_texture)

		# Check color_map.links[0].from_node.image for the Image
		if color_map.links[0].from_node.type == "TEX_IMAGE":
			# Export the Image as a DDS File (DXT3)
			img = color_map.links[0].from_node.image

			if img is not None:
				temp_path = bpy.path.abspath("//") + color_map_texture.name + ".png"
				img.file_format = "PNG"
				img.save(filepath=temp_path)
				args = ["-ft", "dds", "-f", "DXT5", "-dx9", "-pow2", "-srgb", "-y", color_map_texture.name + ".dds", "-o", folder_path]
				subprocess.run([resource_dir + "/texconv.exe", temp_path] + args, check=False)
				os.remove(temp_path)
			else:
				show_message_box("The color_map Texture is not an Image or the Image is None!", "Error", 'ERROR')
				return False
	else:
		show_message_box("The color_map is not linked. Please check the Material Node.", "Error", 'ERROR')
		return False

	return True

def set_normal_map(normal_map: bpy.types.Node, new_mesh: BattleforgeMesh, mesh_index: int, model_name: str, folder_path: str, bool_param_bit_flag: int) -> None:
	if normal_map is not None and normal_map.is_linked:
		# Check normal_map.links[0].from_node.image for the Image
		if normal_map.links[0].from_node.type == "TEX_IMAGE":
			# Export the Image as a DDS File (DXT1)
			img = normal_map.links[0].from_node.image

			if img is not None:
				new_mesh.textures.length+=1
				normal_map_texture = Texture()
				normal_map_texture.name = model_name + "_" + str(mesh_index) + "_nor"
				normal_map_texture.length = normal_map_texture.name.__len__()
				normal_map_texture.identifier = 1852992883
				new_mesh.textures.textures.append(normal_map_texture)
				bool_param_bit_flag += 100000000000000000
				temp_path = bpy.path.abspath("//") + normal_map_texture.name + ".png"
				img.file_format = "PNG"
				img.save(filepath=temp_path)
				args = ["-ft", "dds", "-f", "DXT1", "-dx9", "-pow2", "-srgb", "-at", "0.0", "-y", normal_map_texture.name + ".dds", "-o", folder_path]
				subprocess.run([resource_dir + "/texconv.exe", temp_path] + args, check=False)
				os.remove(temp_path)
			else:
				show_message_box("The normal_map Texture is not an Image or the Image is None!", "Info", 'INFO')
		else:
			show_message_box("The normal_map is not linked. Please check the Material Node if this is intended.", "Info", 'INFO')
	else:
		show_message_box("The normal_map is None. Please check the Material Node if this is intended.", "Info", 'INFO')

# def set_metallic_roughness_emission_map(metallic_map: bpy.types.Node, roughness_map: bpy.types.Node, emission_map: bpy.types.Node, new_mesh: BattleforgeMesh, mesh_index: int, model_name: str, folder_path: str, bool_param_bit_flag: int) -> None:
# 	if (metallic_map is not None and metallic_map.is_linked) or (roughness_map is not None and roughness_map.is_linked) or (emission_map is not None and emission_map.is_linked):
# 		new_mesh.textures.length+=1
# 		metallic_map_texture = Texture()
# 		metallic_map_texture.name = model_name + "_" + str(mesh_index) + "_par"
# 		metallic_map_texture.length = metallic_map_texture.name.__len__()
# 		metallic_map_texture.identifier = 1936745324
# 		new_mesh.textures.textures.append(metallic_map_texture)
# 		bool_param_bit_flag += 10000000000000000
# 		# Par Map is a combination of Metallic, Roughness and Fluid Map and Emission Map. We need to combine them in an array and push them to the ImageToExport List
# 		img_R, img_G, img_A = None, None, None
# 		pixels_R, pixels_G, pixels_A = None, None, None

# 		if metallic_map is not None and metallic_map.is_linked:
# 			# This can either be a Map or a Separate RGB Node
# 			if metallic_map.links[0].from_node.type == "SEPRGB" or metallic_map.links[0].from_node.type == "SEPARATE_COLOR":
# 				# We ned to get the Input
# 				img_R = metallic_map.links[0].from_node.inputs[0].links[0].from_node.image
# 				# If the Image is None, we need to get the Image from the Input. SHow meesage to disconnect the Image from the Node
# 				if img_R is not None and img_R.type == "IMAGE":
# 					pixels_R = img_R.pixels[:]
# 				else:
# 					show_message_box("The metallic_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')
# 			else:
# 				img_R = metallic_map.links[0].from_node.image
# 				if img_R is not None and img_R.pixels[:].__len__() > 0:
# 					pixels_R = img_R.pixels[:]
# 				else:
# 					show_message_box("The metallic_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')

# 		if roughness_map is not None and roughness_map.is_linked:
# 			# This can either be a Map or a Separate RGB Node
# 			if roughness_map.links[0].from_node.type == "SEPRGB" or roughness_map.links[0].from_node.type == "SEPARATE_COLOR":
# 				# We ned to get the Input
# 				img_G = roughness_map.links[0].from_node.inputs[0].links[0].from_node.image
# 				if img_G is not None and img_G.type == "IMAGE":
# 					pixels_G = img_G.pixels[:]
# 				else:
# 					show_message_box("The roughness_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')
# 			else:
# 				img_G = roughness_map.links[0].from_node.image
# 				if img_G is not None and img_G.pixels[:].__len__() > 0:
# 					pixels_G = img_G.pixels[:]
# 				else:
# 					show_message_box("The roughness_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')

# 		if emission_map is not None and emission_map.is_linked:
# 			# This can either be a Map or a Separate RGB Node
# 			if emission_map.links[0].from_node.type == "SEPRGB" or emission_map.links[0].from_node.type == "SEPARATE_COLOR":
# 				# We ned to get the Input
# 				img_A = emission_map.links[0].from_node.inputs[0].links[0].from_node.image
# 				if img_A is not None and img_A.type == "IMAGE":
# 					pixels_A = img_A.pixels[:]
# 				else:
# 					show_message_box("The emission_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')
# 			else:
# 				img_A = emission_map.links[0].from_node.image
# 				if img_A is not None and img_A.pixels[:].__len__() > 0:
# 					pixels_A = img_A.pixels[:]
# 				else:
# 					show_message_box("The emission_map is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')

# 		# Get the Image Size by either the R, G or A Image
# 		if img_R is not None:
# 			Width = img_R.size[0]
# 			Height = img_R.size[1]
# 		elif img_G is not None:
# 			Width = img_G.size[0]
# 			Height = img_G.size[1]
# 		elif img_A is not None:
# 			Width = img_A.size[0]
# 			Height = img_A.size[1]
# 		else:
# 			show_message_box("No Image is set for the parameter map. Please set an Image!", "Info", 'INFO')

# 		# Combine the Images
# 		new_img = bpy.data.images.new(name=metallic_map_texture.name, width=Width, height=Height, alpha=True, float_buffer=False)
# 		new_pixels = []

# 		for i in range(0, Width * Height * 4, 4):
# 			red_value = pixels_R[i] if pixels_R is not None else 0
# 			green_value = pixels_G[i + 1] if pixels_G is not None else 0
# 			# TODO: Fluid
# 			blue_value = 0
# 			alpha_value = pixels_A[i + 3] if pixels_A is not None else 0
# 			new_pixels.extend([red_value, green_value, blue_value, alpha_value])

# 		new_img.pixels = new_pixels
# 		new_img.file_format = "PNG"
# 		new_img.update()

# 		# Export the Image as a DDS File (DXT5)
# 		temp_path = bpy.path.abspath("//") + metallic_map_texture.name + ".png"
# 		new_img.save(filepath=temp_path)

# 		# convert the image to dds dxt5 by using texconv.exe in the resources folder
# 		args = ["-ft", "dds", "-f", "DXT5", "-dx9", "-bc", "d", "-pow2", "-y", metallic_map_texture.name + ".dds", "-o", folder_path]
# 		subprocess.run([resource_dir + "/texconv.exe", temp_path] + args, check=False)

# 		# Remove the Temp File
# 		os.remove(temp_path)

def set_metallic_roughness_emission_map(metallic_map: bpy.types.Node, roughness_map: bpy.types.Node, emission_map: bpy.types.Node, new_mesh: BattleforgeMesh, mesh_index: int, model_name: str, folder_path: str, bool_param_bit_flag: int) -> None:
	def get_image_and_pixels(map_node, map_name):
		if map_node is None or not map_node.is_linked:
			return None, None

		from_node = map_node.links[0].from_node
		if from_node.type in {"SEPRGB", "SEPARATE_COLOR"}:
			if not from_node.inputs[0].is_linked:
				show_message_box(f"The {map_name} input is not linked. Please connect an Image Node!", "Info", 'INFO')
				return None, None
			input_node = from_node.inputs[0].links[0].from_node
			img = getattr(input_node, 'image', None)
		else:
			img = getattr(from_node, 'image', None)

		if img is None or not img.pixels:
			show_message_box(f"The {map_name} is set, but the Image is None. Please disconnect the Image from the Node if you don't want to use it!", "Info", 'INFO')
			return None, None

		return img, img.pixels[:]

	# Check if any of the maps are linked
	if not any(map_node and map_node.is_linked for map_node in [metallic_map, roughness_map, emission_map]):
		return

	# Retrieve images and pixels
	img_R, pixels_R = get_image_and_pixels(metallic_map, "metallic_map")
	img_G, pixels_G = get_image_and_pixels(roughness_map, "roughness_map")
	img_A, pixels_A = get_image_and_pixels(emission_map, "emission_map")

	# Determine image dimensions
	for img in [img_R, img_G, img_A]:
		if img:
			Width, Height = img.size
			break
	else:
		show_message_box("No Image is set for the parameter map. Please set an Image!", "Info", 'INFO')
		return

	# Update mesh textures and flags
	new_mesh.textures.length += 1
	texture_name = f"{model_name}_{mesh_index}_par"
	metallic_map_texture = Texture()
	metallic_map_texture.name = model_name + "_" + str(mesh_index) + "_par"
	metallic_map_texture.length = metallic_map_texture.name.__len__()
	metallic_map_texture.identifier = 1936745324
	new_mesh.textures.textures.append(metallic_map_texture)
	bool_param_bit_flag += 0b10000000000000000

	# Combine the images into a new image
	new_img = bpy.data.images.new(name=texture_name, width=Width, height=Height, alpha=True, float_buffer=False)
	new_pixels = []
	total_pixels = Width * Height * 4

	for i in range(0, total_pixels, 4):
		new_pixels.extend([
			pixels_R[i] if pixels_R else 0,        # Red channel
			pixels_G[i] if pixels_G else 0,        # Green channel
			0,                                     # Blue channel (placeholder for Fluid Map)
			pixels_A[i] if pixels_A else 0         # Alpha channel
		])

	new_img.pixels = new_pixels
	new_img.file_format = "PNG"
	new_img.update()

	# Save the combined image
	temp_path = bpy.path.abspath(f"//{texture_name}.png")
	new_img.save_render(filepath=temp_path)

	# Convert the image to DDS format using texconv.exe
	texconv_exe = os.path.join(resource_dir, "texconv.exe")
	output_path = os.path.join(folder_path, f"{texture_name}.dds")
	args = [
		texconv_exe,
		"-ft", "dds",
		"-f", "DXT5",
		"-dx9",
		"-bc", "d",
		"-pow2",
		"-y",
		"-o", folder_path,
		temp_path
	]
	subprocess.run(args, check=False)

	# Clean up the temporary PNG file
	os.remove(temp_path)

def create_mesh(mesh: bpy.types.Mesh, mesh_index: int, model_name: str, folder_path: str) -> BattleforgeMesh:
	'''Create a Battleforge Mesh from a Blender Mesh Object.'''
	mesh.data.calc_tangents()
	new_mesh = BattleforgeMesh()
	new_mesh.vertex_count = len(mesh.data.vertices)
	new_mesh.face_count = len(mesh.data.polygons)
	new_mesh.faces = []

	new_mesh.mesh_count = 2
	new_mesh.mesh_data = []

	_mesh_0_data = MeshData()
	_mesh_0_data.vertices = [Vertex() for _ in range(new_mesh.vertex_count)]
	_mesh_0_data.revision = 133121
	_mesh_0_data.vertex_size = 32

	_mesh_1_data = MeshData()
	_mesh_1_data.vertices = [Vertex() for _ in range(new_mesh.vertex_count)]
	_mesh_1_data.revision = 12288
	_mesh_1_data.vertex_size = 24

	for _face in mesh.data.polygons:
		new_face = Face()
		new_face.indices = []

		for index in _face.loop_indices:
			vertex = mesh.data.loops[index]
			position = mesh.data.vertices[vertex.vertex_index].co
			normal = vertex.normal
			#TODO: Maybe we need to flip the Y value of the Normal as we convert from OpenGL to DirectX
			uv = mesh.data.uv_layers.active.data[index].uv.copy()
			uv.y = -uv.y
			_mesh_0_data.vertices[vertex.vertex_index] = Vertex(position=position, normal=normal, texture=uv)

			if new_mesh.mesh_count > 1:
				tangent = vertex.tangent
				bitangent = vertex.bitangent_sign * normal.cross(tangent)
				# Switch X and Y as the Tangent is flipped
				tangent = Vector((tangent.y, tangent.x, tangent.z))
				_mesh_1_data.vertices[vertex.vertex_index] = Vertex(tangent=tangent, bitangent=bitangent)

			new_face.indices.append(vertex.vertex_index)

		new_mesh.faces.append(new_face)

	new_mesh.mesh_data.append(_mesh_0_data)
	new_mesh.mesh_data.append(_mesh_1_data)

	# We need to investigate the Bounding Box further, as it seems to be wrong
	new_mesh.bounding_box_lower_left_corner, new_mesh.bounding_box_upper_right_corner = get_bb(mesh)
	new_mesh.material_id = 25702
	# Node Group for Access the Data
	mesh_material: bpy.types.Material = mesh.material_slots[0].material
	material_nodes: List[bpy.types.Node] = mesh_material.node_tree.nodes
	# Find the DRS Node
	color_map = None
	metallic_map = None
	roughness_map = None
	emission_map = None
	normal_map = None
	scratch_map = None
	distortion_map = None
	refraction_map = None
	refraction_color = None
	flu_map = None

	for node in material_nodes:
		if node.type == "GROUP":
			if node.node_tree.name.find("DRS") != -1:
				color_map = node.inputs[0]
				# ColorAlpha = Node.inputs[1] # We don't need this
				metallic_map = node.inputs[2]
				roughness_map = node.inputs[3]
				emission_map = node.inputs[4]
				normal_map = node.inputs[5]
				# scratch_map = Node.inputs[6]
				# distortion_map = Node.inputs[7]
				# refraction_map = Node.inputs[8]
				# RefractionAlpha = Node.inputs[9] # We don't need this
				# refraction_color = Node.inputs[10]
				# flu_map = Node.inputs[11]
				# FluAlpha = Node.inputs[12] # We don't need this
				break

	if flu_map is None or flu_map.is_linked is False:
		# -86061055: no MaterialStuff, no Fluid, no String, no LOD
		new_mesh.material_parameters = -86061055
	else:
		# -86061050: All Materials
		new_mesh.material_parameters = -86061050
		new_mesh.material_stuff = 0
		# Level of Detail
		new_mesh.level_of_detail = LevelOfDetail() # We don't need to update the LOD
		# Empty String
		new_mesh.empty_string = EmptyString() # We don't need to update the Empty String
		# Flow
		new_mesh.flow = Flow() # Maybe later we can add some flow data in blender

	# Individual Material Parameters depending on the MaterialID:
	new_mesh.bool_parameter = 0
	bool_param_bit_flag = 0
	# Textures
	new_mesh.textures = Textures()

	# Check if the Color Map is set
	if not set_color_map(color_map, new_mesh, mesh_index, model_name, folder_path):
		return None

	# Check if the Normal Map is set
	set_normal_map(normal_map, new_mesh, mesh_index, model_name, folder_path, bool_param_bit_flag)

	# Check if the Metallic, Roughness and Emission Map is set
	set_metallic_roughness_emission_map(metallic_map, roughness_map, emission_map, new_mesh, mesh_index, model_name, folder_path, bool_param_bit_flag)

	# Set the Bool Parameter by a bin -> dec conversion
	new_mesh.bool_parameter = int(str(bool_param_bit_flag), 2)

	# Refraction
	refraction = Refraction()
	refraction.length = 1
	# refraction.rgb = list(refraction_color.default_value)[:3] # Default is 0, 0, 0 # TODO: We need to get the color from the Node
	refraction.rgb = [0, 0, 0]
	new_mesh.refraction = refraction

	# Materials
	new_mesh.materials = Materials() # Almost no material data is used in the game, so we set it to defaults

	return new_mesh

def create_cdsp_mesh_file(meshes_collection: bpy.types.Collection, model_name: str, filepath: str) -> CDspMeshFile:
	'''Create a CDspMeshFile from a Collection of Meshes.'''
	_cdsp_meshfile = CDspMeshFile()
	_cdsp_meshfile.mesh_count = 0

	for mesh in meshes_collection.objects:
		if mesh.type == "MESH":
			_mesh = create_mesh(mesh, _cdsp_meshfile.mesh_count, model_name, filepath)
			if _mesh is None:
				return
			_cdsp_meshfile.meshes.append(_mesh)
			_cdsp_meshfile.mesh_count += 1

	_cdsp_meshfile.bounding_box_lower_left_corner = Vector3(0, 0, 0)
	_cdsp_meshfile.bounding_box_upper_right_corner = Vector3(0, 0, 0)

	for _mesh in _cdsp_meshfile.meshes:
		_cdsp_meshfile.bounding_box_lower_left_corner.x = min(_cdsp_meshfile.bounding_box_lower_left_corner.x, _mesh.bounding_box_lower_left_corner.x)
		_cdsp_meshfile.bounding_box_lower_left_corner.y = min(_cdsp_meshfile.bounding_box_lower_left_corner.y, _mesh.bounding_box_lower_left_corner.y)
		_cdsp_meshfile.bounding_box_lower_left_corner.z = min(_cdsp_meshfile.bounding_box_lower_left_corner.z, _mesh.bounding_box_lower_left_corner.z)

		_cdsp_meshfile.bounding_box_upper_right_corner.x = max(_cdsp_meshfile.bounding_box_upper_right_corner.x, _mesh.bounding_box_upper_right_corner.x)
		_cdsp_meshfile.bounding_box_upper_right_corner.y = max(_cdsp_meshfile.bounding_box_upper_right_corner.y, _mesh.bounding_box_upper_right_corner.y)
		_cdsp_meshfile.bounding_box_upper_right_corner.z = max(_cdsp_meshfile.bounding_box_upper_right_corner.z, _mesh.bounding_box_upper_right_corner.z)

	return _cdsp_meshfile

def create_box_shape(box: bpy.types.Object) -> BoxShape:
	"""Create a BoxShape from a Blender Object previously created by create_collision_shape_box_object."""
	# Instantiate the new BoxShape and its sub-components.
	_box_shape = BoxShape()
	_box_shape.coord_system = CMatCoordinateSystem()
	_box_shape.geo_aabox = CGeoAABox()

	# Extract the transformation from the object's world matrix.
	# The rotation part (a 3x3 matrix) and the translation (a vector) directly correspond
	# to the coordinate system used during creation.
	world_matrix = box.matrix_world
	rotation = world_matrix.to_3x3()
	translation = world_matrix.to_translation()

	# Set the coordinate system position.
	_box_shape.coord_system.position = Vector3(translation.x, translation.y, translation.z)
	# Flatten the 3x3 rotation matrix into a row-major list of 9 floats.
	_box_shape.coord_system.matrix.matrix = [
		rotation[0][0], rotation[0][1], rotation[0][2],
		rotation[1][0], rotation[1][1], rotation[1][2],
		rotation[2][0], rotation[2][1], rotation[2][2]
	]

	# Compute the axis aligned bounding box from the object's mesh vertices (in local space).
	# These vertices were created directly from the original AABox corners.
	vertices = [v.co for v in box.data.vertices]
	if not vertices:
		raise ValueError("The object has no vertices to compute a bounding box from.")

	# Determine the minimum and maximum extents along each axis.
	min_x = min(v.x for v in vertices)
	min_y = min(v.y for v in vertices)
	min_z = min(v.z for v in vertices)
	max_x = max(v.x for v in vertices)
	max_y = max(v.y for v in vertices)
	max_z = max(v.z for v in vertices)

	_box_shape.geo_aabox.lower_left_corner = Vector3(min_x, min_y, min_z)
	_box_shape.geo_aabox.upper_right_corner = Vector3(max_x, max_y, max_z)

	return _box_shape

def create_collision_shape(meshes_collection: bpy.types.Collection) -> CollisionShape:
	'''Create a Collision Shape from a Collection of Collision Shapes.'''
	_collision_shape = CollisionShape()
	collision_collection = get_collision_collection(meshes_collection)
	for child in collision_collection.children:
		if child.name.startswith("Boxes_Collection"):
			if len(child.objects) > 0:
				for box in child.objects:
					if box.type == "MESH":
						_collision_shape.box_count += 1
						_collision_shape.boxes.append(create_box_shape(box))
		if child.name.startswith("Spheres_Collection"):
			if len(child.objects) > 0:
				for sphere in child.objects:
					if sphere.type == "MESH":
						_collision_shape.sphere_count += 1
						_collision_shape.spheres.append(create_sphere_shape(sphere))
		if child.name.startswith("Cylinders_Collection"):
			if len(child.objects) > 0:
				for cylinder in child.objects:
					if cylinder.type == "MESH":
						_collision_shape.cylinder_count += 1
						_collision_shape.cylinders.append(create_cylinder_shape(cylinder))
	return _collision_shape

def copy_objects(from_col: bpy.types.Collection, to_col: bpy.types.Collection, linked: bool, dupe_lut: dict[bpy.types.Object, bpy.types.Object]) -> None:
	for o in from_col.objects:
		dupe = o.copy()
		if not linked and o.data:
			dupe.data = dupe.data.copy()
		to_col.objects.link(dupe)
		dupe_lut[o] = dupe

def update_armature_references(dupe_lut: dict[bpy.types.Object, bpy.types.Object]) -> None:
	for original, copy in dupe_lut.items():
		if copy and copy.type == 'MESH':
			for modifier in copy.modifiers:
				if modifier.type == 'ARMATURE' and modifier.object in dupe_lut:
					# Update the modifier's armature reference to the copied armature
					modifier.object = dupe_lut[modifier.object]

def copy(parent: bpy.types.Collection, collection: bpy.types.Collection, linked: bool = False) -> bpy.types.Collection:
	dupe_lut = defaultdict(lambda: None)

	def _copy(parent, collection, linked=False) -> bpy.types.Collection:
		cc = bpy.data.collections.new(collection.name)
		copy_objects(collection, cc, linked, dupe_lut)

		for c in collection.children:
			_copy(cc, c, linked)

		parent.children.link(cc)
		return cc

	# Create the copied collection hierarchy
	new_coll = _copy(parent, collection, linked)

	# Set the parent for each copied object based on the original hierarchy
	for o, dupe in tuple(dupe_lut.items()):
		parent = dupe_lut[o.parent]
		if parent:
			dupe.parent = parent

	# Update armature modifiers in copied objects to reference copied armatures
	update_armature_references(dupe_lut)

	return new_coll

def verify_collections(source_collection: bpy.types.Collection, model_type: str) -> bool:
	# First Check if the selected Collection is a valid Collection by name DRSModel_...
	if not source_collection.name.startswith("DRSModel_"):
		show_message_box("The selected Collection is not a valid Collection. Please select a Collection with the name DRSModel_...", "Error", "ERROR")
		return False

	# Check if the Collection has the correct Children
	nodes = InformationIndices[model_type]
	for node in nodes:
		if node == "CGeoMesh" or node == "CGeoOBBTree" or node == "CDspJointMap" or node == "CDspMeshFile":
			mesh_collection = get_meshes_collection(source_collection)

			if mesh_collection is None:
				show_message_box("No Meshes Collection found!", "Error", "ERROR")
				return False

			# Check if the Meshes Collection has Meshes
			if len(mesh_collection.objects) == 0:
				show_message_box("No Meshes found in the Meshes Collection!", "Error", "ERROR")
				return False

			# Check if every mesh has a material
			for mesh in mesh_collection.objects:
				if mesh.type == "MESH":
					if len(mesh.material_slots) == 0:
						show_message_box("No Material found for Mesh " + mesh.name + "!", "Error", "ERROR")
						return False
					else:
						# print all the nodes with names and types we have in the material
						material_nodes = mesh.material_slots[0].material.node_tree.nodes
						for node in material_nodes:
							if node.type == "Group" and node.label != "DRSMaterial":
								show_message_box(f"Node {node.name} is not a DRSMaterial node!", "Error", "ERROR")
								return False
		if node == "collisionShape":
			collision_collection = get_collision_collection(source_collection)

			if collision_collection is None:
				show_message_box("No Collision Collection found! But is required for a model with collision shapes!", "Error", "ERROR")
				return False

			# Get Boxes, Spheres and Cylinders Collections from the Collision Collection
			boxes_collection = None
			spheres_collection = None
			cylinders_collection = None
			for child in collision_collection.children:
				if child.name.startswith("Boxes_Collection"):
					boxes_collection = child
				if child.name.startswith("Spheres_Collection"):
					spheres_collection = child
				if child.name.startswith("Cylinders_Collection"):
					cylinders_collection = child
			# Check if at least one of the Collision Shapes is present
			if boxes_collection is None and spheres_collection is None and cylinders_collection is None:
				show_message_box("No Collision Shapes found in the Collision Collection!", "Error", "ERROR")
				return False
			# Check if at least one of the Collision Shapes has Collision Shapes (mesh)
			found_collision_shapes = False
			for collision_shape in [boxes_collection, spheres_collection, cylinders_collection]:
				if collision_shape is not None and len(collision_shape.objects) > 0:
					found_collision_shapes = True
					break
			if not found_collision_shapes:
				show_message_box("No Collision Shapes found in the Collision Collection!", "Error", "ERROR")
				return False

	return True

def get_meshes_collection(source_collection: bpy.types.Collection) -> bpy.types.Collection:
	for collection in source_collection.children:
		if collection.name.startswith("Meshes_Collection"):
			return collection
	return None

def get_collision_collection(source_collection: bpy.types.Collection) -> bpy.types.Collection:
	for collection in source_collection.children:
		if collection.name.startswith("CollisionShapes_Collection"):
			return collection
	return None

def abort(keep_debug_collections: bool, source_collection_copy: bpy.types.Collection) -> dict:
	if not keep_debug_collections and source_collection_copy is not None:
		bpy.data.collections.remove(source_collection_copy)

	show_message_box(final=True)

	return {"CANCELLED"}

# def test_export(context: bpy.types.Context, filepath: str, use_apply_transform: bool, split_mesh_by_uv_islands: bool, keep_debug_collections: bool, export_animation: bool, forward_direction: str, up_direction: str, automatic_naming: bool, temporary_file_path: str, model_type: str) -> dict:
	# original_file: DRS = DRS().read(file_name=temporary_file_path)
	# file_name = os.path.basename(filepath).split(".")[0] + ".drs"
	# new_drs_file: DRS = DRS(model_type=model_type)
	# new_drs_file.push_node_infos("CGeoMesh", original_file.cgeo_mesh)
	# new_drs_file.push_node_infos("CGeoOBBTree", original_file.cgeo_obb_tree)
	# new_drs_file.push_node_infos("CDspJointMap", original_file.cdsp_joint_map)
	# new_drs_file.push_node_infos("CDspMeshFile", original_file.cdsp_mesh_file)
	# new_drs_file.push_node_infos("DrwResourceMeta", original_file.drw_resource_meta)
	# new_drs_file.push_node_infos("CDrwLocatorList", original_file.cdrw_locator_list)
	# new_drs_file.push_node_infos("CSkSkeleton", original_file.csk_skeleton)
	# new_drs_file.push_node_infos("CSkSkinInfo", original_file.csk_skin_info)
	# new_drs_file.push_node_infos("AnimationSet", original_file.animation_set)
	# new_drs_file.push_node_infos("AnimationTimings", original_file.animation_timings)
	# new_drs_file.push_node_infos("EffectSet", original_file.effect_set)
	# new_drs_file.update_offsets()
	# new_drs_file.save(filepath)

# def save_drs(context: bpy.types.Context, filepath: str, use_apply_transform: bool, split_mesh_by_uv_islands: bool, keep_debug_collections: bool, export_animation: bool, forward_direction: str, up_direction: str, automatic_naming: bool, model_type: str, temporary_file_path: str = None) -> dict:
	# # Reset messages
	# global messages
	# messages = []
	# # The Collection we want to Export needs to be selected, so we search for it
	# source_collection = bpy.context.view_layer.active_layer_collection.collection

	# # verify the collection
	# if not verify_collections(source_collection):
	# 	print("Collection Verification failed!")
	# 	return abort(keep_debug_collections, None)

	# # We dont want to modify the original Collection so we create a copy
	# source_collection_copy = copy(context.scene.collection, source_collection)
	# source_collection_copy.name += ".copy"

	# # Get the Meshes Collection
	# meshes_collection = get_meshes_collection(source_collection_copy)

	# if meshes_collection is None:
	# 	show_message_box("No Meshes Collection found!", "Error", "ERROR")
	# 	print("No Meshes Collection found!")
	# 	return abort(keep_debug_collections, source_collection_copy)

	# # Be sure that there are only triangles in the Meshes
	# triangulate(source_collection_copy)

	# # Verify the Models
	# if not verify_mesh_vertex_count(meshes_collection):
	# 	print("Model Verification failed!")
	# 	return abort(keep_debug_collections, source_collection_copy)

	# # Split the Meshes by UV Islands
	# if split_mesh_by_uv_islands:
	# 	split_meshes_by_uv_islands(meshes_collection)

	# # Check if there is an Armature in the Collection
	# # armature_object = None
	# # if export_animation:
	# # 	for obj in source_collection_copy.objects:
	# # 		if obj.type == "ARMATURE":
	# # 			armature_object = obj
	# # 			break
	# # 	if armature_object is None:
	# # 		show_message_box("No Armature found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature to the Collection.", "Error", "ERROR")
	# # 		print("No Armature found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature to the Collection.")
	# # 		return abort(keep_debug_collections, source_collection_copy)

	# # First we need to set the origin of all meshes to the center of the scene
	# set_origin_to_world_origin(meshes_collection)

	# if use_apply_transform:
	# 	# Apply the transformations to the Collection
	# 	m = axis_conversion(
	#   		from_forward=forward_direction,
	# 		from_up=up_direction,
	# 		to_forward='-Z',
	# 		to_up='Y').to_4x4()

	# 	for obj in source_collection_copy.all_objects:
	# 		if obj.type == "ARMATURE":
	# 			obj.matrix_world = m @ obj.matrix_world
	# 			# mirror around X
	# 			obj.scale.x *= -1

	# # Create an empty DRS File with the Model Type
	# new_drs_file: DRS = DRS(model_type=model_type)

	# # Name of the Model
	# model_name = ""
	# folder_path = os.path.dirname(filepath)
	# if automatic_naming:
	# 	model_name = model_type + "_" + os.path.basename(filepath).split(".")[0]
	# else:
	# 	# model name from the file path
	# 	model_name = os.path.basename(filepath).split(".")[0]

	# # Create a unified mesh from all meshes
	# unified_mesh = create_unified_mesh(meshes_collection)

	# # Depening on the Model Type we need to create different Nodes
	# nodes = InformationIndices[model_type]
	# for node in nodes:
	# 	if node == "CGeoMesh":
	#         # Needs an excisting Mesh (a Collection named CDspMeshFile in Blender)
	# 		new_drs_file.cgeo_mesh = create_cgeo_mesh(unified_mesh)
	# 		new_drs_file.push_node_infos("CGeoMesh", new_drs_file.cgeo_mesh)
	# 	elif node == "CGeoOBBTree":
	#         # Needs an excisting Mesh (a Collection named CDspMeshFile in Blender)
	# 		new_drs_file.cgeo_obb_tree = create_cgeo_obb_tree(unified_mesh)
	# 		new_drs_file.push_node_infos("CGeoOBBTree", new_drs_file.cgeo_obb_tree)
	# 	elif node == "CDspJointMap":
	#         # Needs an excisting Mesh (a Collection named CDspMeshFile in Blender)
	# 		new_drs_file.cdsp_joint_map, bone_map = create_cdsp_joint_map(meshes_collection)
	# 		new_drs_file.push_node_infos("CDspJointMap", new_drs_file.cdsp_joint_map)
	# 	elif node == "CDspMeshFile":
	#         # Needs an excisting Mesh (a Collection named CDspMeshFile in Blender)
	# 		cdsp_mesh_file = create_cdsp_mesh_file(meshes_collection, model_name, folder_path)
	# 		if cdsp_mesh_file is None:
	# 			return abort(keep_debug_collections, source_collection_copy)
	# 		new_drs_file.cdsp_mesh_file = cdsp_mesh_file
	# 		new_drs_file.push_node_infos("CDspMeshFile", new_drs_file.cdsp_mesh_file)
	# 	elif node == "DrwResourceMeta":
	#         # Empty Node
	# 		new_drs_file.drw_resource_meta = DrwResourceMeta()
	# 		new_drs_file.push_node_infos("DrwResourceMeta", new_drs_file.drw_resource_meta)

	# new_drs_file.update_offsets()

	# # Export the DRS File to folder path with the model name
	# new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))

	# # Remove the copied Collection
	# if not keep_debug_collections:
	# 	bpy.data.collections.remove(source_collection_copy)

	# # Show the Messages
	# show_message_box(final=True)
	# return {"FINISHED"}

def save_drs(context: bpy.types.Context, filepath: str, use_apply_transform: bool, split_mesh_by_uv_islands: bool, keep_debug_collections: bool, export_animation: bool, forward_direction: str, up_direction: str, automatic_naming: bool, model_type: str, temporary_file_path: str = None) -> dict:
	global messages
	messages = []

	# === PRE-VALIDITY CHECKS =================================================
	# Ensure active collection is valid
	source_collection = bpy.context.view_layer.active_layer_collection.collection
	if not verify_collections(source_collection, model_type):
		return abort(keep_debug_collections, None)

	# Create a safe copy of the collection for export
	try:
		source_collection_copy = copy(context.scene.collection, source_collection)
		source_collection_copy.name += ".copy"
	except Exception as e:
		show_message_box(f"Failed to duplicate collection: {e}. Type {type(e)}", "Collection Copy Error", 'ERROR')
		return abort(keep_debug_collections, None)

	# === MESH PREPARATION =====================================================
	meshes_collection = get_meshes_collection(source_collection_copy)
	try:
		triangulate(source_collection_copy)
	except Exception as e:
		show_message_box(f"Error during triangulation: {e}. Type {type(e)}", "Triangulation Error", 'ERROR')
		return abort(keep_debug_collections, source_collection_copy)

	if not verify_mesh_vertex_count(meshes_collection):
		show_message_box("Model verification failed: one or more meshes are invalid or exceed vertex limits.", "Model Verification Error", 'ERROR')
		return abort(keep_debug_collections, source_collection_copy)

	if split_mesh_by_uv_islands:
		try:
			split_meshes_by_uv_islands(meshes_collection)
		except Exception as e:
			show_message_box(f"Error splitting meshes by UV islands: {e}", "UV Island Error", 'ERROR')
			return abort(keep_debug_collections, source_collection_copy)

	# Check if there is an Armature in the Collection
	armature_object = None
	if export_animation:
		for obj in source_collection_copy.objects:
			if obj.type == "ARMATURE":
				armature_object = obj
				break
		if armature_object is None:
			show_message_box("No Armature found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature to the Collection.", "Error", "ERROR")
			print("No Armature found in the Collection. If this is a skinned model, the animation export will fail. Please add an Armature to the Collection.")
			return abort(keep_debug_collections, source_collection_copy)

	try:
		set_origin_to_world_origin(meshes_collection)
	except Exception as e:
		show_message_box(f"Error setting origin for meshes: {e}. Type {type(e)}", "Origin Error", 'ERROR')
		return abort(keep_debug_collections, source_collection_copy)

	# === APPLY TRANSFORMATIONS =================================================
	if use_apply_transform:
		try:
			# Compute the conversion matrix.
			m = axis_conversion(
				from_forward=forward_direction,
				from_up=up_direction,
				to_forward='-Z',
				to_up='Y'
			).to_4x4()

			# Reverse the negative Y scale on non-armature objects.
			# (On import you set obj.scale = (1, -1, 1); here, multiplying Y by -1 resets it to (1, 1, 1).)
			for obj in source_collection_copy.all_objects:
				if obj.type != "ARMATURE":
					obj.scale.y *= -1

			# First update every object's matrix_world with the conversion matrix.
			# (This updates the visual transform.)
			for obj in source_collection_copy.all_objects:
				obj.matrix_world = m @ obj.matrix_world
				# Optionally handle mirror for armatures.
				if armature_object and obj.type == "ARMATURE":
					obj.scale.x *= -1  # mirror around X-axis

			# Now "bake" the transformation into each mesh's data.
			# Deselect everything.
			bpy.ops.object.select_all(action='DESELECT')
			# Gather all mesh objects from the temporary collection.
			mesh_objects = [obj for obj in source_collection_copy.all_objects if obj.type == 'MESH']
			# Select all mesh objects.
			for obj in mesh_objects:
				obj.select_set(True)
			# Set an active object (required by the operator).
			if mesh_objects:
				bpy.context.view_layer.objects.active = mesh_objects[0]
				# Apply location, rotation, and scale.
				bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
				# Optionally, deselect afterwards.
				bpy.ops.object.select_all(action='DESELECT')

		except Exception as e:
			show_message_box(f"Error applying transformations: {e}", "Transformation Error", 'ERROR')
			return abort(keep_debug_collections, source_collection_copy)

	# === CREATE DRS STRUCTURE =================================================
	folder_path = os.path.dirname(filepath)
	model_name = (model_type + "_" + os.path.basename(filepath).split(".")[0]) if automatic_naming else os.path.basename(filepath).split(".")[0]

	new_drs_file: DRS = DRS(model_type=model_type)
	try:
		unified_mesh = create_unified_mesh(meshes_collection)
	except Exception as e:
		show_message_box(f"Error creating unified mesh: {e}. Type {type(e)}", "Unified Mesh Error", 'ERROR')
		return abort(keep_debug_collections, source_collection_copy)

	nodes = InformationIndices[model_type]
	for node in nodes:
		if node == "CGeoMesh":
			new_drs_file.cgeo_mesh = create_cgeo_mesh(unified_mesh)
			new_drs_file.push_node_infos("CGeoMesh", new_drs_file.cgeo_mesh)
		elif node == "CGeoOBBTree":
			new_drs_file.cgeo_obb_tree = create_cgeo_obb_tree(unified_mesh)
			new_drs_file.push_node_infos("CGeoOBBTree", new_drs_file.cgeo_obb_tree)
		elif node == "CDspJointMap":
			new_drs_file.cdsp_joint_map, bone_map = create_cdsp_joint_map(meshes_collection)
			new_drs_file.push_node_infos("CDspJointMap", new_drs_file.cdsp_joint_map)
		elif node == "CDspMeshFile":
			cdsp_mesh_file = create_cdsp_mesh_file(meshes_collection, model_name, folder_path)
			if cdsp_mesh_file is None:
				show_message_box("Failed to create CDspMeshFile.", "Mesh File Error", 'ERROR')
				return abort(keep_debug_collections, source_collection_copy)
			new_drs_file.cdsp_mesh_file = cdsp_mesh_file
			new_drs_file.push_node_infos("CDspMeshFile", new_drs_file.cdsp_mesh_file)
		elif node == "DrwResourceMeta":
			new_drs_file.drw_resource_meta = DrwResourceMeta()
			new_drs_file.push_node_infos("DrwResourceMeta", new_drs_file.drw_resource_meta)
		elif node == "collisionShape":
			new_drs_file.collision_shape = create_collision_shape(source_collection_copy)
			new_drs_file.push_node_infos("collisionShape", new_drs_file.collision_shape)

	new_drs_file.update_offsets()

	# === SAVE THE DRS FILE ====================================================
	try:
		new_drs_file.save(os.path.join(folder_path, model_name + ".drs"))
	except Exception as e:
		show_message_box(f"Error saving DRS file: {e}. Type {type(e)}", "Save Error", 'ERROR')
		print(f"Error saving DRS file: {e}")
		return abort(keep_debug_collections, source_collection_copy)

	# === CLEANUP & FINALIZE ===================================================
	if not keep_debug_collections:
		bpy.data.collections.remove(source_collection_copy)

	show_message_box("Export completed successfully.", "Export Complete", 'INFO')
	return {"FINISHED"}

def create_new_bf_scene(scene_type: str, collision_support: bool):
	"""
	Create the new Battleforge scene structure with the following hierarchy:
	  - DRSModel_<scene_type>
		 ├── Meshes_Collection
		 └── CollisionShapes_Collection (if collision_support is True)
			  ├── Boxes_Collection
			  ├── Spheres_Collection
			  └── Cylinders_Collection
	"""

	# Create the main collection with a name based on the scene type.
	main_collection_name = f"DRSModel_{scene_type}_CHANGENAME"
	main_collection = bpy.data.collections.new(main_collection_name)
	bpy.context.scene.collection.children.link(main_collection)

	# Create and link the Meshes_Collection.
	meshes_collection = bpy.data.collections.new("Meshes_Collection")
	main_collection.children.link(meshes_collection)

	if collision_support:
		# Create the CollisionShapes_Collection and its subcollections.
		collision_collection = bpy.data.collections.new("CollisionShapes_Collection")
		main_collection.children.link(collision_collection)

		boxes_collection = bpy.data.collections.new("Boxes_Collection")
		collision_collection.children.link(boxes_collection)

		spheres_collection = bpy.data.collections.new("Spheres_Collection")
		collision_collection.children.link(spheres_collection)

		cylinders_collection = bpy.data.collections.new("Cylinders_Collection")
		collision_collection.children.link(cylinders_collection)

	list_pathes = [
		("Battleforge Assets", resource_dir + "/assets"),
	]

	offset = len(bpy.context.preferences.filepaths.asset_libraries)
	index = offset

	for path in list_pathes:
		if offset == 0:
			# Add them without any Checks
			bpy.ops.preferences.asset_library_add(directory = path[1])
			# give a name to your asset dir
			bpy.context.preferences.filepaths.asset_libraries[index].name = path[0]
			index += 1
			print("Added Asset Library: " + path[0])
		else:
			for i in range(len(bpy.context.preferences.filepaths.asset_libraries)):
				user_path_name = bpy.context.preferences.filepaths.asset_libraries[i].name

				if user_path_name != path[0]:
					bpy.ops.preferences.asset_library_add(directory = path[1])
					# give a name to your asset dir
					bpy.context.preferences.filepaths.asset_libraries[index].name = path[0]
					index += 1
					print("Added Asset Library: " + path[0])
				else:
					print("Asset Library already exists: " + path[0])
# TODO: Always improt to Main Scene
# TODO: Only one time import Collision Meshes
# TODO: Check why Vertices in CGeoMesh are not the same as in CDspMeshFile
