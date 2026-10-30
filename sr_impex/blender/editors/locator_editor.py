# locator_editor.py
# Minimal, robust CDrwLocatorList editor (Blender 4.x)
# - Single JSON blob stored on the DRSModel_* collection
# - UID per locator object for perfect scene<->blob matching
# - Bone-local vs world transforms via simple rule:
#     bone_id >= 0 -> local (parented to bone)
#     bone_id == -1 -> world (no parent)

from __future__ import annotations
import json
import uuid
from typing import Dict, List, Optional
import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatVectorProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
    BoolProperty,
)
from mathutils import Matrix, Vector

# ---- Imports from your DRS definitions --------------------------------------

from sr_impex.definitions.locator_definitions import (
    CDrwLocatorList,
    SLocator,
    CMatCoordinateSystem,
)
from sr_impex.definitions.enums import LocatorClass
from sr_impex.definitions.base_types import Matrix3x3, Vector3

# ---- Constants ---------------------------------------------------------------

BLOB_KEY = "CDrwLocatorListJSON"
UID_KEY = "_cdrw_uid"
LOCATOR_PREFIX = "Locator_"
SLOCATORS_COLLECTION_NAME = "SLocators_Collection"

_LOCATOR_LABELS = {
    0: "Health Bar", 1: "Model Attachment", 2: "Construction",
    3: "Turret / Weapon Animation", 4: "Figure State FX",
    5: "Wheel / Terrain Attachment", 6: "Persistent Building FX",
    7: "Building Hit Offset", 8: "Persistent Figure FX",
    9: "Damage Flame: Small", 10: "Damage Flame: Small + Smoke",
    11: "Damage Flame: Large", 12: "Damage Smoke", 13: "Damage Flame: Huge",
    14: "Unverified (14)", 15: "Unverified (15)", 16: "Figure Hit Offset",
    17: "Spell Hit", 18: "Spell Cast (retained name only)", 29: "Projectile Spawn",
}
_LOCATOR_NOTES = {
    14: "No class-specific BF/SR consumer verified. Not SpellCast; preserve ID 14 unchanged.",
    15: "No class-specific BF/SR consumer verified. Not SpellHitAll; preserve ID 15 unchanged.",
    17: "Active slot lookup: Spell Hit / SpellHit. Retained name: SpellHitAll. Spell-event usage is untested.",
    18: "SpellCast is a retained engine name at ID 18; no active BF/SR slot consumer verified.",
}
LOCATOR_TYPE_ENUM = [
    (str(k), _LOCATOR_LABELS.get(k, v), _LOCATOR_NOTES.get(k, f"BattleForge / Skylords locator class {k}"), k)
    for k, v in sorted(LocatorClass.items()) if k not in {14, 15}
]
_LOCATOR_ENUM_CACHE = {}
_REFRESHING = False
_PENDING_MODEL = None


def _locator_type_items(item, _context):
    cid = item.class_id
    if cid in LocatorClass and cid not in {14, 15}:
        return LOCATOR_TYPE_ENUM
    # Keep the strings alive, and preserve unknown numeric classes unchanged.
    if cid not in _LOCATOR_ENUM_CACHE:
        _LOCATOR_ENUM_CACHE[cid] = LOCATOR_TYPE_ENUM + [
            (str(cid), f"Unknown ({cid}, preserved)", "Unverified locator class", cid)
        ]
    return _LOCATOR_ENUM_CACHE[cid]


def _resolve_model(name, session_uid):
    if not name or not session_uid:
        return None
    col = bpy.data.collections.get(name)
    if col is not None and str(col.session_uid) == session_uid:
        return col
    # Renaming a collection must not discard a locator-editing draft.
    return next((c for c in bpy.data.collections if str(c.session_uid) == session_uid), None)

# ---- Basic helpers -----------------------------------------------------------


def _flatten_m3(m) -> List[float]:
    """Return 9 floats row-major."""
    try:
        return [float(m[i][j]) for i in range(3) for j in range(3)]
    except Exception:
        v = list(m)
        if len(v) == 9:
            return [float(x) for x in v]
        return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def _m3_from_list(r9: List[float]) -> Matrix:
    r = list(r9) + [0.0] * (9 - len(r9))
    return Matrix(((r[0], r[1], r[2]), (r[3], r[4], r[5]), (r[6], r[7], r[8])))


