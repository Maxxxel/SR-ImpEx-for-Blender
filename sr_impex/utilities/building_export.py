"""Building authoring/export, independent of Outliner visibility and selection.

State resources are rebuilt from temporary meshes. Imported containers are
patched by node index so unedited payloads and hierarchy metadata survive.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import fields, is_dataclass
from io import BytesIO
import json
import math
import hashlib
from pathlib import Path
import re
import shutil
import tempfile

import bmesh
import bpy
from mathutils import Matrix

from sr_impex.definitions.bmg_definitions import BMG
from sr_impex.definitions.drs_definitions import DRS
from sr_impex.definitions.grid_definitions import SMeshState, StateBasedMeshSet
from sr_impex.definitions.resource_definitions import DrwResourceMeta
from sr_impex.definitions.collision_definitions import CollisionShape
from sr_impex.definitions.enums import InformationIndices
from sr_impex.utilities.building_layout import grid_from_blob
from sr_impex.utilities.resource_container import (
    snapshot, restore, payload_bytes, container_nodes, replace_payloads,
)
from sr_impex.utilities.skeleton_metadata import RESOURCE_META
from sr_impex.blender.editors.bmg_state_editor import MESHGRID_BLOB_KEY
from sr_impex.blender.editors.animation_set_editor import ANIM_BLOB_KEY
from sr_impex.blender.editors.effect_set_editor import EFFECT_BLOB_KEY, blob_to_effectset
from sr_impex.blender.editors.locator_editor import BLOB_KEY, blob_to_cdrw

SOURCE_KEY = "_bmg_source_container"
SOURCE_PATH = "_bmg_source_path"
STATE_ID = "bmg_state_id"
CELL_ID = "bmg_cell_index"
STATE_FX = "bmg_state_fx"
TRANSITIONS = "bmg_transitions_json"


def find_building(context):
    """Resolve the building from an active mesh, state or model collection."""
    active = context.view_layer.active_layer_collection.collection
    candidates = [c for c in bpy.data.collections if MESHGRID_BLOB_KEY in c]
    matches = [c for c in candidates if active == c or active in c.children_recursive]
    if len(matches) == 1:
        return matches[0]
    obj = context.object
    if obj:
        matches = [c for c in candidates if obj.name in c.all_objects]
        if len(matches) == 1:
            return matches[0]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("Select a mesh or collection belonging to one BMG building")


def persist_resource(collection, filepath, drs=None):
    from sr_impex.utilities import drs_utility as du
    collection[SOURCE_KEY] = snapshot(Path(filepath).read_bytes())
    collection[SOURCE_PATH] = str(Path(filepath).resolve())
    if drs:
        du.persist_locator_blob_on_collection(collection, drs)
        du.persist_animset_blob_on_collection(collection, drs)
        du.persist_effect_blob_on_collection(collection, drs)
        for key in (BLOB_KEY, ANIM_BLOB_KEY, EFFECT_BLOB_KEY):
            if key in collection:
                collection['_bmg_original_' + key] = collection[key]
        meta = drs.drw_resource_meta
        if meta is not None:
            collection[RESOURCE_META] = json.dumps({"version": meta.version,
                "resource_class": meta.resource_class, "identifier": meta.hash})


def original_bytes(collection):
    embedded = collection.get(SOURCE_KEY)
    if embedded:
        return restore(embedded)
    path = collection.get(SOURCE_PATH)
    return Path(path).read_bytes() if path and Path(path).is_file() else None


def child(collection, prefix):
    return next((c for c in collection.children if c.name.startswith(prefix)), None)


def state_collections(root):
    found = {}
    for col in root.children_recursive:
        if STATE_ID in col:
            state = int(col[STATE_ID])
            cell = int(col.get(CELL_ID, col.get("mesh_set_index", -1)))
        elif str(col.get("state_type", "")).startswith("S") and child(col, "Meshes_Collection"):
            # Compatibility with .blend files saved before explicit state IDs.
            state = int(str(col["state_type"])[1:])
            cell = int(col.get("mesh_set_index", -1))
        else:
            continue
        if not 0 <= state <= 0xffffffff or cell < 0:
            raise ValueError(f"Invalid building state/cell on {col.name}")
        key = (cell, state)
        if key in found:
            raise ValueError(f"Duplicate state S{state} in building cell {cell}")
        found[key] = col
    return found


def create_grid(root):
    raw = root.get(MESHGRID_BLOB_KEY)
    if not raw:
        raise ValueError("Building has no MeshSetGrid settings")
    blob = json.loads(raw)
    if not blob.get('source_grid_payload_hex') and original_bytes(root):
        original = BMG().read_bytes(original_bytes(root)).mesh_set_grid
        blob['source_grid_payload_hex'] = payload_bytes(original).hex()
    grid = grid_from_blob(blob)
    for (index, state_id), collection in state_collections(root).items():
        if not 0 <= index < len(grid.mesh_modules):
            raise ValueError(f"State {collection.name} lies outside the building grid")
        module = grid.mesh_modules[index]
        # A represented cell is occupied unless explicitly disabled in the grid.
        cell_blob = next((c for c in blob.get("cells", []) if int(c["index"]) == index), {})
        if "has_mesh_set" in cell_blob and not cell_blob["has_mesh_set"]:
            raise ValueError(f"Cell {index} is disabled but contains editable states")
        module.has_mesh_set = module.has_mesh_set or 1
        if module.state_based_mesh_set is None:
            module.state_based_mesh_set = StateBasedMeshSet()
        meshset = module.state_based_mesh_set
        state = next((s for s in meshset.mesh_states if s.state_id == state_id), None)
        if state is None:
            state = SMeshState(state_num=state_id, has_files=1)
            meshset.mesh_states.append(state)
        if STATE_FX in collection:
            state.fx_file = str(collection[STATE_FX])
        if "bmg_resource_file" in collection:
            state.resource_file = str(collection["bmg_resource_file"])
        # Resource filenames are assigned after geometry export, keeping
        # non-version-1 records untouched when there is no editable collection.
        state.version = 1
    for col in root.children_recursive:
        if TRANSITIONS not in col:
            continue
        from sr_impex.definitions.grid_definitions import StateTransition
        index = int(col.get(CELL_ID, col.get("mesh_set_index", -1)))
        if not 0 <= index < len(grid.mesh_modules):
            raise ValueError(f"Transition cell outside grid: {col.name}")
        meshset = grid.mesh_modules[index].state_based_mesh_set
        if meshset is None:
            raise ValueError("Transitions require a populated building cell")
        updated = []
        for row in json.loads(col[TRANSITIONS]):
            state_id, filename = int(row['state_id']), str(row.get('fx_file', ''))
            transition = next((t for t in meshset.transitions if t.target_state == state_id), None)
            transition = deepcopy(transition) if transition else StateTransition(state_num=state_id)
            transition.fx_file = filename
            updated.append(transition)
        meshset.transitions = updated
    if BLOB_KEY in root:
        from sr_impex.utilities.drs_utility import _cdrw_to_blob
        current = json.loads(root[BLOB_KEY])
        baseline = root.get('_bmg_original_' + BLOB_KEY)
        before = json.loads(baseline) if baseline else _cdrw_to_blob(grid.cdrw_locator_list)
        if before != current:
            locators = blob_to_cdrw(current)
            locators.magic = grid.cdrw_locator_list.magic
            grid.cdrw_locator_list = locators
    return grid


def raw_game_matrix(obj):
    basis = obj.matrix_basis.copy()
    yaw = obj.get('_bmg_display_yaw')
    if yaw is not None:
        basis = Matrix.Rotation(math.radians(float(yaw)), 4, 'Y') @ basis
    result = obj.parent.matrix_world @ obj.matrix_parent_inverse @ basis if obj.parent else basis
    parent = obj.parent
    while parent:
        if parent.name.startswith("GameOrientation"):
            result = parent.matrix_world.inverted_safe() @ result
            break
        parent = parent.parent
    return result


def game_matrix(obj):
    result = raw_game_matrix(obj)
    baseline = obj.get("_bmg_import_basis")
    if baseline is not None:
        basis = Matrix([baseline[i:i + 4] for i in range(0, 16, 4)])
        transform = obj.get('_bmg_import_transform')
        original = Matrix([transform[i:i+4] for i in range(0,16,4)]) if transform else Matrix.Identity(4)
        result = original @ basis.inverted_safe() @ result
    return result


def collision_fingerprint(collection):
    records = []
    for obj in collection.all_objects:
        if obj.type == 'MESH':
            records.append((obj.name, [round(v, 6) for row in raw_game_matrix(obj) for v in row],
                [[round(v, 6) for v in vertex.co] for vertex in obj.data.vertices]))
    return hashlib.sha256(json.dumps(sorted(records)).encode('utf8')).hexdigest()


def export_collision(owner):
    """Keep untouched imported shapes exact, normalize edited shape transforms."""
    from sr_impex.utilities import drs_utility as du
    original = child(owner, 'CollisionShapes_Collection')
    if original is None:
        return CollisionShape()
    if (original.get('_bmg_collision_fingerprint') == collision_fingerprint(original)
            and '_bmg_collision_payload' in original):
        return CollisionShape().read(BytesIO(bytes.fromhex(original['_bmg_collision_payload'])))
    root = bpy.data.collections.new('__BMG_COLLISION_EXPORT__')
    collections, objects = [], []
    def clone(source, parent):
        col = bpy.data.collections.new(source.name)
        collections.append(col); parent.children.link(col)
        for obj in source.objects:
            copy = obj.copy(); objects.append(copy); col.objects.link(copy)
            copy.parent = None
            copy.matrix_world = game_matrix(obj)
        for sub in source.children:
            clone(sub, col)
    try:
        clone(original, root)
        return du.create_collision_shape(root)
    finally:
        for obj in objects: bpy.data.objects.remove(obj, do_unlink=True)
        for col in reversed(collections): bpy.data.collections.remove(col)
        bpy.data.collections.remove(root)


def merge_editor_changes(original, before, after):
    """Apply represented edits without dropping unrepresented versioned data."""
    if is_dataclass(before) and is_dataclass(after) and is_dataclass(original):
        for item in fields(after):
            name = item.name
            setattr(original, name, merge_editor_changes(getattr(original, name),
                getattr(before, name), getattr(after, name)))
        return original
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after) or not isinstance(original, list) or len(original) < len(before):
            # List length changes are explicit edits to the represented list.
            return deepcopy(after) if before != after else original
        for i in range(len(after)):
            original[i] = merge_editor_changes(original[i], before[i], after[i])
        return original
    return deepcopy(after) if before != after else original


def _split_corners(mesh, split_uv):
    """Split discontinuous export vertices without selection-dependent operators."""
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        uv = bm.loops.layers.uv.active
        if uv is None:
            raise ValueError(f"Mesh {mesh.name} needs a UV map before building export")
        split = []
        for edge in bm.edges:
            loops = list(edge.link_loops)
            if len(loops) != 2:
                continue
            a, b = loops
            different_uv = False
            if split_uv:
                for vert in edge.verts:
                    ua = next(l[uv].uv for l in a.face.loops if l.vert == vert)
                    ub = next(l[uv].uv for l in b.face.loops if l.vert == vert)
                    different_uv |= (ua - ub).length > 1e-7
            if different_uv or not edge.smooth or not a.face.smooth or not b.face.smooth:
                split.append(edge)
        if split:
            bmesh.ops.split_edges(bm, edges=split)
        bm.to_mesh(mesh)
    finally:
        bm.free()


@contextmanager
def prepared_meshes(state, options):
    """Copy only render objects, split material slots, bake game-space transforms."""
    source = child(state, "Meshes_Collection")
    source_objects = list(source.all_objects if source else state.objects)
    render = [o for o in source_objects if o.type == 'MESH']
    if not render:
        raise ValueError(f"State {state.name} has no render meshes")
    collection = bpy.data.collections.new("__BMG_EXPORT_MESHES__")
    created, meshes = [], []
    try:
        for original in render:
            unsupported = [m.name for m in original.modifiers if m.type != 'ARMATURE' and m.show_render
                and not (m.type == 'NODES' and m.node_group and m.node_group.name.startswith('WindEffectTree'))]
            if unsupported:
                raise ValueError(f"Apply mesh modifiers before export on {original.name}: {', '.join(unsupported)}")
            used = sorted({p.material_index for p in original.data.polygons})
            for slot in used:
                material = original.data.materials[slot] if slot < len(original.data.materials) else None
                if material is None:
                    raise ValueError(f"Mesh {original.name}: material slot {slot} is empty")
                obj = original.copy()
                obj.data = original.data.copy()
                created.append(obj)
                meshes.append(obj.data)
                collection.objects.link(obj)
                obj.parent = None
                obj.matrix_world = Matrix.Identity(4)
                bm = bmesh.new()
                try:
                    bm.from_mesh(obj.data)
                    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != slot], context='FACES')
                    loose = [v for v in bm.verts if not v.link_faces]
                    if loose:
                        bmesh.ops.delete(bm, geom=loose, context='VERTS')
                    if options.get("auto_fix_quad_faces", True):
                        bmesh.ops.triangulate(bm, faces=list(bm.faces))
                    elif any(len(f.verts) != 3 for f in bm.faces):
                        raise ValueError(f"Mesh {original.name} contains non-triangular faces")
                    if options.get("flip_normals", False):
                        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
                    bm.to_mesh(obj.data)
                finally:
                    bm.free()
                obj.data.transform(game_matrix(original))
                obj.data.materials.clear()
                obj.data.materials.append(material)
                for polygon in obj.data.polygons:
                    polygon.material_index = 0
                _split_corners(obj.data, options.get("split_mesh_by_uv_islands", True))
                obj.data.update()
        yield collection
    finally:
        for obj in created:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.data.collections.remove(collection)


def armature_for(root, state):
    meshes = child(state, "Meshes_Collection")
    rigs = {m.object for o in (meshes.all_objects if meshes else state.objects)
            for m in o.modifiers if m.type == 'ARMATURE' and m.object}
    if len(rigs) > 1:
        raise ValueError(f"State {state.name} uses more than one skeleton")
    return next(iter(rigs), None)


def compact_skin_groups(obj):
    """Material splitting can leave sparse group IDs; the joint map is dense."""
    for vertex in obj.data.vertices:
        influences = sorted(((g.group, g.weight) for g in vertex.groups if g.weight > 0),
                            key=lambda item: (-item[1], item[0]))
        total = sum(weight for _, weight in influences[:4])
        if total <= 0:
            raise ValueError(f"Skinned mesh {obj.name} has unweighted vertices")
        for index, weight in influences[4:]:
            obj.vertex_groups[index].remove([vertex.index])
        for index, weight in influences[:4]:
            obj.vertex_groups[index].add([vertex.index], weight / total, 'REPLACE')
    used = {g.group for v in obj.data.vertices for g in v.groups if g.weight > 0}
    for group in reversed(list(obj.vertex_groups)):
        if group.index not in used:
            obj.vertex_groups.remove(group)


def export_resource(root, state, path, options):
    from sr_impex.utilities import drs_utility as du
    source = original_bytes(state)
    rig = armature_for(root, state)
    bone_map = du.create_bone_map(rig) if rig else {}
    collision_col = child(state, "CollisionShapes_Collection")
    replacements = {}
    unified = None
    try:
        with prepared_meshes(state, options) as meshes:
            if not du.verify_mesh_vertex_count(meshes):
                raise ValueError(f"State {state.name} exceeds the engine vertex limit")
            if rig:
                for obj in meshes.objects:
                    result=du.prepare_export_skin_weights(obj,set(bone_map))
                    if result['removed_groups'] or result['limited'] or result['normalized']:
                        du.logger.log(f"{obj.name}: export copy skin weights: "
                            f"{result['limited']} vertices limited to four bones, "
                            f"{result['normalized']} normalized; "
                            f"{len(result['removed_groups'])} non-bone groups excluded.",
                            'Skin Weights', 'WARNING')
                    compact_skin_groups(obj)
                    for vertex in obj.data.vertices:
                        influences = [g for g in vertex.groups if g.weight > 0]
                        if not influences:
                            raise ValueError(f"Skinned mesh {obj.name} has unweighted vertices")
                        if any(obj.vertex_groups[g.group].name not in bone_map for g in influences):
                            raise ValueError(f"Mesh {obj.name} has weights for a missing skeleton bone")
            unified = du.create_unified_mesh(meshes)
            meshfile, mesh_bones = du.create_cdsp_mesh_file(meshes, path.stem, str(path.parent),
                False, bool(rig), options.get("mip_maps", "auto"), du.get_environment_cubemap_image(root))
            if meshfile is None:
                raise ValueError(f"Could not export materials/geometry for {state.name}; see SR ImpEx log")
            # Quantized skin weights must still add up to one. Allocate the
            # rounding remainder to the strongest influence, on export data only.
            if rig:
                for mesh in meshfile.meshes:
                    for data in mesh.mesh_data:
                        if data.revision == 12:
                            for vertex in data.vertices:
                                weights = vertex.raw_weights
                                total = sum(weights)
                                if not total:
                                    raise ValueError('Skin weight quantization produced an unweighted vertex')
                                weights[max(range(4), key=lambda i: weights[i])] += 255 - total
            jointmap = du.create_cdsp_joint_map(bool(rig), mesh_bones, bone_map)
            if rig:
                meshfile = du.update_mesh_file_root_reference(meshfile, mesh_bones)
            replacements.update(CGeoMesh=du.create_cgeo_mesh(unified),
                CGeoOBBTree=du.create_cgeo_obb_tree(unified), CDspMeshFile=meshfile, CDspJointMap=jointmap)
            if rig:
                skin=du.create_skin_info(unified, meshes, bone_map)
                if skin is None:
                    raise ValueError(f"Cannot safely match skin vertices for {state.name}; see SR ImpEx log")
                replacements.update(CSkSkeleton=du.create_skeleton(rig, bone_map),CSkSkinInfo=skin)
            if RESOURCE_META in state:
                meta = json.loads(state[RESOURCE_META])
                value = DrwResourceMeta(version=int(meta["version"]), hash=meta["identifier"])
                value.resource_class = int(meta["resource_class"])
                replacements['DrwResourceMeta'] = value
            if collision_col:
                replacements['collisionShape'] = export_collision(state)
            if BLOB_KEY in state:
                before = state.get('_bmg_original_' + BLOB_KEY)
                if before is None or json.loads(before) != json.loads(state[BLOB_KEY]):
                    replacements['CDrwLocatorList'] = blob_to_cdrw(json.loads(state[BLOB_KEY]))
            if source:
                _, _, _, _, entries = container_nodes(source)
                names = {entry[0] for entry in entries.values()}
                if bool(rig) != ('CSkSkeleton' in names):
                    raise ValueError("Changing an imported state between static and skinned requires a new state")
                # Only the primitive-container collisionShape is editable here;
                # similarly named children of CGeoMesh/OBBTree retain their bytes.
                parsed = DRS()
                parsed.node_informations = []
                from sr_impex.definitions.base_types import NodeInformation, RootNodeInformation, Node, RootNode
                table, hierarchy, count, _, _ = container_nodes(source)
                stream = BytesIO(source); stream.seek(table)
                parsed.node_informations = [RootNodeInformation().read(stream)]
                parsed.node_informations += [NodeInformation().read(stream) for _ in range(count - 1)]
                stream.seek(hierarchy); parsed.nodes = [RootNode().read(stream)]
                parsed.nodes += [Node().read(stream) for _ in range(count - 1)]
                payloads = {}
                for index, (name, _, _) in entries.items():
                    if name not in replacements:
                        continue
                    if name == 'collisionShape' and not parsed.is_collision_primitive_child(index):
                        continue
                    if name == 'CDrwLocatorList':
                        from struct import unpack_from
                        replacements[name].magic = unpack_from('<i', source, entries[index][1])[0]
                    payloads[index] = payload_bytes(replacements[name])
                if collision_col and 'CGeoPrimitiveContainer' not in names:
                    raise ValueError("Imported resource has no primitive container; add collisions using a new state")
                path.write_bytes(replace_payloads(source, payloads))
            else:
                model_type = ('AnimatedBuildingCollisionMesh' if rig else
                    'StaticBuildingCollisionMesh' if collision_col else 'StaticObjectNoCollision')
                drs = DRS(model_type=model_type)
                if 'DrwResourceMeta' not in replacements:
                    replacements['DrwResourceMeta'] = DrwResourceMeta(unknown=0)
                replacements.setdefault('collisionShape', CollisionShape())
                for name in InformationIndices[model_type]:
                    if name != 'CGeoPrimitiveContainer':
                        drs.push_node_infos(name, replacements[name])
                drs.update_offsets()
                drs.save(str(path))
            # Re-read before publishing any output, including the geometry bounds.
            result = DRS().read(str(path))
            if result.cdsp_mesh_file.mesh_count != meshfile.mesh_count:
                raise ValueError("State resource validation failed")
            return result
    finally:
        if unified and unified.users == 0:
            bpy.data.meshes.remove(unified)


_ASSET_EXTENSIONS = {'.drs', '.bmg', '.bms', '.ska', '.xml', '.fxb', '.dds', '.wav', '.ogg'}


def asset_references(value, seen=None):
    seen = set() if seen is None else seen
    if type(value).__name__ == 'Texture' and getattr(value, 'name', ''):
        name = value.name
        yield name if name.lower().endswith('.dds') else name + '.dds'
        return
    if isinstance(value, str):
        if Path(value.replace('\\', '/')).suffix.lower() in _ASSET_EXTENSIONS:
            yield value
        return
    if id(value) in seen:
        return
    seen.add(id(value))
    if is_dataclass(value):
        for field in fields(value):
            if not field.name.endswith('_node'):
                yield from asset_references(getattr(value, field.name), seen)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from asset_references(item, seen)


def _copy_dependencies(stage, resources, manifest):
    """Copy local dependencies; report references resolved by the installed game.

    References escaping the package are never written outside the export folder.
    This is an asset export for the installed game, not a standalone game bundle.
    """
    pending = [(src_dir, dest_dir, ref) for value, src_dir, dest_dir in resources
               for ref in asset_references(value)]
    seen = set()
    while pending:
        src_dir, dest_dir, ref = pending.pop()
        normalized = ref.replace('\\', '/')
        dest = (dest_dir / normalized).resolve()
        key = str(dest).lower()
        if key in seen:
            continue
        seen.add(key)
        if not dest.is_relative_to(stage.resolve()):
            manifest['external_references'].append(ref)
            continue
        if dest.is_file():
            continue
        src = (src_dir / normalized).resolve() if src_dir else None
        if (src_dir and (src is None or not src.is_file())
                and Path(normalized).suffix.lower() == '.dds'):
            # Building debris DRSs commonly live in meshes/, while their
            # texture names resolve against the enclosing building folder.
            enclosing = (src_dir.parent / normalized).resolve()
            if enclosing.is_file():
                src = enclosing
                alias = (stage / normalized).resolve()
                if alias.is_relative_to(stage.resolve()) and not alias.exists():
                    alias.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, alias)
        if src is None or not src.is_file():
            manifest['external_references'].append(ref)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        suffix = src.suffix.lower()
        if suffix == '.drs':
            value = DRS().read(str(src))
            pending.extend((src.parent, dest.parent, dep) for dep in asset_references(value))
        elif suffix == '.bms':
            from sr_impex.definitions.bmg_definitions import BMS
            value = BMS().read(str(src))
            pending.extend((src.parent, dest.parent, dep) for dep in asset_references(value))
        elif suffix == '.xml':
            # Resource attributes in debris XML can be relative to meshes/.
            text = src.read_text(encoding='utf-8-sig', errors='replace')
            for dep in re.findall(r'[\w./\\-]+\.(?:drs|bms|fxb|xml|dds|ska)', text, re.I):
                base = src.parent
                target = dest.parent
                if not (base / dep.replace('\\', '/')).is_file() and (base / 'meshes' / dep).is_file():
                    base, target = base / 'meshes', target / 'meshes'
                pending.append((base, target, dep))


def export_building(context, filepath, root=None, **options):
    from sr_impex.utilities import drs_utility as du
    root = root or find_building(context)
    destination = Path(filepath).with_suffix('.bmg').resolve()
    if context.mode not in ('OBJECT', 'POSE'):
        raise ValueError('Leave Edit Mode before exporting a building')
    if any(parent.name.lower() == 'unpack' for parent in destination.parents):
        raise ValueError('Choose a separate export folder; unpacked source assets are read only')
    source_path = root.get(SOURCE_PATH)
    if source_path:
        source_folder = Path(source_path).resolve().parent
        asset_root = next((p for p in source_folder.parents if p.name.lower() == 'unpack'), source_folder)
        if destination.is_relative_to(asset_root):
            raise ValueError("Choose a separate export folder; imported game assets are read only")
    grid = create_grid(root)
    raw = original_bytes(root)
    building = BMG().read_bytes(raw) if raw else None
    collision_col = child(root, 'CollisionShapes_Collection')
    requested = options.get('model_type', 'AUTO')
    if building is None or requested != 'AUTO':
        if requested == 'AUTO':
            requested = ('AnimatedBuildingCollisionEffects' if EFFECT_BLOB_KEY in root else
                'AnimatedBuildingCollisionNoEffects' if ANIM_BLOB_KEY in root else
                'StaticBuildingCollision' if collision_col else 'StaticBuildingNoCollision')
        if building:
            existing = {n.name for n in building.nodes[1:]}
            if existing - set(InformationIndices[requested]):
                raise ValueError("Selected layout would discard source nodes; use Preserve / Auto")
        building = BMG(model_type=requested)
    nodes = {n.name for n in building.nodes[1:]}
    from sr_impex.utilities.resource_editing import POLICY_KEY,apply_node_policy
    node_policy=json.loads(root.get(POLICY_KEY,'{}'))
    if collision_col and 'collisionShape' not in nodes and node_policy.get('CGeoPrimitiveContainer')!='ADD':
        raise ValueError("This layout has no collision node; choose a layout with collisions")
    if EFFECT_BLOB_KEY in root and 'EffectSet' not in nodes and node_policy.get('EffectSet')!='ADD':
        raise ValueError("This layout has no EffectSet; choose a layout with effects")
    name = destination.stem
    if not grid.name:
        grid.name = name
    manifest = {'format_version': 1, 'building': destination.name, 'states': [],
                'external_references': [], 'files': []}
    # Staging isolates failed conversions/invalid geometry from existing exports.
    with tempfile.TemporaryDirectory(prefix='sr-impex-bmg-') as temporary:
        stage = Path(temporary)
        resources = []
        source_dir = Path(source_path).parent if source_path else None
        dependency_contexts = []
        for (index, state_id), col in sorted(state_collections(root).items()):
            resource_name = f'{name}_cell{index:03d}_s{state_id}.drs'
            value = export_resource(root, col, stage / resource_name, options)
            resources.append(value)
            resource_source = Path(col[SOURCE_PATH]).parent if SOURCE_PATH in col else source_dir
            dependency_contexts.append((value, resource_source, stage))
            state = next(s for s in grid.mesh_modules[index].state_based_mesh_set.mesh_states if s.state_id == state_id)
            state.resource_file = resource_name
            manifest['states'].append({'cell': index, 'state': state_id, 'resource': resource_name})
        ground = child(root, 'GroundDecal_Collection')
        if ground and any(o.type == 'MESH' for o in ground.all_objects):
            ground_name = f'{name}_ground.drs'
            ground_resource = export_resource(root, ground, stage / ground_name, options)
            resources.append(ground_resource)
            dependency_contexts.append((ground_resource,
                Path(ground[SOURCE_PATH]).parent if SOURCE_PATH in ground else source_dir, stage))
            grid.ground_decal = ground_name
        if not any(m.has_mesh_set for m in grid.mesh_modules):
            raise ValueError("Building has no populated grid cells")
        for module in grid.mesh_modules:
            if module.has_mesh_set and module.state_based_mesh_set is None:
                raise ValueError("Populated grid cell has no state set")
        building.mesh_set_grid = grid
        if collision_col:
            building.collision_shape = export_collision(root)
        elif 'collisionShape' in nodes and building.collision_shape is None:
            building.collision_shape = CollisionShape()
        if ANIM_BLOB_KEY in root:
            blob = json.loads(root[ANIM_BLOB_KEY])
            rigs = [o for o in root.all_objects if o.type == 'ARMATURE' and 'Control_Rig' not in o.name]
            rig = rigs[0] if rigs else None
            if 'AnimationSet' not in nodes and node_policy.get('AnimationSet')!='ADD':
                raise ValueError("Animation data needs an animated building layout")
            original_blob = root.get('_bmg_original_' + ANIM_BLOB_KEY)
            current_blob = root[ANIM_BLOB_KEY]
            # Older scenes have no baseline: derive it from the embedded source.
            if original_blob is None and building.animation_set is not None:
                baseline = du.animset_to_blob(building.animation_set)
                baseline['timings'] = du.animtimings_to_blob(building.animation_timings) if building.animation_timings else []
                original_blob = json.dumps(baseline)
            if original_blob is None or json.loads(original_blob) != blob:
                bone_map = du.create_bone_map(rig) if rig else {}
                updated = du.create_animation_set(name, rig, bone_map, {ANIM_BLOB_KEY: current_blob})
                timings = du.blob_to_animationtimings(blob)
                if original_blob and building.animation_set:
                    baseline = du.create_animation_set(name, rig, bone_map, {ANIM_BLOB_KEY: original_blob})
                    building.animation_set = merge_editor_changes(building.animation_set, baseline, updated)
                    old_timings = du.blob_to_animationtimings(json.loads(original_blob))
                    building.animation_timings = merge_editor_changes(building.animation_timings, old_timings, timings) if building.animation_timings else timings
                else:
                    building.animation_set, building.animation_timings = updated, timings
        if EFFECT_BLOB_KEY in root:
            before = root.get('_bmg_original_' + EFFECT_BLOB_KEY)
            after = json.loads(root[EFFECT_BLOB_KEY])
            if before is None or json.loads(before) != after or building.effect_set is None:
                building.effect_set = blob_to_effectset(after)
        # Snapshot-only animation data stays byte-exact when not represented by
        # editor properties. Fresh layouts still need valid empty payloads.
        from sr_impex.definitions.animation_definitions import AnimationSet, AnimationTimings
        from sr_impex.definitions.effect_definitions import EffectSet
        for node, attr, factory in [('AnimationSet', 'animation_set', AnimationSet),
                ('AnimationTimings', 'animation_timings', AnimationTimings), ('EffectSet', 'effect_set', EffectSet)]:
            if node in nodes and getattr(building, attr) is None:
                setattr(building, attr, factory())
        # Export actions from the original model context (no scene duplication).
        if options.get('export_all_ska_actions', True) and ANIM_BLOB_KEY in root:
            layer = context.view_layer.active_layer_collection
            def find_layer(node):
                if node.collection == root:
                    return node
                return next((v for c in node.children if (v := find_layer(c))), None)
            target = find_layer(context.view_layer.layer_collection)
            try:
                if target:
                    context.view_layer.active_layer_collection = target
                from sr_impex.utilities.helpers import build_ska_export_name_map
                prefix_mode = options.get('set_model_name_prefix', 'keep_existing')
                prefix = name if prefix_mode == 'model_name' else destination.parent.name if prefix_mode == 'folder_name' else '' if prefix_mode == 'none' else None
                mapping = build_ska_export_name_map(root, prefix)
                du.export_ska_actions_all(str(stage), root, context, mapping, export_tangents=True, armature=rig)
                # Only rename references whose edited action actually exported.
                mapping = {key: value for key, value in mapping.items() if (stage / (value + '.ska')).is_file()}
                if building.animation_set:
                    du._apply_ska_name_map_to_animation_set(building.animation_set, mapping)
                if building.effect_set:
                    du._apply_ska_name_map_to_effect_set(building.effect_set, mapping)
            finally:
                context.view_layer.active_layer_collection = layer
        building.save(str(stage / destination.name))
        final_path=stage/destination.name
        final_path.write_bytes(apply_node_policy(final_path.read_bytes(),root))
        building=BMG().read(str(final_path))
        _copy_dependencies(stage, [(building, source_dir, stage)] + dependency_contexts, manifest)
        # State/decal DRS references are required; optional installed-game FX
        # references are listed separately for developers in the manifest.
        required = [grid.ground_decal] if grid.ground_decal else []
        required += [s.resource_file for m in grid.mesh_modules if m.has_mesh_set
                     for s in m.state_based_mesh_set.mesh_states if s.version == 1 and s.resource_file]
        for ref in required:
            if not (stage / ref.replace('\\', '/')).is_file():
                raise ValueError(f"Missing required building resource: {ref}")
        for value in resources:
            for mesh in value.cdsp_mesh_file.meshes:
                for texture in mesh.textures.textures:
                    for ref in asset_references(texture):
                        if not (stage / ref.replace('\\', '/')).is_file():
                            raise ValueError(f"Missing required material texture: {ref}")
        manifest['external_references'] = sorted(set(manifest['external_references']))
        manifest['files'] = sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
        (stage / f'{name}.bmg-export.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Dependencies first; publish the referring BMG last.
        paths = sorted(stage.rglob('*'), key=lambda p: (p.name == destination.name, str(p)))
        for path in paths:
            if path.is_file():
                target = destination.parent / path.relative_to(stage)
                if source_path and target.resolve() == Path(source_path).resolve():
                    raise ValueError("Export would overwrite an imported source file")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    return manifest
