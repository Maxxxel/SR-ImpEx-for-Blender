import json
from os.path import dirname, realpath
from typing import List
from collections import defaultdict
from mathutils import Vector, Quaternion
import bpy

from .ska_definitions import SKA, SKAHeader, SKAKeyframe
from .message_logger import MessageLogger

resource_dir = dirname(realpath(__file__)) + "/resources"
logger = MessageLogger()

with open(resource_dir + "/bone_versions.json", "r", encoding="utf-8") as f:
    bones_list = json.load(f)


def get_current_collection() -> bpy.types.Collection:
    """Returns the active collection or none."""
    return bpy.context.view_layer.active_layer_collection.collection


def get_current_armature() -> bpy.types.Object:
    """Returns the armature of the current collection or none."""
    current_collection = get_current_collection()
    if current_collection is None:
        return None

    for obj in current_collection.objects:
        if obj.type == "ARMATURE":
            return obj

    return None


def get_actions() -> List[str]:
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


def export_ska(context: bpy.types.Context, filepath: str, action_name: str) -> None:
    """Export the current scene to a .ska file."""
    # Find the Animation Data by the given action name in the current context
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action '{action_name}' not found in the current context.")

    # Get the frames per second of the current scene
    fps = bpy.context.scene.render.fps
    duration = action.frame_range[1] / fps

    # Get the Bones of the Armature
    armature = get_current_armature()
    if armature is None:
        raise ValueError("No armature selected.")

    location_fcurves: dict[str, list[bpy.types.FCurve]] = defaultdict(list)
    rotation_fcurves: dict[str, list[bpy.types.FCurve]] = defaultdict(list)
    # Print Number of Curves
    for fcurve in action.fcurves:
        if fcurve.data_path.endswith("location"):
            location_fcurves[fcurve.data_path].append(fcurve)
        elif fcurve.data_path.endswith("rotation_quaternion"):
            rotation_fcurves[fcurve.data_path].append(fcurve)
        else:
            logger.log(f"Skipping fcurve {fcurve.data_path}")

    # Assure we have the same sizes
    assert len(location_fcurves) == len(
        rotation_fcurves
    ), "Different number of location and rotation keyframes"

    # Bones Lib, with loc and rot attributes
    bone_lib = {}

    # Iterate over all location_fcurves and extract the location
    for data_path, fcurves in location_fcurves.items():
        # Get the bone name from the data path
        bone_name = data_path.split('"')[1]
        bone_lib[bone_name] = (
            {
                "loc_per_time": {"vec": [], "times": []},
                "rot_per_time": {"quat": [], "times": []},
            }
            if bone_name not in bone_lib
            else bone_lib[bone_name]
        )
        x_array = []
        y_array = []
        z_array = []

        for fcurve in fcurves:
            axis_index = fcurve.array_index

            assert axis_index < 3, f"Invalid axis {axis_index}"

            # We can have multiple values for X | Y | Z over time
            for kp in fcurve.keyframe_points:
                coordinate = kp.co[1]  # X | Y | Z value over time
                if axis_index == 0:
                    x_array.append(coordinate)
                    time = kp.co[0] / fps
                    # make it relative to the duration
                    time = time / duration
                    bone_lib[bone_name]["loc_per_time"]["times"].append(time)
                elif axis_index == 1:
                    y_array.append(coordinate)
                elif axis_index == 2:
                    z_array.append(coordinate)

        assert (
            len(x_array) == len(y_array) == len(z_array)
        ), "Different number of keyframes for X | Y | Z"

        # Generate XYZ pairs
        temp_loc_vec = list(zip(x_array, y_array, z_array))
        bone_lib[bone_name]["loc_per_time"]["vec"].extend(temp_loc_vec)

    # Iterate over all rotation_fcurves and extract the rotation
    for data_path, fcurves in rotation_fcurves.items():
        bone_name = data_path.split('"')[1]
        # We should have the bone in the bone_lib
        assert bone_name in bone_lib, f"Bone {bone_name} not found in the bone_lib"

        w_array = []
        x_array = []
        y_array = []
        z_array = []

        for fcurve in fcurves:
            axis_index = fcurve.array_index

            assert axis_index < 4, f"Invalid axis {axis_index}"

            temp_times = []
            for kp in fcurve.keyframe_points:
                coordinate = kp.co[1]  # W | X | Y | Z value over time
                if axis_index == 0:
                    w_array.append(coordinate)
                    time = kp.co[0] / fps
                    # make it relative to the duration
                    time = time / duration
                    bone_lib[bone_name]["rot_per_time"]["times"].append(time)
                elif axis_index == 1:
                    x_array.append(coordinate)
                elif axis_index == 2:
                    y_array.append(coordinate)
                elif axis_index == 3:
                    z_array.append(coordinate)

        assert (
            len(w_array) == len(x_array) == len(y_array) == len(z_array)
        ), "Different number of keyframes for W | X | Y | Z"

        # Generate WXYZ pairs
        temp_rot_quat = list(zip(w_array, x_array, y_array, z_array))
        bone_lib[bone_name]["rot_per_time"]["quat"].extend(temp_rot_quat)

    # Create Header, Time and Keyframes
    headers = []
    times = []
    keyframes: List[SKAKeyframe] = []

    last_tick = 0
    for bone_name, data in bone_lib.items():
        bone_id = bones_list.get(bone_name)
        if bone_id is None:
            logger.log(f"Bone {bone_name} not found in the bone_versions.json")
            return

        # Retrieve the bone from the armature's rest data
        armature_bone = armature.data.bones[bone_name]
        if armature_bone.parent:
            bind_matrix = (
                armature_bone.parent.matrix_local.inverted_safe()
                @ armature_bone.matrix_local
            )
        else:
            bind_matrix = armature_bone.matrix_local

        bind_loc = bind_matrix.to_translation()
        bind_rot = bind_matrix.to_quaternion()

        loc_header = SKAHeader()
        loc_header.type = 0
        loc_header.tick = last_tick
        loc_header.interval = len(data["loc_per_time"]["vec"])
        loc_header.bone_id = bone_id
        last_tick += loc_header.interval
        times.extend(data["loc_per_time"]["times"])
        headers.append(loc_header)

        for loc in data["loc_per_time"]["vec"]:
            original_loc = bind_rot @ Vector(loc) + bind_loc
            loc_keyframe = SKAKeyframe()
            loc_keyframe.w = 1.0
            loc_keyframe.x, loc_keyframe.y, loc_keyframe.z = original_loc[:]
            # Get the index of loca and pull the timing value
            index = data["loc_per_time"]["vec"].index(loc)
            time = data["loc_per_time"]["times"][index]
            if time == 0:
                loc_keyframe.tan_x = 0.0
                loc_keyframe.tan_y = 0.0
                loc_keyframe.tan_z = 0.0
                loc_keyframe.tan_w = 0.0
            else:
                pass  # TODO: implement smoothing
            keyframes.append(loc_keyframe)

        rot_header = SKAHeader()
        rot_header.type = 1
        rot_header.tick = last_tick
        rot_header.interval = len(data["rot_per_time"]["quat"])
        rot_header.bone_id = bone_id
        last_tick += rot_header.interval
        times.extend(data["rot_per_time"]["times"])
        headers.append(rot_header)

        for quat in data["rot_per_time"]["quat"]:
            stored_quat = Quaternion(quat)  # Assuming quat is in (w, x, y, z) order
            original_quat = bind_rot @ stored_quat
            rot_keyframe = SKAKeyframe()
            rot_keyframe.w, rot_keyframe.x, rot_keyframe.y, rot_keyframe.z = (
                original_quat[:]
            )
            # negative w to match the original implementation
            rot_keyframe.w = -rot_keyframe.w
            keyframes.append(rot_keyframe)
            index = data["rot_per_time"]["quat"].index(quat)
            time = data["rot_per_time"]["times"][index]
            if time == 0:
                rot_keyframe.tan_x = 0.0
                rot_keyframe.tan_y = 0.0
                rot_keyframe.tan_z = 0.0
                rot_keyframe.tan_w = 0.0
            else:
                pass

    # Create a new SKA file and write the action data to it
    ska_file = SKA()
    # We will sue type 6 for now
    ska_file.type = 6
    ska_file.duration = duration
    ska_file.repeat = 1  # TODO: get this from the action
    ska_file.stutter_mode = 2  # smooth animation
    ska_file.zeroes = [0, 0, 0]
    ska_file.header_count = len(headers)
    ska_file.headers = headers
    ska_file.time_count = len(times)
    ska_file.times = times
    ska_file.keyframes = keyframes
    # Write the SKA file to disk
    ska_file.write(filepath)

    logger.display()