def _active_top_drsmodel(context=None) -> Optional[bpy.types.Collection]:
    ctx = context or bpy.context
    from sr_impex.utilities.artist_context import find_model
    model=find_model(ctx)
    return model if model and model in list(ctx.scene.collection.children) else None


def _find_armature(col: bpy.types.Collection) -> Optional[bpy.types.Object]:
    if col is None:
        return None
    def visit(c: bpy.types.Collection) -> Optional[bpy.types.Object]:
        for o in c.objects:
            if o.type == "ARMATURE" and "Control_Rig" not in o.name:
                return o
        for ch in c.children:
            a = visit(ch)
            if a:
                return a
        return None

    return visit(col)


def _find_game_orientation(root: bpy.types.Collection) -> Optional[bpy.types.Object]:
    """Find the 'GameOrientation' object in the model collection tree."""
    target_name = "GameOrientation"

    def visit(c: bpy.types.Collection) -> Optional[bpy.types.Object]:
        for o in c.objects:
            if o.name == target_name:
                return o
        for ch in c.children:
            r = visit(ch)
            if r:
                return r
        return None

    return visit(root)


def _ensure_locators_collection(root: bpy.types.Collection) -> bpy.types.Collection:
    col = root.children.get(SLOCATORS_COLLECTION_NAME)
    if not col:
        col = bpy.data.collections.new(SLOCATORS_COLLECTION_NAME)
        root.children.link(col)
    return col


def _read_blob(col: bpy.types.Collection) -> Dict:
    data = col.get(BLOB_KEY)
    if not data:
        return {"version": 5, "locators": []}
    try:
        b = json.loads(data)
        if "locators" not in b:
            b["locators"] = []
        return b
    except Exception:
        return {"version": 5, "locators": []}


def _write_blob(col: bpy.types.Collection, blob: Dict) -> None:
    col[BLOB_KEY] = json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


def _bone_name_from_index(arm: bpy.types.Object, idx: int) -> str:
    if not arm or idx is None or idx < 0:
        return ""
    bones = arm.data.bones
    return bones[idx].name if idx < len(bones) else ""


def _bone_index_from_name(arm: bpy.types.Object, name: str) -> int:
    if not arm or not name:
        return -1
    return arm.data.bones.find(name)


def _iter_locator_objects(root: bpy.types.Collection) -> List[bpy.types.Object]:
    out: List[bpy.types.Object] = []

    def visit(c: bpy.types.Collection):
        for o in c.objects:
            if UID_KEY in o.keys() or o.name.startswith(LOCATOR_PREFIX):
                out.append(o)
        for ch in c.children:
            visit(ch)

    visit(root)
    return out


def _object_by_uid(root: bpy.types.Collection, uid: str) -> Optional[bpy.types.Object]:
    for o in _iter_locator_objects(root):
        if o.get(UID_KEY) == uid:
            return o
    return None


