import os

import bpy
from bpy_extras.image_utils import load_image

from mathutils import Vector, Matrix
from . drs_definitions import (
	DRS, DRSBone,
	CDspMeshFile, CDspJointMap,
	CSkSkeleton, CSkSkinInfo,
	Bone, BoneMatrix, BoneVertex,
	Vertex, Face,
	BattleforgeMesh
)

SOCKET_SHADER = "NodeSocketShader"
SOCKET_COLOR = "NodeSocketColor"
SOCKET_FLOAT = "NodeSocketFloat"
SOCKET_NORMAL = "NodeSocketVector"

def load_drs(context: bpy.types.Context, filepath=""):
	base_name = os.path.basename(filepath).split(".")[0]
	dir_name = os.path.dirname(filepath)
	drs_file: DRS = DRS().Read(filepath)

	# source_collection = SetCollection("DRSModel_" + base_name + "_Type", "", bpy.context.view_layer.layer_collection)
	source_collection = context.scene.collection

	if drs_file.IsSkinned:
		armature = bpy.data.armatures.new("Bones")
		armature_object: bpy.types.Object = bpy.data.objects.new("CSkSkeleton", armature)
		bpy.context.collection.objects.link(armature_object)
		bpy.context.view_layer.objects.active = armature_object
		bone_list = init_skeleton(drs_file.CSkSkeleton)
		build_skeleton(bone_list, armature, armature_object)
		
		weight_list = init_skin(drs_file.CDspMeshFileData, drs_file.CSkSkinInfo, drs_file.CGeoMesh)
		mesh_object: bpy.types.Object = SetObject("CDspMeshFile_" + base_name, "", source_collection) #, armature)
		mesh_object.parent = armature_object
		create_skinned_mesh(drs_file.CDspMeshFile, dir_name, base_name, mesh_object, armature_object, bone_list, weight_list)

		if drs_file.AnimationSet is not None:
			for AnimationKey in drs_file.AnimationSet.ModeAnimationKeys:
				for Variant in AnimationKey.AnimationSetVariants:
					SKAFile: SKA = SKA().Read(os.path.join(dir_name, Variant.File))
					create_animation(SKAFile, armature_object, bone_list, Variant.File)
	else:
		mesh_object: bpy.types.Object = bpy.data.objects.new("CDspMeshFile_" + base_name, None)
		create_static_mesh(drs_file.CDspMeshFileData, base_name, dir_name, mesh_object, override_name=base_name)

	# if DRSFile.CollisionShape is not None:
	# 	CollisionShapeObjectObject = SetObject("CollisionShape", HashOf5Letters, ModelDataCollection)
	# 	CreateCollisionShapes(DRSFile.CollisionShape, CollisionShapeObjectObject)

	# if use_apply_transform:
	# 	if drs_file.CSkSkeleton is not None:
	# 		armature_object.matrix_world = global_matrix @ armature_object.matrix_world
	# 		armature_object.scale = (1, -1, 1)
	# 	else:
	# 		mesh_object.matrix_world = global_matrix @ mesh_object.matrix_world
	# 		mesh_object.scale = (1, -1, 1)

	# 	if DRSFile.CollisionShape is not None:
	# 		CollisionShapeObjectObject.matrix_world = global_matrix @ CollisionShapeObjectObject.matrix_world
	# 		CollisionShapeObjectObject.scale = (1, -1, 1)

def create_static_mesh(mesh_file: CDspMeshFile, base_name: str, dir_name:str, mesh_object: bpy.types.Object, state: bool = False, override_name: str = ""):
	for i in range(mesh_file.MeshCount):
		BattleforgeMeshData: BattleforgeMesh = mesh_file.Meshes[i]

		_name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
		mesh_name = f"MeshData_{_name}"

		static_mesh = bpy.data.meshes.new(mesh_name)
		static_mesh_object = bpy.data.objects.new(mesh_name, static_mesh)

		Vertices = list()
		Faces = list()		
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

		static_mesh.from_pydata(Vertices, [], Faces)
		static_mesh.polygons.foreach_set('use_smooth', [True] * len(static_mesh.polygons))
		static_mesh.normals_split_custom_set_from_vertices(Normals)
		if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]):
			static_mesh.use_auto_smooth = True

		UVList = [_ for poly in static_mesh.polygons for vidx in poly.vertices for _ in UVList[vidx]]
		static_mesh.uv_layers.new().data.foreach_set('uv', UVList)

		MaterialData = create_material(dir_name, base_name, i, BattleforgeMeshData)
		static_mesh.materials.append(MaterialData)
		static_mesh_object.parent = mesh_object

		bpy.context.collection.objects.link(static_mesh_object)
		
