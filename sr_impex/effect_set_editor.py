# effect_set_editor.py
# Always-visible EffectSet editor (Collection Properties).
# Shows an info message if the selected collection is not a DRSModel_* one.

from __future__ import annotations
import json
import zlib
import os
import pathlib
from os.path import dirname, realpath
from pathlib import Path
from typing import Dict, List, Optional
from itertools import chain

import bpy
from bpy.props import (
    StringProperty, IntProperty, BoolProperty, FloatProperty,
    FloatVectorProperty, EnumProperty, CollectionProperty, PointerProperty
)

# Import your current DRS defs (latest uploaded)
from .drs_definitions import (
    EffectSet as DRS_EffectSet,
    SkelEff as DRS_SkelEff,
    Keyframe as DRS_Keyframe,
    Variant as DRS_Variant,
    SoundHeader,
    SoundFile,
    SoundContainer,
    AdditionalSoundContainer,
    SoundType,
)

from .drs_resolvers import resolve_action_from_blob_name
from .debug_asset_library import sound_candidates_for_base, is_sound_cached

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

    try:
        ui = act.get("ui_name", None)
    except Exception:
        ui = None
    if ui:
        return str(ui)

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

    return short


def _action_label_from_id(action_id: str) -> str:
    if not action_id or action_id == "NONE":
        return "<None>"
    act = bpy.data.actions.get(action_id)
    if not act:
        return action_id
    return _ensure_action_name_props(act)


