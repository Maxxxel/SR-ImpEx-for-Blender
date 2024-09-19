from dataclasses import dataclass, field
from struct import calcsize, pack, unpack
from typing import List, Union, BinaryIO, Optional
from mathutils import Vector, Matrix, Quaternion
from .file_io import FileReader, FileWriter

def unpack_data(file: BinaryIO, *formats: str) -> List[List[Union[float, int]]]:
	result = []
	for fmt in formats:
		result.append(list(unpack(fmt, file.read(calcsize(fmt)))))
	return result

MagicValues = {
	"CDspJointMap": -1340635850,
	"CGeoMesh": 100449016,
	"CGeoOBBTree": -933519637,
	"CSkSkinInfo": -761174227,
	"CDspMeshFile": -1900395636,
	"DrwResourceMeta": -183033339,
	"collisionShape": 268607026,
	"CGeoPrimitiveContainer": 1396683476
}

@dataclass(eq=False, repr=False)
class RootNode():
	identifier: int = 0
	unknown: int = 0
	length: int = field(default=9, init=False)
	name: str = "root name"

	def read(self, file: BinaryIO) -> 'RootNode':
		self.identifier, self.unknown, self.length = unpack("iii", file.read(calcsize("iii")))
		self.name = file.read(self.length).decode('utf-8').strip('\x00')
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f"iii{self.length}s", self.identifier, self.unknown, self.length, self.name.encode("utf-8")))

	def size(self) -> int:
		return calcsize(f"iii{self.length}s")

@dataclass(eq=False, repr=False)
class Node:
	info_index: int = 0
	length: int = field(default=0, init=False)
	name: str = ""
	zero: int = 0

	def __post_init__(self):
		self.length = len(self.name)

	def read(self, file: BinaryIO) -> 'Node':
		self.info_index, self.length = unpack('ii', file.read(calcsize('ii')))
		self.name = unpack(f'{self.length}s', file.read(calcsize(f'{self.length}s')))
		self.zero = unpack('i', file.read(calcsize('i')))[0]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f'ii{self.length}si', self.info_index, self.length, self.name.encode("utf-8"), self.zero))

	def size(self) -> int:
		return calcsize(f'ii{self.length}si')

@dataclass(eq=False, repr=False)
class RootNodeInformation:
	zeroes: List[int] = field(default_factory=lambda: [0] * 16)
	neg_one: int = -1
	one: int = 1
	node_information_count: int = 0
	zero: int = 0
	data_object: None = None # Placeholder

	def read(self, file: BinaryIO) -> 'RootNodeInformation':
		self.zeroes = unpack('16b', file.read(calcsize('16b')))
		self.neg_one, self.one, self.node_information_count, self.zero = unpack('iiii', file.read(calcsize('iiii')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('16biiii', *self.zeroes, self.neg_one, self.one, self.node_information_count, self.zero))

	def size(self) -> int:
		return calcsize('16biiii')

@dataclass(eq=False, repr=False)
class NodeInformation:
	"""Node Information"""
	magic: int = field(init=False)
	identifier: int = -1
	offset: int = -1
	node_size: int = field(init=False)
	spacer: List[int] = field(default_factory=lambda: [0] * 16)
	data_object: Optional[object] = None

	def __post_init__(self):
		global MagicValues
		self.magic = MagicValues.get(self.data_object.__class__.__name__, 0) if self.data_object else 0
		self.node_size = self.data_object.size() if self.data_object else 0

	def read(self, file: BinaryIO) -> 'NodeInformation':
		self.magic, self.identifier, self.offset, self.node_size = unpack('iiii', file.read(calcsize('iiii')))
		self.spacer = unpack('16b', file.read(calcsize('16b')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('iiii16b', self.magic, self.identifier, self.offset, self.node_size, *self.spacer))

	def update_offset(self, offset: int) -> None:
		self.offset = offset

	def size(self) -> int:
		return calcsize('iiii16b')

@dataclass(eq=False, repr=False)
class Vertex:
	position: Optional[List[float]] = field(default_factory=list)
	normal: Optional[List[float]] = field(default_factory=list)
	texture: Optional[List[float]] = field(default_factory=list)
	tangent: Optional[List[float]] = field(default_factory=list)
	bitangent: Optional[List[float]] = field(default_factory=list)
	raw_weights: Optional[List[int]] = field(default_factory=lambda: [0] * 4)
	bone_indices: Optional[List[int]] = field(default_factory=lambda: [0] * 4)

	def read(self, file: BinaryIO, revision: int) -> 'Vertex':
		if revision == 133121:
			self.position, self.normal, self.texture = unpack_data(file, 'fff', 'fff', 'ff')
		elif revision == 12288:
			self.tangent, self.bitangent = unpack_data(file, 'fff', 'fff')
		elif revision == 12:
			self.raw_weights, self.bone_indices = unpack_data(file, '4B', '4B')
		return self

	def write(self, file: BinaryIO) -> None:
		if self.position:
			file.write(pack('fff', *self.position))
		if self.normal:
			file.write(pack('fff', *self.normal))
		if self.texture:
			file.write(pack('ff', *self.texture))
		if self.tangent:
			file.write(pack('fff', *self.tangent))
		if self.bitangent:
			file.write(pack('fff', *self.bitangent))
		if self.raw_weights:
			file.write(pack('4B', *self.raw_weights))
		if self.bone_indices:
			file.write(pack('4B', *self.bone_indices))

	def size(self) -> int:
		if self.position:
			return calcsize('fff')
		if self.normal:
			return calcsize('fff')
		if self.texture:
			return calcsize('ff')
		if self.tangent:
			return calcsize('fff')
		if self.bitangent:
			return calcsize('fff')
		if self.raw_weights:
			return calcsize('4B')
		if self.bone_indices:
			return calcsize('4B')
		return 0

@dataclass(eq=False, repr=False)
class VertexData:
	weights: List[float] = field(default_factory=lambda: [0.0] * 4)
	bone_indices: List[int] = field(default_factory=lambda: [0] * 4)

	def read(self, file: BinaryIO) -> 'VertexData':
		data = unpack('4f4i', file.read(calcsize('4f4i')))
		self.weights, self.bone_indices = list(data[:4]), list(data[4:])
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('4f4i', *self.weights, *self.bone_indices))

	def size(self) -> int:
		return calcsize('4f4i')

@dataclass(eq=False, repr=False)
class Face:
	indices: List[int] = field(default_factory=lambda: [0] * 3)

	def read(self, file: BinaryIO) -> 'Face':
		self.indices = list(unpack('3H', file.read(calcsize('3H'))))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('3H', *self.indices))

	def size(self) -> int:
		return calcsize('3H')

