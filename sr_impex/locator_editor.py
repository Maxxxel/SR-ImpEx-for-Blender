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

from .drs_definitions import (
    CDrwLocatorList,
    SLocator,
    CMatCoordinateSystem,
    Matrix3x3,
    Vector3,
    LocatorClass,
)

# ---- Constants ---------------------------------------------------------------

BLOB_KEY = "CDrwLocatorListJSON"
UID_KEY = "_cdrw_uid"
LOCATOR_PREFIX = "Locator_"
SLOCATORS_COLLECTION_NAME = "SLocators_Collection"

LOCATOR_TYPE_ENUM = [
    (str(k), v, "") for k, v in sorted(LocatorClass.items(), key=lambda kv: kv[0])
]

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


def _active_model_collection() -> Optional[bpy.types.Collection]:
    alc = bpy.context.view_layer.active_layer_collection
    if not alc:
        return None
    col = alc.collection
    return col if col and col.name.startswith("DRSModel_") else None


def _find_armature(col: bpy.types.Collection) -> Optional[bpy.types.Object]:
    def visit(c: bpy.types.Collection) -> Optional[bpy.types.Object]:
        for o in c.objects:
            if o.type == "ARMATURE":
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
    arm = _find_armature(col)

    root = layout.column(align=True)

    # --- Top: list + actions (full width) ------------------------------------
    root.template_list(
        "DRS_UL_LocatorList", "", st, "items", st, "active_index", rows=12
    )

    actions = root.row(align=True)
    actions.operator("drs.locator_add", text="Add", icon="ADD")
    actions.operator("drs.locator_remove", text="Remove", icon="REMOVE")
    actions.operator("drs.locator_sync", text="Sync from Scene", icon="FILE_REFRESH")
    root.separator()

    # --- Bottom: details of selected item (full width) -----------------------
    if 0 <= st.active_index < len(st.items):
        it = st.items[st.active_index]

        box = root.box()
        box.label(text="Selected Locator", icon="OUTLINER_OB_EMPTY")

        # nicer property layout in a narrow panel
        box.use_property_split = True
        box.use_property_decorate = False

        box.prop(it, "type", text="Type")
        box.prop(it, "file", text="File")
        if arm:
            box.prop_search(it, "parent_bone", arm.data, "bones", text="Parent")
        else:
            row = box.row()
            row.alert = True
            row.label(text="No armature in this model", icon="INFO")

        row = box.row(align=True)
        op = row.operator(
            "drs.locator_save_item",
            text="Update parent and remove transformations",
            icon="CHECKMARK",
        )
        op.uid = it.uid
        op.idx = st.active_index
    else:
        root.label(text="Select a locator to edit its details.", icon="INFO")


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


def apply_blob_to_scene(root: bpy.types.Collection) -> None:
    """Materialize blob to scene. Create/match by UID. Parent & set transforms by rule."""
    blob = _read_blob(root)
    arm = _find_armature(root)
    dst_col = _ensure_locators_collection(root)
    go = _find_game_orientation(root)  # default parent for non-bone locators

    for entry in blob["locators"]:
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
    arm = _find_armature(root)
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
            entry["bone_id"] = -1
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


class LocatorItemPG(bpy.types.PropertyGroup):
    uid: StringProperty(name="UID", default="")  # type: ignore
    class_id: IntProperty(name="Class ID", default=0)  # type: ignore
    type: EnumProperty(name="Type", items=LOCATOR_TYPE_ENUM, default="0")  # type: ignore
    file: StringProperty(name="File", subtype="FILE_PATH", default="")  # type: ignore
    parent_bone: StringProperty(name="Parent", default="")  # type: ignore
    bone_id: IntProperty(name="Bone ID", default=-1)  # type: ignore
    pos: FloatVectorProperty(name="Position", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")  # type: ignore

    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "class_id": int(self.class_id),
            "type_name": LocatorClass.get(int(self.class_id), "Unknown"),
            "file": self.file or "",
            "bone_id": int(self.bone_id),
            "pos": list(self.pos),
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


class LocatorEditorState(bpy.types.PropertyGroup):
    items: CollectionProperty(type=LocatorItemPG)  # type: ignore

    def _on_active_index_changed(self, _ctx):
        try:
            if not self.model or not (0 <= self.active_index < len(self.items)):
                return
            uid = self.items[self.active_index].uid
            if uid:
                _select_locator_by_uid(self.model, uid)
        except Exception:
            pass

    active_index: IntProperty(default=0, update=_on_active_index_changed)  # type: ignore
    model: PointerProperty(type=bpy.types.Collection)  # type: ignore


def _state() -> LocatorEditorState:
    return bpy.context.window_manager.drs_locator_state


def _refresh_state_from_blob(col: bpy.types.Collection):
    st = _state()
    st.items.clear()
    arm = _find_armature(col)
    blob = _read_blob(col)
    for e in blob.get("locators", []):
        it = st.items.add()
        it.from_dict(e, arm)


# ---- UI list ----------------------------------------------------------------


class DRS_UL_LocatorList(bpy.types.UIList):
    bl_idname = "DRS_UL_LocatorList"

    def draw_item(self, _ctx, layout, _data, item: LocatorItemPG, _icon, _active, _flt):
        row = layout.row(align=True)
        row.label(text=LocatorClass.get(int(item.class_id), "Unknown"))
        if item.file:
            row.label(text=item.file, icon="FILE")


# ---- Operators: core buttons ------------------------------------------------


class DRS_OT_OpenLocatorEditor(bpy.types.Operator):
    bl_idname = "drs.open_locator_editor"
    bl_label = "CDrwLocatorList Editor"
    bl_description = "Open the Locator Editor to view and edit CDrwLocatorList"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, _event):
        col = _active_model_collection()
        if not col:
            self.report({"ERROR"}, "Select a DRSModel_* collection in the Outliner.")
            return {"CANCELLED"}

        st = _state()
        st.model = col
        _refresh_state_from_blob(col)
        bpy.ops.object.select_all(action="DESELECT")

        return context.window_manager.invoke_popup(self, width=780)

    def draw(self, context):
        layout = self.layout
        st = _state()
        col = st.model
        arm = _find_armature(col)

        split = layout.split(factor=0.47)
        left = split.column()
        left.template_list(
            "DRS_UL_LocatorList", "", st, "items", st, "active_index", rows=12
        )
        r = left.row(align=True)
        r.operator("drs.locator_add", text="Add", icon="ADD")
        r.operator("drs.locator_remove", text="Remove", icon="REMOVE")
        r.operator("drs.locator_sync", text="Sync from Scene", icon="FILE_REFRESH")

        right = split.column()
        if 0 <= st.active_index < len(st.items):
            it = st.items[st.active_index]
            right.prop(it, "type", text="Type")
            right.prop(it, "file", text="File")
            if arm:
                right.prop_search(it, "parent_bone", arm.data, "bones", text="Parent")
            else:
                right.label(text="No armature in this model", icon="INFO")
            right.prop(it, "pos", text="Position (view)")
            row = right.row(align=True)
            s = row.operator(
                "drs.locator_save_item",
                text="Update parent and remove transformations",
                icon="CHECKMARK",
            )
            s.uid = it.uid
            s.idx = st.active_index


