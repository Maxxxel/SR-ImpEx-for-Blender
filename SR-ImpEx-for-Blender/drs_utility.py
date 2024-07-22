import os
import stat

import bpy
from bpy_extras.image_utils import load_image
from mathutils import Matrix, Vector
from .drs_definitions import DRS, CDspMeshFile, Vertex, Face, BattleforgeMesh, DRSBone, CSkSkeleton, Bone, BoneVertex
from .drs_material import DRS_Material

def load_drs(context: bpy.types.Context, filepath="", apply_transform=True, global_matrix=Matrix.Identity(4)) -> None:
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
		armature_object: bpy.types.Object = bpy.data.objects.new(f"Armature", armature_data)
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
		# Apply the Transformations to the Armature Object
		apply_transformations(armature_object, global_matrix, apply_transform)
	
	for i in range(drs_file.cdsp_mesh_file.mesh_count):
		# Create the Mesh Data
		mesh_data = create_static_mesh(drs_file.cdsp_mesh_file, i, base_name, dir_name)
		# Create the Mesh Object and add the Mesh Data to it
		mesh_object: bpy.types.Object = bpy.data.objects.new(f"CDspMeshFile_{i}", mesh_data)
		# Link the Mesh Object to the Source Collection
		source_collection.objects.link(mesh_object)
		# Check if the Mesh has a Skeleton and modify the Mesh Object accordingly
		if drs_file.csk_skeleton is not None:
			# Set the Armature Object as the Parent of the Mesh Object
			mesh_object.parent = armature_object
			# Add the Armature Modifier to the Mesh Object
			Modifier = mesh_object.modifiers.new(type="ARMATURE", name='Armature')
			Modifier.object = armature_object
		else:
			# Apply the Transformations to the Mesh Object when no Skeleton is present else we transform the armature
			apply_transformations(mesh_object, global_matrix, apply_transform)

	# if DRSFile.CollisionShape is not None:
	# 	CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, ModelDataCollection)
	# 	CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

	# 	if DRSFile.CollisionShape is not None:
	# 		CollisionShapeObjectObject.matrix_world = global_matrix @ CollisionShapeObjectObject.matrix_world
	# 		CollisionShapeObjectObject.scale = (1, -1, 1)

def apply_transformations(object: bpy.types.Object, global_matrix: Matrix, apply_transform: bool) -> None:
	if apply_transform:
		object.matrix_world = global_matrix @ object.matrix_world
		object.scale = (1, -1, 1)

def create_static_mesh(mesh_file: CDspMeshFile, mesh_index: int, base_name: str, dir_name:str, state: bool = False, override_name: str = "") -> bpy.types.Mesh:
	BattleforgeMeshData: BattleforgeMesh = mesh_file.meshes[mesh_index]
	# _name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
	mesh_data = bpy.data.meshes.new(f"MeshData_{mesh_index}")

	Vertices = list()
	Faces = list()		
	Normals = list()
			
	UVList = list()

	for _ in range(BattleforgeMeshData.face_count):
		_Face: Face = BattleforgeMeshData.faces[_].indices
		Faces.append([_Face[0], _Face[1], _Face[2]])

	for _ in range(BattleforgeMeshData.vertex_count):
		_Vertex = BattleforgeMeshData.mesh_data[0].vertices[_]
		Vertices.append(_Vertex.position)
		Normals.append(_Vertex.normal)
		# Negate the UVs Y Axis before adding them
		UVList.append((_Vertex.texture[0], -_Vertex.texture[1]))

	mesh_data.from_pydata(Vertices, [], Faces)
	mesh_data.polygons.foreach_set('use_smooth', [True] * len(mesh_data.polygons))
	mesh_data.normals_split_custom_set_from_vertices(Normals)
	if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]):
		mesh_data.use_auto_smooth = True

	UVList = [i for poly in mesh_data.polygons for vidx in poly.vertices for i in UVList[vidx]]
	mesh_data.uv_layers.new().data.foreach_set('uv', UVList)

	# Create the Material
	MaterialData = create_material(dir_name, mesh_index, base_name, BattleforgeMeshData)
	# Assign the Material to the Mesh
	mesh_data.materials.append(MaterialData)

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
			ChildID = bone_data.children[j]
			bone_list[ChildID].parent = bone_data.identifier

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

def create_material(dir_name: str, mesh_index: int, base_name: str, mesh_data: BattleforgeMesh, force_new: bool = True) -> bpy.types.Material:
	drs_material: 'DRS_Material' = DRS_Material(f"MaterialData_{mesh_index}")

	for texture in mesh_data.textures.textures:
		if (texture.length > 0):
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
