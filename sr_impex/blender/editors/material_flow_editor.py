# sr_impex/material_flow_editor_blender.py
import bpy
from bpy.props import IntProperty, BoolProperty, FloatVectorProperty, PointerProperty, FloatProperty, StringProperty
from bpy.types import Panel, PropertyGroup, Operator

ENV_HELPER_COLLECTION_NAME = "Environment_Collection"
ENV_HELPER_OBJECT_NAME = "Environment_Cubemap"
ENV_CUBEMAP_NODE_LABEL = "Environment Cubemap (_env)"

# Same labels you used in the PyQt material editor (so users see familiar names)
KNOWN_MATERIAL_FLAGS = {
    0: "Enable Alpha Test",
    1: "Decal Mode",
    16: "Use Parameter Map",
    17: "Use Normal Map",
    18: "Use Refraction / Env Map Flag",
    20: "Disable Receive Shadows",
    21: "Enable SH Lighting",
    # Unknowns are auto-filled as "Unknown Bitflag #N"
}
_MAX_BITS = 32
_REF_ENV_DEBUG = False

# --- Material flags PG --------------------------------------------------------
_UPDATING_FLAGS = False  # guard to avoid recursive updates

def _debug_ref_env(message: str) -> None:
    if _REF_ENV_DEBUG:
        print(f"[DRS RefEnv] {message}")

def _resolve_owner_object(flags_pg: bpy.types.PropertyGroup, ctx: bpy.types.Context | None = None) -> bpy.types.Object | None:
    obj = getattr(flags_pg, "id_data", None)
    if obj is not None and getattr(obj, "type", None) == "MESH":
        return obj
    obj = ctx.object if (ctx is not None and hasattr(ctx, "object")) else None
    if obj is not None and getattr(obj, "type", None) == "MESH":
        return obj
    return None

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
    # inner_tree = drs_group_node.node_tree

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
        # Set Alpha Mode of Color Map to 'Straight' (if applicable)
        if hasattr(color_tex_node, 'image') and color_tex_node.image:
            color_tex_node.image.alpha_mode = 'STRAIGHT'
    else:
        # Disable Alpha Test: remove alpha connection and set default to 1.0
        if alpha_link:
            node_tree.links.remove(alpha_link)
        # Set default alpha to fully opaque when not using alpha test
        if 'Alpha' in drs_node.inputs:
            drs_node.inputs[4].default_value = 1.0
        # Reset Alpha Mode of Color Map to 'None' (if applicable)
        if hasattr(color_tex_node, 'image') and color_tex_node.image:
            color_tex_node.image.alpha_mode = 'NONE'

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

    material_flags = getattr(obj, "drs_material", None)
    if material_flags is None:
        return

    use_refraction = bool(
        getattr(material_flags, 'use_ref_map', getattr(material_flags, 'bit_18', False))
    )
    has_refraction_image = _has_refraction_map_for_object(obj)
    if use_refraction and not has_refraction_image:
        # Keep branch muted when refraction toggle is on but no _ref image exists.
        use_refraction = False

    # Core nodes created by DRSMaterial when _ref is present:
    mix_refraction = None

    # Find Node: Mix Shader Type: MIX_SHADER Label: Mix Refraction Shader
    for node in nt.nodes:
        if node.type == "MIX_SHADER" and node.label == "Mix Refraction Shader":
            mix_refraction = node

    if not mix_refraction:
        return

    if use_refraction:
        try:
            if mix_refraction:
                mat.use_backface_culling  = True
                mix_refraction.mute = False
        except Exception:
            pass
        return

    try:
        if mix_refraction:
            mix_refraction.mute = True
            mat.use_backface_culling  = False
    except Exception:
        pass

