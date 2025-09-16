# animation_utils.py
from typing import List, Dict, Tuple
import os
import json
from mathutils import Quaternion, Vector
import bpy

from .ska_definitions import SKA, SKAKeyframe
from .drs_definitions import DRSBone

IS_44_PLUS = bpy.app.version >= (4, 4, 0)


def assign_action_compat(arm_obj: bpy.types.Object, action: bpy.types.Action) -> None:
    """
    Assign an Action to the armature for playback/authoring.
    On 4.4+ selects an action slot if available; on older versions it's a no-op.
    """
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    anim = arm_obj.animation_data
    anim.action = action

    # Blender 4.4 adds 'slotted' actions; try to pick a suitable slot when available.
    if IS_44_PLUS and hasattr(anim, "action_slot"):
        # Prefer AnimData's suggestion if present
        slots = getattr(anim, "action_suitable_slots", None)
        if slots and len(slots):
            anim.action_slot = slots[0]
        else:
            # Or pick the first slot on the action, if any
            act_slots = getattr(action, "slots", None)
            if act_slots and len(act_slots):
                anim.action_slot = act_slots[0]


def ensure_fcurve_compat(
    action: bpy.types.Action,
    arm_obj: bpy.types.Object,
    data_path: str,
    index: int = 0,
) -> bpy.types.FCurve:
    """
    Create/ensure an FCurve routed correctly.
    - Blender 4.4+: action.fcurve_ensure_for_datablock(...)
    - Older versions: action.fcurves.find/new(...)
    """
    if IS_44_PLUS and hasattr(action, "fcurve_ensure_for_datablock"):
        return action.fcurve_ensure_for_datablock(
            arm_obj, data_path=data_path, index=index
        )

    # Legacy path (<= 4.3)
    fc = action.fcurves.find(data_path=data_path, index=index)
    if fc is None:
        fc = action.fcurves.new(data_path=data_path, index=index)
    return fc


def create_action(
    arm_obj: bpy.types.Object, name: str, cyclic: bool = False
) -> bpy.types.Action:
    """Create a new Action, assign it to the armature, and select a slot on 4.4+."""
    action = bpy.data.actions.new(name=name)
    # keep existing flag if you use it
    if hasattr(action, "use_cyclic"):
        action.use_cyclic = cyclic
    assign_action_compat(arm_obj, action)
    return action


def get_bone_fcurves(
    action: bpy.types.Action, arm_obj: bpy.types.Object, bone_name: str
) -> dict[str, bpy.types.FCurve]:
    fcurves = {}
    base = f'pose.bones["{bone_name}"].'

    for i, ax in enumerate(("x", "y", "z")):
        fcurves[f"location_{ax}"] = ensure_fcurve_compat(
            action, arm_obj, base + "location", i
        )

    for i, ax in enumerate(("w", "x", "y", "z")):
        fcurves[f"rotation_{ax}"] = ensure_fcurve_compat(
            action, arm_obj, base + "rotation_quaternion", i
        )

    return fcurves


def _kf_at_frame(fcurve: bpy.types.FCurve, frame: float, eps: float = 1e-6):
    for k in fcurve.keyframe_points:
        if abs(k.co.x - frame) <= eps:
            return k
    return None


