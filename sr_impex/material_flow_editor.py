# sr_impex/material_flow_editor_blender.py
import bpy
from bpy.props import IntProperty, BoolProperty, FloatVectorProperty, PointerProperty, FloatProperty
from bpy.types import Panel, PropertyGroup

# Same labels you used in the PyQt material editor (so users see familiar names)
KNOWN_MATERIAL_FLAGS = {
    0: "Enable Alpha Test",
    1: "Decal Mode",
    16: "Use Parameter Map",
    17: "Use Normal Map",
    18: "Use Refraction Map",
    20: "Disable Receive Shadows",
    21: "Enable SH Lighting",
    # Unknowns are auto-filled as "Unknown Bitflag #N"
}
_MAX_BITS = 32

# --- Material flags PG --------------------------------------------------------
_updating_flags = False  # guard to avoid recursive updates

# In material_flow_editor.py

def _update_flow_nodes_logic(drs_flow_pg):
    """
    Finds the active material's node group and updates the named
    flow nodes with values from the property group.
    """
    if not drs_flow_pg:
        return
    
    # id_data is the object (e.g., Mesh) that owns this PropertyGroup
    obj = drs_flow_pg.id_data 
    if not obj or obj.type != 'MESH':
        return

    # Get the active material from the object
    mat = obj.active_material
    if not mat or not mat.use_nodes:
        return
    
    node_tree = mat.node_tree
    
    # Find the DRS Material group node
    drs_group_node = None
    for node in node_tree.nodes:
        # Check for label OR name
        if node.type == 'GROUP' and (node.label == 'AIO DRS Engine' or node.name == 'AIO DRS Engine'):
            drs_group_node = node
            break
    
    if not drs_group_node or not drs_group_node.node_tree:
        print("Could not find the DRS node group in this material")
        return
    
    # Get the INNER node tree from the group
    inner_tree = drs_group_node.node_tree
    
    # Get the values from the property group
    # Note: We take the [0:3] (XYZ) components from the Vector4 properties
    max_speed = drs_flow_pg.max_flow_speed
    min_speed = drs_flow_pg.min_flow_speed
    speed_change = drs_flow_pg.flow_speed_change
    flow_scale = drs_flow_pg.flow_scale
    
    # The Group itself has MinSpeed, MaxSpeed, Frequency, Scale Attributes. Print them
    # Set the values in the group node inputs
    drs_group_node.inputs['MaxSpeed'].default_value = (max_speed[0], max_speed[1], max_speed[2])
    drs_group_node.inputs['MinSpeed'].default_value = (min_speed[0], min_speed[1], min_speed[2])
    drs_group_node.inputs['Frequency'].default_value = (speed_change[0], speed_change[1], speed_change[2])
    drs_group_node.inputs['Scale'].default_value = (flow_scale[0], flow_scale[1], flow_scale[2])

def _update_alpha_connection(obj):
    """Update the alpha connection in DRS Material based on Enable Alpha Test flag."""
    if not obj or obj.type != 'MESH':
        return
    if not obj.active_material or not obj.active_material.use_nodes:
        return
    
    mat = obj.active_material
    node_tree = mat.node_tree
    
    # Find the color texture node (the one connected to IN-Color Map)
    color_tex_node = None
    for node in node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.label == 'Color Map (_col)':
            color_tex_node = node
            break
    
    if not color_tex_node:
        print("Color texture node not found.")
        return
    
    # Check if Enable Alpha Test is enabled (bit 0)
    enable_alpha = getattr(obj.drs_material, 'bit_0', False)
    decal_mode = getattr(obj.drs_material, 'bit_1', False)
    
    # Get the Principled BSDF node (assumed to be named 'DRS Shader')
    drs_node = None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED' and node.name == 'DRS Shader':
            drs_node = node
            break
        
    if not drs_node:
        print("DRS Shader node not found.")
        return
    
    # Find existing alpha link
    alpha_link = None
    for link in node_tree.links:
        if (link.from_node == color_tex_node and 
            link.from_socket.name == 'Alpha' and
            link.to_node == drs_node and
            link.to_socket.name == 'Alpha'):
            alpha_link = link
            break
    
    if decal_mode or enable_alpha:
        # Enable Alpha Test: ensure alpha is connected
        if not alpha_link:
            node_tree.links.new(
                color_tex_node.outputs['Alpha'],
                drs_node.inputs[4]
            )
    else:
        # Disable Alpha Test: remove alpha connection and set default to 1.0
        if alpha_link:
            node_tree.links.remove(alpha_link)
        # Set default alpha to fully opaque when not using alpha test
        if 'Alpha' in drs_node.inputs:
            drs_node.inputs[4].default_value = 1.0

