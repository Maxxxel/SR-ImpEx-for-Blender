# bmesh_utils.py
import bmesh
import bpy
from contextlib import contextmanager


@contextmanager
def new_bmesh_from_object(obj: bpy.types.Object):
    """
    Create a new BMesh from the given object's mesh data.
    Automatically write back changes and free the BMesh.
    Use this for operations in OBJECT mode.
    """
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    try:
        yield bm
    finally:
        bm.to_mesh(mesh)
        bm.free()


@contextmanager
def edit_bmesh_from_object(obj: bpy.types.Object):
    """
    Get a BMesh for editing from the given object.
    Assumes the object is already in EDIT mode.
    Automatically updates the edit mesh when done.
    """
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    try:
        yield bm
    finally:
        bmesh.update_edit_mesh(mesh)


@contextmanager
def new_bmesh():
    """
    Create a new BMesh.
    Automatically free the BMesh when done.
    """
    bm = bmesh.new()
    try:
        yield bm
    finally:
        bm.free()