class DRS_OT_LocatorAdd(bpy.types.Operator):
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
    bl_idname = "drs.locator_remove"
    bl_label = "Remove Locator"
    bl_options = {"INTERNAL"}

    def execute(self, _context):
        st = _state()
        if not (0 <= st.active_index < len(st.items)):
            return {"CANCELLED"}
        uid = st.items[st.active_index].uid
        remove_locator(st.model, uid, delete_object=True)
        _refresh_state_from_blob(st.model)
        st.active_index = max(0, min(st.active_index, len(st.items) - 1))
        return {"FINISHED"}


class DRS_OT_LocatorSync(bpy.types.Operator):
    bl_idname = "drs.locator_sync"
    bl_label = "Sync From Scene"
    bl_description = (
        "Capture scene changes into the blob (appends new locators, never removes)"
    )
    bl_options = {"INTERNAL"}

    def execute(self, _context):
        st = _state()
        update_blob_from_scene(st.model, add_new=True)
        # After capturing, re-apply to ensure parenting/transform rule consistency
        apply_blob_to_scene(st.model)
        _refresh_state_from_blob(st.model)
        return {"FINISHED"}


class DRS_OT_LocatorSaveItem(bpy.types.Operator):
    """Apply detail changes (type/file/parent/pos) to blob and scene for the selected item."""

    bl_idname = "drs.locator_save_item"
    bl_label = "Save Locator Item"
    bl_options = {"INTERNAL"}

    uid: bpy.props.StringProperty()
    idx: bpy.props.IntProperty(default=0)

    def execute(self, _context):
        st = _state()
        col = st.model
        if not (0 <= self.idx < len(st.items)):
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

        for e in blob["locators"]:
            if e.get("uid") == self.uid:
                # update type/file
                e["class_id"] = int(it.type) if it.type.isdigit() else int(it.class_id)
                e["file"] = it.file or ""

                if bone_idx >= 0:
                    # Switching to a bone: ALWAYS reset local transform (ignore previous world/GO transform)
                    e["bone_id"] = int(bone_idx)
                    e["pos"] = [0.0, 0.0, 0.0]
                    e["rot3x3"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
                else:
                    # Clearing bone: reset to origin in GAME space (will appear at GO origin in scene)
                    e["bone_id"] = -1
                    e["pos"] = [0.0, 0.0, 0.0]
                    e["rot3x3"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
                break

        _write_blob(col, blob)
        apply_blob_to_scene(col)
        _refresh_state_from_blob(col)
        st.active_index = min(self.idx, len(st.items) - 1)
        return {"FINISHED"}


# ---- Simple launcher panel in N-panel ---------------------------------------


class DRS_PT_LocatorEditorLauncher(bpy.types.Panel):
    bl_label = "CDrwLocatorList"
    bl_idname = "DRS_PT_LocatorEditorLauncher"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS"

    def draw(self, _context):
        col = self.layout.column()

        model = _active_model_collection()
        if not model:
            col.label(
                text="Select a DRSModel_* collection in the Outliner.", icon="INFO"
            )
            return

        # Store the active model on our state and (cheaply) refresh UI data from blob
        st = _state()
        if st.model != model:
            st.model = model
            _refresh_state_from_blob(model)

        # Draw the full editor (list + details + buttons) inside the panel
        _draw_editor_body(col)


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
    DRS_PT_LocatorEditorLauncher,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.drs_locator_state = PointerProperty(type=LocatorEditorState)


def unregister():
    del bpy.types.WindowManager.drs_locator_state
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