def _draw_editor_body(layout: bpy.types.UILayout):
    st = _state()
    col = st.model
    if col is None:
        layout.label(text="Select a model to edit its locators.", icon="INFO")
        return
    arm = _find_armature(col)

    root = layout.column()
    root.use_property_decorate = False
    if not st.items:
        root.label(text='This model has no locators.',icon='INFO')
        root.operator('drs.locator_add',text='Add Locator',icon='ADD')
        return
    listing = root.row()
    listing.template_list(
        "DRS_UL_LocatorList", "", st, "items", st, "active_index", rows=4
    )
    actions = listing.column(align=True)
    actions.operator("drs.locator_add", text="", icon="ADD")
    actions.operator("drs.locator_remove", text="", icon="REMOVE")
    if 0 <= st.active_index < len(st.items):
        it = st.items[st.active_index]
        fields=root.column(align=True)
        _field(fields,'Type').prop(it,'type',text='')
        _field(fields,'Attach to').prop(it,'attachment_mode',text='')
        if it.attachment_mode=='BONE':
            if arm:_field(fields,'Bone').prop_search(it,'parent_bone',arm.data,'bones',text='')
            else:fields.label(text='Import a skeleton to choose a bone.',icon='INFO')
        cid=int(it.type)
        if cid in (1,2,3,4,5,6,8) or it.file:
            is_fx=cid in (4,6,8) or it.file.lower().endswith('.fxb')
            resource=_field(fields,'Effect' if is_fx else 'Resource')
            resource.prop(it,'file',text='')
            if is_fx:resource.operator('drs.effect_selector',text='',icon='VIEWZOOM').target='LOCATOR'
        save=root.row(align=True)
        op=save.operator('drs.locator_save_item',text='Apply Changes',icon='CHECKMARK')
        op.uid=it.uid;op.idx=st.active_index
        save.operator('drs.locator_sync',text='Save Placement',icon='ORIENTATION_LOCAL')
        _draw_fx_tools(root,it)
    else:
        root.label(text="Select a locator to edit its details.", icon="INFO")


def _field(layout,label):
    """Native compact fields with consistent, left-aligned labels."""
    split=layout.row(align=True).split(factor=.24,align=True)
    split.column().label(text=label)
    return split.row(align=True)


def _select_object(obj: Optional[bpy.types.Object]) -> None:
    if not obj:
        return
    # Deselect everything
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    # Select and activate target
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _select_locator_by_uid(root: bpy.types.Collection, uid: str) -> None:
    _select_object(_object_by_uid(root, uid))


# ---- Core: apply/capture/remove ---------------------------------------------


def apply_blob_to_scene(root: bpy.types.Collection, only_uid=None) -> None:
    """Materialize blob to scene. Create/match by UID. Parent & set transforms by rule."""
    blob = _read_blob(root)
    arm = _find_armature(root)
    dst_col = _ensure_locators_collection(root)
    go = _find_game_orientation(root)  # default parent for non-bone locators

    for entry in blob["locators"]:
        if only_uid is not None and entry.get('uid')!=only_uid:continue
        uid = entry.get("uid") or str(uuid.uuid4())
        entry["uid"] = uid
        obj = _object_by_uid(root, uid)

        # Create object if missing
        if not obj:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(0.0, 0.0, 0.0))
            obj = bpy.context.object
            obj.name = f"{LOCATOR_PREFIX}{LocatorClass.get(int(entry.get('class_id', 0)), 'Unknown')}"
            dst_col.objects.link(obj)
            try:
                bpy.context.collection.objects.unlink(obj)
            except Exception:
                pass
            obj[UID_KEY] = uid
            obj.select_set(False)
            bpy.context.view_layer.objects.active = None

        # Read entry transform
        bid_raw = entry.get("bone_id", -1)
        bone_id = int(-1 if bid_raw is None else bid_raw)
        pos = entry.get("pos", [0, 0, 0])
        r9 = entry.get("rot3x3", [1, 0, 0, 0, 1, 0, 0, 0, 1])
        mw = _m3_from_list(r9).to_4x4()
        mw.translation = Vector(pos)

        if bone_id >= 0 and arm:
            # Parent to bone, set LOCAL transform (bone space)
            obj.parent = arm
            obj.parent_type = "BONE"
            obj.parent_bone = _bone_name_from_index(arm, bone_id)
            obj.matrix_parent_inverse.identity()
            obj.location = Vector(pos)
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = _m3_from_list(r9).to_quaternion()
        else:
            # Non-bone: parent to GameOrientation and APPLY its rotation (Y-up -> Z-up)
            if go:
                obj.parent = go
                obj.parent_type = "OBJECT"
                obj.parent_bone = ""
                obj.matrix_parent_inverse.identity()
                # Desired world is GO * (game-space matrix)
                obj.matrix_world = go.matrix_world @ mw
            else:
                obj.parent = None
                obj.matrix_world = mw

        # Optional debug props
        obj["_class_id"] = int(entry.get("class_id", 0))
        if entry.get("file"):
            obj["_file"] = entry.get("file")