def insert_or_replace_key(
    fcurve: bpy.types.FCurve,
    frame: float,
    value: float,
    interpolation: str = "BEZIER",
    handle_type: str = "FREE",
) -> bpy.types.Keyframe:
    k = _kf_at_frame(fcurve, frame)
    if k is None:
        # insert without REPLACE (avoids the proxy return)
        k = fcurve.keyframe_points.insert(frame, value)
    else:
        k.co.y = value  # replace value in-place

    # now it's the *stored* keyframe; safe to edit
    k.interpolation = interpolation
    k.handle_left_type = handle_type
    k.handle_right_type = handle_type

    # finalize
    fcurve.keyframe_points.update()
    fcurve.update()
    return k


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
        insert_or_replace_key(fcurve, f, v, interpolation="BEZIER", handle_type="FREE")
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
    use_bezier: bool = True,
    unit_name: str = "Name",
    map_collection: bpy.types.Collection | None = None,
) -> None:
    """
    Import SKA into Blender by inserting Hermite-interpolated Bézier keyframes.
    """
    blob_key_original = (name or "").strip()
    # 1. Remove .ska extension if present
    if name.lower().endswith(".ska"):
        name = name[:-4]
    # 2. Remove parent folder if present. E.g. D:\Games\Skylords Reborn\Mods\Unpack\bf1\gfx\units\skel_giant_hammer\unit_dreadnought.drs -> skel_giant_hammer is what we want
    parent_folder = os.path.basename(os.path.dirname(unit_name))
    if name.startswith(parent_folder + "_"):
        name = name[len(parent_folder) + 1 :]
    # 3. Check if still too long
    if len(name) > 63:
        print(f"Warning: Action name '{name}' is too long, truncating to 63 chars.")
        name = name[:63]

    # Check if Action with this name already exists
    existing_action = bpy.data.actions.get(name)
    if existing_action is not None:
        # Just assign it and return
        assign_action_compat(arm_obj, existing_action)
        print(f"Info: Action '{name}' already exists, assigned existing action.")
        return

    action = create_action(arm_obj, name=name, cyclic=(ska_file.repeat > 1))
    duration = ska_file.duration
    frame_length = ska_file.frame_length
    original_fps = frame_length / duration

    # ---- Mapping: blob filename -> actual Action name ----
    # Store on the model collection as JSON (ID props are fine, but JSON keeps it simple)
    if map_collection is not None:
        try:
            mapping_raw = map_collection.get("_drs_action_map", "{}")
            mapping = json.loads(mapping_raw) if isinstance(mapping_raw, str) else {}
        except Exception:
            mapping = {}

        # Use the basename of the blob file, AND the raw string, so both resolve.
        base = os.path.basename(blob_key_original)
        mapping[blob_key_original] = action.name
        mapping[base] = action.name

        # Also record no-.ska variant (common in old blobs)
        if blob_key_original.lower().endswith(".ska"):
            mapping[blob_key_original[:-4]] = action.name
        if base.lower().endswith(".ska"):
            mapping[base[:-4]] = action.name

        map_collection["_drs_action_map"] = json.dumps(
            mapping, separators=(",", ":"), ensure_ascii=False
        )

    # Prepare bones and curves
    bone_map = {b.ska_identifier: b for b in bone_list}
    curves_map: Dict[int, Dict[str, bpy.types.FCurve]] = {}
    for b in bone_list:
        curves_map[b.ska_identifier] = get_bone_fcurves(action, arm_obj, b.name)
        arm_obj.pose.bones[b.name].rotation_mode = "QUATERNION"

    # Helper functions for extraction and tangents
    def extract_loc(b: DRSBone, kf: SKAKeyframe) -> Vector:
        return b.bind_rot.conjugated() @ (Vector((kf.x, kf.y, kf.z)) - b.bind_loc)

    def tangent_loc(b: DRSBone, kf: SKAKeyframe) -> Vector:
        return b.bind_rot.conjugated() @ (Vector((kf.tan_x, kf.tan_y, kf.tan_z)))

    def extract_rot(b: DRSBone, kf: SKAKeyframe) -> Tuple[float, float, float, float]:
        q = Quaternion((-kf.w, kf.x, kf.y, kf.z))
        r = b.bind_rot.conjugated() @ q
        return (r.w, r.x, r.y, r.z)

    def tangent_rot(b: DRSBone, kf: SKAKeyframe) -> Tuple[float, float, float, float]:
        tq = Quaternion((-kf.tan_w, kf.tan_x, kf.tan_y, kf.tan_z))
        tr = b.bind_rot.conjugated() @ tq
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
        frames = [round(t * frame_length) for t in times_norm]
        # For each component axis
        for idx, ax in enumerate(axes):
            # Values and tangents
            vals = [extract_fn(bone, kf)[idx] for _, kf in seq]
            tans = [tangent_fn(bone, kf)[idx] for _, kf in seq]
            fcurve = fcs[f"{prefix}_{ax}"]
            if not vals:
                continue
            if use_bezier:
                insert_hermite_bezier_curve(
                    fcurve, frames, vals, tans, duration, original_fps
                )
            else:
                for fr, v in zip(frames, vals):
                    insert_or_replace_key(fcurve, fr, v, interpolation="LINEAR")
    # Add NLA track strip
    track = arm_obj.animation_data.nla_tracks.new()
    strip = track.strips.new(action.name, 0, action)
    strip.repeat = ska_file.repeat
    track.name = action.name
    # Save Original Duration in the Action
    action["ska_original_duration"] = duration
    action["ska_original_fps"] = original_fps
    action["frame_length"] = ska_file.frame_length
