import os

import bpy
from bpy_extras.image_utils import load_image
from mathutils import Matrix, Vector
from .drs_definitions import DRS, CDspMeshFile, Vertex, Face, BattleforgeMesh
from .drs_material import DRS_Material

def load_drs(context: bpy.types.Context, filepath=""):
	base_name = os.path.basename(filepath).split(".")[0]
	dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().read(filepath)

	source_collection: bpy.types.Collection = bpy.data.collections.new("DRSModel_" + base_name + "_Type")
	context.collection.children.link(source_collection)

	# if drs_file.csk_skeleton is not None:
		# armature = bpy.data.armatures.new("Bones")
		# armature_object: bpy.types.Object = bpy.data.objects.new("CSkSkeleton", armature)
		# bpy.context.collection.objects.link(armature_object)
		# bpy.context.view_layer.objects.active = armature_object
		# bone_list = init_skeleton(drs_file.csk_skeleton)
		# build_skeleton(bone_list, armature, armature_object)
		
		# weight_list = init_skin(drs_file.cdsp_mesh_file, drs_file.csk_skin_info, drs_file.cgeo_mesh)
		# mesh_object: bpy.types.Object = SetObject("CDspMeshFile_" + base_name, "", source_collection) #, armature)
		# mesh_object.parent = armature_object
		# create_skinned_mesh(drs_file.cdsp_mesh_file, dir_name, base_name, mesh_object, armature_object, bone_list, weight_list)

		# if drs_file.AnimationSet is not None:
		# 	for AnimationKey in drs_file.AnimationSet.ModeAnimationKeys:
		# 		for Variant in AnimationKey.AnimationSetVariants:
		# 			SKAFile: SKA = SKA().Read(os.path.join(dir_name, Variant.File))
		# 			create_animation(SKAFile, armature_object, bone_list, Variant.File)
	# else:
	mesh_object: bpy.types.Object = bpy.data.objects.new("CDspMeshFile_" + base_name, None)
	create_static_mesh(source_collection, drs_file.cdsp_mesh_file, base_name, dir_name, mesh_object, override_name=base_name)

	# if DRSFile.CollisionShape is not None:
	# 	CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, ModelDataCollection)
	# 	CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

	# if use_apply_transform:
	# 	if drs_file.csk_skeleton is not None:
	# 		armature_object.matrix_world = global_matrix @ armature_object.matrix_world
	# 		armature_object.scale = (1, -1, 1)
	# 	else:
	# 		mesh_object.matrix_world = global_matrix @ mesh_object.matrix_world
	# 		mesh_object.scale = (1, -1, 1)

	# 	if DRSFile.CollisionShape is not None:
	# 		CollisionShapeObjectObject.matrix_world = global_matrix @ CollisionShapeObjectObject.matrix_world
	# 		CollisionShapeObjectObject.scale = (1, -1, 1)

	# ResetViewport()

def create_static_mesh(parent_collection: bpy.types.Collection, mesh_file: CDspMeshFile, base_name: str, dir_name:str, mesh_object: bpy.types.Object, state: bool = False, override_name: str = ""):
	for i in range(mesh_file.mesh_count):
		BattleforgeMeshData: BattleforgeMesh = mesh_file.meshes[i]

		_name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
		mesh_name = f"MeshData_{_name}"

		static_mesh = bpy.data.meshes.new(mesh_name)
		static_mesh_object = bpy.data.objects.new(mesh_name, static_mesh)

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

		static_mesh.from_pydata(Vertices, [], Faces)
		static_mesh.polygons.foreach_set('use_smooth', [True] * len(static_mesh.polygons))
		static_mesh.normals_split_custom_set_from_vertices(Normals)
		if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]):
			static_mesh.use_auto_smooth = True

		UVList = [i for poly in static_mesh.polygons for vidx in poly.vertices for i in UVList[vidx]]
		static_mesh.uv_layers.new().data.foreach_set('uv', UVList)

		MaterialData = create_material(dir_name, base_name, i, BattleforgeMeshData)
		static_mesh.materials.append(MaterialData)
		static_mesh_object.parent = mesh_object

		parent_collection.objects.link(static_mesh_object)
		
