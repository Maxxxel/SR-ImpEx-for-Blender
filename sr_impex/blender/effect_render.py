"""Renderer capacity settings required for layered FX, without shader changes."""
PREVIOUS='_sr_fx_previous_transparent_depth'
APPLIED='_sr_fx_applied_transparent_depth'


def configure(scene,sessions):
    if not hasattr(scene,'cycles'):return
    count=0
    for session in sessions:
        if session.scene!=scene:continue
        for item in session.items:
            count+=item.particle_data[-1] if item.particle_data else int(item.shader is not None)
    limit=scene.cycles.bl_rna.properties['transparent_max_bounces'].hard_max
    target=max(scene.cycles.transparent_max_bounces,min(limit,count+1))
    if target!=scene.cycles.transparent_max_bounces:
        if PREVIOUS not in scene:scene[PREVIOUS]=scene.cycles.transparent_max_bounces
        scene.cycles.transparent_max_bounces=target;scene[APPLIED]=target
    if count+1>limit:
        for session in sessions:
            if session.scene==scene:session.warn(f'Cycles transparency depth capped at {limit}; extremely dense overlaps can still exceed it')


def restore(scene):
    if PREVIOUS in scene:
        if scene.cycles.transparent_max_bounces==scene.get(APPLIED):
            scene.cycles.transparent_max_bounces=int(scene[PREVIOUS])
        del scene[PREVIOUS]
        if APPLIED in scene:del scene[APPLIED]
