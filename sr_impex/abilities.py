from typing import Dict, List

must_have_abilities: Dict[str, Dict[str, List[Dict[str, int]]]] = {
    "Idle": {
        "animations": [{"name": "Idle", "id": 0}],
    },
    "Walk": {
        "animations": [{"name": "Walk", "id": 1}],
    },
    "Run": {
        "animations": [{"name": "Run", "id": 2}],
    },
    "Spawn": {"animations": [{"name": "Spawn", "id": 3}], "marker": True},
    "HitFromBack": {
        "animations": [{"name": "HitFromBack", "id": 4}],
    },
    "Cheer / Emote": {
        "animations": [{"name": "Cheer / Emote", "id": 5}],
    },
    "HitFromFront": {
        "animations": [{"name": "HitFromFront", "id": 11}],
    },
    "Die": {
        "animations": [{"name": "Die", "id": 12}],
    },
    "SpellTargetShotSequenceAreaRecoil / HitFromLeft": {
        "animations": [
            {"name": "SpellTargetShotSequenceAreaRecoil / HitFromLeft", "id": 14}
        ],
    },
    "HitFromRight": {
        "animations": [{"name": "HitFromRight", "id": 23}],
    },
    "PushBackStandUp": {
        "animations": [
            {"name": "PushBackStandUp Start", "id": 29},
            {"name": "PushBackStandUp Loop", "id": 30},
            {"name": "PushBackStandUp End", "id": 31},
        ],
    },
}

situational_abilities: Dict[str, Dict[str, List[Dict[str, int]]]] = {
    "Attack": {"animations": [{"name": "Attack", "id": 8}], "marker": True},
    "Cast": {
        "animations": [{"name": "Cast", "id": 18}, {"name": "Cast Resolve", "id": 19}]
    },
    "CastAir": {
        "animations": [
            {"name": "CastAir", "id": 22},
            {"name": "CastAir Resolve", "id": 21},
        ]
    },
    "WormMovement": {
        "animations": [
            {"name": "WormMovement Start", "id": 10},
            {"name": "WormMovement Loop", "id": 17},
            {"name": "WormMovement End", "id": 28},
        ],
        "description": "Needed by Worm Units.",
    },
}

