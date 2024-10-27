import os
from math import radians
import time
import bmesh
import bpy
from mathutils import Matrix, Vector, Quaternion

from .drs_definitions import DRS, CDspMeshFile, CylinderShape, Face, BattleforgeMesh, DRSBone, CSkSkeleton, Bone, BoneVertex, BoxShape, SphereShape, CSkSkinInfo, CGeoMesh, BoneWeight
from .drs_material import DRSMaterial
from .ska_definitions import SKA, SKAKeyframe

def debug_drs_file(filepath: str) -> 'DRS':
	# base_name = os.path.basename(filepath).split(".")[0]
	# dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)
	return drs_file

def apply_transformations(obj: bpy.types.Object, global_matrix: Matrix, apply_transform: bool) -> None:
	if apply_transform:
		obj.matrix_world = global_matrix @ obj.matrix_world
		obj.scale = (1, -1, 1)

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

# def set_keyframe_tangent(keyframe_point: bpy.types.Keyframe, tan_value: float) -> None:
# 	if tan_value is None:
# 		return

# 	# Calculate handle positions based on tan_value
# 	frame = keyframe_point.co[0]
# 	value = keyframe_point.co[1]
# 	handle_offset = 0.2  # Adjust this calculation based on how tan_value relates to the slope

# 	# Left handle
# 	keyframe_point.handle_left_type = 'FREE'
# 	keyframe_point.handle_left = (frame - 0.1, value - handle_offset * tan_value)

# 	# Right handle
# 	keyframe_point.handle_right_type = 'FREE'
# 	keyframe_point.handle_right = (frame + 0.1, value + handle_offset * tan_value)

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
			print(f"Bone with name {bone.name} not found in armature")

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

def load_drs(context: bpy.types.Context, filepath="", apply_transform=True, global_matrix=Matrix.Identity(4), import_collision_shape=False, fps_selection=30) -> None:
	# Load time measurement
	start_time = time.time()
	base_name = os.path.basename(filepath).split(".")[0]
	dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)

	source_collection: bpy.types.Collection = bpy.data.collections.new("DRSModel_" + base_name + "_Type")
	context.collection.children.link(source_collection)

	# Scene Collection
	# └── ModelName_Collection
	# 	├── Armature (if present)
	# 	│   ├── Animations (stored as action groups)
	# 	├── Meshes_Collection
	# 	│   ├── Mesh_01
	# 	│   |   ├── Material_01
	# 	│   └── Mesh_N
	# 	│       └── Material_N

	if drs_file.csk_skeleton is not None:
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
		if drs_file.animation_set is not None:
			# Apply the Transformations to the Armature Object
			apply_transformations(armature_object, global_matrix, apply_transform)

	if drs_file.csk_skin_info is not None:
		# Create the Bone Weights
		bone_weights = create_bone_weights(drs_file.cdsp_mesh_file, drs_file.csk_skin_info, drs_file.cgeo_mesh)

	# Create a Mesh Collection to store the Mesh Objects
	mesh_collection: bpy.types.Collection = bpy.data.collections.new("Meshes_Collection")
	source_collection.children.link(mesh_collection)
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
		# Create the Material Data
		material_data = create_material(dir_name, mesh_index, drs_file.cdsp_mesh_file.meshes[mesh_index])
		# Assign the Material to the Mesh
		mesh_data.materials.append(material_data)
		# Link the Mesh Object to the Source Collection
		mesh_collection.objects.link(mesh_object)

	if drs_file.collision_shape is not None and import_collision_shape:
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

	if drs_file.animation_set is not None and armature_object is not None:
		# Set the FPS for the Animation
		bpy.context.scene.render.fps = int(fps_selection)
		bpy.ops.object.mode_set(mode='POSE')
		for animation_key in drs_file.animation_set.mode_animation_keys:
			for variant in animation_key.animation_set_variants:
				ska_file: SKA = SKA().read(os.path.join(dir_name, variant.file))
				create_animation(ska_file, armature_object, bone_list, variant.file)

	# Return to the Object Mode
	bpy.ops.object.mode_set(mode='OBJECT')
	# Print the Time Measurement
	print(f"Time to load DRS: {time.time() - start_time}")

