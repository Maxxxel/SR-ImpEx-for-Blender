# animation_set_editor.py
# Compact AnimationSet editor as subpanels under the Locator editor panel (Properties ▶ Collection).
# Blender 4.x, no external deps.

from __future__ import annotations
import json
import uuid
import random
from typing import Dict, Optional
from mathutils import Vector, Matrix
import bpy

from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    FloatVectorProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
)

# ---------------------------------------------------------------------------
# Import definitions: VIS_JOB_MAP comes from your drs_definitions.py
# ---------------------------------------------------------------------------

from .abilities import (
    must_have_abilities,
    situational_abilities,
    addtional_abilities,
)
from .animation_utils import assign_action_compat
from .drs_definitions import VIS_JOB_MAP

# Build a static enum list at import time (identifier is the numeric id as string)
VIS_JOB_ENUM = [
    (str(k), f"{VIS_JOB_MAP.get(k, 'Unknown')} ({k})", "")
    for k in sorted(VIS_JOB_MAP.keys())
]
VIS_JOB_DEFAULT = VIS_JOB_ENUM[0][0] if VIS_JOB_ENUM else "0"

MARKER_ARROW_PREFIX = "DRS_Marker_"
MARKER_PROP_KEY = "DRS_MARKER_ID"

ANIM_BLOB_KEY = "AnimationSetJSON"
PARENT_LOCATOR_PANEL_ID = (
    "DRS_PT_LocatorEditorProps"  # must match the Locator editor panel id
)

# ---------------------------------------------------------------------------
# Active model / armature helpers
# ---------------------------------------------------------------------------


import random

UINT32_MAX = 0xFFFFFFFF


def _try_int(x):
    try:
        return int(x)
    except Exception:
        return None


def _is_uint32(n: int) -> bool:
    return isinstance(n, int) and 0 <= n <= UINT32_MAX


def _collect_marker_uints(st) -> set[int]:
    ids = set()
    for ms in st.marker_sets:
        iv = _try_int(getattr(ms, "animation_marker_id", "0"))
        if _is_uint32(iv):
            ids.add(iv)
    return ids


def _alloc_marker_uint(st) -> int:
    used = _collect_marker_uints(st)
    while True:
        nid = random.getrandbits(32)  # full 32-bit
        if nid not in used:
            return nid


def _on_marker_id_changed(self, _ctx):
    s = getattr(self, "animation_marker_id", "")
    # keep only digits; empty → "0"
    s2 = "".join(ch for ch in str(s) if ch.isdigit())
    if s2 == "":
        s2 = "0"
    # clamp to uint32
    iv = _try_int(s2)
    if iv is None or iv < 0:
        s2 = "0"
    else:
        if iv > UINT32_MAX:
            s2 = str(UINT32_MAX)
    if s2 != s:
        self.animation_marker_id = s2


def _active_drs_collection_from_props(context) -> Optional[bpy.types.Collection]:
    col = getattr(context, "collection", None)
    if (
        col
        and isinstance(col, bpy.types.Collection)
        and col.name.startswith("DRSModel_")
    ):
        return col
    return None


def _has_armature(col: Optional[bpy.types.Collection]) -> bool:
    if not col:
        return False

    def visit(c: bpy.types.Collection) -> bool:
        for o in c.objects:
            if o.type == "ARMATURE":
                return True
        for ch in c.children:
            if visit(ch):
                return True
        return False

    return visit(col)


def _active_drs_collection_with_armature(context) -> Optional[bpy.types.Collection]:
    col = getattr(context, "collection", None)
    if (
        col
        and isinstance(col, bpy.types.Collection)
        and col.name.startswith("DRSModel_")
        and _has_armature(col)
    ):
        return col

    print("No active DRS collection with armature found.")
    return None


def _actions_enum(_self=None, _context=None):
    # Always include a sentinel "(none)" option
    items = [("NONE", "(none)", "No action")]
    if bpy.data.actions:
        items.extend((a.name, a.name, "") for a in bpy.data.actions)
    return items


def _find_game_orientation(root: bpy.types.Collection) -> Optional[bpy.types.Object]:
    """Find 'GameOrientation' object anywhere under this DRS model collection."""
    target = "GameOrientation"

    def visit(c: bpy.types.Collection):
        for o in c.objects:
            if o.name == target:
                return o
        for ch in c.children:
            r = visit(ch)
            if r:
                return r
        return None

    return visit(root)


def _ensure_markers_collection(root: bpy.types.Collection) -> bpy.types.Collection:
    """Ensure a subcollection to host debug marker arrows."""
    name = "DRSMarkers"
    if name in root.children:
        # name collision can happen; fall back to search
        for ch in root.children:
            if ch.name == name:
                return ch
    # create once
    col = bpy.data.collections.get(name)
    if not col or col.name_full.startswith("Scene Collection"):
        col = bpy.data.collections.new(name)
    if col.name not in [c.name for c in root.children]:
        root.children.link(col)
    return col


def _iter_objects_recursive(col: bpy.types.Collection):
    for o in col.objects:
        yield o
    for ch in col.children:
        yield from _iter_objects_recursive(ch)


def _object_by_marker_id(
    root: bpy.types.Collection, marker_id: str
) -> Optional[bpy.types.Object]:
    want = str(marker_id)
    for o in _iter_objects_recursive(root):
        if MARKER_PROP_KEY in o.keys():
            if str(o.get(MARKER_PROP_KEY)) == want:
                return o
    return None