addtional_abilities: Dict[str, Dict[str, List[Dict[str, int]]]] = {
    "Deploy / Charge Attack Run": {
        "animations": [{"name": "Deploy / Charge Attack Run", "id": 9}],
        "description": "Charge Animation without Melee Hit.",
    },
    "Charge Attack": {
        "animations": [
            {"name": "Charge Attack", "id": 199},
        ],
        "description": "Single or follow-up Animation of Charge Attack Run. This Ability hits with a Marker",
        "marker": True,
    },
    "Rage": {
        "animations": [
            {"name": "Rage (Low)", "id": 165},
            {"name": "Rage (High)", "id": 166},
        ],
        "description": "",
        "marker": True,
    },
    "Special Melee Attack Ground (AnimTagID 114)": {
        "animations": [
            {"name": "Special Melee Attack Ground (AnimTagID 114)", "id": 15},
        ],
        "description": "Special melee attack used vs grounded Units.",
        "marker": True,
    },
    "Special Melee Attack Air (AnimTagID 115)": {
        "animations": [
            {"name": "Special Melee Attack Air (AnimTagID 115)", "id": 16},
        ],
        "description": "Special melee attack used vs flying Units.",
        "marker": True,
    },
    "Impactful Movement / Trample": {
        "animations": [
            {"name": "Impactful Movement / Trample", "id": 27},
        ],
        "description": "Used by bigger Units when they move trough smaller ones.",
    },
    "Stampede": {
        "animations": [
            {"name": "StampedeStart", "id": 128},
            {"name": "StampedeRun", "id": 129},
            {"name": "StampedeStop", "id": 130},
        ],
        "description": "",
    },
    "EraseOverTime": {
        "animations": [
            {"name": "EraseOverTimeInit / EraseOverTimeStart", "id": 131},
            {"name": "EraseOverTimeWork / EraseOverTimeLoop", "id": 132},
            {"name": "EraseOverTimeShutDown / EraseOverTimeEnd", "id": 133},
        ],
        "description": "",
    },
    "GroundPounder (Tremor)": {
        "animations": [
            {"name": "GroundPounder (Tremor) Cast", "id": 134},
            {"name": "GroundPounder (Tremor) Resolve", "id": 135},
        ],
        "description": "",
    },
    "Firelance (Emberstrike)": {
        "animations": [
            {"name": "Firelance (Emberstrike) Cast", "id": 136},
            {"name": "Firelance (Emberstrike) Resolve", "id": 137},
        ],
        "description": "",
    },
    "Paralyze": {
        "animations": [
            {"name": "Paralyze Cast", "id": 138},
            {"name": "Paralyze Resolve", "id": 139},
        ],
        "description": "",
    },
    "ThrowFlames": {
        "animations": [
            {"name": "ThrowFlames Init", "id": 140},
            {"name": "ThrowFlames Work", "id": 141},
            {"name": "ThrowFlames ShutDown", "id": 142},
        ],
        "description": "",
    },
    "ThrowShadowFlames": {
        "animations": [
            {"name": "ThrowShadowFlames Init", "id": 143},
            {"name": "ThrowShadowFlames Work", "id": 144},
            {"name": "ThrowShadowFlames ShutDown", "id": 145},
        ],
        "description": "",
    },
    "Conflagration": {
        "animations": [
            {"name": "Conflagration Init", "id": 146},
            {"name": "Conflagration Work", "id": 147},
            {"name": "Conflagration ShutDown", "id": 148},
        ],
        "description": "",
    },
    "Exhaust": {
        "animations": [
            {"name": "Exhaust Cast", "id": 149},
            {"name": "Exhaust Resolve", "id": 150},
        ],
        "description": "",
    },
    "UnholyArmor": {
        "animations": [
            {"name": "UnholyArmor Cast", "id": 151},
            {"name": "UnholyArmor Resolve", "id": 152},
        ],
        "description": "",
    },
    "Frenzy": {
        "animations": [
            {"name": "Frenzy Cast", "id": 153},
            {"name": "Frenzy Resolve", "id": 154},
        ],
        "description": "",
    },
    "SummonSkeletons": {
        "animations": [
            {"name": "SummonSkeletons Cast", "id": 155},
            {"name": "SummonSkeletons Resolve", "id": 156},
        ],
        "description": "",
    },
    "Deathwish": {
        "animations": [
            {"name": "Deathwish Cast", "id": 157},
            {"name": "Deathwish Resolve", "id": 158},
        ],
        "description": "",
    },
    "SacrificeSquad": {
        "animations": [
            {"name": "SacrificeSquad Cast", "id": 159},
            {"name": "SacrificeSquad Resolve", "id": 160},
        ],
        "description": "",
    },
    "SuicidalBomb": {
        "animations": [
            {"name": "SuicidalBomb Cast", "id": 161},
            {"name": "SuicidalBomb Resolve", "id": 162},
        ],
        "description": "",
    },
    "CrushWalls": {
        "animations": [
            {"name": "CrushWalls Cast", "id": 163},
            {"name": "CrushWalls Resolve", "id": 164},
        ],
        "description": "",
    },
    "DisableTower": {
        "animations": [
            {"name": "DisableTower Cast", "id": 167},
            {"name": "DisableTower Resolve", "id": 168},
            {"name": "DisableTower CastAir", "id": 183},
            {"name": "DisableTower ResolveAir", "id": 184},
        ],
        "description": "Disable enemy building's attacks and special abilities for a given time.",
    },
    "PowerSteal": {
        "animations": [
            {"name": "PowerSteal Cast", "id": 169},
            {"name": "PowerSteal Resolve", "id": 170},
        ],
        "description": "",
    },
    "Heal": {
        "animations": [
            {"name": "Heal Cast", "id": 173},
            {"name": "Heal Resolve", "id": 174},
        ],
        "description": "",
    },
    "ThunderousRoar": {
        "animations": [
            {"name": "ThunderousRoar Cast", "id": 175},
            {"name": "ThunderousRoar Resolve", "id": 176},
        ],
        "description": "",
    },
    "Heal Channel": {
        "animations": [
            {"name": "Heal Channel Start", "id": 177},
            {"name": "Heal Channel Loop", "id": 178},
            {"name": "Heal Channel End", "id": 179},
        ],
        "description": "",
    },
    "Paralyze Channel": {
        "animations": [
            {"name": "Paralyze Channel Start", "id": 180},
            {"name": "Paralyze Channel Loop", "id": 181},
            {"name": "Paralyze Channel End", "id": 182},
        ],
        "description": "",
    },
    "PreparedSalvo": {
        "animations": [
            {"name": "PreparedSalvo Cast", "id": 185},
            {"name": "PreparedSalvo Resolve", "id": 186},
            {"name": "PreparedSalvo CastAir", "id": 187},
            {"name": "PreparedSalvo ResolveAir", "id": 188},
        ],
        "description": "",
    },
    "Special Burrow": {
        "animations": [
            {"name": "Special Burrow Cast", "id": 189},
            {"name": "Special Burrow Resolve", "id": 190},
        ],
        "description": "",
    },
    "Turret Fire To Front": {
        "animations": [
            {"name": "Turret Fire To Front Cast", "id": 191},
            {"name": "Turret Fire To Front Resolve", "id": 192},
        ],
        "description": "",
    },
    "Turret Fire To Left": {
        "animations": [
            {"name": "Turret Fire To Left Cast", "id": 193},
            {"name": "Turret Fire To Left Resolve", "id": 194},
        ],
        "description": "",
    },
    "Turret Fire To Back": {
        "animations": [
            {"name": "Turret Fire To Back Cast", "id": 195},
            {"name": "Turret Fire To Back Resolve", "id": 196},
        ],
        "description": "",
    },
    "Turret Fire To Right": {
        "animations": [
            {"name": "Turret Fire To Right Cast", "id": 197},
            {"name": "Turret Fire To Right Resolve", "id": 198},
        ],
        "description": "",
    },
    "SummonDemon": {
        "animations": [
            {"name": "SummonDemon Cast", "id": 200},
            {"name": "SummonDemon Resolve", "id": 201},
        ],
        "description": "",
    },
    "AreaFreeze": {
        "animations": [
            {"name": "AreaFreeze Cast", "id": 202},
            {"name": "AreaFreeze Resolve", "id": 203},
        ],
        "description": "",
    },
    "HealingRay": {
        "animations": [
            {"name": "HealingRay Cast", "id": 204},
            {"name": "HealingRay Resolve", "id": 205},
        ],
        "description": "",
    },
    "IceShield Channel": {
        "animations": [
            {
                "name": "IceShield Channel Start (Previously Winter Witch aura)",
                "id": 206,
            },
            {"name": "IceShield Channel Loop", "id": 207},
            {"name": "IceShield Channel End", "id": 208},
        ],
        "description": "",
    },
    "FrostBeam": {
        "animations": [
            {"name": "FrostBeam Start", "id": 209},
            {"name": "FrostBeam Loop", "id": 210},
            {"name": "FrostBeam End", "id": 211},
        ],
        "description": "",
    },
    "AntimagicField": {
        "animations": [
            {"name": "AntimagicField Start", "id": 212},
            {"name": "AntimagicField Loop", "id": 213},
            {"name": "AntimagicField End", "id": 214},
        ],
        "description": "",
    },
    "FireStream": {
        "animations": [
            {"name": "FireStream Start", "id": 215},
            {"name": "FireStream Loop", "id": 216},
            {"name": "FireStream End", "id": 217},
        ],
        "description": "",
    },
    "StasisField": {
        "animations": [
            {"name": "StasisField Cast", "id": 218},
            {"name": "StasisField Resolve", "id": 219},
        ],
        "description": "",
    },
    "BurningLiquid": {
        "animations": [
            {"name": "BurningLiquid Cast", "id": 220},
            {"name": "BurningLiquid Resolve", "id": 221},
        ],
        "description": "",
    },
    "MindControl": {
        "animations": [
            {"name": "MindControl Cast", "id": 222},
            {"name": "MindControl Resolve", "id": 223},
        ],
        "description": "",
    },
    "IceShield Target": {
        "animations": [
            {"name": "IceShield Target Cast", "id": 224},
            {"name": "IceShield Target Resolve", "id": 225},
        ],
        "description": "",
    },
    "SonicScream": {
        "animations": [
            {"name": "SonicScream Cast", "id": 226},
            {"name": "SonicScream Resolve", "id": 227},
        ],
        "description": "",
    },
    "TeleportSelf": {
        "animations": [
            {"name": "TeleportSelf Cast", "id": 228},
            {"name": "TeleportSelf Resolve", "id": 229},
        ],
        "description": "",
    },
    "Repair Channel": {
        "animations": [
            {"name": "Repair Channel Start (AnimTagID 121)", "id": 247},
            {"name": "Repair Channel Loop (AnimTagID 121)", "id": 248},
            {"name": "Repair Channel End (AnimTagID 121)", "id": 249},
        ],
        "description": "Use this, if the unit cant do anything else but repairing, not even damaging.",
    },
    "Strike": {
        "animations": [
            {"name": "Strike Cast", "id": 233},
            {"name": "Strike Resolve", "id": 234},
        ],
        "description": "",
    },
    "CriticalMass": {
        "animations": [
            {"name": "CriticalMass Cast", "id": 235},
            {"name": "CriticalMass Resolve", "id": 236},
        ],
        "description": "",
    },
    "SiegeTrumpet": {
        "animations": [
            {"name": "SiegeTrumpet Cast", "id": 237},
            {"name": "SiegeTrumpet Resolve", "id": 238},
        ],
        "description": "",
    },
    "Bracing Zone": {
        "animations": [
            {"name": "Bracing Zone Cast", "id": 239},
            {"name": "Bracing Zone Resolve", "id": 240},
        ],
        "description": "",
    },
    "Fireball": {
        "animations": [
            {"name": "Fireball Cast", "id": 241},
            {"name": "Fireball Resolve", "id": 242},
        ],
        "description": "",
    },
    "MassSleep": {
        "animations": [
            {"name": "MassSleep Cast", "id": 243},
            {"name": "MassSleep Resolve", "id": 244},
        ],
        "description": "",
    },
    "ChainInsectRay": {
        "animations": [
            {"name": "ChainInsectRay Cast", "id": 245},
            {"name": "ChainInsectRay Resolve", "id": 246},
        ],
        "description": "",
    },
    "BombRaid": {
        "animations": [
            {"name": "BombRaid Cast", "id": 250},
            {"name": "BombRaid Resolve", "id": 251},
        ],
        "description": "",
    },
    "LifeLink": {
        "animations": [
            {"name": "LifeLink Start", "id": 252},
            {"name": "LifeLink Loop", "id": 253},
            {"name": "LifeLink End", "id": 254},
        ],
        "description": "",
    },
    "WormMovement_Hack": {
        "animations": [
            {"name": "WormMovement_Hack Cast", "id": 255},
            {"name": "WormMovement_Hack Resolve", "id": 256},
        ],
        "description": "",
    },
    "skel_giant_hammer_attack_pve1": {
        "animations": [
            {"name": "skel_giant_hammer_attack_pve1 Cast", "id": 257},
            {"name": "skel_giant_hammer_attack_pve1 Resolve", "id": 258},
        ],
        "description": "",
    },
    "IceBombardment Near": {
        "animations": [
            {"name": "IceBombardment Near Start", "id": 259},
            {"name": "IceBombardment Near Loop", "id": 260},
            {"name": "IceBombardment Near End", "id": 261},
        ],
        "description": "",
    },
    "IceBombardment Far": {
        "animations": [
            {"name": "IceBombardment Far Start", "id": 262},
            {"name": "IceBombardment Far Loop", "id": 263},
            {"name": "IceBombardment Far End", "id": 264},
        ],
        "description": "",
    },
    "ParalyzingRoar": {
        "animations": [
            {"name": "ParalyzingRoar Cast", "id": 265},
            {"name": "ParalyzingRoar Resolve", "id": 266},
        ],
        "description": "",
    },
    "SacrificeKill": {
        "animations": [
            {"name": "SacrificeKill Cast", "id": 267},
            {"name": "SacrificeKill Resolve", "id": 268},
        ],
        "description": "",
    },
    "LifeTransfer": {
        "animations": [
            {"name": "LifeTransfer Cast", "id": 269},
            {"name": "LifeTransfer Resolve", "id": 270},
        ],
        "description": "",
    },
    "Earthquake": {
        "animations": [
            {"name": "Earthquake Start", "id": 271},
            {"name": "Earthquake Loop", "id": 272},
            {"name": "Earthquake End", "id": 273},
        ],
        "description": "",
    },
    "PVEChannel": {
        "animations": [
            {"name": "PVEChannel Start", "id": 274},
            {"name": "PVEChannel Loop", "id": 275},
            {"name": "PVEChannel End", "id": 276},
        ],
        "description": "",
    },
    "PVECast": {
        "animations": [
            {"name": "PVECastResolve Cast", "id": 277},
            {"name": "PVECastResolve Resolve", "id": 278},
        ],
        "description": "",
    },
    "AttachToBuilding": {
        "animations": [
            {"name": "AttachToBuilding Start", "id": 280},
            {"name": "AttachToBuilding Loop", "id": 281},
            {"name": "AttachToBuilding End", "id": 282},
        ],
        "description": "",
    },
    "RepairCastWithChannel": {
        "animations": [
            {"name": "Repair Channel Start (AnimTagID 110)", "id": 230},
            {"name": "Repair Channel Loop (AnimTagID 110)", "id": 231},
            {"name": "Repair Channel End (AnimTagID 110)", "id": 232},
            {"name": "RepairCast Cast", "id": 283},
            {"name": "RepairCast Resolve", "id": 284},
        ],
        "description": "",
    },
    "RageCastStage1": {
        "animations": [
            {"name": "RageCastStage1 Cast", "id": 285},
            {"name": "RageCastStage1 Resolve", "id": 286},
            {"name": "RageCastStage1 CastAir", "id": 287},
            {"name": "RageCastStage1 ResolveAir", "id": 288},
        ],
        "description": "",
    },
    "RageCastStage2": {
        "animations": [
            {"name": "RageCastStage2 Cast", "id": 289},
            {"name": "RageCastStage2 Resolve", "id": 290},
            {"name": "RageCastStage2 CastAir", "id": 291},
            {"name": "RageCastStage2 ResolveAir", "id": 292},
        ],
        "description": "",
    },
    "SuicideAttack": {
        "animations": [
            {"name": "SuicideAttack Cast", "id": 293},
            {"name": "SuicideAttack Resolve", "id": 294},
        ],
        "type": "Damage",
        "description": "Cast a suicide attack.",
    },
    "RelocateBuilding": {
        "animations": [
            {"name": "RelocateBuilding Cast", "id": 295},
            {"name": "RelocateBuilding Resolve", "id": 296},
        ],
        "type": "Buff",
        "description": "Place an object close to the caster, providing a buff.",
    },
    # "DeathCounter": {
    #     "animations": [
    #         {"name": "DeathCounter Cast", "id": 297},
    #         {"name": "DeathCounter Resolve", "id": 298},
    #     ],
    #     "description": "",
    # },
    # "TombOfDeath": {
    #     "animations": [
    #         {"name": "TombOfDeath Start", "id": 299},
    #         {"name": "TombOfDeath Loop", "id": 300},
    #         {"name": "TombOfDeath End", "id": 301},
    #     ],
    #     "description": "",
    # },
    # "VersatileAirSpecial": {
    #     "animations": [
    #         {"name": "VersatileAirSpecial Cast", "id": 302},
    #         {"name": "VersatileAirSpecial Resolve", "id": 303},
    #     ],
    #     "description": "",
    # },
    # "PVECastResolve2": {
    #     "animations": [
    #         {"name": "PVECastResolve2 Cast", "id": 304},
    #         {"name": "PVECastResolve2 Resolve", "id": 305},
    #     ],
    #     "description": "",
    # },
    "Taunt": {
        "animations": [
            {"name": "Taunt Cast", "id": 306},
            {"name": "Taunt Resolve", "id": 307},
        ],
        "type": "Debuff",
        "description": "Taunt a target enemy unit.",
    },
    "Swap": {
        "animations": [
            {"name": "Swap Cast", "id": 308},
            {"name": "Swap Resolve", "id": 309},
        ],
        "type": "Special",
        "description": "Exchange the casting unit with an enemy unit.",
    },
    "Disenchant": {
        "animations": [
            {"name": "Disenchant Cast", "id": 310},
            {"name": "Disenchant Resolve", "id": 311},
        ],
        "type": "Debuff",
        "description": "Remove all buffs from a hostile or all debuffs from a friendly unit.",
    },
    "GravitySurge": {
        "animations": [
            {"name": "GravitySurge Cast", "id": 312},
            {"name": "GravitySurge Resolve", "id": 313},
        ],
        "type": "Debuff",
        "description": "Impale a flying enemy unit and pull it down to the ground.",
    },
    "Enrage": {
        "animations": [
            {"name": "Enrage Cast", "id": 314},
            {"name": "Enrage Resolve", "id": 315},
        ],
        "type": "Buff",
        "description": "Puts the casting unit in a state of rage.",
    },
    "SpecialRangedAir": {
        "animations": [
            {"name": "SpecialRangedAir Cast", "id": 316},
            {"name": "SpecialRangedAir Resolve", "id": 317},
        ],
        "type": "Damage",
        "description": "Shoot a special ranged attack in the air.",
    },
    # "GlobalBuffChannel": {
    #     "animations": [
    #         {"name": "GlobalBuffChannel Start", "id": 318},
    #         {"name": "GlobalBuffChannel Loop", "id": 319},
    #         {"name": "GlobalBuffChannel End", "id": 320},
    #     ],
    #     "description": "Not used?",
    # },
    "Harpoon": {
        "animations": [
            {"name": "Harpoon Cast", "id": 321},
            {"name": "Harpoon Resolve", "id": 322},
        ],
        "type": "Damage",
        "description": "Fire off a harpoon dealing damage and immobilizing the target.",
    },
    "ThrowMines": {
        "animations": [
            {"name": "ThrowMines Cast", "id": 323},
            {"name": "ThrowMines Resolve", "id": 324},
        ],
        "type": "Damage",
        "description": "Throw mines that explode as soon as an enemy unit is nearby.",
    },
}
