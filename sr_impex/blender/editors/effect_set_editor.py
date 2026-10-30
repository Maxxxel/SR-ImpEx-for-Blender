# effect_set_editor.py
# Always-visible EffectSet editor (Collection Properties).
# Shows an info message if the selected collection is not a DRSModel_* one.

from __future__ import annotations
import json
import zlib
import time
from os.path import dirname, realpath
from typing import Dict, Optional

import bpy
from bpy.props import (
    StringProperty, IntProperty, BoolProperty, FloatProperty,
    FloatVectorProperty, EnumProperty, CollectionProperty, PointerProperty
)

# Import your current DRS defs (latest uploaded)
from sr_impex.definitions.effect_definitions import EffectSet, SkelEff, Keyframe, Variant, SoundContainer, SoundHeader, SoundHeader2, SoundFile, AdditionalSoundContainer
from sr_impex.utilities.drs_resolvers import resolve_action_from_blob_name
from sr_impex.utilities.effect_groups import GROUPS,groups as resource_groups,label as resource_group_label

EFFECT_BLOB_KEY = "EffectSetJSON"
resource_dir = dirname(realpath(__file__)) + "/resources"

# -----------------------
# Helpers
# -----------------------

def _norm_ska_name(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return s if s.lower().endswith(".ska") else (s + ".ska")


# ---------------------------------------------------------------------------
# Actions: UI / Name-Handling
# ---------------------------------------------------------------------------

def _ensure_action_name_props(act: bpy.types.Action) -> str:
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

    def _derive_ui_name(src: str) -> str:
        base = (src or "").strip()
        if base.lower().endswith(".ska"):
            base = base[:-4]

        short = base
        if "-" in short:
            short = short.rsplit("-", 1)[-1]
        if short.startswith("skel_") and short.count("_") >= 2:
            short = short.split("_", 2)[2]

        return short or base or (src or "")

    short_from_raw = _derive_ui_name(raw)
    short_from_name = _derive_ui_name(act.name or "")
    short = short_from_name or short_from_raw

    try:
        if act.get('ui_name')!=short:act["ui_name"] = short
    except Exception:
        pass

    return short


def _action_label_from_id(action_id: str) -> str:
    if not action_id or action_id == "NONE":
        return "<None>"
    act = bpy.data.actions.get(action_id)
    if not act:
        return action_id
    return _ensure_action_name_props(act)


def _actions_enum(_self, _ctx):
    global _ACTION_ENUM_KEY,_ACTION_ENUM_ITEMS
    acts = bpy.data.actions
    key=tuple((act.as_pointer(),act.name,act.get('raw_name','')) for act in acts)
    if globals().get('_ACTION_ENUM_KEY')==key:return _ACTION_ENUM_ITEMS
    items = [("NONE", "<None>", "")]
    pairs = []
    for act in acts:
        ident = act.name
        label = _ensure_action_name_props(act)
        pairs.append((ident, label))
    pairs.sort(key=lambda p: p[1].lower())
    items.extend((ident, label, "") for ident, label in pairs)
    _ACTION_ENUM_KEY=key;_ACTION_ENUM_ITEMS=items
    return items


def _read_blob(col: bpy.types.Collection) -> Dict:
    raw = col.get(EFFECT_BLOB_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _write_blob(col: bpy.types.Collection, blob: Dict) -> None:
    # Apply edits to timelines while preserving UUID/version and hidden sounds.
    merged = _read_blob(col)
    merged.update(blob)
    blob = merged
    blob.setdefault("type", 12)  # matches your current drs_definitions default
    cs = blob.get("checksum") or ""
    if not cs:
        # deterministic first-seed using collection name
        crc = zlib.crc32(col.name.encode("utf-8")) & 0xFFFFFFFF
        blob["checksum"] = f"sr-{crc}-0"
    blob["checksum_length"] = len(blob.get("checksum", ""))
    blob.setdefault("unknown4", [])
    blob.setdefault("unknown3", [])
    blob.setdefault("effects", [])
    col[EFFECT_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


def _active_drs_collection(context) -> Optional[bpy.types.Collection]:
    """
    Get the active DRSModel_* collection.
    Checks Outliner selection first, then active view layer collection.
    """
    from sr_impex.utilities.artist_context import find_model
    return find_model(context or bpy.context)


def _find_armature(col: bpy.types.Collection) -> Optional[bpy.types.Object]:
    """
    Recursively find the preferred armature within a collection.
    Prefers 'Control_Rig'.
    """
    def visit(c: bpy.types.Collection) -> Optional[bpy.types.Object]:
        fallback_ctrl = None
        for o in c.objects:
            if o.type == "ARMATURE":
                # Prefer the deform rig
                if "Control_Rig" in o.name:
                    return o
                # Remember a control rig only as fallback
                if fallback_ctrl is None:
                    fallback_ctrl = o
        for ch in c.children:
            got = visit(ch)
            if got:
                return got
        return fallback_ctrl  # if nothing else found
    return visit(col)


def _activate_and_bind_action(context: bpy.types.Context, arm: bpy.types.Object, act: bpy.types.Action):
    """Make armature active/selected and ensure the action is bound for playback."""
    vl = context.view_layer
    # clear selection
    for o in context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    vl.objects.active = arm
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act


# -----------------------
# State
# -----------------------

class EffVariantPG(bpy.types.PropertyGroup):
    weight: IntProperty(name="Chance (%)", default=100, min=0, max=255,
        description="Engine percentage bucket, not a relative weight. A total below 100 leaves a chance of silence/no FX")  # type: ignore
    file: StringProperty(name="File (.fxb/.wav/.snr)", default="")  # type: ignore

    def to_dict(self) -> Dict:
        return {"weight": int(self.weight), "name": self.file or ""}

    def from_dict(self, d: Dict):
        self.weight = int(d.get("weight", 100))
        self.file = (d.get("name") or "").strip()


class EffKeyframePG(bpy.types.PropertyGroup):
    time: FloatProperty(name="Time (0..1)", default=0.0, min=0.0, max=1.0, precision=3)  # type: ignore
    key_type: EnumProperty(
        name="Type",
        items=[
            ("0", "Sound (snr/wav)", "Play audio with falloff, volume and pitch settings"),
            ("1", "World FX (fxb)", "Spawn FX at the actor's sampled world position with XYZ offset"),
            ("2", "Linked FX (fxb)", "Create FX using source/target nodes and animation controllers"),
            ("3", "Fade Out Persistent FX", "Fade existing locator FX matching the variant filename; offset X is seconds"),
            ("4", "Fade In Persistent FX", "Fade existing locator FX matching the variant filename; offset X is seconds"),
        ],
        default="0",
    )  # type: ignore
    min_falloff: FloatProperty(name="Min Falloff (Export Only)", default=0.0,
        description="Engine positional sound distance; Blender timeline audio has no spatial falloff")  # type: ignore
    max_falloff: FloatProperty(name="Max Falloff (Export Only)", default=0.0,
        description="Engine positional sound distance; Blender timeline audio has no spatial falloff")  # type: ignore
    volume: FloatProperty(name="Volume", default=1.0)  # type: ignore
    pitch_min: FloatProperty(name="Pitch Min", default=0.0,
        description="Playback-rate shift: 0 is unchanged, 0.1 adds 10%, -0.1 subtracts 10%; random range with Pitch Max")  # type: ignore
    pitch_max: FloatProperty(name="Pitch Max", default=0.0,
        description="Upper playback-rate shift; 0 is unchanged. Preview changes both pitch and duration")  # type: ignore
    offset: FloatVectorProperty(name="Offset", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")  # type: ignore
    interruptable: BoolProperty(name="Interruptible (Export Only)", default=False,
        description="Engine lifetime handling on animation interruption; Blender timeline has no gameplay state transitions")  # type: ignore
    # Signed byte retained for v12; traced event dispatcher substitutes -1.
    condition: IntProperty(name="Stored Condition", default=-1, min=-128, max=127,
        description="Preserved v12 field; the traced engine timeline path does not forward it to mode filtering")  # type: ignore

    variants: CollectionProperty(type=EffVariantPG)  # type: ignore
    active_variant: IntProperty(default=0)  # type: ignore

    def to_dict(self) -> Dict:
        return {
            "time": float(self.time),
            "keyframe_type": int(self.key_type),
            "min_falloff": float(self.min_falloff),
            "max_falloff": float(self.max_falloff),
            "volume": float(self.volume),
            "pitch_shift_min": float(self.pitch_min),
            "pitch_shift_max": float(self.pitch_max),
            "offset": [float(self.offset[0]), float(self.offset[1]), float(self.offset[2])],
            "interruptable": 1 if bool(self.interruptable) else 0,
            "condition": int(self.condition),
            "variants": [v.to_dict() for v in self.variants],
        }

    def from_dict(self, d: Dict):
        self.time = float(d.get("time", 0.0))
        self.key_type = str(int(1 if d.get("keyframe_type") is None else d["keyframe_type"]))
        self.min_falloff = float(d.get("min_falloff", 0.0))
        self.max_falloff = float(d.get("max_falloff", 0.0))
        self.volume = float(d.get("volume", 1.0))
        self.pitch_min = float(d.get("pitch_shift_min", 0.0))
        self.pitch_max = float(d.get("pitch_shift_max", 0.0))
        off = d.get("offset", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0]
        self.offset = (float(off[0]), float(off[1]), float(off[2]))
        self.interruptable = bool(int(d.get("interruptable", 0)))
        # prefer 'condition', fallback to 'uk'
        cond = d.get("condition", d.get("uk", -1))
        self.condition = int(-1 if cond is None else cond)
        self.variants.clear()
        for vd in d.get("variants", []) or []:
            v = self.variants.add()
            v.from_dict(vd)


def _effect_action_changed(self, context):
    action = bpy.data.actions.get(self.action)
    if action:
        self.raw_ska = _norm_ska_name(action.get('raw_name', action.name))


class EffEntryPG(bpy.types.PropertyGroup):
    action: EnumProperty(name="Action", items=_actions_enum, update=_effect_action_changed)  # type: ignore
    raw_ska: StringProperty(default="", options={"HIDDEN"})  # type: ignore
    keyframes: CollectionProperty(type=EffKeyframePG)  # type: ignore
    active_keyframe: IntProperty(default=0)  # type: ignore

    def to_dict(self) -> Dict:
        ska = self.raw_ska or _norm_ska_name(self.action if self.action and self.action != "NONE" else "")
        return {"action": ska, "keyframes": [k.to_dict() for k in self.keyframes]}

    def from_dict(self, d: dict):
        ska = d.get("action", "") or ""
        # Try to resolve to an existing Action
        act = resolve_action_from_blob_name(ska)
        self.action = act if act else "NONE"
        # Preserve the imported reference; only a later user selection retargets it.
        self.raw_ska = ska

        self.keyframes.clear()
        for kd in d.get("keyframes", []) or []:
            k = self.keyframes.add()
            k.from_dict(kd)


class EffState(bpy.types.PropertyGroup):
    model_key: StringProperty(default='',options={'HIDDEN'})  # type: ignore
    items: CollectionProperty(type=EffEntryPG)  # type: ignore
    active_index: IntProperty(default=0)  # type: ignore
    preview_audio: BoolProperty(name='Audio',default=True,description='Include independent sound cues in the scene timeline preview')  # type: ignore
    preview_seed: IntProperty(default=0,min=0,options={'HIDDEN'},description='Internal Blender preview randomness; never exported')  # type: ignore
    preview_live: BoolProperty(name='Live Update',default=True,
        description='After Update Preview, rebuild automatically when edits settle; deferred during rendering')  # type: ignore
    resource_group: EnumProperty(name='Group',items=GROUPS,default='ALL',
        description='Filter by resource-name/path hints')  # type: ignore
    preview_variant: EnumProperty(name='Variant Preview',default='RANDOM',items=[
        ('RANDOM','Engine Chances','Use the saved percentage buckets, including the chance of no resource'),
        ('SELECTED','Selected Variant','Audition the highlighted variant of the highlighted event, ignoring its chance; not exported')])  # type: ignore


def _state() -> EffState:
    return bpy.context.window_manager.drs_effect_state


# -----------------------
# Blob <-> State
# -----------------------

def _blob_to_state(st: EffState, col: bpy.types.Collection):
    b = _read_blob(col)
    st.items.clear()
    for ed in (b.get("effects") or []):
        it = st.items.add()
        it.from_dict(ed)
    st.model_key=str(col.as_pointer())


def _state_to_blob(st: EffState) -> Dict:
    return {
        "effects": [it.to_dict() for it in st.items],
        # type/checksum/unknown* are preserved in _write_blob
    }


_model_drafts={}

# One explicit preview build arms live editing for that scene/model. Changes
# are coalesced outside RNA callbacks/draw/frame handlers; no asset IO per frame.
_live_target=None
_live_signature=None
_live_pending=None
_live_status=''
_live_source='EFFECT'


def _preview_entry(state):
    return state.items[state.active_index] if 0<=state.active_index<len(state.items) else None


def _variant_override(state,entry):
    if state.preview_variant=='SELECTED' and entry and 0<=entry.active_keyframe<len(entry.keyframes):
        key=entry.keyframes[entry.active_keyframe]
        if 0<=key.active_variant<len(key.variants):return (entry.active_keyframe,key.active_variant)
    return None


def _preview_signature(context,model,state):
    entry=_preview_entry(state) if _live_source=='EFFECT' else None
    action=_locator_action(model) if _live_source=='LOCATOR' else bpy.data.actions.get(entry.action) if entry else None
    data=entry.to_dict() if entry else None
    for key in data['keyframes'] if data else []:
        for field in ('min_falloff','max_falloff','interruptable','condition'):key.pop(field,None)
        if key['keyframe_type']==0:key.pop('offset',None)
        else:
            for field in ('volume','pitch_shift_min','pitch_shift_max'):key.pop(field,None)
    from sr_impex.blender.animation_utils import clip_frame_range
    return json.dumps([data,entry.action if entry else None,
        [list(action.frame_range),clip_frame_range(action),action.get('original_fps'),action.get('repeat')] if action else [context.scene.frame_start,context.scene.frame_end],
        state.preview_audio,state.preview_seed,_variant_override(state,entry),
        _locator_preview_blob(model),context.scene.render.fps,context.scene.render.fps_base],sort_keys=True)


def _arm_live_preview(context,model,source='EFFECT'):
    global _live_target,_live_signature,_live_pending,_live_source
    _live_source=source
    _live_target=(context.scene.as_pointer(),model.as_pointer())
    _live_signature=_preview_signature(context,model,_state());_live_pending=None


def _disarm_live_preview():
    global _live_target,_live_signature,_live_pending,_live_status
    _live_target=_live_signature=_live_pending=None;_live_status=''


def _build_editor_preview(context,model):
    from sr_impex.blender import effect_preview
    state=_state();entry=_preview_entry(state) if _live_source=='EFFECT' else None
    return effect_preview.build(context,model,entry,_library(context),state.preview_seed,state.preview_audio,
                                variant_override=_variant_override(state,entry),
                                locator_blob=_locator_preview_blob(model),
                                action_override=_locator_action(model) if _live_source=='LOCATOR' else None)


def _locator_action(model):
    rig=next((o for o in model.all_objects if o.type=='ARMATURE' and 'Control_Rig' not in o.name),None)
    return rig.animation_data.action if rig and rig.animation_data else None


def _locator_preview_blob(model):
    from .locator_editor import preview_resource_blob
    return preview_resource_blob(model)


def _refresh_live_preview(now=None):
    global _live_signature,_live_pending,_live_status
    if not _live_target:return .2
    context=bpy.context
    if bpy.app.is_job_running('RENDER') or context.mode!='OBJECT':return .2
    try:
        model=_active_drs_collection(context);state=_state()
        if not model or not state.preview_live:return .2
        target=(context.scene.as_pointer(),model.as_pointer())
        if target!=_live_target or (_live_source=='EFFECT' and state.model_key!=str(model.as_pointer())):return .2
        signature=_preview_signature(context,model,state)
        if signature==_live_signature:
            _live_pending=None;return .2
        now=time.monotonic() if now is None else now
        if not _live_pending or _live_pending[0]!=signature:
            _live_pending=(signature,now+.3);return .2
        if now<_live_pending[1]:return .2
        # A failed build is retried only after another edit or Update Preview.
        _live_signature=signature;_live_pending=None
        from sr_impex.blender.effect_preview import NoPreviewResources
        try:
            _build_editor_preview(context,model);_live_status='Live preview updated'
        except NoPreviewResources as exc:_live_status=str(exc)
        except Exception as exc:
            from sr_impex.blender.effect_preview import clear
            clear(context.scene,model)
            _live_status='Preview: '+str(exc)
        # build() can change the scene range to match the Action.
        _live_signature=_preview_signature(context,model,state)
        if context.screen:
            for area in context.screen.areas:
                if area.type=='VIEW_3D':area.tag_redraw()
    except (AttributeError,ReferenceError,RuntimeError):pass
    return .2


def _sync_selected_model():
    # Run outside panel draw: Blender forbids RNA collection writes while drawing.
    if bpy.app.is_job_running('RENDER'):return .5
    try:
        from sr_impex.blender.effect_preview import stop_changed_model_audio
        stop_changed_model_audio(bpy.context)
        model=_active_drs_collection(bpy.context)
        if model:
            state=_state();key=str(model.as_pointer())
            if state.model_key!=key:
                if state.model_key:_model_drafts[state.model_key]=_state_to_blob(state)
                draft=_model_drafts.get(key)
                _blob_to_state(state,model)
                if draft is not None:
                    state.items.clear()
                    for data in draft['effects']:state.items.add().from_dict(data)
    except (AttributeError,ReferenceError,RuntimeError):pass
    return .5


# -----------------------
# DRS <-> Blob
# -----------------------

def effectset_to_blob(eff: EffectSet) -> Dict:
    blob = {
        "type": int(getattr(eff, "type", 12) or 12),
        "checksum_length": int(getattr(eff, "checksum_length", 0)),
        "checksum": getattr(eff, "checksum", "") or "",
        "legacy_v10_header": list(eff.legacy_v10_header),
        "effects": [],
        "impact_sounds": [],
        "additional_sounds": [],
    }

    for se in getattr(eff, "skel_effekts", []) or []:
        entry = {"action": getattr(se, "name", "") or "", "keyframes": []}
        for kf in getattr(se, "keyframes", []) or []:
            kd = {
                "time": float(kf.time),
                "keyframe_type": int(kf.keyframe_type),
                "min_falloff": float(kf.min_falloff),
                "max_falloff": float(kf.max_falloff),
                "volume": float(kf.volume),
                "pitch_shift_min": float(kf.pitch_shift_min),
                "pitch_shift_max": float(kf.pitch_shift_max),
                "offset": list(getattr(kf, "offset", [0.0, 0.0, 0.0])),
                "interruptable": int(getattr(kf, "interruptable", 0)),
                "condition": int(kf.condition if kf.condition is not None else -1),
                "variants": [
                    {"weight": int(v.weight), "name": getattr(v, "name", "") or ""}
                    for v in (getattr(kf, "variants", []) or [])
                ],
            }
            entry["keyframes"].append(kd)
        blob["effects"].append(entry)

    for sound_container in getattr(eff, "impact_sounds", []) or []:
        sc = {
            "sound_header": {
                "is_one": int(sound_container.sound_header.is_one),
                "min_falloff": float(getattr(sound_container.sound_header, "min_falloff", 1.0)),
                "max_falloff": float(getattr(sound_container.sound_header, "max_falloff", 1.0)),
                "volume": float(getattr(sound_container.sound_header, "volume", 1.0)),
                "pitch_shift_min": float(getattr(sound_container.sound_header, "pitch_shift_min", 1.0)),
                "pitch_shift_max": float(getattr(sound_container.sound_header, "pitch_shift_max", 1.0)),
            },
            "uk_index": int(getattr(sound_container, "uk_index", 0)),
            "nbr_sound_variations": int(getattr(sound_container, "nbr_sound_variations", 0)),
            "sound_files": [
                {
                    "weight": int(sound_file.weight),
                    "sound_header": {
                        "is_one": int(sound_file.sound_header.is_one),
                        "min_falloff": float(getattr(sound_file.sound_header, "min_falloff", 1.0)),
                        "max_falloff": float(getattr(sound_file.sound_header, "max_falloff", 1.0)),
                        "volume": float(getattr(sound_file.sound_header, "volume", 1.0)),
                        "pitch_shift_min": float(getattr(sound_file.sound_header, "pitch_shift_min", 1.0)),
                        "pitch_shift_max": float(getattr(sound_file.sound_header, "pitch_shift_max", 1.0)),
                    },
                    "sound_file_name_length": int(getattr(sound_file, "sound_file_name_length", 0)),
                    "sound_file_name": getattr(sound_file, "sound_file_name", "") or "",
                }
                for sound_file in (getattr(sound_container, "sound_files", []) or [])
            ],
        }
        blob["impact_sounds"].append(sc)

    for add_sound_container in getattr(eff, "additional_sounds", []) or []:
        asc = {
            "sound_header": {
                "is_one": int(add_sound_container.sound_header.is_one),
                "min_falloff": float(getattr(add_sound_container.sound_header, "min_falloff", 1.0)),
                "max_falloff": float(getattr(add_sound_container.sound_header, "max_falloff", 1.0)),
                "volume": float(getattr(add_sound_container.sound_header, "volume", 1.0)),
                "pitch_shift_min": float(getattr(add_sound_container.sound_header, "pitch_shift_min", 1.0)),
                "pitch_shift_max": float(getattr(add_sound_container.sound_header, "pitch_shift_max", 1.0)),
            },
            "sound_type": int(getattr(add_sound_container, "sound_type", 0)),
            "nbr_sound_variations": int(getattr(add_sound_container, "nbr_sound_variations", 0)),
            "sound_containers": []
        }
        for sound_container in getattr(add_sound_container, "sound_containers", []) or []:
            sc = {
                "sound_header": {
                    "is_one": int(sound_container.sound_header.is_one),
                    "min_falloff": float(getattr(sound_container.sound_header, "min_falloff", 1.0)),
                    "max_falloff": float(getattr(sound_container.sound_header, "max_falloff", 1.0)),
                    "volume": float(getattr(sound_container.sound_header, "volume", 1.0)),
                    "pitch_shift_min": float(getattr(sound_container.sound_header, "pitch_shift_min", 1.0)),
                    "pitch_shift_max": float(getattr(sound_container.sound_header, "pitch_shift_max", 1.0)),
                },
                "uk_index": int(getattr(sound_container, "uk_index", 0)),
                "nbr_sound_variations": int(getattr(sound_container, "nbr_sound_variations", 0)),
                "sound_files": [
                    {
                        "weight": int(sound_file.weight),
                        "sound_header": {
                            "is_one": int(sound_file.sound_header.is_one),
                            "min_falloff": float(getattr(sound_file.sound_header, "min_falloff", 1.0)),
                            "max_falloff": float(getattr(sound_file.sound_header, "max_falloff", 1.0)),
                            "volume": float(getattr(sound_file.sound_header, "volume", 1.0)),
                            "pitch_shift_min": float(getattr(sound_file.sound_header, "pitch_shift_min", 1.0)),
                            "pitch_shift_max": float(getattr(sound_file.sound_header, "pitch_shift_max", 1.0)),
                        },
                        "sound_file_name_length": int(getattr(sound_file, "sound_file_name_length", 0)),
                        "sound_file_name": getattr(sound_file, "sound_file_name", "") or "",
                    }
                    for sound_file in (getattr(sound_container, "sound_files", []) or [])
                ],
            }
            asc["sound_containers"].append(sc)
        blob["additional_sounds"].append(asc)

    return blob


def blob_to_effectset(blob: Dict) -> EffectSet:
    eff = EffectSet()
    eff.type = int(blob.get("type", 12) or 12)
    eff.checksum = str(blob.get("checksum", ""))
    eff.checksum_length = len(eff.checksum)
    eff.legacy_v10_header = blob.get("legacy_v10_header", blob.get("unknown", [0.0] * 5))

    eff.skel_effekts = []
    for ed in (blob.get("effects") or []):
        se = SkelEff()
        ska = _norm_ska_name(ed.get("action", "") or "")
        se.name = ska
        se.length = len(se.name)

        se.keyframes = []
        for kd in (ed.get("keyframes") or []):
            kf = Keyframe()
            kf.time = float(kd.get("time", 0.0))
            kf.keyframe_type = int(kd.get("keyframe_type", 1))
            kf.min_falloff = float(kd.get("min_falloff", 0.0))
            kf.max_falloff = float(kd.get("max_falloff", 0.0))
            kf.volume = float(kd.get("volume", 1.0))
            kf.pitch_shift_min = float(kd.get("pitch_shift_min", 0.0))
            kf.pitch_shift_max = float(kd.get("pitch_shift_max", 0.0))
            off = kd.get("offset", [0.0, 0.0, 0.0])
            kf.offset = [float(off[0]), float(off[1]), float(off[2])]
            kf.interruptable = 1 if int(kd.get("interruptable", 0)) else 0
            cond = kd.get("condition", kd.get("uk", -1))
            kf.condition = int(-1 if cond is None else cond)

            kf.variants = []
            for vd in (kd.get("variants") or []):
                name = (vd.get("name") or "").strip()
                if not name:
                    continue
                v = Variant()
                v.weight = int(vd.get("weight", 100))
                v.name = name
                v.length = len(v.name)
                kf.variants.append(v)
            kf.variant_count = len(kf.variants)

            se.keyframes.append(kf)

        se.keyframe_count = len(se.keyframes)
        eff.skel_effekts.append(se)

    eff.length = len(eff.skel_effekts)

    eff.impact_sounds = []

    for scd in (blob.get("impact_sounds") or []):
        sc = SoundContainer()
        shd = scd.get("sound_header", {})
        sh = SoundHeader()
        sh.is_one = int(shd.get("is_one", 0))
        sh.max_falloff = float(shd.get("max_falloff", 1.0))
        sh.min_falloff = float(shd.get("min_falloff", 1.0))
        sh.volume = float(shd.get("volume", 1.0))
        sh.pitch_shift_min = float(shd.get("pitch_shift_min", 1.0))
        sh.pitch_shift_max = float(shd.get("pitch_shift_max", 1.0))
        sc.sound_header = sh
        sc.uk_index = int(scd.get("uk_index", 0))
        sc.nbr_sound_variations = int(scd.get("nbr_sound_variations", 0))

        sc.sound_files = []
        for sfd in (scd.get("sound_files") or []):
            sf = SoundFile()
            sf.weight = int(sfd.get("weight", 100))
            sfd_shd = sfd.get("sound_header", {})
            sfd_sh = SoundHeader2()
            sfd_sh.is_one = int(sfd_shd.get("is_one", 0))
            sfd_sh.max_falloff = float(sfd_shd.get("max_falloff", 1.0))
            sfd_sh.min_falloff = float(sfd_shd.get("min_falloff", 1.0))
            sfd_sh.volume = float(sfd_shd.get("volume", 1.0))
            sfd_sh.pitch_shift_min = float(sfd_shd.get("pitch_shift_min", 1.0))
            sfd_sh.pitch_shift_max = float(sfd_shd.get("pitch_shift_max", 1.0))
            sf.sound_header = sfd_sh
            sf.sound_file_name_length = int(sfd.get("sound_file_name_length", 0))
            sf.sound_file_name = str(sfd.get("sound_file_name", "") or "")
            sc.sound_files.append(sf)

        eff.impact_sounds.append(sc)

    eff.number_impact_sounds = len(eff.impact_sounds)

    eff.additional_sounds = []

    for ascd in (blob.get("additional_sounds") or []):
        asc = AdditionalSoundContainer()
        ashd = ascd.get("sound_header", {})
        ash = SoundHeader()
        ash.is_one = int(ashd.get("is_one", 0))
        ash.max_falloff = float(ashd.get("max_falloff", 1.0))
        ash.min_falloff = float(ashd.get("min_falloff", 1.0))
        ash.volume = float(ashd.get("volume", 1.0))
        ash.pitch_shift_min = float(ashd.get("pitch_shift_min", 1.0))
        ash.pitch_shift_max = float(ashd.get("pitch_shift_max", 1.0))
        asc.sound_header = ash
        asc.sound_type = int(ascd.get("sound_type", 0))
        asc.nbr_sound_variations = int(ascd.get("nbr_sound_variations", 0))

        asc.sound_containers = []
        for scd in (ascd.get("sound_containers") or []):
            sc = SoundContainer()
            shd = scd.get("sound_header", {})
            sh = SoundHeader()
            sh.is_one = int(shd.get("is_one", 0))
            sh.max_falloff = float(shd.get("max_falloff", 1.0))
            sh.min_falloff = float(shd.get("min_falloff", 1.0))
            sh.volume = float(shd.get("volume", 1.0))
            sh.pitch_shift_min = float(shd.get("pitch_shift_min", 1.0))
            sh.pitch_shift_max = float(shd.get("pitch_shift_max", 1.0))
            sc.sound_header = sh
            sc.uk_index = int(scd.get("uk_index", 0))
            sc.nbr_sound_variations = int(scd.get("nbr_sound_variations", 0))

            sc.sound_files = []
            for sfd in (scd.get("sound_files") or []):
                sf = SoundFile()
                sf.weight = int(sfd.get("weight", 100))
                sfd_shd = sfd.get("sound_header", {})
                sfd_sh = SoundHeader2()
                sfd_sh.is_one = int(sfd_shd.get("is_one", 0))
                sfd_sh.max_falloff = float(sfd_shd.get("max_falloff", 1.0))
                sfd_sh.min_falloff = float(sfd_shd.get("min_falloff", 1.0))
                sfd_sh.volume = float(sfd_shd.get("volume", 1.0))
                sfd_sh.pitch_shift_min = float(sfd_shd.get("pitch_shift_min", 1.0))
                sfd_sh.pitch_shift_max = float(sfd_shd.get("pitch_shift_max", 1.0))
                sf.sound_header = sfd_sh
                sf.sound_file_name_length = int(sfd.get("sound_file_name_length", 0))
                sf.sound_file_name = str(sfd.get("sound_file_name", "") or "")
                sc.sound_files.append(sf)

            asc.sound_containers.append(sc)

        eff.additional_sounds.append(asc)

    eff.number_additional_sounds = len(eff.additional_sounds)
    return eff


# -----------------------
# UI Lists + Ops
# -----------------------

class DRS_UL_EffectKeyframes(bpy.types.UIList):
    bl_idname = "DRS_UL_EffectKeyframes"

    def draw_item(self, _ctx, layout, _data, item: 'EffKeyframePG', _icon, _active, _flt):
        # compact summary: time + type
        row = layout.row(align=True)
        row.label(text=f"{item.time:.3f}")
        # item.key_type is an enum with labels; show label text:
        label = dict(item.bl_rna.properties['key_type'].enum_items).get(item.key_type).name
        row.label(text=label)


class DRS_UL_Effects(bpy.types.UIList):
    bl_idname = "DRS_UL_Effects"

    def draw_item(self, _ctx, layout, _data, item: 'EffEntryPG', _icon, _active, _flt):
        row = layout.row(align=True)
        label = _action_label_from_id(item.action)
        row.label(text=label, icon="ACTION")
        row.label(
            text=f"{len(item.keyframes)} effect{'s' if len(item.keyframes) != 1 else ''}"
        )



class DRS_UL_EffectVariants(bpy.types.UIList):
    bl_idname = "DRS_UL_EffectVariants"

    def draw_item(self, _ctx, layout, _data, item: 'EffVariantPG', _icon, _active, _flt):
        row = layout.row(align=True)
        row.label(text=item.file or "<empty>", icon="FILE")
        row.label(text=f"{int(item.weight)}%")


class DRS_OT_Effect_Add(bpy.types.Operator):
    bl_description = 'Add an effects entry for a model animation'
    bl_idname = "drs.effect_add"
    bl_label = "Add Effect"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        it = st.items.add()
        it.action = "NONE"
        it.raw_ska = ""
        st.active_index = len(st.items) - 1
        return {"FINISHED"}


class DRS_OT_Effect_Remove(bpy.types.Operator):
    bl_description = 'Remove the selected effects entry; keep the animation and source effect files'
    bl_idname = "drs.effect_remove"
    bl_label = "Remove Effect"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        i = st.active_index
        if 0 <= i < len(st.items):
            st.items.remove(i)
            st.active_index = min(i, len(st.items) - 1)
        return {"FINISHED"}


class DRS_OT_Keyframe_Add(bpy.types.Operator):
    bl_description = 'Add an event at a time within the selected animation'
    bl_idname = "drs.effect_key_add"
    bl_label = "Add Keyframe"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        k = it.keyframes.add()
        k.time = 0.0
        k.key_type = "1"
        k.volume = 1.0
        k.interruptable = False
        v = k.variants.add()
        v.weight = 100
        v.file = ""
        it.active_keyframe = len(it.keyframes) - 1
        return {"FINISHED"}


class DRS_OT_Keyframe_Remove(bpy.types.Operator):
    bl_description = 'Remove the selected event from this animation'
    bl_idname = "drs.effect_key_remove"
    bl_label = "Remove Keyframe"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        i = it.active_keyframe
        if 0 <= i < len(it.keyframes):
            it.keyframes.remove(i)
            it.active_keyframe = min(i, len(it.keyframes) - 1)
        return {"FINISHED"}


class DRS_OT_Variant_Add(bpy.types.Operator):
    bl_description = 'Add a resource alternative for this event; chances determine which one the engine chooses'
    bl_idname = "drs.effect_variant_add"
    bl_label = "Add Variant"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        if not 0 <= it.active_keyframe < len(it.keyframes):
            return {"CANCELLED"}
        k = it.keyframes[it.active_keyframe]
        v = k.variants.add()
        v.weight = 100
        v.file = ""
        k.active_variant = len(k.variants) - 1
        return {"FINISHED"}


class DRS_OT_Variant_Remove(bpy.types.Operator):
    bl_description = 'Remove the selected resource alternative from this event'
    bl_idname = "drs.effect_variant_remove"
    bl_label = "Remove Variant"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        if not 0 <= it.active_keyframe < len(it.keyframes):
            return {"CANCELLED"}
        k = it.keyframes[it.active_keyframe]
        i = k.active_variant
        if 0 <= i < len(k.variants):
            k.variants.remove(i)
            k.active_variant = min(i, len(k.variants) - 1)
        return {"FINISHED"}


class DRS_OT_Effect_Save(bpy.types.Operator):
    """Write current editor state to the active model's EffectSet blob."""
    bl_idname = "drs.effect_save"
    bl_label = "Save"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        col = _active_drs_collection(bpy.context)
        if not col:
            self.report({"ERROR"}, "Select a model mesh to edit its settings.")
            return {"CANCELLED"}
        if _state().model_key and _state().model_key!=str(col.as_pointer()):
            self.report({'ERROR'},'Model selection changed; wait for the EffectSet panel to refresh')
            return {'CANCELLED'}
        _write_blob(col, _state_to_blob(_state()))
        return {"FINISHED"}


class DRS_OT_Effect_Reload(bpy.types.Operator):
    """Reload editor state from the active model's EffectSet blob."""
    bl_idname = "drs.effect_reload"
    bl_label = "Reset"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        col = _active_drs_collection(bpy.context)
        if not col:
            self.report({"ERROR"}, "Select a model mesh to edit its settings.")
            return {"CANCELLED"}
        _blob_to_state(_state(), col)
        _model_drafts.pop(str(col.as_pointer()),None)
        return {"FINISHED"}


class DRS_OT_Keyframe_Move(bpy.types.Operator):
    bl_description = 'Move the selected event up or down in the event list'
    bl_idname = "drs.effect_key_move"
    bl_label = "Move Keyframe"
    bl_options = {"INTERNAL"}

    direction: bpy.props.EnumProperty(
        items=[("UP","Up",""), ("DOWN","Down","")], default="UP"
    )

    def execute(self, _ctx):
        st = _state()
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        i = it.active_keyframe
        if not 0 <= i < len(it.keyframes):
            return {"CANCELLED"}
        j = i - 1 if self.direction == "UP" else i + 1
        if not 0 <= j < len(it.keyframes):
            return {"CANCELLED"}
        it.keyframes.move(i, j)
        it.active_keyframe = j
        return {"FINISHED"}


# -----------------------
# Playback
# -----------------------

class DRS_OT_Effect_PlayAction(bpy.types.Operator):
    """Play the Action assigned to this Effect entry once (no audio)."""
    bl_idname = "drs.effect_play_action"
    bl_label = "Play (Anim Only)"
    bl_options = {"INTERNAL"}

    action_name: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        act_name = (self.action_name or "").strip()
        if not act_name or act_name == "NONE":
            self.report({"ERROR"}, "No Action set on this Effect entry.")
            return {"CANCELLED"}
        act = bpy.data.actions.get(act_name)
        if not act:
            self.report({"ERROR"}, f"Action '{act_name}' not found.")
            return {"CANCELLED"}

        model = _active_drs_collection(context)
        if not model:
            self.report({"ERROR"}, "Select a model mesh to edit its settings.")
            return {"CANCELLED"}

        arm = _find_armature(model)
        if not arm:
            self.report({"ERROR"}, "No Armature found in active DRSModel_* collection.")
            return {"CANCELLED"}
        _activate_and_bind_action(context, arm, act)

        # push NLA or set as active action and play once
        arm.animation_data_create()
        arm.animation_data.action = act
        # set timeline to action range
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        scene = context.scene
        scene.frame_start, scene.frame_end = f0, f1
        scene.frame_set(f0)
        # trigger playback
        bpy.ops.screen.animation_play()
        return {"FINISHED"}

# -----------------------
# Panel (always visible)
# -----------------------

_asset_library = None
_asset_library_key = None
_resource_items = []  # Keep enum strings alive for Blender's search popup.


def _resource_enum(self, context):
    return _resource_items


def _library(context):
    global _asset_library, _asset_library_key
    from sr_impex.utilities.effect_assets import EffectLibrary
    from sr_impex.blender.asset_preferences import paths
    game,effects=paths(context)
    from pathlib import Path
    if game and not Path(game).is_dir():raise ValueError('Skylords Reborn Folder does not exist: '+game)
    if game and not (Path(game)/'base'/'pak').is_dir() and not (Path(game)/'Mods'/'Unpack').is_dir():
        raise ValueError('Select the Skylords installation folder containing base/pak, rather than the pak folder itself')
    if effects and not Path(effects).is_dir():raise ValueError('Effects Folder does not exist. Select its current location or leave it empty: '+effects)
    key = (game, effects)
    if key != _asset_library_key or _asset_library is None:
        if not any(key):
            raise ValueError('Set the Effects Folder or Skylords Reborn Folder in add-on preferences')
        _asset_library = EffectLibrary(game, effects)
        _asset_library_key = key
    else:_asset_library.refresh()
    return _asset_library


def _selected_variant():
    st = _state()
    if not 0 <= st.active_index < len(st.items):
        raise ValueError('Select an animation entry')
    entry = st.items[st.active_index]
    if not 0 <= entry.active_keyframe < len(entry.keyframes):
        raise ValueError('Select an effect event')
    event = entry.keyframes[entry.active_keyframe]
    if not 0 <= event.active_variant < len(event.variants):
        raise ValueError('Select a resource variant')
    return event, event.variants[event.active_variant]


def _resource_choices(library,sound=False,group='ALL'):
    choices=library.assets({'.snr','.wav','.ogg','.xml'} if sound else {'.fxb'})
    if sound:
        choices=[a for a in choices if not a.name.lower().endswith('.xml') or '/sound/' in ('/'+a.name.replace('\\','/').lower())]
    return [a for a in choices if group=='ALL' or group in resource_groups(a.name)]


class DRS_OT_Effect_RefreshLibrary(bpy.types.Operator):
    """Re-scan on the next resource search after adding or changing assets."""
    bl_idname = 'drs.effect_refresh_library'
    bl_label = 'Refresh Effect Library'

    def execute(self, context):
        global _asset_library, _asset_library_key
        if _asset_library is not None:_asset_library.refresh(force=True)
        else:
            try:_library(context).refresh(force=True)
            except ValueError:pass
        _asset_library = _asset_library_key = None
        _resource_items.clear()
        self.report({'INFO'}, 'Effect library will be refreshed on the next search')
        return {'FINISHED'}


class DRS_OT_Effect_BrowseResource(bpy.types.Operator):
    """Choose an existing effect or sound; creates no new FXB files."""
    bl_idname = 'drs.effect_browse_resource'
    bl_label = 'Choose Effect Resource'
    bl_property = 'resource'
    bl_options = {'UNDO'}
    resource: EnumProperty(items=_resource_enum)  # type: ignore
    target: EnumProperty(items=[('EFFECT','EffectSet',''),('LOCATOR','Locator','')],default='EFFECT',options={'HIDDEN'})  # type: ignore
    locator_uid: StringProperty(options={'HIDDEN'})  # type: ignore
    locator_model: StringProperty(options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        global _resource_items
        try:
            sound=False
            if self.target=='LOCATOR':
                from .locator_editor import selected_fx_item
                model,item=selected_fx_item(context)
                self.locator_uid=item.uid;self.locator_model=str(model.session_uid)
            else:
                key,_=_selected_variant();sound=key.key_type=='0'
            library = _library(context)
            context.window.cursor_set('WAIT')
            group=_state().resource_group
            choices=_resource_choices(library,sound,group)
            _resource_items = [(a.name,a.name.replace('\\','/').rsplit('/',1)[-1]+' â€” '+resource_group_label(a.name),a.name) for a in choices]
            _resource_items.sort(key=lambda row:(resource_group_label(row[0]),row[1].lower()))
            if not _resource_items:
                raise ValueError('No matching resources found in the configured library')
            context.window_manager.invoke_search_popup(self)
            return {'RUNNING_MODAL'}
        except (ValueError, OSError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        finally:
            context.window.cursor_set('DEFAULT')

    def execute(self, context):
        try:
            if self.target=='LOCATOR':
                from .locator_editor import selected_fx_item
                model,variant=selected_fx_item(context)
                if self.locator_uid and (variant.uid!=self.locator_uid or str(model.session_uid)!=self.locator_model):
                    raise ValueError('Locator selection changed; reopen Choose Resource')
            else:_, variant = _selected_variant()
            variant.file = self.resource.replace('\\','/').rsplit('/',1)[-1]
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class DRS_OT_Effect_InspectResource(bpy.types.Operator):
    """Read the selected FXB tree and report its elements and dependencies."""
    bl_idname = 'drs.effect_inspect_resource'
    bl_label = 'Inspect Effect Resource'
    target: EnumProperty(items=[('EFFECT','EffectSet',''),('LOCATOR','Locator','')],default='EFFECT',options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        from sr_impex.utilities.effect_inspection import read_effect, inspect_effect
        try:
            if self.target=='LOCATOR':
                from .locator_editor import selected_fx_item
                _,variant=selected_fx_item(context)
            else:_, variant = _selected_variant()
            asset = _library(context).resolve(variant.file)
            if not asset.name.lower().endswith('.fxb'):
                self.report({'INFO'}, f'Resolved audio resource: {asset.name}')
                return {'FINISHED'}
            report = inspect_effect(read_effect(asset.read()))
            report['resource'] = asset.name
            report['source'] = str(asset.source)
            text = bpy.data.texts.get('Effect Resource Report') or bpy.data.texts.new('Effect Resource Report')
            text.clear()
            text.write(json.dumps(report, indent=2))
            self.report({'INFO'}, f"{sum(report['element_counts'].values())} elements; see Effect Resource Report in Blender's Text Editor")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f'Could not inspect resource: {exc}')
            return {'CANCELLED'}

class DRS_OT_Effect_BuildPreview(bpy.types.Operator):
    """Build this animation's effect preview; use Space to play."""
    bl_idname='drs.effect_build_preview'
    bl_label='Update Effect Preview'
    source: EnumProperty(items=[('EFFECT','EffectSet',''),('LOCATOR','Locators','')],default='EFFECT',options={'HIDDEN'})  # type: ignore

    def execute(self,context):
        global _live_status
        from sr_impex.blender import effect_preview
        try:
            model=_active_drs_collection(context)
            state=_state()
            if not model:raise ValueError('Select a model')
            if self.source=='EFFECT' and state.model_key and state.model_key!=str(model.as_pointer()):
                raise ValueError('Model selection changed; wait for the EffectSet panel to refresh')
            context.window.cursor_set('WAIT')
            _arm_live_preview(context,model,self.source)
            session=_build_editor_preview(context,model)
            _arm_live_preview(context,model,self.source);_live_status='Preview ready'
            self.report({'INFO'},f'Preview ready: {len(session.items)} components, {len(session.strips)} audio cues. Space to play. See Effect Preview Report for limitations.')
            return {'FINISHED'}
        except effect_preview.NoPreviewResources as exc:
            _live_status=str(exc)
            self.report({'INFO'} if exc.expected else {'ERROR'},str(exc))
            return {'FINISHED'} if exc.expected else {'CANCELLED'}
        except Exception as exc:
            _live_status=str(exc)
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        finally:context.window.cursor_set('DEFAULT')


class DRS_OT_Effect_ClearPreview(bpy.types.Operator):
    """Remove only this model's generated previews and audio cues."""
    bl_idname='drs.effect_clear_preview'
    bl_label='Clear Effect Preview'

    def execute(self,context):
        _disarm_live_preview()
        from sr_impex.blender.effect_preview import clear
        model=_active_drs_collection(context)
        if model:clear(context.scene,model)
        return {'FINISHED'}


class DRS_OT_Effect_NormalizeChances(bpy.types.Operator):
    """Scale this event's chances to 100%, preserving their relative proportions."""
    bl_idname='drs.effect_normalize_chances'
    bl_label='Normalize to 100%'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        from sr_impex.utilities.effect_tracks import normalized_chances
        try:
            key,_=_selected_variant()
            chances=normalized_chances([v.weight for v in key.variants])
            for variant,chance in zip(key.variants,chances):variant.weight=chance
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


def _draw_effectset_ui(layout, context):
    st = _state()
    col_ui = layout.column(align=True)

    model = _active_drs_collection(context)
    if not model:
        box = col_ui.box()
        box.label(text="Select a model mesh to edit its settings.", icon="INFO")
        return
    if st.model_key!=str(model.as_pointer()):
        col_ui.label(text='Loading this model\'s EffectSetâ€¦',icon='TIME')
        return
    if not st.items:
        col_ui.label(text='This model has no animation effect events.',icon='INFO')
        col_ui.operator('drs.effect_add',text='Add Animation Effects',icon='ADD')
        try:locators=json.loads(model.get('CDrwLocatorListJSON','{}')).get('locators',[])
        except (TypeError,ValueError):locators=[]
        if any(r.get('class_id') in (6,8) and r.get('file','').lower().endswith('.fxb') for r in locators):
            row=col_ui.row(align=True)
            row.operator('drs.effect_build_preview',text='Update Preview',icon='FILE_REFRESH').source='EFFECT'
            row.prop(st,'preview_audio')
        return

    # Header actions
    hdr = col_ui.row(align=True)
    hdr.operator("drs.effect_save", text="Save", icon="CHECKMARK")
    hdr.operator("drs.effect_reload", text="Reset", icon="FILE_REFRESH")
    preview=col_ui.row(align=True)
    preview.operator('drs.effect_build_preview',text='Update Preview',icon='FILE_REFRESH').source='EFFECT'
    preview.operator('drs.effect_clear_preview',text='',icon='X')
    preview.prop(st,'preview_audio')
    col_ui.prop(st,'preview_live')
    col_ui.prop(st,'preview_variant')
    if _live_target==(context.scene.as_pointer(),model.as_pointer()) and _live_status:
        col_ui.label(text=_live_status,icon='INFO')

    # Data available â†’ draw editor UI
    left = col_ui.column()

    left.template_list("DRS_UL_Effects", "", st, "items", st, "active_index", rows=min(5,max(2,len(st.items))))
    row = left.row(align=True)
    row.operator("drs.effect_add", text="", icon="ADD")
    row.operator("drs.effect_remove", text="", icon="REMOVE")
    right = col_ui.column()

    if 0 <= st.active_index < len(st.items):
        it = st.items[st.active_index]
        box = right.box()
        box.use_property_split = True
        box.use_property_decorate = False
        box.prop(it, "action", text="Action")

        # Keyframes
        kbox = box.box()
        head = kbox.row(align=True)
        head.label(text="Keyframes")
        head.operator("drs.effect_key_add", text="", icon="ADD")
        head.operator("drs.effect_key_remove", text="", icon="REMOVE")

        if len(it.keyframes) == 0:
            kbox.label(text="No keyframes yet.", icon="INFO")
        else:
            # list + controls
            row = kbox.row(align=True)
            row.template_list(
                "DRS_UL_EffectKeyframes", "", it, "keyframes", it, "active_keyframe", rows=5
            )
            col_btns = row.column(align=True)
            col_btns.operator("drs.effect_key_move", text="", icon="TRIA_UP").direction = "UP"
            col_btns.operator("drs.effect_key_move", text="", icon="TRIA_DOWN").direction = "DOWN"

            # details pane for the selected keyframe
            idx = max(0, min(it.active_keyframe, len(it.keyframes) - 1))
            k = it.keyframes[idx]

            fld = kbox.box()
            fld.use_property_split = True
            fld.use_property_decorate = False
            fld.prop(k, "time")
            fld.prop(k, "key_type", text="Type")
            if k.key_type=='0':
                fld.prop(k, "min_falloff")
                fld.prop(k, "max_falloff")
                fld.prop(k, "volume")
                fld.prop(k, "pitch_min")
                fld.prop(k, "pitch_max")
            if k.key_type in {"3", "4"}:
                fld.prop(k, "offset", index=0, text="Fade Duration (s)")
            elif k.key_type in {'1','2'}:
                fld.prop(k, "offset")
            fld.prop(k, "interruptable")
            fld.prop(k, "condition",text='Stored Condition (Export Only)')

            vbox = kbox.box()
            head = vbox.row(align=True)
            head.label(text="Variants")
            head.operator("drs.effect_variant_add", text="", icon="ADD")
            head.operator("drs.effect_variant_remove", text="", icon="REMOVE")
            vbox.template_list("DRS_UL_EffectVariants", "", k, "variants", k, "active_variant", rows=3)
            total=sum(v.weight for v in k.variants)
            if total<100:vbox.label(text=f'{100-total}% chance of silence / no FX',icon='INFO')
            elif total>100:vbox.label(text='Above 100%: later variants may be unreachable',icon='ERROR')
            if total!=100 and len(k.variants):vbox.operator('drs.effect_normalize_chances')

            if 0 <= k.active_variant < len(k.variants):
                v = k.variants[k.active_variant]
                det = vbox.box()
                det.use_property_split = True
                det.use_property_decorate = False
                det.prop(v, "file")
                tools = det.row(align=True)
                tools.operator('drs.effect_selector', text='Effect Selector', icon='VIEWZOOM').target='EFFECT'
                det.prop(v, "weight")


class DRS_PT_EffectSetDock(bpy.types.Panel):
    """Sidepanel version in View3D (N-panel), always visible with hint if no DRS model."""
    bl_label = "Effect Set Editor"
    bl_idname = "DRS_PT_EffectSetDock"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 30

    def draw(self, context):
        _draw_effectset_ui(self.layout, context)


# -----------------------
# Registration
# -----------------------

_classes = (
    EffVariantPG,
    EffKeyframePG,
    EffEntryPG,
    EffState,
    DRS_UL_Effects,
    DRS_UL_EffectVariants,
    DRS_UL_EffectKeyframes,
    DRS_OT_Effect_Add,
    DRS_OT_Effect_Remove,
    DRS_OT_Keyframe_Add,
    DRS_OT_Keyframe_Remove,
    DRS_OT_Keyframe_Move,
    DRS_OT_Variant_Add,
    DRS_OT_Variant_Remove,
    DRS_OT_Effect_Save,
    DRS_OT_Effect_Reload,
    DRS_OT_Effect_BrowseResource,
    DRS_OT_Effect_InspectResource,
    DRS_OT_Effect_RefreshLibrary,
    DRS_OT_Effect_BuildPreview,
    DRS_OT_Effect_ClearPreview,
    DRS_OT_Effect_NormalizeChances,
    DRS_PT_EffectSetDock,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.drs_effect_state = PointerProperty(type=EffState)
    from sr_impex.blender import effect_preview
    effect_preview.register()
    from sr_impex.blender import effect_selector
    effect_selector.register()
    if not bpy.app.timers.is_registered(_sync_selected_model):
        bpy.app.timers.register(_sync_selected_model,first_interval=.1,persistent=True)
    if not bpy.app.timers.is_registered(_refresh_live_preview):
        bpy.app.timers.register(_refresh_live_preview,first_interval=.2,persistent=True)

def unregister():
    from sr_impex.blender import effect_selector
    effect_selector.unregister()
    from sr_impex.blender import effect_preview
    effect_preview.unregister()
    if bpy.app.timers.is_registered(_sync_selected_model):bpy.app.timers.unregister(_sync_selected_model)
    if bpy.app.timers.is_registered(_refresh_live_preview):bpy.app.timers.unregister(_refresh_live_preview)
    _disarm_live_preview()
    _model_drafts.clear()
    global _asset_library, _asset_library_key
    _asset_library = _asset_library_key = None
    _resource_items.clear()
    del bpy.types.WindowManager.drs_effect_state
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