def update_blob_from_scene(root: bpy.types.Collection, add_new: bool = True) -> None:
    """Capture scene back into blob. Match by UID. Optionally append new objects."""
    blob = _read_blob(root)
    # arm = _find_armature(root)
    go = _find_game_orientation(root)

    by_uid: Dict[str, Dict] = {
        e.get("uid", ""): e for e in blob["locators"] if e.get("uid")
    }
    changed = False

    for obj in _iter_locator_objects(root):
        uid = obj.get(UID_KEY)
        if not uid:
            if add_new:
                uid = str(uuid.uuid4())
                obj[UID_KEY] = uid
            else:
                continue

        entry = by_uid.get(uid)
        if not entry:
            if not add_new:
                continue
            entry = {
                "uid": uid,
                "class_id": _infer_class_id_from_name(obj.name),
                "file": "",
                "bone_id": -1,
                "uk_int": -1,
                "rot3x3": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "pos": [0, 0, 0],
            }
            blob["locators"].append(entry)
            by_uid[uid] = entry
            changed = True

        if (
            obj.parent_type == "BONE"
            and obj.parent is not None
            and obj.parent.type == "ARMATURE"
            and obj.parent_bone
        ):
            # Bone-local -> store LOCAL (bone space)
            entry["bone_id"] = int(_bone_index_from_name(obj.parent, obj.parent_bone))
            entry["pos"] = list(obj.location)
            entry["rot3x3"] = _flatten_m3(obj.matrix_basis.to_3x3())
        else:
            # Non-bone -> store WORLD IN GAME SPACE
            # Preserve use_parent_minus_two setting when syncing from scene
            use_minus_two = entry.get("use_parent_minus_two", entry.get('bone_id')==-2)
            entry["bone_id"] = -2 if use_minus_two else -1
            if go and obj.parent == go:
                # Remove GO rotation: game_mw = GO^-1 * world
                mw_game = go.matrix_world.inverted() @ obj.matrix_world
            else:
                mw_game = obj.matrix_world
            entry["pos"] = list(mw_game.translation)
            entry["rot3x3"] = _flatten_m3(mw_game.to_3x3())

        if "_class_id" in obj.keys():
            entry["class_id"] = int(obj["_class_id"])
        changed = True

    if changed:
        _write_blob(root, blob)


def remove_locator(
    root: bpy.types.Collection, uid: str, delete_object: bool = True
) -> None:
    blob = _read_blob(root)
    before = len(blob["locators"])
    blob["locators"] = [e for e in blob["locators"] if e.get("uid") != uid]
    if len(blob["locators"]) != before:
        _write_blob(root, blob)
    if delete_object:
        obj = _object_by_uid(root, uid)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)


# ---- Utilities for class/type mapping ---------------------------------------


def _infer_class_id_from_name(name: str) -> int:
    if name.startswith(LOCATOR_PREFIX):
        t = name[len(LOCATOR_PREFIX) :]
        for k, v in LocatorClass.items():
            if v == t:
                return int(k)
    return 0


# ---- Optional conversions (blob <-> CDrwLocatorList) ------------------------


def blob_to_cdrw(blob: Dict) -> CDrwLocatorList:
    ver = int(blob.get("version", 5) or 5)
    sls: List[SLocator] = []
    for e in blob.get("locators", []):
        r = e.get("rot3x3", [1, 0, 0, 0, 1, 0, 0, 0, 1])
        p = e.get("pos", [0, 0, 0])
        m33 = Matrix3x3(
            matrix=tuple(r),
            math_matrix=_m3_from_list(r),
        )
        v3 = Vector3(x=float(p[0]), y=float(p[1]), z=float(p[2]))
        cmat = CMatCoordinateSystem(matrix=m33, position=v3)
        class_id = int(e.get("class_id", 0))
        bone_id = int(e.get("bone_id", -1))
        file_name = e.get("file", "")
        sl = SLocator(
            cmat_coordinate_system=cmat,
            class_id=class_id,
            bone_id=bone_id,
            file_name_length=len(file_name),
            file_name=file_name,
            uk_int=int(e.get("uk_int", -1)),
            class_type=LocatorClass.get(class_id, "Unknown"),
        )
        sls.append(sl)
    return CDrwLocatorList(magic=0, version=ver, length=len(sls), slocators=sls)


