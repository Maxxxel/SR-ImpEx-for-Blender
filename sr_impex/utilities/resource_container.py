"""Preserve container metadata while replacing selected resource payloads.

Shared by building-state export. Unknown chunks, hierarchy links, padding and
trailing data survive; malformed/overlapping replacements are rejected.
"""
from io import BytesIO
from struct import unpack, pack
import base64
import zlib

from sr_impex.definitions.base_types import Node, RootNode


def snapshot(data):
    return base64.b85encode(zlib.compress(bytes(data), 6)).decode("ascii")


def restore(value):
    return zlib.decompress(base64.b85decode(value.encode("ascii")))


def payload_bytes(value):
    stream = BytesIO()
    value.write(stream)
    return stream.getvalue()


def container_nodes(source):
    if len(source) < 20:
        raise ValueError("Truncated resource container")
    magic, _, table, hierarchy, count = unpack("<i4I", source[:20])
    if (magic != -981667554 or count < 1 or table < 20 or
            table + 32 * count > len(source) or not 20 <= hierarchy < len(source)):
        raise ValueError("Invalid resource container header")
    reader = BytesIO(source)
    reader.seek(hierarchy)
    RootNode().read(reader)
    nodes = [Node().read(reader) for _ in range(count - 1)]
    if reader.tell() > len(source):
        raise ValueError("Truncated resource hierarchy")
    entries = {}
    for node in nodes:
        index = node.info_index
        if not 0 < index < count or index in entries:
            raise ValueError("Invalid or repeated resource node index")
        start, length = unpack("<2I", source[table + index * 32 + 8:table + index * 32 + 16])
        if start + length > len(source):
            raise ValueError("Resource payload is outside the file")
        entries[index] = (node.name, start, length)
    return table, hierarchy, count, reader.tell(), entries


def replace_payloads(source, replacements):
    """Replacements are keyed by node-info index, never ambiguous node names."""
    table, hierarchy, count, hierarchy_end, entries = container_nodes(source)
    changes = []
    for index, payload in replacements.items():
        if index not in entries:
            raise ValueError(f"Resource node {index} does not exist")
        _, start, length = entries[index]
        payload = bytes(payload)
        if payload == source[start:start + length]:
            continue
        if not length:
            raise ValueError("Cannot insert data into a zero-byte hierarchy parent")
        end = start + length
        metadata = ((0, 20), (table, table + 32 * count), (hierarchy, hierarchy_end))
        if any(start < hi and end > lo for lo, hi in metadata):
            raise ValueError("Resource payload overlaps container metadata")
        if any(other != index and size and start < offset + size and end > offset
               for other, (_, offset, size) in entries.items()):
            raise ValueError("Resource payloads overlap")
        changes.append((start, end, index, payload))
    if not changes:
        return source
    changes.sort()

    def relocate(offset):
        return offset + sum(len(data) - (end - start)
                            for start, end, _, data in changes if end <= offset)

    result, cursor = bytearray(), 0
    for start, end, _, data in changes:
        result.extend(source[cursor:start])
        result.extend(data)
        cursor = end
    result.extend(source[cursor:])
    new_table = relocate(table)
    result[8:16] = pack("<2I", new_table, relocate(hierarchy))
    sizes = {index: len(data) for _, _, index, data in changes}
    for index, (_, start, length) in entries.items():
        at = new_table + index * 32 + 8
        result[at:at + 8] = pack("<2I", relocate(start), sizes.get(index, length))
    return bytes(result)