# Debug the file by loading it, write a main
# if __name__ == "__main__":
# 	# Load ALL DRS files in given directory
# 	# Create an array sorted by the amount of bones
# 	# check how many duplicate bones the models have and create a ranking, like: only uniques, 2 duplicates, etc. with a counter
# 	dir = "D:\\Games\\Skylords Reborn\\Mods\\Unpack\\bf1\\gfx\\units"
# 	## Load all DRS files in the subdirectories, not main
# 	files = []
# 	for root, dirs, file in os.walk(dir):
# 		for f in file:
# 			if f.endswith(".drs"):
# 				# Append full path
# 				files.append(os.path.relpath(os.path.join(root, f), dir))
	
# 	models_by_bone_count = {}
# 	models_by_duplicate_bones = {}

# 	for file in files:
# 		print(f"Loading: {file}")
# 		drs_file = debug_drs_file(os.path.join(dir, file))
# 		if drs_file.csk_skeleton is not None:

# 			# Every Bone has a 4x4 Matrix. Check if there are bones withing the model with the same matrix. If so add the file name to the list of duplicate counts.
# 			# Compare every matrix with every other matrix
# 			duplicate_bones = 0
# 			cskskeleton: CSkSkeleton = drs_file.csk_skeleton
# 			for i in range(drs_file.csk_skeleton.bone_matrix_count):
# 				matrix_a = cskskeleton.bone_matrices[i].bone_vertices
# 				# Compare the bone matrix with every other bone matrix, every comaprisonr educes the total amount of comparisons by 1
# 				for j in range(i + 1, drs_file.csk_skeleton.bone_matrix_count):
# 					matrix_b = cskskeleton.bone_matrices[j].bone_vertices
# 					# Compare the 4x4 matrix
# 					if matrix_a[0].position.xyz == matrix_b[0].position.xyz and matrix_a[1].position.xyz == matrix_b[1].position.xyz and matrix_a[2].position.xyz == matrix_b[2].position.xyz and matrix_a[3].position.xyz == matrix_b[3].position.xyz:
# 						duplicate_bones += 1
# 						# Print the Bone Names, find by identifiert in the drs_file.csk_skeleton.bones array
# 						bone_a = next((bone for bone in drs_file.csk_skeleton.bones if bone.identifier == i), None)
# 						bone_b = next((bone for bone in drs_file.csk_skeleton.bones if bone.identifier == j), None)
# 						print(f"Duplicate Bones: {bone_a.name} and {bone_b.name}")
# 					# if same is True:
# 					# 	duplicate_bones += 1
# 					# 	print(f"Duplicate Bones: {i} and {j}")
# 					# 	print(f"Matrix A: {matrix_a[0].position.xyz}, {matrix_a[1].position.xyz}, {matrix_a[2].position.xyz}, {matrix_a[3].position.xyz}")
# 					# 	print(f"Matrix B: {matrix_b[0].position.xyz}, {matrix_b[1].position.xyz}, {matrix_b[2].position.xyz}, {matrix_b[3].position.xyz}")
# 					# 	print(matrix_a[3].position.xyz == matrix_b[3].position.xyz)

# 			if duplicate_bones not in models_by_duplicate_bones:
# 				models_by_duplicate_bones[duplicate_bones] = []

# 			models_by_duplicate_bones[duplicate_bones].append(file)
# 			# Now we need to check every corresponding SKA File if the bones have different animation data

# 	print("DONE")
 

# 1
# 'skel_dummy_l\\unit_dummy_l_fire.drs'
# 'skel_scorpion\\unit_skitterer.drs'
# 2
# 'skel_jellyfish\\unit_stonekin_skyslayer.drs'
# 'skel_scorpion\\unit_abyssal_warder.drs'