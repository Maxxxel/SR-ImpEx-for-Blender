import json
from os.path import dirname, realpath
from typing import List, Union
from collections import defaultdict
from mathutils import Vector, Quaternion
import bpy

from sr_impex.definitions.ska_definitions import SKA, SKAHeader, SKAKeyframe
from sr_impex.core.message_logger import MessageLogger

# Resources are in sr_impex/resources, need to go up one level from utilities/
resource_dir = dirname(dirname(realpath(__file__))) + "/resources"
logger = MessageLogger()

with open(resource_dir + "/bone_versions.json", "r", encoding="utf-8") as f:
    bones_list = json.load(f)


def get_current_collection() -> bpy.types.Collection:
    """Returns the active collection or none."""
    return bpy.context.view_layer.active_layer_collection.collection


def get_current_armature() -> Union[bpy.types.Object, None]:
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
    sorted_actions = sorted(relevant_actions)

    # Stelle sicher, dass alle relevanten Actions die DRS-Name-Properties haben
    for act_name in sorted_actions:
        act = bpy.data.actions.get(act_name)
        if not act:
            continue

        try:
            raw = act.get("raw_name", None)
        except Exception:
            raw = None
        if not raw:
            raw = act.name or ""
            try:
                act["raw_name"] = raw
            except Exception:
                pass

        try:
            ui = act.get("ui_name", None)
        except Exception:
            ui = None
        if not ui:
            base = raw
            if base.lower().endswith(".ska"):
                base = base[:-4]
            short = base
            if "-" in short:
                short = short.rsplit("-", 1)[-1]
            if "_" in short:
                short = short.rsplit("_", 1)[-1]
            short = short or base or raw
            try:
                act["ui_name"] = short
            except Exception:
                pass

    return sorted_actions


def generate_bone_id(bone_name: str) -> int:
    """Generate a unique bone ID based on the bone name."""
    # Generate a unique ID for the bone based on its name
    # This is a simple hash function, you can replace it with a more complex one if needed
    bone_id = sum(ord(char) for char in bone_name) % (2**32 - 1)
    return bone_id


# invert Bézier→Hermite for each axis
def invert_bezier_hermite_for_axis(fc: bpy.types.FCurve, i: int, total_frames: float) -> float:
    """Convert Blender Bezier handle slope to a Hermite tangent.

    Note: This requires a *keyframe index*. When we resample curves on a union
    of frame-times, the sample index may exceed the number of keyframes on a
    specific axis. In that case we return 0.0 (no tangent) instead of crashing.
    """
    try:
        kps = fc.keyframe_points
        if i < 0 or (i + 1) >= len(kps):
            return 0.0
        p = kps[i]
        n = kps[i + 1]
        df = n.co[0] - p.co[0]
        if df == 0.0:
            return 0.0
        return 3.0 * (p.handle_right.y - p.co[1]) * total_frames / df
    except Exception:
        return 0.0


def invert_bezier_hermite_for_axis_any(fc: bpy.types.FCurve, i: int, total_frames: float) -> float:
    """
    Return Hermite tangent at key i:
    - for i < last: from handle_right vs next key
    - for i == last: from handle_left vs previous key
    """
    kps = fc.keyframe_points
    if not kps:
        return 0.0

    # last key: derive from incoming (handle_left, previous key)
    if i >= len(kps) - 1:
        if len(kps) < 2:
            return 0.0
        p = kps[-2]
        n = kps[-1]
        df = n.co.x - p.co.x
        if df == 0.0:
            return 0.0
        # handle_left.y = P - (M * dt_n)/3  =>  M = 3*(P - handle_left.y)/dt_n
        return 3.0 * (n.co.y - n.handle_left.y) * total_frames / df

    # normal case: outgoing (handle_right, next key)
    return invert_bezier_hermite_for_axis(fc, i, total_frames)


