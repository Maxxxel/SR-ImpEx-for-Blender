# sr_impex/material_flow_editor_blender.py
import bpy
from bpy.props import IntProperty, BoolProperty, FloatVectorProperty, PointerProperty
from bpy.types import Panel, PropertyGroup

# Same labels you used in the PyQt material editor (so users see familiar names)
KNOWN_MATERIAL_FLAGS = {
    0: "Enable Alpha Test",
    1: "Decal Mode",
    16: "Use Parameter Map",
    17: "Use Normal Map",
    18: "Use Refraction Map",
    20: "Disable Receive Shadows",
    21: "Enable SH Lighting",
    # Unknowns are auto-filled as "Unknown Bitflag #N"
}
_MAX_BITS = 32

# --- Material flags PG --------------------------------------------------------
_updating_flags = False  # guard to avoid recursive updates


def _on_raw_changed(self, _ctx):
    global _updating_flags
    if _updating_flags:
        return
    _updating_flags = True
    v = int(self.bool_parameter) & 0xFFFFFFFF
    for i in range(_MAX_BITS):
        setattr(self, f"bit_{i}", bool((v >> i) & 1))
    _updating_flags = False


def _on_bit_changed(self, _ctx):
    global _updating_flags
    if _updating_flags:
        return
    _updating_flags = True
    v = 0
    for i in range(_MAX_BITS):
        if getattr(self, f"bit_{i}", False):
            v |= 1 << i
    self.bool_parameter = v
    _updating_flags = False


class DRS_MaterialFlagsPG(PropertyGroup):
    bool_parameter: IntProperty(
        name="Raw bool_parameter",
        description="32-bit integer of material flags",
        default=0,
        min=0,
        update=_on_raw_changed,
    )  # type: ignore


# --- Flow PG ------------------------------------------------------------------
class DRS_FlowPG(PropertyGroup):
    use_flow: BoolProperty(
        name="Write Flow",
        description="Enable writing Flow to the mesh material block on export",
        default=False,
    )  # type: ignore
    max_flow_speed: FloatVectorProperty(name="Max Flow Speed", size=4, default=(0, 0, 0, 0))  # type: ignore
    min_flow_speed: FloatVectorProperty(name="Min Flow Speed", size=4, default=(0, 0, 0, 0))  # type: ignore
    flow_speed_change: FloatVectorProperty(name="Flow Speed Change", size=4, default=(0, 0, 0, 0))  # type: ignore
    flow_scale: FloatVectorProperty(name="Flow Scale", size=4, default=(0, 0, 0, 0))  # type: ignore


# --- Helpers ------------------------------------------------------------------
def _in_meshes_collection(obj: bpy.types.Object) -> bool:
    return any(col.name == "Meshes_Collection" for col in obj.users_collection)


def _highest_relevant_bit(value: int) -> int:
    if value <= 0:
        return 7  # show at least 0..7 when nothing is set
    h = value.bit_length() - 1
    return min(max(h, 7), 31)


# --- Panels -------------------------------------------------------------------
class DRS_PT_MaterialFlags(Panel):
    bl_label = "Material (bool_parameter)"
    bl_category = "SR-IMPEx"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, ctx):
        o = ctx.object
        return (
            o is not None
            and o.type == "MESH"
            and _in_meshes_collection(o)
            and hasattr(o, "drs_material")
            and o.drs_material is not None
        )

    def draw(self, ctx):
        layout = self.layout
        o = ctx.object
        flags = o.drs_material

        layout.prop(flags, "bool_parameter")

        # Draw bit checkboxes up to the most relevant bit (plus known named ones)
        max_known = max(KNOWN_MATERIAL_FLAGS.keys()) if KNOWN_MATERIAL_FLAGS else 0
        max_bit = max(_highest_relevant_bit(flags.bool_parameter), max_known, 7)

        col = layout.column(align=True)
        for i in range(max_bit + 1):
            label = KNOWN_MATERIAL_FLAGS.get(i, f"Unknown Bitflag #{i+1}")
            col.prop(flags, f"bit_{i}", text=f"{label} (Bit {i})")


class DRS_PT_Flow(Panel):
    bl_label = "Flow"
    bl_category = "SR-IMPEx"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, ctx):
        o = ctx.object
        return (
            o is not None
            and o.type == "MESH"
            and _in_meshes_collection(o)
            and hasattr(o, "drs_flow")
            and o.drs_flow is not None
        )

    def draw(self, ctx):
        layout = self.layout
        f = ctx.object.drs_flow

        layout.prop(f, "use_flow")
        box = layout.box()
        box.enabled = f.use_flow

        grid = box.grid_flow(columns=1, even_columns=True, even_rows=True, align=True)
        grid.prop(f, "max_flow_speed")
        grid.prop(f, "min_flow_speed")
        grid.prop(f, "flow_speed_change")
        grid.prop(f, "flow_scale")


# --- Register -----------------------------------------------------------------
classes = (
    DRS_MaterialFlagsPG,
    DRS_FlowPG,
    DRS_PT_MaterialFlags,
    DRS_PT_Flow,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Dynamically add bit_0..bit_31 BoolProperties
    for i in range(_MAX_BITS):
        setattr(
            DRS_MaterialFlagsPG,
            f"bit_{i}",
            BoolProperty(name=f"Bit {i}", default=False, update=_on_bit_changed),
        )

    bpy.types.Object.drs_material = PointerProperty(type=DRS_MaterialFlagsPG)  # type: ignore
    bpy.types.Object.drs_flow = PointerProperty(type=DRS_FlowPG)  # keep name stable


def unregister():
    del bpy.types.Object.drs_flow
    del bpy.types.Object.drs_material

    # Remove dynamic bits so reloads are clean
    for i in range(_MAX_BITS):
        try:
            delattr(DRS_MaterialFlagsPG, f"bit_{i}")
        except Exception:
            pass

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