@dataclass(repr=False)
class Vector4:
	x: float = 0.0
	y: float = 0.0
	z: float = 0.0
	w: float = 0.0

	def read(self, file: BinaryIO) -> 'Vector4':
		self.x, self.y, self.z, self.w = unpack('4f', file.read(calcsize('4f')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('4f', self.x, self.y, self.z, self.w))

	def size(self) -> int:
		return calcsize('4f')

@dataclass(repr=False)
class Vector3:
	x: float = 0.0
	y: float = 0.0
	z: float = 0.0

	def read(self, file: BinaryIO) -> 'Vector3':
		self.x, self.y, self.z = unpack('3f', file.read(calcsize('3f')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('3f', self.x, self.y, self.z))

	def size(self) -> int:
		return calcsize('3f')

@dataclass(eq=False, repr=False)
class Matrix4x4:
	matrix: tuple = ((0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0))

	def read(self, file: BinaryIO) -> 'Matrix4x4':
		self.matrix = unpack('16f', file.read(calcsize('16f')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('16f', *self.matrix))

	def size(self) -> int:
		return calcsize('16f')

@dataclass(eq=False, repr=False)
class Matrix3x3:
	matrix: tuple = ((0, 0, 0), (0, 0, 0), (0, 0, 0))

	def read(self, file: BinaryIO) -> 'Matrix3x3':
		self.matrix = unpack('9f', file.read(calcsize('9f')))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('9f', *self.matrix))

	def size(self) -> int:
		return calcsize('9f')

@dataclass(eq=False, repr=False)
class CMatCoordinateSystem:
	matrix: Matrix3x3 = field(default_factory=Matrix3x3)
	position: Vector3 = field(default_factory=Vector3)

	def read(self, file: BinaryIO) -> 'CMatCoordinateSystem':
		self.matrix = Matrix3x3().read(file)
		self.position = Vector3().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		self.matrix.write(file)
		self.position.write(file)

	def size(self) -> int:
		return self.matrix.size() + self.position.size()

@dataclass(eq=False, repr=False)
class CGeoMesh:
	magic: int = 1
	index_count: int = 0
	faces: List[Face] = field(default_factory=list)
	vertex_count: int = 0
	vertices: List[Vector4] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CGeoMesh':
		self.magic, self.index_count = unpack('ii', file.read(calcsize('ii')))
		self.faces = [Face().read(file) for _ in range(self.index_count // 3)]
		self.vertex_count = unpack('i', file.read(calcsize('i')))[0]
		self.vertices = [Vector4().read(file) for _ in range(self.vertex_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('ii', self.magic, self.index_count))
		for face in self.faces:
			face.write(file)
		file.write(pack('i', self.vertex_count))
		for vertex in self.vertices:
			vertex.write(file)

	def size(self) -> int:
		return calcsize('iii') + calcsize('3H') * len(self.faces) + calcsize('4f') * len(self.vertices)

@dataclass(eq=False, repr=False)
class CSkSkinInfo:
	version: int = 1
	vertex_count: int = 0
	vertex_data: List[VertexData] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CSkSkinInfo':
		self.version, self.vertex_count = unpack('ii', file.read(calcsize('ii')))
		self.vertex_data = [VertexData().read(file) for _ in range(self.vertex_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('ii', self.version, self.vertex_count))
		for vertex in self.vertex_data:
			vertex.write(file)

	def size(self) -> int:
		return calcsize('ii') + sum(vd.size() for vd in self.vertex_data)

@dataclass(eq=False, repr=False)
class MeshData:
	revision: int = 0
	vertex_size: int = 0
	vertices: List[Vertex] = field(default_factory=list)

	def read(self, file: BinaryIO, vertex_count: int) -> 'MeshData':
		self.revision, self.vertex_size = unpack('ii', file.read(calcsize('ii')))
		self.vertices = [Vertex().read(file, self.revision) for _ in range(vertex_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('ii', self.revision, self.vertex_size))
		for vertex in self.vertices:
			vertex.write(file)

	def size(self) -> int:
		return calcsize('ii') + self.vertex_size * len(self.vertices)

@dataclass(eq=False, repr=False)
class Bone:
	version: int = 0
	identifier: int = 0
	name_length: int = field(default=0, init=False)
	name: str = ""
	child_count: int = 0
	children: List[int] = field(default_factory=list)

	def __post_init__(self):
		self.name_length = len(self.name)

	def read(self, file: BinaryIO) -> 'Bone':
		self.version, self.identifier, self.name_length = unpack('iii', file.read(calcsize('iii')))
		self.name = unpack(f'{self.name_length}s', file.read(calcsize(f'{self.name_length}s')))[0].decode('utf-8').strip('\x00')
		self.child_count = unpack('i', file.read(calcsize('i')))[0]
		self.children = list(unpack(f'{self.child_count}i', file.read(calcsize(f'{self.child_count}i'))))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f'iiii{self.name_length}s{self.child_count}i', self.version, self.identifier, self.name_length, self.name.encode('utf-8'), self.child_count, *self.children))

	def size(self) -> int:
		return calcsize(f'iiii{self.name_length}s{self.child_count}i')

@dataclass(eq=False, repr=False)
class BoneMatrix:
	bone_vertices: List['BoneVertex'] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'BoneMatrix':
		self.bone_vertices = [BoneVertex().read(file) for _ in range(4)]
		return self

	def write(self, file: BinaryIO) -> 'BoneMatrix':
		for bone_vertex in self.bone_vertices:
			bone_vertex.write(file)
		return self

	def size(self) -> int:
		return sum(bv.size() for bv in self.bone_vertices)

@dataclass(eq=False, repr=False)
class BoneVertex:
	position: 'Vector3' = field(default_factory=Vector3)
	parent: int = 0

	def read(self, file: BinaryIO) -> 'BoneVertex':
		self.position = Vector3().read(file)
		self.parent = unpack('i', file.read(calcsize('i')))[0]
		return self

	def write(self, file: BinaryIO) -> None:
		self.position.write(file)
		file.write(pack('i', self.parent))

	def size(self) -> int:
		return self.position.size() + calcsize('i')

class DRSBone():
	"""docstring for DRSBone"""
	def __init__(self) -> None:
		self.ska_identifier: int
		self.identifier: int
		self.name: str
		self.parent: int = -1
		self.bone_matrix: Matrix
		self.children: List[int]
		self.bind_loc: Vector
		self.bind_rot: Quaternion

@dataclass(eq=False, repr=False)
class CSkSkeleton:
	magic: int = 1558308612
	version: int = 3
	bone_matrix_count: int = 0
	bone_matrices: List[BoneMatrix] = field(default_factory=list)
	bone_count: int = 0
	bones: List[Bone] = field(default_factory=list)
	super_parent: 'Matrix4x4' = field(default_factory=lambda: Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))

	def read(self, file: BinaryIO) -> 'CSkSkeleton':
		self.magic, self.version, self.bone_matrix_count = unpack('iii', file.read(calcsize('iii')))
		self.bone_matrices = [BoneMatrix().read(file) for _ in range(self.bone_matrix_count)]
		self.bone_count = unpack('i', file.read(calcsize('i')))[0]
		self.bones = [Bone().read(file) for _ in range(self.bone_count)]
		self.super_parent = Matrix4x4().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('iii', self.magic, self.version, self.bone_matrix_count))
		for bone_matrix in self.bone_matrices:
			bone_matrix.write(file)
		file.write(pack('i', self.bone_count))
		for bone in self.bones:
			bone.write(file)
		self.super_parent.write(file)

	def size(self) -> int:
		return calcsize('iiii') + sum(bone_matrix.size() for bone_matrix in self.bone_matrices) + sum(bone.size() for bone in self.bones) + self.super_parent.size()

@dataclass(eq=False, repr=False)
class Texture:
	identifier: int = 0
	length: int = field(default=0, init=False)
	name: str = ""
	spacer: int = 0

	def __post_init__(self):
		self.length = len(self.name)

	def read(self, file: BinaryIO) -> 'Texture':
		self.identifier, self.length = unpack('ii', file.read(calcsize('ii')))
		self.name = file.read(self.length).decode('utf-8').strip('\x00')
		self.spacer = unpack('i', file.read(calcsize('i')))[0]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f'ii{self.length}s i', self.identifier, self.length, self.name.encode('utf-8'), self.spacer))

	def size(self) -> int:
		return calcsize(f'ii{self.length}s i')

@dataclass(eq=False, repr=False)
class Textures:
	length: int = 0
	textures: List['Texture'] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'Textures':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		self.textures = [Texture().read(file) for _ in range(self.length)]
		return self

	def write(self, file: BinaryIO) -> None:
		self.length = len(self.textures)
		file.write(pack('i', self.length))
		for texture in self.textures:
			texture.write(file)

	def size(self) -> int:
		return calcsize('i') + sum(texture.size() for texture in self.textures)

@dataclass(eq=False, repr=False)
class Material:
	identifier: int = 0
	smoothness: float = 0.0
	metalness: float = 0.0
	reflectivity: float = 0.0
	emissivity: float = 0.0
	refraction_scale: float = 0.0
	distortion_mesh_scale: float = 0.0
	scratch: float = 0.0
	specular_scale: float = 0.0
	wind_response: float = 0.0
	wind_height: float = 0.0
	depth_write_threshold: float = 0.0
	saturation: float = 0.0
	unknown: float = 0.0

	def __init__(self, index: int = None) -> None:
		"""Material Constructor"""
		if index is not None:
			if index == 0:
				self.identifier = 1668510769
				self.smoothness = 0
			elif index == 1:
				self.identifier = 1668510770
				self.metalness = 0
			elif index == 2:
				self.identifier = 1668510771
				self.reflectivity = 0
			elif index == 3:
				self.identifier = 1668510772
				self.emissivity = 0
			elif index == 4:
				self.identifier = 1668510773
				self.refraction_scale = 1
			elif index == 5:
				self.identifier = 1668510774
				self.distortion_mesh_scale = 0
			elif index == 6:
				self.identifier = 1935897704
				self.scratch = 0
			elif index == 7:
				self.identifier = 1668510775
				self.specular_scale = 1.5
			elif index == 8:
				self.identifier = 1668510776
				self.wind_response = 0  # Needs to be updated
			elif index == 9:
				self.identifier = 1668510777
				self.wind_height = 0  # Needs to be updated
			elif index == 10:
				self.identifier = 1935893623
				self.depth_write_threshold = 0.5
			elif index == 11:
				self.identifier = 1668510785
				self.saturation = 1.0

	def read(self, file: BinaryIO) -> 'Material':
		"""Reads the Material from the buffer"""
		self.identifier = unpack('i', file.read(calcsize('i')))[0]
		if self.identifier == 1668510769:
			self.smoothness = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510770:
			self.metalness = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510771:
			self.reflectivity = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510772:
			self.emissivity = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510773:
			self.refraction_scale = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510774:
			self.distortion_mesh_scale = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1935897704:
			self.scratch = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510775:
			self.specular_scale = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510776:
			self.wind_response = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510777:
			self.wind_height = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1935893623:
			self.depth_write_threshold = unpack('f', file.read(calcsize('f')))[0]
		elif self.identifier == 1668510785:
			self.saturation = unpack('f', file.read(calcsize('f')))[0]
		else:
			self.unknown = unpack('f', file.read(calcsize('f')))[0]
			raise TypeError("Unknown Material {}".format(self.unknown))
		return self

	def write(self, file: BinaryIO) -> None:
		"""Writes the Material to the buffer"""
		file.write(pack('i', self.identifier))
		if self.identifier == 1668510769:
			file.write(pack('f', self.smoothness))
		elif self.identifier == 1668510770:
			file.write(pack('f', self.metalness))
		elif self.identifier == 1668510771:
			file.write(pack('f', self.reflectivity))
		elif self.identifier == 1668510772:
			file.write(pack('f', self.emissivity))
		elif self.identifier == 1668510773:
			file.write(pack('f', self.refraction_scale))
		elif self.identifier == 1668510774:
			file.write(pack('f', self.distortion_mesh_scale))
		elif self.identifier == 1935897704:
			file.write(pack('f', self.scratch))
		elif self.identifier == 1668510775:
			file.write(pack('f', self.specular_scale))
		elif self.identifier == 1668510776:
			file.write(pack('f', self.wind_response))
		elif self.identifier == 1668510777:
			file.write(pack('f', self.wind_height))
		elif self.identifier == 1935893623:
			file.write(pack('f', self.depth_write_threshold))
		elif self.identifier == 1668510785:
			file.write(pack('f', self.saturation))
		else:
			file.write(pack('f', self.unknown))
			raise TypeError("Unknown Material {}".format(self.unknown))
		return self

@dataclass(eq=False, repr=False)
class Materials:
	length: int = 12
	materials: List['Material'] = field(default_factory=lambda: [Material(index) for index in range(12)])

	def read(self, file: BinaryIO) -> 'Materials':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		self.materials = [Material().read(file) for _ in range(self.length)]
		return self

	def write(self, file: BinaryIO) -> None:
		self.length = len(self.materials)
		file.write(pack('i', self.length))
		for material in self.materials:
			material.write(file)

	def size(self) -> int:
		return calcsize('i') + sum(material.size() for material in self.materials)

@dataclass(eq=False, repr=False)
class Refraction:
	length: int = 0
	identifier: int = 1668510769
	rgb: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

	def read(self, file: BinaryIO) -> 'Refraction':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		if self.length == 1:
			self.identifier = unpack('i', file.read(calcsize('i')))[0]
			self.rgb = list(unpack('3f', file.read(calcsize('3f'))))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('i', self.length))
		if self.length == 1:
			file.write(pack('i', self.identifier))
			file.write(pack('3f', *self.rgb))

	def size(self) -> int:
		size = calcsize('i')
		if self.length == 1:
			size += calcsize('i') + calcsize('3f')
		return size