def export_ska(context: bpy.types.Context, filepath: str, action_name: str, export_tangents: bool = False) -> None:
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

    # Bones Lib, with loc and rot attributes.
    # IMPORTANT: The game format expects *two headers per bone* (loc + rot).
    # Therefore we must include every armature bone, not only bones that appear
    # in the action's FCurves.
    bone_lib: dict[str, dict] = {}
    for b in armature.data.bones:
        bone_lib[b.name] = {
            "loc_per_time": {"vec": [], "times": []},
            "rot_per_time": {"quat": [], "times": []},
        }

    # Iterate over all location_fcurves and extract the location
    try:
        for data_path, fcurves in location_fcurves.items():
            # Get the bone name from the data path
            bone_name = data_path.split('"')[1]
            if bone_name not in bone_lib:
                bone_lib[bone_name] = {
                    "loc_per_time": {"vec": [], "times": []},
                    "rot_per_time": {"quat": [], "times": []},
                }

            # Collect all unique frame times from all axes
            all_frames = set()
            fcurves_by_axis = {}
            for fcurve in fcurves:
                axis_index = fcurve.array_index
                assert axis_index < 3, f"Invalid axis {axis_index}"
                fcurves_by_axis[axis_index] = fcurve
                for kp in fcurve.keyframe_points:
                    all_frames.add(kp.co[0])

            # Sort frames to maintain consistent ordering
            sorted_frames = sorted(all_frames)

            # Evaluate each axis at all frame times
            coords = [[], [], []]
            for frame in sorted_frames:
                assert duration > 0, f"Duration is zero: {action.frame_range[1]} / {fps}"
                assert fps > 0, "FPS is zero"
                t = (frame / fps) / duration
                bone_lib[bone_name]["loc_per_time"]["times"].append(t)

                for axis_index in range(3):
                    if axis_index in fcurves_by_axis:
                        # Evaluate the fcurve at this frame
                        value = fcurves_by_axis[axis_index].evaluate(frame)
                        coords[axis_index].append(value)
                    else:
                        # If this axis doesn't have an fcurve, use 0.0
                        coords[axis_index].append(0.0)

            # Generate XYZ pairs
            bone_lib[bone_name]["loc_per_time"]["vec"].extend(zip(*coords))
    except Exception as e:
        raise RuntimeError(f"Error processing location F-curves: {e}") from e

    # Iterate over all rotation_fcurves and extract the rotation
    try:
        for data_path, fcurves in rotation_fcurves.items():
            bone_name = data_path.split('"')[1]
            # Create bone entry if it doesn't exist (in case there are only rotation keyframes)
            if bone_name not in bone_lib:
                bone_lib[bone_name] = {
                    "loc_per_time": {"vec": [], "times": []},
                    "rot_per_time": {"quat": [], "times": []},
                }

            # Collect all unique frame times from all axes
            all_frames = set()
            fcurves_by_axis = {}
            for fcurve in fcurves:
                axis_index = fcurve.array_index
                assert axis_index < 4, f"Invalid axis {axis_index}"
                fcurves_by_axis[axis_index] = fcurve
                for kp in fcurve.keyframe_points:
                    all_frames.add(kp.co[0])

            # Sort frames to maintain consistent ordering
            sorted_frames = sorted(all_frames)

            # Evaluate each axis at all frame times
            coords = [[], [], [], []]
            for frame in sorted_frames:
                t = (frame / fps) / duration
                bone_lib[bone_name]["rot_per_time"]["times"].append(t)

                for axis_index in range(4):
                    if axis_index in fcurves_by_axis:
                        # Evaluate the fcurve at this frame
                        value = fcurves_by_axis[axis_index].evaluate(frame)
                        coords[axis_index].append(value)
                    else:
                        # If this axis doesn't have an fcurve, use default quaternion component
                        # w=1, x=0, y=0, z=0 for identity quaternion
                        coords[axis_index].append(1.0 if axis_index == 0 else 0.0)

            # Generate WXYZ pairs
            bone_lib[bone_name]["rot_per_time"]["quat"].extend(zip(*coords))
    except Exception as e:
        raise RuntimeError(f"Error processing rotation F-curves: {e}") from e

    # Ensure every bone has both location and rotation data (game format requirement).
    # Bones must have at least one keyframe for both location and rotation.
    for bone_name in list(bone_lib.keys()):
        data = bone_lib[bone_name]

        # If location is missing, add a single keyframe at t=0 with zero location
        if len(data["loc_per_time"]["vec"]) == 0:
            data["loc_per_time"]["times"].append(0.0)
            data["loc_per_time"]["vec"].append((0.0, 0.0, 0.0))

        # If rotation is missing, add a single keyframe at t=0 with identity quaternion
        if len(data["rot_per_time"]["quat"]) == 0:
            data["rot_per_time"]["times"].append(0.0)
            data["rot_per_time"]["quat"].append((1.0, 0.0, 0.0, 0.0))

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

    try:
        for bone_name, data in bone_lib.items():
            bone_id = bones_list.get(bone_name, generate_bone_id(bone_name))

            # Retrieve the bone from the armature's rest data
            try:
                armature_bone: bpy.types.Bone = armature.data.bones[bone_name]
                if armature_bone.parent:
                    bind_matrix = (
                        armature_bone.parent.matrix_local.inverted_safe()
                        @ armature_bone.matrix_local
                    )
                else:
                    bind_matrix = armature_bone.matrix_local
            except KeyError as e:
                # We maybe deleted a bone in edit we dont use anymore in the original animation, skip it.
                logger.log(
                    f"Bone '{bone_name}' not found in armature '{armature.name}'. Skipping.",
                    "warning",
                    "WARNING",
                )
                continue

            bind_loc = bind_matrix.to_translation()
            bind_rot = bind_matrix.to_quaternion()

            # Game engine requires both location and rotation headers for every bone
            # Create location header (always, even if empty)
            loc_header = SKAHeader()
            loc_header.type = 0
            loc_header.tick = last_tick
            loc_header.interval = len(data["loc_per_time"]["vec"])
            loc_header.bone_id = bone_id
            last_tick += loc_header.interval
            times.extend(data["loc_per_time"]["times"])
            headers.append(loc_header)

            try:
                loc_fcs = loc_fcc_map.get(bone_name, {})
                for i, loc in enumerate(data["loc_per_time"]["vec"]):
                    original_loc = bind_rot @ Vector(loc) + bind_loc
                    loc_keyframe = SKAKeyframe()
                    loc_keyframe.w = 1.0
                    loc_keyframe.x, loc_keyframe.y, loc_keyframe.z = original_loc[:]
                    # Note: zero-valued keys may also require smoothing.
                    # Check if we can compute tangents (need all axes and not the last keyframe)
                    can_compute_tangents = (
                        len(data["loc_per_time"]["vec"]) >= 2
                        and all(axis in loc_fcs for axis in range(3))
                    )

                    if export_tangents and can_compute_tangents:
                        m_local = Vector((
                            invert_bezier_hermite_for_axis_any(loc_fcs[0], i, total_frames),
                            invert_bezier_hermite_for_axis_any(loc_fcs[1], i, total_frames),
                            invert_bezier_hermite_for_axis_any(loc_fcs[2], i, total_frames)
                        ))
                        m_file = bind_rot @ m_local
                        loc_keyframe.tan_x, loc_keyframe.tan_y, loc_keyframe.tan_z = m_file[:]
                    else:
                        loc_keyframe.tan_x = 0.0
                        loc_keyframe.tan_y = 0.0
                        loc_keyframe.tan_z = 0.0
                    loc_keyframe.tan_w = 0.0  # No tangents for W in location keyframes
                    keyframes.append(loc_keyframe)
            except Exception as e:
                raise RuntimeError(f"Error generating location keyframes for bone '{bone_name}': {e}") from e

            # Create rotation header (always, even if empty)
            rot_header = SKAHeader()
            rot_header.type = 1
            rot_header.tick = last_tick
            rot_header.interval = len(data["rot_per_time"]["quat"])
            rot_header.bone_id = bone_id
            last_tick += rot_header.interval
            times.extend(data["rot_per_time"]["times"])
            headers.append(rot_header)

            try:
                rot_fcs = rot_fcc_map.get(bone_name, {})
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

                    # Check if we can compute tangents (need all axes and not the last keyframe)
                    can_compute_tangents = (
                        len(data["rot_per_time"]["quat"]) >= 2
                        and all(axis in rot_fcs for axis in range(4))
                    )

                    if export_tangents and can_compute_tangents:
                        local_q = Quaternion((
                            invert_bezier_hermite_for_axis_any(rot_fcs[0], i, total_frames),
                            invert_bezier_hermite_for_axis_any(rot_fcs[1], i, total_frames),
                            invert_bezier_hermite_for_axis_any(rot_fcs[2], i, total_frames),
                            invert_bezier_hermite_for_axis_any(rot_fcs[3], i, total_frames),
                        ))
                        file_q = bind_rot @ local_q
                        rot_keyframe.tan_w = -file_q.w
                        rot_keyframe.tan_x, rot_keyframe.tan_y, rot_keyframe.tan_z = (
                            file_q.x,
                            file_q.y,
                            file_q.z,
                        )
                    else:
                        # Note: zero-valued keys may also require smoothing.
                        rot_keyframe.tan_x = 0.0
                        rot_keyframe.tan_y = 0.0
                        rot_keyframe.tan_z = 0.0
                        rot_keyframe.tan_w = 0.0
                    keyframes.append(rot_keyframe)
            except Exception as e:
                raise RuntimeError(f"Error generating rotation keyframes for bone '{bone_name}': {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error generating SKA headers and keyframes: {e}") from e

    # Create a new SKA file and write the action data to it
    ska_file = SKA()
    ska_file.type = 7
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
    logger.display()
