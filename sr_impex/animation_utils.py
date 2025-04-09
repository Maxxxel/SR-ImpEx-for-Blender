# animation_utils.py
import math
from typing import List
import bpy
from mathutils import Quaternion, Vector

from .ska_definitions import SKAKeyframe, SKA
from .drs_definitions import DRSBone


def quat_log(q: Quaternion) -> Quaternion:
    """
    Compute the logarithm of a unit quaternion.
    Returns a pure quaternion (with zero real part).
    """
    # Clamp w to [-1, 1] to avoid numerical issues.
    w = max(min(q.w, 1.0), -1.0)
    theta = math.acos(w)
    sin_theta = math.sin(theta)
    if abs(sin_theta) < 1e-6:
        return Quaternion((0.0, 0.0, 0.0, 0.0))
    factor = theta / sin_theta
    return Quaternion((0.0, q.x * factor, q.y * factor, q.z * factor))


def quat_exp(q: Quaternion) -> Quaternion:
    """
    Compute the exponential of a pure quaternion (with zero real part).
    """
    # q is assumed to have q.w == 0
    v_len = math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z)
    w = math.cos(v_len)
    if v_len > 1e-6:
        sin_v = math.sin(v_len)
        factor = sin_v / v_len
        return Quaternion((w, q.x * factor, q.y * factor, q.z * factor))
    else:
        return Quaternion((w, 0.0, 0.0, 0.0))


def scale_quaternion(q: Quaternion, scale: float) -> Quaternion:
    """
    Scale the vector part of the quaternion by 'scale'.
    Assumes the quaternion is used as a tangent (so its real part is not used).
    """
    return Quaternion((q.w * scale, q.x * scale, q.y * scale, q.z * scale))


def squad(
    q0: Quaternion, s0: Quaternion, s1: Quaternion, q1: Quaternion, t: float
) -> Quaternion:
    """
    Compute squad interpolation.
    """
    # First, perform slerp between q0 and q1
    q0_q1 = q0.slerp(q1, t)
    # Then, slerp between s0 and s1
    s0_s1 = s0.slerp(s1, t)
    # Finally, slerp between the above two with factor 2t(1-t)
    return q0_q1.slerp(s0_s1, 2 * t * (1 - t))


def create_action(
    armature_object: bpy.types.Object, animation_name: str, repeat: bool = False
) -> bpy.types.Action:
    """
    Create a new action for the given armature object.
    """
    action = bpy.data.actions.new(name=animation_name)
    action.use_cyclic = repeat
    armature_object.animation_data.action = action
    return action


def get_bone_fcurves(
    action: bpy.types.Action, pose_bone: bpy.types.PoseBone
) -> dict[str, bpy.types.FCurve]:
    """
    Create and return F-Curves for the location and rotation of the given pose bone.
    """
    fcurves = {}
    data_path_prefix = f'pose.bones["{pose_bone.name}"].'
    # Create location fcurves for x, y, z
    for i, axis in enumerate("xyz"):
        fcurve = action.fcurves.new(data_path=data_path_prefix + "location", index=i)
        fcurves[f"location_{axis}"] = fcurve
    # Create rotation fcurves for quaternion (w, x, y, z)
    for i, axis in enumerate("wxyz"):
        fcurve = action.fcurves.new(
            data_path=data_path_prefix + "rotation_quaternion", index=i
        )
        fcurves[f"rotation_{axis}"] = fcurve
    return fcurves


def insert_keyframes(
    fcurves: dict[str, bpy.types.FCurve],
    frame_data: SKAKeyframe,
    frame: float,
    animation_type: int,
    bind_rot: Quaternion,
    bind_loc: Vector,
    animation_smoothing: bool,
    tangent_store: dict[str, float] = None,
    rot_tangent_store: dict[float, Quaternion] = None,
) -> None:
    """
    Insert keyframes into the provided F-Curves.
    Animation_type 0: Location, 1: Rotation.
    """
    if animation_type == 0:
        # Compute translation relative to binding data
        translation = bind_rot.conjugated() @ (
            Vector((frame_data.x, frame_data.y, frame_data.z)) - bind_loc
        )
        keypoints: List[bpy.types.Keyframe] = []
        for axis, value in zip("xyz", translation):
            kp = fcurves[f"location_{axis}"].keyframe_points.insert(frame, value)
            kp.interpolation = "BEZIER"
            keypoints.append(kp)
            if animation_smoothing and tangent_store:
                tangent_store[f"location_{axis}"][round(frame, 3)] = getattr(
                    frame_data, f"tan_{axis}"
                )
    elif animation_type == 1:
        # Compute rotation. Note the negative sign before frame_data.w may be required,
        # depending on the source file’s convention.
        rotation_quat = bind_rot.conjugated() @ Quaternion(
            (-frame_data.w, frame_data.x, frame_data.y, frame_data.z)
        )
        keypoints: List[bpy.types.Keyframe] = []
        for axis, value in zip("wxyz", rotation_quat):
            kp = fcurves[f"rotation_{axis}"].keyframe_points.insert(frame, value)
            kp.interpolation = "BEZIER"
            keypoints.append(kp)
        if animation_smoothing and rot_tangent_store:
            tquat = Quaternion(
                (frame_data.tan_w, frame_data.tan_x, frame_data.tan_y, frame_data.tan_z)
            )
            rot_tangent_store[round(frame, 3)] = tquat