def _find_node_by_label_or_name(node_tree, node_type, label_or_name):
    for n in node_tree.nodes:
        if n.type == node_type and (n.label == label_or_name or n.name == label_or_name):
            return n
    return None

def _update_parameter_connection(obj):
    """Bit 16: toggles links from Parameter Map image to the group inputs."""
    if not obj or obj.type != 'MESH' or not obj.active_material or not obj.active_material.use_nodes:
        return
    mat = obj.active_material
    nt = mat.node_tree

    # Texture node and Group node
    param_tex = _find_node_by_label_or_name(nt, 'TEX_IMAGE', 'Parameter Map (_par)') or \
                _find_node_by_label_or_name(nt, 'TEX_IMAGE', 'Parameter Map')
    drs_group = None
    for node in nt.nodes:
        if node.type == 'GROUP' and (node.label == 'AIO DRS Engine' or node.name == 'DRS_Engine_Group'):
            drs_group = node
            break
    if not drs_group:
        return

    use_param = getattr(obj.drs_material, 'bit_16', False)

    # Find existing links
    links_to_remove = []
    for lk in list(nt.links):
        if lk.to_node == drs_group and lk.to_socket.name in ("Parameter Map", "Parameter Map - Alpha"):
            links_to_remove.append(lk)

    # Disconnect everything first
    for lk in links_to_remove:
        nt.links.remove(lk)

    if use_param and param_tex:
        # Re-create links
        if "Color" in param_tex.outputs and "Parameter Map" in drs_group.inputs:
            nt.links.new(param_tex.outputs["Color"], drs_group.inputs["Parameter Map"])
        if "Alpha" in param_tex.outputs and "Parameter Map - Alpha" in drs_group.inputs:
            nt.links.new(param_tex.outputs["Alpha"], drs_group.inputs["Parameter Map - Alpha"])
    else:
        # Set sane defaults when disabled (match interface defaults in the group)
        if "Parameter Map" in drs_group.inputs:
            try:
                drs_group.inputs["Parameter Map"].default_value = (0.0, 0.8, 0.0, 0.0)
            except Exception:
                pass
        if "Parameter Map - Alpha" in drs_group.inputs:
            drs_group.inputs["Parameter Map - Alpha"].default_value = 0.0

def _update_normal_connection(obj):
    """Bit 17: toggles links from Normal Map image to the group input and keeps Normal flat when off."""
    if not obj or obj.type != 'MESH' or not obj.active_material or not obj.active_material.use_nodes:
        return
    mat = obj.active_material
    nt = mat.node_tree

    normal_tex = _find_node_by_label_or_name(nt, 'TEX_IMAGE', 'Normal Map (_nor)') or \
                 _find_node_by_label_or_name(nt, 'TEX_IMAGE', 'Normal Map')
    drs_group = None
    for node in nt.nodes:
        if node.type == 'GROUP' and (node.label == 'AIO DRS Engine' or node.name == 'DRS_Engine_Group'):
            drs_group = node
            break
    if not drs_group:
        return

    use_normal = getattr(obj.drs_material, 'bit_17', False)

    # Remove existing normal map input link
    for lk in list(nt.links):
        if lk.to_node == drs_group and lk.to_socket.name == "Normal Map":
            nt.links.remove(lk)

    if use_normal and normal_tex and "Color" in normal_tex.outputs and "Normal Map" in drs_group.inputs:
        nt.links.new(normal_tex.outputs["Color"], drs_group.inputs["Normal Map"])
    else:
        # Flat normal (zero vector) when disabled
        if "Normal Map" in drs_group.inputs:
            try:
                drs_group.inputs["Normal Map"].default_value = (0.0, 0.0, 0.0)
            except Exception:
                pass

