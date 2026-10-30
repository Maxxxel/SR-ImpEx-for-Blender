import json
from os.path import dirname, realpath
from typing import List, Union
from collections import defaultdict
from mathutils import Vector, Quaternion
import bpy

from sr_impex.definitions.ska_definitions import SKA, SKAHeader, SKAKeyframe
from sr_impex.core.message_logger import MessageLogger
from sr_impex.utilities.bone_ids import generate_bone_id, resolve_bone_ids
from sr_impex.utilities.skeleton_metadata import export_bone_identities, super_parent_matrix

# Resources are in sr_impex/resources, need to go up one level from utilities/
resource_dir = dirname(dirname(realpath(__file__))) + "/resources"
logger = MessageLogger()

with open(resource_dir + "/bone_versions.json", "r", encoding="utf-8") as f:
    bones_list = json.load(f)


def _iter_action_fcurves(action: bpy.types.Action):
    """Yield FCurves for both legacy and layered Action APIs (Blender 4.4+/5.x)."""
    # Legacy API path
    if hasattr(action, "fcurves"):
        for fc in action.fcurves:
            yield fc
        return

    # Layered API path
    layers = getattr(action, "layers", None)
    if not layers:
        return

    seen = set()
    for layer in layers:
        strips = getattr(layer, "strips", None)
        if not strips:
            continue

        for strip in strips:
            channelbags = getattr(strip, "channelbags", None)
            if not channelbags:
                continue

            for bag in channelbags:
                fcurves = getattr(bag, "fcurves", None)
                if not fcurves:
                    continue

                for fc in fcurves:
                    key = (getattr(fc, "data_path", ""), int(getattr(fc, "array_index", 0)))
                    if key in seen:
                        continue
                    seen.add(key)
                    yield fc


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

            for fcurve in _iter_action_fcurves(action):
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
            if short.startswith("skel_") and short.count("_") >= 2:
                short = short.split("_", 2)[2]
            short = short or base or raw
            try:
                act["ui_name"] = short
            except Exception:
                pass

    return sorted_actions


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
        df = p.handle_right.x - p.co.x
        if df == 0.0:
            return 0.0
        return (p.handle_right.y - p.co.y) * total_frames / df
    except Exception:
        return 0.0


def invert_bezier_hermite_for_axis_any(fc: bpy.types.FCurve, i: int, total_frames: float, points=None) -> float:
    """
    Return Hermite tangent at key i:
    - for i < last: from handle_right vs next key
    - for i == last: from handle_left vs previous key
    """
    kps = fc.keyframe_points if points is None else points
    if not kps:
        return 0.0

    # last key: derive from incoming (handle_left, previous key)
    if i >= len(kps) - 1:
        if len(kps) < 2:
            point=kps[0];dx=point.handle_right.x-point.co.x
            return (point.handle_right.y-point.co.y)*total_frames/dx if dx else 0.
        n = kps[-1]
        df = n.co.x - n.handle_left.x
        if df == 0.0:
            return 0.0
        return (n.co.y - n.handle_left.y) * total_frames / df

    # normal case: outgoing (handle_right, next key)
    point=kps[i];dx=point.handle_right.x-point.co.x
    return (point.handle_right.y-point.co.y)*total_frames/dx if dx else 0.


def _hermite_tangent_from_sampled_series(
    samples: list[tuple], times: list[float], i: int, component: int
) -> float:
    """Compute Hermite tangent from sampled values in normalized time-space.

    `times` are normalized to [0..1], so this returns dv/dt.
    """
    n = len(samples)
    if n < 2 or i < 0 or i >= n or len(times) != n:
        return 0.0

    def _safe_div(dv: float, dt: float) -> float:
        if abs(dt) < 1e-12:
            return 0.0
        return dv / dt

    if i == 0:
        dv = float(samples[1][component]) - float(samples[0][component])
        dt = float(times[1]) - float(times[0])
        return _safe_div(dv, dt)

    if i == n - 1:
        dv = float(samples[i][component]) - float(samples[i - 1][component])
        dt = float(times[i]) - float(times[i - 1])
        return _safe_div(dv, dt)

    dv = float(samples[i + 1][component]) - float(samples[i - 1][component])
    dt = float(times[i + 1]) - float(times[i - 1])
    return _safe_div(dv, dt)


