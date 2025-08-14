# animation_set_editor.py
# Compact AnimationSet editor as subpanels under the Locator editor panel (Properties ▶ Collection).
# Blender 4.x, no external deps.

from __future__ import annotations
import json
import uuid
from typing import Dict, Optional
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

from .animation_utils import assign_action_compat
from .drs_definitions import VIS_JOB_MAP

# Build a static enum list at import time (identifier is the numeric id as string)
VIS_JOB_ENUM = [
    (str(k), f"{VIS_JOB_MAP.get(k, 'Unknown')} ({k})", "")
    for k in sorted(VIS_JOB_MAP.keys())
]
VIS_JOB_DEFAULT = VIS_JOB_ENUM[0][0] if VIS_JOB_ENUM else "0"


ANIM_BLOB_KEY = "AnimationSetJSON"
PARENT_LOCATOR_PANEL_ID = (
    "DRS_PT_LocatorEditorProps"  # must match the Locator editor panel id
)

# ---------------------------------------------------------------------------
# Active model / armature helpers
# ---------------------------------------------------------------------------


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
    animation_marker_id: StringProperty(name="Marker ID", default="")  # type: ignore
    markers: CollectionProperty(type=MarkerPG)  # type: ignore

    def ensure_id(self):
        if not self.animation_marker_id:
            self.animation_marker_id = str(uuid.uuid4())

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
        return {
            "anim_id": anim_id_int,
            "file": ("" if self.file == "NONE" else self.file),
            "animation_marker_id": self.animation_marker_id,
            "markers": [m0.to_dict()],
        }

    def from_dict(self, d: Dict):
        self.anim_id = str(int(d.get("anim_id", 0)))
        f = d.get("file", "")
        self.file = "NONE" if not f else f
        self.animation_marker_id = d.get("animation_marker_id", "") or ""
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
        ms.animation_marker_id = str(uuid.uuid4())
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    AnimVariantPG,
    ModeKeyPG,
    MarkerPG,
    MarkerSetPG,
    AnimSetState,
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
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.drs_anim_state = PointerProperty(type=AnimSetState)


def unregister():
    del bpy.types.WindowManager.drs_anim_state
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
