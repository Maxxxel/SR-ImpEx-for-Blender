import bpy


def get_actions() -> list:
    """Get all actions relevant to the current selected object."""
    obj = bpy.context.active_object
    if obj is None:
        return []

    actions = []
    for action in bpy.data.actions:
        # Check if any FCurve data_path refers to the current object or its data
        for fcurve in action.fcurves:
            if fcurve.data_path.startswith(("location", "rotation", "scale")):
                actions.append(action.name)
                break
            if obj.type == "ARMATURE" and fcurve.data_path.startswith("pose.bones"):
                actions.append(action.name)
                break

    return actions


def export_ska(
    context: bpy.types.Context,
    filepath: str,
):
    pass
