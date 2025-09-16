from typing import Dict, Any

# This dictionary contains abilities that are fundamental for almost any unit
# to function correctly in the game engine.
must_have_abilities: Dict[str, Dict[str, Any]] = {
    "Idle": {
        "description": "The default, non-active state of the unit.",
        "components": [{"role": "Idle", "vis_job_id": 0}],
    },
    "Walk": {
        "description": "Standard slow movement animation.",
        "components": [{"role": "Walk", "vis_job_id": 1}],
    },
    "Run": {
        "description": "Standard fast movement animation.",
        "components": [{"role": "Run", "vis_job_id": 2}],
    },
    "Spawn": {
        "description": "Animation played when the unit is first created or summoned.",
        "components": [
            {
                "role": "Spawn",
                "vis_job_id": 3,
                "requires_marker": True,
                "marker_defaults": {"is_spawn_animation": True},
            }
        ],
        "timings": [  # Variants
            {
                "animation_type": "Spawn",
                "tag_id": 0,
                "is_enter_mode": 0,
                "description": "Timing for the spawn effect, derived from the marker.",
                "links_to_roles": ["Spawn"],  # Timings
            }
        ],
    },
    "HitFromBack": {
        "description": "Reaction animation for taking damage from the rear.",
        "components": [{"role": "HitFromBack", "vis_job_id": 4}],
    },
    "Cheer / Emote": {
        "description": "A victory pose or other non-combat emote.",
        "components": [{"role": "Cheer", "vis_job_id": 5}],
    },
    "HitFromFront": {
        "description": "Reaction animation for taking damage from the front.",
        "components": [{"role": "HitFromFront", "vis_job_id": 11}],
    },
    "Die": {
        "description": "The unit's death animation.",
        "components": [{"role": "Die", "vis_job_id": 12}],
    },
    "HitFromLeft": {
        "description": "Reaction animation for taking damage from the left.",
        "components": [{"role": "HitFromLeft", "vis_job_id": 14}],
    },
    "HitFromRight": {
        "description": "Reaction animation for taking damage from the right.",
        "components": [{"role": "HitFromRight", "vis_job_id": 23}],
    },
    "PushBackStandUp": {
        "description": "A three-part animation for being knocked down and getting back up.",
        "components": [
            {"role": "PushBackStandUpStart", "vis_job_id": 29},
            {"role": "PushBackStandUpLoop", "vis_job_id": 30},
            {"role": "PushBackStandUpEnd", "vis_job_id": 31},
        ],
    },
}

# This dictionary is for abilities that are common but not universal.
# For example, a building might not have an attack, but most units will.
situational_abilities: Dict[str, Dict[str, Any]] = {
    "Attack": {
        "description": "A standard melee or ranged attack.",
        "components": [
            {
                "role": "MeleeAttack",
                "vis_job_id": 8,
                "requires_marker": True,
                "marker_defaults": {},
            }
        ],
        "timings": [
            {
                "animation_type": "Melee",
                "tag_id": 0,
                "is_enter_mode": 0,
                "links_to_roles": ["MeleeAttack"],
            }
        ],
    },
    "Cast (Ground Only)": {
        "description": "A standard two-part spellcasting animation for ground units.",
        "components": [
            {"role": "CastGround", "vis_job_id": 18},
            {"role": "CastResolve", "vis_job_id": 19},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 0,
                "is_enter_mode": 0,
                "links_to_roles": ["CastGround"],
            }
        ],
    },
    "Cast (Ground & Air)": {
        "description": "A spellcast with animations for both ground and air. The timings NEED to be identical!",
        "components": [
            {"role": "CastGround", "vis_job_id": 18},
            {"role": "CastResolve", "vis_job_id": 19},
            {"role": "CastAir", "vis_job_id": 22},
            {"role": "CastResolveAir", "vis_job_id": 21},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 0,
                "is_enter_mode": 0,
                "links_to_roles": ["CastGround"],
            },
        ],
    },
    "WormMovement": {
        "description": "Three-part animation for burrowing movement (Start, Loop, End).",
        "components": [
            {"role": "Start", "vis_job_id": 10},
            {"role": "Loop", "vis_job_id": 17},
            {"role": "End", "vis_job_id": 28},
        ],
        "timings": [
            {
                "animation_type": "WormMovement",
                "tag_id": 0,
                "is_enter_mode": 0,
                "links_to_roles": ["Start", "Loop"],  # Shared markerID
            }
        ],
    },
    "ModeSwitch (Not yet Supported)": {
        "description": "Animation for units that can switch between two forms or modes.",
        "components": [
            {"role": "SwitchToSpecial", "vis_job_id": 7},
            {"role": "SwitchToNormal", "vis_job_id": 7},
        ],
        "timings": [
            {
                "animation_type": "ModeSwitch",
                "tag_id": 0,
                "is_enter_mode": 0,
                "links_to_roles": ["SwitchToNormal"],
            },
            {
                "animation_type": "ModeSwitch",
                "tag_id": 0,
                "is_enter_mode": 1,
                "links_to_roles": ["SwitchToSpecial"],
            },
        ],
    },
    "Trapped (Flying Units Only)": {
        "description": "Animation for aerial units being trapped or grounded.",
        "components": [
            {
                "role": "Trapped",
                "vis_job_id": 35,
                "marker_defaults": {},
            }
        ],
    },
    "Intro (No Effect)": {
        "description": "A non-interactive intro animation, often used in cinematics.",
        "components": [
            {
                "role": "Intro",
                "vis_job_id": 99,
            }
        ],
    },
}