def _update_refraction_connection(obj):
    """Bit 18: toggles the refraction branch back to Opaque BSDF when off, and reinstates it when on."""
    if not obj or obj.type != 'MESH' or not obj.active_material or not obj.active_material.use_nodes:
        return
    mat = obj.active_material
    nt = mat.node_tree

    # Core nodes created by DRSMaterial when _ref is present:
    drs_bsdf = None
    mat_output = None
    final_mix = None
    mix_refraction = None

    for node in nt.nodes:
        if node.type == 'BSDF_PRINCIPLED' and node.name == 'DRS Shader':
            drs_bsdf = node
        elif node.type == 'OUTPUT_MATERIAL':
            mat_output = node
        elif node.type == 'MIX_SHADER' and node.label == '':  # label may be empty; we locate by inputs
            # we'll identify by structure later
            pass

    # Find the exact nodes by structure
    for node in nt.nodes:
        if node.type == 'MIX_SHADER':
            # final_mix: its inputs[1] is the main BSDF, inputs[2] is a MixShader (glass branch)
            if node.inputs.get(1) and node.inputs.get(2):
                src1 = node.inputs[1].links[0].from_node if node.inputs[1].is_linked else None
                src2 = node.inputs[2].links[0].from_node if node.inputs[2].is_linked else None
                if src1 and drs_bsdf and src1 == drs_bsdf and src2 and src2.type == 'MIX_SHADER':
                    final_mix = node
                    mix_refraction = src2
                    break

    if not drs_bsdf or not mat_output:
        return

    use_refraction = getattr(obj.drs_material, 'bit_18', False)

    # Current output link
    out_link = None
    for lk in list(nt.links):
        if lk.to_node == mat_output and lk.to_socket.name == "Surface":
            out_link = lk
            break

    if use_refraction:
        # Ensure the final_mix drives the output, if the chain exists
        if final_mix:
            # If output is not coming from final_mix, rewire it
            if not (out_link and out_link.from_node == final_mix):
                if out_link:
                    nt.links.remove(out_link)
                nt.links.new(final_mix.outputs[0], mat_output.inputs["Surface"])
        # If refraction nodes were never built (e.g., modules didn’t include "_ref"), we do nothing.
        return

    # Disabled: route plain BSDF to output
    if out_link:
        nt.links.remove(out_link)
    nt.links.new(drs_bsdf.outputs[0], mat_output.inputs["Surface"])

def _update_wind_nodes_logic(drs_wind_pg):
    """
    Finds the GN modifier and updates the named nodes
    with values from the property group.
    """
    if not drs_wind_pg:
        return
    
    # id_data is the object (e.g., Mesh) that owns this PropertyGroup
    obj = drs_wind_pg.id_data 
    if not obj or obj.type != 'MESH':
        return

    # Get the values from the property group
    wind_response = drs_wind_pg.wind_response
    wind_height = drs_wind_pg.wind_height
    
    # Find the GN modifier
    geo_mod = None
    for mod in obj.modifiers:
        # Check for name to be safe, in case of multiple GN mods
        if mod.type == 'NODES' and "WindEffect" in mod.name: 
            geo_mod = mod
            break
    
    if not geo_mod or not geo_mod.node_group:
        return
    
    node_tree = geo_mod.node_group
    
    # Find the named "Wind Response" node and set its value
    response_node = node_tree.nodes.get("Wind Response")
    if response_node:
        response_node.inputs[1].default_value = wind_response
    
    # Find the named "Wind Height" node and set its value
    height_node = node_tree.nodes.get("Wind Height")
    if height_node and "From Min" in height_node.inputs:
        # 'wind_height' from DRS is the minimum height for the effect
        height_node.inputs["From Min"].default_value = wind_height

def _update_wind_geometry_nodes(self, _ctx):
    """This is the update callback for the UI properties."""
    _update_wind_nodes_logic(self) # 'self' is the drs_wind_pg

def _update_wind_nodes(drs_wind_pg):
    """This is the function called by the importer in drs_utility.py."""
    _update_wind_nodes_logic(drs_wind_pg)

# In material_flow_editor.py (near the wind update functions)

def _update_flow_props(self, _ctx):
    """This is the update callback for the UI properties."""
    _update_flow_nodes_logic(self) # 'self' is the drs_flow_pg

def _update_flow_nodes(drs_flow_pg):
    """This is the function called by the importer in drs_utility.py."""
    _update_flow_nodes_logic(drs_flow_pg)