def _update_flu_apply_mask_state(obj):
    """Mute/unmute the 'Apply Flu Mask' mix based on bit 16 and presence of Flu images.
    Conditions to ENABLE (unmute) the node:
      - bit_16 (Use Parameter Map) is True, AND
      - At least one Flu Map Layer (1 or 2) has an image.
    Otherwise the node is muted (acts as passthrough of Color Map).
    """
    try:
        if not obj or obj.type != 'MESH' or not obj.active_material or not obj.active_material.use_nodes:
            return
        mat = obj.active_material
        nt = mat.node_tree

        mix_color_flu = None
        flu_l1 = None
        flu_l2 = None
        for n in nt.nodes:
            if n.type == 'MIX' and n.label == 'Apply Flu Mask':
                mix_color_flu = n
            elif n.type == 'TEX_IMAGE' and n.label == 'Flu Map Layer 1':
                flu_l1 = n
            elif n.type == 'TEX_IMAGE' and n.label == 'Flu Map Layer 2':
                flu_l2 = n
        if mix_color_flu is None:
            return

        use_param = bool(getattr(obj.drs_material, 'bit_16', False))
        has_flu_img = bool((flu_l1 and getattr(flu_l1, 'image', None)) or (flu_l2 and getattr(flu_l2, 'image', None)))

        # Mute when either flag is off OR no images; unmute only when both are true.
        mix_color_flu.mute = not (use_param and has_flu_img)
    except Exception:
        pass

def _get_wind_height_extent(obj: bpy.types.Object) -> float:
    """Return the local span used by the wind height falloff."""
    if not obj or obj.type != 'MESH' or not obj.bound_box:
        return 1.0

    y_values = [corner[1] for corner in obj.bound_box]
    min_y = min(y_values)
    max_y = max(y_values)
    extent = max_y - min_y
    return extent if extent > 0 else 1.0

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

    # Recompute the local mesh height so the wind fade range stays in sync
    # after the user edits the mesh and then changes the wind settings.
    max_height = _get_wind_height_extent(obj)

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
        # 'wind_height' from DRS is the minimum height for the effect.
        height_node.inputs["From Min"].default_value = wind_height
        if "From Max" in height_node.inputs:
            height_node.inputs["From Max"].default_value = max_height
        if "Value" in height_node.inputs:
            incoming_links = list(height_node.inputs["Value"].links)
            for link in incoming_links:
                from_node = link.from_node
                if from_node and from_node.type == 'SEPXYZ' and "Y" in from_node.outputs:
                    if link.from_socket.name != "Y":
                        node_tree.links.remove(link)
                        node_tree.links.new(from_node.outputs["Y"], height_node.inputs["Value"])
                    break

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
    global _UPDATING_FLAGS
    if _UPDATING_FLAGS:
        return
    _UPDATING_FLAGS = True
    v = int(self.bool_parameter) & 0xFFFFFFFF
    old_bit_0 = getattr(self, 'bit_0', False)
    old_bit_18 = getattr(self, 'bit_18', False)
    for i in range(_MAX_BITS):
        setattr(self, f"bit_{i}", bool((v >> i) & 1))
    _UPDATING_FLAGS = False
    # Update alpha connection if bit 0 changed
    new_bit_0 = getattr(self, 'bit_0', False)
    obj = _ctx.object if hasattr(_ctx, 'object') else None
    if old_bit_0 != new_bit_0:
        _update_alpha_connection(obj)
    if obj is not None and old_bit_18 != getattr(self, 'bit_18', False):
        _update_refraction_connection(obj)
    elif obj is not None:
        _update_refraction_connection(obj)

def _on_bit_changed(self, _ctx):
    global _UPDATING_FLAGS
    if _UPDATING_FLAGS:
        return
    _UPDATING_FLAGS = True
    v = 0
    for i in range(_MAX_BITS):
        if getattr(self, f"bit_{i}", False):
            v |= 1 << i
    self.bool_parameter = v
    _UPDATING_FLAGS = False

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
    _update_flu_apply_mask_state(obj)

