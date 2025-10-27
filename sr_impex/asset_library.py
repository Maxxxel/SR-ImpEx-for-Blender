# asset_library.py
# DRS Side Panel → Asset Library
# Blender 4.x

from __future__ import annotations
import bpy
import os, json, time, traceback, subprocess
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel, AddonPreferences

resource_dir = os.path.dirname(os.path.realpath(__file__)) + "/resources"

# --- Paths & helpers ---------------------------------------------------------

def _addon_pkg_name() -> str:
    # e.g. "sr_impex"
    return __package__.split(".")[0] if "." in __package__ else __package__

def _addon_mod():
    return bpy.context.preferences.addons.get(_addon_pkg_name())

def _prefs() -> AddonPreferences | None:
    mod = _addon_mod()
    return getattr(mod, "preferences", None) if mod else None

def _addon_dir() -> str:
    return resource_dir

def _cache_dir() -> str:
    d = os.path.join(_addon_dir(), "asset_cache")
    os.makedirs(d, exist_ok=True)
    return d

def _cache_json_path() -> str:
    return os.path.join(_cache_dir(), "assets_index.json")

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"

def _status_text() -> str:
    path = _cache_json_path()
    if not os.path.exists(path):
        return "empty"
    st = os.stat(path)
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
    return f"cached at {dt} (size: {_fmt_size(st.st_size)})"

def _sound_cache_dir(base_name: str) -> str:
    d = os.path.join(_cache_dir(), "sounds", base_name)
    os.makedirs(d, exist_ok=True)
    return d

def _vgmstream_cli() -> str:
    return os.path.join(_addon_dir(), "vgmstream", "vgmstream-cli.exe" if os.name == "nt" else "vgmstream-cli")

# --- Index helpers -----------------------------------------------------------

def load_assets_index() -> dict:
    p = _cache_json_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        traceback.print_exc()
        return {}

_KNOWN_LANGS = {"de","en","fr","it","pl","ru","es","cz","tr","cn","tw","uk","us"}

def _guess_lang_from_path(rel_path: str) -> str:
    # examples:
    # bf1\sound\de\ram\ack_xxx.snr -> de
    # bf1\sound\ram\ack_xxx.snr     -> (neutral) use "ram"
    parts = rel_path.replace("/", "\\").split("\\")
    try:
        i = parts.index("sound")
    except ValueError:
        return "ram"
    if i+1 < len(parts) and parts[i+1].lower() in _KNOWN_LANGS:
        return parts[i+1].lower()
    return "ram"

def sound_candidates_for_base(base_name: str) -> dict:
    """
    Returns {lang: {'path': rel_path_in_pak, 'pak': pak_name}} for a base like 'ack_enforcer_strike1'.
    Uses assets_index.json which currently maps rel_path -> pak_name.
    """
    idx = load_assets_index()
    files = idx.get("files") or {}
    # Support both dict {path:pak} and list of entries
    if isinstance(files, list):
        # older dummy format — normalize to dict if possible
        mapping = {}
        for entry in files:
            p = entry.get("path") or entry.get("name")
            if p:
                mapping[p] = entry.get("pak") or entry.get("archive") or ""
        files = mapping
    out = {}
    needle = base_name.lower() + ".snr"
    for rel_path, pak in files.items():
        rp = str(rel_path)
        if rp.lower().endswith(needle):
            lang = _guess_lang_from_path(rp)
            out[lang] = {"path": rp, "pak": pak}
    return out

def is_sound_cached(base_name: str, langs: list[str] | None = None) -> bool:
    d = _sound_cache_dir(base_name)
    if not os.path.isdir(d):
        return False
    # if langs provided, require at least those .snr present
    if langs:
        for lg in langs:
            if not os.path.exists(os.path.join(d, f"{lg}.snr")):
                return False
        return True
    # otherwise check any file
    return any(name.endswith(".snr") or name.endswith(".wav") for name in os.listdir(d))

def _convert_snr_to_wav(snr_path: str, wav_path: str) -> None:
    exe = _vgmstream_cli()
    if not os.path.exists(exe):
        raise RuntimeError("vgmstream-cli.exe not found in resources/vgmstream/")
    # vgmstream-cli.exe -o out.wav infile.snr
    # avoid flashing console windows; still simple Popen is fine
    subprocess.check_call([exe, "-o", wav_path, snr_path])

# --- Sound extraction hook (delegates to pak_indexer if available) -----------

def _extract_from_pak_if_possible(game_root: str, rel_path: str, pak_name: str, out_file: str) -> None:
    """
    Ask pak_indexer to extract a single file by its rel_path from pak_name into out_file.
    Must be implemented in pak_indexer as extract_single(root, pak_name, rel_path, out_file).
    """
    try:
        from . import pak_indexer
        if hasattr(pak_indexer, "extract_single"):
            pak_indexer.extract_single(game_root, pak_name, rel_path, out_file)
            return
    except Exception:
        traceback.print_exc()
    raise RuntimeError("No extractor available. Implement pak_indexer.extract_single(...)")


# --- Operators ---------------------------------------------------------------

