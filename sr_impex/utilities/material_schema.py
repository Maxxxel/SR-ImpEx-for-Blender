"""BattleForge material registrations and renderer-independent preview math.

The schema is build-specific engine evidence, not the former BT channel labels.
Blender BSDFs and the preview RNG are explicit substitutes for the game renderer.
"""
from functools import lru_cache
import json
from pathlib import Path

DEFAULT_ID = 0x6466
COLOR_ID, PARAM_ID, NORMAL_ID = 0x64666673, 0x7370636c, 0x6e726d73
ENV_ID, REF_ID, DISTORTION_ID = 0x656e7674, 0x7263636f, 0x6469636f
SCRATCH_ID, FLUID_ID = 0x63737431, 0x63737432
FLOW_IDS = tuple(range(0x63767431, 0x63767435))

# Preview routes are deliberately scoped by handler: cst1/cst2 and even the
# common texture IDs are reused with unrelated meanings. Routes represent only
# the approximate surface graph inputs, not full engine shader implementations.
_DIFFUSE_SPECULAR = frozenset(('DiffuseSpecular', 'DiffuseSpecularAmbientOcclusion',
    'DiffuseSpecularAmbientOcclusionPerVertex', 'DiffuseSpecularMaskedColor', 'Lava', 'Effect'))
_COMMON_COLOR = frozenset(('Billboard', 'Cliff', 'DynamicDecal', 'SelectionDecal',
    'SimpleTextured', 'Sky', 'StatefulParticles', 'StaticDecal', 'StaticDecalPreview',
    'Std', 'Terrain', 'TerrainMultipass', 'TerrainStripe', 'TerrainStripeMultipass',
    'Textured', 'Trail', 'UIBase'))
_CST1_COLOR = frozenset(('ActionButton', 'ParticleSystem', 'EATextFont', 'SH4'))


def scalar_in_range(entry,value):
    """Compare serialized float32 values with the engine's float32 bounds."""
    from struct import pack,unpack
    def f32(v):return unpack('<f',pack('<f',v))[0]
    try:
        value=f32(value)
        return ('min' not in entry or f32(entry['min'])<=value) and ('max' not in entry or value<=f32(entry['max']))
    except (OverflowError,ValueError):return False


def preview_texture_routes(handler):
    """Map group inputs to serialized texture IDs for the selected handler.

    An absent route is intentional: it avoids presenting an untraced texture
    as a different material's input. Additional maps remain editable/exported.
    """
    routes={}
    if handler=='Default':
        routes={'Color Map':COLOR_ID,'Color Alpha':COLOR_ID,
                'Parameter Map':PARAM_ID,'Parameter Alpha':PARAM_ID,
                'Normal Map':NORMAL_ID,'Refraction Map':REF_ID,'Refraction Alpha':REF_ID,
                'Fluid Color':FLUID_ID,'Fluid Alpha':FLUID_ID,'Scratch Alpha':SCRATCH_ID,'Environment Color':ENV_ID}
    elif handler in _DIFFUSE_SPECULAR:
        routes={'Color Map':COLOR_ID,'Color Alpha':COLOR_ID,
                'Parameter Map':PARAM_ID,'Parameter Alpha':PARAM_ID}
    elif handler in _COMMON_COLOR:
        routes={'Color Map':COLOR_ID,'Color Alpha':COLOR_ID}
        if handler in ('Cliff','StaticDecal','StaticDecalPreview','Terrain','TerrainMultipass',
                       'TerrainStripe','TerrainStripeMultipass','UIBase'):
            routes['Normal Map']=NORMAL_ID
    elif handler in _CST1_COLOR:
        routes={'Color Map':SCRATCH_ID,'Color Alpha':SCRATCH_ID}
    return routes


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).resolve().parents[1]/'resources/material_schema.json'
    return json.loads(path.read_text(encoding='utf8'))['materials']


def schema(name=None, material_id=None):
    for item in catalog():
        if (name is not None and item['name'] == name) or (
                name is None and material_id is not None and int(item['id'],16) == (material_id & 0xffff)):
            return item
    return {'name':'Unknown', 'id':hex((material_id or 0)&0xffff), 'flags':[], 'parameters':{}}


