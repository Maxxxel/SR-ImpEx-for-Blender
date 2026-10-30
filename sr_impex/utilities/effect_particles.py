"""Audited SFP render ramps, independent of Blender.

Foundation 10E48610: sources 1..5; float destinations 1..7 and vector
destinations 1/2. Curves are presampled to 128 entries, as 1009AF20 does.
"""
import numpy as np
from sr_impex.utilities.effect_tracks import sample_keys


class Ramp:
    def __init__(self,track):
        self.mode=track.track_mode
        self.table=np.asarray([sample_keys(track,i/127.) for i in range(128)],dtype='float32')

    def evaluate(self,values):
        values=np.asarray(values)
        if self.mode==0:values=np.fmod(values,1.)
        elif self.mode==1:values=np.abs(1.-2.*np.fmod(values,1.))
        position=np.clip(values*127.,0.,127.)
        low=np.floor(position).astype('int32');high=np.ceil(position).astype('int32')
        weight=position-low
        if self.table.ndim>1:weight=weight[...,None]
        return self.table[low]+(self.table[high]-self.table[low])*weight


class SfpRamps:
    def __init__(self,element,warn=lambda value:None):
        self.warn=warn
        self.ramps={}
        for track in element.tracks:
            if track.evaluation_type==1 and track.track_type in (0,1,2,3):
                try:self.ramps[track.track_type]=Ramp(track)
                except ValueError as exc:warn(str(exc))

    def apply(self,tracks,time,duration,age,lifetime,velocity,rotation,angular_velocity,defaults):
        state={key:np.array(value,copy=True) for key,value in defaults.items()}
        def source(kind,scale):
            if kind==1:return age/np.maximum(lifetime,1e-8)
            if kind==2:return np.linalg.norm(velocity,axis=1)*scale
            if kind==3:return age/(scale if abs(scale)>1e-8 else 1e-8)
            if kind==4:return rotation*scale
            if kind==5:return angular_velocity*scale
            if kind!=0:self.warn(f'Unknown SFP ramp input {kind}')
            return None
        targets={1:'alpha',2:'glow',3:'size',4:'rotation',5:'parameter54',6:'density',7:'atlas'}
        for vector in (False,True):
            for index in range(2):
                target=int(tracks.value((119 if vector else 117)+index,time,0.,duration))
                # The engine counts contiguous active targets from index zero.
                if target==0:break
                input_type=int(tracks.value((115 if vector else 113)+index,time,0.,duration))
                values=source(input_type,float(tracks.value((123 if vector else 121)+index,time,1.,duration)))
                ramp=self.ramps.get(index+(2 if vector else 0))
                if values is None or ramp is None:continue
                result=ramp.evaluate(values)
                if vector:
                    if target in (1,2):state['color' if target==1 else 'emissive']=result
                    else:self.warn(f'Unknown SFP vector ramp output {target}')
                elif target in targets:
                    if target in (5,6):
                        self.warn(f'SFP ramp output {targets[target]} is evaluated but has no established Blender shader route')
                    if target==4:result=np.radians(result)
                    elif target==6:result=np.floor(result*255/3).astype('uint8')
                    elif target==7:result=np.floor(result).astype('int32')%256
                    state[targets[target]]=result
                else:self.warn(f'Unknown SFP scalar ramp output {target}')
        return state