@dataclass(eq=False, repr=False)
class LevelOfDetail:
	length: int = 1
	lod_level: int = 2

	def read(self, file: BinaryIO) -> 'LevelOfDetail':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		if self.length == 1:
			self.lod_level = unpack('i', file.read(calcsize('i')))[0]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('i', self.length))
		if self.length == 1:
			file.write(pack('i', self.lod_level))

	def size(self) -> int:
		size = calcsize('i')
		if self.length == 1:
			size += calcsize('i')
		return size

@dataclass(eq=False, repr=False)
class EmptyString:
	length: int = 0
	unknown_string: str = ""

	def read(self, file: BinaryIO) -> 'EmptyString':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		self.unknown_string = unpack(f'{self.length * 2}s', file.read(calcsize(f'{self.length * 2}s')))[0].decode('utf-8')
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f'i{self.length * 2}s', self.length, self.unknown_string.encode('utf-8')))

	def size(self) -> int:
		return calcsize(f'i{self.length * 2}s')

@dataclass(eq=False, repr=False)
class Flow:
	length: int = 4
	max_flow_speed_identifier: int = 1668707377
	max_flow_speed: Vector4 = field(default_factory=Vector4)
	min_flow_speed_identifier: int = 1668707378
	min_flow_speed: Vector4 = field(default_factory=Vector4)
	flow_speed_change_identifier: int = 1668707379
	flow_speed_change: Vector4 = field(default_factory=Vector4)
	flow_scale_identifier: int = 1668707380
	flow_scale: Vector4 = field(default_factory=Vector4)

	def read(self, file: BinaryIO) -> 'Flow':
		self.length = unpack('i', file.read(calcsize('i')))[0]
		if self.length == 4:
			self.max_flow_speed_identifier = unpack('i', file.read(calcsize('i')))[0]
			self.max_flow_speed = Vector4().read(file)
			self.min_flow_speed_identifier = unpack('i', file.read(calcsize('i')))[0]
			self.min_flow_speed = Vector4().read(file)
			self.flow_speed_change_identifier = unpack('i', file.read(calcsize('i')))[0]
			self.flow_speed_change = Vector4().read(file)
			self.flow_scale_identifier = unpack('i', file.read(calcsize('i')))[0]
			self.flow_scale = Vector4().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('i', self.length))
		if self.length == 4:
			file.write(pack('i', self.max_flow_speed_identifier))
			self.max_flow_speed.write(file)
			file.write(pack('i', self.min_flow_speed_identifier))
			self.min_flow_speed.write(file)
			file.write(pack('i', self.flow_speed_change_identifier))
			self.flow_speed_change.write(file)
			file.write(pack('i', self.flow_scale_identifier))
			self.flow_scale.write(file)

	def size(self) -> int:
		size = calcsize('i')
		if self.length == 4:
			size += calcsize('iiii') + self.max_flow_speed.size() + self.min_flow_speed.size() + self.flow_speed_change.size() + self.flow_scale.size()
		return size

@dataclass(eq=False, repr=False)
class BattleforgeMesh:
	vertex_count: int = 0
	face_count: int = 0
	faces: List[Face] = field(default_factory=list)
	mesh_count: int = 0
	mesh_data: List[MeshData] = field(default_factory=list)
	bounding_box_lower_left_corner: Vector3 = field(default_factory=Vector3)
	bounding_box_upper_right_corner: Vector3 = field(default_factory=Vector3)
	material_id: int = 0
	material_parameters: int = 0
	material_stuff: int = 0
	bool_parameter: int = 0
	textures: Textures = field(default_factory=Textures)
	refraction: Refraction = field(default_factory=Refraction)
	materials: Materials = field(default_factory=Materials)
	level_of_detail: LevelOfDetail = field(default_factory=LevelOfDetail)
	empty_string: EmptyString = field(default_factory=EmptyString)
	flow: Flow = field(default_factory=Flow)

	def read(self, file: BinaryIO) -> 'BattleforgeMesh':
		self.vertex_count, self.face_count = unpack('ii', file.read(calcsize('ii')))
		self.faces = [Face().read(file) for _ in range(self.face_count)]
		self.mesh_count = unpack('B', file.read(calcsize('B')))[0]
		self.mesh_data = [MeshData().read(file, self.vertex_count) for _ in range(self.mesh_count)]
		self.bounding_box_lower_left_corner = Vector3().read(file)
		self.bounding_box_upper_right_corner = Vector3().read(file)
		self.material_id, self.material_parameters = unpack('=hi', file.read(calcsize('=hi')))

		if self.material_parameters == -86061050:
			self.material_stuff, self.bool_parameter = unpack('ii', file.read(calcsize('ii')))
			self.textures.read(file)
			self.refraction.read(file)
			self.materials.read(file)
			self.level_of_detail.read(file)
			self.empty_string.read(file)
			self.flow.read(file)
		elif self.material_parameters == -86061051:
			self.material_stuff, self.bool_parameter = unpack('ii', file.read(calcsize('ii')))
			self.textures.read(file)
			self.refraction.read(file)
			self.materials.read(file)
			self.level_of_detail.read(file)
			self.empty_string.read(file)
		elif self.material_parameters == -86061055:
			self.bool_parameter = unpack('i', file.read(calcsize('i')))[0]
			self.textures.read(file)
			self.refraction.read(file)
			self.materials.read(file)
		else:
			raise TypeError(f"Unknown MaterialParameters {self.material_parameters}")
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('ii', self.vertex_count, self.face_count))
		for face in self.faces:
			face.write(file)
		file.write(pack('B', self.mesh_count))
		for mesh_data in self.mesh_data:
			mesh_data.write(file)
		self.bounding_box_lower_left_corner.write(file)
		self.bounding_box_upper_right_corner.write(file)
		file.write(pack('=hi', self.material_id, self.material_parameters))

		if self.material_parameters == -86061050:
			file.write(pack('ii', self.material_stuff, self.bool_parameter))
			self.textures.write(file)
			self.refraction.write(file)
			self.materials.write(file)
			self.level_of_detail.write(file)
			self.empty_string.write(file)
			self.flow.write(file)
		elif self.material_parameters == -86061051:
			file.write(pack('ii', self.material_stuff, self.bool_parameter))
			self.textures.write(file)
			self.refraction.write(file)
			self.materials.write(file)
			self.level_of_detail.write(file)
			self.empty_string.write(file)
		elif self.material_parameters == -86061055:
			file.write(pack('i', self.bool_parameter))
			self.textures.write(file)
			self.refraction.write(file)
			self.materials.write(file)
		else:
			raise TypeError(f"Unknown MaterialParameters {self.material_parameters}")

	def size(self) -> int:
		size = calcsize('=iiB6fhi') + sum(face.size() for face in self.faces) + sum(mesh_data.size() for mesh_data in self.mesh_data)

		if self.material_parameters == -86061050:
			size += calcsize('ii')  # MaterialStuff + BoolParameter
			size += self.textures.size()
			size += self.refraction.size()
			size += self.materials.size()
			size += self.level_of_detail.size()
			size += self.empty_string.size()
			size += self.flow.size()
		elif self.material_parameters == -86061051:
			size += calcsize('ii')  # MaterialStuff + BoolParameter
			size += self.textures.size()
			size += self.refraction.size()
			size += self.materials.size()
			size += self.level_of_detail.size()
			size += self.empty_string.size()
		elif self.material_parameters == -86061055:
			size += calcsize('i')  # BoolParameter
			size += self.textures.size()
			size += self.refraction.size()
			size += self.materials.size()
		return size

@dataclass(eq=False, repr=False)
class CDspMeshFile:
	magic: int = 1314189598
	zero: int = 0
	mesh_count: int = 0
	bounding_box_lower_left_corner: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))
	bounding_box_upper_right_corner: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))
	meshes: List[BattleforgeMesh] = field(default_factory=list)
	some_points: List[Vector4] = field(default_factory=lambda: [Vector4(0, 0, 0, 1), Vector4(1, 1, 0, 1), Vector4(0, 0, 1, 1)])

	def read(self, file: BinaryIO) -> 'CDspMeshFile':
		self.magic = unpack('i', file.read(calcsize('i')))[0]
		if self.magic == 1314189598:
			self.zero, self.mesh_count = unpack('ii', file.read(calcsize('ii')))
			self.bounding_box_lower_left_corner = Vector3().read(file)
			self.bounding_box_upper_right_corner = Vector3().read(file)
			self.meshes = [BattleforgeMesh().read(file) for _ in range(self.mesh_count)]
			self.some_points = [Vector4().read(file) for _ in range(3)]
		else:
			raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('i', self.magic))
		if self.magic == 1314189598:
			file.write(pack('ii', self.zero, self.mesh_count))
			self.bounding_box_lower_left_corner.write(file)
			self.bounding_box_upper_right_corner.write(file)
			for mesh in self.meshes:
				mesh.write(file)
			for point in self.some_points:
				point.write(file)
		else:
			raise TypeError(f"This Mesh has the wrong Magic Value: {self.magic}")

	def size(self) -> int:
		size = calcsize('3i')  # Magic + Zero + MeshCount
		size += self.bounding_box_lower_left_corner.size()
		size += self.bounding_box_upper_right_corner.size()
		size += sum(mesh.size() for mesh in self.meshes)
		size += sum(point.size() for point in self.some_points)
		return size

