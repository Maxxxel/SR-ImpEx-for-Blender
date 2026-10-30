"""Search hints from asset names/paths, never engine effect-type enums."""
GROUPS=[('ALL','All Resources',''),('PERSISTENT','Persistent / Ambient',''),
 ('FIRE','Fire / Smoke / Lava',''),('WATER','Water / Ice',''),('NATURE','Nature / Poison',''),
 ('MAGIC','Magic / Spells',''),('COMBAT','Weapons / Impacts',''),
 ('BUILDING','Buildings / Destruction',''),('WEATHER','Weather / Environment',''),('OTHER','Other','')]
_HINTS={
 'PERSISTENT':('perm','ambient','loop','idle'),
 'FIRE':('fire','flame','smoke','lava','magma','burn','vulcan','volcan'),
 'WATER':('water','ice','frost','snow','freeze','splash','wave'),
 'NATURE':('nature','poison','plant','heal','root','thorn','spore'),
 'MAGIC':('spell','magic','cast','aura','portal','teleport','enchant'),
 'COMBAT':('attack','impact','hit','weapon','projectile','arrow','sword','cannon','explosion'),
 'BUILDING':('building','destruct','debris','gridcrush','tower','wall','rubble'),
 'WEATHER':('weather','rain','wind','storm','cloud','fog','environment'),
}


def groups(name):
    name=name.replace('\\','/').lower()
    result={key for key,words in _HINTS.items() if any(word in name for word in words)}
    return result or {'OTHER'}


def label(name):
    tags=groups(name)
    short={'PERSISTENT':'Persistent','FIRE':'Fire','WATER':'Water / Ice','NATURE':'Nature',
           'MAGIC':'Magic','COMBAT':'Combat','BUILDING':'Building','WEATHER':'Environment','OTHER':'Other'}
    return ' · '.join(short[key] for key,title,_ in GROUPS if key in tags)