# ---- UI state ---------------------------------------------------------------


def _attachment_changed(item,_context):
    if _REFRESHING:return
    if item.attachment_mode!='BONE':
        item.parent_bone=''
        item.use_parent_minus_two=item.attachment_mode=='SKELETON'


def _parent_changed(item,_context):
    if not _REFRESHING and item.parent_bone:item.attachment_mode='BONE'


class LocatorItemPG(bpy.types.PropertyGroup):
    uid: StringProperty(name="UID", default="")  # type: ignore
    class_id: IntProperty(name="Class ID", default=0)  # type: ignore
    type: EnumProperty(name="Type", items=_locator_type_items, default=0)  # type: ignore
    file: StringProperty(name="File", subtype="FILE_PATH", default="")  # type: ignore
    parent_bone: StringProperty(name="Bone", default="",update=_parent_changed)  # type: ignore
    attachment_mode: EnumProperty(name='Attach to',default='MODEL',update=_attachment_changed,items=[
        ('MODEL','Model','Attach to the model node'),
        ('SKELETON','Skeleton','Use the skeleton-aware FX attachment, without selecting one bone. Keep this for effects that use their own bone links'),
        ('BONE','Bone','Follow one selected bone')])  # type: ignore
    bone_id: IntProperty(name="Bone ID", default=-1)  # type: ignore
    uk_int: IntProperty(name="Sub ID", default=-1)  # type: ignore
    rot3x3: FloatVectorProperty(name="Stored orientation", size=9, default=(1, 0, 0, 0, 1, 0, 0, 0, 1))  # type: ignore
    pos: FloatVectorProperty(name="Position", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")  # type: ignore
    use_parent_minus_two: BoolProperty(default=False,options={'HIDDEN'})  # type: ignore

    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "class_id": int(self.class_id),
            "type_name": LocatorClass.get(int(self.class_id), "Unknown"),
            "file": self.file or "",
            "bone_id": int(self.bone_id),
            "uk_int": int(self.uk_int),
            "rot3x3": list(self.rot3x3),
            "pos": list(self.pos),
            "use_parent_minus_two": bool(self.use_parent_minus_two),
        }

    def from_dict(self, d: Dict, arm: Optional[bpy.types.Object]):
        self.uid = d.get("uid", "")
        cid_raw = d.get("class_id", 0)
        self.class_id = int(0 if cid_raw is None else cid_raw)
        self.type = str(self.class_id)
        self.file = d.get("file", "")

        bone_raw = d.get("bone_id", -1)
        self.bone_id = int(-1 if bone_raw is None else bone_raw)

        self.parent_bone = (
            _bone_name_from_index(arm, self.bone_id)
            if (arm and self.bone_id >= 0)
            else ""
        )

        p = d.get("pos", [0, 0, 0])
        self.pos = p

        r = d.get("rot3x3", [1, 0, 0, 0, 1, 0, 0, 0, 1])
        if len(r) == 3 and hasattr(r[0], "__len__"):
            r = [r[i][j] for i in range(3) for j in range(3)]
        self.rot3x3 = r

        uk_raw = d.get("uk_int", -1)
        self.uk_int = int(-1 if uk_raw is None else uk_raw)

        # Load the use_parent_minus_two property; detect from bone_id == -2
        if self.bone_id == -2:
            self.use_parent_minus_two = True
        else:
            self.use_parent_minus_two = bool(d.get("use_parent_minus_two", False))
        self.attachment_mode='BONE' if self.bone_id>=0 else 'SKELETON' if self.use_parent_minus_two else 'MODEL'