# def init_skeleton(skeleton_data: CSkSkeleton, suffix: str = None) -> list[DRSBone]:
# 	BoneList: list[DRSBone] = []

# 	# Init the Bone List
# 	for i in range(skeleton_data.BoneCount):
# 		BoneList.append(DRSBone())

# 	# Set the Bone Datapoints
# 	for i in range(skeleton_data.BoneCount):
# 		BoneData: Bone = skeleton_data.Bones[i]

# 		# Get the RootBone Vertices
# 		BoneVertices: list[BoneVertex] = skeleton_data.BoneMatrices[BoneData.Identifier].BoneVertices

# 		_Vector0 = Vector((BoneVertices[0].Position.x, BoneVertices[0].Position.y, BoneVertices[0].Position.z, BoneVertices[0].Parent))
# 		_Vector1 = Vector((BoneVertices[1].Position.x, BoneVertices[1].Position.y, BoneVertices[1].Position.z, BoneVertices[1].Parent))
# 		_Vector2 = Vector((BoneVertices[2].Position.x, BoneVertices[2].Position.y, BoneVertices[2].Position.z, BoneVertices[2].Parent))
# 		_Vector3 = Vector((BoneVertices[3].Position.x, BoneVertices[3].Position.y, BoneVertices[3].Position.z, BoneVertices[3].Parent))

# 		# Create the Bone Matrix
# 		# Make the 4th column negative to flip the Axis
# 		_Rot = Matrix((_Vector0.xyz, _Vector1.xyz, _Vector2.xyz))
# 		_Loc = _Rot @ (-1 * _Vector3.xyz)
# 		_BoneMatrix = Matrix.LocRotScale(_Loc, _Rot, Vector((1, 1, 1)))

# 		# Set Data
# 		BoneListItem: DRSBone = BoneList[BoneData.Identifier]
# 		BoneListItem.SKAIdentifier = BoneData.Version
# 		BoneListItem.Identifier = BoneData.Identifier
# 		BoneListItem.Name = BoneData.Name + (f"_{suffix}" if suffix else "")
# 		BoneListItem.BoneMatrix = _BoneMatrix

# 		# Set the Bone Children
# 		BoneListItem.Children = BoneData.Children

# 		# Set the Bones Children's Parent ID
# 		for j in range(BoneData.ChildCount):
# 			ChildID = BoneData.Children[j]
# 			BoneList[ChildID].Parent = BoneData.Identifier

# 	# Order the Bones by Parent ID
# 	BoneList.sort(key=lambda x: x.Identifier)

# 	# Return the BoneList
# 	return BoneList

# def build_skeleton(bone_list: list[DRSBone], armature: bpy.types.Armature, armature_object: bpy.types.Object) -> None:
# 	# Switch to edit mode
# 	bpy.context.view_layer.objects.active = armature_object
# 	bpy.ops.object.mode_set(mode='EDIT')

# 	create_bone_tree(armature, bone_list, bone_list[0])

# 	bpy.ops.object.mode_set(mode='OBJECT')

# 	# Record bind pose transform to parent space
# 	# Used to set pose bones for animation
# 	for BoneData in bone_list:
# 		ArmaBone = armature.bones[BoneData.Name]
# 		MatrixLocal = ArmaBone.matrix_local

# 		if ArmaBone.parent:
# 			MatrixLocal = ArmaBone.parent.matrix_local.inverted_safe() @ MatrixLocal

# 		BoneData.BindLoc = MatrixLocal.to_translation()
# 		BoneData.BindRot = MatrixLocal.to_quaternion()

def create_material(dir_name: str, base_name: str, mesh_index: int, mesh_data: BattleforgeMesh, force_new: bool = True) -> bpy.types.Material:
	material_name = f"Material_{base_name}_{mesh_index}"
	drs_material: DRS_Material = DRS_Material(material_name)

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
