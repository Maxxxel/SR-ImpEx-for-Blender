"""Run with Blender --background --factory-startup --python this_file.py.

Optionally append: -- --fixture-dir /path/to/col_test
The fixture directory is read only; no blend or DRS files are saved.
"""

import argparse
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import bpy
from mathutils import Euler, Matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sr_impex.blender.transform_utils import parent_under_game_axes
from sr_impex.definitions.base_types import Vector3
from sr_impex.definitions.collision_definitions import BoxShape, CollisionShape
from sr_impex.definitions.drs_definitions import DRS
from sr_impex.utilities import drs_utility as drs
from sr_impex.utilities.helpers import copy, get_collection


FIXTURE_DIR = None


def import_box(shape, apply_transform):
    root = bpy.data.collections.new("DRSModel_roundtrip")
    bpy.context.scene.collection.children.link(root)
    drs.import_collision_shapes(
        root,
        SimpleNamespace(collision_shape=CollisionShape(box_count=1, boxes=[shape])),
    )
    parent_under_game_axes(root, apply_transform)
    bpy.context.view_layer.update()
    return root, get_box(root)


def get_box(root):
    collisions = get_collection(root, "CollisionShapes_Collection")
    return get_collection(collisions, "Boxes_Collection").objects[0]


def export_box(root):
    # Exercise the same collection copy and shape writer used by save_drs.
    duplicate = copy(bpy.context.scene.collection, root)
    duplicate.name += ".copy"
    shapes = drs.create_collision_shape(duplicate)
    stream = io.BytesIO()
    shapes.write(stream)
    stream.seek(0)
    return CollisionShape().read(stream).boxes[0]


def world_vertices(box):
    return [box.matrix_world @ vertex.co for vertex in box.data.vertices]


class CollisionBoxRoundtripTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def assert_geometry_equal(self, expected, actual):
        self.assertEqual(len(expected), len(actual))
        for vertex in expected:
            self.assertLess(min((vertex - other).length for other in actual), 1e-5)

    def test_offset_and_rotated_boxes_with_both_import_axis_options(self):
        for apply_transform in (False, True):
            for rotated in (False, True):
                for offset in (False, True):
                    with self.subTest(axes=apply_transform, rotated=rotated, offset=offset):
                        shape = BoxShape()
                        rotation = Euler((0.3, -0.7, 0.5)).to_matrix() if rotated else Matrix.Identity(3)
                        shape.coord_system.matrix.matrix = [v for row in rotation for v in row]
                        shape.coord_system.position = Vector3(0.4, 3.462, -0.13845) if offset else Vector3()
                        shape.geo_aabox.lower_left_corner = Vector3(-0.2, -0.4, -1.5)
                        shape.geo_aabox.upper_right_corner = Vector3(0.3, 0.5, 1.7)
                        root, box = import_box(shape, apply_transform)
                        expected = world_vertices(box)
                        # Repeated exports must not accumulate rotations or Z flips.
                        for _ in range(3):
                            root, box = import_box(export_box(root), apply_transform)
                            self.assert_geometry_equal(expected, world_vertices(box))

    def test_edited_box_under_intermediate_parent(self):
        shape = BoxShape()
        shape.coord_system.matrix.matrix = [v for row in Matrix.Identity(3) for v in row]
        shape.geo_aabox.lower_left_corner = Vector3(-0.2, -0.4, -1.5)
        shape.geo_aabox.upper_right_corner = Vector3(0.2, 0.4, 1.5)
        root, box = import_box(shape, True)
        intermediate = bpy.data.objects.new("CollisionPlacement", None)
        root.objects.link(intermediate)
        intermediate.parent = box.parent
        intermediate.location = (0.8, 1.2, -0.6)
        intermediate.rotation_euler = (0.2, -0.5, 0.4)
        box.parent = intermediate
        box.location = (0.3, 0.7, -0.9)
        box.rotation_euler = (-0.3, 0.4, 0.6)
        box.scale = (1.2, 0.8, 1.5)
        bpy.context.view_layer.update()
        expected = world_vertices(box)
        _, imported = import_box(export_box(root), True)
        self.assert_geometry_equal(expected, world_vertices(imported))

    def test_applied_rotation_after_parenting_to_game_orientation(self):
        shape = BoxShape()
        shape.coord_system.matrix.matrix = [v for row in Matrix.Identity(3) for v in row]
        shape.geo_aabox.lower_left_corner = Vector3(-0.2, -0.4, -1.5)
        shape.geo_aabox.upper_right_corner = Vector3(0.3, 0.5, 1.7)
        root, box = import_box(shape, True)
        box.rotation_euler = (0.2, -0.5, 0.4)
        bpy.context.view_layer.objects.active = box
        box.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        bpy.context.view_layer.update()
        expected = world_vertices(box)

        _, imported = import_box(export_box(root), True)
        self.assert_geometry_equal(expected, world_vertices(imported))

    def test_authored_cube_with_applied_rotation_and_scale(self):
        shape = BoxShape()
        shape.coord_system.matrix.matrix = [v for row in Matrix.Identity(3) for v in row]
        shape.geo_aabox.lower_left_corner = Vector3(-1, -1, -1)
        shape.geo_aabox.upper_right_corner = Vector3(1, 1, 1)
        root, original = import_box(shape, True)
        collection = original.users_collection[0]
        parent = original.parent
        bpy.data.objects.remove(original, do_unlink=True)
        bpy.ops.mesh.primitive_cube_add()
        box = bpy.context.object
        for linked in list(box.users_collection):
            linked.objects.unlink(box)
        collection.objects.link(box)
        box.parent = parent
        box.location = (0.3, 0.7, -0.9)
        box.rotation_euler = (0.2, -0.5, 0.4)
        box.scale = (0.2, 0.4, 1.5)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.context.view_layer.update()
        expected = world_vertices(box)
        for _ in range(3):
            root, imported = import_box(export_box(root), True)
            self.assert_geometry_equal(expected, world_vertices(imported))

    def test_unparented_box_in_game_coordinates(self):
        shape = BoxShape()
        shape.coord_system.matrix.matrix = [v for row in Matrix.Identity(3) for v in row]
        shape.coord_system.position = Vector3(0.5, 2.0, -0.75)
        shape.geo_aabox.lower_left_corner = Vector3(-0.2, -0.4, -1.5)
        shape.geo_aabox.upper_right_corner = Vector3(0.2, 0.4, 1.5)
        _, box = import_box(shape, False)
        box.parent = None
        bpy.context.view_layer.update()
        expected = world_vertices(box)
        exported = drs.create_box_shape(box)
        _, imported = import_box(exported, False)
        self.assert_geometry_equal(expected, world_vertices(imported))

    def test_supplied_stone_asset(self):
        if not FIXTURE_DIR:
            self.skipTest("Pass --fixture-dir to check the supplied asset")
        fixture = Path(FIXTURE_DIR)
        original = DRS().read(str(fixture / "object_frostland_stone_m_002.drs"))
        bpy.ops.wm.open_mainfile(filepath=str(fixture / "col_test.blend"))
        bpy.context.view_layer.update()
        box = bpy.data.objects["CollisionBox_0"]
        expected = world_vertices(box)
        root = next(c for c in bpy.data.collections if c.name.startswith("DRSModel_"))
        exported = export_box(root)
        reference = original.collision_shape.boxes[0]
        for actual, target in zip(exported.coord_system.matrix.matrix, reference.coord_system.matrix.matrix):
            self.assertAlmostEqual(actual, target, places=6)
        for axis in ("x", "y", "z"):
            self.assertAlmostEqual(getattr(exported.coord_system.position, axis), getattr(reference.coord_system.position, axis), places=6)
        _, imported = import_box(exported, True)
        self.assert_geometry_equal(expected, world_vertices(imported))
        self.assert_geometry_equal(expected, world_vertices(box))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    FIXTURE_DIR = args.fixture_dir
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollisionBoxRoundtripTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
