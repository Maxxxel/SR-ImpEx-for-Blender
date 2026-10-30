"""Read-only adapter for BattleForge building physics Effect XML.

Only the observed building XML subset is accepted. This is not a general FX
editor or a cross-game enum table; unsupported fields are reported explicitly.
"""
import math
from types import SimpleNamespace as NS
import xml.etree.ElementTree as ET
from sr_impex.definitions.fxb_definitions import (
    Element,NodeLink,Physic,PhysicGroup,Track,TrackKeyframe,
)


def number(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('Non-finite building effect XML number')
    return result


def read_building_effect(raw,warn=lambda message:None):
    if len(raw)>8_000_000:raise ValueError('Building effect XML exceeds preview size budget')
    root=ET.fromstring(raw)
    if root.tag!='Effect':raise ValueError('Expected building physics Effect XML')
    seconds=number(root.get('length','5'))
    if seconds<=0:raise ValueError('Building effect XML needs a positive length')
    if len(list(root.iter()))>20000:raise ValueError('Building effect XML exceeds node budget')
    mapping={'PhysicObject':Physic,'PhysicGroup':PhysicGroup}
    def read_track(xml):
        name=xml.get('type');identifier={'Ground Level':75,'Alpha':5}.get(name)
        if identifier is None:
            warn(f'Building XML track {name} is not simulated');return None
        mode={'Loop':0,'Bounce':1,'Clamp':2}.get(xml.get('mode','Clamp'))
        if mode is None or xml.get('dim','TimeElapsed')!='TimeElapsed':
            raise ValueError('Unsupported building XML track addressing')
        entries=[TrackKeyframe(frame=number(e.get('index','0')),data=number(e.get('value','0')))
                 for e in xml.findall('Entry')]
        if not entries:raise ValueError('Building XML curve has no entries')
        if any(a.frame>=b.frame for a,b in zip(entries,entries[1:])):
            raise ValueError('Building XML curve times must increase')
        if any(e.tag!='Entry' for e in xml):raise ValueError('Unsupported building XML curve handles')
        return Track(track_type=identifier,length=number(xml.get('length',str(seconds))),
                     track_dim=0,track_mode=mode,entries=entries)
    def read_element(xml):
        cls=mapping.get(xml.get('type'))
        if cls is None:raise ValueError(f'Unsupported building XML element {xml.get("type")}')
        payload=cls()
        if cls is Physic:payload.physic_file=xml.get('resource','')
        element=Element(name=xml.get('name','Debris'),element_type_header=payload.header)
        setattr(element,cls.__name__.lower(),payload)
        for item in xml:
            if item.tag=='Link':
                link=NodeLink(parent=item.get('parent',''),slot=item.get('slot',''),
                              destination_slot=item.get('destinationslot',''))
                for key in ('world','floor','node','aim','span','locator'):
                    setattr(link,key,int(item.get(key,'0')))
                element.node_link=link
            elif item.tag=='Track':
                track=read_track(item)
                if track is not None:element.tracks.append(track)
            elif item.tag=='Element':element.children.append(read_element(item))
            elif item.tag=='Static':
                # Priority is the engine budget preference, not mass/force.
                if item.get('type')!='Priority':warn(f'Building XML static {item.get("type")} is not simulated')
            else:raise ValueError(f'Unsupported building XML field {item.tag}')
        return element
    children=[]
    for item in root:
        if item.tag=='Element':children.append(read_element(item))
        elif item.tag=='Static':
            value=item.get('value','')
            if item.get('type')=='SoundFilename' and value:
                warn(f'Building XML root sound is not previewed: {value}')
        elif item.tag=='Track':
            # Shipped destruction roots have neutral TRS. Do not invent support
            # for nonneutral root transforms or reinterpret their rotation units.
            neutral={'Translate':(0.,0.,0.),'Rotate':(0.,0.,0.),'Scale':(1.,1.,1.)}.get(item.get('type'))
            entries=item.findall('Entry')
            if neutral is None or not entries or any(tuple(number(e.get(f'value{i}','0')) for i in (1,2,3))!=neutral for e in entries):
                warn(f'Building XML root track {item.get("type")} is not simulated')
        else:raise ValueError(f'Unsupported building XML root field {item.tag}')
    return NS(name=root.get('name','Building destruction'),length=seconds,play_length=seconds,
              special_effect=NS(children=children))
