# drs_resolvers.py
from __future__ import annotations
import json, os
from typing import Optional
import bpy

_BL_MAX = 63

def _active_top_drsmodel() -> bpy.types.Collection | None:
    """Return the active top-level DRSModel_* collection if available."""
    try:
        col = bpy.context.view_layer.active_layer_collection.collection
        if col and isinstance(col, bpy.types.Collection):
            # Climb to top-most DRSModel_* in the chain
            top = col
            while top and top.name and not top.name.startswith("DRSModel_"):
                # Go up via users_collection if available
                parents = getattr(top, "users_collection", []) or []
                top = parents[0] if parents else None
            if top and top.name.startswith("DRSModel_"):
                return top
    except Exception:
        pass
    # Fallback: scan for an active-like DRSModel_ in the scene
    for c in bpy.data.collections:
        if c.name.startswith("DRSModel_"):
            return c
    return None


def resolve_action_from_blob_name(filename_or_action: str,
                                  model_col: bpy.types.Collection | None = None) -> str:
    """
    Resolve a blob filename (e.g. 'skel_human_idle1.ska') or a raw action name to an
    existing bpy.data.actions entry using the same priority rules the AnimationSet editor uses:

      1) Model mapping on the active top-level DRSModel_* collection (_drs_action_map JSON)
      2) Exact name in bpy.data.actions
      3) .ska <-> no .ska
      4) Blender 63-char truncation (+ numbered variants like 'name.001')
      5) Best common-prefix fallback

    Returns a valid Action name, or 'NONE' if no reasonable match exists.
    """
    want = (filename_or_action or "").strip()
    if not want:
        return "NONE"

    base = want[:-4] if want.lower().endswith(".ska") else want
    names = [a.name for a in bpy.data.actions]
    name_set = set(names)

    # 1) importer mapping on the model collection
    col = model_col or _active_top_drsmodel()
    if col:
        try:
            raw = col.get("_drs_action_map", "{}")
            mp = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            mp = {}
        for key in (want, os.path.basename(want), base, os.path.basename(base)):
            act = mp.get(key)
            if act and act in name_set:
                return act

    def hit(cand: str) -> Optional[str]:
        return cand if cand in name_set else None

    # 2) exact
    if hit(want):
        return want
    # 3) with/without .ska
    if hit(base):
        return base
    if hit(base + ".ska"):
        return base + ".ska"

    # 4) Blender’s 63-char truncation (+ numbered)
    t_want, t_base, t_with_ska = want[:_BL_MAX], base[:_BL_MAX], (base + ".ska")[:_BL_MAX]
    for cand in (t_want, t_base, t_with_ska):
        h = hit(cand)
        if h:
            return h
    # …numbered collisions, prefer the lowest suffix
    prefix = t_base.rstrip(".")
    numbered = [n for n in names if n.startswith(prefix + ".")]
    if numbered:
        def parse_suffix(nm: str):
            try:
                return int(nm.split(".")[-1])
            except Exception:
                return 10**9
        numbered.sort(key=parse_suffix)
        return numbered[0]

    # 5) weak prefix heuristic
    best = None
    best_score = -1
    for n in names:
        nb = n[:-4] if n.lower().endswith(".ska") else n
        score = len(os.path.commonprefix([nb, base]))
        if score > best_score:
            best_score, best = score, n
    return best if best and best_score >= max(8, len(base) // 2) else "NONE"