def init_skeleton(skeleton_data: CSkSkeleton, suffix: str = None) -> list[DRSBone]:
	BoneList: list[DRSBone] = []

	# Init the Bone List
	for i in range(skeleton_data.BoneCount):
		BoneList.append(DRSBone())

	# Set the Bone Datapoints
	for i in range(skeleton_data.BoneCount):
		BoneData: Bone = skeleton_data.Bones[i]

		# Get the RootBone Vertices
		BoneVertices: list[BoneVertex] = skeleton_data.BoneMatrices[BoneData.Identifier].BoneVertices

		_Vector0 = Vector((BoneVertices[0].Position.x, BoneVertices[0].Position.y, BoneVertices[0].Position.z, BoneVertices[0].Parent))
		_Vector1 = Vector((BoneVertices[1].Position.x, BoneVertices[1].Position.y, BoneVertices[1].Position.z, BoneVertices[1].Parent))
		_Vector2 = Vector((BoneVertices[2].Position.x, BoneVertices[2].Position.y, BoneVertices[2].Position.z, BoneVertices[2].Parent))
		_Vector3 = Vector((BoneVertices[3].Position.x, BoneVertices[3].Position.y, BoneVertices[3].Position.z, BoneVertices[3].Parent))

		# Create the Bone Matrix
		# Make the 4th column negative to flip the Axis
		_Rot = Matrix((_Vector0.xyz, _Vector1.xyz, _Vector2.xyz))
		_Loc = _Rot @ (-1 * _Vector3.xyz)
		_BoneMatrix = Matrix.LocRotScale(_Loc, _Rot, Vector((1, 1, 1)))

		# Set Data
		BoneListItem: DRSBone = BoneList[BoneData.Identifier]
		BoneListItem.SKAIdentifier = BoneData.Version
		BoneListItem.Identifier = BoneData.Identifier
		BoneListItem.Name = BoneData.Name + (f"_{suffix}" if suffix else "")
		BoneListItem.BoneMatrix = _BoneMatrix

		# Set the Bone Children
		BoneListItem.Children = BoneData.Children

		# Set the Bones Children's Parent ID
		for j in range(BoneData.ChildCount):
			ChildID = BoneData.Children[j]
			BoneList[ChildID].Parent = BoneData.Identifier

	# Order the Bones by Parent ID
	BoneList.sort(key=lambda x: x.Identifier)

	# Return the BoneList
	return BoneList

def build_skeleton(bone_list: list[DRSBone], armature: bpy.types.Armature, armature_object: bpy.types.Object) -> None:
	# Switch to edit mode
	bpy.context.view_layer.objects.active = armature_object
	bpy.ops.object.mode_set(mode='EDIT')

	create_bone_tree(armature, bone_list, bone_list[0])

	bpy.ops.object.mode_set(mode='OBJECT')

	# Record bind pose transform to parent space
	# Used to set pose bones for animation
	for BoneData in bone_list:
		ArmaBone = armature.bones[BoneData.Name]
		MatrixLocal = ArmaBone.matrix_local

		if ArmaBone.parent:
			MatrixLocal = ArmaBone.parent.matrix_local.inverted_safe() @ MatrixLocal

		BoneData.BindLoc = MatrixLocal.to_translation()
		BoneData.BindRot = MatrixLocal.to_quaternion()