def _frame_from_time(action: bpy.types.Action, t: float) -> tuple[int, float]:
    """Return (frame, subframe) without rounding. t∈[0,1] = normalized; else absolute."""
    f0, f1 = action.frame_range
    span = max(1.0, (f1 - f0))
    f = (f0 + t * span) if 0.0 <= t <= 1.0 else float(t)
    base = int(f)  # floor
    return base, float(f - base)


def _upsert_marker_arrow(
    model: bpy.types.Collection,
    marker_id: str,
    pos: Vector,
    direction: Vector,
) -> bpy.types.Object:
    """
    Create or update a SINGLE_ARROW Empty at GameOrientation * (pos, dir).
    Arrow local +Y is considered 'forward'.
    """
    from mathutils import Quaternion

    go = _find_game_orientation(model)
    # Build game-space rotation: by convention, arrow local +Y is forward.
    # If the marker direction is non-zero, point the arrow *along where it goes*,
    # i.e. away from the unit ⇒ use the NEGATED direction. If zero, keep +Y.
    dir_input = Vector(direction) if direction is not None else Vector((0.0, 0.0, 0.0))
    base = Vector((0.0, 1.0, 0.0))
    if dir_input.length < 1e-8:
        rot_q = Quaternion()  # identity → arrow keeps +Y forward
    else:
        dir_v = dir_input.normalized()
        rot_q: Quaternion = base.rotation_difference(-dir_v)

    m_game = rot_q.to_matrix().to_4x4()
    m_game.translation = Vector(pos)

    # Convert to world using GameOrientation if available
    if go:
        m_world = go.matrix_world @ m_game
    else:
        m_world = m_game

    # Reuse existing object or create a new one
    obj = _object_by_marker_id(model, marker_id)
    if not obj:
        obj = bpy.data.objects.new(f"{MARKER_ARROW_PREFIX}{marker_id}", None)
        obj.empty_display_type = "SINGLE_ARROW"
        obj.empty_display_size = 0.25
        obj[MARKER_PROP_KEY] = str(marker_id)
        # link to markers subcollection
        dst = _ensure_markers_collection(model)
        dst.objects.link(obj)

    # Parent to GameOrientation for consistent game-space organization
    if go:
        obj.parent = go
        obj.parent_type = "OBJECT"
        obj.matrix_parent_inverse = go.matrix_world.inverted()
    else:
        obj.parent = None

    # Apply world transform
    obj.matrix_world = m_world

    # Keep UI calm
    obj.select_set(False)
    if bpy.context.view_layer.objects.active is obj:
        bpy.context.view_layer.objects.active = None

    return obj


# --- Playback helpers: play once from start..end and auto-stop ----------------
_playback_state = {"handler": None, "end_frame": None}


def _stop_preview_playback():
    """Stop animation playback and remove our handler, if present."""
    if _playback_state.get("handler"):
        try:
            bpy.app.handlers.frame_change_post.remove(_playback_state["handler"])
        # pylint: disable=broad-exception-caught
        except Exception:
            pass
        _playback_state["handler"] = None
    _playback_state["end_frame"] = None
    # Toggle off if currently playing
    try:
        if bpy.context.screen and bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
    # pylint: disable=broad-exception-caught
    except Exception:
        pass


def _frame_stop_handler(scene, _depsgraph):
    """Auto-stop when we reach/past the requested end frame."""
    endf = _playback_state.get("end_frame")
    if endf is not None and scene.frame_current >= endf:
        _stop_preview_playback()


# ---------------------------------------------------------------------------
# Blob I/O
# ---------------------------------------------------------------------------


def _empty_blob() -> Dict:
    return {
        "default_run_speed": 5.0,
        "default_walk_speed": 2.0,
        "mode_change_type": 0,
        "hovering_ground": 0,
        "fly_bank_scale": 0.0,
        "fly_accel_scale": 0.0,
        "fly_hit_scale": 0.0,
        "align_to_terrain": 0,
        "mode_keys": [],
        "marker_sets": [],
    }


def _read_anim_blob(col: bpy.types.Collection) -> Dict:
    data = col.get(ANIM_BLOB_KEY)
    if not data:
        return _empty_blob()
    try:
        b = json.loads(data)
        # ensure keys
        b.setdefault("mode_keys", [])
        b.setdefault("marker_sets", [])
        return b
    # pylint: disable=broad-exception-caught
    except Exception:
        return _empty_blob()


