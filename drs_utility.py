from .drs_file import BattleforgeMesh, CDspMeshFile, Face, Vertex
from .drs_importer import create_material


import bpy


def create_static_mesh(context: bpy.types.Context, mesh_file: CDspMeshFile, base_name: str, dir_name:str, mesh_object: bpy.types.Object, state: bool = False, override_name: str = ""):
    for i in range(mesh_file.MeshCount):
        BattleforgeMeshData: BattleforgeMesh = mesh_file.Meshes[i]

        _name = override_name if (override_name != '') else f"State_{i}" if (state == True) else f"{i}"
        mesh_name = f"MeshData_{_name}"

        static_mesh = bpy.data.meshes.new(mesh_name)
        static_mesh_object = bpy.data.objects.new(mesh_name, static_mesh)

        Vertices = list()
        Faces = list()		
        Normals = list()
                
        UVList = list()

        for _ in range(BattleforgeMeshData.FaceCount):
            _Face: Face = BattleforgeMeshData.Faces[_].Indices
            Faces.append([_Face[0], _Face[1], _Face[2]])

        for _ in range(BattleforgeMeshData.VertexCount):
            _Vertex: Vertex = BattleforgeMeshData.MeshData[0].Vertices[_]
            Vertices.append(_Vertex.Position)
            Normals.append(_Vertex.Normal)
            # Negate the UVs Y Axis before adding them
            UVList.append((_Vertex.Texture[0], -_Vertex.Texture[1]))

        static_mesh.from_pydata(Vertices, [], Faces)
        static_mesh.polygons.foreach_set('use_smooth', [True] * len(static_mesh.polygons))
        static_mesh.normals_split_custom_set_from_vertices(Normals)
        if (bpy.app.version[:2] in [(3,3),(3,4),(3,5),(3,6),(4,0)]):
            static_mesh.use_auto_smooth = True

        UVList = [i for poly in static_mesh.polygons for vidx in poly.vertices for i in UVList[vidx]]
        static_mesh.uv_layers.new().data.foreach_set('uv', UVList)

        MaterialData = create_material(i, BattleforgeMeshData, dir_name, base_name)
        static_mesh.materials.append(MaterialData)
        static_mesh_object.parent = mesh_object

        bpy.context.collection.objects.link(static_mesh_object)
        