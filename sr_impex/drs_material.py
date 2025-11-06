# sr_impex/drs_material.py
import os
import bpy
from bpy_extras.image_utils import load_image

# Socket type constants for clarity
SOCKET_SHADER = "NodeSocketShader"
SOCKET_COLOR = "NodeSocketColor"
SOCKET_VECTOR = "NodeSocketVector"
SOCKET_FLOAT = "NodeSocketFloat"
SOCKET_BOOL = "NodeSocketBool"


class DRSMaterial:
    """
    Creates and manages a single, unified DRS Shader Node Group.

    This class builds a material by linking texture nodes to a central
    "AIO_DRS_Engine" node group.

    The node group is a pure data-processing engine. It takes in map data
    and outputs the final PBR values and fluid animation vectors.

    All texture nodes, the Principled BSDF, and final mixing are
    handled *outside* the group, in the main material tree.
    """

    def __init__(self, material_name: str, modules: list = None) -> None:
        self.modules = modules if modules is not None else []

        # --- Exposed Texture Nodes for Importer ---
        self.color_tex_node = None
        self.param_tex_node = None
        self.flu_tex_node_L1 = None
        self.flu_tex_node_L2 = None
        self.normal_tex_node = None
        self.refraction_tex_node = None

        # --- Artist-Specific Texture Nodes ---
        self.sep_metallic_tex_node = None
        self.sep_roughness_tex_node = None
        self.sep_emission_tex_node = None
        self.sep_flu_mask_tex_node = None

        # --- Internal Node References ---
        self.material = None
        self.group_tree = None           # The NodeTree (template)
        self.group_node = None           # The ShaderNodeGroup in the material
        self.bsdf_node = None            # The main Principled BSDF

        self._create_material(material_name)
        self._get_or_create_aio_engine_group()
        self._create_material_nodes()
        self._link_material_nodes()
        self._layout_outer_nodes()

    def _create_material(self, material_name: str) -> None:
        """Create a new material (or get existing) and set basic settings."""
        mat = bpy.data.materials.get(material_name)
        if mat is None:
            mat = bpy.data.materials.new(material_name)

        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        mat.blend_method = "CLIP"
        if bpy.app.version < (4, 3):
            mat.shadow_method = "NONE"
        self.material = mat

    def _get_or_create_aio_engine_group(self) -> None:
        """
        Finds or creates the master "AIO_DRS_Engine" NodeTree template.
        This group is a data-only processor.
        """
        group_name = "AIO_DRS_Engine"
        base_tree = bpy.data.node_groups.get(group_name)

        rebuild = False
        if base_tree:
            # Check for a key output. If it's "Shader", the old design is wrong.
            uses_shader = base_tree.get_output_node('ALL')
            if uses_shader:
                rebuild = True

        if base_tree is None or rebuild:
            if base_tree:
                bpy.data.node_groups.remove(base_tree)

            base_tree = bpy.data.node_groups.new(group_name, type="ShaderNodeTree")
            self._build_aio_engine_group_internals(base_tree)

        self.group_tree = base_tree

    def _build_aio_engine_group_internals(self, tree: bpy.types.NodeTree) -> None:
        """
        Builds the *internal* logic for the "AIO_DRS_Engine" group.
        It only processes and outputs data, no shaders.
        """
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        def_in = self._def_socket_in
        def_out = self._def_socket_out

        # --- 1. Define Group Interface ---
        inp = nodes.new("NodeGroupInput")
        inp.location = (-2500, 500)
        outp = nodes.new("NodeGroupOutput")
        outp.location = (2000, 0)

        # Inputs
        def_in(tree, "Use Separate Maps", SOCKET_BOOL, 0)
        def_in(tree, "Parameter Map", SOCKET_COLOR, (0.0, 0.0, 0.0, 0.0))
        def_in(tree, "Parameter Map - Alpha", SOCKET_FLOAT, 0.0)
        def_in(tree, "Sep. Metallic", SOCKET_FLOAT, 0.0)
        def_in(tree, "Sep. Roughness", SOCKET_FLOAT, 0.8)
        def_in(tree, "Sep. Emission", SOCKET_FLOAT, 0.0)
        def_in(tree, "Sep. Flu Mask", SOCKET_FLOAT, 0.0)
        def_in(tree, "Normal Map", SOCKET_VECTOR)
        def_in(tree, "Refraction Map", SOCKET_COLOR, (0.0, 0.0, 0.0, 0.0))
        def_in(tree, "Refraction Color", SOCKET_COLOR, (1.0, 1.0, 1.0, 1.0))
        

        # Flow Parameters
        def_in(tree, "MinSpeed", SOCKET_VECTOR)
        def_in(tree, "MaxSpeed", SOCKET_VECTOR)
        def_in(tree, "Frequency", SOCKET_VECTOR)
        def_in(tree, "Scale", SOCKET_VECTOR, (1.0, 1.0, 1.0))

        # Outputs
        def_out(tree, "Metallic", SOCKET_FLOAT)
        def_out(tree, "Roughness", SOCKET_FLOAT)
        def_out(tree, "Emission", SOCKET_FLOAT)
        def_out(tree, "Flu Mask", SOCKET_FLOAT)
        def_out(tree, "Normal", SOCKET_VECTOR)
        def_out(tree, "Refraction BSDF", SOCKET_SHADER)

        # Fluid Animation Outputs
        # if "_par" in self.modules:
        def_out(tree, "Flu Offset (Layer 1)", SOCKET_VECTOR)
        def_out(tree, "Flu Offset (Layer 2)", SOCKET_VECTOR)
        def_out(tree, "Flu Crossfade", SOCKET_FLOAT)

        # --- 2. Build Fluid Animation Logic ("_par" module) ---
        # if "_par" in self.modules:
        # This function is now self-contained and just links to inputs/outputs
        self._create_flu_animation_nodes(tree, inp, outp)

        # --- 3. Build PBR Parameter Switching Logic ---

        # Separate the Parameter Map
        sep_param = nodes.new("ShaderNodeSeparateColor")
        sep_param.label = "Split Parameter Map"
        sep_param.location = (-2200, 200)
        links.new(inp.outputs["Parameter Map"], sep_param.inputs[0])
        
        # Refraction Map Range
        map_range_ref = nodes.new("ShaderNodeMapRange")
        map_range_ref.label = "Refraction Map Range"
        map_range_ref.location = (-1700, 900)
        # 0.0, 1.0, 1.0, 0.96
        map_range_ref.inputs['From Min'].default_value = 0.0
        map_range_ref.inputs['From Max'].default_value = 1.0
        map_range_ref.inputs['To Min'].default_value = 1.0
        map_range_ref.inputs['To Max'].default_value = 0.96
        links.new(inp.outputs["Refraction Map"], map_range_ref.inputs['Value'])
        
        # Refraction BSDF
        # We use Beckmann
        refraction_bsdf = nodes.new("ShaderNodeBsdfGlass")
        refraction_bsdf.label = "Refraction BSDF"
        refraction_bsdf.location = (-1200, 900)
        refraction_bsdf.distribution = 'BECKMANN'
        refraction_bsdf.inputs["Roughness"].default_value = 1.0
        links.new(inp.outputs["Refraction Color"], refraction_bsdf.inputs["Color"])
        links.new(map_range_ref.outputs['Result'], refraction_bsdf.inputs["IOR"])
        links.new(refraction_bsdf.outputs['BSDF'], outp.inputs["Refraction BSDF"])

        # Mix Metallic
        mix_met = nodes.new("ShaderNodeMix")
        mix_met.data_type = 'FLOAT'
        mix_met.label = "Mix Metallic"
        mix_met.location = (-1700, 600)
        links.new(inp.outputs["Use Separate Maps"], mix_met.inputs['Factor']) # Fac
        links.new(sep_param.outputs["Red"], mix_met.inputs['A'])        # A (False)
        links.new(inp.outputs["Sep. Metallic"], mix_met.inputs['B'])    # B (True)
        links.new(mix_met.outputs['Result'], outp.inputs["Metallic"])        # Link to Group Output

        # Mix Roughness
        mix_rough = nodes.new("ShaderNodeMix")
        mix_rough.data_type = 'FLOAT'
        mix_rough.label = "Mix Roughness"
        mix_rough.location = (-1700, 400)
        links.new(inp.outputs["Use Separate Maps"], mix_rough.inputs['Factor']) # Fac
        links.new(sep_param.outputs["Green"], mix_rough.inputs['A'])      # A (False)
        links.new(inp.outputs["Sep. Roughness"], mix_rough.inputs['B'])  # B (True)
        links.new(mix_rough.outputs['Result'], outp.inputs["Roughness"])      # Link to Group Output

        # Mix Emission (FIXED: Using Alpha from sep_param)
        mix_emis = nodes.new("ShaderNodeMix")
        mix_emis.data_type = 'FLOAT'
        mix_emis.label = "Mix Emission"
        mix_emis.location = (-1700, 200)
        links.new(inp.outputs["Use Separate Maps"], mix_emis.inputs['Factor'])
        links.new(inp.outputs["Parameter Map - Alpha"], mix_emis.inputs['A'])
        links.new(inp.outputs["Sep. Emission"], mix_emis.inputs['B'])
        links.new(mix_emis.outputs['Result'], outp.inputs["Emission"])        # Link to Group Output

        # Mix Flu Mask
        mix_flu_mask = nodes.new("ShaderNodeMix")
        mix_flu_mask.data_type = 'FLOAT'
        mix_flu_mask.label = "Mix Flu Mask"
        mix_flu_mask.location = (-1700, 0)
        links.new(inp.outputs["Use Separate Maps"], mix_flu_mask.inputs['Factor'])
        links.new(sep_param.outputs["Blue"], mix_flu_mask.inputs['A'])
        links.new(inp.outputs["Sep. Flu Mask"], mix_flu_mask.inputs['B'])
        links.new(mix_flu_mask.outputs['Result'], outp.inputs["Flu Mask"])    # Link to Group Output

        # --- 4. Normal Map Logic ---
        # if "_nor" in self.modules:
        norm_map_node = nodes.new("ShaderNodeNormalMap")
        norm_map_node.label = "Normal Map"
        norm_map_node.location = (800, -300)
        links.new(inp.outputs["Normal Map"], norm_map_node.inputs["Color"])
        links.new(norm_map_node.outputs["Normal"], outp.inputs["Normal"])
        # else:
        #     # Pass through an empty vector if no normal map
        #     links.new(inp.outputs["Normal Map"], outp.inputs["Normal"])

    def _create_flu_animation_nodes(self, tree, inp_node, outp_node):
        """Builds the 3D fluid animation graph inside the node group."""
        # This function is now identical to your previous version,
        # as its internal logic was correct.
        nodes = tree.nodes
        links = tree.links

        loc = (-1500, -500)

        time_node = nodes.new("ShaderNodeValue")
        time_node.label = "Time"
        time_node.location = (loc[0] - 1500, loc[1] + 300)
        try:
            fcurve = time_node.outputs[0].driver_add("default_value")
            # fcurve.driver.expression = "frame / 100"
            fcurve.driver.expression = "(sin(frame / 100 * pi) * 0.5) + 0.5"
        except Exception:
            pass # Fails in headless mode, which is fine

        tex_coord_node = nodes.new("ShaderNodeTexCoord")
        tex_coord_node.label = "Texture Coordinate"
        tex_coord_node.location = (loc[0] - 1500, loc[1] - 300)

        scaled_coords = nodes.new("ShaderNodeVectorMath")
        scaled_coords.label = "Scaled Coords"
        scaled_coords.operation = 'MULTIPLY'
        scaled_coords.location = (loc[0] - 1200, loc[1] - 300)
        links.new(inp_node.outputs["Scale"], scaled_coords.inputs[0])
        links.new(tex_coord_node.outputs["Generated"], scaled_coords.inputs[1])

        mult_time_freq = nodes.new("ShaderNodeVectorMath")
        mult_time_freq.label = "Time x Frequency"
        mult_time_freq.operation = 'MULTIPLY'
        mult_time_freq.location = (loc[0] - 1200, loc[1] + 300)
        links.new(time_node.outputs[0], mult_time_freq.inputs[0])
        links.new(inp_node.outputs["Frequency"], mult_time_freq.inputs[1])

        sine_node = nodes.new("ShaderNodeVectorMath")
        sine_node.label = "Sine"
        sine_node.operation = 'SINE'
        sine_node.location = (loc[0] - 900, loc[1] + 300)
        links.new(mult_time_freq.outputs[0], sine_node.inputs[0])

        pulse_vec = nodes.new("ShaderNodeMapRange")
        pulse_vec.label = "PulseVector [0,1]"
        pulse_vec.data_type = 'FLOAT_VECTOR'
        pulse_vec.location = (loc[0] - 600, loc[1] + 300)
        pulse_vec.inputs['From Min'].default_value = (-1.0, -1.0, -1.0)
        pulse_vec.inputs['From Max'].default_value = ( 1.0,  1.0,  1.0)
        links.new(sine_node.outputs['Vector'], pulse_vec.inputs['Vector'])

        speed_range = nodes.new("ShaderNodeVectorMath")
        speed_range.label = "SpeedRange"
        speed_range.operation = 'SUBTRACT'
        speed_range.location = (loc[0] - 900, loc[1] + 100)
        links.new(inp_node.outputs["MaxSpeed"], speed_range.inputs[0])
        links.new(inp_node.outputs["MinSpeed"], speed_range.inputs[1])

        mult_pulse_range = nodes.new("ShaderNodeVectorMath")
        mult_pulse_range.operation = 'MULTIPLY'
        mult_pulse_range.location = (loc[0] - 300, loc[1] + 200)
        links.new(pulse_vec.outputs['Vector'], mult_pulse_range.inputs['Vector'])
        links.new(speed_range.outputs[0], mult_pulse_range.inputs[1])

        pulsing_speed = nodes.new("ShaderNodeVectorMath")
        pulsing_speed.label = "PulsingSpeed"
        pulsing_speed.operation = 'ADD'
        pulsing_speed.location = (loc[0], loc[1] + 100)
        links.new(mult_pulse_range.outputs[0], pulsing_speed.inputs[0])
        links.new(inp_node.outputs["MinSpeed"], pulsing_speed.inputs[1])

        offset_l1 = nodes.new("ShaderNodeVectorMath")
        offset_l1.label = "Offset L1"
        offset_l1.operation = 'MULTIPLY'
        offset_l1.location = (loc[0] + 300, loc[1])
        links.new(pulsing_speed.outputs[0], offset_l1.inputs[0])
        links.new(time_node.outputs[0], offset_l1.inputs[1])

        final_vec_l1 = nodes.new("ShaderNodeVectorMath")
        final_vec_l1.label = "Final Vector L1"
        final_vec_l1.operation = 'ADD'
        final_vec_l1.location = (loc[0] + 600, loc[1])
        links.new(scaled_coords.outputs[0], final_vec_l1.inputs[0])
        links.new(offset_l1.outputs[0], final_vec_l1.inputs[1])

        links.new(final_vec_l1.outputs[0], outp_node.inputs["Flu Offset (Layer 1)"])

        time_offset = nodes.new("ShaderNodeMath")
        time_offset.label = "Time Offset"
        time_offset.operation = 'ADD'
        time_offset.location = (loc[0], loc[1] - 200)
        time_offset.inputs[1].default_value = 0.5
        links.new(time_node.outputs[0], time_offset.inputs[0])

        offset_l2 = nodes.new("ShaderNodeVectorMath")
        offset_l2.label = "Offset L2"
        offset_l2.operation = 'MULTIPLY'
        offset_l2.location = (loc[0] + 300, loc[1] - 200)
        links.new(pulsing_speed.outputs[0], offset_l2.inputs[0])
        links.new(time_offset.outputs[0], offset_l2.inputs[1])

        final_vec_l2 = nodes.new("ShaderNodeVectorMath")
        final_vec_l2.label = "Final Vector L2"
        final_vec_l2.operation = 'ADD'
        final_vec_l2.location = (loc[0] + 600, loc[1] - 200)
        links.new(scaled_coords.outputs[0], final_vec_l2.inputs[0])
        links.new(offset_l2.outputs[0], final_vec_l2.inputs[1])

        links.new(final_vec_l2.outputs[0], outp_node.inputs["Flu Offset (Layer 2)"])

        fade_speed = nodes.new("ShaderNodeMath")
        fade_speed.label = "FadeSpeed"
        fade_speed.operation = 'MULTIPLY'
        fade_speed.location = (loc[0] + 300, loc[1] - 400)
        fade_speed.inputs[1].default_value = 1.0
        links.new(time_node.outputs[0], fade_speed.inputs[0])

        fade_sine = nodes.new("ShaderNodeMath")
        fade_sine.label = "Sine(FadeSpeed)"
        fade_sine.operation = 'SINE'
        fade_sine.location = (loc[0] + 600, loc[1] - 400)
        links.new(fade_speed.outputs[0], fade_sine.inputs[0])

        crossfade = nodes.new("ShaderNodeMapRange")
        crossfade.label = "CrossFade [0,1]"
        crossfade.name = "CrossFade [0,1]"
        crossfade.location = (loc[0] + 900, loc[1] - 400)
        crossfade.inputs[1].default_value = -1.0
        crossfade.inputs[2].default_value =  1.0
        links.new(fade_sine.outputs[0], crossfade.inputs[0])

        links.new(crossfade.outputs[0], outp_node.inputs["Flu Crossfade"])

    def _create_material_nodes(self) -> None:
        """
        Creates all nodes *outside* the group in the material tree.
        """
        nodes = self.material.node_tree.nodes

        # --- Create Core Shader Nodes ---
        output_node = nodes.new("ShaderNodeOutputMaterial")
        output_node.label = "Material Output"
        output_node.location = (1200, 0)
        output_node.hide = True

        self.bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
        self.bsdf_node.label = "DRS Shader"
        self.bsdf_node.name = "DRS Shader"
        self.bsdf_node.location = (800, 0)
        self.bsdf_node.width = 250
        self.bsdf_node.inputs["IOR"].default_value = 1.0
        if bpy.app.version[0] == 3:
            self.bsdf_node.inputs["Specular"].default_value = 0.0
        self.bsdf_node.hide = True

        # AIO Engine Group Node
        self.group_node = nodes.new("ShaderNodeGroup")
        self.group_node.node_tree = self.group_tree
        self.group_node.label = "AIO DRS Engine"
        self.group_node.name = "DRS_Engine_Group"
        self.group_node.location = (-400, 500)
        self.group_node.width = 250

        # --- Create Texture Nodes ---
        base_x = -800
        curr_y = 1000

        self.color_tex_node = nodes.new("ShaderNodeTexImage")
        self.color_tex_node.label = "Color Map (_col)"
        self.color_tex_node.location = (base_x, curr_y); curr_y -= 350

        self.param_tex_node = nodes.new("ShaderNodeTexImage")
        self.param_tex_node.label = "Parameter Map (_par)"
        self.param_tex_node.location = (base_x, curr_y); curr_y -= 350

        self.sep_metallic_tex_node = nodes.new("ShaderNodeTexImage")
        self.sep_metallic_tex_node.label = "Separate Metallic"
        self.sep_metallic_tex_node.location = (base_x, curr_y); curr_y -= 300

        self.sep_roughness_tex_node = nodes.new("ShaderNodeTexImage")
        self.sep_roughness_tex_node.label = "Separate Roughness"
        self.sep_roughness_tex_node.location = (base_x, curr_y); curr_y -= 300

        self.sep_emission_tex_node = nodes.new("ShaderNodeTexImage")
        self.sep_emission_tex_node.label = "Separate Emission"
        self.sep_emission_tex_node.location = (base_x, curr_y); curr_y -= 300

        self.sep_flu_mask_tex_node = nodes.new("ShaderNodeTexImage")
        self.sep_flu_mask_tex_node.label = "Separate Flu Mask"
        self.sep_flu_mask_tex_node.location = (base_x, curr_y); curr_y -= 350

        self.normal_tex_node = nodes.new("ShaderNodeTexImage")
        self.normal_tex_node.label = "Normal Map (_nor)"
        self.normal_tex_node.location = (base_x, curr_y); curr_y -= 350

        self.refraction_tex_node = nodes.new("ShaderNodeTexImage")
        self.refraction_tex_node.label = "Refraction Map (_ref)"
        self.refraction_tex_node.location = (base_x, curr_y); curr_y -= 300

        self.refraction_color_node = nodes.new("ShaderNodeRGB")
        self.refraction_color_node.label = "Refraction Color"
        self.refraction_color_node.location = (base_x, curr_y)
        self.refraction_color_node.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)

        # --- Create Fluid Nodes ---
        # if "_par" in self.modules:
        self.flu_tex_node_L1 = nodes.new("ShaderNodeTexImage")
        self.flu_tex_node_L1.label = "Flu Map Layer 1"
        self.flu_tex_node_L1.location = (0, -300)
        self.flu_tex_node_L1.extension = 'REPEAT'
        self.flu_tex_node_L1.projection = 'SPHERE'

        self.flu_tex_node_L2 = nodes.new("ShaderNodeTexImage")
        self.flu_tex_node_L2.label = "Flu Map Layer 2"
        self.flu_tex_node_L2.location = (0, -500)
        self.flu_tex_node_L2.extension = 'REPEAT'
        self.flu_tex_node_L2.projection = 'SPHERE'

    def _link_material_nodes(self) -> None:
        """Links all the external nodes to the Engine group and BSDF."""
        links = self.material.node_tree.links

        # --- Link Textures -> Engine Group ---
        links.new(self.param_tex_node.outputs["Color"], self.group_node.inputs["Parameter Map"])
        links.new(self.param_tex_node.outputs["Alpha"], self.group_node.inputs["Parameter Map - Alpha"])
        links.new(self.sep_metallic_tex_node.outputs["Color"], self.group_node.inputs["Sep. Metallic"])
        links.new(self.sep_roughness_tex_node.outputs["Color"], self.group_node.inputs["Sep. Roughness"])
        links.new(self.sep_emission_tex_node.outputs["Color"], self.group_node.inputs["Sep. Emission"])
        links.new(self.sep_flu_mask_tex_node.outputs["Color"], self.group_node.inputs["Sep. Flu Mask"])
        links.new(self.normal_tex_node.outputs["Color"], self.group_node.inputs["Normal Map"])

        # --- Link Engine Group -> BSDF ---
        links.new(self.group_node.outputs["Metallic"], self.bsdf_node.inputs["Metallic"])
        links.new(self.group_node.outputs["Roughness"], self.bsdf_node.inputs["Roughness"])
        links.new(self.group_node.outputs["Emission"], self.bsdf_node.inputs["Emission Strength"])
        # if "_nor" in self.modules:
        links.new(self.group_node.outputs["Normal"], self.bsdf_node.inputs["Normal"])

        # --- Link Color Map -> BSDF ---
        # FIX 1: Link Color Alpha to BSDF Alpha
        links.new(self.color_tex_node.outputs["Alpha"], self.bsdf_node.inputs["Alpha"])
        # Link Color to Emission Color
        links.new(self.color_tex_node.outputs["Color"], self.bsdf_node.inputs["Emission Color"])

        # --- Final Color & Shader Linking ---
        last_shader_node = self.bsdf_node # Start with the BSDF

        # if "_par" in self.modules:
        # --- Build Fluid Color Mixing Chain ---
        mix_flu_layers = self.material.node_tree.nodes.new("ShaderNodeMix")
        mix_flu_layers.label = "Crossfade Flu Layers"
        mix_flu_layers.data_type = 'RGBA'
        mix_flu_layers.location = (400, -400)
        mix_flu_layers.hide = True

        mix_color_flu = self.material.node_tree.nodes.new("ShaderNodeMix")
        mix_color_flu.label = "Apply Flu Mask"
        mix_color_flu.data_type = 'RGBA'
        mix_color_flu.location = (600, -200)
        mix_color_flu.hide = True

        # Link Engine -> Fluid Textures
        links.new(self.group_node.outputs["Flu Offset (Layer 1)"], self.flu_tex_node_L1.inputs["Vector"])
        links.new(self.group_node.outputs["Flu Offset (Layer 2)"], self.flu_tex_node_L2.inputs["Vector"])

        # Link Engine & Textures -> Mixers
        links.new(self.group_node.outputs["Flu Crossfade"], mix_flu_layers.inputs[0]) # Fac
        links.new(self.flu_tex_node_L1.outputs["Color"], mix_flu_layers.inputs[6]) # A
        links.new(self.flu_tex_node_L2.outputs["Color"], mix_flu_layers.inputs[7]) # B

        links.new(self.group_node.outputs["Flu Mask"], mix_color_flu.inputs[0]) # Fac
        links.new(self.color_tex_node.outputs["Color"], mix_color_flu.inputs[6]) # A
        links.new(mix_flu_layers.outputs[2], mix_color_flu.inputs[7]) # B

        # Link Final Color -> BSDF
        links.new(mix_color_flu.outputs[2], self.bsdf_node.inputs["Base Color"])
        # else:
            # No fluid, just link Color Map directly
            # links.new(self.color_tex_node.outputs["Color"], self.bsdf_node.inputs["Base Color"])

        # if "_ref" in self.modules:
        # --- Build Refraction Mixing Chain ---
        links.new(self.refraction_color_node.outputs["Color"], self.group_node.inputs["Refraction Color"])
        links.new(self.refraction_tex_node.outputs["Color"], self.group_node.inputs["Refraction Map"])
        final_mix = self.material.node_tree.nodes.new("ShaderNodeMixShader")
        final_mix.label = "Mix Refraction Shader"
        final_mix.location = (1050, 0)
        final_mix.hide = True
        links.new(self.refraction_tex_node.outputs['Alpha'], final_mix.inputs[0])
        links.new(self.bsdf_node.outputs[0], final_mix.inputs[1]) # Opaque shader
        links.new(self.group_node.outputs["Refraction BSDF"], final_mix.inputs[2]) # Glass shader

        last_shader_node = final_mix # Update the last node in the chain
        self.material.use_backface_culling = True

        # --- Link Final Shader -> Output ---
        links.new(last_shader_node.outputs[0], self.material.node_tree.nodes["Material Output"].inputs["Surface"])

    def _layout_outer_nodes(self) -> None:
        """Creates frames to organize the external texture nodes."""
        nodes = self.material.node_tree.nodes

        frame_combined = nodes.new("NodeFrame")
        frame_combined.label = "Combined Maps (Importer Default)"
        self.color_tex_node.parent = frame_combined
        self.param_tex_node.parent = frame_combined

        frame_sep = nodes.new("NodeFrame")
        frame_sep.label = "Separate Maps (Artist Override)"
        self.sep_metallic_tex_node.parent = frame_sep
        self.sep_roughness_tex_node.parent = frame_sep
        self.sep_emission_tex_node.parent = frame_sep
        self.sep_flu_mask_tex_node.parent = frame_sep

        frame_common = nodes.new("NodeFrame")
        frame_common.label = "Common Maps"
        self.normal_tex_node.parent = frame_common
        self.refraction_tex_node.parent = frame_common
        self.refraction_color_node.parent = frame_common

        if "_par" in self.modules:
            frame_flu = nodes.new("NodeFrame")
            frame_flu.label = "Flu Animation Textures"
            self.flu_tex_node_L1.parent = frame_flu
            self.flu_tex_node_L2.parent = frame_flu

        for node in nodes:
            if node.type == 'FRAME':
                node.shrink = True

    def _def_socket_in(self, tree, name, type, default=None):
        """Helper to create an input socket (BlB 3.x / 4.x compatible)."""
        if bpy.app.version[0] >= 4:
            sock = tree.interface.new_socket(name=name, in_out="INPUT", socket_type=type)
            if default is not None:
                if type == SOCKET_VECTOR and isinstance(default, (tuple, list)):
                    sock.default_value[0] = default[0]
                    sock.default_value[1] = default[1]
                    sock.default_value[2] = default[2]
                else:
                    sock.default_value = default
        else:
            sock = tree.inputs.new(type, name)
            if default is not None:
                sock.default_value = default
        return sock

    def _def_socket_out(self, tree, name, type):
        """Helper to create an output socket (BlB 3.x / 4.x compatible)."""
        if bpy.app.version[0] >= 4:
            return tree.interface.new_socket(name=name, in_out="OUTPUT", socket_type=type)
        else:
            return tree.outputs.new(type, name)

    # --- Public Methods for Importer ---

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
        if "_par" not in self.modules:
            return # Don't load if flu isn't enabled

        img = self.load_image(texture_name, dir_path)
        if img:
            img.colorspace_settings.name = "sRGB"
            self.flu_tex_node_L1.image = img
            self.flu_tex_node_L2.image = img

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