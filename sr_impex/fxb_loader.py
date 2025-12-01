"""
FXB Effect Loader for Blender
Loads and visualizes Battleforge .fxb effect files in Blender.

FXB Structure:
- FxMaster root with .special_effect
- .special_effect.children contains Element list
- Each Element may have sub-FX like .emitter, .light, etc.
- Elements have .tracks containing animated parameters

Currently supports:
- Emitter (particle systems) with track-based animation

Designed to easily extend with additional FX types:
Light, StaticDecal, Sound, Billboard, CameraShake, EffectMesh, Effect,
Trail, PhysicGroup, Physic, Decal, Force, ForcePoint, AnimatedMesh,
AnimatedMeshMaterial, WaterDecal, SfpSystem, SfpEmitter, SfpForceField
"""

from __future__ import annotations
import os
from typing import Optional, Dict, Any, List
from mathutils import Vector
import bpy

from bpy_extras.image_utils import load_image
from .drs_definitions import (
    DRS, FxMaster, Element, Emitter, Track, TrackType,
    FloatKeyframe, Vector3Keyframe
)
from .message_logger import MessageLogger

logger = MessageLogger()


# ============================================================================
# FX Type Registry (Plugin Architecture)
# ============================================================================

class FXTypeHandler:
    """Base class for FX type handlers."""
    
    fx_type: str = "Unknown"
    
    def can_handle(self, element: Element) -> bool:
        """Check if this handler can process the given Element."""
        return False
    
    def create_visual(
        self,
        element: Element,
        parent_object: bpy.types.Object,
        context: Dict[str, Any]
    ) -> Optional[bpy.types.Object]:
        """
        Create a visual representation of this Element in Blender.
        
        Args:
            element: Element from FXB special_effect.children
            parent_object: The parent empty/object to attach to
            context: Additional context (effects_dir, effect_name, etc.)
            
        Returns:
            Created Blender object or None
        """
        raise NotImplementedError


class FXRegistry:
    """Registry for FX type handlers."""
    
    def __init__(self):
        self._handlers: list[FXTypeHandler] = []
    
    def register(self, handler: FXTypeHandler):
        """Register a new FX type handler."""
        self._handlers.append(handler)
        logger.log(
            f"Registered FX handler: {handler.fx_type}",
            "Info",
            "INFO"
        )
    
    def get_handler(self, element: Element) -> Optional[FXTypeHandler]:
        """Find a handler that can process the given Element."""
        for handler in self._handlers:
            if handler.can_handle(element):
                return handler
        return None
    
    def list_supported_types(self) -> list[str]:
        """Return list of supported FX types."""
        return [h.fx_type for h in self._handlers]


# Global registry instance
_fx_registry = FXRegistry()


# ============================================================================
# Emitter Handler (Particle System)
# ============================================================================

