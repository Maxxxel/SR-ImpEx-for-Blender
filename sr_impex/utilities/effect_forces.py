"""Seekable, bounded SFP force preview based on 10DC7610.

Unreduced motion uses the native 60 Hz gravity/damping order. The random
generator and reduced caches remain preview substitutes. Force types
0..5 follow the engine consumers, with substitute random directions for type 3.
Uniform force (4) offsets positions, rather than accelerating velocities.
"""
import numpy as np
import math


def step_force(position,velocity,dt,kind,center,radius=0.,strength=0.,resilience=0.,
               uniform=(0.,0.,0.),axis=(0.,1.,0.),rotation_speed=0.,
               minimum=0.,maximum=0.,height=0.,kill_radius=0.,distortion_offset=0.,random_direction=None):
    center=np.broadcast_to(center,position.shape)
    radius,strength,resilience,rotation_speed,minimum,maximum,height,kill_radius=[
        np.broadcast_to(value,(len(position),)) for value in
        (radius,strength,resilience,rotation_speed,minimum,maximum,height,kill_radius)]
    delta=center-position
    distance=np.linalg.norm(delta,axis=1)
    normal=delta/np.maximum(distance[:,None],1e-8)
    alive=np.ones(len(position),dtype=bool)
    if kind==0:
        mask=(distance>1e-8)&((radius<=0)|(distance<radius))
        velocity[mask]+=normal[mask]*np.asarray(strength)[mask,None]*dt
        alive[mask&(distance<kill_radius)]=False
    elif kind in (1,2):
        mask=(distance>1e-8)&((distance<radius) if kind==1 else (distance>radius))
        position[mask]=center[mask]-normal[mask]*np.asarray(radius)[mask,None]
        impulse=normal[mask]*np.asarray(resilience)[mask,None]
        velocity[mask]+=(-impulse if kind==1 else impulse)
    elif kind==4:
        position+=np.asarray(uniform)*dt
    elif kind==3:
        # Engine 10DC7610 uses a fixed 0.1 factor with its random perturbation.
        # The preview scales by its own dt instead of depending on UI FPS.
        mask=(distance>1e-8)&(distance<radius)
        offset=np.broadcast_to(distortion_offset,(len(position),))
        falloff=1.-(offset+(radius-offset)*distance)
        direction=np.broadcast_to((0.,1.,0.) if random_direction is None else random_direction,position.shape)
        velocity[mask]+=direction[mask]*(strength*falloff)[mask,None]*dt
    elif kind==5:
        axis=np.broadcast_to(axis,position.shape)
        axis=axis/np.maximum(np.linalg.norm(axis,axis=1)[:,None],1e-8)
        offset=position-center
        along=np.sum(offset*axis,axis=1)
        radial=offset-along[:,None]*axis
        distance=np.linalg.norm(radial,axis=1)
        radial/=np.maximum(distance[:,None],1e-8)
        tangent=np.cross(radial,axis)
        direction=velocity/np.maximum(np.linalg.norm(velocity,axis=1)[:,None],1e-8)
        factor=1.-np.sum(tangent*direction,axis=1)
        mask=(distance>minimum)&(distance<maximum)&(np.abs(along)<height)
        acceleration=(-np.asarray(strength)[:,None]*radial
            +np.asarray(rotation_speed)[:,None]*factor[:,None]*tangent)
        velocity[mask]+=acceleration[mask]*dt
    return alive


def interpolate(times,values,query):
    query=np.asarray(query)
    high=np.clip(np.searchsorted(times,query,side='right'),1,len(times)-1)
    low=high-1
    weight=np.clip((query-times[low])/np.maximum(times[high]-times[low],1e-8),0,1)
    weight=weight.reshape((*weight.shape,*([1]*(values.ndim-1))))
    return values[low]+(values[high]-values[low])*weight