@dataclass(eq=False, repr=False)
class OBBNode:
	oriented_bounding_box: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
	unknown1: int = 0
	unknown2: int = 0
	unknown3: int = 0
	node_depth: int = 0
	current_triangle_count: int = 0
	minimum_triangles_found: int = 0

	def read(self, file: BinaryIO) -> 'OBBNode':
		self.oriented_bounding_box = CMatCoordinateSystem().read(file)
		self.unknown1, self.unknown2, self.unknown3, self.node_depth, self.current_triangle_count, self.minimum_triangles_found = unpack('4H2i', file.read(calcsize('4H2i')))
		return self

	def write(self, file: BinaryIO) -> None:
		self.oriented_bounding_box.write(file)
		file.write(pack('4H2i', self.unknown1, self.unknown2, self.unknown3, self.node_depth, self.current_triangle_count, self.minimum_triangles_found))

	def size(self) -> int:
		return self.oriented_bounding_box.size() + calcsize('4H2i')

@dataclass(eq=False, repr=False)
class CGeoOBBTree:
	magic: int = 1845540702
	version: int = 3
	matrix_count: int = 0
	obb_nodes: List[OBBNode] = field(default_factory=list)
	triangle_count: int = 0
	faces: List[Face] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CGeoOBBTree':
		self.magic, self.version, self.matrix_count = unpack('iii', file.read(calcsize('iii')))
		self.obb_nodes = [OBBNode().read(file) for _ in range(self.matrix_count)]
		self.triangle_count = unpack('i', file.read(calcsize('i')))[0]
		self.faces = [Face().read(file) for _ in range(self.triangle_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('iii', self.magic, self.version, self.matrix_count))
		for obb_node in self.obb_nodes:
			obb_node.write(file)
		file.write(pack('i', self.triangle_count))
		for face in self.faces:
			face.write(file)

	def size(self) -> int:
		return calcsize('iiii') + sum(obb_node.size() for obb_node in self.obb_nodes) + sum(face.size() for face in self.faces)

@dataclass(eq=False, repr=False)
class JointGroup:
	joint_count: int = 0
	joints: List[int] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'JointGroup':
		self.joint_count = unpack('i', file.read(calcsize('i')))[0]
		self.joints = list(unpack(f'{self.joint_count}i', file.read(calcsize(f'{self.joint_count}i'))))
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack(f'i{self.joint_count}i', self.joint_count, *self.joints))

	def size(self) -> int:
		return calcsize('i') + calcsize(f'{self.joint_count}i')

@dataclass(eq=False, repr=False)
class CDspJointMap:
	version: int = 1
	joint_group_count: int = 0
	joint_groups: List[JointGroup] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CDspJointMap':
		self.version, self.joint_group_count = unpack('ii', file.read(calcsize('ii')))
		self.joint_groups = [JointGroup().read(file) for _ in range(self.joint_group_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('ii', self.version, self.joint_group_count))
		for joint_group in self.joint_groups:
			joint_group.write(file)

	def size(self) -> int:
		return calcsize('ii') + sum(joint_group.size() for joint_group in self.joint_groups)

@dataclass(eq=False, repr=False)
class SLocator:
	cmat_coordinate_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
	class_id: int = 0
	sub_id: int = 0
	file_name_length: int = 0
	file_name: str = ""
	uk_int: int = 0

	def read(self, file: BinaryIO, version: int) -> 'SLocator':
		self.cmat_coordinate_system = CMatCoordinateSystem().read(file)
		self.class_id, self.sub_id, self.file_name_length = unpack('iii', file.read(calcsize('iii')))
		self.file_name = unpack(f'{self.file_name_length}s', file.read(calcsize(f'{self.file_name_length}s')))[0].decode('utf-8').strip('\x00')
		if version == 5:
			self.uk_int = unpack('i', file.read(calcsize('i')))[0]
		return self

	def write(self, file: BinaryIO) -> None:
		self.cmat_coordinate_system.write(file)
		file.write(pack(f'iii{self.file_name_length}s', self.class_id, self.sub_id, self.file_name_length, self.file_name.encode('utf-8')))
		if hasattr(self, 'uk_int'):
			file.write(pack('i', self.uk_int))

	def size(self) -> int:
		size = self.cmat_coordinate_system.size() + calcsize(f'iii{self.file_name_length}s')
		if hasattr(self, 'uk_int'):
			size += calcsize('i')
		return size

@dataclass(eq=False, repr=False)
class CDrwLocatorList:
	magic: int = 0
	version: int = 0
	length: int = 0
	slocators: List[SLocator] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CDrwLocatorList':
		self.magic, self.version, self.length = unpack('iii', file.read(calcsize('iii')))
		self.slocators = [SLocator().read(file, self.version) for _ in range(self.length)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('iii', self.magic, self.version, self.length))
		for locator in self.slocators:
			locator.write(file)

	def size(self) -> int:
		return calcsize('iii') + sum(locator.size() for locator in self.slocators)

@dataclass(eq=False, repr=False)
class CGeoAABox:
	lower_left_corner: Vector3 = field(default_factory=Vector3)
	upper_right_corner: Vector3 = field(default_factory=Vector3)

	def read(self, file: BinaryIO) -> 'CGeoAABox':
		self.lower_left_corner = Vector3().read(file)
		self.upper_right_corner = Vector3().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		self.lower_left_corner.write(file)
		self.upper_right_corner.write(file)

	def size(self) -> int:
		return self.lower_left_corner.size() + self.upper_right_corner.size()

@dataclass(eq=False, repr=False)
class BoxShape:
	coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
	geo_aabox: CGeoAABox = field(default_factory=CGeoAABox)

	def read(self, file: BinaryIO) -> 'BoxShape':
		self.coord_system = CMatCoordinateSystem().read(file)
		self.geo_aabox = CGeoAABox().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		self.coord_system.write(file)
		self.geo_aabox.write(file)

	def size(self) -> int:
		return self.coord_system.size() + self.geo_aabox.size()

@dataclass(eq=False, repr=False)
class CGeoCylinder:
	center: Vector3 = field(default_factory=Vector3)
	height: float = 0.0
	radius: float = 0.0

	def read(self, file: BinaryIO) -> 'CGeoCylinder':
		self.center = Vector3().read(file)
		self.height, self.radius = unpack('ff', file.read(calcsize('ff')))
		return self

	def write(self, file: BinaryIO) -> None:
		self.center.write(file)
		file.write(pack('ff', self.height, self.radius))

	def size(self) -> int:
		return self.center.size() + calcsize('ff')

@dataclass(eq=False, repr=False)
class CylinderShape:
	coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
	geo_cylinder: CGeoCylinder = field(default_factory=CGeoCylinder)

	def read(self, file: BinaryIO) -> 'CylinderShape':
		self.coord_system = CMatCoordinateSystem().read(file)
		self.geo_cylinder = CGeoCylinder().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		self.coord_system.write(file)
		self.geo_cylinder.write(file)

	def size(self) -> int:
		return self.coord_system.size() + self.geo_cylinder.size()

@dataclass(eq=False, repr=False)
class CGeoSphere:
	radius: float = 0.0
	center: Vector3 = field(default_factory=Vector3)

	def read(self, file: BinaryIO) -> 'CGeoSphere':
		self.radius = unpack('f', file.read(calcsize('f')))[0]
		self.center = Vector3().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('f', self.radius))
		self.center.write(file)

	def size(self) -> int:
		return calcsize('f') + self.center.size()

@dataclass(eq=False, repr=False)
class SphereShape:
	coord_system: CMatCoordinateSystem = field(default_factory=CMatCoordinateSystem)
	geo_sphere: CGeoSphere = field(default_factory=CGeoSphere)

	def read(self, file: BinaryIO) -> 'SphereShape':
		self.coord_system = CMatCoordinateSystem().read(file)
		self.geo_sphere = CGeoSphere().read(file)
		return self

	def write(self, file: BinaryIO) -> None:
		self.coord_system.write(file)
		self.geo_sphere.write(file)

	def size(self) -> int:
		return self.coord_system.size() + self.geo_sphere.size()

@dataclass(eq=False, repr=False)
class CollisionShape:
	version: int = 1
	box_count: int = 0
	boxes: List[BoxShape] = field(default_factory=list)
	sphere_count: int = 0
	spheres: List[SphereShape] = field(default_factory=list)
	cylinder_count: int = 0
	cylinders: List[CylinderShape] = field(default_factory=list)

	def read(self, file: BinaryIO) -> 'CollisionShape':
		self.version = unpack('B', file.read(calcsize('B')))
		self.box_count = unpack('i', file.read(calcsize('i')))[0]
		self.boxes = [BoxShape().read(file) for _ in range(self.box_count)]
		self.sphere_count = unpack('i', file.read(calcsize('i')))[0]
		self.spheres = [SphereShape().read(file) for _ in range(self.sphere_count)]
		self.cylinder_count = unpack('i', file.read(calcsize('i')))[0]
		self.cylinders = [CylinderShape().read(file) for _ in range(self.cylinder_count)]
		return self

	def write(self, file: BinaryIO) -> None:
		file.write(pack('Bi', self.version, self.box_count))
		for box in self.boxes:
			box.write(file)
		file.write(pack('i', self.sphere_count))
		for sphere in self.spheres:
			sphere.write(file)
		file.write(pack('i', self.cylinder_count))
		for cylinder in self.cylinders:
			cylinder.write(file)

	def size(self) -> int:
		return (calcsize('Biii') + sum(box.size() for box in self.boxes) + sum(sphere.size() for sphere in self.spheres) + sum(cylinder.size() for cylinder in self.cylinders))

@dataclass(eq=False, repr=False)
class DrwResourceMeta:
	unknown: List[int] = field(default_factory=lambda: [0, 0])
	length: int = 0
	hash: str = ""

	def read(self, file: BinaryIO) -> 'DrwResourceMeta':
		"""Reads the DrwResourceMeta from the buffer"""
		self.unknown = list(unpack('2i', file.read(calcsize('2i'))))
		self.length = unpack('i', file.read(calcsize('i')))[0]
		self.hash = file.read(self.length).decode('utf-8').strip('\x00')
		return self

	def write(self, file: BinaryIO) -> None:
		"""Writes the DrwResourceMeta to the buffer"""
		file.write(pack(f'2ii{self.length}s', *self.unknown, self.length, self.hash.encode('utf-8')))

	def size(self) -> int:
		"""Returns the size of the DrwResourceMeta"""
		return calcsize(f'2ii{self.length}s')

