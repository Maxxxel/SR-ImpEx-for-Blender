# Advanced Object Setup

Start with the [Object Creation Guide](object_creation_guide.md).
These notes cover the less common problems and export options.

## Orientation and parenting

Collections determine the exported objects. A parent relationship determines
coordinate space. GameOrientation includes a rotation and a mirror for the
Blender display; do not reset it or apply its transform to all children.

Ctrl+P > Object (Keep Transform) keeps the object in place by adding a parent
inverse. Assigning a parent directly in Object Properties > Relations is a
different operation. Applying object rotation does not remove a parent inverse.
For a new object that exports rotated, compare a fresh import, then review the
mesh's baked transform and parent inverse. Keep an untouched copy before
correcting them. Use the GameOrientation belonging to the same model.
Rigged objects should retain their existing armature relationships.

## Mesh preparation

The exporter reads stored mesh data. Convert non-mesh objects and apply
geometry-changing modifiers on a working copy before export. Provide an active
UV layer; tangents are calculated from it. Auto-fix Quad Faces triangulates
the export copy, but inspect problematic faces beforehand.

Validation checks both individual meshes and the combined, welded render mesh
against the 32,767-vertex limit. UV seams may create additional vertices.
UV splitting can add vertices, so leave headroom below the vertex limit.

Use one exported material per mesh. Multiple material slots do not establish
independent game materials for that object.

## Collision

Collection membership selects the primitive type. Boxes must remain
rectangular, spheres round, and cylinders circular with parallel caps.
Avoid bevels and shear. A single sphere cannot represent an ellipsoid, and a
cylinder cannot represent an elliptical cylinder exactly.

Parent collision objects to GameOrientation, fit them, and check a fresh
export/import for position, rotation, radius and height. Collision-enabled
export requires collision data and the matching Model Type.

Collision, terrain height and unit navigation are different systems. Adding
collision to a bridge model does not establish that units can walk on it.
Test navigation separately in the Map Editor and in game.

## Export options

Select a mesh in the model or its DRSModel_ collection. The exporter detects the model root.
The exporter finds the root from a model mesh or nested model collection.
You do not need to move the 3D cursor; preparation uses the world origin and
restores the cursor afterwards. Source meshes remain outside the export selection.

| Option | Use |
| --- | --- |
| Split Mesh by UV Islands | Leave the default unless you manage splits yourself. |
| Flip Normals | Only for a confirmed face-orientation problem. |
| Auto-fix Quad Faces | Triangulates the export copy. |
| Mip Maps | Auto preserves eligible unchanged DDS sources. Other choices cap mip counts; they do not force a particular in-game mip level. |
| Export All SKA Actions | For animations; unnecessary for static objects. |
| Model Name Prefix | Changes exported SKA naming. |
| Export SKA Tangents | Animation debugging; unnecessary for static objects. |
| Keep Debug Collection | Retains the export copy for inspection. |

After export, import into a fresh scene with the same import settings. Compare
scale, orientation, surface appearance and collision fit. If export fails,
read the add-on log before changing geometry or materials at random.