def _write_anim_blob(col: bpy.types.Collection, blob: Dict) -> None:
    col[ANIM_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# PropertyGroups (state in UI)
# ---------------------------------------------------------------------------


class AbilityItemPG(bpy.types.PropertyGroup):
    name: StringProperty()  # type: ignore
    category: StringProperty()  # type: ignore
    description: StringProperty()  # type: ignore
    marker: BoolProperty(default=False)  # type: ignore
    animations_json: StringProperty()  # type: ignore
    selected: BoolProperty(default=False)  # type: ignore
    available: BoolProperty(default=True)  # type: ignore


class AnimVariantPG(bpy.types.PropertyGroup):
    weight: IntProperty(name="Weight", default=100, min=0, max=100)  # type: ignore
    start: FloatProperty(name="Start", default=0.0, min=0.0, max=1.0)  # type: ignore
    end: FloatProperty(name="End", default=1.0, min=0.0, max=1.0)  # type: ignore
    allows_ik: BoolProperty(name="Allows IK", default=True)  # type: ignore
    file: EnumProperty(name="Action", items=_actions_enum)  # type: ignore

    def to_dict(self) -> Dict:
        return {
            "weight": int(self.weight),
            "start": float(self.start),
            "end": float(self.end),
            "allows_ik": 1 if self.allows_ik else 0,
            "file": ("" if self.file == "NONE" else self.file),
        }

    def from_dict(self, d: Dict):
        self.weight = int(d.get("weight", 100))
        self.start = float(d.get("start", 0.0))
        self.end = float(d.get("end", 1.0))
        self.allows_ik = bool(int(d.get("allows_ik", 1)))
        f = d.get("file", "")
        self.file = "NONE" if not f else f


class ModeKeyPG(bpy.types.PropertyGroup):
    # Store enum string of id; convert to int on save
    vis_job: EnumProperty(name="VisJob", items=VIS_JOB_ENUM, default=VIS_JOB_DEFAULT)  # type: ignore
    variants: CollectionProperty(type=AnimVariantPG)  # type: ignore
    active_variant: IntProperty(default=0)  # type: ignore

    def to_dict(self) -> Dict:
        try:
            vj = int(self.vis_job)
        # pylint: disable=broad-exception-caught
        except Exception:
            vj = 0
        return {"vis_job": vj, "variants": [v.to_dict() for v in self.variants]}

    def from_dict(self, d: Dict):
        self.vis_job = str(int(d.get("vis_job", 0)))
        self.variants.clear()
        for v in d.get("variants", []):
            it: AnimVariantPG = self.variants.add()
            it.from_dict(v)


class MarkerPG(bpy.types.PropertyGroup):
    is_spawn_animation: BoolProperty(name="Spawn Animation", default=False)  # type: ignore
    time: FloatProperty(name="Time", default=0.0)  # type: ignore
    direction: FloatVectorProperty(name="Direction", size=3, default=(0.0, 0.0, 0.0))  # type: ignore
    position: FloatVectorProperty(name="Position", size=3, default=(0.0, 0.0, 0.0))  # type: ignore

    def to_dict(self) -> Dict:
        return {
            "is_spawn_animation": 1 if self.is_spawn_animation else 0,
            "time": float(self.time),
            "direction": list(self.direction),
            "position": list(self.position),
        }

    def from_dict(self, d: Dict):
        self.is_spawn_animation = bool(int(d.get("is_spawn_animation", 0)))
        self.time = float(d.get("time", 0.0))
        self.direction = d.get("direction", [0.0, 0.0, 0.0])
        self.position = d.get("position", [0.0, 0.0, 0.0])


class MarkerSetPG(bpy.types.PropertyGroup):
    anim_id: EnumProperty(
        name="VisJob", items=VIS_JOB_ENUM, default=VIS_JOB_DEFAULT
    )  # type: ignore
    file: EnumProperty(name="Action", items=_actions_enum)  # type: ignore
    animation_marker_id: StringProperty(
        name="Marker ID", default="0", update=_on_marker_id_changed
    )  # type: ignore
    markers: CollectionProperty(type=MarkerPG)  # type: ignore

    def ensure_id(self):
        # If empty or invalid, assign a fresh full 32-bit uint
        iv = _try_int(self.animation_marker_id)
        if not _is_uint32(iv):
            self.animation_marker_id = str(
                _alloc_marker_uint(bpy.context.window_manager.drs_anim_state)
            )

    def to_dict(self) -> Dict:
        self.ensure_id()
        if not self.markers:
            m: MarkerPG = self.markers.add()
            m.from_dict({})
        m0 = self.markers[0]
        try:
            anim_id_int = int(self.anim_id)
        # pylint: disable=broad-exception-caught
        except Exception:
            anim_id_int = 0
        iv = _try_int(self.animation_marker_id)
        iv = iv if _is_uint32(iv) else 0
        return {
            "anim_id": anim_id_int,
            "file": ("" if self.file == "NONE" else self.file),
            "animation_marker_id": iv,  # JSON stores true integer
            "markers": [m0.to_dict()],
        }

    def from_dict(self, d: Dict):
        self.anim_id = str(int(d.get("anim_id", 0)))
        f = d.get("file", "")
        self.file = "NONE" if not f else f
        # Accept legacy string UUIDs by regenerating a numeric id
        raw = d.get("animation_marker_id", 0)
        iv = raw if isinstance(raw, int) else _try_int(raw)
        if _is_uint32(iv):
            self.animation_marker_id = str(iv)
        else:
            self.animation_marker_id = "0"  # will be fixed by ensure_id/use-sites
        self.markers.clear()
        m: MarkerPG = self.markers.add()
        ms = d.get("markers", [])
        m.from_dict(ms[0] if ms else {})


class AnimSetState(bpy.types.PropertyGroup):
    # Top-level:
    default_run_speed: FloatProperty(name="Default Run Speed", default=5.0)  # type: ignore
    default_walk_speed: FloatProperty(name="Default Walk Speed", default=2.0)  # type: ignore
    mode_change_type: EnumProperty(name="Mode Change", items=[("0", "0", ""), ("1", "1", "")], default="0")  # type: ignore
    hovering_ground: BoolProperty(name="Hovering Ground", default=False)  # type: ignore
    fly_bank_scale: FloatProperty(name="Fly Bank Scale", default=0.0, min=0.0, max=1.0)  # type: ignore
    fly_accel_scale: FloatProperty(name="Fly Accel Scale", default=0.0, min=0.0, max=1.0)  # type: ignore
    fly_hit_scale: FloatProperty(name="Fly Hit Scale", default=0.0, min=0.0, max=1.0)  # type: ignore
    align_to_terrain: BoolProperty(name="Align To Terrain", default=False)  # type: ignore

    # Collections:
    mode_keys: CollectionProperty(type=ModeKeyPG)  # type: ignore
    active_mode_key: IntProperty(default=0)  # type: ignore

    marker_sets: CollectionProperty(type=MarkerSetPG)  # type: ignore
    active_marker_set: IntProperty(default=0)  # type: ignore

    # model reference
    model: PointerProperty(type=bpy.types.Collection)  # type: ignore


def _state() -> AnimSetState:
    return bpy.context.window_manager.drs_anim_state


# ---------------------------------------------------------------------------
# Conversions: state <-> blob
# ---------------------------------------------------------------------------


def _state_to_blob(st: AnimSetState) -> Dict:
    return {
        "default_run_speed": float(st.default_run_speed),
        "default_walk_speed": float(st.default_walk_speed),
        "mode_change_type": int(st.mode_change_type),
        "hovering_ground": 1 if st.hovering_ground else 0,
        "fly_bank_scale": float(st.fly_bank_scale),
        "fly_accel_scale": float(st.fly_accel_scale),
        "fly_hit_scale": float(st.fly_hit_scale),
        "align_to_terrain": 1 if st.align_to_terrain else 0,
        "mode_keys": [k.to_dict() for k in st.mode_keys],
        "marker_sets": [m.to_dict() for m in st.marker_sets],
    }


def _blob_to_state(st: AnimSetState, blob: Dict) -> None:
    st.default_run_speed = float(blob.get("default_run_speed", 5.0))
    st.default_walk_speed = float(blob.get("default_walk_speed", 2.0))
    st.mode_change_type = str(int(blob.get("mode_change_type", 0)))
    st.hovering_ground = bool(int(blob.get("hovering_ground", 0)))
    st.fly_bank_scale = float(blob.get("fly_bank_scale", 0.0))
    st.fly_accel_scale = float(blob.get("fly_accel_scale", 0.0))
    st.fly_hit_scale = float(blob.get("fly_hit_scale", 0.0))
    st.align_to_terrain = bool(int(blob.get("align_to_terrain", 0)))

    st.mode_keys.clear()
    for k in blob.get("mode_keys", []):
        mk: ModeKeyPG = st.mode_keys.add()
        mk.from_dict(k)

    st.marker_sets.clear()
    for m in blob.get("marker_sets", []):
        ms: MarkerSetPG = st.marker_sets.add()
        ms.from_dict(m)


# ---------------------------------------------------------------------------
# UI Lists
# ---------------------------------------------------------------------------


class DRS_UL_AbilityPicker(bpy.types.UIList):
    bl_idname = "DRS_UL_AbilityPicker"

    def draw_item(
        self,
        _ctx,
        layout,
        _data,
        item: AbilityItemPG,
        _icon,
        _active_data,
        _active_propname,
        _index,
    ):
        row = layout.row(align=True)
        row.enabled = bool(item.available)  # <- disable if already present
        row.prop(item, "selected", text="")
        row.label(text=item.name)
        tag = item.category if item.available else "Already in model"
        row.label(text=tag, icon="OUTLINER")


class DRS_UL_ModeKeys(bpy.types.UIList):
    bl_idname = "DRS_UL_ModeKeys"

    def draw_item(self, _ctx, layout, _data, item: ModeKeyPG, _icon, _active, _flt):
        try:
            key = int(item.vis_job)
        # pylint: disable=broad-exception-caught
        except Exception:
            key = 0
        layout.label(text=f"{VIS_JOB_MAP.get(key, 'Unknown')} ({key})")


class DRS_UL_Variants(bpy.types.UIList):
    bl_idname = "DRS_UL_Variants"

    def draw_item(self, _ctx, layout, _data, item: AnimVariantPG, _icon, _active, _flt):
        lab = "(no action)" if item.file == "NONE" else item.file
        layout.label(text=f"{lab}  [{item.weight}%]  {item.start:.2f}-{item.end:.2f}")


class DRS_UL_MarkerSets(bpy.types.UIList):
    bl_idname = "DRS_UL_MarkerSets"

    def draw_item(self, _ctx, layout, _data, item: MarkerSetPG, _icon, _active, _flt):
        try:
            key = int(item.anim_id)
        # pylint: disable=broad-exception-caught
        except Exception:
            key = 0
        lab = "(no action)" if item.file == "NONE" else item.file
        layout.label(text=f"{VIS_JOB_MAP.get(key, 'Unknown')} ({key}) — {lab}")


# ---------------------------------------------------------------------------
# Operators: save/reload + add/remove for lists
# ---------------------------------------------------------------------------


class DRS_OT_AnimSet_Reload(bpy.types.Operator):
    bl_idname = "drs.animset_reload"
    bl_label = "Reload"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        if not st.model:
            self.report({"ERROR"}, "No DRS model selected.")
            return {"CANCELLED"}
        _blob_to_state(st, _read_anim_blob(st.model))
        return {"FINISHED"}


class DRS_OT_AnimSet_Save(bpy.types.Operator):
    bl_idname = "drs.animset_save"
    bl_label = "Save"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        if not st.model:
            self.report({"ERROR"}, "No DRS model selected.")
            return {"CANCELLED"}
        _write_anim_blob(st.model, _state_to_blob(st))
        return {"FINISHED"}


class DRS_OT_ModeKey_Add(bpy.types.Operator):
    bl_idname = "drs.animset_modekey_add"
    bl_label = "Add Key"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        mk: ModeKeyPG = st.mode_keys.add()
        mk.vis_job = VIS_JOB_DEFAULT
        st.active_mode_key = len(st.mode_keys) - 1
        return {"FINISHED"}


class DRS_OT_ModeKey_Remove(bpy.types.Operator):
    bl_idname = "drs.animset_modekey_remove"
    bl_label = "Remove Key"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        idx = st.active_mode_key
        if 0 <= idx < len(st.mode_keys):
            st.mode_keys.remove(idx)
            st.active_mode_key = min(idx, len(st.mode_keys) - 1)
        return {"FINISHED"}


class DRS_OT_Variant_Add(bpy.types.Operator):
    bl_idname = "drs.animset_variant_add"
    bl_label = "Add Variant"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        if not (0 <= st.active_mode_key < len(st.mode_keys)):
            return {"CANCELLED"}
        mk = st.mode_keys[st.active_mode_key]
        v: AnimVariantPG = mk.variants.add()
        v.weight = 100
        v.start = 0.0
        v.end = 1.0
        v.allows_ik = True
        v.file = "NONE"  # sentinel always valid
        mk.active_variant = len(mk.variants) - 1
        return {"FINISHED"}


class DRS_OT_Variant_Remove(bpy.types.Operator):
    bl_idname = "drs.animset_variant_remove"
    bl_label = "Remove Variant"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        if not (0 <= st.active_mode_key < len(st.mode_keys)):
            return {"CANCELLED"}
        mk = st.mode_keys[st.active_mode_key]
        idx = mk.active_variant
        if 0 <= idx < len(mk.variants):
            mk.variants.remove(idx)
            mk.active_variant = min(idx, len(mk.variants) - 1)
        return {"FINISHED"}


class DRS_OT_MarkerSet_Add(bpy.types.Operator):
    bl_idname = "drs.animset_markerset_add"
    bl_label = "Add Marker Set"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        ms: MarkerSetPG = st.marker_sets.add()
        ms.anim_id = VIS_JOB_DEFAULT
        ms.file = "NONE"  # sentinel always valid
        ms.animation_marker_id = str(_alloc_marker_uint(st))
        m: MarkerPG = ms.markers.add()
        m.is_spawn_animation = False
        m.time = 0.0
        m.direction = (0.0, 0.0, 0.0)
        m.position = (0.0, 0.0, 0.0)
        st.active_marker_set = len(st.marker_sets) - 1
        return {"FINISHED"}


class DRS_OT_MarkerSet_Remove(bpy.types.Operator):
    bl_idname = "drs.animset_markerset_remove"
    bl_label = "Remove Marker Set"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        st.model = _active_drs_collection_from_props(context)
        idx = st.active_marker_set
        if 0 <= idx < len(st.marker_sets):
            st.marker_sets.remove(idx)
            st.active_marker_set = min(idx, len(st.marker_sets) - 1)
        return {"FINISHED"}


class DRS_OT_AnimSet_PlayVariant(bpy.types.Operator):
    """Play the active Variant's action once (start..end)."""

    bl_idname = "drs.animset_play_variant"
    bl_label = "Play"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        model = _active_drs_collection_with_armature(context)
        if not model:
            self.report({"ERROR"}, "Select a DRSModel_* collection with an Armature.")
            return {"CANCELLED"}

        arm = next((obj for obj in model.objects if obj.type == "ARMATURE"), None)
        if not arm:
            self.report({"ERROR"}, "No Armature found in this model.")
            return {"CANCELLED"}

        # Need an active Mode Key + Variant
        if not (0 <= st.active_mode_key < len(st.mode_keys)):
            self.report({"ERROR"}, "No Mode Key selected.")
            return {"CANCELLED"}
        mk = st.mode_keys[st.active_mode_key]
        if not (0 <= mk.active_variant < len(mk.variants)):
            self.report({"ERROR"}, "No Variant selected.")
            return {"CANCELLED"}
        v = mk.variants[mk.active_variant]

        # Resolve action
        act_name = (v.file or "").strip()
        if not act_name or act_name == "NONE":
            self.report({"ERROR"}, "Variant has no Action assigned.")
            return {"CANCELLED"}
        act = bpy.data.actions.get(act_name)
        if not act:
            self.report({"ERROR"}, f"Action '{act_name}' not found.")
            return {"CANCELLED"}

        # Map normalized [0..1] start/end to action frame range
        f0, f1 = act.frame_range
        span = max(1.0, (f1 - f0))
        n0 = max(0.0, min(1.0, float(v.start)))
        n1 = max(0.0, min(1.0, float(v.end)))
        if n1 <= n0:
            n1 = min(1.0, n0 + 0.01)  # ensure at least 1% span

        start_f = int(round(f0 + n0 * span))
        end_f = int(round(f0 + n1 * span))
        end_f = max(start_f + 1, end_f)

        # Assign action to armature (active action path, keep it simple)
        assign_action_compat(arm, act)

        # Restart playback cleanly
        _stop_preview_playback()
        scn = context.scene
        scn.frame_current = start_f

        # Register our stop-at-end handler (once)
        _playback_state["end_frame"] = end_f
        if _playback_state["handler"] is None:
            _playback_state["handler"] = _frame_stop_handler
            bpy.app.handlers.frame_change_post.append(_frame_stop_handler)

        # Start playing
        try:
            bpy.ops.screen.animation_play()
        # pylint: disable=broad-exception-caught
        except Exception:
            # Fallback: even if play couldn't start (rare), keep frame set
            pass

        return {"FINISHED"}


class DRS_OT_AnimSet_ShowMarker(bpy.types.Operator):
    """Assign the marker's Action at its time and show an arrow at its position/direction."""

    bl_idname = "drs.animset_show_marker"
    bl_label = "Show Marker"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = _state()
        model = _active_drs_collection_with_armature(context)
        if not model:
            self.report({"ERROR"}, "Select a DRSModel_* collection with an Armature.")
            return {"CANCELLED"}

        # Need an active marker set with one marker
        if not (0 <= st.active_marker_set < len(st.marker_sets)):
            self.report({"ERROR"}, "No Marker Set selected.")
            return {"CANCELLED"}
        ms = st.marker_sets[st.active_marker_set]
        if not ms.markers:
            self.report({"ERROR"}, "Marker Set has no marker.")
            return {"CANCELLED"}
        mk = ms.markers[0]

        # Resolve action (optional)
        act_name = (ms.file or "").strip()
        act = None
        if act_name and act_name != "NONE":
            act = bpy.data.actions.get(act_name)
            if not act:
                self.report(
                    {"WARNING"}, f"Action '{act_name}' not found; showing arrow only."
                )
        # Find armature
        arm = next(
            (o for o in _iter_objects_recursive(model) if o.type == "ARMATURE"), None
        )

        # Set frame from time if we have an action & armature
        if act and arm:
            from .animation_utils import assign_action_compat

            assign_action_compat(arm, act)
            base, sub = _frame_from_time(act, float(mk.time))
            print(base, sub)
            context.scene.frame_set(base, subframe=sub)

        # Create/update arrow at position/direction in GameOrientation space
        _upsert_marker_arrow(
            model,
            ms.animation_marker_id,  # CHANGED: pass string ID
            Vector(mk.position),
            Vector(mk.direction),
        )

        return {"FINISHED"}


class DRS_OT_AnimSet_PickAbilities(bpy.types.Operator):
    """Pick abilities to add. Creates Mode Keys (and Marker Sets for marker=True) with placeholders."""

    bl_idname = "drs.animset_pick_abilities"
    bl_label = "Add from Abilities"
    bl_options = {"INTERNAL"}

    items: CollectionProperty(type=AbilityItemPG)  # type: ignore
    active_index: IntProperty(default=0)  # type: ignore

    def _fill(self):
        st = _state()
        existing_key_ids = {int(m.vis_job) for m in st.mode_keys}

        def add_group(src: dict, label: str):
            for name, info in (src or {}).items():
                it = self.items.add()
                it.name = name
                it.category = label
                it.description = (info.get("description") or "").strip()
                it.marker = bool(info.get("marker", False))
                anims = info.get("animations", []) or []
                it.animations_json = json.dumps(anims)
                # availability: selectable only if at least one id is not yet present
                ids = {int(a["id"]) for a in anims if "id" in a}
                it.available = any(
                    (aid >= 0) and (aid not in existing_key_ids) for aid in ids
                )
                # do NOT preselect; user will choose explicitly
                it.selected = False

        self.items.clear()
        add_group(must_have_abilities, "Must")
        add_group(situational_abilities, "Situational")
        add_group(addtional_abilities, "Additional")

    def invoke(self, context, _event):
        self._fill()
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, _ctx):
        col = self.layout.column()
        row = col.row()
        row.template_list(
            "DRS_UL_AbilityPicker", "", self, "items", self, "active_index", rows=12
        )
        if 0 <= self.active_index < len(self.items):
            it = self.items[self.active_index]
            box = col.box()
            box.label(text=f"Type: {it.category}")
            if it.marker:
                box.label(
                    text="Requires a marker (will create placeholder).",
                    icon="MARKER_HLT",
                )
            desc = it.description or "(no description)"
            box.label(text=desc)

    def execute(self, _ctx):
        st = _state()

        existing_key_ids = {int(m.vis_job) for m in st.mode_keys}
        existing_ms_ids = {int(ms.anim_id) for ms in st.marker_sets}

        added_any = False
        for it in self.items:
            if not (it.selected and it.available):
                continue
            try:
                anims = json.loads(it.animations_json) or []
            except Exception:
                anims = []

            for a in anims:
                if "id" not in a:
                    continue
                try:
                    anim_id = int(a["id"])
                except Exception:
                    continue
                if anim_id < 0:
                    continue

                if anim_id not in existing_key_ids:
                    mk = st.mode_keys.add()
                    mk.vis_job = str(anim_id)
                    v = mk.variants.add()
                    v.weight = 100
                    v.start = 0.0
                    v.end = 1.0
                    v.allows_ik = True
                    v.file = "NONE"
                    st.active_mode_key = len(st.mode_keys) - 1
                    existing_key_ids.add(anim_id)
                    added_any = True

                if it.marker and anim_id not in existing_ms_ids:
                    ms = st.marker_sets.add()
                    ms.anim_id = str(anim_id)
                    ms.file = "NONE"
                    ms.animation_marker_id = str(_alloc_marker_uint(st))
                    m = ms.markers.add()
                    m.is_spawn_animation = False
                    m.time = 0.0
                    m.direction = (0.0, 0.0, 0.0)
                    m.position = (0.0, 0.0, 0.0)
                    st.active_marker_set = len(st.marker_sets) - 1
                    existing_ms_ids.add(anim_id)
                    added_any = True

        return {"FINISHED" if added_any else "CANCELLED"}


