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
    
    # Assure we have the right collection Name -> Should be Armature_Collection
    if "Armature" not in current_collection.name:
        # We are for sure in the main Collection DRSModel... so we need to dig one level deeper
        for coll in current_collection.children:
            if "Armature" in coll.name:
                current_collection = coll
                break
        else:
            print("No Armature collection found.")
            return None

    for obj in current_collection.objects:
        if obj.type == "ARMATURE" and "Control_Rig" not in obj.name:
            return obj

    return None


def get_actions(current_collection: bpy.types.Collection = None) -> List[str]:
    """Get all actions relevant to the current selected object."""
    current_collection = get_current_collection() if current_collection is None else current_collection
    if current_collection is None:
        print("No active collection found.")
        return []
    # Check for the collection Name -> Should be Armature_Collection
    if "Armature" not in current_collection.name:
        # We are for sure in the main Collection DRSModel... so we need to dig one level deeper
        for coll in current_collection.children:
            if "Armature" in coll.name:
                current_collection = coll
                break
        else:
            print("No Armature collection found.")
            return []

    relevant_actions = set()

    # Iterate over all objects in the current collection
    for obj in current_collection.objects:
        if obj.animation_data and "Control_Rig" not in obj.name:
            # Add the current active action of this object, if any
            if obj.animation_data.action:
                relevant_actions.add(obj.animation_data.action.name)

        # Additionally, find actions that animate this object indirectly via FCurves
        for action in bpy.data.actions:
            # But avoid actions linked to Control_Rig Armatures
            if "Control_Rig" in action.name:
                continue
            
            for fcurve in action.fcurves:
                # Check if the action references this object's properties or pose bones
                if fcurve.data_path.startswith(("location", "rotation", "scale")):
                    relevant_actions.add(action.name)
                    break
                if obj.type == "ARMATURE" and fcurve.data_path.startswith("pose.bones") and not "Control_Rig" in obj.name:
                    # Extract the bone name from the data path
                    relevant_actions.add(action.name)
                    break

    # Return sorted list for consistent ordering
    return sorted(relevant_actions)

def generate_bone_id(bone_name: str) -> int:
    """Generate a unique bone ID based on the bone name."""
    # Generate a unique ID for the bone based on its name
    # This is a simple hash function, you can replace it with a more complex one if needed
    bone_id = sum(ord(char) for char in bone_name) % (2**32 - 1)
    return bone_id


