# Glossary (Enums & Constants)

Central reference for magic values, enums and indices used across the DRS format and Blender tools.  
Values are shown in **decimal** and **hex**.

---

## MagicValues

These are the `NodeInformation.magic` identifiers used to tag blocks in the container.

| Name | Decimal | Hex |
|---|---:|---:|
| `CDspJointMap` | -1340635850 | 0xB01E64C6 |
| `CGeoMesh` | 100449016 | 0x05FBDF08 |
| `CGeoOBBTree` | -933519637 | 0xC88A90FB |
| `CSkSkinInfo` | -761174227 | 0xD2541ADD |
| `CDspMeshFile` | -1900395636 | 0x8EDCF4A4 |
| `DrwResourceMeta` | -183033339 | 0xF51F0ED5 |
| `collisionShape` | 268607026 | 0x1006C5F2 |
| `CGeoPrimitiveContainer` | 1396683476 | 0x5342C5D4 |
| `CSkSkeleton` | -2110567991 | 0x8192C3B9 |
| `CDrwLocatorList` | 735146985 | 0x2BC5D0C9 |
| `AnimationSet` | -475734043 | 0xE3A5C3E5 |
| `AnimationTimings` | -1403092629 | 0xAC56E6BB |
| `EffectSet` | 688490554 | 0x2912AE1A |

> Note: exact hex is shown as two’s complement for negatives. The decimal values are what you actually read/write.

---

## AnimationType

Used in `AnimationTimings` / ability timing metadata.

| Name | Value |
|---|---:|
| `CastResolve` | 0 |
| `Spawn` | 1 |
| `Melee` | 2 |
| `Channel` | 3 |
| `ModeSwitch` | 4 |
| `WormMovement` | 5 |

---

## LocatorClass

Semantic meaning for locators in `CDrwLocatorList`.

| ID | Name | Notes |
|---:|---|---|
| 0 | `HealthBar` | Health bar offset |
| 1 | `DestructiblePart` | Static module/parts |
| 2 | `Construction` | “PivotOffset”; construction pieces |
| 3 | `Turret` | Animated child unit (plays SKA) |
| 4 | `FxbIdle` | WormDecal; idle effects |
| 5 | `Wheel` | Animated child (idle/walk/run) |
| 6 | `StaticPerm` | FXNode; permanent building/object FX |
| 7 | `Unknown7` | — |
| 8 | `DynamicPerm` | Unit permanent effects → FXB |
| 9 | `DamageFlameSmall` | Building damage fire (small) |
| 10 | `DamageFlameSmallSmoke` | Damage smoke |
| 11 | `DamageFlameLarge` | Building damage fire (large) |
| 12 | `DamageSmokeOnly` | Damage smoke only |
| 13 | `DamageFlameHuge` | Building damage fire (huge) |
| 14 | `SpellCast` | Legacy/unused |
| 15 | `SpellHitAll` | Legacy/unused |
| 16 | `Hit` | Hit point for attacks/spells |
| 29 | `Projectile_Spawn` | Projectile/effect spawn point |
