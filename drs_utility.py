import os

import bpy
from bpy_extras.image_utils import load_image

from mathutils import Vector
from . drs_definitions import BattleforgeMesh, CDspMeshFile, Vertex, Face

SOCKET_SHADER = "NodeSocketShader"


def create_static_mesh(context: bpy.types.Context, mesh_file: CDspMeshFile, base_name: str, dir_name:str, mesh_object: bpy.types.Object, state: bool = False, override_name: str = ""):
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

        UVList = [i for poly in static_mesh.polygons for vidx in poly.vertices for i in UVList[vidx]]
        static_mesh.uv_layers.new().data.foreach_set('uv', UVList)

        MaterialData = create_material(i, BattleforgeMeshData, dir_name, base_name)
        static_mesh.materials.append(MaterialData)
        static_mesh_object.parent = mesh_object

        bpy.context.collection.objects.link(static_mesh_object)
        

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

    DRSNodeGroup : bpy.types.NodeGroup = bpy.data.node_groups.get("DRS") if ( bpy.data.node_groups.get("DRS") is not None) else bpy.data.node_groups.new("DRS", type="ShaderNodeTree")
    DRSNodeGroup.node_tree.nodes.clear()
    DRSNodeGroup.node_tree.interface.clear()

    if (bpy.app.version[0] in [3]):
        DRSNodeGroup.outputs.new(name="OUT-DRS Shader", type=SOCKET_SHADER)
    if (bpy.app.version[0] in [4]):
        DRSNodeGroup.node_tree.interface.new_socket(name="OUT-DRS Shader", in_out="OUTPUT", socket_type=SOCKET_SHADER, parent=None)

    DRSShaderGroup : bpy.types.NodeGroup = mesh_material.node_tree.nodes.new('ShaderNodeGroup')
    DRSShaderGroup.node_tree = DRSNodeGroup

    mesh_material_output = mesh_material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mesh_material_output.location = Vector((400.0, 0.0))

    if (bpy.app.version[0] in [3]):
        mesh_material.node_tree.links.new(DRSShaderGroup.outputs.get("OUT-DRS Shader"), mesh_material_output.inputs['Surface'])
    if (bpy.app.version[0] in [4]):
        mesh_material.node_tree.links.new(DRSShaderGroup.node_tree.interface.get("OUT-DRS Shader"), mesh_material_output.inputs['Surface'])

    # NewMaterial.blend_method = 'CLIP'
    # NewMaterial.alpha_threshold = 0.6
    # NewMaterial.show_transparent_back = False
    # NewMaterial.use_nodes = True
    # NewMaterial.node_tree.nodes['Material Output'].location = Vector((400.0, 0.0))	
    # BSDF = NewMaterial.node_tree.nodes["Principled BSDF"]
    # BSDF.location = Vector((0.0, 0.0))
    # ColorMapNode = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
    # ColorMapNode.location = Vector((-700.0, 0.0))

    # Add BaseColor Texture
    for Tex in mesh_data.Textures.Textures:
        if Tex.Identifier == 1684432499 and Tex.Length > 0:
            col_image = load_image(os.path.basename(Tex.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
            col_node = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
            col_node.location = Vector((-700.0, 0.0))
            col_node.image = col_image
            NewMaterial.node_tree.links.new(col_node.outputs['Color'], DRSGroupNode.inputs['Color Map'])
            NewMaterial.node_tree.links.new(col_node.outputs['Alpha'], DRSGroupNode.inputs['Color Alpha'])

    # Add ParameterMap if present
    for Tex in mesh_data.Textures.Textures:
        if Tex.Identifier == 1936745324 and Tex.Length > 0:
            param_image = load_image(os.path.basename(Tex.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
            param_node = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
            param_node.location = Vector((-700.0, -100.0))
            param_node.image = param_image
            # Create a Separate RGB Node between the ParameterMap and the DRS Group Node
            sep_rgb_node = NewMaterial.node_tree.nodes.new('ShaderNodeSeparateRGB')
            sep_rgb_node.location = Vector((-400.0, -100.0))
            NewMaterial.node_tree.links.new(param_node.outputs['Color'], sep_rgb_node.inputs['Image'])
            NewMaterial.node_tree.links.new(sep_rgb_node.outputs['R'], DRSGroupNode.inputs['Metallic (Red)'])
            NewMaterial.node_tree.links.new(sep_rgb_node.outputs['G'], DRSGroupNode.inputs['Roughness (Green)'])
            # Skip B
            NewMaterial.node_tree.links.new(param_node.outputs['Alpha'], DRSGroupNode.inputs['Emission (Alpha)'])

    # Add NormalMap Texture if present
    for Tex in mesh_data.Textures.Textures:
        if Tex.Identifier == 1852992883 and Tex.Length > 0:
            nor_image = load_image(os.path.basename(Tex.Name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)
            nor_node = NewMaterial.node_tree.nodes.new('ShaderNodeTexImage')
            nor_node.location = Vector((-700.0, -300.0))
            nor_node.image = nor_image
            NewMaterial.node_tree.links.new(nor_node.outputs['Color'], DRSGroupNode.inputs['Normal Map'])

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

    return NewMaterial


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