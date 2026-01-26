"""
BMG (Building Mesh Grid) File Format Definitions

This module contains data structure definitions for BMG files,
which define building layouts with modular grids and state-based meshes.
"""

from __future__ import annotations
from dataclasses import dataclass
from struct import pack, unpack
from typing import cast

from sr_impex.core.file_io import FileReader, FileWriter
from sr_impex.definitions.base_types import (
    BaseContainer,
    Node,
    NodeInformation,
    RootNode,
    RootNodeInformation,
    error_context,
    ExportError,
)
from sr_impex.definitions.animation_definitions import AnimationSet, AnimationTimings
from sr_impex.definitions.collision_definitions import CollisionShape
from sr_impex.definitions.effect_definitions import EffectSet
from sr_impex.definitions.resource_definitions import CGeoPrimitiveContainer
from sr_impex.definitions.grid_definitions import (
    SMeshState,
    DestructionState,
    StateBasedMeshSet,
    MeshGridModule,
    MeshSetGrid,
)
from sr_impex.definitions.enums import WriteOrder, InformationIndices

# Re-export grid classes for backward compatibility
__all__ = [
    'SMeshState', 'DestructionState', 'StateBasedMeshSet', 
    'MeshGridModule', 'MeshSetGrid', 'BMG', 'BMS',
]


@dataclass(eq=False, repr=False)
class BMG(BaseContainer):
    """BMG (Building Mesh Grid) file format for buildings with modular grids"""
    animation_set_node: Node = None
    animation_timings_node: Node = None
    cgeo_primitive_container_node: Node = None
    collision_shape_node: Node = None
    effect_set_node: Node = None
    animation_set: AnimationSet = None
    mesh_set_grid_node: Node = None
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

    def push_node_infos(self, class_name: str, data_object: object):
        # Get the right node from self.node_informations
        for node_info in self.node_informations:
            if node_info.node_name == class_name:
                node_info.data_object = data_object
                node_info.node_size = data_object.size()
                break

    def update_offsets(self):
        for node_name in WriteOrder[self.model_type]:
            # get the right node_infortmation froms self.node_informations
            node_information = next(
                (
                    node_info
                    for node_info in self.node_informations
                    if node_info.node_name == node_name
                ),
                None,
            )
            node_information.offset = self.data_offset
            self.data_offset += node_information.node_size

    def read(self, file_name: str) -> "BMG":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiiI", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        # Read Node Informations
        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)

        node_information_map = {
            154295579: "mesh_set_grid_node",
            -475734043: "animation_set_node",
            -1403092629: "animation_timings_node",
            1396683476: "cgeo_primitive_container_node",
            268607026: "collision_shape_node",
            688490554: "effect_set_node",
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            if node_info.magic in node_information_map:
                setattr(self, node_information_map[node_info.magic], node_info)
                self.node_informations.append(node_info)
            else:
                raise TypeError(f"Unknown Node: {node_info.magic}")

        # Read Node Hierarchy
        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)

        node_map = {
            "AnimationSet": "animation_set_node",
            "AnimationTimings": "animation_timings_node",
            "CGeoPrimitiveContainer": "cgeo_primitive_container_node",
            "collisionShape": "collision_shape_node",
            "EffectSet": "effect_set_node",
            "MeshSetGrid": "mesh_set_grid_node",
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            if node.name in node_map:
                val = node_map[node.name]
                if val == "collisionShape":
                    val = "CollisionShape"
                setattr(self, val, node)
                self.nodes.append(node)
            else:
                raise TypeError(f"Unknown Node: {node.name}")

        for node in self.nodes[1:]:  # skip root node, it has no info_index
            if not isinstance(node, Node):
                continue
            node = cast(Node, node)

            node_info = self.node_informations[node.info_index]  # type: ignore[attr-defined]
            if node_info is None:
                raise TypeError(f"Node {node.name} not found")

            reader.seek(node_info.offset)
            node_name = node_map.get(node.name, None).replace("_node", "")
            if node_map is None:
                raise TypeError(f"Node {node.name} not found in node_map")

            val = node.name
            if val == "collisionShape":
                val = "CollisionShape"

            setattr(self, node_name, globals()[val]().read(reader))

        reader.close()
        return self

    def save(self, file_name: str):
        writer = FileWriter(file_name)
        try:
            # offsets
            for ni in self.node_informations:
                self.node_information_offset += ni.node_size
            self.node_hierarchy_offset = self.node_information_offset + 32 + (self.node_count - 1) * 32

            # header
            with error_context("BMG header"):
                writer.write(pack(
                    "iiiiI",
                    self.magic,
                    self.number_of_models,
                    self.node_information_offset,
                    self.node_hierarchy_offset,
                    self.node_count,
                ))

            # packets (in WriteOrder)
            for node_name in WriteOrder[self.model_type]:
                if node_name == "CGeoPrimitiveContainer":
                    continue
                node_info = next((ni for ni in self.node_informations if ni.node_name == node_name), None)
                with error_context(f"{node_name}.write"):
                    node_info.data_object.write(writer)

            # node infos
            for node_info in self.node_informations:
                with error_context(f"NodeInformation[{node_info.node_name}].write"):
                    node_info.write(writer)

            # hierarchy
            for node in self.nodes:
                with error_context(f"Hierarchy node '{node.name}'.write"):
                    node.write(writer)

        except ExportError:
            # bubble normalized errors
            raise
        except Exception as e:
            # normalize anything else
            raise ExportError(f"DRS.save failed: {e}") from e
        finally:
            writer.close()


@dataclass(eq=False, repr=False)
class BMS(BaseContainer):
    """BMS (Building Module Set) file format for construction pieces"""
    node_information_offset: int = -1
    node_hierarchy_offset: int = -1
    root_node: RootNode = RootNode()
    state_based_mesh_set_node: NodeInformation = None
    state_based_mesh_set: StateBasedMeshSet = None
    animation_set: AnimationSet = None  # Fake Object

    def read(self, file_name: str) -> "BMS":
        reader = FileReader(file_name)
        (
            self.magic,
            self.number_of_models,
            self.node_information_offset,
            self.node_hierarchy_offset,
            self.node_count,
        ) = unpack("iiiii", reader.read(20))

        if self.magic != -981667554 or self.node_count < 1:
            raise TypeError(
                f"This is not a valid file. Magic: {self.magic}, NodeCount: {self.node_count}"
            )

        reader.seek(self.node_information_offset)
        self.node_informations[0] = RootNodeInformation().read(reader)

        node_information_map = {
            120902304: "state_based_mesh_set_node",
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            setattr(self, node_information_map.get(node_info.magic, ""), node_info)

        reader.seek(self.node_hierarchy_offset)
        self.nodes[0] = RootNode().read(reader)

        reader.seek(self.node_hierarchy_offset)
        node_map = {
            "StateBasedMeshSet": "state_based_mesh_set_node",
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            setattr(self, node_map.get(node.name, ""), node)

        for key, value in node_map.items():
            # remove _node from the value
            node_info: NodeInformation = getattr(self, value, None)
            index = value.replace("_node", "")
            if node_info is not None:
                reader.seek(node_info.offset)
                setattr(self, index, globals()[key]().read(reader))

        reader.close()
        return self