def add_animation_to_nla_track(
    armature_object: bpy.types.Object, action: bpy.types.Action
) -> None:
    """
    Add the given action to an NLA track on the armature object.
    """
    track = armature_object.animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, 0, action)
    strip.name = action.name
    strip.repeat = True
    track.lock = False
    track.mute = False


def apply_translation_smoothing(
    fcurve: bpy.types.FCurve, tangent_dict: dict[float, float], fps: int
) -> None:
    """
    For a given translation F-Curve and its stored tangent values (mapping from keyframe frame to tangent),
    adjust the Bézier handles of consecutive keyframes based on Hermite-to-Bézier conversion.

    The conversion is:
        handle_offset = dt/3
    where dt is the difference in time between the two keys.
    """
    # Sort keyframe points by the frame (x coordinate)
    kfs = sorted(fcurve.keyframe_points, key=lambda kp: kp.co.x)
    for i in range(len(kfs) - 1):
        current = kfs[i]
        nxt = kfs[i + 1]
        dt_frames = nxt.co.x - current.co.x
        dt_seconds = dt_frames / fps
        factor_frame = dt_frames / 3.0
        factor_value = dt_seconds / 3.0
        # Retrieve stored tangent values based on the keyframe frame (rounded to match storage)
        current_frame_key = round(current.co.x, 3)
        nxt_frame_key = round(nxt.co.x, 3)
        tan_current = tangent_dict.get(current_frame_key, 0.0)
        tan_next = tangent_dict.get(nxt_frame_key, 0.0)

        # Set handles to 'FREE' so they can be manually overridden.
        current.handle_right_type = "FREE"
        nxt.handle_left_type = "FREE"

        # Adjust horizontal (frame) positions for handles.
        current.handle_right.x = current.co.x + factor_frame
        nxt.handle_left.x = nxt.co.x - factor_frame

        # Adjust vertical values using tangent * (dt_seconds/3)
        current.handle_right.y = current.co.y + tan_current * factor_value
        nxt.handle_left.y = nxt.co.y - tan_next * factor_value


def apply_rotation_smoothing(
    fcurves: dict[str, bpy.types.FCurve],
    rot_tangent_dict: dict[float, Quaternion],
    fps: int,
    num_samples: int = 3,
) -> None:
    """
    For each segment between consecutive rotation keyframes, compute control quaternions
    using the stored tangent values and insert extra keyframes via squad interpolation.
    """
    # Gather keyframe frames from one channel (say, rotation_w)
    fcurve = fcurves["rotation_w"]
    key_frames = sorted([round(kp.co.x, 3) for kp in fcurve.keyframe_points])
    # Build a dictionary mapping frame -> quaternion from all rotation channels.
    q_dict = {}
    for frame in key_frames:
        # Get the value at that frame from each channel.
        vals = []
        for ch in ["rotation_w", "rotation_x", "rotation_y", "rotation_z"]:
            val = next(
                (
                    kp.co.y
                    for kp in fcurves[ch].keyframe_points
                    if round(kp.co.x, 3) == frame
                ),
                None,
            )
            if val is None:
                break
            vals.append(val)
        if len(vals) == 4:
            q = Quaternion(tuple(vals))
            q.normalize()
            q_dict[frame] = q

    # Process each segment between consecutive keyframes.
    for i in range(len(key_frames) - 1):
        f0 = key_frames[i]
        f1 = key_frames[i + 1]
        dt_frames = f1 - f0
        dt = dt_frames / fps  # time difference in seconds
        q0 = q_dict[f0]
        q1 = q_dict[f1]
        # Retrieve stored tangent quaternions (default to zero tangent if not stored)
        T0 = rot_tangent_dict.get(f0, Quaternion((0.0, 0.0, 0.0, 0.0)))
        T1 = rot_tangent_dict.get(f1, Quaternion((0.0, 0.0, 0.0, 0.0)))
        # Compute control quaternions for the squad interpolation.
        # The control quaternion is computed as: S = Q * exp((dt/3)*T)
        S0 = q0 @ quat_exp(scale_quaternion(T0, dt / 3.0))
        S1 = q1 @ quat_exp(scale_quaternion(T1, -dt / 3.0))

        # Insert additional keyframes between f0 and f1.
        for j in range(1, num_samples):
            t = j / num_samples
            q_sample = squad(q0, S0, S1, q1, t)
            f_sample = f0 + t * dt_frames
            # Insert the sample into each rotation fcurve.
            for axis, ch in zip(
                ("w", "x", "y", "z"),
                ["rotation_w", "rotation_x", "rotation_y", "rotation_z"],
            ):
                fc = fcurves[ch]
                kp = fc.keyframe_points.insert(
                    f_sample, q_sample[("w", "x", "y", "z").index(axis)]
                )
                kp.interpolation = "LINEAR"


