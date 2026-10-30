"""Cached CPhy-style debris preview with explicit collision/inertia substitutes.

10E38E20: default gravity/force factor 30, update rate 60. 10E360D0:
point fields attract with constant power inside range. Runtime inputs are
mass 76, force 72, body torque 189, point range/power 73/74, group offset 75
and within-group collision 167. Scene triangles and bounding boxes substitute
for the engine's terrain, collision shapes and inertia tensors.
"""
from dataclasses import dataclass
import math
import numpy as np
from mathutils import Matrix,Quaternion,Vector
from sr_impex.utilities.effect_forces import interpolate


@dataclass
class Body:
    item:object
    center:object
    half:object
    scale:object
    position:object
    rotation:object
    group:object
    velocity:object
    angular:object
    positions:object
    rotations:object
    mass:float=1.
    fixed:bool=False


def support(rotation,half,normal):
    axes=rotation.to_matrix()
    return sum(abs(axes.col[i].dot(normal))*half[i] for i in range(3))


def contacts(body,old,tree,origin,up,offset,dt):
    normal=up
    depth=(body.position-origin).dot(up)-offset-support(body.rotation,body.half,up)
    collision=depth<0 and tree is None
    if tree:
        motion=body.position-old
        distance=motion.length
        if distance>1e-8:
            hit,n,_,_=tree.ray_cast(old+up*abs(offset),motion/distance,distance+body.half.length+2*abs(offset))
            if hit is not None:
                if n.dot(motion)>0:n=-n
                penetration=(body.position-hit-up*offset).dot(n)-support(body.rotation,body.half,n)
                if penetration<0:
                    body.position-=penetration*n;normal=n;collision=True
    depth=(body.position-origin).dot(up)-offset-support(body.rotation,body.half,up)
    if tree is None and depth<0:body.position-=depth*up;normal=up;collision=True
    if collision:
        inward=body.velocity.dot(normal)
        if inward<0:body.velocity-=inward*normal  # Default CPhy restitution is zero.
        tangent=body.velocity-body.velocity.dot(normal)*normal
        if tangent.length:
            body.velocity-=tangent*min(1.,.5*30.*dt/max(tangent.length,1e-8))
        body.angular*=max(0.,1.-4.*dt)