class LocatorEditorState(bpy.types.PropertyGroup):
    items: CollectionProperty(type=LocatorItemPG)  # type: ignore

    def _on_active_index_changed(self, _ctx):
        if _REFRESHING:
            return
        try:
            if not self.model or not 0 <= self.active_index < len(self.items):
                return
            uid = self.items[self.active_index].uid
            if uid:
                _select_locator_by_uid(self.model, uid)
        except Exception:
            pass

    active_index: IntProperty(default=0, update=_on_active_index_changed)  # type: ignore
    # Never retain an ID pointer in WindowManager UI state. It can outlive a
    # collection through deletion/undo/file reload (the reported IDP_AssignID crash).
    model_name: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # type: ignore
    model_session_uid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # type: ignore
    notice: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    @property
    def model(self):
        return _resolve_model(self.model_name, self.model_session_uid)

    @model.setter
    def model(self, col):
        self.model_name = col.name if col is not None else ""
        self.model_session_uid = str(col.session_uid) if col is not None else ""


def _state() -> LocatorEditorState:
    return bpy.context.window_manager.drs_locator_state


def selected_fx_item(context):
    state=_state();model=state.model
    if not model or _active_top_drsmodel(context)!=model:raise ValueError('Select this model in Locator Editor')
    if not 0<=state.active_index<len(state.items):raise ValueError('Select an effect locator')
    item=state.items[state.active_index]
    if int(item.type) not in (4,6,8) and not item.file.lower().endswith('.fxb'):
        raise ValueError('This locator does not reference an FX resource')
    return model,item


def preview_resource_blob(model):
    """Preview draft resource edits without changing exported locator records."""
    blob=_read_blob(model);state=_state()
    if state.model==model:
        drafts={item.uid:item for item in state.items}
        for row in blob.get('locators',[]):
            item=drafts.get(row.get('uid'))
            if item and row.get('class_id') in (6,8):row['file']=item.file
    return blob


def _draw_fx_tools(layout,item):
    cid=int(item.type)
    if cid not in (4,6,8) and not item.file.lower().endswith('.fxb'):return
    from . import effect_set_editor as effects
    state=effects._state()
    if cid not in (6,8):
        return
    row=layout.row(align=True)
    row.operator('drs.effect_build_preview',text='Update Preview',icon='FILE_REFRESH').source='LOCATOR'
    row.operator('drs.effect_clear_preview',text='',icon='X')
    options=layout.row(align=True)
    options.prop(state,'preview_audio',text='Audio')
    options.prop(state,'preview_live',text='Live Update')
    model=_state().model
    if (model and effects._live_target==(bpy.context.scene.as_pointer(),model.as_pointer())
            and effects._live_status and effects._live_status not in ('Live preview updated','Preview ready')):
        layout.label(text=effects._live_status,icon='INFO')


def _refresh_state_from_blob(col: bpy.types.Collection):
    global _REFRESHING
    st = _state()
    _REFRESHING = True
    try:
        st.items.clear()
        arm = _find_armature(col)
        blob = _read_blob(col)
        for e in blob.get("locators", []):
            it = st.items.add()
            it.from_dict(e, arm)
        st.active_index = max(0, min(st.active_index, len(st.items) - 1))
        st.notice = ""
    finally:
        _REFRESHING = False


def _request_model_refresh(col):
    global _PENDING_MODEL
    _PENDING_MODEL = (col.name, str(col.session_uid))
    if not bpy.app.timers.is_registered(_apply_pending_refresh):
        bpy.app.timers.register(_apply_pending_refresh, first_interval=0.0)


def _apply_pending_refresh():
    global _PENDING_MODEL
    token, _PENDING_MODEL = _PENDING_MODEL, None
    if token is None:
        return None
    col = _resolve_model(*token)
    # Selection may have moved while the UI draw was finishing.
    if col is None or _active_top_drsmodel() != col:
        return None
    st = _state()
    st.model = col
    try:
        _refresh_state_from_blob(col)
    except Exception as exc:
        st.notice = f"Could not load locators: {exc}"
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
    return None


@persistent
def _invalidate_locator_state(*_args):
    global _PENDING_MODEL
    _PENDING_MODEL = None
    for wm in bpy.data.window_managers:
        if hasattr(wm, "drs_locator_state"):
            st = wm.drs_locator_state
            st.model = None
            st.notice = ""


# ---- UI list ----------------------------------------------------------------


