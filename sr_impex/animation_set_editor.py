# animation_set_editor.py — Minimal, standalone AnimationSet Editor window
# Blender 4.x

from __future__ import annotations
import json
import hashlib
import os
import json
from typing import Dict, Optional, Set, Tuple

import bpy
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
)

# ---------------------------------------------------------------------------
# Abilities / actions
# ---------------------------------------------------------------------------

from .abilities import (
    must_have_abilities,
    situational_abilities,
    additional_abilities,
)


_ACTIONS_ENUM_CACHE = None
_ACTIONS_ENUM_COUNT = -1


def _actions_enum(_self, _ctx):
    # Build once per action-count change (fast)
    global _ACTIONS_ENUM_CACHE, _ACTIONS_ENUM_COUNT
    acts = bpy.data.actions
    if _ACTIONS_ENUM_CACHE is None or len(acts) != _ACTIONS_ENUM_COUNT:
        names = [a.name for a in acts]
        names.sort()  # stable order, build once
        items = [("NONE", "<None>", "")]
        items.extend((n, n, "") for n in names)
        _ACTIONS_ENUM_CACHE = items
        _ACTIONS_ENUM_COUNT = len(acts)
    return _ACTIONS_ENUM_CACHE


def _iter_all_abilities() -> dict:
    merged = {}
    for src in (
        must_have_abilities or {},
        situational_abilities or {},
        additional_abilities or {},
    ):
        merged.update(src or {})
    return merged


def _build_vis_maps() -> Tuple[dict, dict, dict]:
    """vis_id -> label (Ability), ability, role."""
    v_to_label, v_to_ability, v_to_role = {}, {}, {}
    for ability_name, ability_data in _iter_all_abilities().items():
        for comp in ability_data.get("components", []) or []:
            vid = comp.get("vis_job_id")
            if vid is None:
                continue
            try:
                vid = int(vid)
            except:  # pylint: disable=bare-except
                continue
            v_to_label[vid] = ability_name
            v_to_ability[vid] = ability_name
            v_to_role[vid] = (comp.get("role") or "").strip()
    return v_to_label, v_to_ability, v_to_role


VIS_JOB_MAP, VIS_JOB_TO_ABILITY, VIS_JOB_TO_ROLE = _build_vis_maps()
VIS_JOB_ENUM = [
    (str(k), f"{VIS_JOB_MAP.get(k, 'Unknown')} ({k})", "")
    for k in sorted(VIS_JOB_MAP.keys())
]
VIS_JOB_DEFAULT = VIS_JOB_ENUM[0][0] if VIS_JOB_ENUM else "0"


def _ability_components_map() -> Dict[str, Set[int]]:
    out = {}
    for name, data in _iter_all_abilities().items():
        vids = set()
        for c in data.get("components", []) or []:
            try:
                vids.add(int(c.get("vis_job_id")))
            except:  # pylint: disable=bare-except
                pass
        if vids:
            out[name] = vids
    return out


_ABILITY_COMPONENTS = _ability_components_map()


def _present_vis_ids(st) -> Set[int]:
    ids = set()
    for mk in st.mode_keys:
        try:
            ids.add(int(mk.vis_job))
        except:  # pylint: disable=bare-except
            pass
    return ids


def _infer_ability_for_visjob(vis_id: int, _st=None) -> str:
    # O(1) – direct mapping is enough for labels/grouping
    return VIS_JOB_TO_ABILITY.get(vis_id, VIS_JOB_MAP.get(vis_id, "Unknown"))