def _on_raw_changed(self, _ctx):
    global _updating_flags
    if _updating_flags:
        return
    _updating_flags = True
    v = int(self.bool_parameter) & 0xFFFFFFFF
    old_bit_0 = getattr(self, 'bit_0', False)
    for i in range(_MAX_BITS):
        setattr(self, f"bit_{i}", bool((v >> i) & 1))
    _updating_flags = False
    # Update alpha connection if bit 0 changed
    new_bit_0 = getattr(self, 'bit_0', False)
    if old_bit_0 != new_bit_0:
        obj = _ctx.object if hasattr(_ctx, 'object') else None
        _update_alpha_connection(obj)

def _on_bit_changed(self, _ctx):
    global _updating_flags
    if _updating_flags:
        return
    _updating_flags = True
    v = 0
    for i in range(_MAX_BITS):
        if getattr(self, f"bit_{i}", False):
            v |= 1 << i
    self.bool_parameter = v
    _updating_flags = False

def _on_bit_0_changed(self, ctx):
    """Special handler for bit 0 (Enable Alpha Test) that updates shader graph."""
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_alpha_connection(obj)

def _on_bit_1_changed(self, ctx):
    """Special handler for bit 1 (Enable Decal Mode) that updates shader graph."""
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_alpha_connection(obj)

def _on_bit_16_changed(self, ctx):
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_parameter_connection(obj)

def _on_bit_17_changed(self, ctx):
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_normal_connection(obj)

def _on_bit_18_changed(self, ctx):
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_refraction_connection(obj)


class DRS_MaterialFlagsPG(PropertyGroup):
    bool_parameter: IntProperty(
        name="Raw bool_parameter",
        description="32-bit integer of material flags",
        default=0,
        min=0,
        update=_on_raw_changed,
    )  # type: ignore

def _bit_prop_factory(idx):
    if idx == 0:
        return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(0, f"Flag {idx}"), update=_on_bit_0_changed)
    if idx == 1:
        return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(1, f"Flag {idx}"), update=_on_bit_1_changed)
    if idx == 16:
        return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(16, f"Flag {idx}"), update=_on_bit_16_changed)
    if idx == 17:
        return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(17, f"Flag {idx}"), update=_on_bit_17_changed)
    if idx == 18:
        return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(18, f"Flag {idx}"), update=_on_bit_18_changed)
    # default
    return BoolProperty(name=KNOWN_MATERIAL_FLAGS.get(idx, f"Unknown Bitflag #{idx}"), update=_on_bit_changed)

# --- Flow PG ------------------------------------------------------------------
class DRS_FlowPG(PropertyGroup):
    use_flow: BoolProperty(
        name="Write Flow",
        description="Enable writing Flow to the mesh material block on export",
        default=False,
    )  # type: ignore
    max_flow_speed: FloatVectorProperty(name="Max Flow Speed", size=4, default=(0, 0, 0, 0), update=_update_flow_props)  # type: ignore
    min_flow_speed: FloatVectorProperty(name="Min Flow Speed", size=4, default=(0, 0, 0, 0), update=_update_flow_props)  # type: ignore
    flow_speed_change: FloatVectorProperty(name="Flow Speed Change", size=4, default=(0, 0, 0, 0), update=_update_flow_props)  # type: ignore
    flow_scale: FloatVectorProperty(name="Flow Scale", size=4, default=(0, 0, 0, 0), update=_update_flow_props)  # type: ignore

class DRS_WindPG(PropertyGroup):
    wind_response: FloatProperty(
        name="Wind Response",
        description="Wind response strength",
        default=0.0,
        min=0.0,
        update=_update_wind_geometry_nodes,
    )  # type: ignore
    wind_height: FloatProperty(
        name="Wind Height",
        description="Wind height offset",
        default=0.0,
        update=_update_wind_geometry_nodes,
    )  # type: ignore


# --- Helpers ------------------------------------------------------------------
def _in_meshes_collection(obj: bpy.types.Object) -> bool:
    return any(col.name == "Meshes_Collection" for col in obj.users_collection)

def _in_ground_decal_collection(obj: bpy.types.Object) -> bool:
    return any(col.name == "GroundDecal_Collection" for col in obj.users_collection)

def _highest_relevant_bit(value: int) -> int:
    if value <= 0:
        return 7  # show at least 0..7 when nothing is set
    h = value.bit_length() - 1
    return min(max(h, 7), 31)