class DRS_UL_LocatorList(bpy.types.UIList):
    bl_idname = "DRS_UL_LocatorList"

    def draw_item(self, _ctx, layout, _data, item: LocatorItemPG, _icon, _active, _flt):
        layout.label(text=_LOCATOR_LABELS.get(int(item.type), f"Unknown ({item.type})"))


# ---- Operators: core buttons ------------------------------------------------


class DRS_OT_OpenLocatorEditor(bpy.types.Operator):
    bl_idname = "drs.open_locator_editor"
    bl_label = "Locator Editor"
    bl_description = "Edit locator attachments, resources and placement"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, _event):
        col = _active_top_drsmodel(context)
        if not col:
            self.report({"ERROR"}, "Select a model to edit its locators.")
            return {"CANCELLED"}

        st = _state()
        st.model = col
        _refresh_state_from_blob(col)
        bpy.ops.object.select_all(action="DESELECT")

        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        _draw_editor_body(self.layout)


class DRS_OT_LocatorAdd(bpy.types.Operator):
    bl_description = 'Add an attachment point of the selected type to this model'
    bl_idname = "drs.locator_add"
    bl_label = "Add Locator"
    bl_options = {"INTERNAL"}

    locator_type: EnumProperty(name="Type", items=LOCATOR_TYPE_ENUM, default="0")

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, _context):
        self.layout.prop(self, "locator_type")

    def execute(self, context):
        st = _state()
        col = st.model
        if col is None:
            self.report({"ERROR"}, "Select a model to edit its locators.")
            return {"CANCELLED"}
        blob = _read_blob(col)

        uid = str(uuid.uuid4())
        entry = {
            "uid": uid,
            "class_id": int(self.locator_type),
            "file": "",
            "bone_id": -1,  # non-bone => world in blob; parent to GameOrientation in scene
            "uk_int": -1,
            "rot3x3": [1, 0, 0, 0, 1, 0, 0, 0, 1],
            "pos": [0.0, 0.0, 0.0],
        }
        blob["locators"].append(entry)
        _write_blob(col, blob)

        # Materialize -> this will parent to GameOrientation if present
        apply_blob_to_scene(col)
        _refresh_state_from_blob(col)

        bpy.ops.object.select_all(action="DESELECT")
        return {"FINISHED"}


class DRS_OT_LocatorRemove(bpy.types.Operator):
    bl_description = 'Remove the selected locator and its attachment helper'
    bl_idname = "drs.locator_remove"
    bl_label = "Remove Locator"
    bl_options = {"INTERNAL"}

    def execute(self, _context):
        st = _state()
        if st.model is None:
            return {"CANCELLED"}
        if not 0 <= st.active_index < len(st.items):
            return {"CANCELLED"}
        uid = st.items[st.active_index].uid
        remove_locator(st.model, uid, delete_object=True)
        _refresh_state_from_blob(st.model)
        st.active_index = max(0, min(st.active_index, len(st.items) - 1))
        return {"FINISHED"}


class DRS_OT_LocatorSync(bpy.types.Operator):
    bl_idname = "drs.locator_sync"
    bl_label = "Save Placement"
    bl_description = (
        "Save locator positions and rotations from the viewport"
    )
    bl_options = {"INTERNAL"}

    def execute(self, _context):
        st = _state()
        if st.model is None:
            return {"CANCELLED"}
        update_blob_from_scene(st.model, add_new=True)
        # After capturing, re-apply to ensure parenting/transform rule consistency
        apply_blob_to_scene(st.model)
        _refresh_state_from_blob(st.model)
        return {"FINISHED"}


