"""Loss-aware artist metadata for SKA; no Blender dependencies."""
import json
import math
from struct import pack, unpack
from sr_impex.definitions.ska_definitions import SKAHeader, SKAKeyframe

ALPHA_ID = 0x16C2CE77
ALPHA_PATH = '["sr_ska_alpha"]'
RAW_TRACKS = 'ska_preserved_tracks'


def capture_track(ska, header):
    start, end = header.tick, header.tick + header.interval
    if start < 0 or end > len(ska.times) or end > len(ska.keyframes):
        raise ValueError('SKA track points outside the keyframe arrays')
    keys = ska.keyframes[start:end]
    return {'bone_id': header.bone_id, 'type': header.type,
            'times': list(ska.times[start:end]),
            'keyframes': [[getattr(k, name) for name in
                ('x','y','z','w','tan_x','tan_y','tan_z','tan_w')] for k in keys]}


def append_preserved_tracks(ska, records, represented):
    """Absent skeleton joints and special channels remain valid shared tracks."""
    for row in records:
        key = int(row['bone_id']), int(row['type'])
        if key in represented:
            continue
        times, values = row['times'], row['keyframes']
        if len(times) != len(values):
            raise ValueError('Preserved SKA time/keyframe count mismatch')
        ska.headers.append(SKAHeader(tick=len(ska.times), interval=len(times),
            type=key[1], bone_id=key[0]))
        ska.times.extend(float(t) for t in times)
        ska.keyframes.extend(SKAKeyframe(*value) for value in values)
    ska.header_count, ska.time_count = len(ska.headers), len(ska.times)


def marker_rows(metadata):
    buffer = bytes.fromhex(metadata.get('annotation_hex',''))
    rows = []
    for raw in metadata.get('text_markers_hex',[]):
        time, offset, length = unpack('<fHH', bytes.fromhex(raw))
        if offset + length > len(buffer):
            raise ValueError('SKA marker references bytes outside its annotation buffer')
        payload = buffer[offset:offset+length]
        rows.append({'time':time, 'text':payload.rstrip(b'\0').decode('utf8',errors='surrogateescape'),
                     'raw_hex':payload.hex(), 'offset':offset, 'length':length})
    return rows


def edit_markers(metadata, rows, target_ids):
    """Retain unrelated bytes and reuse untouched slices; append edited strings."""
    buffer = bytearray.fromhex(metadata.get('annotation_hex',''))
    markers = []
    for row in rows:
        time = float(row['time'])
        if not math.isfinite(time) or not 0 <= time <= 1:
            raise ValueError('Marker time must be normalized to 0–1')
        payload = row['text'].encode('utf8',errors='surrogateescape')
        old = bytes.fromhex(row.get('raw_hex',''))
        old_text = old.rstrip(b'\0').decode('utf8',errors='surrogateescape')
        offset, length = int(row.get('offset',-1)), int(row.get('length',0))
        if (row['text'] == old_text and offset >= 0 and
                bytes(buffer[offset:offset+length]) == old):
            payload = old
        else:
            offset, length = len(buffer), len(payload)
            if offset > 65535 or length > 65535:
                raise ValueError('SKA marker offset and length are limited to 65535 bytes')
            buffer.extend(payload); buffer.append(0)
        markers.append(pack('<fHH',time,offset,len(payload)).hex())
    ids = [int(value,0) if isinstance(value,str) else int(value) for value in target_ids]
    if any(not 0 <= value <= 0xffffffff for value in ids):
        raise ValueError('Target IDs must be uint32 values')
    return {'target_ids':ids,'text_markers_hex':markers,'annotation_hex':buffer.hex()}


def action_tail(action):
    return json.loads(action.get('ska_tail_metadata','{}'))


def reorder_tracks(ska, order):
    records = [capture_track(ska,h) for h in ska.headers]
    sorted_records = []
    for key in order:
        index = next((i for i,r in enumerate(records) if [r['bone_id'],r['type']]==list(key)),None)
        if index is not None:sorted_records.append(records.pop(index))
    sorted_records.extend(records)
    ska.headers, ska.times, ska.keyframes = [], [], []
    append_preserved_tracks(ska,sorted_records,set())
