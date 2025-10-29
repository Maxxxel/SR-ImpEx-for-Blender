from audioop import mul
from email.mime import nonmultipart
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

    def __init__(
        self, material_name: str, use_separate_maps: bool = False, modules: list = None
    ) -> None:
        """Initialize the DRS Material with node setup.
        If use_separate_maps is True, expects separate Metallic, Roughness, Emission maps.
        The 'modules' list controls which texture modules to include.
        Defaults to all: ["_col", "_nor", "_par", "_ref"].
        """
        self.use_separate_maps = use_separate_maps
        self.modules = (
            modules if modules is not None else ["_col", "_nor", "_par", "_ref"]
        )
        # References to important nodes (for later image assignment)
        self.color_tex_node = None
        self.param_tex_node = None
        self.metallic_tex_node = None
        self.roughness_tex_node = None
        self.emission_tex_node = None
        self.normal_tex_node = None
        self.refraction_tex_node = None
        self.refraction_color_node = None
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
        sockets = []
        if "_col" in self.modules:
            sockets.append(
                {"name": "IN-Color Map", "type": SOCKET_COLOR, "in_out": "INPUT"}
            )
            sockets.append(
                {"name": "IN-Color Map Alpha", "type": SOCKET_FLOAT, "in_out": "INPUT"}
            )
        if "_par" in self.modules:
            sockets.append(
                {"name": "IN-Metallic [red]", "type": SOCKET_COLOR, "in_out": "INPUT"}
            )
            sockets.append(
                {
                    "name": "IN-Roughness [green]",
                    "type": SOCKET_COLOR,
                    "in_out": "INPUT",
                }
            )
            sockets.append(
                {"name": "IN-Emission [alpha]", "type": SOCKET_COLOR, "in_out": "INPUT"}
            )
        if "_nor" in self.modules:
            sockets.append(
                {"name": "IN-Normal Map", "type": SOCKET_NORMAL, "in_out": "INPUT"}
            )
        if "_ref" in self.modules:
            sockets.append(
                {"name": "IN-Refraction Color", "type": SOCKET_COLOR, "in_out": "INPUT"}
            )
            sockets.append(
                {"name": "IN-Refraction Map", "type": SOCKET_FLOAT, "in_out": "INPUT"}
            )
        sockets.append(
            {"name": "DRS-Output", "type": SOCKET_SHADER, "in_out": "OUTPUT"}
        )

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
        self._input_node = nodes.new("NodeGroupInput")
        self._input_node.location = Vector((-1000.0, 0.0))
        # Create an Output Group
        self._output_node = nodes.new("NodeGroupOutput")
        self._output_node.location = Vector((800.0, 0.0))
        # Create the main shader (Principled BSDF) inside the group
        self._bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
        self._bsdf_node.location = Vector((0.0, 0.0))
        self._bsdf_node.inputs["IOR"].default_value = 1.0
        if bpy.app.version[0] == 3:
            self._bsdf_node.inputs["Specular"].default_value = 0.0
        if "_nor" in self.modules:
            self._normal_map_node = nodes.new("ShaderNodeNormalMap")
            self._normal_map_node.location = Vector((-300.0, -300.0))
            links.new(
                self._normal_map_node.outputs["Normal"],
                self._bsdf_node.inputs["Normal"],
            )
        if "_ref" in self.modules:
            self.invert_refraction_map_node = nodes.new("ShaderNodeInvert")
            self.invert_refraction_map_node.label = "Invert Refraction Map"
            self.invert_refraction_map_node.location = Vector((-300.0, 300.0))
            self.transparent_bsdf = nodes.new("ShaderNodeBsdfTransparent")
            self.transparent_bsdf.location = Vector((-300.0, 0.0))
            self.refraction_bsdf = nodes.new("ShaderNodeBsdfGlass")
            self.refraction_bsdf.inputs["IOR"].default_value = 1.5
            self.refraction_bsdf.location = Vector((-300.0, -300.0))
            self.refraction_bsdf.distribution = "BECKMANN"
            self.mix_transparent_refraction = nodes.new("ShaderNodeMixShader")
            self.mix_transparent_refraction.location = Vector((-100.0, 0.0))
            self.final_mix_shader = nodes.new("ShaderNodeMixShader")
            self.final_mix_shader.location = Vector((100.0, 0.0))
            # enable backface culling for refraction
            self.material.use_backface_culling = True

    def _link_group_nodes(self) -> None:
        """Link group input sockets to the Principled BSDF inputs, and BSDF output to group output."""
        links = self.group_tree.links
        inp = self._input_node.outputs
        out = self._output_node.inputs
        # Connect base inputs to Principled BSDF
        if "_col" in self.modules:
            links.new(inp["IN-Color Map"], self._bsdf_node.inputs["Base Color"])
            links.new(inp["IN-Color Map Alpha"], self._bsdf_node.inputs["Alpha"])
        if "_par" in self.modules:
            links.new(inp["IN-Metallic [red]"], self._bsdf_node.inputs["Metallic"])
            links.new(inp["IN-Roughness [green]"], self._bsdf_node.inputs["Roughness"])
            links.new(
                inp["IN-Emission [alpha]"], self._bsdf_node.inputs["Emission Strength"]
            )
            if bpy.app.version[0] == 3:
                links.new(
                    inp["IN-Emission [alpha]"], self._bsdf_node.inputs["Emission"]
                )
            else:
                links.new(inp["IN-Color Map"], self._bsdf_node.inputs["Emission Color"])
        if "_nor" in self.modules:
            links.new(inp["IN-Normal Map"], self._normal_map_node.inputs["Color"])
            links.new(
                self._normal_map_node.outputs["Normal"],
                self._bsdf_node.inputs["Normal"],
            )
        if "_ref" in self.modules:
            links.new(inp["IN-Refraction Color"], self.refraction_bsdf.inputs["Color"])
            links.new(inp["IN-Refraction Color"], self.transparent_bsdf.inputs["Color"])
            links.new(
                inp["IN-Roughness [green]"], self.refraction_bsdf.inputs["Roughness"]
            )
            links.new(
                self._normal_map_node.outputs["Normal"],
                self.refraction_bsdf.inputs["Normal"],
            )
            links.new(
                inp["IN-Refraction Map"],
                self.invert_refraction_map_node.inputs["Color"],
            )
            links.new(
                self.invert_refraction_map_node.outputs["Color"],
                self.final_mix_shader.inputs["Fac"],
            )
            links.new(
                self.transparent_bsdf.outputs["BSDF"],
                self.mix_transparent_refraction.inputs[1],
            )
            links.new(
                self.refraction_bsdf.outputs["BSDF"],
                self.mix_transparent_refraction.inputs[2],
            )
            # Link the final mix shader to the BSDF output
            links.new(
                self.mix_transparent_refraction.outputs["Shader"],
                self.final_mix_shader.inputs[1],
            )
            links.new(self._bsdf_node.outputs["BSDF"], self.final_mix_shader.inputs[2])
            links.new(self.final_mix_shader.outputs["Shader"], out["DRS-Output"])
        else:
            links.new(self._bsdf_node.outputs["BSDF"], out["DRS-Output"])

    def _create_outer_nodes(self) -> None:
        nodes = self.material.node_tree.nodes
        links = self.material.node_tree.links
        base_x = -800.0
        current_y = 0.0
        delta_y = -350.0

        # _col module: Color Map
        if "_col" in self.modules:
            self.color_tex_node = nodes.new("ShaderNodeTexImage")
            self.color_tex_node.label = "Color Map"
            self.color_tex_node.location = Vector((base_x, current_y))
            links.new(
                self.color_tex_node.outputs["Color"],
                self.group_node.inputs["IN-Color Map"],
            )
            # Alpha connection will be managed by material_flow_editor based on Enable Alpha Test flag
            # By default, connect it (will be disconnected if flag is off)
            links.new(
                self.color_tex_node.outputs["Alpha"],
                self.group_node.inputs["IN-Color Map Alpha"],
            )
            current_y += delta_y

        # _par module: Parameter Map
        if "_par" in self.modules:
            if not self.use_separate_maps:
                self.param_tex_node = nodes.new("ShaderNodeTexImage")
                self.param_tex_node.label = "Param Map (RGBA)"
                self.param_tex_node.location = Vector((base_x, current_y))
                separate_rgb = nodes.new("ShaderNodeSeparateColor")
                separate_rgb.label = "Split Metallic/Roughness"
                separate_rgb.location = Vector((base_x + 300, current_y))
                links.new(
                    self.param_tex_node.outputs["Color"], separate_rgb.inputs["Color"]
                )
                links.new(
                    separate_rgb.outputs["Red"],
                    self.group_node.inputs["IN-Metallic [red]"],
                )
                links.new(
                    separate_rgb.outputs["Green"],
                    self.group_node.inputs["IN-Roughness [green]"],
                )
                links.new(
                    self.param_tex_node.outputs["Alpha"],
                    self.group_node.inputs["IN-Emission [alpha]"],
                )
                current_y += delta_y
            else:
                self.metallic_tex_node = nodes.new("ShaderNodeTexImage")
                self.metallic_tex_node.label = "Metallic Map (R)"
                self.metallic_tex_node.location = Vector((base_x, current_y))
                links.new(
                    self.metallic_tex_node.outputs["Color"],
                    self.group_node.inputs["IN-Metallic [red]"],
                )
                current_y += delta_y

                self.roughness_tex_node = nodes.new("ShaderNodeTexImage")
                self.roughness_tex_node.label = "Roughness Map (G)"
                self.roughness_tex_node.location = Vector((base_x, current_y))
                links.new(
                    self.roughness_tex_node.outputs["Color"],
                    self.group_node.inputs["IN-Roughness [green]"],
                )
                current_y += delta_y

                self.emission_tex_node = nodes.new("ShaderNodeTexImage")
                self.emission_tex_node.label = "Emission Map (A)"
                self.emission_tex_node.location = Vector((base_x, current_y))
                links.new(
                    self.emission_tex_node.outputs["Color"],
                    self.group_node.inputs["IN-Emission [alpha]"],
                )
                current_y += delta_y

        # _nor module: Normal Map
        if "_nor" in self.modules:
            self.normal_tex_node = nodes.new("ShaderNodeTexImage")
            self.normal_tex_node.label = "Normal Map"
            self.normal_tex_node.location = Vector((base_x, current_y))
            links.new(
                self.normal_tex_node.outputs["Color"],
                self.group_node.inputs["IN-Normal Map"],
            )
            current_y += delta_y

        # _ref module: Refraction Map and Refraction Color
        if "_ref" in self.modules:
            self.refraction_tex_node = nodes.new("ShaderNodeTexImage")
            self.refraction_tex_node.label = "Refraction Map"
            self.refraction_tex_node.location = Vector((base_x, current_y))
            links.new(
                self.refraction_tex_node.outputs["Alpha"],
                self.group_node.inputs["IN-Refraction Map"],
            )
            current_y += delta_y

            self.refraction_color_node = nodes.new("ShaderNodeRGB")
            self.refraction_color_node.label = "Refraction Color"
            self.refraction_color_node.location = Vector((base_x, current_y))
            self.refraction_color_node.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            links.new(
                self.refraction_color_node.outputs["Color"],
                self.group_node.inputs["IN-Refraction Color"],
            )
            current_y += delta_y

        # Output node for the material
        output_node = nodes.new("ShaderNodeOutputMaterial")
        output_node.location = Vector((800.0, 0.0))
        links.new(self.group_node.outputs["DRS-Output"], output_node.inputs["Surface"])

    def _layout_and_decorate_nodes(self) -> None:
        nodes = self.material.node_tree.nodes
        frames = {}
        # Create frames based on enabled modules.
        if "_col" in self.modules:
            frame_color = nodes.new("NodeFrame")
            frame_color.label = "Color Map"
            frame_color.use_custom_color = True
            frame_color.color = (1.0, 0.9, 0.4)  # warm yellow
            frames["_col"] = frame_color
        if "_par" in self.modules:
            frame_par = nodes.new("NodeFrame")
            frame_par.label = "Parameters (Metallic/Roughness/Emission)"
            frame_par.use_custom_color = True
            frame_par.color = (0.6, 0.9, 0.6)  # light green
            frames["_par"] = frame_par
        if "_nor" in self.modules:
            frame_nor = nodes.new("NodeFrame")
            frame_nor.label = "Normal Map"
            frame_nor.use_custom_color = True
            frame_nor.color = (0.6, 0.8, 1.0)  # light blue
            frames["_nor"] = frame_nor
        if "_ref" in self.modules:
            frame_ref = nodes.new("NodeFrame")
            frame_ref.label = "Refraction (Glass/Ice)"
            frame_ref.use_custom_color = True
            frame_ref.color = (0.8, 0.8, 1.0)  # light purple/blue
            frames["_ref"] = frame_ref

        # Parent nodes to their respective frames.
        if "_col" in self.modules and self.color_tex_node:
            self.color_tex_node.parent = frames["_col"]
        if "_par" in self.modules:
            if not self.use_separate_maps:
                if self.param_tex_node:
                    self.param_tex_node.parent = frames["_par"]
                # Parent the Separate RGB node if present.
                separate_node = next(
                    (n for n in nodes if "Separate Color" in n.name), None
                )
                if separate_node:
                    separate_node.parent = frames["_par"]
            else:
                if self.metallic_tex_node:
                    self.metallic_tex_node.parent = frames["_par"]
                if self.roughness_tex_node:
                    self.roughness_tex_node.parent = frames["_par"]
                if self.emission_tex_node:
                    self.emission_tex_node.parent = frames["_par"]
        if "_nor" in self.modules and self.normal_tex_node:
            self.normal_tex_node.parent = frames["_nor"]
        if "_ref" in self.modules:
            if self.refraction_tex_node:
                self.refraction_tex_node.parent = frames["_ref"]
            if self.refraction_color_node:
                self.refraction_color_node.parent = frames["_ref"]

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

    def set_color_map(self, texture_name: str, dir_path: str, alpha_test: bool) -> None:
        """Assign the Color (albedo) map texture by name (without extension)."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.color_tex_node.image = img
            self.color_tex_node.image.alpha_mode = 'STRAIGHT' if alpha_test else 'NONE' # 'Straight' if using alpha test, else 'NONE'

    def set_parameter_map(self, texture_name: str, dir_path: str) -> None:
        """Assign the combined parameter map (RGBA) texture by name. Applicable if not using separate maps."""
        if self.use_separate_maps:
            raise RuntimeError(
                "DRSMaterial is in separate maps mode; use set_metallic_map, set_roughness_map, set_emission_map instead."
            )
        img = self.load_image(texture_name, dir_path)
        if img:
            self.param_tex_node.image = img
            # Treat combined parameter maps as non-color data
            img.colorspace_settings.name = "Non-Color"
            img.alpha_mode = "CHANNEL_PACKED"

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

    def set_refraction_map(
        self, texture_name: str, dir_path: str, rgb: list[float]
    ) -> None:
        """Load and assign the refraction texture. Its alpha controls transparency."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.refraction_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"
        if rgb:
            argb = tuple(rgb) + (1.0,)
            self.refraction_color_node.outputs[0].default_value = argb

    def create_wind_nodes(self, mesh_object: bpy.types.Object) -> None:
        """Uses Geometry Nodes to create a wind effect on the material's assigned object."""
        if mesh_object is None or mesh_object.type != 'MESH':
            raise ValueError("A valid mesh object must be provided for wind effect.")
            
        # Create the new GeometryNodes modifier
        modifier = mesh_object.modifiers.new(name="WindEffect", type="NODES")
        node_group = bpy.data.node_groups.new("WindEffectTree", "GeometryNodeTree")
        node_group.interface.new_socket(name="Geometry In", in_out ="INPUT", socket_type="NodeSocketGeometry")
        node_group.interface.new_socket(name="Geometry Out", in_out ="OUTPUT", socket_type="NodeSocketGeometry")
        links = node_group.links
        # Input Node
        input_node = node_group.nodes.new("NodeGroupInput")
        input_node.location = (0, 0)
        # Output Node
        output_node = node_group.nodes.new("NodeGroupOutput")
        output_node.location = (1350, -300)
        # Create a scene time node
        scene_time = node_group.nodes.new("GeometryNodeInputSceneTime")
        scene_time.location = (0, -300)
        # Create a math (multiply) node
        multiply_node = node_group.nodes.new("ShaderNodeMath")
        multiply_node.name = "Wind Response"
        multiply_node.location = (150, -300)
        multiply_node.operation = "MULTIPLY"
        multiply_node.inputs["Value"].default_value = 0.0
        links.new(scene_time.outputs["Seconds"], multiply_node.inputs[0])
        # Create a noise texture node
        noise_texture = node_group.nodes.new("ShaderNodeTexNoise")
        noise_texture.location = (300, -300)
        noise_texture.noise_dimensions = '1D'
        links.new(multiply_node.outputs["Value"], noise_texture.inputs["W"])
        # Create a Vector (subtract) node to center noise around 0
        subtract_node = node_group.nodes.new("ShaderNodeVectorMath")
        subtract_node.location = (450, -300)
        subtract_node.operation = "SUBTRACT"
        links.new(noise_texture.outputs["Color"], subtract_node.inputs[0])
        # Create a separate XYZ node
        separate_xyz = node_group.nodes.new("ShaderNodeSeparateXYZ")
        separate_xyz.location = (600, -300)
        links.new(subtract_node.outputs["Vector"], separate_xyz.inputs["Vector"])
        # Create a combine XYZ node for offset
        combine_xyz = node_group.nodes.new("ShaderNodeCombineXYZ")
        combine_xyz.location = (750, -300)
        combine_xyz.inputs["Y"].default_value = 0.0
        combine_xyz.inputs["Z"].default_value = 0.0
        links.new(separate_xyz.outputs["X"], combine_xyz.inputs["X"])
        # Create a Position node
        position_node = node_group.nodes.new("GeometryNodeInputPosition")
        position_node.location = (450, 0)
        # Create a second separate XYZ node for original position
        separate_y = node_group.nodes.new("ShaderNodeSeparateXYZ")
        separate_y.location = (600, 0)
        links.new(position_node.outputs["Position"], separate_y.inputs["Vector"])
        # Create a map range node to control wind height
        y_values = [corner[1] for corner in mesh_object.bound_box]
        min_y = min(y_values)
        max_y = max(y_values)
        map_range = node_group.nodes.new("ShaderNodeMapRange")
        map_range.name = "Wind Height"
        map_range.location = (750, 0)
        map_range.inputs["From Min"].default_value = 0.0
        map_range.inputs["From Max"].default_value = (max_y - min_y)
        map_range.inputs["To Min"].default_value = 0.0
        map_range.inputs["To Max"].default_value = 1.0
        links.new(separate_y.outputs["Y"], map_range.inputs["Value"])
        # Create a Scale node
        scale_node = node_group.nodes.new("ShaderNodeVectorMath")
        scale_node.location = (900, -300)
        scale_node.operation = "SCALE"
        links.new(combine_xyz.outputs["Vector"], scale_node.inputs["Vector"])
        links.new(map_range.outputs["Result"], scale_node.inputs["Scale"])
        # Create a second control scale node for wind strength
        control_scale = node_group.nodes.new("ShaderNodeVectorMath")
        control_scale.location = (1050, -300)
        control_scale.operation = "SCALE"
        control_scale.inputs["Scale"].default_value = 1.0
        links.new(scale_node.outputs["Vector"], control_scale.inputs["Vector"])
        # Create a final set position node
        set_position = node_group.nodes.new("GeometryNodeSetPosition")
        set_position.location = (1200, -300)
        links.new(input_node.outputs["Geometry In"], set_position.inputs["Geometry"])
        links.new(set_position.outputs["Geometry"], output_node.inputs["Geometry Out"])
        links.new(control_scale.outputs["Vector"], set_position.inputs["Offset"])
        # Finish linking input and output
        modifier.node_group = node_group