def _actions_enum(_self, _ctx):
    acts = bpy.data.actions
    items = [("NONE", "<None>", "")]
    pairs = []
    for act in acts:
        ident = act.name
        label = _ensure_action_name_props(act)
        pairs.append((ident, label))
    pairs.sort(key=lambda p: p[1].lower())
    items.extend((ident, label, "") for ident, label in pairs)
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
    # Make sure the hidden members exist but keep them out of the UI
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
    col = None
    ctx = context or bpy.context
    col = getattr(ctx, "collection", None)
    if isinstance(col, bpy.types.Collection) and col.name.startswith("DRSModel_"):
        return col
    alc = ctx.view_layer.active_layer_collection.collection if ctx.view_layer else None
    if alc and alc.name.startswith("DRSModel_"):
        return alc
    return None


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
    weight: IntProperty(name="Weight", default=100, min=0, max=255)  # type: ignore
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
            ("0", "Audio (snr/wav)", ""),
            ("1", "FX1 (fxb)", ""),
            ("2", "FX2 (fxb)", ""),
            ("3", "Permanent FX1 (fxb)", ""),
            ("4", "Permanent FX2 (fxb)", ""),
        ],
        default="0",
    )  # type: ignore
    min_falloff: FloatProperty(name="Min Falloff", default=0.0)  # type: ignore
    max_falloff: FloatProperty(name="Max Falloff", default=0.0)  # type: ignore
    volume: FloatProperty(name="Volume", default=1.0)  # type: ignore
    pitch_min: FloatProperty(name="Pitch Min", default=0.0)  # type: ignore
    pitch_max: FloatProperty(name="Pitch Max", default=0.0)  # type: ignore
    offset: FloatVectorProperty(name="Offset", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")  # type: ignore
    interruptable: BoolProperty(name="Interruptable", default=False)  # type: ignore
    # Serialized as 'uk' in your defs when type not in [10,11]. We keep it as 'condition' UI:
    condition: IntProperty(name="Condition", default=-1, min=-1, max=255)  # type: ignore

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


class EffEntryPG(bpy.types.PropertyGroup):
    action: EnumProperty(name="Action", items=_actions_enum)  # type: ignore
    raw_ska: StringProperty(default="", options={"HIDDEN"})  # type: ignore
    keyframes: CollectionProperty(type=EffKeyframePG)  # type: ignore
    active_keyframe: IntProperty(default=0)  # type: ignore

    def to_dict(self) -> Dict:
        ska = self.raw_ska or _norm_ska_name(self.action if self.action and self.action != "NONE" else "")
        return {"action": ska, "keyframes": [k.to_dict() for k in self.keyframes]}

    def from_dict(self, d: dict):
        ska = d.get("action", "") or ""
        self.raw_ska = ska

        # Try to resolve to an existing Action
        act = resolve_action_from_blob_name(ska)
        self.action = act if act else "NONE"

        self.keyframes.clear()
        for kd in d.get("keyframes", []) or []:
            k = self.keyframes.add()
            k.from_dict(kd)


class EffState(bpy.types.PropertyGroup):
    items: CollectionProperty(type=EffEntryPG)  # type: ignore
    active_index: IntProperty(default=0)  # type: ignore


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


def _state_to_blob(st: EffState) -> Dict:
    return {
        "effects": [it.to_dict() for it in st.items],
        # type/checksum/unknown* are preserved in _write_blob
    }


# -----------------------
# DRS <-> Blob
# -----------------------

def effectset_to_blob(eff: DRS_EffectSet) -> Dict:
    blob = {
        "type": int(getattr(eff, "type", 12) or 12),
        "checksum_length": int(getattr(eff, "checksum_length", 0)),
        "checksum": getattr(eff, "checksum", "") or "",
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
                "condition": int(getattr(kf, "uk", -1) if getattr(kf, "uk", None) is not None else -1),
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


def blob_to_effectset(blob: Dict) -> DRS_EffectSet:
    eff = DRS_EffectSet()
    eff.type = int(blob.get("type", 12) or 12)
    eff.checksum = str(blob.get("checksum", ""))
    eff.checksum_length = len(eff.checksum)

    eff.skel_effekts = []
    for ed in (blob.get("effects") or []):
        se = DRS_SkelEff()
        ska = _norm_ska_name(ed.get("action", "") or "")
        se.name = ska
        se.length = len(se.name)

        se.keyframes = []
        for kd in (ed.get("keyframes") or []):
            kf = DRS_Keyframe()
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
            kf.uk = int(-1 if cond is None else cond)

            kf.variants = []
            for vd in (kd.get("variants") or []):
                name = (vd.get("name") or "").strip()
                if not name:
                    continue
                v = DRS_Variant()
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
            sfd_sh = SoundHeader()
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
                sfd_sh = SoundHeader()
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
    
    eff.number_additional_Sounds = len(eff.additional_sounds)
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
    bl_idname = "drs.effect_key_add"
    bl_label = "Add Keyframe"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
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
    bl_idname = "drs.effect_key_remove"
    bl_label = "Remove Keyframe"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        i = it.active_keyframe
        if 0 <= i < len(it.keyframes):
            it.keyframes.remove(i)
            it.active_keyframe = min(i, len(it.keyframes) - 1)
        return {"FINISHED"}


class DRS_OT_Variant_Add(bpy.types.Operator):
    bl_idname = "drs.effect_variant_add"
    bl_label = "Add Variant"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        if not (0 <= it.active_keyframe < len(it.keyframes)):
            return {"CANCELLED"}
        k = it.keyframes[it.active_keyframe]
        v = k.variants.add()
        v.weight = 100
        v.file = ""
        k.active_variant = len(k.variants) - 1
        return {"FINISHED"}


class DRS_OT_Variant_Remove(bpy.types.Operator):
    bl_idname = "drs.effect_variant_remove"
    bl_label = "Remove Variant"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        if not (0 <= it.active_keyframe < len(it.keyframes)):
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
            self.report({"ERROR"}, "Select a DRSModel_* collection in the Outliner.")
            return {"CANCELLED"}
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
            self.report({"ERROR"}, "Select a DRSModel_* collection.")
            return {"CANCELLED"}
        _blob_to_state(_state(), col)
        return {"FINISHED"}


class DRS_OT_Keyframe_Move(bpy.types.Operator):
    bl_idname = "drs.effect_key_move"
    bl_label = "Move Keyframe"
    bl_options = {"INTERNAL"}

    direction: bpy.props.EnumProperty(
        items=[("UP","Up",""), ("DOWN","Down","")], default="UP"
    )

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
            return {"CANCELLED"}
        it = st.items[st.active_index]
        i = it.active_keyframe
        if not (0 <= i < len(it.keyframes)):
            return {"CANCELLED"}
        j = i - 1 if self.direction == "UP" else i + 1
        if not (0 <= j < len(it.keyframes)):
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
            self.report({"ERROR"}, "Select a DRSModel_* collection.")
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

def _draw_effectset_ui(layout, context):
    st = _state()
    col_ui = layout.column(align=True)

    # Header actions
    hdr = col_ui.row(align=True)
    hdr.operator("drs.effect_save", text="Save", icon="CHECKMARK")
    hdr.operator("drs.effect_reload", text="Reset", icon="FILE_REFRESH")

    model = _active_drs_collection(context)
    if not model:
        box = col_ui.box()
        box.label(text="Select a DRSModel_* collection to edit EffectSet.", icon="INFO")
        box.label(text="(The editor is always visible here for convenience.)")
        return

    # Data available → draw editor UI
    split = col_ui.split(factor=0.42)
    left = split.column()
    right = split.column()

    left.template_list("DRS_UL_Effects", "", st, "items", st, "active_index", rows=10)
    row = left.row(align=True)
    row.operator("drs.effect_add", text="", icon="ADD")
    row.operator("drs.effect_remove", text="", icon="REMOVE")

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
            it.active_keyframe = idx
            k = it.keyframes[idx]

            fld = kbox.box()
            fld.use_property_split = True
            fld.use_property_decorate = False
            fld.prop(k, "time")
            fld.prop(k, "key_type", text="Type")
            fld.prop(k, "min_falloff")
            fld.prop(k, "max_falloff")
            # fld.prop(k, "volume") # Use 3D audio volume
            fld.prop(k, "pitch_min")
            fld.prop(k, "pitch_max")
            fld.prop(k, "offset")
            fld.prop(k, "interruptable")
            fld.prop(k, "condition")

            vbox = kbox.box()
            head = vbox.row(align=True)
            head.label(text="Variants")
            head.operator("drs.effect_variant_add", text="", icon="ADD")
            head.operator("drs.effect_variant_remove", text="", icon="REMOVE")
            vbox.template_list("DRS_UL_EffectVariants", "", k, "variants", k, "active_variant", rows=3)
            
            if 0 <= k.active_variant < len(k.variants):
                v = k.variants[k.active_variant]
                det = vbox.box()
                det.use_property_split = True
                det.use_property_decorate = False
                det.prop(v, "file")
                det.prop(v, "weight")


class DRS_PT_EffectSetDock(bpy.types.Panel):
    """Sidepanel version in View3D (N-panel), always visible with hint if no DRS model."""
    bl_label = "EffectSet"
    bl_idname = "DRS_PT_EffectSetDock"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"

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
    DRS_PT_EffectSetDock,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.drs_effect_state = PointerProperty(type=EffState)

def unregister():
    del bpy.types.WindowManager.drs_effect_state
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)