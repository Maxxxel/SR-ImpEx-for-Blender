# CGeoPrimitiveContainer
<a id="cgeoprimitivecontainer"></a>

Marker node used by certain object types. It has **no payload**; it exists to structure the DRS and gate where primitive or collision-related blocks appear in the node order.

---

## Overview

- **Purpose:** Structural placeholder in the DRS hierarchy (no data to edit).  
- **Where it shows up:** Common in **static objects** and some **animated objects with collision**, placed before OBB/collision mesh blocks in the write order.  
- **Engine impact:** None directly; readers use its presence to route parsing/ordering.

---

## Structure
<a id="cgeoprimitivecontainer-struct"></a>

| Field | Type | Default | Description |
|------:|------|---------|-------------|
| *(none)* | – | – | This class has **no binary content** (size `0`). |

---

## Authoring & In-Game Behavior

- **Nothing to tweak:** Artists don’t edit this node; it’s created or written by the exporter to keep node order consistent.  
- **Why you might care:** If you diff DRS files or inspect node tables, you’ll see this entry around collision-related blocks. Its presence doesn’t change visuals or physics on its own.

---

## Validation Rules

| Rule | Why it matters |
|------|----------------|
| `size == 0` | Confirms it’s truly a marker-only block. |
| NodeInformation points to a 0-byte region | Keeps offsets and sizes consistent for readers. |

---

## Performance Notes

None — zero-size marker; no runtime data or traversal costs.

---

## Cross-References

- **Header / Nodes:** How classes are linked → [Header → NodeInformation](../drs/header.md#nodeinformation).  
- **Write order contexts:** Appears in *StaticObjectCollision* and *AnimatedObjectCollision* pipelines before OBBTree or Mesh.  
- **Magic value:** `CGeoPrimitiveContainer = 1396683476 (0x5342C5D4)`. See [Glossary → MagicValues](../glossary.md#magicvalues).

---

## Known Variants / Game Differences

None known — always zero-sized in current BF/Skylords data.

---

## Nice to know

If you delete it manually from a DRS, some tools may still load fine, but **exporters and validators** expect it where defined by the node order. Keep it.
