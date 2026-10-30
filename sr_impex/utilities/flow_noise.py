"""Recovered CLavaTurbulenceProcessor alpha channel (foundationr.dll).

The 32-cube is tiled into a 2D atlas with wrap gutters for Blender image nodes.
Texture format and shader position-space parity still require engine comparison.
"""
import json
from pathlib import Path
import numpy as np

PERMUTATION = np.asarray(json.loads((Path(__file__).resolve().parents[1] /
    'resources' / 'flow_permutation.json').read_text(encoding='utf8')),dtype=np.int32)


def perlin(x,y,z):
    x,y,z=np.broadcast_arrays(np.asarray(x,dtype=np.float32),np.asarray(y,dtype=np.float32),np.asarray(z,dtype=np.float32))
    X=np.floor(x).astype(np.int32)&255;Y=np.floor(y).astype(np.int32)&255;Z=np.floor(z).astype(np.int32)&255
    x=x-np.floor(x);y=y-np.floor(y);z=z-np.floor(z)
    fade=lambda t:t*t*t*(t*(t*6-15)+10)
    u,v,w=fade(x),fade(y),fade(z)
    p=PERMUTATION
    def grad(hash_value,a,b,c):
        h=hash_value&15
        first=np.where(h<8,a,b)
        second=np.where(h<4,b,np.where((h==12)|(h==14),a,c))
        return np.where(h&1,-first,first)+np.where(h&2,-second,second)
    def lookup(a,b,c):return p[(p[(p[a&255]+b)&255]+c)&255]
    def mix(a,b,t):return a+t*(b-a)
    x0=mix(grad(lookup(X,Y,Z),x,y,z),grad(lookup(X+1,Y,Z),x-1,y,z),u)
    x1=mix(grad(lookup(X,Y+1,Z),x,y-1,z),grad(lookup(X+1,Y+1,Z),x-1,y-1,z),u)
    x2=mix(grad(lookup(X,Y,Z+1),x,y,z-1),grad(lookup(X+1,Y,Z+1),x-1,y,z-1),u)
    x3=mix(grad(lookup(X,Y+1,Z+1),x,y-1,z-1),grad(lookup(X+1,Y+1,Z+1),x-1,y-1,z-1),u)
    return mix(mix(x0,x1,v),mix(x2,x3,v),w)


def alpha_cube(size=32):
    z,y,x=np.indices((size,size,size),dtype=np.float32)
    # Processor Begin receives reciprocal dimensions; its scale is .33 / step.
    x*=np.float32(.33);y*=np.float32(.33);z*=np.float32(.33)
    shift=np.float32(.33)
    return np.clip(np.float32(.5)+np.float32(.354)*(perlin(x-shift,y,z)+perlin(x,y,z)+
                   perlin(x,y,z-shift)+perlin(x-shift,y,z-shift)),0,1)


def alpha_atlas(size=32):
    cube=alpha_cube(size);out=np.empty((size+2,size*(size+2),4),dtype=np.float32)
    for z in range(size):
        tile=np.pad(cube[z],((1,1),(1,1)),mode='wrap')
        out[:,z*(size+2):(z+1)*(size+2),:3]=tile[:,:,None]
        out[:,z*(size+2):(z+1)*(size+2),3]=1
    return out
