
Unit Types:
1. Melee
2. Caster (Ground AND Air)
3. Caster (Ground ONLY)
4. Abilities Only

Units of Type 2 need to use the same animation file and timings values!

What i need to simplify later: 
- Rage Cast and other abilities with more than just Cast and Resolve
- Show only Cast in Blender (as Resolve is simply the remaining animation length)

For Mode Switches
- In AnimationKey set unknown4 to 1 for the 2nd Mode
- ModeSwitches always take the full animation length


"""
Defines a structured dictionary of abilities for units.

This file provides a clear, scalable structure for defining in-game abilities,
their animation components, and their timing requirements.

New Structure Overview:

"AbilityName": {
    "description": "User-friendly description for UI tooltips.",
    "components": [
        {
            "role": "Logical name for this animation (e.g., 'Cast', 'Loop').",
            "vis_job_id": The integer ID for the animation (from VIS_JOB_MAP).,
            "requires_marker": (Optional) True if this component needs an AnimationMarkerSet.,
            "marker_defaults": (Optional) A dict of default values for the marker.
        },
        # ... more components for multi-part animations
    ],
    "timings": [
        {
            "animation_type": "The string name from AnimationType enum (e.g., 'Spawn').",
            "tag_id": The integer AnimTagID for this timing group.,
            "is_enter_mode": Integer flag, typically 0 or 1.,
            "links_to_roles": A list of 'role' strings, explicitly linking this
                              timing entry to one or more components defined above.
                              If the component has a marker, both share the same markerID.
                              If the component does not use a marker, and multiple roles in the list, they share the same unique markerID.
        },
        # ... more timing entries if an ability has multiple timing groups
    ]
}

Additional Hints:
- The resolveMS in the timing should be the total length of the animation,
- The castMS is when the effect should occur within that animation: animation.length * animationKey.end

"""