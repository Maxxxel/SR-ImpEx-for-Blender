"""Animation authoring defaults and small starter layouts, not gameplay definitions."""

# CVisAnimationSet / CSkAnimationSet constructors in the Skylords visual DLL.
# The loader does not clamp these floats. Soft UI ranges are editing conveniences.
FLOAT32_MAX = float.fromhex('0x1.fffffep+127')
BASIC_DEFAULTS = {
    'default_run_speed': 4.8,
    'default_walk_speed': 2.3,
    'mode_change_type': 0,
    'hovering_ground': False,
    'fly_bank_scale': 2.0,
    'fly_accel_scale': 0.4,
    'fly_hit_scale': 1.0,
    'align_to_terrain': False,
}

PROFILE_ITEMS = (
    ('STATIC', 'Static Object', 'No skeletal animation mappings; wind and flow do not need SKA clips'),
    ('ANIMATED_OBJECT', 'Animated Object', 'Idle only, for a prop with a skeleton'),
    ('UNIT', 'Unit', 'Idle, Walk, Run, Spawn and Die; add attacks and other reactions as needed'),
    ('BUILDING', 'Building', 'Idle for a skinned building; static building states need no SKA clips'),
)


def starter_abilities(profile, has_skeleton):
    """Return conditional starter mappings, never a universal engine requirement."""
    if profile == 'STATIC':
        return ()
    if profile == 'BUILDING':
        return ('Idle',) if has_skeleton else ()
    if profile == 'ANIMATED_OBJECT':
        return ('Idle',)
    if profile == 'UNIT':
        return ('Idle', 'Walk', 'Run', 'Spawn', 'Die')
    raise ValueError('Unknown animation profile: ' + profile)
