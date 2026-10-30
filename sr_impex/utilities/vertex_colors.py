"""BattleForge 0x28001 POINT color stream, represented as editable RGBA."""

COLOR_ATTRIBUTE = 'SR Color0'
COLOR_STREAM_KEY = '_sr_vertex_color_stream'
COLOR_STREAM_REVISION = 0x28001


def import_color_stream(mesh, vertices):
    """Keep bytes losslessly while presenting the shader's BGR swizzle as RGB."""
    attr=mesh.color_attributes.new(name=COLOR_ATTRIBUTE,type='FLOAT_COLOR',domain='POINT')
    for vertex,value in enumerate(vertices):
        b,g,r,a=value.diffuse
        attr.data[vertex].color=(r/255.,g/255.,b/255.,a/255.)
    mesh[COLOR_STREAM_KEY]=True
    return attr


def color_stream_bytes(attribute,vertex_index):
    rgba=attribute.data[vertex_index].color
    def byte(value):return max(0,min(255,round(float(value)*255)))
    return [byte(rgba[2]),byte(rgba[1]),byte(rgba[0]),byte(rgba[3])]
