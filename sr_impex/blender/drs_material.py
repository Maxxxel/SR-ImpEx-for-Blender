"""DRS material creation; v2 artist controls use the audited handler schema."""
import os
import bpy
from bpy_extras.image_utils import load_image
from sr_impex.blender.material_preview import build_material

class DRSMaterial:
    def __init__(self, material_name: str, modules: list = None):
        self.modules = modules or []
        # Each imported mesh has independent artist settings; never clear an
        # existing artist material just because its generated name matches.
        self.material = bpy.data.materials.new(material_name)
        self.group_node, textures = build_material(self.material)
        self.group_tree = self.group_node.node_tree
        self.color_tex_node = textures[0x64666673]
        self.param_tex_node = textures[0x7370636c]
        self.normal_tex_node = textures[0x6e726d73]
        self.refraction_tex_node = textures[0x7263636f]
        self.flu_tex_node_layer_1 = textures[0x63737432]
        self.flu_tex_node_layer_2 = self.flu_tex_node_layer_1
        self.refraction_color_node = self.material.node_tree.nodes['Refraction Color']
        self.bsdf_node = self.group_tree.nodes['DRS Shader']
        self.sep_metallic_tex_node = self.material.node_tree.nodes['Separate Metallic']
        self.sep_roughness_tex_node = self.material.node_tree.nodes['Separate Roughness']
        self.sep_emission_tex_node = self.material.node_tree.nodes['Separate Emission']
        self.sep_flu_mask_tex_node = self.material.node_tree.nodes['Separate Mask']
        from sr_impex.blender.editors.material_editor import initialize_new
        initialize_new(self.material)

    def load_image(self, image_name: str, dir_path: str) -> bpy.types.Image:
        """Loads an image from a directory (e.g., "texture.dds")."""
        if not image_name: # Handle empty texture names
            return None
        if not image_name.endswith(".dds"):
            image_name += ".dds"

        try:
            img = load_image(
                os.path.basename(image_name),
                dir_path,
                check_existing=True,
                place_holder=False,
                recursive=False,
            )
            return img
        except Exception as e:
            print(f"Warning: Could not load image {image_name} from {dir_path}. {e}")
            return None

    def set_color_map(self, texture_name: str, dir_path: str, alpha_test: bool, use_decal_mode: bool = None) -> None:
        """Assigns the Color (albedo) map."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.color_tex_node.image = img
            # Decal Mode is > than alpha test
            if use_decal_mode is not None:
                img.alpha_mode = 'CHANNEL_PACKED' if use_decal_mode else 'NONE'
            else:
                img.alpha_mode = 'CHANNEL_PACKED' if alpha_test else 'NONE'

    def set_parameter_map(self, texture_name: str, dir_path: str) -> None:
        """Assigns the combined parameter map (_par)."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.param_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"
            img.alpha_mode = "CHANNEL_PACKED"

    def set_normal_map(self, texture_name: str, dir_path: str) -> None:
        """Assigns the Normal map (_nor)."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.normal_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"

    def set_refraction_map(self, texture_name: str, dir_path: str, rgb: list[float]) -> None:
        """Assigns the Refraction map (_ref) and its color."""
        img = self.load_image(texture_name, dir_path)
        if img:
            self.refraction_tex_node.image = img
            img.colorspace_settings.name = "Non-Color"
            # Refraction implies transparency

        if rgb and len(rgb) == 3:
            self.refraction_color_node.outputs[0].default_value = tuple(rgb) + (1.0,)

    def set_flumap(self, texture_name: str, dir_path: str) -> None:
        """Assigns the tileable Fluid map (_flu)."""
        img = self.load_image(texture_name, dir_path)
        if img:
            img.colorspace_settings.name = "sRGB"
            self.flu_tex_node_layer_1.image = img
            self.flu_tex_node_layer_2.image = img

    def create_wind_nodes(self, mesh_object: bpy.types.Object) -> None:
        """
        Creates the Geometry Nodes modifier for the wind effect.
        """
        if mesh_object is None or mesh_object.type != 'MESH':
            print("Warning: A valid mesh object must be provided for wind effect.")
            return

        if "WindEffect" in mesh_object.modifiers:
            return # Already exists

        modifier = mesh_object.modifiers.new(name="WindEffect", type="NODES")
        node_group = bpy.data.node_groups.new("WindEffectTree", "GeometryNodeTree")

        if bpy.app.version[0] >= 4:
            node_group.interface.new_socket(name="Geometry", in_out ="INPUT", socket_type="NodeSocketGeometry")
            node_group.interface.new_socket(name="Geometry", in_out ="OUTPUT", socket_type="NodeSocketGeometry")
        else:
            node_group.inputs.new("NodeSocketGeometry", "Geometry")
            node_group.outputs.new("NodeSocketGeometry", "Geometry")

        modifier.node_group = node_group
        links = node_group.links

        inp = node_group.nodes.new("NodeGroupInput")
        inp.location = (0, 0)

        outp = node_group.nodes.new("NodeGroupOutput")
        outp.location = (1350, -300)

        scene_time = node_group.nodes.new("GeometryNodeInputSceneTime")
        scene_time.location = (0, -300)

        mult_node = node_group.nodes.new("ShaderNodeMath")
        mult_node.name = "Wind Response"
        mult_node.label = "Wind Response"
        mult_node.location = (150, -300)
        mult_node.operation = "MULTIPLY"
        mult_node.inputs[1].default_value = 0.0
        links.new(scene_time.outputs["Seconds"], mult_node.inputs[0])

        noise = node_group.nodes.new("ShaderNodeTexNoise")
        noise.location = (300, -300)
        noise.noise_dimensions = '1D'
        links.new(mult_node.outputs["Value"], noise.inputs["W"])

        subtract = node_group.nodes.new("ShaderNodeVectorMath")
        subtract.location = (450, -300)
        subtract.operation = "SUBTRACT"
        subtract.inputs[1].default_value = (0.5, 0.5, 0.5)
        links.new(noise.outputs["Color"], subtract.inputs[0])

        sep_xyz = node_group.nodes.new("ShaderNodeSeparateXYZ")
        sep_xyz.location = (600, -300)
        links.new(subtract.outputs["Vector"], sep_xyz.inputs["Vector"])

        comb_xyz = node_group.nodes.new("ShaderNodeCombineXYZ")
        comb_xyz.location = (750, -300)
        links.new(sep_xyz.outputs["X"], comb_xyz.inputs["X"])

        pos_node = node_group.nodes.new("GeometryNodeInputPosition")
        pos_node.location = (450, 0)

        sep_y = node_group.nodes.new("ShaderNodeSeparateXYZ")
        sep_y.location = (600, 0)
        links.new(pos_node.outputs["Position"], sep_y.inputs["Vector"])

        map_range = node_group.nodes.new("ShaderNodeMapRange")
        map_range.name = "Wind Height"
        map_range.label = "Wind Height"
        map_range.location = (750, 0)
        map_range.data_type = 'FLOAT'
        map_range.clamp = True

        min_y, max_y = 0.0, 1.0
        if mesh_object.bound_box:
            y_values = [corner[1] for corner in mesh_object.bound_box]
            min_y = min(y_values)
            max_y = max(y_values)

        map_range.inputs["From Min"].default_value = 0.0
        map_range.inputs["From Max"].default_value = max_y - min_y if (max_y - min_y) > 0 else 1.0
        map_range.inputs["To Min"].default_value = 0.0
        map_range.inputs["To Max"].default_value = 1.0
        links.new(sep_y.outputs["Y"], map_range.inputs["Value"])

        scale_node = node_group.nodes.new("ShaderNodeVectorMath")
        scale_node.location = (900, -300)
        scale_node.operation = "SCALE"
        links.new(comb_xyz.outputs["Vector"], scale_node.inputs[0])
        links.new(map_range.outputs["Result"], scale_node.inputs['Scale'])

        strength_scale = node_group.nodes.new("ShaderNodeVectorMath")
        strength_scale.location = (1050, -300)
        strength_scale.operation = "SCALE"
        strength_scale.inputs[1].default_value = (1.0, 1.0, 1.0)
        links.new(scale_node.outputs[0], strength_scale.inputs[0])

        set_pos = node_group.nodes.new("GeometryNodeSetPosition")
        set_pos.location = (1200, -300)
        links.new(inp.outputs[0], set_pos.inputs["Geometry"])
        links.new(strength_scale.outputs[0], set_pos.inputs["Offset"])
        links.new(set_pos.outputs["Geometry"], outp.inputs[0])
