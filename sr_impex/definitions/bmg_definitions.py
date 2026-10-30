"""
BMG (Building Mesh Grid) File Format Definitions

This module contains data structure definitions for BMG files,
which define building layouts with modular grids and state-based meshes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from struct import pack, unpack

from sr_impex.definitions.base_types import (
    BaseContainer,
    Node,
    NodeInformation,
    RootNode,
    RootNodeInformation,
)
from sr_impex.definitions.animation_definitions import AnimationSet, AnimationTimings
from sr_impex.definitions.collision_definitions import CollisionShape
from sr_impex.definitions.effect_definitions import EffectSet
from sr_impex.definitions.resource_definitions import CGeoPrimitiveContainer
from sr_impex.definitions.grid_definitions import (
    SMeshState,
    DestructionState,
    StateTransition,
    StateBasedMeshSet,
    MeshGridModule,
    MeshSetGrid,
)
from sr_impex.definitions.enums import WriteOrder, InformationIndices

# Re-export grid classes for backward compatibility
__all__ = [
    'SMeshState', 'DestructionState', 'StateTransition', 'StateBasedMeshSet',
    'MeshGridModule', 'MeshSetGrid', 'BMG', 'BMS',
]


@dataclass(eq=False, repr=False)
class BMG(BaseContainer):
    """BMG (Building Mesh Grid) file format for buildings with modular grids"""
    animation_set_node: NodeInformation = None
    animation_timings_node: NodeInformation = None
    cgeo_primitive_container_node: NodeInformation = None
    collision_shape_node: NodeInformation = None
    effect_set_node: NodeInformation = None
    animation_set: AnimationSet = None
    mesh_set_grid_node: NodeInformation = None
    cgeo_primitive_container: CGeoPrimitiveContainer = None
    collision_shape: CollisionShape = None
    effect_set: EffectSet = None
    animation_timings: AnimationTimings = None
    mesh_set_grid: MeshSetGrid = None

    def __post_init__(self):
        self.nodes = [RootNode()]
        if self.model_type is not None:
            model_struct = InformationIndices[self.model_type]
            # Prefill the node_informations with the RootNodeInformation and empty NodeInformations
            self.node_informations = [
                RootNodeInformation(node_information_count=len(model_struct))
            ]
            self.node_count = len(model_struct) + 1
            for _ in range(len(model_struct)):
                self.node_informations.append(NodeInformation())

            for index, (node_name, info_index) in enumerate(model_struct.items()):
                node = Node(info_index, node_name)
                self.nodes.append(node)
                node_info = NodeInformation(identifier=index + 1, node_name=node_name)
                # Fix for missing node_size as size is 0 and not Note for CGeoPrimitiveContainer
                if node_name == "CGeoPrimitiveContainer":
                    node_info.node_size = 0
                self.node_informations[info_index] = node_info

    _payload_types = {
        "MeshSetGrid": ("mesh_set_grid", MeshSetGrid),
        "AnimationSet": ("animation_set", AnimationSet),
        "AnimationTimings": ("animation_timings", AnimationTimings),
        "EffectSet": ("effect_set", EffectSet),
        "CGeoPrimitiveContainer": ("cgeo_primitive_container", CGeoPrimitiveContainer),
        "collisionShape": ("collision_shape", CollisionShape),
    }

    def push_node_infos(self, class_name: str, data_object: object):
        info = next((item for item in self.node_informations if item.node_name == class_name), None)
        if info is None:
            raise ValueError(f"BMG has no {class_name} node")
        info.data_object = data_object
        info.node_size = data_object.size()
        if class_name in self._payload_types:
            setattr(self, self._payload_types[class_name][0], data_object)

    def update_offsets(self):
        """Compatibility hook; serialization always calculates offsets from scratch."""
        self.to_bytes()

    def read(self, file_name: str) -> "BMG":
        return self.read_bytes(Path(file_name).read_bytes())

    def read_bytes(self, source: bytes) -> "BMG":
        """Load an embedded Blender snapshot without creating a temporary game file."""
        source = bytes(source)
        reader = BytesIO(source)
        (self.magic, self.number_of_models, self.node_information_offset,
         self.node_hierarchy_offset, self.node_count) = unpack("<i4I", reader.read(20))
        table, hierarchy = self.node_information_offset, self.node_hierarchy_offset
        if (self.magic != -981667554 or self.node_count < 1 or table < 20
                or table + 32 * self.node_count > len(source) or not 20 <= hierarchy < len(source)):
            raise ValueError("Invalid BMG container header")
        reader.seek(table)
        self.node_informations = [RootNodeInformation().read(reader)]
        self.node_informations.extend(NodeInformation().read(reader) for _ in range(self.node_count - 1))
        reader.seek(hierarchy)
        self.nodes = [RootNode().read(reader)]
        self.nodes.extend(Node().read(reader) for _ in range(self.node_count - 1))
        self._hierarchy_end = reader.tell()
        if self._hierarchy_end > len(source):
            raise ValueError("Truncated BMG hierarchy")
        for attribute, _ in self._payload_types.values():
            setattr(self, attribute, None)
            setattr(self, attribute + "_node", None)
        for node in self.nodes[1:]:
            if not 0 < node.info_index < self.node_count:
                raise ValueError("BMG hierarchy references an invalid node-info index")
            info = self.node_informations[node.info_index]
            info.node_name = node.name
        self._source_spans = {}
        for index, info in enumerate(self.node_informations[1:], 1):
            if info.node_size < 0 or (info.node_size and
                    (info.offset < 20 or info.offset + info.node_size > len(source))):
                raise ValueError("BMG payload is outside the file")
            self._source_spans[index] = (info.offset, info.node_size)
            definition = self._payload_types.get(info.node_name)
            if definition is None:
                continue  # Unknown node payload and metadata remain in the original container.
            attribute, factory = definition
            setattr(self, attribute + "_node", info)
            if not info.node_size:  # Primitive container is a zero-byte hierarchy parent.
                continue
            stream = BytesIO(source[info.offset:info.offset + info.node_size])
            value = factory().read(stream)
            if stream.tell() != info.node_size:
                raise ValueError(f"Unparsed bytes in BMG {info.node_name}")
            info.data_object = value
            setattr(self, attribute, value)
        if self.mesh_set_grid is None:
            raise ValueError("BMG has no MeshSetGrid")
        self._source_bytes = source
        return self

    def _payload(self, info) -> bytes:
        if info.node_name == "CGeoPrimitiveContainer" and info.node_size == 0:
            return b""
        definition = self._payload_types.get(info.node_name)
        value = getattr(self, definition[0], None) if definition else None
        if value is None:
            value = getattr(info, "data_object", None)
        if value is None:
            raise ValueError(f"Missing BMG payload: {info.node_name}")
        stream = BytesIO()
        value.write(stream)
        return stream.getvalue()

    def to_bytes(self) -> bytes:
        """Write loaded edits without discarding unknown nodes, links or padding."""
        source = getattr(self, "_source_bytes", None)
        if source is not None:
            changes = []
            for index, (start, length) in self._source_spans.items():
                info = self.node_informations[index]
                if not length or info.node_name not in self._payload_types:
                    continue
                payload = self._payload(info)
                if payload != source[start:start + length]:
                    changes.append((start, start + length, index, payload))
            if not changes:
                return source
            changes.sort()
            table, hierarchy = unpack("<2I", source[8:16])
            metadata = ((0, 20), (table, table + self.node_count * 32),
                        (hierarchy, self._hierarchy_end))
            for start, end, index, _ in changes:
                if any(start < hi and end > lo for lo, hi in metadata):
                    raise ValueError("BMG payload overlaps container metadata")
                for other, (offset, length) in self._source_spans.items():
                    if other != index and length and start < offset + length and end > offset:
                        raise ValueError("BMG node payloads overlap")
            def relocate(offset):
                return offset + sum(len(payload) - (end - start)
                    for start, end, _, payload in changes if end <= offset)
            result = bytearray()
            cursor = 0
            for start, end, _, payload in changes:
                result.extend(source[cursor:start]); result.extend(payload); cursor = end
            result.extend(source[cursor:])
            new_table = relocate(table)
            result[8:16] = pack("<2I", new_table, relocate(hierarchy))
            sizes = {index: len(payload) for _, _, index, payload in changes}
            for index, (start, length) in self._source_spans.items():
                at = new_table + index * 32
                result[at + 8:at + 16] = pack("<2I", relocate(start), sizes.get(index, length))
            return bytes(result)

        if self.model_type not in WriteOrder:
            raise ValueError("New BMG needs a building model_type")
        payloads = []
        cursor = 20
        for name in WriteOrder[self.model_type]:
            info = next((item for item in self.node_informations if item.node_name == name), None)
            if info is None:
                raise ValueError(f"Missing BMG node: {name}")
            payload = self._payload(info)
            info.offset, info.node_size = cursor, len(payload)
            cursor += len(payload)
            payloads.append(payload)
        self.link_collision_primitive_child()
        self.node_count = len(self.node_informations)
        self.node_information_offset = cursor
        self.node_hierarchy_offset = cursor + 32 * self.node_count
        self.data_offset = cursor
        stream = BytesIO()
        stream.write(pack("<i4I", self.magic, self.number_of_models, cursor,
                          self.node_hierarchy_offset, self.node_count))
        for payload in payloads:
            stream.write(payload)
        for info in self.node_informations:
            info.write(stream)
        for node in self.nodes:
            node.write(stream)
        return stream.getvalue()

    def save(self, file_name: str):
        # Validate and serialize before opening the destination.
        Path(file_name).write_bytes(self.to_bytes())


@dataclass(eq=False, repr=False)
class BMS(BaseContainer):
    """Chunk container for CDrwStateBasedMeshSet (also used outside construction)."""
    node_information_offset: int = -1
    node_hierarchy_offset: int = -1
    root_node: RootNode = field(default_factory=RootNode)
    state_based_mesh_set_node: NodeInformation = None
    state_based_mesh_set: StateBasedMeshSet = None
    animation_set: AnimationSet = None  # Fake Object

    def read(self, file_name: str) -> "BMS":
        return self.read_bytes(Path(file_name).read_bytes())

    def read_bytes(self, source: bytes) -> "BMS":
        self._source_bytes = bytes(source)
        reader = BytesIO(self._source_bytes)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiii", reader.read(20))

        if (self.magic != -981667554 or self.node_count < 1
                or self.node_information_offset < 20
                or self.node_information_offset + 32 * self.node_count > len(self._source_bytes)
                or not 20 <= self.node_hierarchy_offset < len(self._source_bytes)):
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        reader.seek(self.node_information_offset)
        self.node_informations = [RootNodeInformation().read(reader)]
        self.node_informations.extend(NodeInformation().read(reader) for _ in range(self.node_count - 1))
        self.state_based_mesh_set_node = None
        self.state_based_mesh_set = None
        for node_info in self.node_informations[1:]:
            if node_info.magic == 120902304:
                if self.state_based_mesh_set_node is not None:
                    raise ValueError("BMS contains multiple StateBasedMeshSet nodes")
                self.state_based_mesh_set_node = node_info
            if node_info.node_size < 0 or (node_info.node_size and
                    (node_info.offset < 20 or node_info.offset + node_info.node_size > len(self._source_bytes))):
                raise ValueError("BMS node payload is outside the file")

        reader.seek(self.node_hierarchy_offset)
        self.root_node = RootNode().read(reader)
        self.nodes = [self.root_node]
        self.nodes.extend(Node().read(reader) for _ in range(self.node_count - 1))
        self._hierarchy_end = reader.tell()
        for node in self.nodes[1:]:
            if not 0 < node.info_index < self.node_count:
                raise ValueError("BMS hierarchy references an invalid node-info index")
            self.node_informations[node.info_index].node_name = node.name
        if self.state_based_mesh_set_node is None:
            raise ValueError("BMS has no StateBasedMeshSet node")
        info = self.state_based_mesh_set_node
        stream = BytesIO(self._source_bytes[info.offset:info.offset + info.node_size])
        self.state_based_mesh_set = StateBasedMeshSet().read(stream)
        if stream.tell() != info.node_size:
            raise ValueError("Unparsed bytes in BMS StateBasedMeshSet payload")
        self._source_payload_span = (info.offset, info.node_size)
        return self

    def to_bytes(self) -> bytes:
        """Serialize edits, preserving loaded container metadata and unknown nodes."""
        if self.state_based_mesh_set is None:
            raise ValueError("BMS has no StateBasedMeshSet to export")
        output = BytesIO()
        self.state_based_mesh_set.write(output)
        payload = output.getvalue()
        source = getattr(self, "_source_bytes", None)
        if source is None:
            # Canonical one-node container, identical to the engine's chunk scheme.
            name = b"StateBasedMeshSet"
            table = 20 + len(payload)
            hierarchy = table + 64
            return (pack("<i4I", self.magic, self.number_of_models, table, hierarchy, 2)
                + payload + bytes(16) + pack("<i3I", -1, 1, 1, 0)
                + pack("<4I", 120902304, 1, 20, len(payload)) + bytes(16)
                + pack("<3I", 0, 0, 9) + b"root node"
                + pack("<2I", 1, len(name)) + name + pack("<I", 0))
        start, old_size = self._source_payload_span
        end = start + old_size
        if payload == source[start:end]:
            return source
        table, hierarchy = unpack("<2I", source[8:16])
        table_end = table + self.node_count * 32
        if start < table_end and end > table and self.node_count == 2 and start == 20 and table < hierarchy:
            # One stock scoutship declares its last string four bytes beyond the
            # payload, into the root table's zero padding. Preserve unchanged files
            # above; edited files receive a separate payload and intact metadata.
            new_table = 20 + len(payload)
            result = bytearray(source[:20] + payload + source[table:])
            result[8:16] = pack("<2I", new_table, hierarchy + new_table - table)
            result[new_table + 40:new_table + 48] = pack("<2I", 20, len(payload))
            return bytes(result)
        if (start < table_end and end > table) or (start < self._hierarchy_end and end > hierarchy):
            raise ValueError("BMS payload overlaps container metadata")
        delta = len(payload) - old_size
        def relocate(offset):
            return offset + delta if offset >= end else offset
        result = bytearray(source[:start] + payload + source[end:])
        new_table, new_hierarchy = relocate(table), relocate(hierarchy)
        result[8:16] = pack("<2I", new_table, new_hierarchy)
        # Change only offset/size words; retain root links, flags, identifiers and unknown data.
        for index, info in enumerate(self.node_informations[1:], 1):
            at = new_table + index * 32
            if info is self.state_based_mesh_set_node:
                result[at + 8:at + 16] = pack("<2I", start, len(payload))
            elif info.node_size:
                if info.offset < end and info.offset + info.node_size > start:
                    raise ValueError("BMS node payloads overlap")
                result[at + 8:at + 12] = pack("<I", relocate(info.offset))
        return bytes(result)

    def save(self, file_name: str) -> None:
        Path(file_name).write_bytes(self.to_bytes())
