import bpy
from bpy_extras.image_utils import load_image
from mathutils import Vector
import os

SOCKET_SHADER = "NodeSocketShader"
SOCKET_COLOR = "NodeSocketColor"
SOCKET_NORMAL = "NodeSocketVector"
SOCKET_FLOAT = "NodeSocketFloat"

class DRSMaterial:
	def __init__(self, material_name: str) -> None:
		self.group = None
		self.shader = None
		self.inputs = None
		self.outputs = None
		self.node_tree = None
		self.material = None

		self.create_material(material_name)
		self.copy_node_tree()
		self.create_nodes()
		self.link_nodes()
		self.create_image_nodes()

	def create_material(self, material_name: str) -> None:
		_material = bpy.data.materials.get(material_name)
		if _material is None:
			self.material = bpy.data.materials.new(material_name)
		else:
			self.material = _material

		self.material.use_nodes = True
		self.material.node_tree.nodes.clear()
		self.material.blend_method = "CLIP"
		self.material.shadow_method = "NONE"

	def get_or_create_base_node_tree(self) -> bpy.types.NodeTree:
		base_node_tree_name = "DRS_Base_NodeGroup"
		base_node_tree = bpy.data.node_groups.get(base_node_tree_name)
		if base_node_tree is None:
			base_node_tree = bpy.data.node_groups.new(base_node_tree_name, type="ShaderNodeTree")
			self.setup_node_tree_inputs_outputs(base_node_tree)
		return base_node_tree

	def copy_node_tree(self) -> None:
		base_node_tree = self.get_or_create_base_node_tree()
		self.node_tree = base_node_tree.copy()
		self.node_tree.nodes.clear()
		self.setup_node_tree_inputs_outputs(self.node_tree)

	def setup_node_tree_inputs_outputs(self, node_tree: bpy.types.NodeTree) -> None:
		if bpy.app.version[0] == 3:
			node_tree.inputs.new(name="IN-Color Map", type=SOCKET_COLOR)
			node_tree.inputs.new(name="IN-Color Map Alpha", type=SOCKET_FLOAT)
			node_tree.inputs.new(name="IN-Metallic [red]", type=SOCKET_COLOR)
			node_tree.inputs.new(name="IN-Roughness [green]", type=SOCKET_COLOR)
			node_tree.inputs.new(name="IN-Emission [alpha]", type=SOCKET_COLOR)
			node_tree.inputs.new(name="IN-Normal Map", type=SOCKET_NORMAL)
			node_tree.outputs.new(name="OUT-DRS Shader", type=SOCKET_SHADER)
		elif bpy.app.version[0] == 4:
			node_tree.interface.clear()
			node_tree.interface.new_socket(name="IN-Color Map", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
			node_tree.interface.new_socket(name="IN-Color Map Alpha", in_out="INPUT", socket_type=SOCKET_FLOAT, parent=None)
			node_tree.interface.new_socket(name="IN-Metallic [red]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
			node_tree.interface.new_socket(name="IN-Roughness [green]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
			node_tree.interface.new_socket(name="IN-Emission [alpha]", in_out="INPUT", socket_type=SOCKET_COLOR, parent=None)
			node_tree.interface.new_socket(name="IN-Normal Map", in_out="INPUT", socket_type=SOCKET_NORMAL, parent=None)
			node_tree.interface.new_socket(name="OUT-DRS Shader", in_out="OUTPUT", socket_type=SOCKET_SHADER, parent=None)

	def create_nodes(self) -> None:
		self.inputs = self.node_tree.nodes.new("NodeGroupInput")
		self.inputs.location = Vector((-1000.0, 0.0))

		self.shader = self.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
		self.shader.location = Vector((0.0, 0.0))
		self.shader.inputs.get("IOR").default_value = 1.0
		if bpy.app.version[0] == 3:
			self.shader.inputs.get("Specular").default_value = 0

		self.outputs = self.node_tree.nodes.new("NodeGroupOutput")
		self.outputs.location = Vector((1000.0, 0.0))

		self.group = self.material.node_tree.nodes.get("DRS")
		if self.group is None:
			self.group = self.material.node_tree.nodes.new("ShaderNodeGroup")
		self.group.node_tree = self.node_tree

		self.material_output = self.material.node_tree.nodes.new("ShaderNodeOutputMaterial")
		self.material_output.location = Vector((400.0, 0.0))

	def link_nodes(self) -> None:
		self.material.node_tree.links.new(self.group.outputs.get("OUT-DRS Shader"), self.material_output.inputs.get("Surface"))
		self.node_tree.links.new(self.shader.outputs.get("BSDF"), self.outputs.inputs.get("OUT-DRS Shader"))

		# Link default inputs to the shader
		self.node_tree.links.new(self.inputs.outputs.get("IN-Color Map"), self.shader.inputs.get("Base Color"))
		self.node_tree.links.new(self.inputs.outputs.get("IN-Color Map Alpha"), self.shader.inputs.get("Alpha"))
		self.node_tree.links.new(self.inputs.outputs.get("IN-Metallic [red]"), self.shader.inputs.get("Metallic"))
		self.node_tree.links.new(self.inputs.outputs.get("IN-Roughness [green]"), self.shader.inputs.get("Roughness"))
		self.node_tree.links.new(self.inputs.outputs.get("IN-Emission [alpha]"), self.shader.inputs.get("Emission Strength"))
		if bpy.app.version[0] in [3]:
			self.node_tree.links.new(self.inputs.outputs.get("IN-Emission [alpha]"), self.shader.inputs.get("Emission"))
		if bpy.app.version[0] in [4]:
			self.node_tree.links.new(self.inputs.outputs.get("IN-Color Map"), self.shader.inputs.get("Emission Color"))

	def create_image_nodes(self) -> None:
		# Create empty image nodes for later use
		self.color_map_node = self.material.node_tree.nodes.new('ShaderNodeTexImage')
		self.color_map_node.location = Vector((-700.0, 0.0))
		self.material.node_tree.links.new(self.color_map_node.outputs.get("Color"), self.group.inputs.get("IN-Color Map"))
		self.material.node_tree.links.new(self.color_map_node.outputs.get("Alpha"), self.group.inputs.get("IN-Color Map Alpha"))

		self.parameter_map_node = self.material.node_tree.nodes.new('ShaderNodeTexImage')
		self.parameter_map_node.location = Vector((-700.0, -100.0))
		self.material.node_tree.links.new(self.parameter_map_node.outputs.get("Alpha"), self.group.inputs.get("IN-Emission [alpha]"))

		separate_rgb_node = self.material.node_tree.nodes.new('ShaderNodeSeparateColor')
		separate_rgb_node.location = Vector((-400.0, -100.0))
		self.material.node_tree.links.new(self.parameter_map_node.outputs.get("Color"), separate_rgb_node.inputs.get("Color"))
		self.material.node_tree.links.new(separate_rgb_node.outputs[1], self.group.inputs.get("IN-Roughness [green]"))
		self.material.node_tree.links.new(separate_rgb_node.outputs[0], self.group.inputs.get("IN-Metallic [red]"))

		self.normal_map_node = self.material.node_tree.nodes.new('ShaderNodeTexImage')
		self.normal_map_node.location = Vector((-700.0, -300.0))
		self.material.node_tree.links.new(self.normal_map_node.outputs.get("Color"), self.group.inputs.get("IN-Normal Map"))

		# Normal map nodes setup
		self.normal_map_separate = self.node_tree.nodes.new("ShaderNodeSeparateXYZ")
		self.normal_map_separate.location = Vector((-700.0, -100.0))

		self.normal_map_invert = self.node_tree.nodes.new("ShaderNodeInvert")
		self.normal_map_invert.location = Vector((-500.0, -100.0))

		self.normal_map_combine = self.node_tree.nodes.new("ShaderNodeCombineXYZ")
		self.normal_map_combine.location = Vector((-300.0, -100.0))

		# Link normal map nodes internally
		self.node_tree.links.new(self.inputs.outputs.get("IN-Normal Map"), self.normal_map_separate.inputs.get("Vector"))
		self.node_tree.links.new(self.normal_map_separate.outputs.get("Y"), self.normal_map_invert.inputs.get("Color"))
		self.node_tree.links.new(self.normal_map_invert.outputs.get("Color"), self.normal_map_combine.inputs.get("Y"))
		self.node_tree.links.new(self.normal_map_separate.outputs.get("X"), self.normal_map_combine.inputs.get("X"))
		self.node_tree.links.new(self.normal_map_separate.outputs.get("Z"), self.normal_map_combine.inputs.get("Z"))
		self.node_tree.links.new(self.normal_map_combine.outputs.get("Vector"), self.shader.inputs.get("Normal"))

	def load_image(self, texture_name: str, dir_name: str) -> bpy.types.Image:
		return load_image(os.path.basename(texture_name + ".dds"), dir_name, check_existing=True, place_holder=False, recursive=False)

	def set_color_map(self, texture_name: str, dir_name: str) -> None:
		self.color_map_node.image = self.load_image(texture_name, dir_name)

	def set_parameter_map(self, texture_name: str, dir_name: str) -> None:
		self.parameter_map_node.image = self.load_image(texture_name, dir_name)

	def set_normal_map(self, texture_name: str, dir_name: str) -> None:
		self.normal_map_node.image = self.load_image(texture_name, dir_name)
