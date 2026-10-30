"""Traced CPtlEmitter color and blend inputs; not the SFP enum namespace."""
import numpy as np
import struct
import math
from functools import lru_cache

# 112BD994 table, consumed by 10B32740. These routes reproduce RGB blending
# with neutral fog/fade blend constants. Scene fog/glow need separate passes.
BLEND_PRESETS=(0x302,0x323,0x325,0x326,0x328,0x32c,0x32e,0x32f)
SURFACE_ROUTES={1:0x304,2:0x305,4:0x305,5:0x30b}


def alpha_only_dds(raw):
    """Extract the base mip of DDS A8; never reinterpret RGB/luminance DDS."""
    if len(raw)<128 or raw[:4]!=b'DDS ':return None
    size,flags,fourcc,bits,r,g,b,a=struct.unpack_from('<8I',raw,76)
    if (size,flags,fourcc,bits,r,g,b,a)!=(32,2,0,8,0,0,0,255):return None
    height,width,pitch=struct.unpack_from('<3I',raw,12)
    if not width or not height or width*height>16_777_216:raise ValueError('A8 texture exceeds preview bounds')
    pitch=max(width,pitch) if struct.unpack_from('<I',raw,8)[0]&8 else width
    if len(raw)<128+pitch*height:raise ValueError('Truncated A8 DDS')
    return width,height,b''.join(raw[128+y*pitch:128+y*pitch+width] for y in range(height))


def colors(start,end,alpha_start,alpha_end,age,lifetime):
    # 10BC1CA0/10BC1CF0 square RGB into CPtlEmitter +54/+64.
    # 10DF8CF0 routes alpha 12/13 to the matching RGBA.w fields.
    weight=np.clip(np.asarray(age)/np.maximum(lifetime,1e-8),0.,1.)
    a=np.asarray(start,dtype=float)**2;b=np.asarray(end,dtype=float)**2
    return a[None,:]+(b-a)[None,:]*weight[:,None],alpha_start+(alpha_end-alpha_start)*weight


@lru_cache(maxsize=16)
def samples(count):
    """CPtlMesh::InitParticles (10BC4320), one shared deterministic mesh."""
    seed=0xa2f42f08
    def integer():
        nonlocal seed
        seed=(seed*0xea8965f5)&0xffffffff
        return seed
    def scalar():
        value=integer()
        return float(np.float32((value if value<0x80000000 else value-0x100000000)/4294967296.))
    def vector():
        value=np.array([scalar(),scalar(),scalar()],dtype='float32')
        length=float(np.linalg.norm(value))
        return value/length if length>np.finfo('float32').eps else value
    position=[];direction=[];phase=[];random=[]
    for _ in range(count):
        position.append(vector());direction.append(vector())
        phase.append(scalar());scalar()  # tangent.y: not consumed by emitter VS
        random.append(scalar()+.5)
        for _ in range(16):integer()  # four packed corner colors
    result=(np.asarray(position).reshape((-1,3)),np.asarray(direction).reshape((-1,3)),np.asarray(phase),np.asarray(random))
    for value in result:value.setflags(write=False)
    return result


def playback_time(time,mode):
    """CPtlParticleSystem::GetPlaybackTime (10BC4D20), native modes 0–9."""
    if mode==0:return math.fmod(time,1.)
    if mode==1:return 1.-math.fmod(time,1.)
    if mode==2:
        phase=math.fmod(time,2.)
        return 2.-phase if phase>1 else phase
    if mode==3:return .5+.5*math.sin(time*math.pi)
    if mode==4:return math.sin(time*math.pi)**4
    if mode==5:
        phase=math.fmod(time,1.)
        return phase*phase+.5*math.sin(phase*2*math.pi)
    if mode in (6,7,8,9):
        multiplier,divisor=(15.,31.) if mode in (6,7) else (6.,13.)
        phase=math.fmod(time,2.)*multiplier
        return -phase/(divisor*(phase-divisor)) if mode in (6,8) else phase/(1.+phase)+1./divisor
    return time  # native default branch


def evaluate(tracks,time,duration,data,warn=lambda message:None):
    """Emitter VS 0/1 local trajectory and color/size age, not an SFP birth sim.

    CPU field layout: 109BFE20; uniforms: 10BC2B50; shader: emitter_sm4_0.
    The returned coordinates are emitter-local. Apply its attachment matrix once.
    Scene trails, fog, soft intersections and random corner colors remain separate.
    """
    value=lambda key,default:tracks.value(key,time,default,duration)
    start,direction,phase,random=data
    mode=int(round(value(34,0)))
    clock=playback_time(time*value(33,.3),mode)
    phase=phase*value(29,.9)+clock
    phase=phase-np.floor(phase)
    age=phase*(1-value(30,0.))+value(30,0.)
    scale=value(25,4.8)
    velocity=(1-value(35,0.)*random)[:,None]*direction*np.asarray(value(27,(.27,.27,.27)))*scale
    force=np.asarray(value(26,(0.,0.,0.)))*scale
    gravity=np.asarray(value(28,(0.,0.,0.)))*max(1.,scale)
    positions=start*np.asarray(value(32,(0.,0.,0.)))+age[:,None]*(velocity+force+age[:,None]*gravity)
    # StartEndWeighting: the shader bends size/color age, not spatial age.
    bias=value(18,0.)
    weight=phase+abs(bias)*((.5+.5*bias)*phase**8+(.5-.5*bias)*phase**.125-phase)
    rgb,alpha=colors(value(10,(1.,1.,0.)),value(11,(0.,0.,1.)),value(12,1.),value(13,.5),weight,np.ones(len(age)))
    start_size,end_size=value(16,.381),value(17,.715)
    size=(start_size+(end_size-start_size)*weight)*(1-value(21,0.)+random*value(21,0.))
    active=max(0,int(round(value(36,250))))
    alpha=alpha*(np.arange(len(age))<active)
    return positions,{'color':rgb,'alpha':alpha,'size':size,
        'rotation':value(39,0.)*2*math.pi*direction[:,0]+time*value(31,math.pi),
        'emissive':np.zeros_like(rgb),'glow':np.ones(len(age)),
        'atlas':np.full(len(age),int(value(24,0)),dtype='int32')}
