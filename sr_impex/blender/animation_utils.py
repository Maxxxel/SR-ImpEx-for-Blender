# animation_utils.py
from typing import List, Dict, Tuple
import os
import json
import math
from mathutils import Quaternion, Vector
import bpy

from sr_impex.definitions.ska_definitions import SKA, SKAKeyframe
from sr_impex.definitions.skeleton_definitions import DRSBone

IS_44_PLUS = bpy.app.version >= (4, 4, 0)


def clip_frame_range(clip):
    """Logical time interval, independent of the last stored pose sample."""
    start=float(clip.get('ska_start_frame',clip.frame_range[0]))
    return start,start+float(clip.get('frame_length',max(1.,clip.frame_range[1]-clip.frame_range[0])))


def configure_clip_playback(scene,clip,loop=None,start=0.,end=1.):
    """Blender range ends are inclusive; looping clip time is half-open."""
    if 'frame_length' in clip:
        from sr_impex.blender.ska_loop import sync
        sync(clip)
    first,last=clip_frame_range(clip);span=last-first
    first,last=first+start*span,first+end*span
    fps=float(clip.get('original_fps',scene.render.fps/scene.render.fps_base))
    base=max(1,min(120,round(fps)))
    scene.render.fps=base;scene.render.fps_base=base/max(fps,.001)
    loop=int(clip.get('repeat',0))==1 if loop is None else loop
    scene.frame_start=round(first)
    scene.frame_end=max(scene.frame_start,math.ceil(last-1e-6)-1 if loop else round(last))
    if scene.use_preview_range:
        scene.frame_preview_start=scene.frame_start;scene.frame_preview_end=scene.frame_end
    # Keep wall-clock speed when a heavy preview cannot draw every frame.
    scene.sync_mode='FRAME_DROP'
    return first,last


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
        p0, p1 = values[i], values[i + 1]
        m0, m1 = tangents[i], tangents[i + 1]
        dt_n = (f1 - f0) / (duration * fps)
        off_f = (f1 - f0) / 3.0
        off_v0 = (m0 * dt_n) / 3.0
        off_v1 = (m1 * dt_n) / 3.0
        kp0 = fcurve.keyframe_points[i]
        kp1 = fcurve.keyframe_points[i + 1]
        kp0.handle_right.x = f0 + off_f
        kp0.handle_right.y = p0 + off_v0
        kp1.handle_left.x = f1 - off_f
        kp1.handle_left.y = p1 - off_v1

    # Also set endpoint handles so endpoint tangents survive round-trips.
    # Blender doesn't need them for evaluation outside the curve range,
    # but SKA stores tangents for *every* keyframe, including endpoints.
    if n == 1:
        point=fcurve.keyframe_points[0];width=duration*fps/3
        point.handle_left=(frames[0]-width,values[0]-tangents[0]/3)
        point.handle_right=(frames[0]+width,values[0]+tangents[0]/3)
    if n >= 2:
        # First key: set LEFT handle from tangent[0] using first segment length
        f0, f1 = frames[0], frames[1]
        p0 = values[0]
        m0 = tangents[0]
        dt_n = (f1 - f0) / (duration * fps)
        off_f = (f1 - f0) / 3.0
        off_v0 = (m0 * dt_n) / 3.0
        kp0 = fcurve.keyframe_points[0]
        kp0.handle_left.x = f0 - off_f
        kp0.handle_left.y = p0 - off_v0

        # Last key: set RIGHT handle from tangent[-1] using last segment length
        f0, f1 = frames[-2], frames[-1]
        p1 = values[-1]
        m1 = tangents[-1]
        dt_n = (f1 - f0) / (duration * fps)
        off_f = (f1 - f0) / 3.0
        off_v1 = (m1 * dt_n) / 3.0
        kp1 = fcurve.keyframe_points[-1]
        kp1.handle_right.x = f1 + off_f
        kp1.handle_right.y = p1 + off_v1


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

    from sr_impex.utilities.ska_artist import capture_track
    import hashlib
    signature = hashlib.sha256(json.dumps([
        ska_file.type,ska_file.duration,ska_file.frame_length,ska_file.repeat,ska_file.stutter_mode,
        ska_file.unused1,ska_file.target_ids,[m.hex() for m in ska_file.text_markers],ska_file.annotation_bytes.hex(),
        [capture_track(ska_file,h) for h in ska_file.headers],
        [(b.ska_identifier,b.name,list(b.bind_loc),list(b.bind_rot)) for b in bone_list]],
        separators=(',',':')).encode()).hexdigest()
    # Reuse only identical animation/bind data, not unrelated short filenames.
    existing_action = bpy.data.actions.get(name)
    if existing_action is not None and existing_action.get('ska_import_signature')==signature:
        # Just assign it and return
        assign_action_compat(arm_obj, existing_action)
        if map_collection is not None:
            mapping=json.loads(map_collection.get('_drs_action_map','{}'))
            for key in (blob_key_original,os.path.basename(blob_key_original),
                        os.path.splitext(blob_key_original)[0],os.path.splitext(os.path.basename(blob_key_original))[0]):
                mapping[key]=existing_action.name
            map_collection['_drs_action_map']=json.dumps(mapping)
        print(f"Info: Action '{name}' already exists, assigned existing action.")
        return

    action = create_action(arm_obj, name=name, cyclic=ska_file.repeat == 1)
    duration = ska_file.duration
    frame_length = ska_file.frame_length
    if duration <= 0 or frame_length <= 0:
        raise ValueError('SKA duration and frame count must be greater than zero')
    original_fps = frame_length / duration
    from sr_impex.utilities.ska_artist import ALPHA_ID, ALPHA_PATH, RAW_TRACKS, capture_track
    preserved = []

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
        if hdr.bone_id == ALPHA_ID and hdr.type == 0:
            preserved.append(capture_track(ska_file,hdr))
            arm_obj['sr_ska_alpha'] = 1.0
            curve = ensure_fcurve_compat(action,arm_obj,ALPHA_PATH)
            seq = [(ska_file.times[i],ska_file.keyframes[i])
                   for i in range(hdr.tick,hdr.tick+hdr.interval)]
            frames = [t*frame_length for t,_ in seq]
            values, tangents = [k.x for _,k in seq], [k.tan_x for _,k in seq]
            if ska_file.stutter_mode == 2 and use_bezier:
                insert_hermite_bezier_curve(curve,frames,values,tangents,duration,original_fps)
            else:
                for frame,value in zip(frames,values):
                    insert_or_replace_key(curve,frame,value,
                        interpolation='CONSTANT' if ska_file.stutter_mode==0 else 'LINEAR')
            continue
        bone = bone_map.get(hdr.bone_id)
        fcs = curves_map.get(hdr.bone_id)
        if bone is None or fcs is None or hdr.type not in (0,1):
            preserved.append(capture_track(ska_file,hdr))
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
        frames = [t * frame_length for t in times_norm]
        # For each component axis
        for idx, ax in enumerate(axes):
            # Values and tangents
            vals = [extract_fn(bone, kf)[idx] for _, kf in seq]
            tans = [tangent_fn(bone, kf)[idx] for _, kf in seq]
            fcurve = fcs[f"{prefix}_{ax}"]
            if not vals:
                continue
            if use_bezier and ska_file.stutter_mode == 2:
                insert_hermite_bezier_curve(
                    fcurve, frames, vals, tans, duration, original_fps
                )
            else:
                for fr, v in zip(frames, vals):
                    insert_or_replace_key(fcurve, fr, v, interpolation="CONSTANT" if ska_file.stutter_mode==0 else "LINEAR")
    # Add NLA track strip
    track = arm_obj.animation_data.nla_tracks.new()
    track.strips.new(action.name, 0, action)
    track.name = action.name
    track.mute = True  # The selected active action plays; other imported clips do not stack.
    # Save Original Duration in the Action
    action["original_duration"] = duration
    action["original_fps"] = original_fps
    action["frame_length"] = ska_file.frame_length
    action["repeat"] = ska_file.repeat
    action["stutter_mode"] = ska_file.stutter_mode
    action['ska_version'] = ska_file.type
    action['ska_start_frame'] = 0.0
    # Compressed SKA tracks often stop at sample N-1. Keep that final interval
    # when fitting edited keys; last-key time is not the clip duration.
    from sr_impex.utilities.ska_utility import _iter_action_fcurves
    key_times=[p.co.x for c in _iter_action_fcurves(action) for p in c.keyframe_points]
    if key_times:
        action['ska_fit_padding']=[float(min(key_times)),float(frame_length-max(key_times))]
    from sr_impex.blender.ska_loop import sync
    sync(action)
    action[RAW_TRACKS] = json.dumps(preserved)
    action['ska_track_order'] = json.dumps([[h.bone_id,h.type] for h in ska_file.headers])
    action['ska_import_signature'] = signature
    # Preserve nonempty version 6/7 tail blocks through Blender actions.
    # Marker offsets refer to raw bytes in the shared annotation buffer.
    if ska_file.target_ids or ska_file.text_markers or ska_file.annotation_bytes:
        action["ska_tail_metadata"] = json.dumps({
            "target_ids": ska_file.target_ids,
            "text_markers_hex": [marker.hex() for marker in ska_file.text_markers],
            "annotation_hex": ska_file.annotation_bytes.hex(),
        })
    if ska_file.type == 7:
        action["unused1"] = ska_file.unused1
    action["prefix"] = parent_folder