def bake(session):
    items=[item for item in session.items if item.kind=='Physic' and item.material_bindings]
    if not items:return
    if len(items)>64:session.warn('Physics simulation capped at 64 debris pieces; remaining pieces retain their start transforms')
    items=items[:64]
    session.warn('Physics uses box inertia/contact proxies, cached scene surfaces and a model-origin ground plane; not the engine CPhy solver')
    duration=(session.frame_end-session.frame_start)/session.fps
    count=min(6001,max(2,math.ceil(duration*60)+1))
    times=np.linspace(0,duration,count);dt=times[1]-times[0]
    if duration>100:session.warn('Physics cache uses reduced sampling for clips over 100 seconds')
    by_obj={item.obj.as_pointer():item for item in session.items}
    groups=[item for item in session.items if item.kind=='PhysicGroup']
    fields=[item for item in session.items if item.kind=='ForcePoint']
    up=(session.base_matrix.to_3x3()@Vector((0,1,0))).normalized()
    origin=session.base_matrix.translation
    bodies=[]
    for item in items:
        corners=[obj.matrix_basis@Vector(corner) for obj in item.obj.children if obj.type=='MESH' for corner in obj.bound_box]
        if not corners:continue
        low=Vector(tuple(min(p[i] for p in corners) for i in range(3)))
        high=Vector(tuple(max(p[i] for p in corners) for i in range(3)))
        center=(low+high)*.5
        initial=Matrix(interpolate(session.motion_times,session.motion[id(item)],item.start))
        _,rotation,scale=initial.decompose()
        half=Vector(tuple(max(.005,(high[i]-low[i])*abs(scale[i])*.5) for i in range(3)))
        parent=item.graph_parent;group=None
        while parent:
            node=by_obj.get(parent.as_pointer())
            if node and node.kind=='PhysicGroup':group=node;break
            siblings=[g for g in groups if g.graph_parent==parent]
            if len(siblings)==1:group=siblings[0];break
            parent=node.graph_parent if node else parent.parent
        if group is None and len(groups)==1:group=groups[0]
        bodies.append(Body(item,center,half,scale,initial@center,rotation,group,
            Vector(),Vector(),np.empty((count,3),dtype='float32'),np.empty((count,4),dtype='float32')))
    for index,time in enumerate(times):
        active=[]
        for body in bodies:
            item=body.item;t=time-item.start
            if index and 0<=t<=item.duration:
                active.append(body)
                mass=float(item.tracks.value(76,t,1.,item.duration))
                body.mass=max(1e-5,mass)
                body.fixed=mass<=0
                if mass<=0:
                    session.warn('Nonpositive physics mass is treated as immovable in preview');continue
                # CPhy::CalculateForce consumes the force vector in world space.
                force=session.base_matrix.to_3x3()@Vector(item.tracks.value(72,t,(0,0,0),item.duration))
                for field in fields:
                    ft=time-field.start
                    if not 0<=ft<=field.duration:continue
                    matrix=Matrix(interpolate(session.motion_times,session.motion[id(field)],time))
                    delta=matrix.translation-body.position;distance=delta.length
                    radius=float(field.tracks.value(73,ft,0.,field.duration))
                    if 1e-8<distance<=radius:
                        force+=delta/distance*float(field.tracks.value(74,ft,0.,field.duration))
                body.velocity+=(force*(30./body.mass)-up*30.)*dt
                torque=Vector(item.tracks.value(189,t,(0,0,0),item.duration))
                inverse=getattr(item,'physics_inverse_inertia',None)
                if inverse is None:
                    inertia=Vector(tuple(body.mass*(body.half[(i+1)%3]**2+body.half[(i+2)%3]**2)/3. for i in range(3)))
                    inverse=tuple(1./max(v,1e-5) for v in inertia)
                body.angular+=Vector(tuple(torque[i]*inverse[i] for i in range(3)))*dt
                if body.angular.length>1e-8:
                    body.rotation=(body.rotation@Quaternion(body.angular.normalized(),body.angular.length*dt)).normalized()
                old=body.position.copy();body.position+=body.velocity*dt
                offset=body.group.tracks.value(75,time-body.group.start,0.,body.group.duration) if body.group else 0.
                contacts(body,old,session.surface,origin,up,float(offset),dt)
        for a_index,a in enumerate(active):
            for b in active[a_index+1:]:
                if getattr(a.item,'physics_no_piece_collision',False) or getattr(b.item,'physics_no_piece_collision',False):continue
                if a.group is b.group and a.group and not a.group.tracks.value(167,time-a.group.start,1.,a.group.duration):continue
                # Bounded broadphase/contact substitute: rotated box AABBs.
                extents=[]
                for body in (a,b):
                    r=body.rotation.to_matrix()
                    extents.append(Vector(tuple(sum(abs(r[row][col])*body.half[col] for col in range(3)) for row in range(3))))
                delta=b.position-a.position
                overlap=extents[0]+extents[1]-Vector(tuple(abs(v) for v in delta))
                if min(overlap)>0:
                    axis=min(range(3),key=lambda k:overlap[k]);normal=Vector();normal[axis]=1. if delta[axis]>=0 else -1.
                    inverse_a=0. if a.fixed else 1./a.mass;inverse_b=0. if b.fixed else 1./b.mass;total=inverse_a+inverse_b
                    if total==0:continue
                    a.position-=normal*overlap[axis]*inverse_a/total
                    b.position+=normal*overlap[axis]*inverse_b/total
                    closing=(b.velocity-a.velocity).dot(normal)
                    if closing<0:
                        impulse=-closing/total
                        a.velocity-=normal*impulse*inverse_a;b.velocity+=normal*impulse*inverse_b
        for body in bodies:
            body.positions[index]=body.position;body.rotations[index]=body.rotation
    for body in bodies:
        body.item.physics_cache=(times,body.positions,body.rotations,body.scale,body.center)


def evaluate(cache,time):
    times,positions,rotations,scale,center=cache
    high=max(1,min(len(times)-1,int(np.searchsorted(times,time,side='right'))));low=high-1
    weight=max(0.,min(1.,(time-times[low])/max(times[high]-times[low],1e-8)))
    position=Vector(positions[low]+(positions[high]-positions[low])*weight)
    rotation=Quaternion(rotations[low]).slerp(Quaternion(rotations[high]),weight)
    matrix=Matrix.LocRotScale(Vector(),rotation,scale)
    matrix.translation=position-matrix.to_3x3()@center
    return matrix
