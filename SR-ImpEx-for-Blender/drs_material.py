import os
import bpy
from mathutils import Vector
from bpy_extras.image_utils import load_image

# Socket type constants for clarity
SOCKET_SHADER = "NodeSocketShader"
SOCKET_COLOR = "NodeSocketColor"
SOCKET_NORMAL = "NodeSocketVector"
SOCKET_FLOAT = "NodeSocketFloat"


class DRSMaterial:
    def __init__(self, material_name: str, use_separate_maps: bool = False) -> None:
        """Initialize the DRS Material with node setup.
        If use_separate_maps is True, expects separate Metallic, Roughness, Emission maps instead of a combined RGBA map.
        """
        self.use_separate_maps = use_separate_maps
        # References to important nodes (for later image assignment)
        self.color_tex_node = None
        self.param_tex_node = None
        self.metallic_tex_node = None
        self.roughness_tex_node = None
        self.emission_tex_node = None
        self.normal_tex_node = None
        # Node group (NodeTree) and outer group node reference
        self.group_tree = None
        self.group_node = None
        # Create material and node setup
        self._create_material(material_name)
        self._create_node_group()
        self._create_group_nodes()
        self._link_group_nodes()
        self._create_outer_nodes()
        self._layout_and_decorate_nodes()

    def _create_material(self, material_name: str) -> None:
        """Create a new material (or get existing) and set basic settings."""
        mat = bpy.data.materials.get(material_name)
        if mat is None:
            mat = bpy.data.materials.new(material_name)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()  # start with a fresh node tree
        # Enable alpha clip blending (common for cutout opacity) and set shadow mode to none for older versions
        mat.blend_method = "CLIP"
        if bpy.app.version < (4, 3):
            mat.shadow_method = "NONE"
        self.material = mat

    def _create_node_group(self) -> None:
        """Create or copy a base node group (NodeTree) and set up its interface sockets."""
        # Use a base node group as a template (to share interface definition across materials)
        base_name = "DRS_Base_NodeGroup"
        base_tree = bpy.data.node_groups.get(base_name)
        if base_tree is None:
            base_tree = bpy.data.node_groups.new(base_name, type="ShaderNodeTree")
            # Define interface sockets on the base template
            self._setup_node_group_interface(base_tree)
        # Copy the base node tree for this material's use
        self.group_tree = base_tree.copy()
        # Remove any nodes from the new group (retain interface)
        for node in list(self.group_tree.nodes):
            self.group_tree.nodes.remove(node)
        # (Re)define the interface in case base was updated or to avoid duplication issues
        self._setup_node_group_interface(self.group_tree)
        # Create a group node in the material's node tree to use this node group
        self.group_node = self.material.node_tree.nodes.new("ShaderNodeGroup")
        self.group_node.node_tree = self.group_tree
        # Name the group node for clarity in the shader editor
        self.group_node.label = "DRS Material"
        self.group_node.name = "DRS"

    def _setup_node_group_interface(self, node_tree: bpy.types.NodeTree) -> None:
        """Set up input/output sockets for the node group (compatible with Blender 3.x and 4.x)."""
        # Define the desired sockets (name, type, in/out). Using color sockets for scalar maps for flexibility.
        sockets = [
            {"name": "IN-Color Map", "type": SOCKET_COLOR, "in_out": "INPUT"},
            {"name": "IN-Color Map Alpha", "type": SOCKET_FLOAT, "in_out": "INPUT"},
            {"name": "IN-Metallic [red]", "type": SOCKET_COLOR, "in_out": "INPUT"},
            {"name": "IN-Roughness [green]", "type": SOCKET_COLOR, "in_out": "INPUT"},
            {"name": "IN-Emission [alpha]", "type": SOCKET_COLOR, "in_out": "INPUT"},
            {"name": "IN-Normal Map", "type": SOCKET_NORMAL, "in_out": "INPUT"},
            {"name": "OUT-DRS Shader", "type": SOCKET_SHADER, "in_out": "OUTPUT"},
        ]
        if bpy.app.version[0] >= 4:
            # In Blender 4.x+, use the interface API for node group sockets&#8203;:contentReference[oaicite:3]{index=3}
            node_tree.interface.clear()
            for sock in sockets:
                new_sock = node_tree.interface.new_socket(
                    name=sock["name"], in_out=sock["in_out"], socket_type=sock["type"]
                )
                # Hide the default value field for inputs (they will be texture-driven)
                if sock["in_out"] == "INPUT" and hasattr(new_sock, "hide_value"):
                    new_sock.hide_value = True
        else:
            # Blender 3.x and earlier
            # First remove existing sockets to avoid duplicates on re-run
            for i in range(len(node_tree.inputs) - 1, -1, -1):
                node_tree.inputs.remove(node_tree.inputs[i])
            for o in range(len(node_tree.outputs) - 1, -1, -1):
                node_tree.outputs.remove(node_tree.outputs[o])
            # Create sockets using old API
            for sock in sockets:
                if sock["in_out"] == "INPUT":
                    new_sock = node_tree.inputs.new(
                        type=sock["type"], name=sock["name"]
                    )
                    if hasattr(new_sock, "hide_value"):
                        new_sock.hide_value = True
                else:  # OUTPUT
                    node_tree.outputs.new(type=sock["type"], name=sock["name"])

    def _create_group_nodes(self) -> None:
        """Create internal nodes within the node group (Principled BSDF, NormalMap, Input/Output nodes)."""
        nodes = self.group_tree.nodes
        links = self.group_tree.links
        # Group Input and Output nodes (appear automatically in new node group, but we ensure references)
        input_node = nodes.new("NodeGroupInput")
        output_node = nodes.new("NodeGroupOutput")
        input_node.location = Vector((-1000.0, 0.0))
        output_node.location = Vector((800.0, 0.0))
        # Create the main shader (Principled BSDF) inside the group
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = Vector((0.0, 0.0))
        # Set Principled defaults for a metallic workflow
        bsdf.inputs["IOR"].default_value = 1.0
        if bpy.app.version[0] == 3:
            bsdf.inputs["Specular"].default_value = 0.0
        # Create a Normal Map node inside the group (to handle normal map conversion)
        normal_map_node = nodes.new("ShaderNodeNormalMap")
        normal_map_node.location = Vector((-300.0, -300.0))
        # Link the normal map node to the BSDF normal input
        links.new(normal_map_node.outputs["Normal"], bsdf.inputs["Normal"])
        # Save references for later use if needed
        self._bsdf_node = bsdf
        self._normal_map_node = normal_map_node
        self._input_node = input_node
        self._output_node = output_node

    def _link_group_nodes(self) -> None:
        """Link group input sockets to the Principled BSDF inputs, and BSDF output to group output."""
        links = self.group_tree.links
        inp = self._input_node.outputs
        out = self._output_node.inputs
        # Connect group inputs to Principled BSDF (base color, alpha, metallic, roughness, emission strength)
        links.new(inp["IN-Color Map"], self._bsdf_node.inputs["Base Color"])
        links.new(inp["IN-Color Map Alpha"], self._bsdf_node.inputs["Alpha"])
        links.new(inp["IN-Metallic [red]"], self._bsdf_node.inputs["Metallic"])
        links.new(inp["IN-Roughness [green]"], self._bsdf_node.inputs["Roughness"])
        links.new(
            inp["IN-Emission [alpha]"], self._bsdf_node.inputs["Emission Strength"]
        )
        links.new(inp["IN-Normal Map"], self._normal_map_node.inputs["Color"])
        # Handle emission color differently in Blender 3 vs 4
        if bpy.app.version[0] == 3:
            # In Blender 3.x, Principled BSDF uses "Emission" input (color) for emissive color
            links.new(inp["IN-Emission [alpha]"], self._bsdf_node.inputs["Emission"])
        else:
            # In Blender 4.x, use Base Color map as the emission color (if desired for glowing materials)
            links.new(inp["IN-Color Map"], self._bsdf_node.inputs["Emission Color"])
        # Connect BSDF output to the group’s output socket
        links.new(self._bsdf_node.outputs["BSDF"], out["OUT-DRS Shader"])
        # Now link the node group (as a whole) to the material output in the outer material node tree
        self.material_output = self.material.node_tree.nodes.new(
            "ShaderNodeOutputMaterial"
        )
        self.material_output.location = Vector((400.0, 0.0))
        self.material.node_tree.links.new(
            self.group_node.outputs["OUT-DRS Shader"],
            self.material_output.inputs["Surface"],
        )

    def _create_outer_nodes(self) -> None:
        """Create image texture nodes in the material's node tree for Color, Parameter (or separate) and Normal maps."""
        nodes = self.material.node_tree.nodes
        links = self.material.node_tree.links
        # Color map texture
        self.color_tex_node = nodes.new("ShaderNodeTexImage")
        self.color_tex_node.label = "Color Map"
        self.color_tex_node.location = Vector((-800.0, 0.0))
        # Link color and alpha from color texture to group inputs
        links.new(
            self.color_tex_node.outputs["Color"], self.group_node.inputs["IN-Color Map"]
        )
        links.new(
            self.color_tex_node.outputs["Alpha"],
            self.group_node.inputs["IN-Color Map Alpha"],
        )
        # Parameter maps (combined or separate)
        if not self.use_separate_maps:
            # Single combined parameter map (RGBA channels)
            self.param_tex_node = nodes.new("ShaderNodeTexImage")
            self.param_tex_node.label = "Param Map (RGBA)"
            self.param_tex_node.location = Vector((-800.0, -350.0))
            # Separate RGB node to split channels
            separate_rgb = nodes.new("ShaderNodeSeparateColor")
            separate_rgb.label = "Split Metallic/Roughness"
            separate_rgb.location = Vector((-500.0, -350.0))
            # Link param texture color into Separate RGB
            links.new(
                self.param_tex_node.outputs["Color"], separate_rgb.inputs["Color"]
            )
            # R -> Metallic, G -> Roughness, Alpha -> Emission
            links.new(
                separate_rgb.outputs["Red"], self.group_node.inputs["IN-Metallic [red]"]
            )
            links.new(
                separate_rgb.outputs["Green"],
                self.group_node.inputs["IN-Roughness [green]"],
            )
            links.new(
                self.param_tex_node.outputs["Alpha"],
                self.group_node.inputs["IN-Emission [alpha]"],
            )
        else:
            # Separate texture nodes for Metallic, Roughness, Emission
            self.metallic_tex_node = nodes.new("ShaderNodeTexImage")
            self.metallic_tex_node.label = "Metallic Map (R)"
            self.metallic_tex_node.location = Vector((-800.0, -350.0))
            self.roughness_tex_node = nodes.new("ShaderNodeTexImage")
            self.roughness_tex_node.label = "Roughness Map (G)"
            self.roughness_tex_node.location = Vector((-800.0, -700.0))
            self.emission_tex_node = nodes.new("ShaderNodeTexImage")
            self.emission_tex_node.label = "Emission Map (A)"
            self.emission_tex_node.location = Vector((-800.0, -1050.0))
            # Link each map's color output to the respective group input
            links.new(
                self.metallic_tex_node.outputs["Color"],
                self.group_node.inputs["IN-Metallic [red]"],
            )
            links.new(
                self.roughness_tex_node.outputs["Color"],
                self.group_node.inputs["IN-Roughness [green]"],
            )
            links.new(
                self.emission_tex_node.outputs["Color"],
                self.group_node.inputs["IN-Emission [alpha]"],
            )
        # Normal map texture
        self.normal_tex_node = nodes.new("ShaderNodeTexImage")
        self.normal_tex_node.label = "Normal Map"
        self.normal_tex_node.location = Vector(
            (-800.0, -700 if not self.use_separate_maps else -1400)
        )
        # Link normal map color to group Normal Map input
        links.new(
            self.normal_tex_node.outputs["Color"],
            self.group_node.inputs["IN-Normal Map"],
        )

    def _layout_and_decorate_nodes(self) -> None:
        """Organize nodes into frames with labels and colors for visual clarity."""
        nodes = self.material.node_tree.nodes
        # Create frames for grouping related nodes
        frame_color = nodes.new("NodeFrame")
        frame_params = nodes.new("NodeFrame")
        frame_normal = nodes.new("NodeFrame")
        # Set frame labels as hints
        frame_color.label = "Color Map"
        frame_params.label = "Parameters (Metallic/Roughness/Emission)"
        frame_normal.label = "Normal Map"
        # Use custom colors for frames (optional aesthetic choice)
        frame_color.use_custom_color = True
        frame_color.color = (1.0, 0.9, 0.4)  # warm yellow
        frame_params.use_custom_color = True
        frame_params.color = (0.6, 0.9, 0.6)  # light green
        frame_normal.use_custom_color = True
        frame_normal.color = (0.6, 0.8, 1.0)  # light blue
        # Parent the relevant nodes to frames
        self.color_tex_node.parent = frame_color
        self.normal_tex_node.parent = frame_normal
        if not self.use_separate_maps:
            self.param_tex_node.parent = frame_params
            # Also frame the Separate RGB node with the param map
            separate_node = next(
                (n for n in nodes if n.name.startswith("Separate Color")), None
            )
            if separate_node:
                separate_node.parent = frame_params
        else:
            self.metallic_tex_node.parent = frame_params
            self.roughness_tex_node.parent = frame_params
            self.emission_tex_node.parent = frame_params

    # --- Texture assignment methods for user to call after initialization --- #
    def load_image(self, image_name: str, dir_path: str) -> bpy.types.Image:
        """Load an image by name from the directory (expects .dds by default)."""
        # Use Blender's image loader which checks for existing and supports DDS
        img = load_image(
            os.path.basename(image_name + ".dds"),
            dir_path,
            check_existing=True,
            place_holder=False,
            recursive=False,
        )
        return img

    def set_color_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the Color (albedo) map texture by name (without extension)."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.color_tex_node.image = img
            # Color maps contain color data, typically use sRGB (default), so no change needed

    def set_parameter_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the combined parameter map (RGBA) texture by name. Applicable if not using separate maps."""
        if self.use_separate_maps:
            raise RuntimeError(
                "DRSMaterial is in separate maps mode; use set_metallic_map, set_roughness_map, set_emission_map instead."
            )
        img = self.load_image(texture_name, dir_path)
        if img:
            self.param_tex_node.image = img
            # Treat combined parameter maps as non-color data (grayscale channels)&#8203;:contentReference[oaicite:4]{index=4}
            img.colorspace_settings.name = "Non-Color"

    def set_metallic_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the Metallic map (grayscale) texture by name. Applicable if using separate maps."""
        if not self.use_separate_maps:
            raise RuntimeError(
                "DRSMaterial is in combined map mode; use set_parameter_map instead of individual maps."
            )
        img = self.load_image(texture_name, dir_path)
        if img:
            self.metallic_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"  # metallic is non-color data&#8203;:contentReference[oaicite:5]{index=5}

    def set_roughness_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the Roughness map (grayscale) texture by name. Applicable if using separate maps."""
        if not self.use_separate_maps:
            raise RuntimeError(
                "DRSMaterial is in combined map mode; use set_parameter_map instead of individual maps."
            )
        img = self.load_image(texture_name, dir_path)
        if img:
            self.roughness_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"  # roughness is non-color data

    def set_emission_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the Emission intensity map (grayscale) texture by name. Applicable if using separate maps."""
        if not self.use_separate_maps:
            raise RuntimeError(
                "DRSMaterial is in combined map mode; use set_parameter_map instead."
            )
        img = self.load_image(texture_name, dir_path)
        if img:
            self.emission_tex_node.image = img
            img.colorspace_settings.name = (
                "Non-Color"  # emission mask is non-color data
            )

    def set_normal_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the Normal map texture by name."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.normal_tex_node.image = img
            # Normal maps should be non-color data to prevent color space corrections
            img.colorspace_settings.name = "Non-Color"