class DRS_OT_AnimSet_PickAbilities_Toggle(bpy.types.Operator):
    """Helper: select/deselect all items in the ability picker."""

    bl_idname = "drs.animset_pick_abilities_toggle"
    bl_label = "Toggle"
    bl_options = {"INTERNAL"}

    mode: StringProperty(default="ALL")  # type: ignore

    def execute(self, _ctx):
        # find the running picker in context (the operator owns the items)
        # This operator is called from inside the dialog; its properties live there.
        for wm in bpy.data.window_managers:
            for op in wm.operators:
                if isinstance(op, DRS_OT_AnimSet_PickAbilities):
                    if self.mode == "ALL":
                        for it in op.items:
                            it.selected = True
                    else:
                        for it in op.items:
                            it.selected = False
                    return {"FINISHED"}
        return {"CANCELLED"}


class DRS_OT_AnimSet_InitUnit(bpy.types.Operator):
    """Add all 'Must' abilities (creates missing Mode Keys and required Marker Sets)."""

    bl_idname = "drs.animset_init_unit"
    bl_label = "Init Unit"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        existing_key_ids = {int(m.vis_job) for m in st.mode_keys}
        existing_ms_ids = {int(ms.anim_id) for ms in st.marker_sets}

        added_any = False
        for name, info in (must_have_abilities or {}).items():
            anims = info.get("animations", []) or []
            needs_marker = bool(info.get("marker", False))
            for a in anims:
                if "id" not in a:
                    continue
                try:
                    anim_id = int(a["id"])
                except Exception:
                    continue
                if anim_id < 0:
                    continue

                if anim_id not in existing_key_ids:
                    mk = st.mode_keys.add()
                    mk.vis_job = str(anim_id)
                    v = mk.variants.add()
                    v.weight = 100
                    v.start = 0.0
                    v.end = 1.0
                    v.allows_ik = True
                    v.file = "NONE"
                    st.active_mode_key = len(st.mode_keys) - 1
                    existing_key_ids.add(anim_id)
                    added_any = True

                if needs_marker and anim_id not in existing_ms_ids:
                    ms = st.marker_sets.add()
                    ms.anim_id = str(anim_id)
                    ms.file = "NONE"
                    ms.animation_marker_id = str(_alloc_marker_uint(st))
                    m = ms.markers.add()
                    m.is_spawn_animation = False
                    m.time = 0.0
                    m.direction = (0.0, 0.0, 0.0)
                    m.position = (0.0, 0.0, 0.0)
                    st.active_marker_set = len(st.marker_sets) - 1
                    existing_ms_ids.add(anim_id)
                    added_any = True

        return {"FINISHED" if added_any else "CANCELLED"}


