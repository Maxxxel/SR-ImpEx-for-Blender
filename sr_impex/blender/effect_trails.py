"""Bounded, seekable ribbon preview of CDrwTrailNode motion history.

10E21BC0 + 1009AB40..80: 170/171 start/end width; 172 lifetime;
173 start fade; 174 minimum segment length. Texture is the Trail payload.
Engine spline subdivision, wind and trail-specific ramps remain separate work.
"""
import numpy as np

SEGMENTS=128


def prepare(item):
    mesh=item.geometry.data;mesh.clear_geometry()
    for layer in list(mesh.uv_layers):mesh.uv_layers.remove(layer)
    mesh.from_pydata([(0,0,0)]*(2*SEGMENTS),[],
        [(2*i,2*i+1,2*i+3,2*i+2) for i in range(SEGMENTS-1)])
    mesh.uv_layers.new()
    for name in ('FX Color','FX Emissive'):
        mesh.color_attributes.new(name=name,type='FLOAT_COLOR',domain='POINT')


def update(item,time,times,matrices):
    tr=item.tracks;t=time-item.start;duration=item.duration
    life=max(1e-5,float(tr.value(172,t,1.,duration)))
    lower=max(item.start,time-life);upper=min(time,item.start+duration)
    indices=np.flatnonzero((times>=lower)&(times<=upper))
    if len(indices)>SEGMENTS:indices=indices[np.linspace(0,len(indices)-1,SEGMENTS,dtype='int32')]
    vertices=np.zeros((SEGMENTS,2,3),dtype='float32')
    colors=np.zeros((SEGMENTS,2,4),dtype='float32')
    age=np.zeros(SEGMENTS,dtype='float32')
    n=len(indices)
    if n:
        points=matrices[indices,:3,3]
        age[:n]=time-times[indices]
        minimum=max(0.,float(tr.value(174,t,0.,duration)))
        if minimum>0:
            keep=np.zeros(len(points),dtype=bool);keep[0]=True;last=points[0]
            for index,point in enumerate(points[1:],1):
                if np.linalg.norm(point-last)>=minimum:
                    keep[index]=True;last=point
            indices=indices[keep];points=points[keep];n=len(points)
        age[:n]=time-times[indices]
        width=(float(tr.value(170,t,1.,duration))*(1-age[:n]/life)
               +float(tr.value(171,t,0.,duration))*age[:n]/life)
        alignment=int(tr.value(169,t,0.,duration))
        axis=matrices[indices,:3,min(1,max(0,alignment))]
        axis/=np.maximum(np.linalg.norm(axis,axis=1)[:,None],1e-8)
        vertices[:n,0]=points-axis*width[:,None]*.5
        vertices[:n,1]=points+axis*width[:,None]*.5
        vertices[n:]=vertices[n-1]
        fade=float(tr.value(173,t,0.,duration))
        alpha=np.clip((life-age[:n])/max(life-fade,1e-8),0,1)
        colors[:n,:,:3]=1.;colors[:n,:,3]=alpha[:,None]
    mesh=item.geometry.data
    mesh.vertices.foreach_set('co',vertices.ravel())
    mesh.color_attributes['FX Color'].data.foreach_set('color',colors.ravel())
    cache=getattr(item,'_trail_uv_indices',None)
    if cache is None or len(cache[0])!=len(mesh.loops):
        loop_indices=np.empty(len(mesh.loops),dtype='int32')
        mesh.loops.foreach_get('vertex_index',loop_indices)
        cache=np.divmod(loop_indices,2);item._trail_uv_indices=cache
    point,edge=cache
    uv=np.column_stack((edge,age[point]/life)).astype('float32')
    mesh.uv_layers.active.data.foreach_set('uv',uv.ravel());mesh.update()