def _ensure_quaternion_continuity(quats: list[tuple]) -> tuple[list[tuple], list[bool]]:
    """Ensure quaternion sign continuity across a keyframe sequence.

    q and -q represent the same rotation, but Hermite interpolation between
    quaternions of opposite sign takes the "long path" through 4D space,
    producing non-unit-length intermediate values that the game renders as
    scale distortion.  This flips signs so dot(q[i], q[i+1]) >= 0.

    Returns (corrected_quats, flip_mask) where flip_mask[i] is True if
    that keyframe was negated.
    """
    if not quats:
        return quats, []

    result = []
    flipped = []

    # Normalize and keep first quaternion as-is
    q0 = Quaternion(quats[0])
    if q0.magnitude > 1e-8:
        q0.normalize()
    result.append((q0.w, q0.x, q0.y, q0.z))
    flipped.append(False)

    for i in range(1, len(quats)):
        prev = Quaternion(result[i - 1])
        curr = Quaternion(quats[i])
        if curr.magnitude > 1e-8:
            curr.normalize()

        # Dot product in 4D — negative means opposite hemispheres
        dot = prev.w * curr.w + prev.x * curr.x + prev.y * curr.y + prev.z * curr.z
        if dot < 0:
            curr = Quaternion((-curr.w, -curr.x, -curr.y, -curr.z))
            flipped.append(True)
        else:
            flipped.append(False)

        result.append((curr.w, curr.x, curr.y, curr.z))

    return result, flipped


def _hermite_tangent_from_fcurve(
    fcurve: bpy.types.FCurve | None, frame: float, total_frames: float, eps: float = 0.5
) -> float:
    """Compute Hermite tangent of an fcurve at *frame* from actual Bézier handles.

    If *frame* matches a keyframe, the exact handle-based tangent is extracted.
    Otherwise, the numerical derivative of the evaluated curve is used.
    Returns dv/dt in normalized-time space (matching SKA file convention).
    """
    if fcurve is None:
        return 0.0
    from sr_impex.blender.ska_loop import authored_points
    kps = authored_points(fcurve.id_data,fcurve)
    if not kps:
        return 0.0

    # Match the actual key, not a neighboring subframe less than half a frame
    # away. Blender stores these coordinates as single-precision values.
    for idx, kp in enumerate(kps):
        if abs(kp.co.x - frame) < 1e-5:
            return invert_bezier_hermite_for_axis_any(fcurve, idx, total_frames,points=kps)

    # No keyframe match — compute numerical derivative
    nearest=min(abs(kp.co.x-frame) for kp in kps)
    eps=min(eps,nearest*.25)
    if eps<=1e-8:return 0.0
    v_plus = fcurve.evaluate(frame + eps)
    v_minus = fcurve.evaluate(frame - eps)
    return (v_plus - v_minus) * total_frames / (2.0 * eps)


