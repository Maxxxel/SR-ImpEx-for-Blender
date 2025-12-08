
The most important file the bmg file.

magic -> -981667554
number of models -> 1
node offset, node info offset, node count -> dynamic -> need to find "types" of buildings first so i know the write orders

Types:
- Static Building
    Nodes: RootNode, MeshSetGrid_1, CGeoPrimitiveContainer2, collisionShape3
    Example: "buildings\\frost\\ice_shield_tower\\building_frost_ice_shield_tower.bmg"
    DRS Structure: CGeoMesh1_CGeoOBBTree5_CDspJointMap4_CDspMeshFile3_DrwResourceMeta6_CGeoPrimitiveContainer2_collisionShape7
    Note: there are 2 drs files with CDrwLocatorList, check them later!
- Animated with Effects
    Nodes: RootNode, MeshSetGrid_1, AnimationSet_5, AnimationTimings_4, EffectSet_2, CGeoPrimitiveContainer_3, collisionShape_6
    Example: "buildings\\bandits\\air_defense_launcher\\building_bandits_air_defense_launcher.bmg"
    DRS Structure: CGeoMesh1_CGeoOBBTree6_CDspJointMap5_CSkSkinInfo7_CSkSkeleton3_CDspMeshFile4_DrwResourceMeta8_CGeoPrimitiveContainer2_collisionShape9
- Animated no Effects
    Nodes: RootNode, MeshSetGrid_1, AnimationSet_4, AnimationTimings_3, CGeoPrimitiveContainer_2, collisionShape_5
    Example: "buildings\\fire\\termite_hill\\building_fire_termite_hill.bmg"
    DRS Structure: CGeoMesh1_CGeoOBBTree6_CDspJointMap5_CSkSkinInfo7_CSkSkeleton3_CDspMeshFile4_DrwResourceMeta8_CGeoPrimitiveContainer2_collisionShape9
- Static Building no Collision
    Nodes: RootNode, MeshSetGrid_1
    Example: "buildings\\quest\\pve_firewall\\quest_pve_firewall.bmg" (the only one)
    DRS Structure: Read ERROR!

MeshSetGrid:
    revision -> 5
    gridWidht and gridHeight need to be automatically calculated to fit the model
    name -> empty
    uuid -> test if there are empty ones
    gridRotation -> we set 0 default
    groundDecal -> if present use it
    effectGenDebris -> only fire and nature use that rarely else empty
    uk_string1 -> always empty
    moduleDistance -> always 2
    isCenterPivoted -> we set 1 by default
    Cells:
        rotation: 0
        hasMeshSet: depends
        stateBasedMeshSet:
            version: 1
            revision: 10
            numMeshStates: its always 2
            MeshStates:
                stateNum: 0 or 2 (depends)
                hasFiles: 1
                unknownFile: always empty
                drsFile: str
            numDestructionStates: its always 2
            DestructionStates
                stateNum: 2 or 3 (depends)
                destructionFile: str
    drawLocatorList:
        magic: 281702437
        version: 5
        len: depends
        SLocators: depends

CollisionShape:
- Always the collision shapes of State 0 (duplicates). State2 will overwrite it if needed in the game engine.