def edit_optional_nodes(source, additions, removals):
    """Rebuild a changed tree with CRC-sorted, contiguous sibling ranges.

    Additions map name -> payload; collisionShape is added under its primitive
    container. Payloads and flags of unrelated existing nodes remain intact.
    """
    from copy import deepcopy
    from sr_impex.definitions.base_types import NodeInformation,RootNodeInformation
    from sr_impex.definitions.enums import MagicValues
    table,hierarchy,count,hierarchy_end,entries=container_nodes(source)
    stream=BytesIO(source);stream.seek(table)
    root_info=RootNodeInformation().read(stream)
    infos={i:NodeInformation().read(stream) for i in range(1,count)}
    stream.seek(hierarchy);root_node=RootNode().read(stream)
    nodes={}
    for _ in range(count-1):
        node=Node().read(stream);nodes[node.info_index]=node
    records={}
    for i,(name,start,length) in entries.items():
        parent,_,_,flags=unpack('<4i',pack('16b',*infos[i].spacer))
        if not 0<=parent<count or parent==i:raise ValueError('Invalid parent link; tree editing is unsafe')
        records[i]={'name':name,'info':infos[i],'node':nodes[i],
                    'parent':parent,'flags':flags,'payload':source[start:start+length]}
    removing={i for i,r in records.items() if r['name'] in removals}
    # Removing primitive collisions does not remove same-name geometry children.
    if 'collisionShape' in removals:
        removing={i for i in removing if records[i]['name']!='collisionShape' or
            records.get(records[i]['parent'],{}).get('name')=='CGeoPrimitiveContainer'}
    while True:
        more={i for i,r in records.items() if r['parent'] in removing}
        if more<=removing:break
        removing|=more
    records={i:r for i,r in records.items() if i not in removing}
    next_id=max([0]+list(records))+1
    for name,payload in additions.items():
        existing=next((i for i,r in records.items() if r['name']==name and
            (name!='collisionShape' or records.get(r['parent'],{}).get('name')=='CGeoPrimitiveContainer')),None)
        if existing is not None:
            records[existing]['payload']=bytes(payload);continue
        if name not in MagicValues:raise ValueError(f'No verified node identifier for {name}')
        parent=0
        if name=='collisionShape':
            parent=next((i for i,r in records.items() if r['name']=='CGeoPrimitiveContainer'),None)
            if parent is None:raise ValueError('Primitive collision needs CGeoPrimitiveContainer')
        info=NodeInformation(identifier=next_id,node_name=name)
        records[next_id]={'name':name,'info':info,'node':Node(next_id,name),
                          'parent':parent,'flags':0,'payload':bytes(payload)}
        next_id+=1
    order=[];queue=[0];visited=set()
    while queue:
        parent=queue.pop(0)
        children=sorted((i for i,r in records.items() if r['parent']==parent),
                        key=lambda i:records[i]['info'].magic&0xffffffff)
        if any(i in visited for i in children):raise ValueError('Resource tree contains a cycle')
        order.extend(children);visited.update(children);queue.extend(children)
    if len(order)!=len(records):raise ValueError('Resource tree contains unreachable nodes')
    remap={old:i+1 for i,old in enumerate(order)};remap[0]=0
    payloads=[];cursor=20
    for old in order:
        record=records[old];info=record['info'];payload=record['payload']
        info.offset,info.node_size=cursor,len(payload);cursor+=len(payload);payloads.append(payload)
        children=[remap[i] for i in order if records[i]['parent']==old]
        if children and children!=list(range(min(children),min(children)+len(children))):
            raise ValueError('Node children must form a contiguous sibling range')
        info.spacer=list(unpack('16b',pack('<4i',remap[record['parent']],min(children) if children else 0,len(children),record['flags'])))
        record['node'].info_index=remap[old]
    root_children=[remap[i] for i in order if records[i]['parent']==0]
    root_info.one=min(root_children) if root_children else 0
    root_info.node_information_count=len(root_children)
    output=BytesIO();magic,models,_,_,_=unpack('<i4I',source[:20])
    output.write(pack('<i4I',magic,models,cursor,cursor+32*(len(order)+1),len(order)+1))
    for payload in payloads:output.write(payload)
    root_info.write(output)
    for old in order:records[old]['info'].write(output)
    root_node.write(output)
    for old in order:records[old]['node'].write(output)
    output.write(source[hierarchy_end:])
    return output.getvalue()