def export_ska(context: bpy.types.Context, filepath: str, action_name: str, export_tangents: bool = False,
               armature: bpy.types.Object = None) -> None:
    """Export the current scene to a .ska file."""
    # Find the Animation Data by the given action name in the current context
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action '{action_name}' not found in the current context.")
    from sr_impex.blender.ska_loop import sync,authored_points
    sync(action)

    try:
        frame_length = action["frame_length"]
    except Exception:
        frame_length = None

    try:
        fps = action["original_fps"]
    except Exception:
        fps = None
        print(f"Warning: Action {action_name} missing 'original_fps' property. Using current scene fps.")

    if fps is None:
        scene_fps = float(context.scene.render.fps or 30.0)
        scene_fps_base = float(context.scene.render.fps_base or 1.0)
        fps = scene_fps / max(1e-8, scene_fps_base)
    else:
        fps = float(fps)

    if fps <= 1e-6:
        fps = 30.0

    # Prefer importer metadata for frame length. If missing, reconstruct from
    # original duration + fps before falling back to current action frame range.
    if frame_length is None:
        try:
            original_duration = action["original_duration"]
            if original_duration is not None:
                frame_length = int(round(float(original_duration) * float(fps)))
        except Exception:
            frame_length = None

    if frame_length is None:
        print(
            f"Warning: Action {action_name} missing 'frame_length' and 'original_duration'. Using frame range instead."
        )
        frame_length = action.frame_range[1] - action.frame_range[0]

    frame_length = int(max(1, round(float(frame_length))))

    duration = frame_length / fps
    start_frame = float(action.get('ska_start_frame',0.0))

    # Get the Bones of the Armature
    armature = armature or get_current_armature()
    if armature is None:
        raise ValueError("No armature selected.")

    bone_ids = {name: record["key"] for name, record in
                export_bone_identities(armature.data.bones, bones_list).items()}

    location_fcurves: dict[str, list[bpy.types.FCurve]] = defaultdict(list)
    rotation_fcurves: dict[str, list[bpy.types.FCurve]] = defaultdict(list)
    # Print Number of Curves
    for fcurve in _iter_action_fcurves(action):
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
            "loc_per_time": {"vec": [], "times": [], "frames": []},
            "rot_per_time": {"quat": [], "times": [], "frames": []},
        }

    # Iterate over all location_fcurves and extract the location
    try:
        for data_path, fcurves in location_fcurves.items():
            # Get the bone name from the data path
            bone_name = data_path.split('"')[1]
            if bone_name not in bone_lib:
                bone_lib[bone_name] = {
                    "loc_per_time": {"vec": [], "times": [], "frames": []},
                    "rot_per_time": {"quat": [], "times": [], "frames": []},
                }

            # Collect all unique frame times from all axes
            all_frames = set()
            fcurves_by_axis = {}
            for fcurve in fcurves:
                axis_index = fcurve.array_index
                assert axis_index < 3, f"Invalid axis {axis_index}"
                fcurves_by_axis[axis_index] = fcurve
                for kp in authored_points(action,fcurve):
                    all_frames.add(kp.co[0])

            # Sort frames to maintain consistent ordering
            sorted_frames = sorted(all_frames)

            # Evaluate each axis at all frame times
            coords = [[], [], []]
            for frame in sorted_frames:
                assert duration > 0, f"Duration is zero: {action.frame_range[1]} / {fps}"
                assert fps > 0, "FPS is zero"
                t = (frame - start_frame) / frame_length
                bone_lib[bone_name]["loc_per_time"]["times"].append(t)
                bone_lib[bone_name]["loc_per_time"]["frames"].append(frame)

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
                    "loc_per_time": {"vec": [], "times": [], "frames": []},
                    "rot_per_time": {"quat": [], "times": [], "frames": []},
                }

            # Collect all unique frame times from all axes
            all_frames = set()
            fcurves_by_axis = {}
            for fcurve in fcurves:
                axis_index = fcurve.array_index
                assert axis_index < 4, f"Invalid axis {axis_index}"
                fcurves_by_axis[axis_index] = fcurve
                for kp in authored_points(action,fcurve):
                    all_frames.add(kp.co[0])

            # Sort frames to maintain consistent ordering
            sorted_frames = sorted(all_frames)

            # Evaluate each axis at all frame times
            coords = [[], [], [], []]
            for frame in sorted_frames:
                t = (frame - start_frame) / frame_length
                bone_lib[bone_name]["rot_per_time"]["times"].append(t)
                bone_lib[bone_name]["rot_per_time"]["frames"].append(frame)

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
            data["loc_per_time"]["frames"].append(0.0)
            data["loc_per_time"]["vec"].append((0.0, 0.0, 0.0))

        # If rotation is missing, add a single keyframe at t=0 with identity quaternion
        if len(data["rot_per_time"]["quat"]) == 0:
            data["rot_per_time"]["times"].append(0.0)
            data["rot_per_time"]["frames"].append(0.0)
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
            bone_id = bone_ids[bone_name]

            # Retrieve the bone from the armature's rest data
            try:
                armature_bone: bpy.types.Bone = armature.data.bones[bone_name]
                if armature_bone.parent:
                    bind_matrix = (
                        armature_bone.parent.matrix_local.inverted_safe()
                        @ armature_bone.matrix_local
                    )
                else:
                    bind_matrix = (super_parent_matrix(armature.data).inverted_safe()
                                   @ armature_bone.matrix_local)
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
                    can_compute_tangents = len(data["loc_per_time"]["vec"]) >= 1

                    if export_tangents and can_compute_tangents:
                        frame = data["loc_per_time"]["frames"][i]
                        m_local = Vector((
                            _hermite_tangent_from_fcurve(loc_fcs.get(0), frame, total_frames),
                            _hermite_tangent_from_fcurve(loc_fcs.get(1), frame, total_frames),
                            _hermite_tangent_from_fcurve(loc_fcs.get(2), frame, total_frames),
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
                # Fix quaternion sign continuity before export.
                # q and -q are the same rotation, but opposite signs cause
                # Hermite interpolation to produce non-unit quaternions
                # which the game renders as scale distortion (squishing).
                quats_fixed, flip_mask = _ensure_quaternion_continuity(
                    data["rot_per_time"]["quat"]
                )
                for i, quat in enumerate(quats_fixed):
                    stored_quat = Quaternion(quat)  # (w, x, y, z) order, sign-fixed
                    original_quat = bind_rot @ stored_quat
                    rot_keyframe = SKAKeyframe()
                    rot_keyframe.w, rot_keyframe.x, rot_keyframe.y, rot_keyframe.z = (
                        -original_quat.w,
                        original_quat.x,
                        original_quat.y,
                        original_quat.z,
                    )

                    can_compute_tangents = len(quats_fixed) >= 1

                    if export_tangents and can_compute_tangents:
                        frame = data["rot_per_time"]["frames"][i]
                        # Extract per-component Hermite tangents from Bézier handles.
                        tan_w = _hermite_tangent_from_fcurve(rot_fcs.get(0), frame, total_frames)
                        tan_x = _hermite_tangent_from_fcurve(rot_fcs.get(1), frame, total_frames)
                        tan_y = _hermite_tangent_from_fcurve(rot_fcs.get(2), frame, total_frames)
                        tan_z = _hermite_tangent_from_fcurve(rot_fcs.get(3), frame, total_frames)

                        # If this keyframe was sign-flipped for continuity,
                        # negate the tangent to match (derivative of -q is -dq/dt).
                        if flip_mask[i]:
                            tan_w, tan_x, tan_y, tan_z = -tan_w, -tan_x, -tan_y, -tan_z

                        local_q = Quaternion((tan_w, tan_x, tan_y, tan_z))
                        file_q = bind_rot @ local_q
                        rot_keyframe.tan_w = -file_q.w
                        rot_keyframe.tan_x, rot_keyframe.tan_y, rot_keyframe.tan_z = (
                            file_q.x,
                            file_q.y,
                            file_q.z,
                        )
                    else:
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
    ska_file.type = int(action.get('ska_version',7))
    if ska_file.type not in (6,7):
        raise ValueError('Only SKA 6 and 7 are supported for artist export')
    ska_file.duration = duration
    ska_file.repeat = action["repeat"] if "repeat" in action else 0
    ska_file.stutter_mode = action.get("stutter_mode", 2)
    ska_file.unused1 = action.get("unused1", 0)
    ska_file.zeroes = [0, 0, 0]
    if "ska_tail_metadata" in action:
        try:
            metadata = json.loads(action["ska_tail_metadata"])
            ska_file.target_ids = [int(value) for value in metadata["target_ids"]]
            ska_file.text_markers = [bytes.fromhex(value) for value in metadata["text_markers_hex"]]
            ska_file.annotation_bytes = bytes.fromhex(metadata["annotation_hex"])
            if any(len(marker) != 8 for marker in ska_file.text_markers):
                raise ValueError("Text markers must contain exactly 8 bytes")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid preserved SKA metadata on action '{action.name}': {exc}") from exc
    ska_file.header_count = len(headers)
    ska_file.headers = headers
    ska_file.time_count = len(times)
    ska_file.times = times
    ska_file.keyframes = keyframes
    ska_file.frame_length = frame_length
    from sr_impex.utilities.ska_artist import ALPHA_ID, ALPHA_PATH, RAW_TRACKS, append_preserved_tracks
    preserved = json.loads(action.get(RAW_TRACKS,'[]'))
    alpha = next((fc for fc in _iter_action_fcurves(action) if fc.data_path==ALPHA_PATH),None)
    represented = {(h.bone_id,h.type) for h in ska_file.headers}
    if not action.get('ska_write_alpha',True):
        preserved=[r for r in preserved if r['bone_id']!=ALPHA_ID]
    if alpha and alpha.keyframe_points and action.get('ska_write_alpha',True):
        original = next((r for r in preserved if r['bone_id']==ALPHA_ID and r['type']==0),None)
        points=authored_points(action,alpha)
        header = SKAHeader(tick=len(ska_file.times), interval=len(points),type=0,bone_id=ALPHA_ID)
        ska_file.headers.append(header)
        for point in points:
            time = (point.co.x-start_frame)/frame_length
            values = [0.0]*8
            if original:
                source = next((i for i,t in enumerate(original['times']) if abs(t-time)<1e-6),None)
                if source is not None: values=list(original['keyframes'][source])
            values[0] = float(point.co.y)
            if export_tangents:values[4] = _hermite_tangent_from_fcurve(alpha,point.co.x,frame_length)
            ska_file.times.append(time);ska_file.keyframes.append(SKAKeyframe(*values))
        represented.add((ALPHA_ID,0))
    append_preserved_tracks(ska_file,preserved,represented)
    from sr_impex.utilities.ska_artist import reorder_tracks
    if 'ska_track_order' in action:
        reorder_tracks(ska_file,json.loads(action['ska_track_order']))
    # Write the SKA file to disk
    # Assure filepath has the .ska extension
    if not filepath.endswith(".ska"):
        filepath += ".ska"
    ska_file.write(filepath)
    logger.display()