def create_material(dir_name: str, base_name: str, mesh_index: int, mesh_data: BattleforgeMesh, force_new: bool = True) -> bpy.types.Material:
	mesh_material = None
	material_name = f"Material_{base_name}_{mesh_index}"

	if (force_new == True):
		mesh_material = bpy.data.materials.new(material_name)
	else:
		_material = bpy.data.materials.get(material_name)
		if (_material is not None):
			mesh_material = _material
		else:
			mesh_material = bpy.data.materials.new(material_name)

	mesh_material.use_nodes = True
	mesh_material.node_tree.nodes.clear()

	DRSShaderNodeTree: bpy.types.ShaderNodeTree = bpy.data.node_groups.get("DRS") if ( bpy.data.node_groups.get("DRS") is not None) else bpy.data.node_groups.new("DRS", type="ShaderNodeTree")
	DRSShaderNodeTree.nodes.clear()

	if (bpy.app.version[0] in [3]):
		DRSShaderNodeTree.inputs.new(name="IN-Color Map", type=SOCKET_COLOR)
		DRSShaderNodeTree.inputs.new(name="IN-Color Map Alpha", type=SOCKET_FLOAT)

		DRSShaderNodeTree.inputs.new(name="IN-Metallic [red]", type=SOCKET_COLOR)
		DRSShaderNodeTree.inputs.new(name="IN-Roughness [green]", type=SOCKET_COLOR)
		DRSShaderNodeTree.inputs.new(name="IN-Emission [alpha]", type=SOCKET_COLOR)

		DRSShaderNodeTree.inputs.new(name="IN-Normal Map", type=SOCKET_NORMAL)

		DRSShaderNodeTree.outputs.new(name="OUT-DRS Shader", type=SOCKET_SHADER)

	if (bpy.app.version[0] in [4]):
		DRSShaderNodeTree.interface.clear()
		DRSShaderNodeTree.interface.new_socket(name="IN-Color Map", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
		DRSShaderNodeTree.interface.new_socket(name="IN-Color Map Alpha", in_out="INPUT", socket_type=SOCKET_FLOAT, parent=None)

		DRSShaderNodeTree.interface.new_socket(name="IN-Metallic [red]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
		DRSShaderNodeTree.interface.new_socket(name="IN-Roughness [green]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
		DRSShaderNodeTree.interface.new_socket(name="IN-Emission [alpha]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)

		DRSShaderNodeTree.interface.new_socket(name="IN-Normal Map", in_out="INPUT", socket_type=SOCKET_NORMAL, parent=None)

		DRSShaderNodeTree.interface.new_socket(name="OUT-DRS Shader", in_out="OUTPUT", socket_type=SOCKET_SHADER, parent=None)
		
	DRSShaderGroupInputs = DRSShaderNodeTree.nodes.new("NodeGroupInput") # Internal Node of the DRS Custom Shader
	DRSShaderGroupInputs.location = Vector((-1000.0, 0.0))

	# Create the BSDF Shader
	DRSShaderGroupShader = DRSShaderNodeTree.nodes.new("ShaderNodeBsdfPrincipled")
	DRSShaderGroupShader.location = Vector((0.0, 0.0))
	DRSShaderGroupShader.inputs.get("IOR").default_value = 1.0

	if (bpy.app.version[0] in [3]):
		DRSShaderGroupShader.inputs.get("Specular").default_value = 0

	DRSShaderGroupOutputs = DRSShaderNodeTree.nodes.new("NodeGroupOutput") # Internal Node of the DRS Custom Shader
	DRSShaderGroupOutputs.location = Vector((1000.0, 0.0))

	DRSShaderGroup: bpy.types.ShaderNodeGroup = mesh_material.node_tree.nodes.get("DRS") if (mesh_material.node_tree.nodes.get("DRS") is not None) else mesh_material.node_tree.nodes.new("ShaderNodeGroup")
	DRSShaderGroup.node_tree = DRSShaderNodeTree

	mesh_material_output = mesh_material.node_tree.nodes.new("ShaderNodeOutputMaterial")
	mesh_material_output.location = Vector((400.0, 0.0))
	
	mesh_material.node_tree.links.new(DRSShaderGroup.outputs.get("OUT-DRS Shader"), mesh_material_output.inputs.get("Surface"))
	DRSShaderNodeTree.links.new(DRSShaderGroupShader.outputs.get("BSDF"), DRSShaderGroupOutputs.inputs.get("OUT-DRS Shader"))

	for texture in mesh_data.Textures.Textures:
		if (texture.Length > 0):
			match texture.Identifier:
				case 1684432499:
					color_map_img = load_image(os.path.basename(texture.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
					color_map_node = mesh_material.node_tree.nodes.new('ShaderNodeTexImage')
					color_map_node.location = Vector((-700.0, 0.0))
					color_map_node.image = color_map_img

					mesh_material.node_tree.links.new(color_map_node.outputs.get("Color"), DRSShaderGroup.inputs.get("IN-Color Map"))
					mesh_material.node_tree.links.new(color_map_node.outputs.get("Alpha"), DRSShaderGroup.inputs.get("IN-Color Map Alpha"))
					# Group Internal Links
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Color Map"), DRSShaderGroupShader.inputs.get("Base Color"))
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Color Map Alpha"), DRSShaderGroupShader.inputs.get("Alpha"))
				case 1936745324:
					parameter_map_img = load_image(os.path.basename(texture.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
					parameter_map_node = mesh_material.node_tree.nodes.new('ShaderNodeTexImage')
					parameter_map_node.location = Vector((-700.0, -100.0))
					parameter_map_node.image = parameter_map_img

					separate_rgb_node = mesh_material.node_tree.nodes.new('ShaderNodeSeparateColor')
					separate_rgb_node.location = Vector((-400.0, -100.0))

					mesh_material.node_tree.links.new(parameter_map_node.outputs.get("Color"), separate_rgb_node.inputs.get("Color"))
					mesh_material.node_tree.links.new(separate_rgb_node.outputs[0], DRSShaderGroup.inputs.get("IN-Metallic [red]"))
					mesh_material.node_tree.links.new(separate_rgb_node.outputs[1], DRSShaderGroup.inputs.get("IN-Roughness [green]"))

					mesh_material.node_tree.links.new(parameter_map_node.outputs.get("Alpha"), DRSShaderGroup.inputs.get("IN-Emission [alpha]"))
					# Group Internal Links
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Metallic [red]"), DRSShaderGroupShader.inputs.get("Metallic"))
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Roughness [green]"), DRSShaderGroupShader.inputs.get("Roughness"))
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Emission [alpha]"), DRSShaderGroupShader.inputs.get("Emission Strength"))
					if (bpy.app.version[0] in [3]):
						DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Emission [alpha]"), DRSShaderGroupShader.inputs.get("Emission"))
					if (bpy.app.version[0] in [4]):
						DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Color Map"), DRSShaderGroupShader.inputs.get("Emission Color"))
				case 1852992883:
					normal_map_image = load_image(os.path.basename(texture.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
					normal_map_node = mesh_material.node_tree.nodes.new('ShaderNodeTexImage')
					normal_map_node.location = Vector((-700.0, -300.0))
					normal_map_node.image = normal_map_image

					mesh_material.node_tree.links.new(normal_map_node.outputs.get("Color"), DRSShaderGroup.inputs.get("IN-Normal Map"))
					# Group Internal Links
					# We need to flip the Y Axis of the Normal Map to match Blender's Normal Map
					# Separate
					normal_map_separate = DRSShaderNodeTree.nodes.new("ShaderNodeSeparateXYZ")
					normal_map_separate.location = Vector((-700.0, -100.0))
					DRSShaderNodeTree.links.new(DRSShaderGroupInputs.outputs.get("IN-Normal Map"), normal_map_separate.inputs.get("Vector"))
					# Invert
					normal_map_invert = DRSShaderNodeTree.nodes.new("ShaderNodeInvert")
					normal_map_invert.location = Vector((-500.0, -100.0))
					DRSShaderNodeTree.links.new(normal_map_separate.outputs.get("Y"), normal_map_invert.inputs.get("Color"))
					# Combine
					normal_map_combine = DRSShaderNodeTree.nodes.new("ShaderNodeCombineXYZ")
					normal_map_combine.location = Vector((-300.0, -100.0))
					DRSShaderNodeTree.links.new(normal_map_invert.outputs.get("Color"), normal_map_combine.inputs.get("Y"))
					DRSShaderNodeTree.links.new(normal_map_separate.outputs.get("X"), normal_map_combine.inputs.get("X"))
					DRSShaderNodeTree.links.new(normal_map_separate.outputs.get("Z"), normal_map_combine.inputs.get("Z"))
					DRSShaderNodeTree.links.new(normal_map_combine.outputs.get("Vector"), DRSShaderGroupShader.inputs.get("Normal"))

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

	return mesh_material

def create_action(armature_object: bpy.types.Object, animation_name: str, animation_time_in_frames: int, force_new: bool = True, repeat: bool = False):
	armature_action = None
	if (force_new == False):
		armature_action = bpy.data.actions.new(name=animation_name)
	else:
		action = bpy.data.actions.get(animation_name)
		if (action is not None):
			armature_action = (bpy.data.get(animation_name) is None)

	armature_action.use_frame_range = True
	armature_action.frame_range = (0, animation_time_in_frames)
	armature_action.frame_start = 0
	armature_action.frame_end = animation_time_in_frames
	armature_action.use_cyclic = repeat

	bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, animation_time_in_frames)
	armature_object.animation_data.action = armature_action
	return armature_action
