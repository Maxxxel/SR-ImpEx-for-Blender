"""Preserve imported material blocks that the Blender UI cannot fully represent."""
from base64 import b64decode, b64encode
from io import BytesIO
import json

from sr_impex.definitions.mesh_definitions import EmptyString, Flow, LevelOfDetail, Materials, Refraction

METADATA_KEY = '_drs_material_metadata_v1'
_WIND_FIELDS = {1668510776: 'wind_response', 1668510777: 'wind_height'}


def _encode(value):
    stream = BytesIO()
    value.write(stream)
    return b64encode(stream.getvalue()).decode('ascii')


def _decode(value, cls):
    stream = BytesIO(b64decode(value, validate=True))
    result = cls().read(stream)
    if stream.read(1):
        raise ValueError('Trailing bytes in preserved DRS material block')
    return result


def capture_metadata(mesh, flow_state, wind_state, refraction_state=None):
    """Return a JSON blob for one imported mesh, plus its editable UI state."""
    return json.dumps({
        'version': 1,
        'material_id': mesh.material_id,
        'textures': [{'identifier': texture.identifier, 'name': texture.name}
                     for texture in mesh.textures.textures if texture.name],
        'materials': _encode(mesh.materials),
        'level_of_detail': _encode(mesh.level_of_detail) if mesh.material_parameters != -86061055 else None,
        'strings': _encode(mesh.empty_string) if mesh.material_parameters in (-86061053, -86061052, -86061051, -86061050) else None,
        'flow': _encode(mesh.flow) if mesh.material_parameters == -86061050 else None,
        'refraction': _encode(mesh.refraction),
        'flow_state': flow_state,
        'wind_state': wind_state,
        'refraction_state': refraction_state,
    }, separators=(',', ':'), allow_nan=False)


def missing_texture_ids(mesh, blob):
    """Find named source texture slots absent from the generated material.

    This is advisory: a matching identifier does not prove that the image or
    its contents were preserved. Older metadata has no texture inventory.
    """
    data = json.loads(blob)
    if data.get('version') != 1:
        raise ValueError('Unsupported preserved DRS material metadata version')
    generated = {texture.identifier for texture in mesh.textures.textures if texture.name}
    return sorted({texture['identifier'] for texture in data.get('textures', [])
                   if texture.get('name') and texture['identifier'] not in generated})


def restore_metadata(mesh, blob, flow_state, wind_state, refraction_state=None):
    """Restore unedited blocks, retaining artist changes to exposed controls."""
    data = json.loads(blob)
    if data.get('version') != 1:
        raise ValueError('Unsupported preserved DRS material metadata version')
    # The exporter currently constructs material ID 25702. Other material
    # types can interpret identically named constant slots differently.
    if data.get('material_id') is not None and data['material_id'] != mesh.material_id:
        return False
    materials = _decode(data['materials'], Materials)
    # The exporter has already applied artist wind edits to its default list.
    # Use these values only when the user changed the imported controls; this
    # also avoids replacing an original value clamped by a Blender property.
    if data.get('wind_state') != wind_state and wind_state is not None:
        generated = {m.identifier: m for m in mesh.materials.materials if m.identifier in _WIND_FIELDS}
        for identifier, attr in _WIND_FIELDS.items():
            previous = data.get('wind_state') or {}
            if previous.get(attr) == wind_state.get(attr):
                continue
            desired = generated.get(identifier)
            if desired is None:
                continue
            existing = [m for m in materials.materials if m.identifier == identifier]
            if existing:
                for material in existing:
                    setattr(material, attr, getattr(desired, attr))
            elif getattr(desired, attr) != 0:
                materials.materials.append(desired)
        materials.length = len(materials.materials)
    mesh.materials = materials
    if data.get('level_of_detail') is not None:
        mesh.level_of_detail = _decode(data['level_of_detail'], LevelOfDetail)
    if data.get('strings') is not None:
        mesh.empty_string = _decode(data['strings'], EmptyString)
    if data.get('flow') is not None and data.get('flow_state') == flow_state:
        mesh.flow = _decode(data['flow'], Flow)
    if data.get('refraction') is not None and data.get('refraction_state') == refraction_state:
        mesh.refraction = _decode(data['refraction'], Refraction)
    return True