class DRS_OT_AnimSet_ClearAll(bpy.types.Operator):
    """Remove all Mode Keys and Marker Sets from the editor state."""

    bl_idname = "drs.animset_clear_all"
    bl_label = "Remove All"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        st.mode_keys.clear()
        st.marker_sets.clear()
        st.active_mode_key = 0
        st.active_marker_set = 0
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Panels: appear under the Locator editor panel (compact subpanels)
# ---------------------------------------------------------------------------


class DRS_PT_AnimSetRoot(bpy.types.Panel):
    bl_label = "Animation Set"
    bl_idname = "DRS_PT_AnimSetRoot"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "collection"

    @classmethod
    def poll(cls, context):
        return _active_drs_collection_with_armature(context) is not None

    def draw(self, context):
        st = _state()
        model = _active_drs_collection_with_armature(context)
        if st.model != model:
            st.model = model
            if st.model:
                _blob_to_state(st, _read_anim_blob(st.model))

        changed = False
        used = _collect_marker_uints(st)
        for ms in st.marker_sets:
            iv = _try_int(ms.animation_marker_id)
            if not _is_uint32(iv):
                nid = _alloc_marker_uint(st)
                ms.animation_marker_id = str(nid)
                used.add(nid)
                changed = True

        row = self.layout.row(align=True)
        row.operator("drs.animset_save", icon="CHECKMARK")
        row.operator("drs.animset_reload", icon="FILE_REFRESH")