def _on_bit_17_changed(self, ctx):
    _on_bit_changed(self, ctx)
    obj = ctx.object if hasattr(ctx, 'object') else None
    _update_normal_connection(obj)

def _sync_effective_bit_18(flags_pg: bpy.types.PropertyGroup) -> None:
    use_ref = bool(getattr(flags_pg, "use_ref_map", False))
    use_env = bool(getattr(flags_pg, "use_env_map", False))
    _set_bit_state(flags_pg, 18, use_ref or use_env)

def _set_ref_env_notice(flags_pg: bpy.types.PropertyGroup, text: str) -> None:
    if flags_pg is None:
        return
    try:
        flags_pg.ref_env_notice = text
    except Exception:
        pass

def _on_bit_18_changed(self, ctx):
    if _UPDATING_FLAGS:
        return

    _on_bit_changed(self, ctx)
    obj = _resolve_owner_object(self, ctx)

    if bool(getattr(self, "bit_18", False)):
        has_refraction_image = _has_refraction_map_for_object(obj)
        if not has_refraction_image:
            _set_bit_state(self, 18, False)
            _set_ref_env_notice(self, "Enable Refraction Map requires a loaded Refraction Map (_ref) image.")
        else:
            _set_ref_env_notice(self, "")
    else:
        _set_ref_env_notice(self, "")

    _update_refraction_connection(obj)

def _on_use_ref_map_changed(self, ctx):
    if _UPDATING_FLAGS:
        return

    obj = _resolve_owner_object(self, ctx)

    if bool(getattr(self, "use_ref_map", False)) and not _has_refraction_map_for_object(obj):
        _debug_ref_env(
            f"_on_use_ref_map_changed: rejected enable for mesh='{getattr(obj, 'name', '<none>')}' because no refraction image was detected"
        )
        self.use_ref_map = False
        _set_ref_env_notice(self, "Enable Refraction Map requires a loaded Refraction Map (_ref) image.")
        _sync_effective_bit_18(self)
        _update_refraction_connection(obj)
        return

    _set_ref_env_notice(self, "")
    _sync_effective_bit_18(self)
    _update_refraction_connection(obj)

def _find_parent_collection(root: bpy.types.Collection, target: bpy.types.Collection) -> bpy.types.Collection | None:
    for child in root.children:
        if child == target:
            return root
        found = _find_parent_collection(child, target)
        if found is not None:
            return found
    return None

