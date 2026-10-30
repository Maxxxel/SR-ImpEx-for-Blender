"""FXB inspection for authoring tools; does not create or rewrite effects."""
from collections import Counter
from pathlib import Path

from sr_impex.core.file_io import FileReader
from sr_impex.definitions.fxb_definitions import FxMaster, _element_type_map
from sr_impex.utilities.resource_container import container_nodes


def read_effect(source):
    raw = bytes(source) if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    _, _, _, _, entries = container_nodes(raw)
    matches = [entry for entry in entries.values() if entry[0] == 'FxMaster']
    if len(matches) != 1:
        raise ValueError('This resource has no FxMaster node')
    _, offset, size = matches[0]
    reader = FileReader(raw[offset:offset+size])
    try:
        master = FxMaster().read(reader)
        if reader.tell() != size:
            raise ValueError(f'FXB parser did not consume the node: {reader.tell()} of {size} bytes')
        return master
    finally:
        reader.close()


def inspect_effect(master):
    counts = Counter()
    def visit(element):
        name = _element_type_map[element.element_type_header].__name__
        counts[name] += 1
        payload = getattr(element, name.lower())
        dependencies = {k:v for k,v in vars(payload).items() if isinstance(v,str) and v}
        link = element.node_link
        return {'name': element.name, 'type': name, 'id': f'{element.element_type_header:08X}',
                'link': {k:getattr(link,k) for k in ('parent','slot','destination_slot','world','node','floor','aim','span','locator')},
                'dependencies':dependencies,
                'tracks':[{'id':t.track_type,'keys':len(t.entries),'dimension':t.track_dim,
                           'address_mode':t.track_mode,'interpolation':t.interpolation_type,
                           'evaluation':t.evaluation_type} for t in element.tracks],
                'materials':[{'material_id':m.material_id,'tracks':[
                    {'semantic':f'{t.semantic:08X}','type':t.parameter_type,'keys':len(t.entries)} for t in m.tracks]} for m in element.materials],
                'children':[visit(e) for e in element.children]}
    tree = [visit(e) for e in master.special_effect.children]
    return {'name':master.name,'length':master.length,'play_length':master.play_length,
            'element_counts':dict(counts),'elements':tree,
            'preview_status':'Inspection only; this report does not claim render support'}