def _draw_editor_ui(layout):
    st = _state()
    col = _active_top_drsmodel()
    if not col:
        box = layout.box()
        box.label(
            text="Select the main DRSModel_* collection (it must be ACTIVE).",
            icon="INFO",
        )
        return

    # Header bar
    hdr = layout.row(align=True)
    hdr.label(text=("" if col else "No DRSModel selected"))
    hdr.operator("drs.animset_reinit", text="Init", icon="FILE_REFRESH")
    hdr.operator("drs.animset_clear_all", text="Remove All", icon="TRASH")
    hdr.separator()
    hdr.separator()
    hdr.operator("drs.animset_save", text="Save", icon="CHECKMARK")
    hdr.operator("drs.animset_reload", text="Reset", icon="FILE_REFRESH")

    layout.separator()

    # Basics (compact, two columns)
    basics = layout.box()
    basics.label(text="Basics", icon="ANIM_DATA")
    g = basics.grid_flow(
        row_major=True, columns=2, even_columns=True, even_rows=True, align=True
    )
    g.prop(st, "default_walk_speed")
    g.prop(st, "fly_bank_scale")
    g.prop(st, "default_run_speed")
    g.prop(st, "fly_accel_scale")
    g.prop(st, "mode_change_type")
    g.prop(st, "fly_hit_scale")
    g.prop(st, "hovering_ground")
    g.prop(st, "align_to_terrain")

    layout.separator()

    # Mode + Ability list on left, Details on right
    split = layout.split(factor=0.42)
    left = split.column()
    right = split.column()

    # Mode switch (disabled if no model)
    rowm = left.row(align=True)
    rowm.enabled = bool(col)
    rowm.prop(st, "show_mode", text="Mode", expand=True)

    # Show EACH mode_key (no dedup) so Cast Ground / Cast Air appear as separate items
    row = left.row()
    col_list = row.column()
    # Build items for the left list
    items = []  # (display_label, representative_index)
    seen_groups = set()

    for i, mk in enumerate(st.mode_keys):
        if int(mk.special_mode) != _current_mode():
            continue
        ab = _infer_ability_for_visjob(int(mk.vis_job), st)
        source_role = mk.role or ""
        role = (mk.role or "").lower()

        # skip any resolve-only entries
        if "resolve" in role:
            continue

        # group S/L/E by (ability,special) so we list them once
        if role.endswith("start") or role.endswith("loop") or role.endswith("end"):
            if role.find("modechannel") >= 0:
                continue
            key = (ab, mk.special_mode, "SLE")
            if key in seen_groups:  # already added
                continue
            seen_groups.add(key)
            items.append((f"{ab} — Loop Set", i))
            continue

        # cast-like entries (ground/air are separate visjobs -> separate rows)
        suffix = ""

        if "Cast" in source_role:
            if "Ground" in source_role:
                suffix = " (Ground)"
            elif "Air" in source_role:
                suffix = " (Air)"
            items.append((f"{ab} — Cast{suffix}", i))
            continue

        # plain entries (walk/run/idle etc.)
        # role_lbl = role.replace("_", " ").title() if role else "Normal"
        items.append((f"{ab}", i))

    # draw list
    for label, any_idx in items:
        r = left.row(align=True)
        r.enabled = True
        op = r.operator(
            "drs.animset_select_ability",
            text=label,
            depress=(st.active_mode_key == any_idx),
        )
        op.index = any_idx
        r.operator("drs.modekey_remove", text="", icon="REMOVE").index = any_idx

    # --- Add Ability (current mode) ---
    add_box = left.box()
    add_box.enabled = True
    add_box.label(text=f"Add Ability to {_mode_label(_current_mode())}")
    row = add_box.row(align=True)
    row.operator("drs.open_ability_picker", text="Add Ability…", icon="PLUS")

    if not _available_abilities_for_mode(_current_mode()):
        add_box.label(
            text="All abilities for this mode are already present.", icon="CHECKMARK"
        )

    # details for the selected representative
    if 0 <= st.active_mode_key < len(st.mode_keys):
        mk = st.mode_keys[st.active_mode_key]
        ab_name = _infer_ability_for_visjob(int(mk.vis_job), st)
        box = right.box()
        box.label(text=ab_name, icon="ACTION")
        if mk.target_mode >= 0:
            box.label(
                text=f"ModeSwitch → {_mode_label(int(mk.target_mode))}",
                icon="SORT_DESC",
            )
        role = (mk.role or "").lower()

        # Cast detail (no resolve row)
        if "cast" in role:
            rowt = box.row(align=True)
            rowt.prop(mk, "cast_to_resolve", text="Cast→Resolve")
            # keep variant.end synced (source of truth is mk.cast_to_resolve)
            if 0 <= mk.active_variant < len(mk.variants):
                mk.variants[mk.active_variant].end = mk.cast_to_resolve

            btn = box.row(align=True)
            op = btn.operator("drs.animset_play_range", text="Play Cast", icon="PLAY")
            op.mode_key_index, op.n0, op.n1 = (
                st.active_mode_key,
                0.0,
                mk.cast_to_resolve,
            )
            op = btn.operator(
                "drs.animset_play_range", text="Play Resolve", icon="PLAY"
            )
            op.mode_key_index, op.n0, op.n1 = (
                st.active_mode_key,
                mk.cast_to_resolve,
                1.0,
            )

        # S/L/E shown ONCE with two timings and three play buttons
        comps = [
            (i2, m2)
            for i2, m2 in enumerate(st.mode_keys)
            if _infer_ability_for_visjob(int(m2.vis_job), st) == ab_name
            and m2.special_mode == mk.special_mode
        ]
        roles = {}
        for i2, m2 in comps:
            r2 = (m2.role or "").lower()
            key = (
                "start"
                if r2.endswith("start")
                else (
                    "loop"
                    if r2.endswith("loop")
                    else "end" if r2.endswith("end") else r2
                )
            )
            roles[key] = (i2, m2)

        start = roles.get("start")
        loop = roles.get("loop")
        end = roles.get("end")
        if start and loop:
            s_idx, s_mk = start
            l_idx, l_mk = loop

            rowt = box.row(align=True)
            rowt.prop(s_mk, "start_to_loop", text="Start.end")
            rowt.prop(s_mk, "loop_to_end", text="Loop.end")

            # clamp & propagate to first variant of S and L (acts as preview)
            s_mk.start_to_loop = min(
                max(0.0, s_mk.start_to_loop), max(0.0, s_mk.loop_to_end)
            )
            s_mk.loop_to_end = max(
                min(1.0, s_mk.loop_to_end), min(1.0, s_mk.start_to_loop)
            )
            if s_mk.variants:
                s_mk.variants[0].end = s_mk.start_to_loop
            if l_mk.variants:
                l_mk.variants[0].start = s_mk.start_to_loop
                l_mk.variants[0].end = s_mk.loop_to_end

            btn = box.row(align=True)
            op = btn.operator("drs.animset_play_range", text="Start", icon="PLAY")
            op.mode_key_index, op.n0, op.n1 = s_idx, 0.0, s_mk.start_to_loop
            op = btn.operator("drs.animset_play_range", text="Loop", icon="PLAY")
            op.mode_key_index, op.n0, op.n1 = (
                l_idx,
                s_mk.start_to_loop,
                s_mk.loop_to_end,
            )
            if end:
                e_idx, _ = end
                op = btn.operator("drs.animset_play_range", text="End", icon="PLAY")
                op.mode_key_index, op.n0, op.n1 = e_idx, s_mk.loop_to_end, 1.0

        _draw_variant_editor(
            box,
            st.active_mode_key,
            mk,
            is_cast=("cast" in role and "resolve" not in role),
            is_sle=bool(start and loop),
        )


# ---------- Filename -> Action resolver using model's mapping ----------
_BL_MAX = 63


