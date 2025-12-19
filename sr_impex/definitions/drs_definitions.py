from __future__ import annotations

from dataclasses import dataclass
from struct import pack, unpack

from sr_impex.core.file_io import FileReader, FileWriter
from sr_impex.definitions.base_types import BaseContainer,ExportError,Node,NodeInformation,RootNode,RootNodeInformation, _auto_wrap_all_write_methods, error_context
from sr_impex.definitions.enums import WriteOrder, InformationIndices
from sr_impex.definitions.fxb_definitions import FxMaster
from sr_impex.definitions.mesh_definitions import CGeoMesh, CDspMeshFile
from sr_impex.definitions.skeleton_definitions import CSkSkeleton,CSkSkinInfo,CDspJointMap
from sr_impex.definitions.collision_definitions import CollisionShape
from sr_impex.definitions.obb_definitions import CGeoOBBTree
from sr_impex.definitions.locator_definitions import CDrwLocatorList
from sr_impex.definitions.resource_definitions import DrwResourceMeta, CGeoPrimitiveContainer
from sr_impex.definitions.animation_definitions import AnimationSet, AnimationTimings
from sr_impex.definitions.effect_definitions import EffectSet

@dataclass(eq=False, repr=False)
class DRS(BaseContainer):
    """DRS (DirectResource System) file format for models"""
    animation_set_node: Node = None
    cdsp_mesh_file_node: Node = None
    cgeo_mesh_node: Node = None
    csk_skin_info_node: Node = None
    csk_skeleton_node: Node = None
    animation_timings_node: Node = None
    cdsp_joint_map_node: Node = None
    cgeo_obb_tree_node: Node = None
    drw_resource_meta_node: Node = None
    cgeo_primitive_container_node: Node = None
    collision_shape_node: Node = None
    effect_set_node: Node = None
    cdrw_locator_list_node: Node = None
    fx_master_node: Node = None
    animation_set: AnimationSet = None
    cdsp_mesh_file: CDspMeshFile = None
    cgeo_mesh: CGeoMesh = None
    csk_skin_info: CSkSkinInfo = None
    csk_skeleton: CSkSkeleton = None
    cdsp_joint_map: CDspJointMap = None
    cgeo_obb_tree: CGeoOBBTree = None
    drw_resource_meta: DrwResourceMeta = None
    cgeo_primitive_container: CGeoPrimitiveContainer = None
    collision_shape: CollisionShape = None
    cdrw_locator_list: CDrwLocatorList = None
    effect_set: EffectSet = None
    animation_timings: AnimationTimings = None
    fx_master: "FxMaster" = None

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

    def read(self, file_name: str) -> "DRS":
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
            -475734043: "animation_set_node",
            -1900395636: "cdsp_mesh_file_node",
            100449016: "cgeo_mesh_node",
            -761174227: "csk_skin_info_node",
            -2110567991: "csk_skeleton_node",
            -1403092629: "animation_timings_node",
            -1340635850: "cdsp_joint_map_node",
            -933519637: "cgeo_obb_tree_node",
            -183033339: "drw_resource_meta_node",
            1396683476: "cgeo_primitive_container_node",
            268607026: "collision_shape_node",
            688490554: "effect_set_node",
            735146985: "cdrw_locator_list_node",
            -196433635: "gd_locator_list_node",  # Not yet implemented
            -1424862619: "fx_master_node",
        }

        for _ in range(self.node_count - 1):
            node_info = NodeInformation().read(reader)
            # Check if the node_info is in the node_information_map
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
            "CDspMeshFile": "cdsp_mesh_file_node",
            "CGeoMesh": "cgeo_mesh_node",
            "CSkSkinInfo": "csk_skin_info_node",
            "CSkSkeleton": "csk_skeleton_node",
            "AnimationTimings": "animation_timings_node",
            "CDspJointMap": "cdsp_joint_map_node",
            "CGeoOBBTree": "cgeo_obb_tree_node",
            "DrwResourceMeta": "drw_resource_meta_node",
            "CGeoPrimitiveContainer": "cgeo_primitive_container_node",
            "collisionShape": "collision_shape_node",
            "EffectSet": "effect_set_node",
            "CDrwLocatorList": "cdrw_locator_list_node",
            "CGdLocatorList": "gd_locator_list_node",  # Not yet implemented
            "FxMaster": "fx_master_node",
        }

        for _ in range(self.node_count - 1):
            node = Node().read(reader)
            # Check if the node is in the node_map
            if node.name in node_map:
                # collisionShape is a special case, as its first letter is lowercase
                val = node_map[node.name]
                if val == "collisionShape":
                    val = "CollisionShape"
                setattr(self, val, node)
                self.nodes.append(node)
            else:
                raise TypeError(f"Unknown Node: {node.name}")

        for node in self.nodes:
            if not hasattr(node, "info_index"):
                # Root Node has no info_index
                continue

            node_info = self.node_informations[node.info_index] # pylint: disable=E1101
            if node_info is None:
                raise TypeError(f"Node {node.name} not found")

            reader.seek(node_info.offset)
            node_name = node_map.get(node.name, None).replace("_node", "")
            if node_map is None:
                raise TypeError(f"Node {node.name} not found in node_map")
            # CollisionShape is a special case, as its first letter is lowercase
            val = node.name
            if val == "collisionShape":
                val = "CollisionShape"

            if val == "FxMaster":
                self.fx_master = FxMaster().read(reader)
                continue

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
            with error_context("DRS header"):
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

_auto_wrap_all_write_methods(globals())
