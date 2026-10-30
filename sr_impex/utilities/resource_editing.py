"""Validated artist operations for optional classes and source-only metadata."""
import json
from io import BytesIO
from pathlib import Path
from sr_impex.utilities.resource_container import restore,payload_bytes,container_nodes,edit_optional_nodes

POLICY_KEY='sr_export_node_policy'
PATCH_KEY='sr_class_payload_patches'
OPTIONAL=('CDrwLocatorList','AnimationSet','AnimationTimings','EffectSet','CGeoPrimitiveContainer')


def source_bytes(root):
    value=root.get('_bmg_source_container')
    return restore(value) if value else None


def source_payload(root,name):
    raw=source_bytes(root)
    if not raw:return None
    _,_,_,_,entries=container_nodes(raw)
    entry=next((e for e in entries.values() if e[0]==name),None)
    return raw[entry[1]:entry[1]+entry[2]] if entry else None


def factories():
    from sr_impex.definitions.animation_definitions import AnimationSet,AnimationTimings
    from sr_impex.definitions.effect_definitions import EffectSet
    from sr_impex.definitions.locator_definitions import CDrwLocatorList
    from sr_impex.definitions.resource_definitions import DrwResourceMeta
    return {'AnimationSet':AnimationSet,'AnimationTimings':AnimationTimings,'EffectSet':EffectSet,
            'CDrwLocatorList':CDrwLocatorList,'DrwResourceMeta':DrwResourceMeta}


def validate_payload(name,raw):
    factory=factories().get(name)
    if factory is None:raise ValueError('This generated class cannot be replaced with a metadata patch')
    stream=BytesIO(raw);value=factory().read(stream)
    if stream.tell()!=len(raw):raise ValueError(f'Unparsed bytes in {name} patch')
    return value


def apply_node_policy(raw,root):
    from sr_impex.utilities import drs_utility as du
    policy=json.loads(root.get(POLICY_KEY,'{}'));patches=json.loads(root.get(PATCH_KEY,'{}'))
    _,_,_,_,entries=container_nodes(raw);names={r[0] for r in entries.values()}
    additions={};removals=set()
    for name,mode in policy.items():
        if name not in OPTIONAL:raise ValueError(f'Class {name} is generated from scene data; cannot toggle it')
        if mode=='REMOVE':removals.add(name)
        elif mode=='ADD' and name not in names:
            if name=='CGeoPrimitiveContainer':
                from sr_impex.utilities.building_export import export_collision
                additions[name]=b'';additions['collisionShape']=payload_bytes(export_collision(root))
            elif name=='CDrwLocatorList':additions[name]=payload_bytes(du.create_cdrw_locator_list(root))
            elif name=='EffectSet':additions[name]=payload_bytes(du.create_effect_set('model.drs',root))
            elif name=='AnimationTimings':
                additions[name]=payload_bytes(du.blob_to_animationtimings(json.loads(root.get('AnimationSetJSON','{}'))))
            else:
                rig=next((o for o in root.all_objects if o.type=='ARMATURE' and 'Control_Rig' not in o.name),None)
                additions[name]=payload_bytes(du.create_animation_set('model',rig,du.create_bone_map(rig) if rig else {},root))
    for name,hex_value in patches.items():
        if name in removals:continue
        value=bytes.fromhex(hex_value);validate_payload(name,value);additions[name]=value
    if not additions and not removals:return raw
    return edit_optional_nodes(raw,additions,removals)


def preserve_opaque_nodes(raw,root):
    """Retain unmodeled source payloads when their root placement is safe."""
    from struct import unpack_from
    source=source_bytes(root)
    if not source:return raw
    table,_,_,_,entries=container_nodes(source)
    _,_,_,_,current=container_nodes(raw)
    present={entry[0] for entry in current.values()}
    additions={}
    for index,(name,start,length) in entries.items():
        if name not in ('CGdLocatorList','FxMaster') or name in present:continue
        parent,_,children,flags=unpack_from('<4i',source,table+index*32+16)
        if parent!=0 or children!=0 or flags!=0:
            raise ValueError(f'Cannot safely preserve this {name} hierarchy; export is stopped')
        additions[name]=source[start:start+length]
    return edit_optional_nodes(raw,additions,set()) if additions else raw


def preserve_metadata(root,name,updated,rig=None,bone_map=None):
    """Merge represented edits; source versions, extra markers and IK survive."""
    raw=source_payload(root,name)
    if raw is None:return updated
    original=validate_payload(name,raw)
    from sr_impex.utilities import drs_utility as du
    from sr_impex.utilities.building_export import merge_editor_changes
    keys={'AnimationSet':'AnimationSetJSON','AnimationTimings':'AnimationSetJSON',
          'EffectSet':'EffectSetJSON','CDrwLocatorList':'CDrwLocatorListJSON'}
    key=keys.get(name)
    if not key:return updated
    before=root.get('_bmg_original_'+key)
    current=root.get(key)
    if not current or (before and json.loads(current)==json.loads(before)):return original
    if name=='AnimationSet':
        baseline=du.create_animation_set('model',rig,bone_map or {},{key:before or '{}'})
        return merge_editor_changes(original,baseline,updated)
    if name=='AnimationTimings':
        baseline=du.blob_to_animationtimings(json.loads(before or '{}'))
        return merge_editor_changes(original,baseline,updated)
    if name=='CDrwLocatorList':updated.magic=original.magic
    return updated
