"""Read DDS volume base-level slices without modifying the source texture."""
import struct


def split_volume(data,max_texels=16_777_216):
    if len(data)<128 or data[:4]!=b'DDS ':raise ValueError('Water-decal animation requires a volume DDS texture')
    height,width,depth=struct.unpack_from('<II4xI',data,12)
    if width<=0 or height<=0 or depth<2:raise ValueError('Water-decal texture is 2D; native shader samples a 3D volume')
    fourcc=data[84:88];offset=128
    if fourcc==b'DX10':
        if len(data)<148:raise ValueError('Truncated DDS DX10 header')
        fmt,dimension,_,array_size,_=struct.unpack_from('<5I',data,128)
        if dimension!=4 or array_size!=1:raise ValueError('Expected one DDS 3D texture')
        offset=148
        if fmt in (71,72,80,81):block=8
        elif fmt in (74,75,77,78,83,84,95,96,98,99):block=16
        elif fmt in (28,29,87,91):block=0
        else:raise ValueError(f'Volume DDS DXGI format {fmt} has no slice decoder route')
        size=((width+3)//4)*((height+3)//4)*block if block else width*height*4
    elif fourcc in (b'DXT1',b'ATI1',b'BC4U',b'BC4S'):
        size=((width+3)//4)*((height+3)//4)*8
    elif fourcc in (b'DXT3',b'DXT5',b'ATI2',b'BC5U',b'BC5S'):
        size=((width+3)//4)*((height+3)//4)*16
    elif fourcc==b'\0\0\0\0':
        bits=struct.unpack_from('<I',data,88)[0]
        if bits not in (8,16,24,32):raise ValueError(f'Unsupported volume DDS pixel width {bits}')
        pitch=struct.unpack_from('<I',data,20)[0]
        size=max(width*bits//8,pitch)*height
    else:raise ValueError(f'Unsupported volume DDS FourCC {fourcc!r}')
    if offset+size*depth>len(data):raise ValueError('Truncated DDS volume base level')
    count=min(depth,128,max_texels//(width*height))
    if count<2:raise ValueError('Volume texture exceeds the preview pixel budget')
    indices=[round(i*(depth-1)/(count-1)) for i in range(count)]
    header=bytearray(data[:offset])
    flags=struct.unpack_from('<I',header,8)[0]
    struct.pack_into('<I',header,8,flags&~(0x800000|0x20000))
    struct.pack_into('<II',header,24,0,1)
    caps=struct.unpack_from('<I',header,108)[0]
    struct.pack_into('<II',header,108,(caps&~(8|0x400000))|0x1000,0)
    if flags&0x80000:struct.pack_into('<I',header,20,size)
    if fourcc==b'DX10':struct.pack_into('<I',header,132,3)
    slices=[bytes(header)+data[offset+i*size:offset+(i+1)*size] for i in indices]
    return slices,indices,depth


def volume_coordinate(time,indices,depth):
    """Clamp/trilinear Z sampling, including half-texel centers."""
    from bisect import bisect_right
    position=max(0.,min(depth-1.,time*depth-.5))
    high=max(1,min(len(indices)-1,bisect_right(indices,position)));low=high-1
    weight=(position-indices[low])/max(1,indices[high]-indices[low])
    return low,high,max(0.,min(1.,weight))