class DRS_OT_LocatorSaveResource(bpy.types.Operator):
    """Save the selected locator's resource without changing its attachment or transform."""
    bl_idname='drs.locator_save_resource'
    bl_label='Save Locator Resource'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        try:
            model,item=selected_fx_item(context)
            blob=_read_blob(model)
            row=next((r for r in blob['locators'] if r.get('uid')==item.uid),None)
            if row is None:raise ValueError('Locator was removed; reload the Locator Editor')
            row['file']=item.file
            _write_blob(model,blob)
            obj=_object_by_uid(model,item.uid)
            if obj:obj['_file']=item.file
        except ValueError as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class DRS_OT_LocatorSaveItem(bpy.types.Operator):
    """Apply detail changes (type/file/parent/pos) to blob and scene for the selected item."""

    bl_idname = "drs.locator_save_item"
    bl_label = "Apply Changes"
    bl_description = "Save type, resource and attachment. A changed attachment starts at its origin; position it in the viewport and Save Placement"
    bl_options = {"INTERNAL","UNDO"}

    uid: bpy.props.StringProperty()
    idx: bpy.props.IntProperty(default=0)

    def execute(self, _context):
        st = _state()
        col = st.model
        if col is None:
            return {"CANCELLED"}
        if not 0 <= self.idx < len(st.items):
            return {"CANCELLED"}

        it = st.items[self.idx]
        arm = _find_armature(col)
        blob = _read_blob(col)

        # compute target bone index; keep 0 valid
        bone_idx = (
            _bone_index_from_name(arm, it.parent_bone)
            if (arm and it.parent_bone)
            else -1
        )
        if it.attachment_mode=='BONE' and bone_idx<0:
            self.report({'ERROR'},'Choose a bone for this attachment');return {'CANCELLED'}
        changed_parent=False

        for e in blob["locators"]:
            if e.get("uid") == self.uid:
                # update type/file
                e["class_id"] = int(it.type) if it.type.isdigit() else int(it.class_id)
                e["file"] = it.file or ""
                # Store the use_parent_minus_two property
                e["use_parent_minus_two"] = bool(it.use_parent_minus_two)

                parent=int(bone_idx) if bone_idx>=0 else -2 if it.use_parent_minus_two else -1
                changed_parent=parent!=e.get('bone_id',-1)
                e['bone_id']=parent
                if changed_parent:
                    e["pos"] = [0.0, 0.0, 0.0]
                    e["rot3x3"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
                break

        _write_blob(col, blob)
        if changed_parent:apply_blob_to_scene(col,only_uid=self.uid)
        obj=_object_by_uid(col,self.uid)
        if obj:
            obj['_file']=it.file
            obj['_class_id']=int(it.type)
        _refresh_state_from_blob(col)
        st.active_index = min(self.idx, len(st.items) - 1)
        return {"FINISHED"}


# ---- Simple launcher panel in N-panel ---------------------------------------
class DRS_PT_LocatorEditorDock(bpy.types.Panel):
    bl_order = 40
    bl_label = "Locator Editor"
    bl_idname = "DRS_PT_LocatorEditorDock"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS Editor"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, _ctx):
        return True

    def draw(self, context):
        layout = self.layout
        model = _active_top_drsmodel(context)

        if not model:
            box = layout.box()
            box.label(text="Select a model to edit its locators.", icon="INFO")
            return

        st = _state()
        if st.model != model:
            _request_model_refresh(model)
            layout.label(text="Loading locatorsâ€¦", icon="TIME")
            return
        if st.notice:
            layout.label(text=st.notice, icon="ERROR")
            return

        _draw_editor_body(layout)


# ---- Registration ------------------------------------------------------------

_classes = (
    LocatorItemPG,
    LocatorEditorState,
    DRS_UL_LocatorList,
    DRS_OT_OpenLocatorEditor,
    DRS_OT_LocatorAdd,
    DRS_OT_LocatorRemove,
    DRS_OT_LocatorSync,
    DRS_OT_LocatorSaveItem,
    DRS_OT_LocatorSaveResource,
    DRS_PT_LocatorEditorDock,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.drs_locator_state = PointerProperty(type=LocatorEditorState)
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _invalidate_locator_state not in handlers:
            handlers.append(_invalidate_locator_state)


def unregister():
    global _PENDING_MODEL
    _PENDING_MODEL = None
    if bpy.app.timers.is_registered(_apply_pending_refresh):
        bpy.app.timers.unregister(_apply_pending_refresh)
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _invalidate_locator_state in handlers:
            handlers.remove(_invalidate_locator_state)
    del bpy.types.WindowManager.drs_locator_state
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