@dataclass(eq=False, repr=False)
class CGeoPrimitiveContainer:
	"""CGeoPrimitiveContainer class"""

	def read(self, file: BinaryIO) -> 'CGeoPrimitiveContainer':
		"""Reads the CGeoPrimitiveContainer from the buffer"""
		# Add code here if you need to read specific data for this class
		return self

	def write(self, file: BinaryIO) -> 'CGeoPrimitiveContainer':
		"""Writes the CGeoPrimitiveContainer to the buffer"""
		pass

	def size(self) -> int:
		"""Returns the size of the CGeoPrimitiveContainer"""
		return 0

@dataclass(eq=False, repr=False)
class DRS:
	operator: object = None
	context: object = None
	keywords: object = None
	magic: int = -981667554
	number_of_models: int = 1
	node_information_offset: int = 41
	node_hierarchy_offset: int = 20
	data_offset: int = 73
	node_count: int = 1
	nodes: List[Node] = field(default_factory=lambda: [RootNode()])
	node_informations: List[Union[NodeInformation, RootNodeInformation]] = field(default_factory=lambda: [RootNodeInformation()])
	animation_set_node: Node = None
	cdsp_mesh_file_node: Node = None
	cgeo_mesh_node: Node = None
	csk_skin_info_node: Node = None
	csk_skeleton_node: Node = None
	animation_timings_node: Node = None
	joint_map_node: Node = None
	cgeo_obb_tree_node: Node = None
	drw_resource_meta_node: Node = None
	cgeo_primitive_container_node: Node = None
	collision_shape_node: Node = None
	effect_set_node: Node = None
	mesh_set_grid_node: Node = None
	cdrw_locator_list_node: Node = None
	# animation_set: AnimationSet = None
	cdsp_mesh_file: CDspMeshFile = None
	cgeo_mesh: CGeoMesh = None
	csk_skin_info: CSkSkinInfo = None
	csk_skeleton: CSkSkeleton = None
	joints: CDspJointMap = None
	cgeo_obb_tree: CGeoOBBTree = None
	drw_resource_meta: DrwResourceMeta = None
	cgeo_primitive_container: CGeoPrimitiveContainer = None
	collision_shape: CollisionShape = None
	# mesh_set_grid: MeshSetGrid = None

	def read(self, file_name: str) -> 'DRS':
		reader = FileReader(file_name)
		self.magic, self.number_of_models, self.node_information_offset, self.node_hierarchy_offset, self.node_count = unpack('iiiii', reader.read(calcsize('iiiii')))

		if self.magic != -981667554 or self.node_count < 1:
			raise TypeError(f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}")

		reader.seek(self.node_information_offset)
		self.node_informations[0] = RootNodeInformation().read(reader)

		node_information_map = {
			# -475734043: 'animation_set_node',
			-1900395636: 'cdsp_mesh_file_node',
			100449016: 'cgeo_mesh_node',
			-761174227: 'csk_skin_info_node',
			-2110567991: 'csk_skeleton_node',
			# -1403092629: 'animation_timings_node',
			-1340635850: 'joint_map_node',
			-933519637: 'cgeo_obb_tree_node',
			-183033339: 'drw_resource_meta_node',
			1396683476: 'cgeo_primitive_container_node',
			268607026: 'collision_shape_node',
			# 688490554: 'effect_set_node',
			# 154295579: 'mesh_set_grid_node',
			735146985: 'cdrw_locator_list_node'
		}

		for _ in range(self.node_count - 1):
			node_info = NodeInformation().read(reader)
			setattr(self, node_information_map.get(node_info.magic, ''), node_info)

		reader.seek(self.node_hierarchy_offset)
		self.nodes[0] = RootNode().read(reader)

		node_map = {
			# "AnimationSet": 'animation_set_node',
			"CDspMeshFile": 'cdsp_mesh_file_node',
			"CGeoMesh": 'cgeo_mesh_node',
			"CSkSkinInfo": 'csk_skin_info_node',
			"CSkSkeleton": 'csk_skeleton_node',
			# "AnimationTimings": 'animation_timings_node',
			"CDspJointMap": 'joint_map_node',
			"CGeoOBBTree": 'cgeo_obb_tree_node',
			"DrwResourceMeta": 'drw_resource_meta_node',
			"CGeoPrimitiveContainer": 'cgeo_primitive_container_node',
			"CollisionShape": 'collision_shape_node',
			# "EffectSet": 'effect_set_node',
			# "MeshSetGrid": 'mesh_set_grid_node',
			"CDrwLocatorList": 'cdrw_locator_list_node'
		}

		for _ in range(self.node_count - 1):
			node = Node().read(reader)
			setattr(self, node_map.get(node.name, ''), node)

		for key, value in node_map.items():
			# remove _node from the value
			node_info = getattr(self, value, None)
			index = value.replace('_node', '')
			if node_info is not None:
				reader.seek(node_info.offset)
				setattr(self, index, globals()[key]().read(reader))

		reader.close()
		return self

	def push_node(self, name: str, data_object):
		new_node = Node(self.node_count, name)
		self.nodes.append(new_node)
		self.node_information_offset += new_node.size()
		self.data_offset += new_node.size()
		self.node_informations[0].node_information_count += 1
		self.push_node_information(name, self.node_informations[0].node_information_count, data_object)
		self.node_count += 1

	def push_node_information(self, name: str, identifier: int, data_object):
		new_node_information = NodeInformation(name, identifier, data_object)
		self.node_informations.append(new_node_information)
		self.data_offset += new_node_information.size()

	def save(self, file_name: str):
		writer = FileWriter(file_name + "_new.drs")
		writer.write(pack('iiiii', self.magic, self.number_of_models, self.node_information_offset, self.node_hierarchy_offset, self.node_count))

		for node in self.nodes:
			node.write(writer)

		for node_info in self.node_informations:
			if node_info.data_object is None:
				node_info.write(writer)
				continue
			node_info.update_offset(self.data_offset)
			self.data_offset += node_info.node_size
			node_info.write(writer)

		for node_info in self.node_informations:
			if node_info.data_object is not None:
				node_info.data_object.write(writer)

		writer.close()

# class Constraint():
# 	"""Constraint"""
# 	def __init__(self) -> None:
# 		"""Constraint Constructor"""
# 		self.Revision: int
# 		self.LeftAngle: float
# 		self.RightAngle: float
# 		self.LeftDampStart: float
# 		self.RightDamStart: float
# 		self.DampRatio: float

# 	def read(self, file: BinaryIO) -> 'Constraint':
# 		"""Reads the Constraint from the buffer"""
# 		self.Revision = Buffer.ReadShort()
# 		if self.Revision == 1:
# 			self.LeftAngle = Buffer.ReadFloat()
# 			self.RightAngle = Buffer.ReadFloat()
# 			self.LeftDampStart = Buffer.ReadFloat()
# 			self.RightDamStart = Buffer.ReadFloat()
# 			self.DampRatio = Buffer.ReadFloat()
# 		return self

# 	def write(self, file: BinaryIO) -> 'Constraint':
# 		"""Writes the Constraint to the buffer"""
# 		Buffer.WriteShort(self.Revision)
# 		Buffer.WriteFloat(self.LeftAngle)
# 		Buffer.WriteFloat(self.RightAngle)
# 		Buffer.WriteFloat(self.LeftDampStart)
# 		Buffer.WriteFloat(self.RightDamStart)
# 		Buffer.WriteFloat(self.DampRatio)
# 		return self

# class IKAtlas():
# 	"""IKAtlas"""
# 	def __init__(self) -> None:
# 		"""IKAtlas Constructor"""
# 		self.Identifier: int
# 		self.Version: int
# 		self.Axis: int
# 		self.ChainOrder: int
# 		self.Constraints: List[Constraint]
# 		self.PurposeFlags: int

# 	def read(self, file: BinaryIO) -> 'IKAtlas':
# 		"""Reads the IKAtlas from the buffer"""
# 		self.Identifier = Buffer.ReadInt()
# 		self.Version = Buffer.ReadShort()
# 		if self.Version >= 1:
# 			self.Axis = Buffer.ReadInt()
# 			self.ChainOrder = Buffer.ReadInt()
# 			self.Constraints = [Constraint().Read(Buffer) for _ in range(3)]
# 			if self.Version >= 2:
# 				self.PurposeFlags = Buffer.ReadShort()
# 		return self

# 	def write(self, file: BinaryIO) -> 'IKAtlas':
# 		"""Writes the IKAtlas to the buffer"""
# 		Buffer.WriteInt(self.Identifier)
# 		Buffer.WriteShort(self.Version)
# 		Buffer.WriteInt(self.Axis)
# 		Buffer.WriteInt(self.ChainOrder)
# 		for _Constraint in self.Constraints:
# 			_Constraint.Write(Buffer)
# 		Buffer.WriteShort(self.PurposeFlags)
# 		return self


# class ModeAnimationKey():
# 	"""ModeAnimationKey"""
# 	def __init__(self, animation_file_name: str = "") -> None:
# 		"""ModeAnimationKey Constructor"""
# 		self.Type: int = 6 # TODO: Is this always 6?
# 		self.Length: int = 11
# 		self.File: str = "Battleforge"
# 		self.Unknown: int = 2 # TODO: Is this always 2?
# 		self.Unknown2: int = 3 # TODO: Is this always 3?
# 		self.VisJob: int = 0 # Short. 0 for Animated Objects else it can be used to link this animation key to an animation tag ID from the AnimationTimings
# 		self.Unknown3: int = 3 # TODO: Is this always 3?
# 		self.Unknown4: int = 0 # Short. TODO: Is this always 0?
# 		self.VariantCount: int = 1 # 1 for animated objects, units can have more variants per animation if needed.
# 		self.AnimationSetVariants: List[AnimationSetVariant] = []
# 		if animation_file_name != "":
# 			for _ in range(self.VariantCount):
# 				self.AnimationSetVariants.append(AnimationSetVariant(animation_file_name=animation_file_name))