class EmitterHandler(FXTypeHandler):
    """Handler for particle emitter effects."""
    
    fx_type = "Emitter"
    
    def can_handle(self, element: Element) -> bool:
        """Check if element has an emitter."""
        return hasattr(element, 'emitter') and element.emitter is not None
    
    @staticmethod
    def _get_track_by_name(tracks: List[Track], track_type_name: str) -> Optional[Track]:
        """
        Find track by type name.
        """
        # TrackType is dict mapping int -> string name
        track_type_id = None
        for tname, tid in TrackType.items():
            if tname.strip() == track_type_name.strip():
                track_type_id = tid
                break
        
        if track_type_id is None:
            return None
        
        for track in tracks:
            if track.track_type == track_type_id:
                return track
        return None
    
    @staticmethod
    def _get_track_first_value(track: Optional[Track]) -> Any:
        """
        Extract first keyframe value from track.
        """
        if not track or not track.entries or len(track.entries) == 0:
            return None
        
        first_entry = track.entries[0]
        if isinstance(first_entry, FloatKeyframe):
            return first_entry.data
        elif isinstance(first_entry, Vector3Keyframe):
            return (first_entry.data[0], first_entry.data[1], first_entry.data[2])
        return None
    
    def create_visual(
        self,
        element: Element,
        parent_object: bpy.types.Object,
        context: Dict[str, Any]
    ) -> Optional[bpy.types.Object]:
        """
        Create a geometry nodes particle system for the emitter.
        """
        emitter: Emitter = element.emitter
        effect_name = context.get('effect_name', 'Effect')
        
        # Extract texture from Element (stored in emitter.emitter_file or element name)
        texture_file = emitter.emitter_file if emitter.emitter_file else None
        if not texture_file and '.' in element.name:
            # Sometimes texture is in element name like "Color_Particles.dds"
            texture_file = element.name
        
        # Create mesh emitter object (point for geometry nodes)
        bpy.ops.mesh.primitive_plane_add(size=0.5, location=parent_object.location)
        emitter_obj = bpy.context.object
        emitter_obj.name = f"{effect_name}_{element.name}_Emitter"
        
        parent_collection = (
            parent_object.users_collection[0]
            if parent_object.users_collection
            else bpy.context.scene.collection
        )

        # primitive_plane_add already linked emitter_obj to current collection.
        # If it's not the parent collection, move it once.
        if parent_collection not in emitter_obj.users_collection:
            for col in list(emitter_obj.users_collection):
                col.objects.unlink(emitter_obj)
            parent_collection.objects.link(emitter_obj)
        
        emitter_obj.parent = parent_object
        emitter_obj.matrix_parent_inverse.identity()
        
        # Store emitter metadata
        emitter_obj['fx_type'] = 'Emitter'
        emitter_obj['fx_element_name'] = element.name
        emitter_obj['particle_count'] = emitter.particle_count
        
        # Extract track data
        particle_count = 100
        particle_size = 1.0
        speed_factor = 1.0
        emitter_scale = (1.5, 0, 1.5)  # Default volume
        
        if element.tracks:
            particles_track = self._get_track_by_name(element.tracks, "Particles")
            if particles_track:
                particles_val = self._get_track_first_value(particles_track)
                if particles_val:
                    particle_count = int(particles_val)
                    emitter_obj['particles'] = particle_count
            
            start_size_track = self._get_track_by_name(element.tracks, "Start Size")
            if start_size_track:
                size_val = self._get_track_first_value(start_size_track)
                if size_val:
                    particle_size = size_val
                    emitter_obj['start_size'] = particle_size
            
            speed_factor_track = self._get_track_by_name(element.tracks, "Speed Factor")
            if speed_factor_track:
                speed = self._get_track_first_value(speed_factor_track)
                if speed:
                    speed_factor = speed
                    emitter_obj['speed_factor'] = speed_factor
            
            emitter_geom_track = self._get_track_by_name(element.tracks, "Emitter Geometry")
            if emitter_geom_track:
                geom = self._get_track_first_value(emitter_geom_track)
                if geom and isinstance(geom, tuple):
                    emitter_scale = geom
                    emitter_obj.scale = geom
                    emitter_obj['emitter_geometry'] = geom
        
        # --------------------------------------------------------------------
        # Geometry Nodes particle system (FIXED)
        # --------------------------------------------------------------------
        geo_mod = emitter_obj.modifiers.new(name="ParticleSystem", type='NODES')

        node_group = bpy.data.node_groups.new(
            name=f"{effect_name}_Particles", type='GeometryNodeTree'
        )
        geo_mod.node_group = node_group

        # Ensure sockets exist
        if not node_group.interface.items_tree:
            node_group.interface.new_socket(
                name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry'
            )
            node_group.interface.new_socket(
                name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry'
            )

        nodes = node_group.nodes
        links = node_group.links
        nodes.clear()

        input_node = nodes.new('NodeGroupInput')
        input_node.location = (-900, 0)
        output_node = nodes.new('NodeGroupOutput')
        output_node.location = (900, 0)

        distribute_node = nodes.new('GeometryNodeDistributePointsOnFaces')
        distribute_node.location = (-600, 0)
        distribute_node.distribute_method = 'POISSON'

        # Use Distance Min instead of Density for more predictable counts
        # Calculate spacing to approximate desired particle count
        import math
        plane_area = 0.5 * 0.5  # Size from primitive_plane_add
        spacing = math.sqrt(plane_area / max(particle_count, 1)) * 0.8
        distribute_node.inputs['Distance Min'].default_value = spacing
        distribute_node.inputs['Density Max'].default_value = 10000.0  # High enough
        distribute_node.inputs['Seed'].default_value = 0

        links.new(input_node.outputs['Geometry'], distribute_node.inputs['Mesh'])
        points_out = distribute_node.outputs['Points']

        # ------------------------------------------------------------
        # Flipbook frame attribute (driven by Scene Time)
        # We animate columns within the fixed row.
        # ------------------------------------------------------------
        scene_time = nodes.new('GeometryNodeInputSceneTime')
        scene_time.location = (-350, 250)

        # frames per row in your atlas
        frames_per_row = 4.0

        # approximate flipbook FPS: base 8 * speed_factor from FX
        flipbook_fps = 8.0 * float(speed_factor)

        # time_seconds * fps -> frame_float
        mul_fps = nodes.new('ShaderNodeMath')
        mul_fps.location = (-150, 250)
        mul_fps.operation = 'MULTIPLY'
        mul_fps.inputs[1].default_value = flipbook_fps

        # frame_float mod frames_per_row
        mod_frames = nodes.new('ShaderNodeMath')
        mod_frames.location = (50, 250)
        mod_frames.operation = 'MODULO'
        mod_frames.inputs[1].default_value = frames_per_row

        # floor to integer frame 0..3
        floor_frame = nodes.new('ShaderNodeMath')
        floor_frame.location = (250, 250)
        floor_frame.operation = 'FLOOR'

        # store as named attribute "frame"
        store_frame = nodes.new('GeometryNodeStoreNamedAttribute')
        store_frame.location = (450, 120)
        store_frame.domain = 'POINT'
        store_frame.data_type = 'FLOAT'
        store_frame.inputs['Name'].default_value = "frame"

        # wiring
        links.new(scene_time.outputs['Seconds'], mul_fps.inputs[0])
        links.new(mul_fps.outputs[0], mod_frames.inputs[0])
        links.new(mod_frames.outputs[0], floor_frame.inputs[0])

        links.new(points_out, store_frame.inputs['Geometry'])
        links.new(floor_frame.outputs[0], store_frame.inputs['Value'])

        # ------------------------------------------------------------
        # Flipbook frame attribute (random per particle, static)
        # Each particle picks one of the 4 columns in the fixed row.
        # ------------------------------------------------------------
        rand = nodes.new('FunctionNodeRandomValue')
        rand.location = (-250, 220)
        rand.data_type = 'INT'
        rand.inputs['Min'].default_value = 0
        rand.inputs['Max'].default_value = 3  # 4 frames: 0,1,2,3

        store_frame = nodes.new('GeometryNodeStoreNamedAttribute')
        store_frame.location = (-50, 120)
        store_frame.domain = 'POINT'
        store_frame.data_type = 'INT'
        store_frame.inputs['Name'].default_value = "frame"

        links.new(points_out, store_frame.inputs['Geometry'])
        links.new(rand.outputs['Value'], store_frame.inputs['Value'])

        points_out = store_frame.outputs['Geometry']

        # Instance on points
        instance_node = nodes.new('GeometryNodeInstanceOnPoints')
        instance_node.location = (150, 0)

        # Billboard quad (single face)
        mesh_plane_node = nodes.new('GeometryNodeMeshGrid')
        mesh_plane_node.location = (-250, -250)
        mesh_plane_node.inputs['Size X'].default_value = float(particle_size)
        mesh_plane_node.inputs['Size Y'].default_value = float(particle_size)
        mesh_plane_node.inputs['Vertices X'].default_value = 2
        mesh_plane_node.inputs['Vertices Y'].default_value = 2

        set_material_node = nodes.new('GeometryNodeSetMaterial')
        set_material_node.location = (-50, -250)

        realize_node = nodes.new('GeometryNodeRealizeInstances')
        realize_node.location = (400, 0)

        shade_smooth_node = nodes.new('GeometryNodeSetShadeSmooth')
        shade_smooth_node.location = (650, 0)

        # Links
        links.new(points_out, instance_node.inputs['Points'])
        links.new(mesh_plane_node.outputs['Mesh'], set_material_node.inputs['Geometry'])
        links.new(set_material_node.outputs['Geometry'], instance_node.inputs['Instance'])
        links.new(instance_node.outputs['Instances'], realize_node.inputs['Geometry'])
        links.new(realize_node.outputs['Geometry'], shade_smooth_node.inputs['Geometry'])
        links.new(shade_smooth_node.outputs['Geometry'], output_node.inputs['Geometry'])


        # Handle texture and create material
        if texture_file:
            effects_dir = context.get('effects_dir', '')
            texture_path = os.path.join(effects_dir, 'textures', texture_file)
            emitter_obj['texture_file'] = texture_file
            emitter_obj['texture_path'] = texture_path
            
            logger.log(f"Looking for texture at: {texture_path}", "Info", "INFO")
            
            if os.path.exists(texture_path):
                # Create material with sprite sheet support
                mat = bpy.data.materials.new(name=f"{effect_name}_ParticleMat")
                mat.use_nodes = True
                mat.blend_method = 'BLEND'
                mat_nodes = mat.node_tree.nodes
                if bpy.app.version < (4, 3):
                    mat.shadow_method = "NONE"
                mat_nodes.clear()
                
                # Output
                output = mat_nodes.new('ShaderNodeOutputMaterial')
                output.location = (600, 0)
                
                add_shader = mat_nodes.new('ShaderNodeAddShader')
                add_shader.location = (400, 0)
                
                # Emission for glow
                emission = mat_nodes.new('ShaderNodeEmission')
                emission.location = (200, 100)
                emission.inputs['Strength'].default_value = 2.0
                
                # Transparent
                transparent = mat_nodes.new('ShaderNodeBsdfTransparent')
                transparent.location = (200, -100)
                
                # UV Map for sprite sheet (2nd row = Y offset 0.25-0.5 in 4x4 grid)
                tex_coord = mat_nodes.new('ShaderNodeTexCoord')
                tex_coord.location = (-600, -200)
                
                # Mapping to select 2nd row of 4x4 sprite sheet
                mapping = mat_nodes.new('ShaderNodeMapping')
                mapping.location = (-400, -200)
                # Scale UV to show only 1/4th in each direction (4x4 grid)
                mapping.inputs['Scale'].default_value = (4.0, 4.0, 1.0)
                # Offset Y by -0.25 to show 2nd row (rows from top: 0, -0.25, -0.5, -0.75)
                mapping.inputs['Location'].default_value = (0.0, -0.25, 0.0)
                
                # Image texture
                tex_image = mat_nodes.new('ShaderNodeTexImage')
                tex_image.location = (-200, 0)
                tex_image.interpolation = 'Linear'
                
                # Load texture
                try:
                    img = load_image(
                        os.path.basename(texture_path),
                        os.path.dirname(texture_path),
                        check_existing=True,
                        place_holder=False,
                        recursive=False,
                    )
                    img.alpha_mode = 'STRAIGHT'
                    tex_image.image = img
                    logger.log(f"Successfully loaded texture: {texture_file}", "Info", "INFO")
                except Exception as e:
                    logger.log(f"Failed to load texture {texture_path}: {e}", "Warning", "WARNING")

                attr_frame = mat_nodes.new('ShaderNodeAttribute')
                attr_frame.attribute_name = "frame"

                # frame / 4 -> x offset (0, 0.25, 0.5, 0.75)
                frame_div = mat_nodes.new('ShaderNodeMath')
                frame_div.location = (-200, 80)
                frame_div.operation = 'DIVIDE'
                frame_div.inputs[1].default_value = 4.0

                # add to UV.x after scaling
                separate_uv = mat_nodes.new('ShaderNodeSeparateXYZ')
                separate_uv.location = (-250, -140)

                combine_uv = mat_nodes.new('ShaderNodeCombineXYZ')
                combine_uv.location = (0, -140)

                add_x = mat_nodes.new('ShaderNodeMath')
                add_x.location = (-50, -60)
                add_x.operation = 'ADD'

                # Link material nodes
                mat_links = mat.node_tree.links
                # UV -> mapping (row select)
                mat_links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

                # mapping output -> separate
                mat_links.new(mapping.outputs['Vector'], separate_uv.inputs['Vector'])

                # frame attribute -> /4
                mat_links.new(attr_frame.outputs['Fac'], frame_div.inputs[0])


                # add frame offset to X
                mat_links.new(separate_uv.outputs['X'], add_x.inputs[0])
                mat_links.new(frame_div.outputs[0], add_x.inputs[1])

                # recombine UV
                mat_links.new(add_x.outputs[0], combine_uv.inputs['X'])
                mat_links.new(separate_uv.outputs['Y'], combine_uv.inputs['Y'])
                mat_links.new(separate_uv.outputs['Z'], combine_uv.inputs['Z'])

                # alpha -> emission strength
                alpha_mul = mat_nodes.new('ShaderNodeMath')
                alpha_mul.location = (0, 100)
                alpha_mul.operation = 'MULTIPLY'
                alpha_mul.inputs[1].default_value = 2.0  # boost

                # final UV to texture
                mat_links.new(tex_image.outputs['Color'], emission.inputs['Color'])
                mat_links.new(tex_image.outputs['Alpha'], alpha_mul.inputs[0])
                mat_links.new(alpha_mul.outputs[0], emission.inputs['Strength'])

                mat_links.new(emission.outputs['Emission'], add_shader.inputs[0])
                mat_links.new(transparent.outputs['BSDF'], add_shader.inputs[1])
                mat_links.new(add_shader.outputs['Shader'], output.inputs['Surface'])
                
                # Assign material to geometry nodes
                set_material_node.inputs['Material'].default_value = mat
                
                logger.log(f"Created geometry nodes particle system with sprite sheet texture (row 2)", "Info", "INFO")
            else:
                logger.log(f"Texture file not found: {texture_path}", "Warning", "WARNING")
        else:
            logger.log(f"No texture file specified for element: {element.name}", "Warning", "WARNING")
        
        logger.log(
            f"Created emitter '{element.name}' with {particle_count} particles using Geometry Nodes",
            "Info",
            "INFO"
        )
        
        return emitter_obj


