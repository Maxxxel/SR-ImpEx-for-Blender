"""Blender-independent building grid authoring and snapshot reconstruction."""
from io import BytesIO
import math
import uuid

from sr_impex.definitions.grid_definitions import MeshSetGrid, MeshGridModule


def grid_from_blob(blob):
    raw = blob.get("source_grid_payload_hex")
    grid = MeshSetGrid().read(BytesIO(bytes.fromhex(raw))) if raw else MeshSetGrid()
    old_w, old_h = grid.grid_width, grid.grid_height
    width = int(blob.get("grid_width", blob.get("columns", old_w)))
    height = int(blob.get("grid_height", blob.get("rows", old_h)))
    if width != height or not 0 <= width <= 127:
        raise ValueError("The engine requires a square building grid with half extent 0–127")
    spacing = float(blob.get("module_distance", grid.module_distance))
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("Building cell spacing must be finite and greater than zero")
    grid.grid_width, grid.grid_height = width, height
    grid.module_distance = spacing
    grid.grid_rotation = int(round(float(blob.get("grid_rotation", blob.get("orientation", grid.grid_rotation)))))
    if not -32768 <= grid.grid_rotation <= 32767:
        raise ValueError("Building rotation is outside the signed 16-bit range")
    grid.is_center_pivoted = int(blob.get("is_center_pivoted", grid.is_center_pivoted))
    for attr in ("name", "uuid", "debris_effect", "destruction_effect", "ground_decal"):
        if attr in blob:
            setattr(grid, attr, str(blob[attr]))
    if not grid.uuid:
        grid.uuid = uuid.uuid1().hex.upper()
    modules = [MeshGridModule() for _ in range((width * 2 + 1) ** 2)]
    old_side, side = old_w * 2 + 1, width * 2 + 1
    for index, module in enumerate(grid.mesh_modules):
        x, z = index // old_side - old_w, index % old_side - old_h
        if abs(x) <= width and abs(z) <= height:
            modules[(x + width) * side + z + height] = module
        elif module.has_mesh_set:
            raise ValueError("Grid resize would discard a populated cell; remove it explicitly first")
    grid.mesh_modules = modules
    seen = set()
    for cell in blob.get("cells", []):
        index = int(cell["index"])
        if index in seen or not 0 <= index < len(modules):
            raise ValueError("Invalid or repeated building grid cell index")
        seen.add(index)
        module = modules[index]
        module.rotation = int(cell.get("rotation", module.rotation))
        if not 0 <= module.rotation <= 65535:
            raise ValueError("Cell rotation must fit an unsigned 16-bit value")
        # Explicitly disabled cells are meaningful. Enabling an empty cell needs
        # a state collection, which the Blender export layer supplies next.
        module.has_mesh_set = int(cell.get("has_mesh_set", module.has_mesh_set))
        if not 0 <= module.has_mesh_set <= 255:
            raise ValueError("Cell presence must fit an unsigned byte")
    return grid