class DRS_PT_AnimSetBasics(bpy.types.Panel):
    bl_label = "Basics"
    bl_idname = "DRS_PT_AnimSetBasics"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "collection"
    bl_parent_id = "DRS_PT_AnimSetRoot"

    @classmethod
    def poll(cls, context):
        return _active_drs_collection_with_armature(context) is not None

    def draw(self, _context):
        st = _state()
        box = self.layout.box()
        box.use_property_split = True
        box.use_property_decorate = False

        box.prop(st, "default_run_speed")
        box.prop(st, "default_walk_speed")
        row = box.row(align=True)
        row.prop(st, "mode_change_type")
        row.prop(st, "hovering_ground")
        box.prop(st, "align_to_terrain")
        box.separator()
        box.prop(st, "fly_bank_scale")
        box.prop(st, "fly_accel_scale")
        box.prop(st, "fly_hit_scale")


class DRS_PT_AnimSetModeKeys(bpy.types.Panel):
    bl_label = "Mode Keys"
    bl_idname = "DRS_PT_AnimSetModeKeys"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "collection"
    bl_parent_id = "DRS_PT_AnimSetRoot"

    @classmethod
    def poll(cls, context):
        return _active_drs_collection_with_armature(context) is not None

    def draw(self, _context):
        st = _state()
        col = self.layout.column(align=True)

        row_toolbar = col.row(align=True)
        row_toolbar.operator(
            "drs.animset_pick_abilities", icon="PLUS", text="Add from Abilities"
        )
        row_toolbar.operator(
            "drs.animset_init_unit", icon="OUTLINER_OB_ARMATURE", text="Init Unit"
        )
        row_toolbar.operator("drs.animset_clear_all", icon="TRASH", text="Remove All")

        row = col.row()
        row.template_list(
            "DRS_UL_ModeKeys", "", st, "mode_keys", st, "active_mode_key", rows=5
        )
        side = row.column(align=True)
        side.operator("drs.animset_modekey_add", icon="ADD", text="")
        side.operator("drs.animset_modekey_remove", icon="REMOVE", text="")

        if 0 <= st.active_mode_key < len(st.mode_keys):
            mk = st.mode_keys[st.active_mode_key]
            b = col.box()
            b.use_property_split = True
            b.use_property_decorate = False
            b.prop(mk, "vis_job")

            b.label(text="Variants")
            r = b.row()
            r.template_list(
                "DRS_UL_Variants", "", mk, "variants", mk, "active_variant", rows=4
            )
            rs = r.column(align=True)
            rs.operator("drs.animset_variant_add", icon="ADD", text="")
            rs.operator("drs.animset_variant_remove", icon="REMOVE", text="")

            if 0 <= mk.active_variant < len(mk.variants):
                v = mk.variants[mk.active_variant]
                b2 = b.box()
                b2.use_property_split = True
                b2.use_property_decorate = False
                b2.prop(v, "file", text="Action")
                b2.prop(v, "weight")
                row2 = b2.row(align=True)
                row2.prop(v, "start")
                row2.prop(v, "end")
                b2.prop(v, "allows_ik")
                rowp = b2.row(align=True)
                rowp.operator("drs.animset_play_variant", text="Play", icon="PLAY")


