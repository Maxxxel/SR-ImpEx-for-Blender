"""FX track evaluation without Blender state or filesystem access.

Addressing and explicit Bezier handles follow Foundation's CFxBaseTrack and
TCFxTableInterpolate. Unsupported inputs raise instead of silently becoming time.
"""
from bisect import bisect_right
import math
import random


def components(value):
    if hasattr(value, 'x'):
        return (value.x, value.y, value.z)
    return value


def multiply(a, b):
    if isinstance(a, (tuple,list)):
        return tuple(x*y for x,y in zip(a,b))
    return a*b


def node_active(window,time):
    """CFxNode::IsNodeActive: static Start/End/Loop (8/9/18), in seconds."""
    start,end,period=window
    if start<0 or end<0:return True
    phase=math.fmod(time,period) if period>0 else time
    return start<phase<end


def choose_variant(variants, seed=0):
    """Engine-style percentage buckets, including an intentional no-choice gap."""
    pick = random.Random(seed).randint(1,100)
    accumulated = 0
    for variant in variants:
        accumulated += max(0,int(variant.get('weight',100)))
        if pick <= accumulated:
            return variant
    return None


def normalized_chances(weights):
    """Explicit authoring conversion to integer percentages; never on import."""
    weights=[max(0,int(value)) for value in weights]
    total=sum(weights)
    if not total:raise ValueError('Set at least one chance above zero before normalizing')
    result=[100*value//total for value in weights]
    order=sorted(range(len(weights)),key=lambda i:-(100*weights[i]%total))
    for i in order[:100-sum(result)]:result[i]+=1
    return result


def cubic(a,b,c,d,t):
    return a*(1-t)**3+3*b*t*(1-t)**2+3*c*t*t*(1-t)+d*t**3


def fade_value(events,time):
    """Deterministic persistent-FX fades, including interrupted fades and seeks."""
    begin=0.;duration=0.;initial=target=1.
    def value(at):
        weight=1. if duration<=0 else max(0.,min(1.,(at-begin)/duration))
        return initial+(target-initial)*weight
    for start,goal,seconds in sorted(events):
        if start>time:break
        initial=value(start);begin=start;duration=max(.00001,seconds);target=goal
    return value(time)


def sample(track, elapsed, duration=1., absolute=None, size=1., power=1., random_value=.5):
    keys = track.entries
    if not keys:
        raise ValueError('FX track has no keys')
    if len(keys)==1:
        return components(keys[0].data)
    return sample_keys(track,address_time(track,elapsed,duration,absolute,size,power,random_value))


def address_time(track,elapsed,duration=1.,absolute=None,size=1.,power=1.,random_value=.5):
    """Convert an input dimension to the engine's normalized curve domain."""
    inputs=(elapsed, elapsed/max(duration,1e-8), duration-elapsed,
            elapsed if absolute is None else absolute, size, power, random_value)
    if not 0 <= track.track_dim < len(inputs):
        raise ValueError(f'Unsupported FX track dimension {track.track_dim}')
    length=max(float(track.length),1e-8)
    time=inputs[track.track_dim]
    if track.track_mode==0:
        time=math.fmod(time,length)/length
    elif track.track_mode==1:
        time=abs(1-2*math.fmod(time,length)/length)
    elif track.track_mode==2:
        time=max(0.,min(1.,time/length))
    else:
        raise ValueError(f'Unsupported FX address mode {track.track_mode}')
    return time


def sample_keys(track,time):
    keys=track.entries
    i=bisect_right([k.frame for k in keys],time)-1
    if i<0:return components(keys[0].data)
    if i>=len(keys)-1:return components(keys[-1].data)
    a,d=keys[i],keys[i+1]
    t=(time-a.frame)/max(d.frame-a.frame,1e-8)
    av,dv=components(a.data),components(d.data)
    if track.interpolation_type==0:
        if isinstance(av,(tuple,list)):return tuple(x+(y-x)*t for x,y in zip(av,dv))
        return av+(dv-av)*t
    if track.interpolation_type!=1:
        raise ValueError(f'Unsupported FX interpolation {track.interpolation_type}')
    if len(track.control_points)<2*(len(keys)-1):
        raise ValueError('Bezier FX track has no complete explicit handle set')
    b,c=track.control_points[2*i:2*i+2]
    bx=(b.frame-a.frame)/max(d.frame-a.frame,1e-8)
    cx=(c.frame-a.frame)/max(d.frame-a.frame,1e-8)
    # The scalar engine path performs three Newton iterations on handle time.
    u=t
    for _ in range(3):
        derivative=3*(1-u)**2*bx+6*(1-u)*u*(cx-bx)+3*u*u*(1-cx)
        if derivative==0:break
        u-=(cubic(0,bx,cx,1,u)-t)/derivative
    bv,cv=components(b.data),components(c.data)
    if isinstance(av,(tuple,list)):
        return tuple(cubic(x,y,z,w,u) for x,y,z,w in zip(av,bv,cv,dv))
    return cubic(av,bv,cv,dv,u)


class TrackSet:
    def __init__(self, element, warn=lambda message:None):
        self.groups={}
        self.warn=warn
        for track in element.tracks:
            if track.evaluation_type==0:
                self.groups.setdefault(track.track_type,[]).append(track)
                if track.track_dim in (4,5,6) and len(track.entries)>1:
                    self.warn('FX size/power/random inputs use neutral preview values')

    def value(self, identifier, time, default=1., duration=1.):
        result=None
        for track in self.groups.get(identifier,[]):
            try:value=sample(track,time,duration)
            except ValueError as exc:
                self.warn(str(exc));continue
            result=value if result is None else multiply(result,value)
        return default if result is None else result