# 	def Read(self, Buffer: FileReader, UK: int) -> 'ModeAnimationKey':
# 		"""Reads the ModeAnimationKey from the buffer"""
# 		if UK != 2:
# 			self.Type = Buffer.ReadInt()
# 		else:
# 			self.Type = 2
# 		self.Length = Buffer.ReadInt()
# 		self.File = Buffer.ReadString(self.Length)
# 		self.Unknown = Buffer.ReadInt()
# 		if self.Type == 1:
# 			self.Unknown2 = [Buffer.ReadByte() for _ in range(24)]
# 		elif self.Type <= 5:
# 			self.Unknown2 = [Buffer.ReadByte() for _ in range(6)]
# 		elif self.Type == 6:
# 			self.Unknown2 = Buffer.ReadInt()
# 			self.VisJob = Buffer.ReadShort()
# 			self.Unknown3 = Buffer.ReadInt()
# 			self.Unknown4 = Buffer.ReadShort()
# 		self.VariantCount = Buffer.ReadInt()
# 		self.AnimationSetVariants = [AnimationSetVariant().Read(Buffer) for _ in range(self.VariantCount)]
# 		return self

# 	def write(self, file: BinaryIO) -> 'ModeAnimationKey':
# 		"""Writes the ModeAnimationKey to the buffer"""
# 		Buffer.WriteInt(self.Type)
# 		Buffer.WriteInt(self.Length)
# 		Buffer.WriteString(self.File)
# 		Buffer.WriteInt(self.Unknown)
# 		Buffer.WriteInt(self.Unknown2)
# 		Buffer.WriteShort(self.VisJob)
# 		Buffer.WriteInt(self.Unknown3)
# 		Buffer.WriteShort(self.Unknown4)
# 		Buffer.WriteInt(self.VariantCount)
# 		for _AnimationSetVariant in self.AnimationSetVariants:
# 			_AnimationSetVariant.Write(Buffer)
# 		return self

# 	def Size(self) -> int:
# 		"""Returns the size of the ModeAnimationKey"""
# 		add = 0
# 		for Variant in self.AnimationSetVariants:
# 			add += Variant.Size()
# 		return 39 + add

# class AnimationMarker():
# 	"""AnimationMarker"""
# 	def __init__(self) -> None:
# 		"""AnimationMarker Constructor"""
# 		self.Class: int
# 		self.Time: float
# 		self.Direction: Vector
# 		self.Position: Vector

# 	def read(self, file: BinaryIO) -> 'AnimationMarker':
# 		"""Reads the AnimationMarker from the buffer"""
# 		self.Class = Buffer.ReadInt()
# 		self.Time = Buffer.ReadFloat()
# 		self.Direction = Buffer.ReadVector3()
# 		self.Position = Buffer.ReadVector3()
# 		return self

# 	def write(self, file: BinaryIO) -> 'AnimationMarker':
# 		"""Writes the AnimationMarker to the buffer"""
# 		Buffer.WriteInt(self.Class)
# 		Buffer.WriteFloat(self.Time)
# 		Buffer.WriteVector3(self.Direction)
# 		Buffer.WriteVector3(self.Position)
# 		return self

# class AnimationMarkerSet():
# 	"""AnimationMarkerSet"""
# 	def __init__(self) -> None:
# 		"""AnimationMarkerSet Constructor"""
# 		self.AnimID: int
# 		self.Length: int
# 		self.Name: str
# 		self.AnimationMarkerID: int
# 		self.MarkerCount: int
# 		self.AnimationMarkers: List[AnimationMarker]

# 	def read(self, file: BinaryIO) -> 'AnimationMarkerSet':
# 		"""Reads the AnimationMarkerSet from the buffer"""
# 		self.AnimID = Buffer.ReadInt()
# 		self.Length = Buffer.ReadInt()
# 		self.Name = Buffer.ReadString(self.Length)
# 		self.AnimationMarkerID = Buffer.ReadInt()
# 		self.MarkerCount = Buffer.ReadInt()
# 		self.AnimationMarkers = [AnimationMarker().Read(Buffer) for _ in range(self.MarkerCount)]
# 		return self

# 	def write(self, file: BinaryIO) -> 'AnimationMarkerSet':
# 		"""Writes the AnimationMarkerSet to the buffer"""
# 		Buffer.WriteInt(self.AnimID)
# 		Buffer.WriteInt(self.Length)
# 		Buffer.WriteString(self.Name)
# 		Buffer.WriteInt(self.AnimationMarkerID)
# 		Buffer.WriteInt(self.MarkerCount)
# 		for _AnimationMarker in self.AnimationMarkers:
# 			_AnimationMarker.Write(Buffer)
# 		return self

# class AnimationSet():
# 	"""AnimationSet"""
# 	def __init__(self, animation_file_name: str = "") -> None:
# 		"""AnimationSet Constructor"""
# 		self.Length: int = 11
# 		self.Magic: str = "Battleforge"
# 		self.Version: int = 6
# 		# Is used by the game to determine the animation speed when walking/running
# 		self.DefaultRunSpeed: float = 4.8 # TODO: Add a way to show/edit this value in Blender
# 		self.DefaultWalkSpeed: float = 2.4 # TODO: Add a way to show/edit this value in Blender
# 		self.Revision: int = 6 # TODO: Is it all the time?
# 		self.ModeAnimationKeyCount: int = 1 # How many different animations are there?
# 		# TODO find out how often these values are used and for which object/unit/building types
# 		self.ModeChangeType: int = 0
# 		self.HoveringGround: int = 0
# 		self.FlyBankScale: float = 1 # Changes for flying units
# 		self.FlyAccelScale: float = 0 # Changes for flying units
# 		self.FlyHitScale: float = 1 # Changes for flying units
# 		self.AllignToTerrain: int = 0
# 		# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# 		self.ModeAnimationKeys: List[ModeAnimationKey] = []
# 		if animation_file_name != "": # So we can still import original drs files
# 			# Assure the name end with '.ska'
# 			if not animation_file_name.endswith(".ska"):
# 				animation_file_name += ".ska"
# 			for _ in range(self.ModeAnimationKeyCount):
# 				self.ModeAnimationKeys.append(ModeAnimationKey(animation_file_name))
# 		self.HasAtlas: int = 1 # 1 or 2
# 		self.AtlasCount: int = 0 # Animated Objects: 0
# 		self.IKAtlases: List[IKAtlas] = []
# 		self.UKLen: int = 0 # TODO: Always 0?
# 		self.UKInts: List[int] = []
# 		self.Subversion: int = 2 # TODO: Always 2?
# 		self.AnimationMarkerCount: int = 0 # Animated Objects: 0
# 		self.AnimationMarkerSets: List[AnimationMarkerSet] = []
# 		self.Unknown: int # Not needed
# 		self.UnknownStructs: List[UnknownStruct] # Not needed

# 	def read(self, file: BinaryIO) -> 'AnimationSet':
# 		"""Reads the AnimationSet from the buffer"""
# 		self.Length = Buffer.ReadInt()
# 		self.Magic = Buffer.ReadString(self.Length)
# 		self.Version = Buffer.ReadInt()
# 		self.DefaultRunSpeed = Buffer.ReadFloat()
# 		self.DefaultWalkSpeed = Buffer.ReadFloat()

# 		if self.Version == 2:
# 			self.ModeAnimationKeyCount = Buffer.ReadInt()
# 		else:
# 			self.Revision = Buffer.ReadInt()

# 		if self.Version >= 6:
# 			if self.Revision >= 2:
# 				self.ModeChangeType = Buffer.ReadByte()
# 				self.HoveringGround = Buffer.ReadByte()

# 			if self.Revision >= 5:
# 				self.FlyBankScale = Buffer.ReadFloat()
# 				self.FlyAccelScale = Buffer.ReadFloat()
# 				self.FlyHitScale = Buffer.ReadFloat()

# 			if self.Revision >= 6:
# 				self.AllignToTerrain = Buffer.ReadByte()

# 		UK:int = 0

# 		if self.Version == 2:
# 			UK = Buffer.ReadInt()
# 		else:
# 			self.ModeAnimationKeyCount = Buffer.ReadInt()

# 		self.ModeAnimationKeys = [ModeAnimationKey().Read(Buffer, UK) for _ in range(self.ModeAnimationKeyCount)]

# 		if self.Version >= 3:
# 			self.HasAtlas = Buffer.ReadShort()

# 			if self.HasAtlas >= 1:
# 				self.AtlasCount = Buffer.ReadInt()
# 				self.IKAtlases = [IKAtlas().Read(Buffer) for _ in range(self.AtlasCount)]

# 			if self.HasAtlas >= 2:
# 				self.UKLen = Buffer.ReadInt()
# 				self.UKInts = [Buffer.ReadInt() for _ in range(self.UKLen * 3)]

# 		if self.Version >= 4:
# 			self.Subversion = Buffer.ReadShort()

# 			if self.Subversion == 2:
# 				self.AnimationMarkerCount = Buffer.ReadInt()
# 				self.AnimationMarkerSets = [AnimationMarkerSet().Read(Buffer) for _ in range(self.AnimationMarkerCount)]
# 			elif self.Subversion == 1:
# 				self.Unknown = Buffer.ReadInt()
# 				self.UnknownStructs = [UnknownStruct().Read(Buffer) for _ in range(self.Unknown)]

# 		return self

# 	def write(self, file: BinaryIO) -> 'AnimationSet':
# 		"""Writes the AnimationSet to the buffer"""
# 		Buffer.WriteInt(self.Length)
# 		Buffer.WriteString(self.Magic)
# 		Buffer.WriteInt(self.Version)
# 		Buffer.WriteFloat(self.DefaultRunSpeed)
# 		Buffer.WriteFloat(self.DefaultWalkSpeed)