def _active_mesh(ctx) -> bpy.types.Object | None:
    o = getattr(ctx, "object", None)
    if o and o.type == "MESH" and _in_meshes_collection(o) or _in_ground_decal_collection(o):
        return o
    return None

# --- Panels -------------------------------------------------------------------
class DRS_PT_Material(Panel):
    bl_label = "Material"
    bl_category = "DRS Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, _ctx):
        return True

    def draw(self, ctx):
        layout = self.layout
        o = _active_mesh(ctx)
        if not o:
            box = layout.box()
            box.label(text="Select a Mesh inside 'Meshes_Collection' to edit material properties.", icon="INFO")

class DRS_PT_MaterialFlags(Panel):
    bl_label = "Flags (bool_parameter)"
    bl_parent_id = "DRS_PT_Material"
    bl_category = "DRS Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, _ctx):
        return True

    def draw(self, ctx):
        layout = self.layout
        o = _active_mesh(ctx)
        if not o or not hasattr(o, "drs_material") or o.drs_material is None:
            box = layout.box()
            box.label(text="Select a Mesh inside 'Meshes_Collection' to edit material flags.", icon="INFO")
            return

        flags = o.drs_material
        layout.prop(flags, "bool_parameter")

        max_known = max(KNOWN_MATERIAL_FLAGS.keys()) if KNOWN_MATERIAL_FLAGS else 0
        max_bit = max(_highest_relevant_bit(flags.bool_parameter), max_known, 7)

        col = layout.column(align=True)
        for i in range(max_bit + 1):
            label = KNOWN_MATERIAL_FLAGS.get(i, f"Unknown Bitflag #{i+1}")
            col.prop(flags, f"bit_{i}", text=f"{label} (Bit {i})")

class DRS_PT_Flow(Panel):
    bl_label = "Flow"
    bl_parent_id = "DRS_PT_Material"
    bl_category = "DRS Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, _ctx):
        return True

    def draw(self, ctx):
        layout = self.layout
        o = _active_mesh(ctx)
        if not o or not hasattr(o, "drs_flow") or o.drs_flow is None:
            box = layout.box()
            box.label(text="Select a Mesh inside 'Meshes_Collection' to edit flow.", icon="INFO")
            return

        f = o.drs_flow
        layout.prop(f, "use_flow")
        box = layout.box()
        box.enabled = f.use_flow
        grid = box.grid_flow(columns=1, even_columns=True, even_rows=True, align=True)
        grid.prop(f, "max_flow_speed")
        grid.prop(f, "min_flow_speed")
        grid.prop(f, "flow_speed_change")
        grid.prop(f, "flow_scale")

class DRS_PT_Wind(Panel):
    bl_label = "Wind"
    bl_parent_id = "DRS_PT_Material"
    bl_category = "DRS Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, _ctx):
        return True

    def draw(self, ctx):
        layout = self.layout
        o = _active_mesh(ctx)
        if not o or not hasattr(o, "drs_wind") or o.drs_wind is None:
            box = layout.box()
            box.label(text="Select a Mesh inside 'Meshes_Collection' to edit wind.", icon="INFO")
            return

        w = o.drs_wind
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(w, "wind_response")
        layout.prop(w, "wind_height")

# --- Register -----------------------------------------------------------------
classes = (
    DRS_MaterialFlagsPG,
    DRS_FlowPG,
    DRS_WindPG,
    DRS_PT_Material,
    DRS_PT_MaterialFlags,
    DRS_PT_Flow,
    DRS_PT_Wind,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for i in range(_MAX_BITS):
        setattr(DRS_MaterialFlagsPG, f"bit_{i}", _bit_prop_factory(i))

    bpy.types.Object.drs_material = PointerProperty(type=DRS_MaterialFlagsPG)  # type: ignore
    bpy.types.Object.drs_flow = PointerProperty(type=DRS_FlowPG)  # type: ignore
    bpy.types.Object.drs_wind = PointerProperty(type=DRS_WindPG)  # type: ignore


def unregister():
    del bpy.types.Object.drs_wind
    del bpy.types.Object.drs_flow
    del bpy.types.Object.drs_material

    # Remove dynamic bits so reloads are clean
    for i in range(_MAX_BITS):
        try:
            delattr(DRS_MaterialFlagsPG, f"bit_{i}")
        except Exception:
            pass

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