def _find_drs_model_collection_for_object(obj: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection | None:
    if obj is None or obj.type != "MESH" or scene is None:
        return None

    for start_col in getattr(obj, "users_collection", []) or []:
        col = start_col
        for _ in range(32):
            if col is None:
                break
            if col.name.startswith("DRSModel_"):
                return col
            col = _find_parent_collection(scene.collection, col)
    return None

def _has_refraction_map_for_object(obj: bpy.types.Object) -> bool:
    if obj is None or obj.type != 'MESH':
        return False
    mat = obj.active_material
    if mat is None or not mat.use_nodes:
        return False

    refraction_tex_node = _find_node_by_label_or_name(mat.node_tree, 'TEX_IMAGE', 'Refraction Map (_ref)') or \
                          _find_node_by_label_or_name(mat.node_tree, 'TEX_IMAGE', 'Refraction Map')
    return bool(refraction_tex_node and getattr(refraction_tex_node, 'image', None))

def _get_env_cubemap_object_for_object(obj: bpy.types.Object, ctx: bpy.types.Context | None = None) -> bpy.types.Object | None:
    scene = None
    if ctx is not None:
        scene = ctx.scene
    elif bpy.context is not None:
        scene = bpy.context.scene

    source_collection = _find_drs_model_collection_for_object(obj, scene)
    if source_collection is None:
        return None

    env_collection = source_collection.children.get(ENV_HELPER_COLLECTION_NAME)
    if env_collection is None:
        return None

    env_obj = env_collection.objects.get(ENV_HELPER_OBJECT_NAME)
    if env_obj is None or env_obj.type != "MESH":
        return None

    return env_obj

def _has_env_cubemap_for_object(obj: bpy.types.Object, ctx: bpy.types.Context | None = None) -> bool:
    env_obj = _get_env_cubemap_object_for_object(obj, ctx)
    if env_obj is None:
        _debug_ref_env(f"_has_env_cubemap_for_object: no env helper object for mesh '{getattr(obj, 'name', '<none>')}'")
        return False

    mat = env_obj.active_material
    if mat is None and getattr(env_obj.data, "materials", None):
        mat = env_obj.data.materials[0]
        _debug_ref_env(
            f"_has_env_cubemap_for_object: using first material slot fallback for env helper '{env_obj.name}'"
        )
    if mat is None or not mat.use_nodes:
        _debug_ref_env(
            f"_has_env_cubemap_for_object: material missing or no nodes on env helper '{env_obj.name}'"
        )
        return False

    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and (node.label == ENV_CUBEMAP_NODE_LABEL or node.name == ENV_CUBEMAP_NODE_LABEL):
            has_image = bool(getattr(node, "image", None))
            _debug_ref_env(
                f"_has_env_cubemap_for_object: env image node found on '{env_obj.name}', has_image={has_image}"
            )
            return has_image
    _debug_ref_env(
        f"_has_env_cubemap_for_object: env image node '{ENV_CUBEMAP_NODE_LABEL}' not found on '{env_obj.name}'"
    )
    return False

def _set_env_cubemap_visibility_for_object(obj: bpy.types.Object, visible: bool, ctx: bpy.types.Context | None = None) -> None:
    env_obj = _get_env_cubemap_object_for_object(obj, ctx)
    if env_obj is None:
        return

    try:
        env_obj.hide_viewport = not visible
        env_obj.hide_render = not visible
        env_obj.hide_set(not visible)
    except Exception:
        pass

def _set_bit_state(flags_pg: bpy.types.PropertyGroup, idx: int, enabled: bool) -> None:
    global _UPDATING_FLAGS
    if flags_pg is None:
        return

    # Build raw value from the current checkbox states to avoid stale raw-property races.
    current_raw = 0
    for i in range(_MAX_BITS):
        if bool(getattr(flags_pg, f"bit_{i}", False)):
            current_raw |= 1 << i

    mask = 1 << idx
    target_raw = (current_raw | mask) if enabled else (current_raw & ~mask)
    current_bit = bool(getattr(flags_pg, f"bit_{idx}", False))
    if current_raw == target_raw and current_bit == enabled:
        return

    if _UPDATING_FLAGS:
        return

    _UPDATING_FLAGS = True
    try:
        flags_pg.bool_parameter = target_raw
        for i in range(_MAX_BITS):
            setattr(flags_pg, f"bit_{i}", bool((target_raw >> i) & 1))
    finally:
        _UPDATING_FLAGS = False

def _initialize_ref_env_toggles_from_import(obj: bpy.types.Object, ctx: bpy.types.Context | None = None) -> None:
    global _UPDATING_FLAGS
    if obj is None or obj.type != 'MESH' or not hasattr(obj, "drs_material") or obj.drs_material is None:
        return

    flags = obj.drs_material
    imported_raw = int(obj.get("_drs_imported_bool_parameter", int(getattr(flags, "bool_parameter", 0))))
    imported_bit_18 = bool((imported_raw >> 18) & 1)

    has_refraction_image = _has_refraction_map_for_object(obj)
    has_env_cubemap = _has_env_cubemap_for_object(obj, ctx)

    target_ref_toggle = imported_bit_18 and has_refraction_image
    target_env_toggle = imported_bit_18 and has_env_cubemap

    _debug_ref_env(
        f"_initialize_ref_env_toggles_from_import: mesh='{obj.name}', imported_raw={imported_raw}, imported_bit18={imported_bit_18}, has_ref={has_refraction_image}, has_env={has_env_cubemap}, target_ref={target_ref_toggle}, target_env={target_env_toggle}"
    )

    _set_bit_state(flags, 18, target_ref_toggle)
    prev_guard = _UPDATING_FLAGS
    _UPDATING_FLAGS = True
    try:
        flags.use_ref_map = target_ref_toggle
    finally:
        _UPDATING_FLAGS = prev_guard

    if bool(getattr(flags, "use_env_map", False)) != target_env_toggle:
        prev_guard = _UPDATING_FLAGS
        _UPDATING_FLAGS = True
        try:
            flags.use_env_map = target_env_toggle
        finally:
            _UPDATING_FLAGS = prev_guard

    _sync_effective_bit_18(flags)

    _set_ref_env_notice(flags, "")
    _set_env_cubemap_visibility_for_object(obj, target_env_toggle, ctx)
    _update_refraction_connection(obj)

    _debug_ref_env(
        f"_initialize_ref_env_toggles_from_import result: mesh='{obj.name}', bit_18={bool(getattr(flags, 'bit_18', False))}, use_ref_map={bool(getattr(flags, 'use_ref_map', False))}, use_env_map={bool(getattr(flags, 'use_env_map', False))}, raw={int(getattr(flags, 'bool_parameter', 0))}"
    )

def _on_use_env_map_changed(self, ctx):
    if _UPDATING_FLAGS:
        return

    obj = _resolve_owner_object(self, ctx)
    if bool(getattr(self, "use_env_map", False)) and not _has_env_cubemap_for_object(obj, ctx):
        _debug_ref_env(
            f"_on_use_env_map_changed: rejected enable for mesh='{getattr(obj, 'name', '<none>')}' because no env image was detected"
        )
        self.use_env_map = False
        _set_ref_env_notice(self, "Enable Env/Cube Map requires a loaded Environment Cubemap (_env) image.")
        _set_env_cubemap_visibility_for_object(obj, False, ctx)
        _sync_effective_bit_18(self)
        _update_refraction_connection(obj)
        return

    _debug_ref_env(
        f"_on_use_env_map_changed: mesh='{getattr(obj, 'name', '<none>')}', use_env_map={bool(getattr(self, 'use_env_map', False))}"
    )

    _set_ref_env_notice(self, "")
    _set_env_cubemap_visibility_for_object(obj, bool(getattr(self, "use_env_map", False)), ctx)
    _sync_effective_bit_18(self)
    _update_refraction_connection(obj)

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

class DRS_MaterialFlagsPG(PropertyGroup):
    bool_parameter: IntProperty(
        name="Raw bool_parameter",
        description="32-bit integer of material flags",
        default=0,
        min=0,
        update=_on_raw_changed,
    )  # type: ignore
    use_env_map: BoolProperty(
        name="Use Env/Cube Map",
        description="Treat environment cubemap as refraction flag source on export when available",
        default=False,
        update=_on_use_env_map_changed,
    )  # type: ignore
    use_ref_map: BoolProperty(
        name="Use Refraction Map",
        description="Use Refraction Map (_ref) image as bit 18 source",
        default=False,
        update=_on_use_ref_map_changed,
    )  # type: ignore
    ref_env_notice: StringProperty(
        name="Ref/Env Notice",
        default="",
        options={'HIDDEN'},
    )  # type: ignore

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
        max=0.1,
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
    return any("Meshes_Collection" in col.name for col in obj.users_collection)

def _in_ground_decal_collection(obj: bpy.types.Object) -> bool:
    return any(col.name == "GroundDecal_Collection" for col in obj.users_collection)

def _highest_relevant_bit(value: int) -> int:
    if value <= 0:
        return 7  # show at least 0..7 when nothing is set
    h = value.bit_length() - 1
    return min(max(h, 7), 31)

def _active_mesh(ctx) -> bpy.types.Object | None:
    o = getattr(ctx, "object", None)
    if o and o.type == "MESH" and (_in_meshes_collection(o) or _in_ground_decal_collection(o)):
        return o
    return None

def _find_wind_modifier(obj: bpy.types.Object) -> bpy.types.Modifier | None:
    if not obj or obj.type != 'MESH':
        return None
    for mod in obj.modifiers:
        if mod.type == 'NODES' and "WindEffect" in mod.name:
            return mod
    return None

def _create_wind_modifier(obj: bpy.types.Object) -> bool:
    """Create the WindEffect geometry-nodes modifier on a mesh if it does not exist."""
    if not obj or obj.type != 'MESH':
        return False
    if _find_wind_modifier(obj):
        return False

    modifier = obj.modifiers.new(name="WindEffect", type="NODES")
    node_group = bpy.data.node_groups.new("WindEffectTree", "GeometryNodeTree")

    if bpy.app.version[0] >= 4:
        node_group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        node_group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
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

    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = _get_wind_height_extent(obj)
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

    return True


class DRS_OT_AddWindModifier(Operator):
    bl_idname = "drs.add_wind_modifier"
    bl_label = "Add Wind Modifier"
    bl_description = "Adds the WindEffect Geometry Nodes modifier to the active DRS mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        o = _active_mesh(context)
        return o is not None and _find_wind_modifier(o) is None

    def execute(self, context):
        o = _active_mesh(context)
        if o is None:
            self.report({'WARNING'}, "Select a mesh inside 'Meshes_Collection' or 'GroundDecal_Collection'.")
            return {'CANCELLED'}

        created = _create_wind_modifier(o)
        if not created:
            self.report({'INFO'}, "Wind modifier already exists on the selected mesh.")
            return {'CANCELLED'}

        if hasattr(o, "drs_wind") and o.drs_wind:
            _update_wind_nodes(o.drs_wind)

        self.report({'INFO'}, "Wind modifier added.")
        return {'FINISHED'}

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

        has_env_cubemap = _has_env_cubemap_for_object(o, ctx)
        has_refraction_map = _has_refraction_map_for_object(o)

        notice_text = str(getattr(flags, "ref_env_notice", "") or "")
        if notice_text:
            notice_box = layout.box()
            notice_box.alert = True
            notice_box.label(text=notice_text, icon="ERROR")

        if not (has_env_cubemap or has_refraction_map):
            layout.label(text="Use Refraction Map / Use Env/Cube Map requires a Refraction Map (_ref) or Environment Cubemap (_env) with an image.", icon="INFO")

        # max_known = max(KNOWN_MATERIAL_FLAGS.keys()) if KNOWN_MATERIAL_FLAGS else 0

        col = layout.column(align=True)
        for i in range(_MAX_BITS):
            if i == 18:
                col.prop(flags, "use_ref_map", text="Use Refraction Map (Bit 18)")
                if not has_refraction_map:
                    col.label(text="Ref toggle needs Refraction Map (_ref) image.", icon="INFO")
                env_row = col.row()
                env_row.enabled = True
                env_row.prop(flags, "use_env_map", text="Use Env/Cube Map (Bit 18)")
                if not has_env_cubemap:
                    col.label(text="Env toggle needs Environment Cubemap (_env) image.", icon="INFO")
                continue
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
        has_wind_modifier = _find_wind_modifier(o) is not None

        row = layout.row()
        row.enabled = not has_wind_modifier
        row.operator("drs.add_wind_modifier", icon="GEOMETRY_NODES")

        layout.use_property_split = True
        layout.use_property_decorate = False
        value_col = layout.column()
        value_col.enabled = has_wind_modifier
        value_col.prop(w, "wind_response")
        value_col.prop(w, "wind_height")

# --- Register -----------------------------------------------------------------
classes = (
    DRS_MaterialFlagsPG,
    DRS_FlowPG,
    DRS_WindPG,
    DRS_OT_AddWindModifier,
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