def parameter_name(handler, category, identifier, fallback=None):
    entries = schema(name=handler)['parameters'].get(category, [])
    return next((item['name'] for item in entries if item['id'] == (identifier & 0xffffffff)),
                fallback or f'Unmapped 0x{identifier & 0xffffffff:08X}')


def signed32(value):
    value = int(value) & 0xffffffff
    return value if value < 0x80000000 else value-0x100000000


def signed16(value):
    value = int(value) & 0xffff
    return value if value < 0x8000 else value-0x10000


def registered_mask(handler):
    result = 0
    for flag in schema(name=handler)['flags']:
        result |= int(flag['mask'],16)
    return result


def flow_step(speed, offset, minimum, maximum, change, scale, dt, random_signed):
    """Default setup 106a8950: one shared random value changes XYZ speed.

    Change is per rendered update, not a sine frequency. W speed is not changed
    in that routine. Offset integrates speed * FlowScale * min(dt, 1).
    """
    speed = list(speed)
    for axis in range(3):
        speed[axis] = min(max(speed[axis] + random_signed*change[axis], minimum[axis]), maximum[axis])
    dt = min(dt, 1.0)
    return tuple(speed), tuple(offset[i]+speed[i]*scale[i]*dt for i in range(4))


def flow_timeline(frame_count, fps, minimum, maximum, change, scale, seed=1):
    """Deterministic scrubbing, with an independent MSVC-style preview RNG.

    The game shares rand() with other consumers; this seed cannot reproduce a
    live game's RNG history. The update structure is retained, not that history.
    """
    speed = offset = (0.,)*4
    result = [offset]
    state = seed & 0xffffffff
    for _ in range(max(0, frame_count)):
        state = (214013*state+2531011) & 0xffffffff
        random_signed = (((state >> 16)&32767)/32767.)*2.-1.
        speed, offset = flow_step(speed, offset, minimum, maximum, change, scale,
                                  1./max(fps, 1e-6), random_signed)
        result.append(offset)
    return result


class FlowSequence:
    """Incremental fixed-step preview, with bounded checkpoints for scrubbing.

    Clock and RNG no longer depend on the selected animation's FPS/length.
    Checkpoints store integration state, not a growing list of every frame.
    """
    def __init__(self,minimum,maximum,change,scale,seed=1):
        self.minimum=minimum;self.maximum=maximum;self.change=change;self.scale=scale
        self.index=0;self.state=seed&0xffffffff;self.speed=self.offset=(0.,)*4
        self.checkpoints={0:(self.state,self.speed,self.offset)}

    def _step(self):
        state=(214013*self.state+2531011)&0xffffffff
        random_signed=(((state>>16)&32767)/32767.)*2.-1.
        speed,offset=flow_step(self.speed,self.offset,self.minimum,self.maximum,self.change,self.scale,1./60,random_signed)
        return state,speed,offset

    def sample(self,seconds):
        position=max(0.,float(seconds))*60
        target=int(position);fraction=position-target
        if target<self.index:
            self.index=max(i for i in self.checkpoints if i<=target)
            self.state,self.speed,self.offset=self.checkpoints[self.index]
        while self.index<target:
            self.state,self.speed,self.offset=self._step();self.index+=1
            if self.index%600==0:
                self.checkpoints[self.index]=(self.state,self.speed,self.offset)
                if len(self.checkpoints)>257:del self.checkpoints[min(i for i in self.checkpoints if i)]
        next_offset=self._step()[2]
        return tuple(a+(b-a)*fraction for a,b in zip(self.offset,next_offset))


def fluid_lookup_coordinate(position, scale, offset):
    """The shader's position shear, followed by scale and integrated offset."""
    return tuple((position[i]+(position[(i+1)%3]+position[(i+2)%3])/32.)*scale[i]+offset[i]
                 for i in range(3))


def fluid_lookup_u(noise1, noise2, noise4):
    return (noise1+.5*noise2+.25*noise4)*(4./7.)


def parameter_values(rgba, fluid=False):
    """Flow PS176 uses B for the fluid blend; reflection variants also consume B."""
    return {'smoothness':rgba[0], 'metalness':rgba[1], 'emissivity':rgba[3],
            'flow_mask' if fluid else 'reflectivity':rgba[2]}


def refraction_offset(rg, scale):
    """Default PS158/174: normalized screen displacement, not an IOR."""
    return tuple((component-.5)*scale/256. for component in rg[:2])