class DRS_PT_AnimSetMarkerSets(bpy.types.Panel):
    bl_label = "Marker Sets"
    bl_idname = "DRS_PT_AnimSetMarkerSets"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "collection"
    bl_parent_id = "DRS_PT_AnimSetRoot"

    @classmethod
    def poll(cls, context):
        return _active_drs_collection_with_armature(context) is not None

    def draw(self, _context):
        st = _state()
        col = self.layout.column(align=True)

        r = col.row()
        r.template_list(
            "DRS_UL_MarkerSets", "", st, "marker_sets", st, "active_marker_set", rows=4
        )
        rs = r.column(align=True)
        rs.operator("drs.animset_markerset_add", icon="ADD", text="")
        rs.operator("drs.animset_markerset_remove", icon="REMOVE", text="")

        if 0 <= st.active_marker_set < len(st.marker_sets):
            ms = st.marker_sets[st.active_marker_set]
            b3 = col.box()
            b3.use_property_split = True
            b3.use_property_decorate = False
            b3.prop(ms, "anim_id", text="VisJob")
            b3.prop(ms, "file", text="Action")
            b3.prop(ms, "animation_marker_id", text="Marker ID")
            if ms.markers:
                mk = ms.markers[0]
                b4 = b3.box()
                b4.use_property_split = True
                b4.use_property_decorate = False
                b4.prop(mk, "is_spawn_animation")
                b4.prop(mk, "time")
                row = b4.row(align=True)
                row.prop(mk, "direction")
                row.prop(mk, "position")
                row_btn = col.row(align=True)
                row_btn.operator(
                    "drs.animset_show_marker",
                    text="Show Marker",
                    icon="ORIENTATION_LOCAL",
                )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    AnimVariantPG,
    ModeKeyPG,
    MarkerPG,
    MarkerSetPG,
    AnimSetState,
    AbilityItemPG,
    DRS_UL_ModeKeys,
    DRS_UL_Variants,
    DRS_UL_MarkerSets,
    DRS_OT_AnimSet_Reload,
    DRS_OT_AnimSet_Save,
    DRS_OT_ModeKey_Add,
    DRS_OT_ModeKey_Remove,
    DRS_OT_Variant_Add,
    DRS_OT_Variant_Remove,
    DRS_OT_MarkerSet_Add,
    DRS_OT_MarkerSet_Remove,
    DRS_PT_AnimSetRoot,
    DRS_PT_AnimSetBasics,
    DRS_PT_AnimSetModeKeys,
    DRS_PT_AnimSetMarkerSets,
    DRS_OT_AnimSet_PlayVariant,
    DRS_OT_AnimSet_ShowMarker,
    DRS_UL_AbilityPicker,
    DRS_OT_AnimSet_PickAbilities,
    DRS_OT_AnimSet_PickAbilities_Toggle,
    DRS_OT_AnimSet_InitUnit,
    DRS_OT_AnimSet_ClearAll,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.drs_anim_state = PointerProperty(type=AnimSetState)


def unregister():
    del bpy.types.WindowManager.drs_anim_state
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
