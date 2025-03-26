# animation_utils.py
import math
import bpy
from mathutils import Quaternion, Vector

from .ska_definitions import SKAKeyframe, SKA


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
) -> None:
    """
    Insert keyframes into the provided F-Curves.
    Animation_type 0: Location, 1: Rotation.
    """
    if animation_type == 0:
        translation = bind_rot.conjugated() @ (
            Vector((frame_data.x, frame_data.y, frame_data.z)) - bind_loc
        )
        for axis, value in zip("xyz", translation):
            kp = fcurves[f"location_{axis}"].keyframe_points.insert(frame, value)
            kp.interpolation = "BEZIER"
    elif animation_type == 1:
        # Convert frame_data into a quaternion (adjust sign as needed)
        rotation_quat = bind_rot.conjugated() @ Quaternion(
            (-frame_data.w, frame_data.x, frame_data.y, frame_data.z)
        )
        for axis, value in zip("wxyz", rotation_quat):
            kp = fcurves[f"rotation_{axis}"].keyframe_points.insert(frame, value)
            kp.interpolation = "BEZIER"


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


def create_animation(
    ska_file: SKA,
    armature_object: bpy.types.Object,
    bone_list: list,
    animation_name: str,
    import_animation_type: str,
) -> None:
    """
    High-level routine to create an animation on the armature from a SKA file.
    Prepares F-Curves for each bone and inserts keyframes based on the SKA keyframes.
    """
    fps = bpy.context.scene.render.fps
    armature_object.animation_data_create()
    action = create_action(armature_object, animation_name, repeat=ska_file.repeat)
    action["original_durion"] = ska_file.duration

    # Map bones to their fcurves using bone identifiers.
    bone_fcurve_map = {}
    for bone in bone_list:
        pose_bone = armature_object.pose.bones.get(bone.name)
        if pose_bone:
            bone_fcurve_map[bone.ska_identifier] = get_bone_fcurves(action, pose_bone)
        else:
            print(f"Warning: Bone {bone.name} not found in armature.")

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

            insert_keyframes(
                fcurves, frame_data, frame, header.type, bone.bind_rot, bone.bind_loc
            )

    add_animation_to_nla_track(armature_object, action)