def _resolve_action_name(name: str) -> str:
    """Resolve blob filename to a valid Action name shown in Enum.
    Priority:
      1) Model mapping (_drs_action_map) on active top-level DRSModel_*
      2) Exact matches in bpy.data.actions
      3) .ska <-> no .ska
      4) Blender 63-char truncation (+ numbered variants)
      5) Prefix fallback
    """
    if not name:
        return "NONE"
    want = name.strip()
    base = want[:-4] if want.lower().endswith(".ska") else want

    # 1) mapping from importer
    col = _active_top_drsmodel()
    if col:
        try:
            raw = col.get("_drs_action_map", "{}")
            mp = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            mp = {}
        # Try different keys the blob might contain
        for key in (want, os.path.basename(want), base, os.path.basename(base)):
            act = mp.get(key)
            if act and act in bpy.data.actions:
                return act

    names = [a.name for a in bpy.data.actions]
    name_set = set(names)

    def hit(cand: str) -> Optional[str]:
        return cand if cand in name_set else None

    # 2) exact
    if hit(want):
        return want
    # 3) with / without .ska
    if hit(base):
        return base
    if hit(base + ".ska"):
        return base + ".ska"
    # 4) truncation
    t_want, t_base, t_with_ska = (
        want[:_BL_MAX],
        base[:_BL_MAX],
        (base + ".ska")[:_BL_MAX],
    )
    if hit(t_want):
        return t_want
    if hit(t_base):
        return t_base
    if hit(t_with_ska):
        return t_with_ska
    # … numbered collisions
    prefix = t_base.rstrip(".")
    numbered = [n for n in names if n.startswith(prefix + ".")]
    if numbered:

        def parse_suffix(nm: str):
            try:
                return int(nm.split(".")[-1])
            except:
                return 99999

        numbered.sort(key=parse_suffix)
        return numbered[0]
    # 5) weak prefix fallback
    best = None
    best_score = -1
    for n in names:
        nb = n[:-4] if n.lower().endswith(".ska") else n
        score = len(os.path.commonprefix([nb, base]))
        if score > best_score:
            best_score, best = score, n
    return best if best and best_score >= max(8, len(base) // 2) else "NONE"


# ---- Mode labeling (generic) ----
def _mode_label(m: int) -> str:
    return {
        0: "Base",
        1: "Special",
        2: "Rest",
        3: "Rest->Base",
    }.get(int(m), f"Mode {int(m)}")


def _available_modes_from_drs(col: bpy.types.Collection) -> set[int]:
    modes = set()
    try:
        ks = col.get("_drs_animset_keys")
        if isinstance(ks, (list, tuple)):
            for k in ks:
                modes.add(int(k.get("special_mode", 0)))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    # include any editor-added empty modes
    try:
        extra = col.get("_drs_extra_modes", [])
        if isinstance(extra, (list, tuple)):
            modes |= {int(x) for x in extra}
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return modes


def _available_modes() -> list[int]:
    st = _state()
    modes = {int(m.special_mode) for m in st.mode_keys}
    col = _active_top_drsmodel()
    if col:
        modes |= _available_modes_from_drs(col)
    if not modes:
        modes = {0}
    return sorted(modes)


def _mode_items(_self, _ctx):
    modes = sorted(_available_modes())  # your function that collects ints
    if not modes:
        modes = [0]
    # Important: identifiers are strings, but the Enum default is an INDEX (we set default=0 in the prop)
    return [(str(m), _mode_label(m), "", i) for i, m in enumerate(modes)]


def _current_mode() -> int:
    try:
        st = _state()
        v = getattr(st, "show_mode", "")
        return int(v) if v not in ("", None) else 0
    except Exception:  # pylint: disable=broad-exception-caught
        return 0


def _register_extra_mode(col: bpy.types.Collection, mode_val: int) -> None:
    """Expose a new empty mode in the UI even if no keys exist yet."""
    try:
        extra = col.get("_drs_extra_modes", [])
        if not isinstance(extra, list):
            extra = []
        if int(mode_val) not in extra:
            extra.append(int(mode_val))
        col["_drs_extra_modes"] = extra
    except Exception:
        pass


def _parse_modeswitch_target(role: str, cur_mode: int) -> int | None:
    r = (role or "").lower()
    if "modeswitch" not in r:
        return None
    # crude tokens
    # look for "..._to_<name>" pattern
    parts = r.split("_to_")
    if len(parts) >= 2:
        tail = parts[-1]
        # strip trailing digits like "..._turret1"
        base = "".join(ch for ch in tail if not ch.isdigit())
        base = base.strip("_")
    else:
        base = ""
    name_to_mode = {"base": 0, "special": 1, "rest": 2, "rest->base": 3}
    if base in name_to_mode:
        return name_to_mode[base]
    return None


def _redraw_ui():
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", []):
        scr = getattr(win, "screen", None)
        if not scr:
            continue
        for area in scr.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---- Ability inventory helpers ---------------------------------------------


# Build a flat abilities map from abilities.py
def _all_abilities_map():
    d = {}
    from .abilities import (
        must_have_abilities,
        situational_abilities,
        additional_abilities,
    )

    d.update(must_have_abilities)
    d.update(situational_abilities)
    d.update(additional_abilities)
    return d


# Search items for the CURRENT mode (dynamic int)
def _ability_items_for_current_mode():
    names = list(_available_abilities_for_mode(_current_mode()))
    ab_map = _all_abilities_map()
    out = []
    for name in sorted(names, key=str.lower):
        desc = (ab_map.get(name, {}).get("description") or "").strip()
        label = f"{name} - {desc}" if desc else name
        out.append((name, label, desc))
    return out


# Stable items callback Blender can always find
def _ability_items_cb(self, _ctx):
    try:
        return _ability_items_for_current_mode()
    except Exception:
        return []


def _ability_catalog():
    # flatten with categories
    from .abilities import (
        must_have_abilities,
        situational_abilities,
        additional_abilities,
    )

    cat = {}
    for k in must_have_abilities.keys():
        cat[k] = ("Must-have", must_have_abilities[k])
    for k in situational_abilities.keys():
        cat[k] = ("Situational", situational_abilities[k])
    for k in additional_abilities.keys():
        cat[k] = ("Additional", additional_abilities[k])
    return cat


def _fill_picker_items(self_items, mode: int, query: str = ""):
    """
    Populate AbilityPickItemPG collection for current mode.
    Only shows abilities not yet added to this mode (uses your _available_abilities_for_mode).
    """
    self_items.clear()
    names = list(_available_abilities_for_mode(mode))
    catalog = _ability_catalog()
    q = (query or "").lower().strip()
    for name in sorted(names, key=str.lower):
        cat, data = catalog.get(name, ("", {}))
        desc = (data.get("description") or "").strip()
        if q and (q not in name.lower()) and (q not in desc.lower()):
            continue
        it = self_items.add()
        it.name = name
        it.description = desc
        it.category = cat
        it.available = True
        it.selected = False


# ---------------------------------------------------------------------------
# Blob I/O
# ---------------------------------------------------------------------------

ANIM_BLOB_KEY = "AnimationSetJSON"


def _empty_blob() -> Dict:
    return {
        "default_run_speed": 5.0,
        "default_walk_speed": 2.0,
        "mode_change_type": 0,
        "hovering_ground": False,
        "fly_bank_scale": 0.0,
        "fly_accel_scale": 0.0,
        "fly_hit_scale": 0.0,
        "align_to_terrain": False,
        "mode_keys": [],
    }


def _read_blob(col: bpy.types.Collection) -> Dict:
    data = col.get(ANIM_BLOB_KEY)
    if not data:
        return _empty_blob()
    try:
        b = json.loads(data)
        b.setdefault("mode_keys", [])
        return b
    except Exception:  # pylint: disable=broad-exception-caught
        return _empty_blob()


def _write_blob(col: bpy.types.Collection, blob: Dict) -> None:
    col[ANIM_BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_last = {"col_name": None, "blob_sig": None}


def _active_top_drsmodel(context=None):
    ctx = context or bpy.context
    alc = ctx.view_layer.active_layer_collection.collection if ctx.view_layer else None
    if not isinstance(alc, bpy.types.Collection):
        return None
    if not alc.name.startswith("DRSModel_"):
        return None
    for top in ctx.scene.collection.children:
        if top == alc:
            return alc
    return None


def _blob_sig(col: bpy.types.Collection) -> str | None:
    data = col.get(ANIM_BLOB_KEY, "")
    return (
        hashlib.sha1(data.encode("utf-8")).hexdigest()
        if isinstance(data, str)
        else None
    )


def _poll_editor_refresh():
    try:
        col = _active_top_drsmodel()
        name = col.name if col else None
        sig = _blob_sig(col) if col else None

        # If the active model changed, remember it, but do NOT clobber the UI unless empty.
        if name != _last["col_name"]:
            _last["col_name"] = name
            _last["blob_sig"] = sig
            # Only pull from blob when editor has no data yet.
            if col and len(_state().mode_keys) == 0:
                _refresh_state_from_blob(col)
        else:
            # Track sig, but never auto-apply it. User must press Reload.
            _last["blob_sig"] = sig
    except Exception:
        pass
    return 0.5


class AnimVariantPG(bpy.types.PropertyGroup):
    weight: IntProperty(name="Weight", default=100, min=0, max=100)  # type: ignore
    start: FloatProperty(name="Start", default=0.0, min=0.0, max=1.0)  # type: ignore
    end: FloatProperty(name="End", default=1.0, min=0.0, max=1.0)  # type: ignore
    allows_ik: BoolProperty(name="Allows IK", default=True)  # type: ignore
    force_no_blend: BoolProperty(name="Force No Blend", default=False)  # type: ignore
    file: EnumProperty(name="Action", items=_actions_enum)  # type: ignore


def _update_cast_to_resolve(self, _ctx):
    val = max(0.0, min(1.0, float(self.cast_to_resolve)))
    for v in self.variants:
        v.end = val


class ModeKeyPG(bpy.types.PropertyGroup):
    vis_job: EnumProperty(name="VisJob", items=VIS_JOB_ENUM, default=VIS_JOB_DEFAULT)  # type: ignore
    ability_name: StringProperty(name="Ability", default="")  # type: ignore
    role: StringProperty(name="Role", options={"HIDDEN"}, default="")  # type: ignore
    special_mode: IntProperty(name="Mode", default=0, min=0)  # type: ignore
    target_mode: IntProperty(name="Target Mode", default=-1, min=-1)  # type: ignore
    # Linked timing sliders
    start_to_loop: FloatProperty(name="Start→Loop", default=0.33, min=0.0, max=1.0)  # type: ignore
    loop_to_end: FloatProperty(name="Loop→End", default=0.66, min=0.0, max=1.0)  # type: ignore
    cast_to_resolve: FloatProperty(
        name="Cast→Resolve",
        default=0.5,
        min=0.0,
        max=1.0,
        update=_update_cast_to_resolve,
    )  # type: ignore
    variants: CollectionProperty(type=AnimVariantPG)  # type: ignore
    active_variant: IntProperty(default=0)  # type: ignore


class AnimSetState(bpy.types.PropertyGroup):
    # Basics
    default_run_speed: FloatProperty(name="Run Speed", default=5.0, description="Default run speed for the character")  # type: ignore
    default_walk_speed: FloatProperty(name="Walk Speed", default=2.0, description="Default walk speed for the character")  # type: ignore
    fly_bank_scale: FloatProperty(name="Fly Bank Scale", default=0.0, description="Fly bank scale for the character")  # type: ignore
    fly_accel_scale: FloatProperty(name="Fly Accel Scale", default=0.0, description="Fly acceleration scale for the character")  # type: ignore
    fly_hit_scale: FloatProperty(name="Fly Hit Scale", default=0.0, description="Fly hit scale for the character")  # type: ignore

    mode_change_type: IntProperty(name="Mode Change Type", default=0, min=0, max=1, description="Whether the mode change is of a specific type")  # type: ignore
    hovering_ground: BoolProperty(name="Hovering Ground", default=False, description="Whether the character is hovering above the ground")  # type: ignore
    align_to_terrain: BoolProperty(name="Align to Terrain", default=False, description="Whether the character aligns to the terrain")  # type: ignore

    # Mode (Dynamic))
    show_mode: EnumProperty(name="Mode", items=_mode_items, default=0)  # type: ignore

    # AnimModeKeys
    mode_keys: CollectionProperty(type=ModeKeyPG)  # type: ignore
    active_mode_key: IntProperty(default=0)  # type: ignore


# ---------------------------------------------------------------------------
# Active model helpers (DRSModel_* collection + armature presence)
# ---------------------------------------------------------------------------


def _active_model() -> Optional[bpy.types.Collection]:
    # Selected collection in Outliner preferred; else active layer collection.
    col = None
    ctx = bpy.context
    col = getattr(ctx, "collection", None)
    if isinstance(col, bpy.types.Collection) and col.name.startswith("DRSModel_"):
        return col
    alc = ctx.view_layer.active_layer_collection.collection if ctx.view_layer else None
    if alc and alc.name.startswith("DRSModel_"):
        return alc
    return None


def _find_armature(col: bpy.types.Collection) -> Optional[bpy.types.Object]:
    def visit(c: bpy.types.Collection) -> Optional[bpy.types.Object]:
        for o in c.objects:
            if o.type == "ARMATURE":
                return o
        for ch in c.children:
            r = visit(ch)
            if r:
                return r
        return None

    return visit(col)


# ---------------------------------------------------------------------------
# Read/Write between blob and UI state
# ---------------------------------------------------------------------------


def _state() -> AnimSetState:
    return bpy.context.window_manager.drs_anim_state


def _refresh_state_from_blob(col: bpy.types.Collection):
    st = _state()
    b = _read_blob(col)
    st.default_run_speed = float(b.get("default_run_speed", 5.0))
    st.default_walk_speed = float(b.get("default_walk_speed", 2.0))
    st.mode_change_type = int(b.get("mode_change_type", 0))
    st.fly_bank_scale = float(b.get("fly_bank_scale", 0.0))
    st.fly_accel_scale = float(b.get("fly_accel_scale", 0.0))
    st.fly_hit_scale = float(b.get("fly_hit_scale", 0.0))
    st.hovering_ground = bool(b.get("hovering_ground", 0))
    st.align_to_terrain = bool(b.get("align_to_terrain", 0))

    st.mode_keys.clear()
    # First pass: build entries
    tmp = []
    for mkd in b.get("mode_keys", []):
        mk: ModeKeyPG = st.mode_keys.add()
        mk.vis_job = str(int(mkd.get("vis_job", 0)))
        mk.ability_name = ""
        # role may be absent in blob; infer from abilities map if needed
        mk.role = VIS_JOB_TO_ROLE.get(int(mk.vis_job), mkd.get("role", ""))
        mk.special_mode = int(mkd.get("special_mode", 0))
        mk.start_to_loop = float(mkd.get("start_to_loop", 0.33))
        mk.loop_to_end = float(mkd.get("loop_to_end", 0.66))
        mk.cast_to_resolve = float(mkd.get("cast_to_resolve", 0.5))
        mk.variants.clear()
        vlist = []
        for vd in mkd.get("variants", []):
            v = mk.variants.add()
            v.weight = int(vd.get("weight", 100))
            v.start = float(vd.get("start", 0.0))
            v.end = float(vd.get("end", 1.0))
            v.allows_ik = bool(int(vd.get("allows_ik", 1)))
            v.force_no_blend = bool(int(vd.get("force_no_blend", 0)))
            f = (vd.get("file") or "").strip()
            v.file = _resolve_action_name(f)
            vlist.append(v)
        tmp.append((mk, vlist))

    # Second pass: derive sliders from actual variants (file truth)
    # - Cast: for EVERY cast-* ModeKey, set cast_to_resolve = its first variant's end
    # - S/L/E: keep grouped timing (Start.end, Loop.end) per ability+special
    def _rolekey(mk):
        r = (mk.role or "").lower()
        if r.endswith("start"):
            return "start"
        if r.endswith("loop"):
            return "loop"
        if r.endswith("end"):
            return "end"
        if "cast" in r and "resolve" not in r:
            return "cast"
        return r

    # 2a) CAST: seed every cast-* entry individually
    for mk, vlist in tmp:
        r = (mk.role or "").lower()
        if "cast" in r and "resolve" not in r:
            if vlist:
                mk.cast_to_resolve = float(vlist[0].end)

    # 2b) S/L/E grouped per (ability, special)
    buckets = {}
    for mk, vlist in tmp:
        ab = _infer_ability_for_visjob(int(mk.vis_job), st)
        buckets.setdefault((ab, mk.special_mode), []).append((mk, vlist))

    for (_ab, _sp), items in buckets.items():
        roles = {}
        for mk, vlist in items:
            roles[_rolekey(mk)] = (mk, vlist)
        # S/L/E
        if "start" in roles and "loop" in roles:
            mk_s, vl_s = roles["start"]
            mk_l, vl_l = roles["loop"]
            if vl_s:
                mk_s.start_to_loop = float(vl_s[0].end)
            if vl_l:
                mk_s.loop_to_end = float(vl_l[0].end)

    try:
        modes = sorted(_available_modes())
        st = _state()
        # If current value invalid/empty, set to first mode's identifier
        if not modes:
            st.show_mode = "0"
        else:
            cur = getattr(st, "show_mode", "")
            if cur == "" or (cur not in {str(m) for m in modes}):
                st.show_mode = str(modes[0])
    except Exception:
        pass


def _write_state_to_blob(col: bpy.types.Collection):
    st = _state()
    b = {
        "default_run_speed": float(st.default_run_speed),
        "default_walk_speed": float(st.default_walk_speed),
        "mode_change_type": int(st.mode_change_type),
        "hovering_ground": int(st.hovering_ground),
        "fly_bank_scale": float(st.fly_bank_scale),
        "fly_accel_scale": float(st.fly_accel_scale),
        "fly_hit_scale": float(st.fly_hit_scale),
        "align_to_terrain": int(st.align_to_terrain),
        "mode_keys": [],
    }
    for mk in st.mode_keys:
        try:
            vj = int(mk.vis_job)
        except:  # pylint: disable=bare-except
            vj = 0
        md = {
            "vis_job": vj,
            "role": mk.role,
            "special_mode": int(mk.special_mode),
            "start_to_loop": float(mk.start_to_loop),
            "loop_to_end": float(mk.loop_to_end),
            "cast_to_resolve": float(mk.cast_to_resolve),
            "variants": [],
        }
        for v in mk.variants:
            md["variants"].append(
                {
                    "weight": int(v.weight),
                    "start": float(v.start),
                    "end": float(v.end),
                    "allows_ik": 1 if v.allows_ik else 0,
                    "force_no_blend": 1 if v.force_no_blend else 0,
                    "file": "" if v.file == "NONE" else v.file,
                }
            )
        b["mode_keys"].append(md)
    _write_blob(col, b)


# ---------------------------------------------------------------------------
# Operators: Add/Remove, Init/Reinit/Clear, Playback
# ---------------------------------------------------------------------------


class DRS_OT_AnimSet_InitUnit(bpy.types.Operator):
    """Initialize base animations for the selected unit."""

    bl_idname = "drs.animset_init_unit"
    bl_label = "Init Base Animations"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        # uniquess: don't add duplicates
        existing = {(int(m.vis_job), int(m.special_mode)) for m in st.mode_keys}
        for (
            ability_name,
            data,
        ) in (
            must_have_abilities.items()
        ):  # base set only :contentReference[oaicite:3]{index=3}
            for comp in data.get("components", []):
                vis = int(comp.get("vis_job_id", -1))
                if vis < 0:
                    continue
                key = (vis, 0)
                if key in existing:
                    continue
                mk = st.mode_keys.add()
                mk.vis_job = str(vis)
                mk.ability_name = ability_name
                mk.role = comp.get("role", "")
                mk.special_mode = 0
                v = mk.variants.add()
                v.weight, v.start, v.end, v.allows_ik, v.file, v.force_no_blend = (
                    100,
                    0.0,
                    1.0,
                    True,
                    "NONE",
                )
                existing.add(key)
        return {"FINISHED"}


class DRS_OT_AnimSet_ClearAll(bpy.types.Operator):
    """Remove all animation set data from the active model."""

    bl_idname = "drs.animset_clear_all"
    bl_label = "Remove All"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        st = _state()
        st.mode_keys.clear()
        st.active_mode_key = 0
        return {"FINISHED"}


class DRS_OT_AnimSet_Reinit(bpy.types.Operator):
    """Initialize base animations for the selected unit."""

    bl_idname = "drs.animset_reinit"
    bl_label = "Reinitialize"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        bpy.ops.drs.animset_clear_all()
        bpy.ops.drs.animset_init_unit()
        return {"FINISHED"}


class DRS_OT_ModeKey_AddAbility(bpy.types.Operator):
    bl_idname = "drs.modekey_add_ability"
    bl_label = "Add Ability"
    bl_options = {"INTERNAL"}

    ability: StringProperty(default="")  # type: ignore
    mode: IntProperty(default=0)  # type: ignore

    def execute(self, _ctx):
        st = _state()
        ability_data = _iter_all_abilities().get(self.ability) or {}
        existing = {(int(m.vis_job), int(m.special_mode)) for m in st.mode_keys}
        col = _active_top_drsmodel()

        added = False
        for comp in ability_data.get("components", []):
            vis = int(comp.get("vis_job_id", -1))
            if vis < 0:
                continue
            key = (vis, int(self.mode))
            if key in existing:
                continue  # uniqueness enforced
            mk = st.mode_keys.add()
            mk.vis_job = str(vis)
            mk.ability_name = self.ability
            mk.role = comp.get("role", "")
            mk.special_mode = int(self.mode)
            # If this component is a ModeSwitch, set connector and ensure target mode exists
            dst = _parse_modeswitch_target(mk.role, int(self.mode))
            if dst is not None:
                mk.target_mode = int(dst)
                # auto-create target mode in UI if it's new
                if col and int(dst) not in _available_modes():
                    _register_extra_mode(col, int(dst))
            else:
                mk.target_mode = -1
            v = mk.variants.add()
            v.weight, v.start, v.end, v.allows_ik, v.file, v.force_no_blend = (
                100,
                0.0,
                1.0,
                True,
                "NONE",
                False,
            )
            existing.add(key)
            added = True

        _redraw_ui()
        return {"FINISHED" if added else "CANCELLED"}


class DRS_OT_ModeKey_Remove(bpy.types.Operator):
    bl_idname = "drs.modekey_remove"
    bl_label = "Remove"
    bl_options = {"INTERNAL"}
    index: IntProperty(default=-1)  # type: ignore

    def execute(self, _ctx):
        st = _state()
        if 0 <= self.index < len(st.mode_keys):
            st.mode_keys.remove(self.index)
            st.active_mode_key = min(st.active_mode_key, len(st.mode_keys) - 1)
            _redraw_ui()
            return {"FINISHED"}
        return {"CANCELLED"}


# Playback helper (simple, scoped to selected Action)
_playback = {"handler": None, "end": None}


def _stop_play():
    if _playback["handler"]:
        try:
            bpy.app.handlers.frame_change_post.remove(_playback["handler"])
        except:  # pylint: disable=bare-except
            pass
    _playback["handler"] = None
    _playback["end"] = None
    try:
        if bpy.context.screen and bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
    except:  # pylint: disable=bare-except
        pass


def _on_frame(scene, _deps):
    endf = _playback.get("end")
    if endf is not None and scene.frame_current >= endf:
        _stop_play()


def _assign_action(arm: bpy.types.Object, act: bpy.types.Action):
    # robust for Blender 3.x/4.x
    if not arm.animation_data:
        arm.animation_data_create()
    arm.animation_data.action = act


def _frame_from_nrange(act: bpy.types.Action, n0: float, n1: float) -> Tuple[int, int]:
    f0, f1 = act.frame_range
    span = max(1.0, (f1 - f0))
    a = max(0.0, min(1.0, float(n0)))
    b = max(0.0, min(1.0, float(n1)))
    if b <= a:
        b = min(1.0, a + 0.01)
    start_f = int(round(f0 + a * span))
    end_f = int(round(f0 + b * span))
    end_f = max(start_f + 1, end_f)
    return start_f, end_f


class DRS_OT_PlayRange(bpy.types.Operator):
    bl_idname = "drs.animset_play_range"
    bl_label = "Play"
    bl_options = {"INTERNAL"}

    mode_key_index: IntProperty(default=-1)  # type: ignore
    n0: FloatProperty(default=0.0)  # type: ignore
    n1: FloatProperty(default=1.0)  # type: ignore

    def execute(self, context):
        st = _state()
        if not 0 <= self.mode_key_index < len(st.mode_keys):
            return {"CANCELLED"}
        mk = st.mode_keys[self.mode_key_index]
        if not 0 <= mk.active_variant < len(mk.variants):
            return {"CANCELLED"}
        v = mk.variants[mk.active_variant]
        act_name = (v.file or "").strip()
        act = (
            bpy.data.actions.get(act_name) if act_name and act_name != "NONE" else None
        )

        model = _active_model()
        arm = _find_armature(model) if model else None
        if not (act and arm):
            return {"CANCELLED"}

        _assign_action(arm, act)
        start_f, end_f = _frame_from_nrange(act, self.n0, self.n1)

        _stop_play()
        context.scene.frame_current = start_f
        context.scene.frame_start = start_f
        context.scene.frame_end = end_f
        _playback["end"] = end_f

        if not _playback["handler"]:
            _playback["handler"] = _on_frame
            bpy.app.handlers.frame_change_post.append(_on_frame)
        try:
            bpy.context.scene.show_subframe = True
            bpy.ops.screen.animation_play()
        except:  # pylint: disable=bare-except
            pass
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# UI: Standalone Window Operator
# ---------------------------------------------------------------------------


# Menus for adding abilities with uniqueness
def _available_abilities_for_mode(mode_val: int) -> list[str]:
    st = _state()
    target = int(mode_val)
    present_ids = {(int(m.vis_job), int(m.special_mode)) for m in st.mode_keys}
    out = []
    for name, data in _iter_all_abilities().items():
        # if all comps would be duplicates, we skip
        comps = data.get("components", []) or []
        if not comps:
            continue
        any_new = False
        for c in comps:
            try:
                vis = int(c.get("vis_job_id"))
            except:  # pylint: disable=bare-except
                continue
            if (vis, target) not in present_ids:
                any_new = True
                break
        if any_new:
            out.append(name)
    return sorted(out, key=str.lower)


class DRS_OT_SelectAbility(bpy.types.Operator):
    bl_idname = "drs.animset_select_ability"
    bl_label = "Select"
    bl_options = {"INTERNAL"}
    index: IntProperty(default=-1)  # type: ignore

    def execute(self, _ctx):
        st = _state()
        if 0 <= self.index < len(st.mode_keys):
            st.active_mode_key = self.index
            return {"FINISHED"}
        return {"CANCELLED"}


class DRS_OT_AnimSet_Save(bpy.types.Operator):
    """Write current editor state to the active model's AnimationSet blob."""

    bl_idname = "drs.animset_save"
    bl_label = "Save"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        col = _active_model()
        if not col:
            return {"CANCELLED"}
        _write_state_to_blob(col)
        return {"FINISHED"}


class DRS_OT_AnimSet_Reload(bpy.types.Operator):
    """Reload animation set data from the active model's AnimationSet blob."""

    bl_idname = "drs.animset_reload"
    bl_label = "Reload"
    bl_options = {"INTERNAL"}

    def execute(self, _ctx):
        col = _active_model()
        if not col:
            return {"CANCELLED"}
        _refresh_state_from_blob(col)
        return {"FINISHED"}


# Small helper for drawing variants
def _draw_variant_editor(
    layout, mk_index: int, mk: ModeKeyPG, is_cast: bool = False, is_sle: bool = False
):
    box = layout.box()
    row = box.row()
    row.label(text="Variants")
    side = row.row(align=True)
    add = side.operator("drs.variant_add", text="", icon="ADD")
    add.index = mk_index
    rem = side.operator("drs.variant_remove", text="", icon="REMOVE")
    rem.index = mk_index

    row = box.row()
    row.template_list(
        "DRS_UL_Variants", "", mk, "variants", mk, "active_variant", rows=2
    )

    if 0 <= mk.active_variant < len(mk.variants):
        v = mk.variants[mk.active_variant]
        det = box.box()
        det.use_property_split = True
        det.use_property_decorate = False
        det.prop(v, "file", text="Action")
        det.prop(v, "weight")
        det.prop(v, "allows_ik")
        det.prop(v, "force_no_blend")
        # det.prop(v, "start")
        if is_cast:
            # End belongs to slider; show locked (no explicit Resolve part UI)
            v.end = mk.cast_to_resolve
            row = det.row()
            row.enabled = False
            # row.prop(v, "end", text="End (Resolve)")
        else:
            # det.prop(v, "end")
            pass

        if not is_sle and not is_cast:
            pr = det.row(align=True)
            op = pr.operator("drs.animset_play_range", text="Play", icon="PLAY")
            op.mode_key_index, op.n0, op.n1 = mk_index, float(v.start), float(v.end)


class DRS_UL_Variants(bpy.types.UIList):
    def draw_item(self, _ctx, layout, _data, item: AnimVariantPG, _icon, _act, _flt):
        row = layout.row(align=True)
        row.label(
            text=item.file if item.file and item.file != "NONE" else "<None>",
            icon="ACTION",
        )
        row.label(text=f"{int(item.weight)}%")
        row.label(text=f"{item.start:.2f}–{item.end:.2f}")


class DRS_OT_VariantAdd(bpy.types.Operator):
    bl_idname = "drs.variant_add"
    bl_label = "Add Variant"
    bl_options = {"INTERNAL"}
    index: IntProperty(default=-1)  # type: ignore

    def execute(self, _ctx):
        st = _state()
        if not 0 <= self.index < len(st.mode_keys):
            return {"CANCELLED"}
        mk = st.mode_keys[self.index]
        v = mk.variants.add()
        v.weight, v.start, v.end, v.allows_ik, v.file, v.force_no_blend = (
            100,
            0.0,
            1.0,
            True,
            "NONE",
            False,
        )
        mk.active_variant = len(mk.variants) - 1
        _redraw_ui()
        return {"FINISHED"}


class DRS_OT_VariantRemove(bpy.types.Operator):
    bl_idname = "drs.variant_remove"
    bl_label = "Remove Variant"
    bl_options = {"INTERNAL"}
    index: IntProperty(default=-1)  # type: ignore

    def execute(self, _ctx):
        st = _state()
        if not 0 <= self.index < len(st.mode_keys):
            return {"CANCELLED"}
        mk = st.mode_keys[self.index]
        i = mk.active_variant
        if 0 <= i < len(mk.variants):
            mk.variants.remove(i)
            mk.active_variant = min(i, len(mk.variants) - 1)
        _redraw_ui()
        return {"FINISHED"}


class DRS_PT_AnimSetEditorDock(bpy.types.Panel):
    bl_idname = "DRS_PT_AnimSetEditorDock"
    bl_label = "AnimationSet Editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, _ctx):
        _draw_editor_ui(self.layout)


class DRS_OT_OpenAnimSetEditorWindow(bpy.types.Operator):
    bl_idname = "drs.open_animset_editor_window"
    bl_label = "Open AnimationSet Editor (Window)"
    bl_description = "Open a dedicated window with the AnimationSet Editor sidebar"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        # Preload state if possible (but we open either way)
        col = _active_model()
        if col:
            _refresh_state_from_blob(col)

        # Create new window
        bpy.ops.wm.window_new()
        win = bpy.context.window_manager.windows[-1]

        # Configure the new window: set area to VIEW_3D and open the N-panel
        with bpy.context.temp_override(window=win):
            # Pick first non-statusbar area
            area = next((a for a in win.screen.areas if a.type != "STATUSBAR"), None)
            if not area:
                self.report({"ERROR"}, "No usable area in new window.")
                return {"CANCELLED"}

            area.type = "VIEW_3D"
            space = area.spaces.active
            # Ensure sidebar (N-panel) is visible
            try:
                space.show_region_ui = True
            except Exception:  # pylint: disable=broad-exception-caught
                pass

            # Optional: reduce clutter (hide toolbar)
            try:
                space.show_region_tool_header = False
                space.show_region_toolbar = False
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        return {"FINISHED"}


# ---- Searchable picker operator --------------------------------------------


class AbilityPickItemPG(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()  # type: ignore
    description: bpy.props.StringProperty()  # type: ignore
    category: bpy.props.StringProperty(default="")  # type: ignore
    available: bpy.props.BoolProperty(default=True)  # type: ignore
    selected: bpy.props.BoolProperty(default=False)  # type: ignore


class DRS_UL_AbilityPicker(bpy.types.UIList):
    bl_idname = "DRS_UL_AbilityPicker"

    def draw_filter(self, _ctx, layout):
        row = layout.row(align=True)
        row.prop(self, "filter_name", text="", icon="VIEWZOOM")
        row.prop(self, "use_filter_sort_alpha", text="", icon="SORTALPHA", toggle=True)
        row.prop(self, "use_filter_sort_reverse", text="", icon="SORT_ASC", toggle=True)

    def draw_item(
        self, _ctx, layout, _data, item: AbilityPickItemPG, _icon, _active, _flt
    ):
        row = layout.row(align=True)
        row.enabled = bool(getattr(item, "available", True))
        row.prop(item, "selected", text="")
        col = row.column(align=False)
        col.label(text=item.name, icon="ANIM_DATA")
        desc = getattr(item, "description", "")
        self.use_filter_show = True
        if desc:
            sub = col.row()
            sub.enabled = False
            sub.label(text=desc)
        row.label(text=getattr(item, "category", ""), icon="OUTLINER")

    def filter_items(self, _ctx, data, propname):
        items = getattr(data, propname, [])
        flt_flags = [self.bitflag_filter_item] * len(items)

        patt = (self.filter_name or "").lower().strip()
        if patt:
            for i, it in enumerate(items):
                hay = f"{it.name} {getattr(it, 'description', '')}".lower()
                flt_flags[i] = self.bitflag_filter_item if patt in hay else 0

        flt_neworder = []
        if self.use_filter_sort_alpha:
            order = sorted(range(len(items)), key=lambda i: items[i].name.lower())
            if self.use_filter_sort_reverse:
                order.reverse()
            flt_neworder = order

        return flt_flags, flt_neworder


class DRS_OT_OpenAbilityPicker(bpy.types.Operator):
    bl_idname = "drs.open_ability_picker"
    bl_label = "Add Ability…"
    bl_options = {"REGISTER", "INTERNAL"}

    items: bpy.props.CollectionProperty(type=AbilityPickItemPG)  # type: ignore
    active_index: bpy.props.IntProperty(default=0)  # type: ignore
    mode: bpy.props.IntProperty(default=0)  # type: ignore

    def _rebuild_items(self, _ctx):
        _fill_picker_items(self.items, self.mode)
        self.active_index = min(max(0, self.active_index), max(0, len(self.items) - 1))

    def invoke(self, context, event):
        self.mode = _current_mode()
        self._rebuild_items(context)
        return context.window_manager.invoke_props_dialog(self, width=700)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.template_list(
            "DRS_UL_AbilityPicker", "", self, "items", self, "active_index", rows=12
        )
        row = layout.row()
        row.label(text=f"Target: {_mode_label(self.mode)}")
        row.separator()
        row.label(text="Enter to add", icon="KEYTYPE_KEYFRAME_VEC")

    def execute(self, context):
        # collect all checked items
        selected_names = [
            it.name
            for it in self.items
            if getattr(it, "selected", False) and getattr(it, "available", True)
        ]

        # fallback: if nothing checked, use the active row
        if not selected_names and (0 <= self.active_index < len(self.items)):
            selected_names = [self.items[self.active_index].name]

        if not selected_names:
            return {"CANCELLED"}

        any_added = False
        for ability_name in selected_names:
            try:
                res = bpy.ops.drs.modekey_add_ability(
                    "EXEC_DEFAULT", ability=ability_name, mode=int(self.mode)
                )
                any_added = any_added or ("FINISHED" in res)
            except Exception as e:
                self.report({"ERROR"}, f"Failed to add '{ability_name}': {e}")

        # Rebuild list so newly-added abilities disappear from the picker
        try:
            self._rebuild_items(context)
        except Exception:
            pass

        _redraw_ui()
        return {"FINISHED"} if any_added else {"CANCELLED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    AnimVariantPG,
    ModeKeyPG,
    AnimSetState,
    DRS_OT_AnimSet_InitUnit,
    DRS_OT_AnimSet_ClearAll,
    DRS_OT_AnimSet_Reinit,
    DRS_OT_ModeKey_AddAbility,
    DRS_OT_ModeKey_Remove,
    DRS_OT_PlayRange,
    DRS_UL_Variants,
    DRS_OT_VariantAdd,
    DRS_OT_VariantRemove,
    DRS_OT_SelectAbility,
    DRS_OT_AnimSet_Save,
    DRS_OT_AnimSet_Reload,
    DRS_PT_AnimSetEditorDock,
    DRS_OT_OpenAnimSetEditorWindow,
    AbilityPickItemPG,
    DRS_UL_AbilityPicker,
    DRS_OT_OpenAbilityPicker,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.drs_anim_state = PointerProperty(type=AnimSetState)
    bpy.app.timers.register(_poll_editor_refresh, first_interval=0.5, persistent=True)


def unregister():
    del bpy.types.WindowManager.drs_anim_state
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