def create_animation(
    ska_file: SKA,
    armature_object: bpy.types.Object,
    bone_list: List["DRSBone"],
    animation_name: str,
    import_animation_type: str,
    fps: int,
    animation_smoothing: bool,
) -> None:
    """
    High-level routine to create an animation on the armature from a SKA file.
    Prepares F-Curves for each bone and inserts keyframes based on the SKA keyframes.
    """
    armature_object.animation_data_create()
    action = create_action(armature_object, animation_name, repeat=ska_file.repeat)
    action["original_duration"] = ska_file.duration

    # Map bones to their fcurves using bone identifiers.
    bone_fcurve_map = {}
    # We'll also use this to store tangent values.
    tangent_storage_all: dict[int, dict[str, dict[float, float]]] = {}
    rot_tangent_storage_all: dict[int, dict[float, Quaternion]] = {}

    for bone in bone_list:
        pose_bone = armature_object.pose.bones.get(bone.name)
        fcurves = get_bone_fcurves(action, pose_bone)
        bone_fcurve_map[bone.ska_identifier] = fcurves
        # Initialize the tangent storage for this bone's channels.
        tangent_storage_all[bone.ska_identifier] = {
            "location_x": {},
            "location_y": {},
            "location_z": {},
        }
        rot_tangent_storage_all[bone.ska_identifier] = {}

    # Insert keyframes for each bone based on the SKA data.
    for header in ska_file.headers:
        fcurves = bone_fcurve_map.get(header.bone_id)
        bone = next((b for b in bone_list if b.ska_identifier == header.bone_id), None)
        if not fcurves or not bone:
            continue
        for idx in range(header.tick, header.tick + header.interval):
            frame_data = ska_file.keyframes[idx]
            if import_animation_type == "FRAMES":
                frame = round(ska_file.times[idx] * ska_file.duration * fps)
            elif import_animation_type == "SECONDS":
                frame = ska_file.times[idx] * ska_file.duration * fps

            if frame is None:
                raise ValueError(f"Invalid frame value for keyframe {idx}: {frame}")

            if header.type == 0:
                insert_keyframes(
                    fcurves,
                    frame_data,
                    frame,
                    header.type,
                    bone.bind_rot,
                    bone.bind_loc,
                    animation_smoothing,
                    tangent_store=tangent_storage_all[bone.ska_identifier],
                )
            else:
                insert_keyframes(
                    fcurves,
                    frame_data,
                    frame,
                    header.type,
                    bone.bind_rot,
                    bone.bind_loc,
                    animation_smoothing,
                    rot_tangent_store=rot_tangent_storage_all[bone.ska_identifier],
                )

    # Post-process: apply smoothing to translation F-Curves using stored tangent values.
    if animation_smoothing:
        for bone_id, fcurves in bone_fcurve_map.items():
            tangents = tangent_storage_all.get(bone_id, {})
            for axis in "xyz":
                key = f"location_{axis}"
                if key in fcurves:
                    apply_translation_smoothing(fcurves[key], tangents[key], fps)
        # For rotation, process the rotation channels.
        for bone_id, fcurves in bone_fcurve_map.items():
            rot_tans = rot_tangent_storage_all.get(bone_id, {})
            apply_rotation_smoothing(fcurves, rot_tans, fps, num_samples=3)

    add_animation_to_nla_track(armature_object, action)
