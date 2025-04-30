# animation_utils.py
from typing import List, Dict, Tuple
import bpy
from mathutils import Quaternion, Vector
from .ska_definitions import SKA, SKAKeyframe
from .drs_definitions import DRSBone


def create_action(
    arm_obj: bpy.types.Object, name: str, cyclic: bool = False
) -> bpy.types.Action:
    """
    Create and assign a new Action to the armature.
    """
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    action = bpy.data.actions.new(name=name)
    action.use_cyclic = cyclic
    arm_obj.animation_data.action = action
    return action


def get_bone_fcurves(
    action: bpy.types.Action, bone_name: str
) -> Dict[str, bpy.types.FCurve]:
    """
    Create FCurves for location (x,y,z) and rotation_quaternion (w,x,y,z).
    """
    fcurves: Dict[str, bpy.types.FCurve] = {}
    path = f'pose.bones["{bone_name}"].'
    for idx, ax in enumerate(("x", "y", "z")):
        fcurves[f"location_{ax}"] = action.fcurves.new(path + "location", index=idx)
    for idx, ax in enumerate(("w", "x", "y", "z")):
        fcurves[f"rotation_{ax}"] = action.fcurves.new(
            path + "rotation_quaternion", index=idx
        )
    return fcurves


def insert_hermite_bezier_curve(
    fcurve: bpy.types.FCurve,
    frames: List[float],
    values: List[float],
    tangents: List[float],
    duration: float,
    fps: int,
) -> None:
    """
    Insert a single-component curve as Bézier whose handles reproduce the exact Hermite spline.
    """
    n = len(frames)
    if n == 0:
        return
    # Insert keyframes
    for f, v in zip(frames, values):
        kp = fcurve.keyframe_points.insert(f, v, options={"REPLACE"})
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "FREE"
    # Compute and set handles
    for i in range(n - 1):
        f0, f1 = frames[i], frames[i + 1]
        P0, P1 = values[i], values[i + 1]
        M0, M1 = tangents[i], tangents[i + 1]
        dt_n = (f1 - f0) / (duration * fps)
        off_f = (f1 - f0) / 3.0
        off_v0 = (M0 * dt_n) / 3.0
        off_v1 = (M1 * dt_n) / 3.0
        kp0 = fcurve.keyframe_points[i]
        kp1 = fcurve.keyframe_points[i + 1]
        kp0.handle_right.x = f0 + off_f
        kp0.handle_right.y = P0 + off_v0
        kp1.handle_left.x = f1 - off_f
        kp1.handle_left.y = P1 - off_v1


def import_ska_animation(
    ska_file: SKA,
    arm_obj: bpy.types.Object,
    bone_list: List[DRSBone],
    name: str,
    fps: int,
    use_bezier: bool = True,
    import_type: str = "SECONDS",
) -> None:
    """
    Import SKA into Blender by inserting Hermite-interpolated Bézier keyframes.
    """
    action = create_action(arm_obj, name=name, cyclic=(ska_file.repeat > 1))
    duration = ska_file.duration
    # Prepare bones and curves
    bone_map = {b.ska_identifier: b for b in bone_list}
    curves_map: Dict[int, Dict[str, bpy.types.FCurve]] = {}
    for b in bone_list:
        curves_map[b.ska_identifier] = get_bone_fcurves(action, b.name)
        arm_obj.pose.bones[b.name].rotation_mode = "QUATERNION"

    # Helper functions for extraction and tangents
    def extract_loc(b: DRSBone, kf: SKAKeyframe) -> Vector:
        return b.bind_rot.conjugated() @ (Vector((kf.x, kf.y, kf.z)) - b.bind_loc)

    def tangent_loc(b: DRSBone, kf: SKAKeyframe) -> Vector:
        return b.bind_rot.conjugated() @ (Vector((kf.tan_x, kf.tan_y, kf.tan_z)))

    def extract_rot(b: DRSBone, kf: SKAKeyframe) -> Tuple[float, float, float, float]:
        q = Quaternion((-kf.w, kf.x, kf.y, kf.z))
        r = b.bind_rot.conjugated() @ q
        # r.normalize()
        return (r.w, r.x, r.y, r.z)

    def tangent_rot(b: DRSBone, kf: SKAKeyframe) -> Tuple[float, float, float, float]:
        tq = Quaternion((-kf.tan_w, kf.tan_x, kf.tan_y, kf.tan_z))
        tr = b.bind_rot.conjugated() @ tq
        # tr.normalize()
        return (tr.w, tr.x, tr.y, tr.z)

    # Process each channel header
    for hdr in ska_file.headers:
        bone = bone_map.get(hdr.bone_id)
        fcs = curves_map.get(hdr.bone_id)
        if bone is None or fcs is None:
            continue
        # Choose extraction
        if hdr.type == 0:
            extract_fn = extract_loc
            tangent_fn = tangent_loc
            axes = ("x", "y", "z")
            prefix = "location"
        else:
            extract_fn = extract_rot
            tangent_fn = tangent_rot
            axes = ("w", "x", "y", "z")
            prefix = "rotation"

        # Collect samples
        seq = [
            (ska_file.times[i], ska_file.keyframes[i])
            for i in range(hdr.tick, hdr.tick + hdr.interval)
        ]
        seq.sort(key=lambda tk: tk[0])
        times_norm = [t for t, _ in seq]
        frames = [
            (
                round(t * duration * fps)
                if import_type == "FRAMES"
                else t * duration * fps
            )
            for t in times_norm
        ]
        # For each component axis
        for idx, ax in enumerate(axes):
            # Values and tangents
            vals = [extract_fn(bone, kf)[idx] for _, kf in seq]
            tans = [tangent_fn(bone, kf)[idx] for _, kf in seq]
            fcurve = fcs[f"{prefix}_{ax}"]
            if not vals:
                continue
            if use_bezier:
                insert_hermite_bezier_curve(fcurve, frames, vals, tans, duration, fps)
            else:
                for fr, v in zip(frames, vals):
                    kp = fcurve.keyframe_points.insert(fr, v, options={"REPLACE"})
                    kp.interpolation = "LINEAR"
    # Add NLA track strip
    track = arm_obj.animation_data.nla_tracks.new()
    strip = track.strips.new(action.name, 0, action)
    strip.repeat = ska_file.repeat
    track.name = action.name