# ============================================================================
# Placeholder Handlers (for future implementation)
# ============================================================================

class PlaceholderHandler(FXTypeHandler):
    """Generic placeholder for unsupported FX types."""
    
    def __init__(self, fx_type: str):
        self.fx_type = fx_type
    
    def can_handle(self, element: Element) -> bool:
        """Placeholder - never handles anything."""
        return False
    
    def create_visual(
        self,
        element: Element,
        parent_object: bpy.types.Object,
        context: Dict[str, Any]
    ) -> Optional[bpy.types.Object]:
        """Placeholder - creates a simple empty."""
        logger.log(
            f"FX type '{self.fx_type}' not yet implemented",
            "Info",
            "INFO"
        )
        return None


# ============================================================================
# Main FXB Loader
# ============================================================================

def load_fxb_effect(
    fxb_file_path: str,
    parent_object: bpy.types.Object,
    effect_name: Optional[str] = None
) -> Optional[bpy.types.Object]:
    """
    Load an FXB effect file and create a visual representation in Blender.
    
    FXB files are DRS format with FxMaster root containing:
    - .special_effect.children: List of Element objects
    - Each Element may have .emitter, .light, etc. sub-FX types
    - Elements have .tracks with animated parameters
    
    Args:
        fxb_file_path: Full path to the .fxb file
        parent_object: Parent object (usually a locator) to attach the effect to
        effect_name: Optional name for the effect (defaults to filename)
        
    Returns:
        The root empty object representing the effect, or None on failure
    """
    
    if not os.path.exists(fxb_file_path):
        logger.log(
            f"FXB file not found: {fxb_file_path}",
            "Warning",
            "WARNING"
        )
        return None
    
    # Default effect name from filename
    if not effect_name:
        effect_name = os.path.splitext(os.path.basename(fxb_file_path))[0]
    
    try:
        # Load the DRS file (FXB files are DRS format)
        fxb_drs: DRS = DRS().read(fxb_file_path)
        
        # FXB files have FxMaster structure
        if not hasattr(fxb_drs, 'fx_master') or not fxb_drs.fx_master:
            logger.log(
                f"No FxMaster found in {fxb_file_path}",
                "Warning",
                "WARNING"
            )
            return None
        
        fx_master: FxMaster = fxb_drs.fx_master
        
        # Create root effect empty
        effect_root = bpy.data.objects.new(f"Effect_{effect_name}", None)
        effect_root.empty_display_type = 'CUBE'
        effect_root.empty_display_size = 0.2
        effect_root['fx_file'] = os.path.basename(fxb_file_path)
        effect_root['fx_length'] = fx_master.length
        effect_root['fx_play_length'] = fx_master.play_length
        
        # Link to parent's collection
        parent_collection = parent_object.users_collection[0] if parent_object.users_collection else bpy.context.scene.collection
        parent_collection.objects.link(effect_root)
        
        # Parent to locator
        effect_root.parent = parent_object
        effect_root.matrix_parent_inverse.identity()
        
        # Build context for handlers
        effects_dir = os.path.dirname(fxb_file_path)
        context = {
            'effect_name': effect_name,
            'effects_dir': effects_dir,
            'fx_master': fx_master,
        }
        
        # Extract child elements from special_effect
        elements = _extract_fx_elements(fx_master)
        
        if not elements:
            logger.log(
                f"No FX elements found in {fxb_file_path}",
                "Info",
                "INFO"
            )
            return effect_root
        
        created_count = 0
        for element in elements:
            handler = _fx_registry.get_handler(element)
            
            if handler:
                obj = handler.create_visual(element, effect_root, context)
                if obj:
                    created_count += 1
            else:
                # Unknown FX type - create a simple marker
                _create_unknown_fx_marker(element, effect_root)
        
        logger.log(
            f"Loaded effect '{effect_name}' with {created_count} components from {len(elements)} elements",
            "Info",
            "INFO"
        )
        
        return effect_root
        
    except Exception as e:
        logger.log(
            f"Failed to load FXB effect {fxb_file_path}: {e}",
            "Error",
            "ERROR"
        )
        import traceback
        traceback.print_exc()
        return None


