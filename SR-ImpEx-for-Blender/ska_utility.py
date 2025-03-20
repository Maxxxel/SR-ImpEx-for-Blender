import bpy


def get_current_collection() -> bpy.types.Collection:
    """Returns the active collection or none."""
    return bpy.context.view_layer.active_layer_collection.collection


def get_actions() -> list:
    """Get all actions relevant to the current selected object."""
    current_collection = get_current_collection()

    if current_collection is None:
        return []

    relevant_actions = set()

    # Iterate over all objects in the current collection
    for obj in current_collection.objects:
        if obj.animation_data:
            # Add the current active action of this object, if any
            if obj.animation_data.action:
                relevant_actions.add(obj.animation_data.action.name)

        # Additionally, find actions that animate this object indirectly via FCurves
        for action in bpy.data.actions:
            for fcurve in action.fcurves:
                # Check if the action references this object's properties or pose bones
                if fcurve.data_path.startswith(("location", "rotation", "scale")):
                    relevant_actions.add(action.name)
                    break
                if obj.type == "ARMATURE" and fcurve.data_path.startswith("pose.bones"):
                    relevant_actions.add(action.name)
                    break

    # Return sorted list for consistent ordering
    return sorted(relevant_actions)


def export_ska(
    context: bpy.types.Context,
    filepath: str,
):
    pass