def bake(item,fields,times,motion,gravity_axis,warn,seed=0,point_budget=2_000_000):
    life,births,directions,system,count=item.particle_data
    n=len(births)
    if not n:return None
    # Native system +1084 = float 1/60 (1111F638). Damping and gravity
    # are applied per step, not multiplied by the UI frame interval.
    requested=max(2,math.ceil(life*60)+1)
    steps=min(300,requested,max(2,point_budget//n))
    if steps<requested:warn('SFP motion history uses reduced sampling to bound memory')
    dt=(1/60.) if steps==requested else life/(steps-1)
    matrices=interpolate(times,motion[id(item)],births+item.start)
    position=matrices[:,:3,3].copy()
    if item.birth_state is not None:
        position+=np.einsum('nij,nj->ni',matrices[:,:3,:3],item.birth_state['offset'])
        speed=item.birth_state['speed']
    else:speed=np.array([item.tracks.value(102,t,1.,item.duration) for t in births])
    velocity=np.einsum('nij,nj->ni',matrices[:,:3,:3],directions)
    velocity/=np.maximum(np.linalg.norm(velocity,axis=1)[:,None],1e-8)
    velocity*=speed[:,None]
    mass=item.birth_state.get('mass',np.ones(n)) if item.birth_state is not None else np.ones(n)
    history=np.empty((n,steps,3),dtype='float32');history[:,0]=position
    velocity_history=np.empty_like(history);velocity_history[:,0]=velocity
    live=np.ones((n,steps),dtype=bool)
    caches=[]
    for field in fields:
        scalars={key:np.array([field.tracks.value(key,t-field.start,default,field.duration) for t in times])
                 for key,default in ((125,0.),(110,0.),(126,0.),(127,0.),(128,0.),(153,0.),
                                     (156,0.),(157,0.),(158,0.),(159,0.))}
        vector=np.array([field.tracks.value(155,t-field.start,(0.,0.,0.),field.duration) for t in times])
        caches.append((field,scalars,vector))
    gravity=np.array([system[1].value(97,t-item.start,0.,item.duration)/100. for t in times])
    damping=np.array([system[1].value(98,t-item.start,0.,item.duration)/100. for t in times])
    rng=np.random.default_rng(seed)
    for index in range(1,steps):
        query=births+item.start+(index-1)*dt
        for field,scalars,uniform in caches:
            values={key:interpolate(times,value,query) for key,value in scalars.items()}
            matrices=interpolate(times,motion[id(field)],query)
            center=matrices[:,:3,3]
            force=np.einsum('nij,nj->ni',matrices[:,:3,:3],interpolate(times,uniform,query))
            kinds=np.rint(values[125]).astype('int32')
            active=(query>=field.start)&(query<=field.start+field.duration)
            for kind in np.unique(kinds[active]):
                if kind not in (0,1,2,3,4,5):
                    warn(f'SFP force type {kind} is not simulated');continue
                mask=active&(kinds==kind)
                p=position[mask].copy();v=velocity[mask].copy()
                random_direction=None
                if kind==3:
                    warn('SFP distortion field uses a deterministic RNG/timestep substitute')
                    random_direction=rng.normal(size=p.shape)
                    random_direction/=np.maximum(np.linalg.norm(random_direction,axis=1)[:,None],1e-8)
                survives=step_force(p,v,dt,int(kind),center[mask],values[128][mask],values[110][mask],
                    values[126][mask],force[mask],matrices[mask,:3,1],values[156][mask],
                    values[157][mask],values[158][mask],values[159][mask],values[153][mask],
                    values[127][mask],random_direction)
                position[mask]=p;velocity[mask]=v
                live[mask,index]=survives
        velocity-=interpolate(times,gravity,query)[:,None]*np.asarray(gravity_axis)[None,:]*(dt*60.)
        factor=1.-interpolate(times,damping,query)/mass
        # Preserve the native factor's sign (no invented clamp). Reduced
        # caches approximate its decay; the normal path is exactly one step.
        factor=np.sign(factor)*np.abs(factor)**(dt*60.)
        velocity*=factor[:,None]
        position+=velocity*dt
        live[:,index]&=live[:,index-1]
        history[:,index]=position
        velocity_history[:,index]=velocity
    return history,live,dt,velocity_history


def evaluate(cache,indices,age):
    history,live,dt,velocity=cache
    pos=np.clip(age/dt,0,history.shape[1]-1)
    low=np.floor(pos).astype('int32');high=np.minimum(low+1,history.shape[1]-1)
    return (history[indices,low]+(history[indices,high]-history[indices,low])*(pos-low)[:,None],
            live[indices,low],
            velocity[indices,low]+(velocity[indices,high]-velocity[indices,low])*(pos-low)[:,None])