# This dictionary is for special, unit-specific abilities.
additional_abilities: Dict[str, Dict[str, Any]] = {
    "Charge Run": {
        "description": "A fast, aggressive charge movement without hit interaction.",
        "components": [{"role": "ChargeRun", "vis_job_id": 9}],
    },
    "Special Melee Attack Ground": {
        "description": "A powerful melee attack animation against ground units.",
        "components": [
            {
                "role": "SpecialMeleeAttack",
                "vis_job_id": 15,
                "requires_marker": True,
                "marker_defaults": {},
            }
        ],
        "timings": [
            {
                "animation_type": "Melee",
                "tag_id": 114,
                "is_enter_mode": 0,
                "links_to_roles": ["SpecialMeleeAttack"],
            }
        ],
    },
    "Special Melee Attack Air": {
        "description": "A powerful melee attack animation against aerial units.",
        "components": [
            {
                "role": "SpecialMeleeAttackAir",
                "vis_job_id": 16,
                "requires_marker": True,
                "marker_defaults": {},
            }
        ],
        "timings": [
            {
                "animation_type": "Melee",
                "tag_id": 115,
                "is_enter_mode": 0,
                "links_to_roles": ["SpecialMeleeAttackAir"],
            }
        ],
    },
    "Impactful Movement / Trample": {
        "description": "A movement animation that causes damage to small units in the path.",
        "components": [{"role": "Trample", "vis_job_id": 27}],
    },
    "Stampede": {
        "description": "A high-speed charge that knocks down enemies in its path.",
        "components": [
            {"role": "StampedeStart", "vis_job_id": 128},
            {"role": "StampedeLoop", "vis_job_id": 129},
            {"role": "StampedeEnd", "vis_job_id": 130},
        ],
    },
    "EraseOverTime": {
        "description": "An animation that gradually fades out the unit over time.",
        "components": [
            {"role": "EraseOverTimeStart", "vis_job_id": 131},
            {"role": "EraseOverTimeLoop", "vis_job_id": 132},
            {"role": "EraseOverTimeEnd", "vis_job_id": 133},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 124,
                "is_enter_mode": 0,
                "links_to_roles": ["EraseOverTimeStart", "EraseOverTimeLoop"],
            }
        ],
    },
    "GroundPounder (Tremor)": {
        "description": "A powerful ground attack used by Tremor.",
        "components": [
            {"role": "GroundPounderCast", "vis_job_id": 134},
            {"role": "GroundPounderResolve", "vis_job_id": 135},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 18,
                "is_enter_mode": 0,
                "links_to_roles": ["GroundPounderCast"],
            }
        ],
    },
    "Firelance (Emberstrike)": {
        "description": "A fiery lance attack used by Emberstrike.",
        "components": [
            {"role": "FirelanceCast", "vis_job_id": 136},
            {"role": "FirelanceResolve", "vis_job_id": 137},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 9,
                "is_enter_mode": 0,
                "links_to_roles": ["FirelanceCast"],
            }
        ],
    },
    "Paralyze": {
        "description": "An animation for units paralysing their targets.",
        "components": [
            {"role": "ParalyzeCast", "vis_job_id": 138},
            {"role": "ParalyzeResolve", "vis_job_id": 139},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 11,
                "is_enter_mode": 0,
                "links_to_roles": ["ParalyzeCast"],
            }
        ],
    },
    "ThrowFlames": {
        "description": "An animation for units that throw flames.",
        "components": [
            {"role": "ThrowFlamesStart", "vis_job_id": 140},
            {"role": "ThrowFlamesLoop", "vis_job_id": 141},
            {"role": "ThrowFlamesEnd", "vis_job_id": 142},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 12,
                "is_enter_mode": 0,
                "links_to_roles": ["ThrowFlamesStart", "ThrowFlamesLoop"],
            }
        ],
    },
    "ThrowShadowFlames": {
        "description": "An animation for units that throw shadow flames.",
        "components": [
            {"role": "ThrowShadowFlamesStart", "vis_job_id": 143},
            {"role": "ThrowShadowFlamesLoop", "vis_job_id": 144},
            {"role": "ThrowShadowFlamesEnd", "vis_job_id": 145},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 13,
                "is_enter_mode": 0,
                "links_to_roles": ["ThrowShadowFlamesStart", "ThrowShadowFlamesLoop"],
            }
        ],
    },
    "Conflagration": {
        "description": "An animation for units that create a conflagration.",
        "components": [
            {"role": "ConflagrationStart", "vis_job_id": 146},
            {"role": "ConflagrationLoop", "vis_job_id": 147},
            {"role": "ConflagrationEnd", "vis_job_id": 148},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 14,
                "is_enter_mode": 0,
                "links_to_roles": ["ConflagrationStart", "ConflagrationLoop"],
            }
        ],
    },
    "Exhaust": {
        "description": "An animation for units that exhaust their targets.",
        "components": [
            {"role": "ExhaustCast", "vis_job_id": 149},
            {"role": "ExhaustResolve", "vis_job_id": 150},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 15,
                "is_enter_mode": 0,
                "links_to_roles": ["ExhaustCast"],
            }
        ],
    },
    "UnholyArmor": {
        "description": "An animation for units that cast unholy armor.",
        "components": [
            {"role": "UnholyArmorCast", "vis_job_id": 151},
            {"role": "UnholyArmorResolve", "vis_job_id": 152},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 16,
                "is_enter_mode": 0,
                "links_to_roles": ["UnholyArmorCast"],
            }
        ],
    },
    "Frenzy": {
        "description": "An animation for units that enter a frenzy state.",
        "components": [
            {"role": "FrenzyCast", "vis_job_id": 153},
            {"role": "FrenzyResolve", "vis_job_id": 154},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 19,
                "is_enter_mode": 0,
                "links_to_roles": ["FrenzyCast"],
            }
        ],
    },
    "SummonSkeletons": {
        "description": "An animation for units that summon skeletons.",
        "components": [
            {"role": "SummonSkeletonsCast", "vis_job_id": 155},
            {"role": "SummonSkeletonsResolve", "vis_job_id": 156},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 23,
                "is_enter_mode": 0,
                "links_to_roles": ["SummonSkeletonsCast"],
            }
        ],
    },
    "Deathwish": {
        "description": "An animation for units that activate deathwish.",
        "components": [
            {"role": "DeathwishCast", "vis_job_id": 157},
            {"role": "DeathwishResolve", "vis_job_id": 158},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 25,
                "is_enter_mode": 0,
                "links_to_roles": ["DeathwishCast"],
            }
        ],
    },
    "SacrificeSquad": {
        "description": "An animation for units that sacrifice their squad.",
        "components": [
            {"role": "SacrificeSquadCast", "vis_job_id": 159},
            {"role": "SacrificeSquadResolve", "vis_job_id": 160},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 26,
                "is_enter_mode": 0,
                "links_to_roles": ["SacrificeSquadCast"],
            }
        ],
    },
    "SuicidalBomb": {
        "description": "An animation for units that perform a suicidal bomb attack.",
        "components": [
            {"role": "SuicidalBombCast", "vis_job_id": 161},
            {"role": "SuicidalBombResolve", "vis_job_id": 162},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 27,
                "is_enter_mode": 0,
                "links_to_roles": ["SuicidalBombCast"],
            }
        ],
    },
    "CrushWalls": {
        "description": "An animation for units that crush walls.",
        "components": [
            {"role": "CrushWallsCast", "vis_job_id": 163},
            {"role": "CrushWallsResolve", "vis_job_id": 164},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 28,
                "is_enter_mode": 0,
                "links_to_roles": ["CrushWallsCast"],
            }
        ],
    },
    "Rage": {
        "description": "An animation for units that enter a rage state.",
        "components": [
            {"role": "RageLow", "vis_job_id": 165, "requires_marker": True},
            {"role": "RageHigh", "vis_job_id": 166, "requires_marker": True},
        ],
        "timings": [
            {
                "animation_type": "Melee",
                "tag_id": 31,
                "is_enter_mode": 0,
                "links_to_roles": ["RageLow"],
            },
            {
                "animation_type": "Melee",
                "tag_id": 32,
                "is_enter_mode": 0,
                "links_to_roles": ["RageHigh"],
            },
        ],
    },
    "DisableTower (NOT IMPLEMENTED)": {
        # "description": "An animation for units that disable towers.",
        # "components": [
        #     {"role": "DisableTowerCast", "vis_job_id": 167},
        #     {"role": "DisableTowerResolve", "vis_job_id": 168},
        #     {"role": "DisableTowerCastAir", "vis_job_id": 183},
        #     {"role": "DisableTowerResolveAir", "vis_job_id": 184},
        # ],
        # "timings": [
        #     {
        #         "animation_type": "CastResolve",
        #         "tag_id": 33,
        #         "is_enter_mode": 0,
        #         "links_to_roles": ["DisableTowerCast"],
        #     }
        # ],
    },
    "PowerSteal": {
        "description": "An animation for units that steal power.",
        "components": [
            {"role": "PowerStealCast", "vis_job_id": 169},
            {"role": "PowerStealResolve", "vis_job_id": 170},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 34,
                "is_enter_mode": 0,
                "links_to_roles": ["PowerStealCast"],
            }
        ],
    },
    "Heal": {
        "description": "An animation for units that heal themselves or allies.",
        "components": [
            {"role": "HealCast", "vis_job_id": 173},
            {"role": "HealResolve", "vis_job_id": 174},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 39,
                "is_enter_mode": 0,
                "links_to_roles": ["HealCast"],
            }
        ],
    },
    "ThunderousRoar": {
        "description": "An animation for units that unleash a thunderous roar.",
        "components": [
            {"role": "ThunderousRoarCast", "vis_job_id": 175},
            {"role": "ThunderousRoarResolve", "vis_job_id": 176},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 47,
                "is_enter_mode": 0,
                "links_to_roles": ["ThunderousRoarCast"],
            }
        ],
    },
    "Heal Channel": {
        "description": "A channeling heal animation for units that heal over time.",
        "components": [
            {"role": "HealChannelStart", "vis_job_id": 177},
            {"role": "HealChannelLoop", "vis_job_id": 178},
            {"role": "HealChannelEnd", "vis_job_id": 179},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 48,
                "is_enter_mode": 0,
                "links_to_roles": ["HealChannelStart", "HealChannelLoop"],
            }
        ],
    },
    "Paralyze Channel": {
        "description": "A channeling paralyze animation for units that paralyze over time.",
        "components": [
            {"role": "ParalyzeChannelStart", "vis_job_id": 180},
            {"role": "ParalyzeChannelLoop", "vis_job_id": 181},
            {"role": "ParalyzeChannelEnd", "vis_job_id": 182},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 49,
                "is_enter_mode": 0,
                "links_to_roles": ["ParalyzeChannelStart", "ParalyzeChannelLoop"],
            }
        ],
    },
    "PreparedSalvo": {
        "description": "An animation for units that prepare and fire a salvo of attacks.",
        "components": [
            {"role": "PreparedSalvoCast", "vis_job_id": 185},
            {"role": "PreparedSalvoResolve", "vis_job_id": 186},
            {"role": "PreparedSalvoCastAir", "vis_job_id": 187},
            {"role": "PreparedSalvoResolveAir", "vis_job_id": 188},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 54,
                "is_enter_mode": 0,
                "links_to_roles": ["PreparedSalvoCast"],
            }
        ],
    },
    "Special Burrow": {
        "description": "A special burrowing animation for units that can burrow underground.",
        "components": [
            {"role": "SpecialBurrowCast", "vis_job_id": 189},
            {"role": "SpecialBurrowResolve", "vis_job_id": 190},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 63,
                "is_enter_mode": 0,
                "links_to_roles": ["SpecialBurrowCast"],
            }
        ],
    },
    "Turret Fire To Front": {
        "description": "An animation for turret units that fire towards the front.",
        "components": [
            {"role": "TurretFireToFrontCast", "vis_job_id": 191},
            {"role": "TurretFireToFrontResolve", "vis_job_id": 192},
        ],
    },
    "Turret Fire To Left": {
        "description": "An animation for turret units that fire towards the left.",
        "components": [
            {"role": "TurretFireToLeftCast", "vis_job_id": 193},
            {"role": "TurretFireToLeftResolve", "vis_job_id": 194},
        ],
    },
    "Turret Fire To Back": {
        "description": "An animation for turret units that fire towards the back.",
        "components": [
            {"role": "TurretFireToBackCast", "vis_job_id": 195},
            {"role": "TurretFireToBackResolve", "vis_job_id": 196},
        ],
    },
    "Turret Fire To Right": {
        "description": "An animation for turret units that fire towards the right.",
        "components": [
            {"role": "TurretFireToRightCast", "vis_job_id": 197},
            {"role": "TurretFireToRightResolve", "vis_job_id": 198},
        ],
    },
    "Charge Attack": {
        "description": "Single or follow-up Animation of Charge Attack Run.",
        "components": [
            {"role": "ChargeAttack", "vis_job_id": 199, "requires_marker": True}
        ],
        "timings": [
            {
                "animation_type": "Melee",
                "tag_id": 65,
                "is_enter_mode": 0,
                "links_to_roles": ["ChargeAttack"],
            }
        ],
    },
    "SummonDemon": {
        "description": "An animation for units that summon demons.",
        "components": [
            {"role": "SummonDemonCast", "vis_job_id": 200},
            {"role": "SummonDemonResolve", "vis_job_id": 201},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 78,
                "is_enter_mode": 0,
                "links_to_roles": ["SummonDemonCast"],
            }
        ],
    },
    "AreaFreeze": {
        "description": "An animation for units that freeze an area.",
        "components": [
            {"role": "AreaFreezeCast", "vis_job_id": 202},
            {"role": "AreaFreezeResolve", "vis_job_id": 203},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 79,
                "is_enter_mode": 0,
                "links_to_roles": ["AreaFreezeCast"],
            }
        ],
    },
    "HealingRay": {
        "description": "An animation for units that cast a healing ray.",
        "components": [
            {"role": "HealingRayCast", "vis_job_id": 204},
            {"role": "HealingRayResolve", "vis_job_id": 205},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 80,
                "is_enter_mode": 0,
                "links_to_roles": ["HealingRayCast"],
            }
        ],
    },
    "IceShield Channel (Previously Winter Witch aura)": {
        "description": "A channeling shield animation.",
        "components": [
            {"role": "IceShieldStart", "vis_job_id": 206},
            {"role": "IceShieldLoop", "vis_job_id": 207},
            {"role": "IceShieldEnd", "vis_job_id": 208},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 91,
                "is_enter_mode": 0,
                "links_to_roles": ["IceShieldStart", "IceShieldLoop"],
            }
        ],
    },
    "FrostBeam": {
        "description": "A channeling frosty beam animation.",
        "components": [
            {"role": "FrostBeamStart", "vis_job_id": 209},
            {"role": "FrostBeamLoop", "vis_job_id": 210},
            {"role": "FrostBeamEnd", "vis_job_id": 211},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 94,
                "is_enter_mode": 0,
                "links_to_roles": ["FrostBeamStart", "FrostBeamLoop"],
            }
        ],
    },
    "AntimagicField": {
        "description": "A channeling anti-magic field or aura cast.",
        "components": [
            {"role": "AntimagicFieldStart", "vis_job_id": 212},
            {"role": "AntimagicFieldLoop", "vis_job_id": 213},
            {"role": "AntimagicFieldEnd", "vis_job_id": 214},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 97,
                "is_enter_mode": 0,
                "links_to_roles": ["AntimagicFieldStart", "AntimagicFieldLoop"],
            }
        ],
    },
    "FireStream": {
        "description": "A channeling firestream animation.",
        "components": [
            {"role": "FireStreamStart", "vis_job_id": 215},
            {"role": "FireStreamLoop", "vis_job_id": 216},
            {"role": "FireStreamEnd", "vis_job_id": 217},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 98,
                "is_enter_mode": 0,
                "links_to_roles": ["FireStreamStart", "FireStreamLoop"],
            }
        ],
    },
    "StasisField": {
        "description": "An animation for units that cast a stasis field.",
        "components": [
            {"role": "StasisFieldCast", "vis_job_id": 218},
            {"role": "StasisFieldResolve", "vis_job_id": 219},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 99,
                "is_enter_mode": 0,
                "links_to_roles": ["StasisFieldCast"],
            }
        ],
    },
    "BurningLiquid": {
        "description": "An animation for units that release a burning liquid around them.",
        "components": [
            {"role": "BurningLiquidCast", "vis_job_id": 220},
            {"role": "BurningLiquidResolve", "vis_job_id": 221},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 100,
                "is_enter_mode": 0,
                "links_to_roles": ["BurningLiquidCast"],
            }
        ],
    },
    "MindControl": {
        "description": "An animation for units that can take over control of other units.",
        "components": [
            {"role": "MindControlCast", "vis_job_id": 222},
            {"role": "MindControlResolve", "vis_job_id": 223},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 101,
                "is_enter_mode": 0,
                "links_to_roles": ["MindControlCast"],
            }
        ],
    },
    "IceShield Target": {
        "description": "An animation for units that can cast an iceshield on other units.",
        "components": [
            {"role": "IceShieldTargetCast", "vis_job_id": 224},
            {"role": "IceShieldTargetResolve", "vis_job_id": 225},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 102,
                "is_enter_mode": 0,
                "links_to_roles": ["IceShieldTargetCast"],
            }
        ],
    },
    "SonicScream": {
        "description": "An animation for units that cast a sonic scream.",
        "components": [
            {"role": "SonicScreamCast", "vis_job_id": 226},
            {"role": "SonicScreamResolve", "vis_job_id": 227},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 103,
                "is_enter_mode": 0,
                "links_to_roles": ["SonicScreamCast"],
            }
        ],
    },
    "TeleportSelf": {
        "description": "An animation for units that can teleport themselves.",
        "components": [
            {"role": "TeleportSelfCast", "vis_job_id": 228},
            {"role": "TeleportSelfResolve", "vis_job_id": 229},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 104,
                "is_enter_mode": 0,
                "links_to_roles": ["TeleportSelfCast"],
            }
        ],
    },
    "RepairCast with Channel": {
        "description": "A repair cast ability with a channeling component.",
        "components": [
            {"role": "RepairModeChannelStart", "vis_job_id": 230},
            {"role": "RepairModeChannelLoop", "vis_job_id": 231},
            {"role": "RepairModeChannelEnd", "vis_job_id": 232},
            {"role": "RepairCast", "vis_job_id": 283},
            {"role": "RepairResolve", "vis_job_id": 284},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 136,
                "is_enter_mode": 0,
                "links_to_roles": ["RepairCast"],
            },
            {
                "animation_type": "Channel",
                "tag_id": 110,
                "is_enter_mode": 0,
                "links_to_roles": ["RepairModeChannelStart", "RepairModeChannelLoop"],
            },
        ],
    },
    "Strike": {
        "description": "An animation for units that cast a projectile in a direction.",
        "components": [
            {"role": "StrikeCast", "vis_job_id": 233},
            {"role": "StrikeResolve", "vis_job_id": 234},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 111,
                "is_enter_mode": 0,
                "links_to_roles": ["StrikeCast"],
            }
        ],
    },
    "CriticalMass": {
        "description": "An animation for units that cast a projectile in a direction.",
        "components": [
            {"role": "CriticalMassCast", "vis_job_id": 235},
            {"role": "CriticalMassResolve", "vis_job_id": 236},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 112,
                "is_enter_mode": 0,
                "links_to_roles": ["CriticalMassCast"],
            }
        ],
    },
    "SiegeTrumpet": {
        "description": "An animation for units that sound a siege trumpet.",
        "components": [
            {"role": "SiegeTrumpetCast", "vis_job_id": 237},
            {"role": "SiegeTrumpetResolve", "vis_job_id": 238},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 113,
                "is_enter_mode": 0,
                "links_to_roles": ["SiegeTrumpetCast"],
            }
        ],
    },
    "Bracing Zone": {
        "description": "An animation for units that create a bracing zone.",
        "components": [
            {"role": "BracingZoneCast", "vis_job_id": 239},
            {"role": "BracingZoneResolve", "vis_job_id": 240},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 116,
                "is_enter_mode": 0,
                "links_to_roles": ["BracingZoneCast"],
            }
        ],
    },
    "Fireball": {
        "description": "An animation for units that cast a fireball.",
        "components": [
            {"role": "FireballCast", "vis_job_id": 241},
            {"role": "FireballResolve", "vis_job_id": 242},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 117,
                "is_enter_mode": 0,
                "links_to_roles": ["FireballCast"],
            }
        ],
    },
    "MassSleep": {
        "description": "An animation for units that cast a mass sleep spell.",
        "components": [
            {"role": "MassSleepCast", "vis_job_id": 243},
            {"role": "MassSleepResolve", "vis_job_id": 244},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 119,
                "is_enter_mode": 0,
                "links_to_roles": ["MassSleepCast"],
            }
        ],
    },
    "Repair Channel": {
        "description": "A channeling repair animation for units that repair over time.",
        "components": [
            {"role": "RepairChannelStart", "vis_job_id": 247},
            {"role": "RepairChannelLoop", "vis_job_id": 248},
            {"role": "RepairChannelEnd", "vis_job_id": 249},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 121,
                "is_enter_mode": 0,
                "links_to_roles": ["RepairChannelStart", "RepairChannelLoop"],
            }
        ],
    },
    "BombRaid": {
        "description": "An animation for units that perform a bombing raid.",
        "components": [
            {"role": "BombRaidCast", "vis_job_id": 250},
            {"role": "BombRaidResolve", "vis_job_id": 251},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 122,
                "is_enter_mode": 0,
                "links_to_roles": ["BombRaidCast"],
            }
        ],
    },
    "PVEAttack1": {
        "description": "A powerful hammer attack used by Units in PVE Scenarios.",
        "components": [
            {"role": "PVEAttack1Cast", "vis_job_id": 257},
            {"role": "PVEAttack1Resolve", "vis_job_id": 258},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 126,
                "is_enter_mode": 0,
                "links_to_roles": ["PVEAttack1Cast"],
            }
        ],
    },
    "IceBombardment": {
        "description": "An animation for units that cast a ice bombardment.",
        "components": [
            {"role": "IceBombardmentNearStart", "vis_job_id": 259},
            {"role": "IceBombardmentNearLoop", "vis_job_id": 260},
            {"role": "IceBombardmentNearEnd", "vis_job_id": 261},
            {"role": "IceBombardmentFarStart", "vis_job_id": 262},
            {"role": "IceBombardmentFarLoop", "vis_job_id": 263},
            {"role": "IceBombardmentFarEnd", "vis_job_id": 264},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 127,
                "is_enter_mode": 0,
                "links_to_roles": ["IceBombardmentNearStart", "IceBombardmentNearLoop"],
            }
        ],
    },
    "ParalyzingRoar": {
        "description": "An animation for units that cast a paralyzing roar.",
        "components": [
            {"role": "ParalyzingRoarCast", "vis_job_id": 265},
            {"role": "ParalyzingRoarResolve", "vis_job_id": 266},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 128,
                "is_enter_mode": 0,
                "links_to_roles": ["ParalyzingRoarCast"],
            }
        ],
    },
    "SacrificeKill": {
        "description": "An animation for units that perform a sacrifice kill.",
        "components": [
            {"role": "SacrificeKillCast", "vis_job_id": 267},
            {"role": "SacrificeKillResolve", "vis_job_id": 268},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 129,
                "is_enter_mode": 0,
                "links_to_roles": ["SacrificeKillCast"],
            }
        ],
    },
    "LifeTransfer": {
        "description": "An animation for units that transfer life.",
        "components": [
            {"role": "LifeTransferCast", "vis_job_id": 269},
            {"role": "LifeTransferResolve", "vis_job_id": 270},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 130,
                "is_enter_mode": 0,
                "links_to_roles": ["LifeTransferCast"],
            }
        ],
    },
    "Earthquake": {
        "description": "An animation for units that cast an earthquake.",
        "components": [
            {"role": "EarthquakeStart", "vis_job_id": 271},
            {"role": "EarthquakeLoop", "vis_job_id": 272},
            {"role": "EarthquakeEnd", "vis_job_id": 273},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 131,
                "is_enter_mode": 0,
                "links_to_roles": ["EarthquakeStart", "EarthquakeLoop"],
            }
        ],
    },
    "PVEChannel": {
        "description": "A channeling animation used in PVE scenarios.",
        "components": [
            {"role": "PVEChannelStart", "vis_job_id": 274},
            {"role": "PVEChannelLoop", "vis_job_id": 275},
            {"role": "PVEChannelEnd", "vis_job_id": 276},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 132,
                "is_enter_mode": 0,
                "links_to_roles": ["PVEChannelStart", "PVEChannelLoop"],
            }
        ],
    },
    "PVECast": {
        "description": "A casting animation used in PVE scenarios.",
        "components": [
            {"role": "PVECast", "vis_job_id": 277},
            {"role": "PVEResolve", "vis_job_id": 278},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 133,
                "is_enter_mode": 0,
                "links_to_roles": ["PVECast"],
            }
        ],
    },
    "AttachToBuilding": {
        "description": "An animation for units that attach to buildings.",
        "components": [
            {"role": "AttachToBuildingStart", "vis_job_id": 280},
            {"role": "AttachToBuildingLoop", "vis_job_id": 281},
            {"role": "AttachToBuildingEnd", "vis_job_id": 282},
        ],
        "timings": [
            {
                "animation_type": "Channel",
                "tag_id": 135,
                "is_enter_mode": 0,
                "links_to_roles": ["AttachToBuildingStart", "AttachToBuildingLoop"],
            }
        ],
    },
    "RageCastStage1": {
        "description": "An animation for units that enter rage stage 1.",
        "components": [
            {"role": "RageCastStage1Cast", "vis_job_id": 285},
            {"role": "RageCastStage1Resolve", "vis_job_id": 286},
            {"role": "RageCastStage1CastAir", "vis_job_id": 287},
            {"role": "RageCastStage1ResolveAir", "vis_job_id": 288},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 31,
                "is_enter_mode": 0,
                "links_to_roles": ["RageCastStage1Cast"],
            }
        ],
    },
    "RageCastStage2": {
        "description": "An animation for units that enter rage stage 2.",
        "components": [
            {"role": "RageCastStage2Cast", "vis_job_id": 289},
            {"role": "RageCastStage2Resolve", "vis_job_id": 290},
            {"role": "RageCastStage2CastAir", "vis_job_id": 291},
            {"role": "RageCastStage2ResolveAir", "vis_job_id": 292},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 32,
                "is_enter_mode": 0,
                "links_to_roles": ["RageCastStage2Cast"],
            }
        ],
    },
    "SuicideAttack": {
        "description": "An animation for units that perform a suicide attack.",
        "components": [
            {"role": "SuicideAttackCast", "vis_job_id": 293},
            {"role": "SuicideAttackResolve", "vis_job_id": 294},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 118,
                "is_enter_mode": 0,
                "links_to_roles": ["SuicideAttackCast"],
            }
        ],
    },
    "RelocateBuilding": {
        "description": "An animation for units that relocate a building.",
        "components": [
            {"role": "RelocateBuildingCast", "vis_job_id": 295},
            {"role": "RelocateBuildingResolve", "vis_job_id": 296},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 137,
                "is_enter_mode": 0,
                "links_to_roles": ["RelocateBuildingCast"],
            }
        ],
    },
    "PVEAttack2": {
        "description": "A different animation for units that attack in PVE with a two-handed weapon.",
        "components": [
            {"role": "PVEAttack2Cast", "vis_job_id": 304},
            {"role": "PVEAttack2Resolve", "vis_job_id": 305},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 142,
                "is_enter_mode": 0,
                "links_to_roles": ["PVEAttack2Cast"],
            }
        ],
    },
    "Taunt": {
        "description": "An animation for units that taunt enemies.",
        "components": [
            {"role": "TauntCast", "vis_job_id": 306},
            {"role": "TauntResolve", "vis_job_id": 307},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 143,
                "is_enter_mode": 0,
                "links_to_roles": ["TauntCast"],
            }
        ],
    },
    "Swap": {
        "description": "An animation for units that swap with another unit.",
        "components": [
            {"role": "SwapCast", "vis_job_id": 308},
            {"role": "SwapResolve", "vis_job_id": 309},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 144,
                "is_enter_mode": 0,
                "links_to_roles": ["SwapCast"],
            }
        ],
    },
    "Disenchant": {
        "description": "An animation for units that disenchant magical effects.",
        "components": [
            {"role": "DisenchantCast", "vis_job_id": 310},
            {"role": "DisenchantResolve", "vis_job_id": 311},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 145,
                "is_enter_mode": 0,
                "links_to_roles": ["DisenchantCast"],
            }
        ],
    },
    "GravitySurge": {
        "description": "An animation for units that pull down flying units.",
        "components": [
            {"role": "GravitySurgeCast", "vis_job_id": 312},
            {"role": "GravitySurgeResolve", "vis_job_id": 313},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 146,
                "is_enter_mode": 0,
                "links_to_roles": ["GravitySurgeCast"],
            }
        ],
    },
    "Enrage": {
        "description": "An animation for units that become enraged.",
        "components": [
            {"role": "EnrageCast", "vis_job_id": 314},
            {"role": "EnrageResolve", "vis_job_id": 315},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 147,
                "is_enter_mode": 0,
                "links_to_roles": ["EnrageCast"],
            }
        ],
    },
    "SpecialRangedAir": {
        "description": "A powerful ranged attack animation against aerial units.",
        "components": [
            {"role": "SpecialRangedAirCast", "vis_job_id": 316},
            {"role": "SpecialRangedAirResolve", "vis_job_id": 317},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 148,
                "is_enter_mode": 0,
                "links_to_roles": ["SpecialRangedAirCast"],
            }
        ],
    },
    "Harpoon": {
        "description": "An animation for units that throw a harpoon.",
        "components": [
            {"role": "HarpoonCast", "vis_job_id": 321},
            {"role": "HarpoonResolve", "vis_job_id": 322},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 150,
                "is_enter_mode": 0,
                "links_to_roles": ["HarpoonCast"],
            }
        ],
    },
    "Reassemble the Ravens": {
        "description": "An animation for units that spawn additional units.",
        "components": [
            {"role": "ReassembletheRavensCast", "vis_job_id": 323},
            {"role": "ReassembletheRavensResolve", "vis_job_id": 324},
        ],
        "timings": [
            {
                "animation_type": "CastResolve",
                "tag_id": 151,
                "is_enter_mode": 0,
                "links_to_roles": ["ReassembletheRavensCast"],
            }
        ],
    },
}