def _extract_fx_elements(fx_master: FxMaster) -> List[Element]:
    """
    Extract FX elements from FxMaster.special_effect.children.
    
    Args:
        fx_master: FxMaster instance from DRS
        
    Returns:
        List of Element objects
    """
    elements = []
    
    try:
        if hasattr(fx_master, 'special_effect') and fx_master.special_effect:
            special_effect = fx_master.special_effect
            
            if hasattr(special_effect, 'children') and special_effect.children:
                elements.extend(special_effect.children)
                logger.log(
                    f"Found {len(elements)} elements in special_effect.children",
                    "Info",
                    "INFO"
                )
    except Exception as e:
        logger.log(
            f"Error extracting FX elements: {e}",
            "Warning",
            "WARNING"
        )
    
    return elements


def _create_unknown_fx_marker(element: Element, parent_object: bpy.types.Object):
    """Create a simple marker for unsupported FX element types."""
    try:
        marker_name = f"{element.name}_Unknown"
        marker = bpy.data.objects.new(marker_name, None)
        marker.empty_display_type = 'PLAIN_AXES'
        marker.empty_display_size = 0.1
        
        parent_collection = parent_object.users_collection[0] if parent_object.users_collection else bpy.context.scene.collection
        parent_collection.objects.link(marker)
        
        marker.parent = parent_object
        marker.matrix_parent_inverse.identity()
        
        # Store element name and type
        marker['fx_element_name'] = element.name
        marker['fx_element_type'] = hex(element.element_type_header) if hasattr(element, 'element_type_header') else 'unknown'
        marker['fx_track_count'] = len(element.tracks) if hasattr(element, 'tracks') and element.tracks else 0
        
        logger.log(
            f"Created marker for unsupported element: {element.name}",
            "Info",
            "INFO"
        )
        
    except Exception as e:
        logger.log(
            f"Failed to create unknown FX marker: {e}",
            "Warning",
            "WARNING"
        )


# ============================================================================
# Initialization
# ============================================================================

def initialize_fx_handlers():
    """Register all FX type handlers."""
    
    # Register implemented handlers
    _fx_registry.register(EmitterHandler())
    
    # Register placeholders for future types
    # (These won't handle anything yet but document what's planned)
    future_types = [
        'Light', 'StaticDecal', 'Sound', 'Billboard', 'CameraShake',
        'EffectMesh', 'Effect', 'Trail', 'PhysicGroup', 'Physic',
        'Decal', 'Force', 'ForcePoint', 'AnimatedMesh',
        'AnimatedMeshMaterial', 'WaterDecal', 'SfpSystem',
        'SfpEmitter', 'SfpForceField'
    ]
    
    # Don't register placeholders to registry to keep it clean
    # Just document them here for future reference
    
    logger.log(
        f"FXB loader initialized. Supported types: {', '.join(_fx_registry.list_supported_types())}",
        "Info",
        "INFO"
    )


# Initialize on module load
initialize_fx_handlers()