# 		if self.Version == 2:
# 			Buffer.WriteInt(self.ModeAnimationKeyCount)
# 		else:
# 			Buffer.WriteInt(self.Revision)

# 		if self.Version >= 6:
# 			if self.Revision >= 2:
# 				Buffer.WriteByte(self.ModeChangeType)
# 				Buffer.WriteByte(self.HoveringGround)

# 			if self.Revision >= 5:
# 				Buffer.WriteFloat(self.FlyBankScale)
# 				Buffer.WriteFloat(self.FlyAccelScale)
# 				Buffer.WriteFloat(self.FlyHitScale)

# 			if self.Revision >= 6:
# 				Buffer.WriteByte(self.AllignToTerrain)

# 		if self.Version == 2:
# 			Buffer.WriteInt(0)
# 		else:
# 			Buffer.WriteInt(self.ModeAnimationKeyCount)

# 		for _ModeAnimationKey in self.ModeAnimationKeys:
# 			_ModeAnimationKey.Write(Buffer)

# 		if self.Version >= 3:
# 			Buffer.WriteShort(self.HasAtlas)

# 			if self.HasAtlas >= 1:
# 				Buffer.WriteInt(self.AtlasCount)
# 				for _IKAtlas in self.IKAtlases:
# 					_IKAtlas.Write(Buffer)

# 			if self.HasAtlas >= 2:
# 				Buffer.WriteInt(self.UKLen)
# 				for UKInt in self.UKInts:
# 					Buffer.WriteInt(UKInt)

# 		if self.Version >= 4:
# 			Buffer.WriteShort(self.Subversion)

# 			if self.Subversion == 2:
# 				Buffer.WriteInt(self.AnimationMarkerCount)
# 				for _AnimationMarkerSet in self.AnimationMarkerSets:
# 					_AnimationMarkerSet.Write(Buffer)
# 			elif self.Subversion == 1:
# 				Buffer.WriteInt(self.Unknown)
# 				for _UnknownStruct in self.UnknownStructs:
# 					_UnknownStruct.Write(Buffer)

# 		return self

# 	def Size(self) -> int:
# 		"""Returns the size of the AnimationSet"""
# 		add = 0
# 		for Key in self.ModeAnimationKeys:
# 			add += Key.Size()
# 		return 62 + add

# class AnimationSetVariant():
# 	"""AnimationSetVariant"""
# 	def __init__(self, weight: int = 100, animation_file_name: str = "") -> None:
# 		"""AnimationSetVariant Constructor"""
# 		self.Version: int = 7 # 6 or 7
# 		self.Weight: int = weight # Maximum 100 in sum for all Variants
# 		self.Length: int = len(animation_file_name)
# 		self.File: str = animation_file_name
# 		self.Start: float = 0 # TODO: Sometimes it isnt 0, why?
# 		self.End: float = 1 # TODO: always 1?
# 		self.AllowsIK: int = 1 # TODO: Most of the time 1?
# 		self.Unknown2: int = 0 # TODO: Most of the time 0?

# 	def read(self, file: BinaryIO) -> 'AnimationSetVariant':
# 		"""Reads the AnimationSetVariant from the buffer"""
# 		self.Version = Buffer.ReadInt()
# 		self.Weight = Buffer.ReadInt()
# 		self.Length = Buffer.ReadInt()
# 		self.File = Buffer.ReadString(self.Length)

# 		if self.Version >= 4:
# 			self.Start = Buffer.ReadFloat()
# 			self.End = Buffer.ReadFloat()

# 		if self.Version >= 5:
# 			self.AllowsIK = Buffer.ReadByte()

# 		if self.Version >= 7:
# 			self.Unknown2 = Buffer.ReadByte()

# 		return self

# 	def write(self, file: BinaryIO) -> 'AnimationSetVariant':
# 		"""Writes the AnimationSetVariant to the buffer"""
# 		Buffer.WriteInt(self.Version)
# 		Buffer.WriteInt(self.Weight)
# 		Buffer.WriteInt(self.Length)
# 		Buffer.WriteString(self.File)
# 		Buffer.WriteFloat(self.Start)
# 		Buffer.WriteFloat(self.End)
# 		Buffer.WriteByte(self.AllowsIK)
# 		Buffer.WriteByte(self.Unknown2)
# 		return self

# 	def Size(self) -> int:
# 		"""Returns the size of the AnimationSetVariant"""
# 		return 21 + self.Length

# class SMeshState():
# 	"""SMeshState"""
# 	def __init__(self) -> None:
# 		"""SMeshState Constructor"""
# 		self.StateNum: int
# 		self.HasFiles: int
# 		self.UKFileLength: int
# 		self.UKFile: str
# 		self.DRSFileLength: int
# 		self.DRSFile: str

# 	def read(self, file: BinaryIO) -> 'SMeshState':
# 		"""Reads the SMeshState from the buffer"""
# 		self.StateNum = Buffer.ReadInt()
# 		self.HasFiles = Buffer.ReadShort()
# 		if self.HasFiles == 1:
# 			self.UKFileLength = Buffer.ReadInt()
# 			self.UKFile = Buffer.ReadString(self.UKFileLength)
# 			self.DRSFileLength = Buffer.ReadInt()
# 			self.DRSFile = Buffer.ReadString(self.DRSFileLength)
# 		return self

# 	def write(self, file: BinaryIO) -> 'SMeshState':
# 		"""Writes the SMeshState to the buffer"""
# 		Buffer.WriteInt(self.StateNum)
# 		Buffer.WriteShort(self.HasFiles)
# 		if self.HasFiles == 1:
# 			Buffer.WriteInt(self.UKFileLength)
# 			Buffer.WriteString(self.UKFile)
# 			Buffer.WriteInt(self.DRSFileLength)
# 			Buffer.WriteString(self.DRSFile)
# 		return self

# class DestructionState():
# 	"""DestructionState"""
# 	def __init__(self) -> None:
# 		"""DestructionState Constructor"""
# 		self.StateNum: int
# 		self.FileNameLength: int
# 		self.FileName: str

# 	def read(self, file: BinaryIO) -> 'DestructionState':
# 		"""Reads the DestructionState from the buffer"""
# 		self.StateNum = Buffer.ReadInt()
# 		self.FileNameLength = Buffer.ReadInt()
# 		self.FileName = Buffer.ReadString(self.FileNameLength)
# 		return self

# 	def write(self, file: BinaryIO) -> 'DestructionState':
# 		"""Writes the DestructionState to the buffer"""
# 		Buffer.WriteInt(self.StateNum)
# 		Buffer.WriteInt(self.FileNameLength)
# 		Buffer.WriteString(self.FileName)
# 		return self

# class StateBasedMeshSet():
# 	"""StateBasedMeshSet"""
# 	def __init__(self) -> None:
# 		"""StateBasedMeshSet Constructor"""
# 		self.UKShort: int
# 		self.UKInt: int
# 		self.NumMeshStates: int
# 		self.SMeshStates: List[SMeshState]
# 		self.NumDestructionStates: int
# 		self.DestructionStates: List[DestructionState]

# 	def read(self, file: BinaryIO) -> 'StateBasedMeshSet':
# 		"""Reads the StateBasedMeshSet from the buffer"""
# 		self.UKShort = Buffer.ReadShort()
# 		self.UKInt = Buffer.ReadInt()
# 		self.NumMeshStates = Buffer.ReadInt()
# 		self.SMeshStates = [SMeshState().Read(Buffer) for _ in range(self.NumMeshStates)]
# 		self.NumDestructionStates = Buffer.ReadInt()
# 		self.DestructionStates = [DestructionState().Read(Buffer) for _ in range(self.NumDestructionStates)]
# 		return self

# 	def write(self, file: BinaryIO) -> 'StateBasedMeshSet':
# 		"""Writes the StateBasedMeshSet to the buffer"""
# 		Buffer.WriteShort(self.UKShort)
# 		Buffer.WriteInt(self.UKInt)
# 		Buffer.WriteInt(self.NumMeshStates)
# 		for MeshState in self.SMeshStates:
# 			MeshState.Write(Buffer)
# 		Buffer.WriteInt(self.NumDestructionStates)
# 		for _DestructionState in self.DestructionStates:
# 			_DestructionState.Write(Buffer)
# 		return self

# class MeshGridModule():
# 	"""MeshGridModule"""
# 	def __init__(self) -> None:
# 		"""MeshGridModule Constructor"""
# 		self.UKShort: int
# 		self.HasMeshSet: int
# 		self.StateBasedMeshSet: StateBasedMeshSet

# 	def read(self, file: BinaryIO) -> 'MeshGridModule':
# 		"""Reads the MeshGridModule from the buffer"""
# 		self.UKShort = Buffer.ReadShort()
# 		self.HasMeshSet = Buffer.ReadByte()
# 		if self.HasMeshSet == 1:
# 			self.StateBasedMeshSet = StateBasedMeshSet().Read(Buffer)
# 		return self

# 	def write(self, file: BinaryIO) -> 'MeshGridModule':
# 		"""Writes the MeshGridModule to the buffer"""
# 		Buffer.WriteShort(self.UKShort)
# 		Buffer.WriteByte(self.HasMeshSet)
# 		if self.HasMeshSet == 1:
# 			self.StateBasedMeshSet.Write(Buffer)
# 		return self