class DRS_OT_assetlib_create(Operator):
    bl_idname = "drs.assetlib_create"
    bl_label = "Create Asset Index"
    bl_description = "Parse game PAKs and build an asset index JSON"

    def execute(self, _ctx):
        prefs = _prefs()
        root = getattr(prefs, "skylords_root", "") if prefs else ""
        if not root or not os.path.isdir(root):
            self.report({"ERROR"}, "Please set a valid Skylords Reborn folder first.")
            return {"CANCELLED"}

        out_json = _cache_json_path()
        os.makedirs(os.path.dirname(out_json), exist_ok=True)

        # Try to call user-provided parser if available
        used_external = False
        try:
            from . import pak_indexer  # you add this file later
            if hasattr(pak_indexer, "build_index"):
                pak_indexer.build_index(root, out_json)  # <-- your real parser hook
                used_external = True
        except Exception:
            # Show a short trace in console but continue with minimal index
            print("[AssetLibrary] pak_indexer.build_index failed or missing:")
            traceback.print_exc()

        if not used_external:
            # Minimal index so UI isn't empty (replace by your parser anytime)
            data = {
                "version": 1,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "root": os.path.abspath(root),
                "files": [],  # your parser should fill this with {name, pak, ...}
            }
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

        self.report({"INFO"}, f"Asset index written: {out_json}")
        return {"FINISHED"}


class DRS_OT_assetlib_check(Operator):
    bl_idname = "drs.assetlib_check"
    bl_label = "Check"
    bl_description = "Display current cache status in the panel"

    def execute(self, _ctx):
        self.report({"INFO"}, _status_text())
        return {"FINISHED"}


class DRS_OT_assetlib_remove(Operator):
    bl_idname = "drs.assetlib_remove"
    bl_label = "Remove Cache"
    bl_description = "Delete the cached asset index"

    confirm: BoolProperty(default=True)

    def execute(self, _ctx):
        p = _cache_json_path()
        if os.path.exists(p):
            try:
                os.remove(p)
                self.report({"INFO"}, "Asset cache removed.")
            except Exception as e:
                self.report({"ERROR"}, f"Failed to remove cache: {e}")
                return {"CANCELLED"}
        else:
            self.report({"INFO"}, "No cache file found.")
        return {"FINISHED"}

# --- Sound: read/extract + convert -------------------------------------------

class DRS_OT_assetlib_sound_read(Operator):
    """Read all language variants for a given sound base, extract .snr and convert to .wav."""
    bl_idname = "drs.assetlib_sound_read"
    bl_label = "Read file"
    bl_options = {"INTERNAL"}

    base_name: StringProperty(default="")  # e.g. 'ack_enforcer_strike1'

    def execute(self, _ctx):
        prefs = _prefs()
        game_root = getattr(prefs, "skylords_root", "") if prefs else ""
        if not game_root or not os.path.isdir(game_root):
            self.report({"ERROR"}, "Set a valid Skylords path in Add-on Preferences first.")
            return {"CANCELLED"}

        base = (self.base_name or "").strip()
        if not base:
            self.report({"ERROR"}, "Missing sound base name.")
            return {"CANCELLED"}

        candidates = sound_candidates_for_base(base)
        if not candidates:
            self.report({"ERROR"}, f"No entries in asset index for '{base}'.")
            return {"CANCELLED"}

        out_dir = _sound_cache_dir(base)
        ok_count = 0
        for lang, info in candidates.items():
            rel_path = info["path"]
            pak = info["pak"]
            snr_out = os.path.join(out_dir, f"{lang}.snr")
            wav_out = os.path.join(out_dir, f"{lang}.wav")
            try:
                if not os.path.exists(snr_out):
                    _extract_from_pak_if_possible(game_root, rel_path, pak, snr_out)
                # convert every time if snr newer or wav missing
                if (not os.path.exists(wav_out)) or (os.path.getmtime(snr_out) > os.path.getmtime(wav_out)):
                    _convert_snr_to_wav(snr_out, wav_out)
                ok_count += 1
            except Exception as e:
                self.report({"WARNING"}, f"{lang}: {e}")
        if ok_count == 0:
            self.report({"ERROR"}, "Failed to read any language file.")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Read {ok_count} file(s) for '{base}'.")
        return {"FINISHED"}

# --- UI Panel ----------------------------------------------------------------

class DRS_PT_AssetLibrary(Panel):
    bl_label = "Asset Library"
    bl_idname = "DRS_PT_AssetLibrary"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"

    def draw(self, context):
        layout = self.layout
        prefs = _prefs()

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Game Path", icon="FILE_FOLDER")
        row = box.row()
        if prefs:
            row.prop(prefs, "skylords_root", text="")  # DIR_PATH in AddonPreferences
        else:
            row.label(text="Addon preferences unavailable", icon="ERROR")

        box.separator()
        col = box.column(align=True)
        col.label(text=f"Status: {_status_text()}", icon="INFO")

        row = box.row(align=True)
        row.operator("drs.assetlib_create", text="Create", icon="ADD")
        row.operator("drs.assetlib_check", text="Check", icon="FILE_REFRESH")
        row.operator("drs.assetlib_remove", text="Remove", icon="TRASH")

# --- Registration ------------------------------------------------------------

CLASSES = (
    DRS_OT_assetlib_create,
    DRS_OT_assetlib_check,
    DRS_OT_assetlib_remove,
    DRS_PT_AssetLibrary,
    DRS_OT_assetlib_sound_read,
)

# def register():
#     for c in CLASSES:
#         bpy.utils.register_class(c)

# def unregister():
#     for c in reversed(CLASSES):
#         bpy.utils.unregister_class(c)
