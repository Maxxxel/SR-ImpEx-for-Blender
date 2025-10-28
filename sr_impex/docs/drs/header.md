# DRS Header & Core Nodes

This section describes the **DRS file header** and the **core node structures** on which all class data depends.  
These structures form the backbone of the DRS archive layout.

---

## Overview

```mermaid
flowchart TD
  A[DRS Header] --> B[NodeInformation[]]
  A --> C[Node[]]
  B -->|info_index| C
  C -->|name / identifier| D[Class Data Blocks]
```

!!! note "Root Elements"
    - The **first NodeInformation entry** and the **first Node** always represent the **Root Node**.  
    - The Root Node itself does not contain payload data — it only anchors the hierarchy.

---

## Header Structure

| Field | Type | Description |
|-------|------|-------------|
| `magic` | `int` | Constant signature value `-981667554` |
| `number_of_models` | `uint` | Always `1` in *BattleForge* |
| `node_information_offset` | `uint` | Offset where the **NodeInformation** section starts |
| `node_hierarchy_offset` | `uint` | Offset where the **Node** section starts |
| `node_count` | `uint` | Total number of Nodes |

> The first NodeInformation and Node entries at these offsets correspond to the Root Node.

---

## RootNodeInformation

Represents metadata for the Root Node and tracks how many additional nodes exist.

| Field | Type | Default | Description |
|--------|------|----------|-------------|
| `zeroes[16]` | `int[16]` | `0` | Spacer / padding (16×0) |
| `neg_one` | `int` | `-1` | Unknown use, always `-1` |
| `one` | `uint` | `1` | Unknown use, always `1` |
| `node_information_count` | `uint` | – | Number of **additional NodeInformation** entries |
| `zero` | `uint` | `0` | Unknown use, always `0` |

!!! tip
    `node_information_count` equals `node_count - 1`, because the Root Node itself is excluded.

---

## NodeInformation

Links each Node to the data blob of its class.

| Field | Type | Description |
|--------|------|-------------|
| `magic` | `int` | Unique magic number identifying the class type |
| `identifier` | `uint` | References `Node.info_index` (`-1` for Root) |
| `offset` | `uint` | File offset where the class data starts |
| `size` | `uint` | Size of the data blob in bytes |
| `unused[4]` | `uint[4]` | Four unused values (ignored in BattleForge / Skylords, used in SpellForce 2) |

---

## Root Node (first entry in Node hierarchy)

| Field | Type | Default | Description |
|--------|------|----------|-------------|
| `identifier` | `uint` | `0` | Identifier of the Root Node |
| `unknown` | `uint` | `0` | Unknown, always zero |
| `length` | `uint` | `9` | Length of the string `"root_node"` |
| `name` | `str` | `"root_node"` | Name of the Root Node |

The Root Node always has identifier `0` and name `"root_node"`.  
It precedes all other class nodes in the hierarchy.

---

## Node (generic hierarchy entry)

Each Node represents a link between a **class name** and its corresponding **NodeInformation entry**.  
Every Node ends with a zero integer used as a spacer.

| Field | Type | Description |
|--------|------|-------------|
| `info_index` | `uint` | Index into the **NodeInformation** table (`-1` for Root) |
| `length` | `uint` | Length of the class name string |
| `name` | `str` | The class name |
| `zero` | `uint` | Always `0` (spacer) |

---

## Validation Rules

| Rule | Description |
|------|--------------|
| `Header.magic == -981667554` | Validates file signature |
| `Header.node_count >= 1` | At least one node (Root) must exist |
| `RootNode.identifier == 0` and `RootNode.name == "root_node"` | Root node consistency |
| `len(NodeInformation) == Header.node_count - 1` | Node counts must match (`-1` for RootNodeInformation) |
| Each `Node.info_index >= 0` | Must reference valid NodeInformation (except Root) |
| No overlapping `offset`/`size` pairs | Class data blocks must not overlap |

---

## Known Variants

| Game / Version | Notes |
|----------------|-------|
| **BattleForge / Skylords Reborn** | `unused[4]` fields are unused; `number_of_models` is always `1`. |
| **SpellForce 2 DRS** | `unused[4]` were used to override settings for certain assets. |

---

## Summary

The DRS Header defines where all structural blocks of the archive begin.  
From there, each **NodeInformation** and **Node** entry establishes the relationship between **class metadata** and **data payloads**.  
Understanding this hierarchy is essential before parsing any of the 15 class structures that follow.