# class Timing():
# 	'''Timing'''
# 	def __init__(self) -> None:
# 		'''Timing Constructor'''
# 		self.CastMs: int # Int
# 		self.ResolveMs: int # Int
# 		self.UK1: float # Float
# 		self.UK2: float # Float
# 		self.UK3: float # Float
# 		self.AnimationMarkerID: int # Int
# 		# NOTICE:
# 		# When tying the visual animation to the game logic,
# 		# the castMs/resolveMs seem to get converted into game ticks by simply dividing them by 100.
# 		# So while the visual part of the animation is handled in milliseconds,
# 		# the maximum precision for the game logic is in deciseconds/game ticks.
# 		#
# 		# Meaning of the variables below:
# 		# For type Spawn:
# 		# castMs is the duration it will take until the unit can be issued commands or lose damage immunity
# 		# If castMs is for zero game ticks (< 100), then the animation is skipped entirely.
# 		# If castMs is for exactly one game tick (100-199), it seems to bug out.
# 		# Therefore the minimum value here should be 200, if you wish to play a spawn animation.
# 		# resolveMs is the duration the spawn animation will play out for in total.
# 		# This should match the total time from the .ska file, otherwise it looks weird.
# 		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
# 		#
# 		# For type CastResolve:
# 		# castMs is the duration it will take the unit to start casting its ability (can still be aborted)
# 		# If castMs is for zero game ticks (< 100), then the ability skips the cast stage
# 		# and instantly moves onto the resolve stage.
# 		# resolveMs is the duration it will take the unit to finish casting its ability (cannot be aborted)
# 		# It seems the stage cannot be skipped and uses a minimum duration of 1 game tick,
# 		# even if a value < 100 is specified.
# 		# The animation is automatically slowed down/sped up based on these timings.
# 		# The total time from the .ska file is ignored.
# 		#
# 		# For type ModeSwitch:
# 		# castMs is the duration it will take the unit to start its mode switch animation.
# 		# If castMs is for zero game ticks (< 100), then the mode switch is done instantly
# 		# and also does not interrupt movement. During castMs, any commands are blocked.
# 		# resolveMs seems to be ignored here. The unit can be issued new commands after the cast time.
# 		# If you wish to slow down/speed up the animation, you can change the total time in the .ska file.
# 		#
# 		# For type Melee/WormMovement No experiments conducted yet.
# 		#  castMs;
# 		#  resolveMs;
# 		# at uk1;
# 		# at uk2;
# 		#
# 		# Can be used to link an AnimationMarkerSet to a timing.
# 		# Relevant field: AnimationMarkerSet.animationMarkerID
# 		#
# 		# Seems to be often used for Spawn animations.
# 		# In cases where e.g. the animationTagID is used,
# 		# the animationMarkerID usually not referenced anywhere.

# class TimingVariant():
# 	'''TimingVariant'''
# 	def __init__(self) -> None:
# 		'''TimingVariant Constructor'''
# 		self.Weight: int # Byte. The weight of this variant. The higher the weight, the more likely it is to be chosen.
# 		self.VariantIndex: int # Byte.
# 		self.TimingCount: int # Short. The number of Timings for this Variant. Most of the time, this is 1.
# 		self.Timings: List[Timing]

# class AnimationTiming():
# 	'''AnimationTiming'''
# 	def __init__(self) -> None:
# 		'''AnimationTiming Constructor'''
# 		self.AnimationType: int = AnimationType['CastResolve']
# 		self.AnimationTagID: int = 0
# 		self.IsEnterModeAnimation: int = 0 # Short. This is 1 most of the time.
# 		self.VariantCount: int # Short. The number of Animations for this Type/TagID combination.
# 		self.TimingVariants: List[TimingVariant]

# class StructV3():
# 	'''StructV3'''
# 	def __init__(self) -> None:
# 		'''StructV3 Constructor'''
# 		self.Length: int = 1
# 		self.Unknown: List[int] = [0, 0]

# 	def write(self, file: BinaryIO) -> 'StructV3':
# 		'''Writes the StructV3 to the buffer'''
# 		Buffer.WriteInt(self.Length)
# 		for Unknown in self.Unknown:
# 			Buffer.WriteInt(Unknown)
# 		return self

# 	def Size(self) -> int:
# 		'''Returns the size of the StructV3'''
# 		return 12

# class AnimationTimings():
# 	"""AnimationTimings"""
# 	def __init__(self):
# 		"""AnimationTimings Constructor"""
# 		self.Magic: int = 1650881127
# 		self.Version: int = 4 # Short. 3 or 4
# 		self.AnimationTimingCount: int = 0 # Short. Only used if there are multiple Animations.
# 		self.AnimationTimings: List[AnimationTiming]
# 		self.StructV3: StructV3 = StructV3()

# 	def write(self, file: BinaryIO) -> 'AnimationTimings':
# 		"""Writes the AnimationTimings to the buffer"""
# 		Buffer.WriteInt(self.Magic)
# 		Buffer.WriteShort(self.Version)
# 		Buffer.WriteShort(self.AnimationTimingCount)
# 		if self.AnimationTimingCount > 0:
# 			# TODO
# 			pass
# 		self.StructV3.Write(Buffer)
# 		return self

# 	def Size(self) -> int:
# 		"""Returns the size of the AnimationTimings"""
# 		return 8 + self.StructV3.Size()

# class MeshSetGrid():
# 	"""MeshSetGrid class"""
# 	def __init__(self) -> None:
# 		self.Revision: int
# 		self.GridWidth: int
# 		self.GridHeight: int
# 		self.NameLength: int
# 		self.Name: str
# 		self.UUIDLength: int
# 		self.UUID: str
# 		self.GridRotation: int
# 		self.GroundDecalLength: int
# 		self.GroundDecal: str
# 		self.UKString0Length: int
# 		self.UKString0: str
# 		self.UKString1Length: int
# 		self.UKString1: str
# 		self.ModuleDistance: float
# 		self.IsCenterPivoted: int
# 		self.MeshModules: List[MeshGridModule]

# 	def read(self, file: BinaryIO) -> 'MeshSetGrid':
# 		"""Reads the MeshSetGrid from the buffer"""
# 		self.Revision = Buffer.ReadShort()
# 		self.GridWidth = Buffer.ReadByte()
# 		self.GridHeight = Buffer.ReadByte()
# 		self.NameLength = Buffer.ReadInt()
# 		self.Name = Buffer.ReadString(self.NameLength)
# 		self.UUIDLength = Buffer.ReadInt()
# 		self.UUID = Buffer.ReadString(self.UUIDLength)
# 		self.GridRotation = Buffer.ReadShort()
# 		self.GroundDecalLength = Buffer.ReadInt()
# 		self.GroundDecal = Buffer.ReadString(self.GroundDecalLength)
# 		self.UKString0Length = Buffer.ReadInt()
# 		self.UKString0 = Buffer.ReadString(self.UKString0Length)
# 		self.UKString1Length = Buffer.ReadInt()
# 		self.UKString1 = Buffer.ReadString(self.UKString1Length)
# 		self.ModuleDistance = Buffer.ReadFloat()
# 		self.IsCenterPivoted = Buffer.ReadByte()
# 		self.MeshModules = [MeshGridModule().Read(Buffer) for _ in range((self.GridWidth * 2 + 1) * (self.GridHeight * 2 + 1))]
# 		return self

# 	def write(self, file: BinaryIO) -> 'MeshSetGrid':
# 		"""Writes the MeshSetGrid to the buffer"""
# 		Buffer.WriteShort(self.Revision)
# 		Buffer.WriteByte(self.GridWidth)
# 		Buffer.WriteByte(self.GridHeight)
# 		Buffer.WriteInt(self.NameLength)
# 		Buffer.WriteString(self.Name)
# 		Buffer.WriteInt(self.UUIDLength)
# 		Buffer.WriteString(self.UUID)
# 		Buffer.WriteShort(self.GridRotation)
# 		Buffer.WriteInt(self.GroundDecalLength)
# 		Buffer.WriteString(self.GroundDecal)
# 		Buffer.WriteInt(self.UKString0Length)
# 		Buffer.WriteString(self.UKString0)
# 		Buffer.WriteInt(self.UKString1Length)
# 		Buffer.WriteString(self.UKString1)
# 		Buffer.WriteFloat(self.ModuleDistance)
# 		Buffer.WriteByte(self.IsCenterPivoted)
# 		for MeshModule in self.MeshModules: MeshModule.Write(Buffer)
# 		return self

# AnimationType = {
# 	"CastResolve": 0,
# 	"Spawn": 1,
# 	"Melee": 2,
# 	"Channel": 3,
# 	"ModeSwitch": 4,
# 	"WormMovement": 5,
# }

# class UnknownStruct():
# 	"""UnknownStruct"""
# 	def __init__(self) -> None:
# 		"""UnknownStruct Constructor"""
# 		self.Unknown: int
# 		self.Length: int
# 		self.Name: str
# 		self.Unknown2: int
# 		self.Unknown3: int
# 		self.UnknownStructs: List[UnknownStruct2]

# 	def read(self, file: BinaryIO) -> 'UnknownStruct':
# 		"""Reads the UnknownStruct from the buffer"""
# 		self.Unknown = Buffer.ReadInt()
# 		self.Length = Buffer.ReadInt()
# 		self.Name = Buffer.ReadString(self.Length)
# 		self.Unknown2 = Buffer.ReadInt()
# 		self.Unknown3 = Buffer.ReadInt()
# 		self.UnknownStructs = [UnknownStruct2().Read(Buffer) for _ in range(self.Unknown3)]
# 		return self

# 	def write(self, file: BinaryIO) -> 'UnknownStruct':
# 		"""Writes the UnknownStruct to the buffer"""
# 		Buffer.WriteInt(self.Unknown)
# 		Buffer.WriteInt(self.Length)
# 		Buffer.WriteString(self.Name)
# 		Buffer.WriteInt(self.Unknown2)
# 		Buffer.WriteInt(self.Unknown3)
# 		for _UnknownStruct2 in self.UnknownStructs:
# 			_UnknownStruct2.Write(Buffer)
# 		return self

# class UnknownStruct2():
# 	"""UnknownStruct2"""
# 	def __init__(self) -> None:
# 		"""UnknownStruct2 Constructor"""
# 		self.UnknownInts: List[int]

# 	def read(self, file: BinaryIO) -> 'UnknownStruct2':
# 		"""Reads the UnknownStruct2 from the buffer"""
# 		self.UnknownInts = [Buffer.ReadInt() for _ in range(5)]
# 		return self

# 	def write(self, file: BinaryIO) -> 'UnknownStruct2':
# 		"""Writes the UnknownStruct2 to the buffer"""
# 		for UnknownInt in self.UnknownInts:
# 			Buffer.WriteInt(UnknownInt)
# 		return self
