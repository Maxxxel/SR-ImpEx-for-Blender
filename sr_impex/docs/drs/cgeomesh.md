# CGeoMesh

The `CGeoMesh` class represents the final triangle mesh after deduplication.

---

## Structure

| Field          | Type            | Default | Description                                                     |
|----------------|-----------------|---------|-----------------------------------------------------------------|
| `magic`        | `uint`          | `1`     | Constant identifier for `CGeoMesh`                              |
| `index_count`  | `uint`          | `0`     | Number of face indices (`#Faces * 3`)                           |
| `faces`        | `List[Face]`    | –       | List of triangle faces (see [Face](../common.md#face-struct))   |
| `vertex_count` | `uint`          | –       | Number of vertices                                              |
| `vertices`     | `List[Vertex4]` | –       | See [Vertex (Vector4)](../common.md#vertex-struct)              |

**Hard limit:** because faces index vertices via `ushort`, `vertex_count ≤ 65535`.

---

## Validation Rules

| Rule                                 | Description                                  |
|--------------------------------------|----------------------------------------------|
| `magic == 1`                         | Valid CGeoMesh block                          |
| `index_count % 3 == 0`               | Triangles only                                |
| `len(vertices) == vertex_count`      | Vertex list consistency                       |
| `max(face indices) < vertex_count`   | All indices must be within range              |
| `vertex_count ≤ 65535`               | Imposed by 16-bit indices                     |

---

## Nice to know

**NodeInformation Magic:** See [MagicValues → CGeoMesh](../glossary.md#magicvalues).