def export_ska(context: bpy.types.Context, filepath: str, action_name: str) -> None:
    """Export the current scene to a .ska file."""
    # Find the Animation Data by the given action name in the current context
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action '{action_name}' not found in the current context.")
    
    try:
        frame_length = action["frame_length"]
    except Exception:
        frame_length = None
        print(f"Warning: Action {action_name} missing 'frame_length' property. Using frame range instead.")
    
    if frame_length is None:
        # Maybe we have a Animation created from scratch and not imported, then it doesent have this value, so we create it from the Action
        frame_length = action.frame_range[1] - action.frame_range[0]

    try:
        fps = action["original_fps"]
    except Exception:
        fps = None
        print(f"Warning: Action {action_name} missing 'original_fps' property. Using current scene fps.")
    
    fps = context.scene.render.fps = int(fps)

    duration = frame_length / fps

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
            logger.log(f"Skipping fcurve {fcurve.data_path}", "info", "INFO")

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

        coords = [[], [], []]

        for fcurve in fcurves:
            axis_index = fcurve.array_index

            assert axis_index < 3, f"Invalid axis {axis_index}"

            # We can have multiple values for X | Y | Z over time
            for kp in fcurve.keyframe_points:
                coords[axis_index].append(kp.co[1])  # X | Y | Z value over time
                if axis_index == 0:
                    assert duration > 0, f"Duration is zero: {action.frame_range[1]} / {fps}"
                    assert fps > 0, "FPS is zero"
                    t = (kp.co[0] / fps) / duration
                    bone_lib[bone_name]["loc_per_time"]["times"].append(t)

        assert (
            len(coords[0]) == len(coords[1]) == len(coords[2])
        ), "Uneven loc keycounts"

        # Generate XYZ pairs
        bone_lib[bone_name]["loc_per_time"]["vec"].extend(zip(*coords))

    # Iterate over all rotation_fcurves and extract the rotation
    for data_path, fcurves in rotation_fcurves.items():
        bone_name = data_path.split('"')[1]
        # We should have the bone in the bone_lib
        assert bone_name in bone_lib, f"Bone {bone_name} not found in the bone_lib"

        coords = [[], [], [], []]

        for fcurve in fcurves:
            axis_index = fcurve.array_index

            assert axis_index < 4, f"Invalid axis {axis_index}"

            for kp in fcurve.keyframe_points:
                coords[axis_index].append(kp.co[1])  # W | X | Y | Z value over time
                if axis_index == 0:
                    t = (kp.co[0] / fps) / duration
                    bone_lib[bone_name]["rot_per_time"]["times"].append(t)

        assert all(
            len(coords[i]) == len(coords[0]) for i in range(4)
        ), "Uneven rot keycounts"

        # Generate WXYZ pairs
        bone_lib[bone_name]["rot_per_time"]["quat"].extend(zip(*coords))

    # Create Header, Time and Keyframes
    headers: list[SKAHeader] = []
    times: list[float] = []
    keyframes: list[SKAKeyframe] = []
    last_tick = 0

    # Build quick lookup of F-curves by bone & axis
    loc_fcc_map: dict[str, dict[int, bpy.types.FCurve]] = {
        dp.split('"')[1]: {fc.array_index: fc for fc in fcs}
        for dp, fcs in location_fcurves.items()
    }

    rot_fcc_map: dict[str, dict[int, bpy.types.FCurve]] = {
        dp.split('"')[1]: {fc.array_index: fc for fc in fcs}
        for dp, fcs in rotation_fcurves.items()
    }

    total_frames = duration * fps

    for bone_name, data in bone_lib.items():
        bone_id = bones_list.get(bone_name, generate_bone_id(bone_name))

        # Retrieve the bone from the armature's rest data
        armature_bone: bpy.types.Bone = armature.data.bones[bone_name]
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

        loc_fcs = loc_fcc_map[bone_name]
        for i, loc in enumerate(data["loc_per_time"]["vec"]):
            original_loc = bind_rot @ Vector(loc) + bind_loc
            loc_keyframe = SKAKeyframe()
            loc_keyframe.w = 1.0
            loc_keyframe.x, loc_keyframe.y, loc_keyframe.z = original_loc[:]
            time = data["loc_per_time"]["times"][i]
            # TODO: Maybe also zero values have a smoothing?
            if i == len(data["loc_per_time"]["vec"]) - 1 or time == 0.0:
                loc_keyframe.tan_x = 0.0
                loc_keyframe.tan_y = 0.0
                loc_keyframe.tan_z = 0.0
                loc_keyframe.tan_w = 0.0
            else:
                # invert Bézier→Hermite for each axis
                def M(fc: bpy.types.FCurve) -> float:
                    p = fc.keyframe_points[i]
                    n = fc.keyframe_points[i + 1]
                    df = n.co[0] - p.co[0]
                    return 3.0 * (p.handle_right.y - p.co[1]) * total_frames / df

                M_local = Vector((M(loc_fcs[0]), M(loc_fcs[1]), M(loc_fcs[2])))
                M_file = bind_rot @ M_local
                loc_keyframe.tan_x, loc_keyframe.tan_y, loc_keyframe.tan_z = M_file[:]
            loc_keyframe.tan_w = 0.0  # No tangents for W in location keyframes
            keyframes.append(loc_keyframe)

        rot_header = SKAHeader()
        rot_header.type = 1
        rot_header.tick = last_tick
        rot_header.interval = len(data["rot_per_time"]["quat"])
        rot_header.bone_id = bone_id
        last_tick += rot_header.interval
        times.extend(data["rot_per_time"]["times"])
        headers.append(rot_header)

        rot_fcs = rot_fcc_map[bone_name]
        for i, quat in enumerate(data["rot_per_time"]["quat"]):
            stored_quat = Quaternion(quat)  # Assuming quat is in (w, x, y, z) order
            original_quat = bind_rot @ stored_quat
            rot_keyframe = SKAKeyframe()
            rot_keyframe.w, rot_keyframe.x, rot_keyframe.y, rot_keyframe.z = (
                -original_quat.w,
                original_quat.x,
                original_quat.y,
                original_quat.z,
            )

            time = data["rot_per_time"]["times"][i]
            if i == len(data["rot_per_time"]["quat"]) - 1 or time == 0.0:
                # TODO: Maybe also zero values have a smoothing?
                rot_keyframe.tan_x = 0.0
                rot_keyframe.tan_y = 0.0
                rot_keyframe.tan_z = 0.0
                rot_keyframe.tan_w = 0.0
            else:
                # invert Bézier→Hermite for each axis
                def Mq(fc: bpy.types.FCurve) -> float:
                    p = fc.keyframe_points[i]
                    n = fc.keyframe_points[i + 1]
                    df = n.co[0] - p.co[0]
                    return 3.0 * (p.handle_right.y - p.co[1]) * total_frames / df

                local_q = Quaternion(
                    (Mq(rot_fcs[0]), Mq(rot_fcs[1]), Mq(rot_fcs[2]), Mq(rot_fcs[3]))
                )
                file_q = bind_rot @ local_q
                rot_keyframe.tan_w = -file_q.w
                rot_keyframe.tan_x, rot_keyframe.tan_y, rot_keyframe.tan_z = (
                    file_q.x,
                    file_q.y,
                    file_q.z,
                )
            keyframes.append(rot_keyframe)

    # Create a new SKA file and write the action data to it
    ska_file = SKA()
    # We will use type 6 for now
    ska_file.type = 6
    ska_file.duration = duration
    ska_file.repeat = action["repeat"] if "repeat" in action else 0
    ska_file.stutter_mode = 2  # smooth animation
    ska_file.zeroes = [0, 0, 0]
    ska_file.header_count = len(headers)
    ska_file.headers = headers
    ska_file.time_count = len(times)
    ska_file.times = times
    ska_file.keyframes = keyframes
    ska_file.frame_length = frame_length
    # Write the SKA file to disk
    # Assure filepath has the .ska extension
    if not filepath.endswith(".ska"):
        filepath += ".ska"
    ska_file.write(filepath)
    logger.log(f"Exported SKA file to {filepath} with {fps} FPS", "info", "INFO")
    logger.display()
