"""Persist library paths independently of Blender's Save Preferences toggle."""
import json
import os
from pathlib import Path
import tempfile
import bpy

FIELDS=('skylords_root','effects_folder')
_restoring=False
_edited=False
_initialized=False


def config_path():
    return Path(bpy.utils.user_resource('CONFIG',path='sr_impex',create=True))/'asset_library.json'


def saved_paths():
    candidates=[]
    for path in (config_path(),shared_path()):
        try:
            data=json.loads(path.read_text(encoding='utf8'))
            values={key:data[key] for key in FIELDS if isinstance(data.get(key),str)}
            if values:candidates.append((path.stat().st_mtime_ns,values))
        except (OSError,ValueError,TypeError,AttributeError):pass
    return max(candidates,key=lambda row:row[0])[1] if candidates else {}


def shared_path():
    override=os.environ.get('SR_IMPEX_ASSET_CONFIG')
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'SRImpEx'/'settings'/'asset_library.json'


def _save(values):
    for path in {config_path(),shared_path()}:
        temporary=None
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,delete=False) as stream:
                temporary=Path(stream.name);json.dump(values,stream)
            os.replace(temporary,path)
        except OSError as exc:print(f'SR ImpEx: could not save asset library paths to {path}: {exc}')
        finally:
            try:
                if temporary and temporary.exists():temporary.unlink()
            except OSError:pass


def changed(prefs,context):
    global _edited
    if _restoring:return
    values={key:bpy.path.abspath(getattr(prefs,key,'') or '') for key in FIELDS}
    # RNA initialization/reset during enable must not overwrite saved paths
    # with empty defaults before the deferred restore has run.
    if not _initialized and not _edited and not any(values.values()) and any(saved_paths().values()):return
    _edited=True;_save(values)


def preferences(context):
    addons=context.preferences.addons
    addon=addons.get('sr_impex') or next((a for a in addons if a.module.endswith('.sr_impex')),None)
    return addon.preferences if addon else None


def restore(context=None):
    global _restoring,_initialized
    context=context or bpy.context;prefs=preferences(context)
    if prefs is None:return False
    _initialized=True
    if _edited:return True
    data=saved_paths();_restoring=True
    try:
        for key in FIELDS:
            if key in data and getattr(prefs,key,'')!=data[key]:setattr(prefs,key,data[key])
    finally:_restoring=False
    if not data:
        values={key:bpy.path.abspath(getattr(prefs,key,'') or '') for key in FIELDS}
        if any(values.values()):_save(values)
    return True


def paths(context):
    restore(context)
    prefs=preferences(context);data=saved_paths()
    return tuple(bpy.path.abspath(getattr(prefs,key,'') if prefs else data.get(key,'')) for key in FIELDS)


def _restore_after_enable():
    return None if restore() else .25


def register():
    global _edited,_initialized
    _edited=False;_initialized=False
    if not bpy.app.timers.is_registered(_restore_after_enable):
        bpy.app.timers.register(_restore_after_enable,first_interval=.1)


def unregister():
    if bpy.app.timers.is_registered(_restore_after_enable):bpy.app.timers.unregister(_restore_after_enable)
