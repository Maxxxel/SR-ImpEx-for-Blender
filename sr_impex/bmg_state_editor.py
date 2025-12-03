"""
BMG Building State Editor

UI panel and operators for managing building mesh states (S0, S2, debris).
Allows switching between undamaged, damaged, and destruction states.
"""

import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty, EnumProperty


class BMG_OT_SwitchMeshState(Operator):
    """Switch the visible state of a MeshSet"""
    bl_idname = "bmg.switch_mesh_state"
    bl_label = "Switch Mesh State"
    bl_options = {'REGISTER', 'UNDO'}
    
    state: EnumProperty(
        name="State",
        description="Which state to display",
        items=[
            ('S0', "S0 - Undamaged", "Show undamaged building state"),
            ('S2', "S2 - Damaged", "Show damaged building state"),
            ('S2_with_debris', "S2 + Debris", "Show damaged state with debris"),
            ('S3_destroyed', "S3 - Destroyed", "Show only debris (destroyed state)"),
            ('all_states', "All States", "Show all states (for editing)"),
        ],
        default='S0'
    )
    
    @classmethod
    def poll(cls, context):
        """Only enable if a MeshSet collection is selected or active"""
        if context.collection:
            return context.collection.name.startswith("MeshSet_")
        if context.active_object and context.active_object.users_collection:
            for col in context.active_object.users_collection:
                if col.name.startswith("MeshSet_"):
                    return True
        return False
    
    def execute(self, context):
        from .drs_utility import switch_meshset_state
        
        # Try to get MeshSet collection from context
        meshset_collection = None
        
        if context.collection and context.collection.name.startswith("MeshSet_"):
            meshset_collection = context.collection
        elif context.active_object:
            for col in context.active_object.users_collection:
                if col.name.startswith("MeshSet_"):
                    meshset_collection = col
                    break
        
        if not meshset_collection:
            self.report({'WARNING'}, "No MeshSet collection found")
            return {'CANCELLED'}
        
        # Switch the state
        switch_meshset_state(meshset_collection, self.state)
        
        # Update viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        self.report({'INFO'}, f"Switched to state: {self.state}")
        return {'FINISHED'}


class BMG_OT_SwitchAllMeshSetsState(Operator):
    """Switch the visible state of all MeshSets in the current BMG model"""
    bl_idname = "bmg.switch_all_meshsets_state"
    bl_label = "Switch All MeshSets State"
    bl_options = {'REGISTER', 'UNDO'}
    
    state: EnumProperty(
        name="State",
        description="Which state to display",
        items=[
            ('S0', "S0 - Undamaged", "Show undamaged building state"),
            ('S2', "S2 - Damaged", "Show damaged building state"),
            ('S2_with_debris', "S2 + Debris", "Show damaged state with debris"),
            ('S3_destroyed', "S3 - Destroyed", "Show only debris (destroyed state)"),
            ('all_states', "All States", "Show all states (for editing)"),
        ],
        default='S0'
    )
    
    @classmethod
    def poll(cls, context):
        """Only enable if a DRSModel collection exists in the scene"""
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                return True
        return False
    
    def execute(self, context):
        from .drs_utility import switch_meshset_state
        
        count = 0
        # Find all DRSModel collections first, then look for MeshSetGrid children
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                # Look for MeshSetGrid in children
                for child in col.children:
                    if child.name.startswith("MeshSetGrid_"):
                        # Find all MeshSet children
                        for meshset in child.children:
                            if meshset.name.startswith("MeshSet_"):
                                switch_meshset_state(meshset, self.state)
                                count += 1
        
        if count == 0:
            self.report({'WARNING'}, "No MeshSet collections found")
            return {'CANCELLED'}
        
        # Update viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        self.report({'INFO'}, f"Switched {count} MeshSet(s) to state: {self.state}")
        return {'FINISHED'}


class BMG_PT_MeshStateEditor(Panel):
    """Panel for controlling BMG building mesh states"""
    bl_label = "BMG Mesh State Editor"
    bl_idname = "BMG_PT_mesh_state_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BMG Editor'
    
    @classmethod
    def poll(cls, context):
        """Only show panel if a BMG model is present"""
        for col in bpy.data.collections:
            if col.name.startswith("DRSModel_"):
                for child in col.children_recursive:
                    if child.name.startswith("MeshSetGrid_"):
                        return True
        return False
    
    def draw(self, context):
        layout = self.layout
        
        # All MeshSets section
        box = layout.box()
        box.label(text="All MeshSets in Scene", icon='WORLD')
        
        col = box.column(align=True)
        col.label(text="Switch All States:")
        
        op = col.operator("bmg.switch_all_meshsets_state", text="Show undamaged", icon='MESH_CUBE')
        op.state = 'S0'
        
        op = col.operator("bmg.switch_all_meshsets_state", text="Show damaged", icon='MOD_EXPLODE')
        op.state = 'S2'
        
        op = col.operator("bmg.switch_all_meshsets_state", text="Show damaged + Debris (should look undamaged)", icon='PHYSICS')
        op.state = 'S2_with_debris'
        
        op = col.operator("bmg.switch_all_meshsets_state", text="Show Debris", icon='PARTICLE_DATA')
        op.state = 'S3_destroyed'
        
        col.separator()
        op = col.operator("bmg.switch_all_meshsets_state", text="Show All Stages", icon='PRESET')
        op.state = 'all_states'


# Registration
classes = (
    BMG_OT_SwitchMeshState,
    BMG_OT_SwitchAllMeshSetsState,
    BMG_PT_MeshStateEditor,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
