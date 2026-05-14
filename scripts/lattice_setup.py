"""
lattice_setup.py — Proportion lattice helper.

A Lattice modifier with a coarse control cage is the right tool for GROSS
proportion changes (make the character taller, narrow the waist, bigger
head). Per-vertex sculpting is the right tool for FINE detail (lift this
cheekbone, tweak that bicep). Use both, in this order.

This module sets up a 5×5×9 lattice cage around a body and adds a Lattice
modifier to every mesh you pass it, all referencing the same lattice. When
you grab a control point in Edit Mode on the lattice, all of those meshes
deform together — body, eyes, hair, costumes, decals — keeping the character
visually coherent through proportion changes.

KEY DESIGN CHOICE: scale the lattice DATA, not the lattice OBJECT
==================================================================

Blender lets you do `lattice.scale = (sx, sy, sz)` and then "apply scale" to
the lattice object. This is unreliable in headless contexts and only scales
`point.co` (rest position), not `point.co_deform` (deformed position) —
which creates a mismatch the modifier reads as "the lattice IS deformed by
default," producing baseline deformation before you've moved any point.

Instead, scale the underlying Lattice data block via `lat_data.transform(M)`,
which scales BOTH `co` and `co_deform`. That keeps them equal at startup
(no baseline deformation) and works headlessly.

WHY 5×5×9
=========

5×5 in the X/Y plane is fine-grained enough to taper the waist without
affecting the shoulders. 9 layers in Z gives you ~one control row per
anatomical region: feet, ankle, knee, mid-thigh, waist, lower chest,
chest, neck/shoulders, top of head. With 9 W layers, the layer-index ↔
anatomy mapping is meaningful enough to script ("lift the head layer").

A finer lattice (7×7×11) gives more control but takes longer to edit
manually. A coarser one (3×3×5) is too blunt — moving any single point
distorts large regions.

USAGE
=====

```python
from scripts.lattice_setup import add_proportion_lattice

body = bpy.data.objects["SuperHero_Male"]
costumes = [bpy.data.objects[n] for n in ["Eyes", "Eyebrows", "Shirt", "Pants"]]

lattice = add_proportion_lattice(
    primary=body,
    deformed_meshes=[body] + costumes,
    name="ProportionLattice",
)

# Now in Blender's UI, select the Lattice object, Tab into Edit Mode,
# grab control points (G key + X/Y/Z for axis lock) to deform.
```

WORKFLOW AFTER LATTICE EDITS
============================

When you've nailed proportions:

1. For each mesh with the Lattice modifier: Modifier Properties → drop-down
   → Apply. This bakes the deformation into the geometry permanently.
2. Delete the lattice object.
3. Move on to Sculpt Mode for fine details.

If you skip Apply and try to use the .glb directly, the lattice will still
deform the meshes at runtime — which works in Blender but doesn't survive
glTF export (the export bakes geometry without applying Lattice modifiers
unless `export_apply=True` is set).

AXIS LOCK DISCIPLINE
====================

When grabbing control points in Edit Mode, ALWAYS lock to an axis:
- `G` then `Z` — vertical motion only (stretch height, lift a layer)
- `G` then `X` — horizontal motion only (pinch the waist, widen shoulders)
- `G` then `Y` — front/back motion only (rare; usually you don't want this)

If you grab freely (`G` without an axis), Blender will happily move points
in all three dimensions — including Y depth — and your character will end
up with a stretched skull in side view that you didn't notice in front view.

LICENSE
=======

MIT — see LICENSE file in the repo root.
"""

from __future__ import annotations

from typing import Optional

import bpy
import mathutils


# Default lattice resolution. Reasonable for a humanoid body bbox.
DEFAULT_POINTS_U = 5
DEFAULT_POINTS_V = 5
DEFAULT_POINTS_W = 9

# Default margin around the primary mesh's bbox. The lattice should
# encompass the mesh plus a bit of headroom (literally) so deformations
# don't immediately clip the lattice cage.
DEFAULT_X_MARGIN = 1.10  # +10% around arm-span / width
DEFAULT_Y_MARGIN = 1.20  # +20% around depth (more room for "push out" deformations)
DEFAULT_Z_MARGIN = 1.05  # +5% above head, below feet


def add_proportion_lattice(
    primary: bpy.types.Object,
    deformed_meshes: list[bpy.types.Object],
    name: str = "ProportionLattice",
    points_u: int = DEFAULT_POINTS_U,
    points_v: int = DEFAULT_POINTS_V,
    points_w: int = DEFAULT_POINTS_W,
    x_margin: float = DEFAULT_X_MARGIN,
    y_margin: float = DEFAULT_Y_MARGIN,
    z_margin: float = DEFAULT_Z_MARGIN,
    modifier_index: int = 0,
) -> bpy.types.Object:
    """
    Set up a proportion lattice over `primary` and add a Lattice modifier
    referencing it to every object in `deformed_meshes`.

    Parameters
    ----------
    primary : the mesh whose bbox determines the lattice extent (usually the body).
              This object MUST be in the deformed_meshes list separately if you
              want it to deform — it's not added automatically.
    deformed_meshes : all meshes that should follow the lattice deformation.
                      Pass `[body] + costumes` to include everything together.
    name : name for the lattice object and its data block
    points_u, points_v, points_w : lattice control point counts on each axis
    x_margin, y_margin, z_margin : multipliers on the primary's bbox extent
    modifier_index : where to place the Lattice modifier in each mesh's stack.
                     0 = top (before Armature), which is usually right.

    Returns
    -------
    The created Lattice object.

    Side effects: removes any prior Lattice modifier from the deformed_meshes
    (idempotent re-runs), removes prior lattice object/data with the same name,
    adds a fresh lattice + modifiers.
    """
    # === Idempotent cleanup ============================================
    for obj in deformed_meshes:
        for mod in list(obj.modifiers):
            if mod.type == 'LATTICE':
                obj.modifiers.remove(mod)

    old_obj = bpy.data.objects.get(name)
    if old_obj is not None:
        bpy.data.objects.remove(old_obj, do_unlink=True)

    old_data_name = f"{name}_data"
    old_data = bpy.data.lattices.get(old_data_name)
    if old_data is not None:
        bpy.data.lattices.remove(old_data)

    # === Bbox: from the primary mesh only ==============================
    # Don't include arm-extended children or costume meshes in the bbox
    # calculation — they'd inflate the cage past where the body actually is.
    xs, ys, zs = [], [], []
    for corner in primary.bound_box:
        wp = primary.matrix_world @ mathutils.Vector(corner)
        xs.append(wp.x)
        ys.append(wp.y)
        zs.append(wp.z)

    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    target_x = (max(xs) - min(xs)) * x_margin
    target_y = (max(ys) - min(ys)) * y_margin
    target_z = (max(zs) - min(zs)) * z_margin

    # === Build the lattice ============================================
    lat_data = bpy.data.lattices.new(old_data_name)
    lat_data.points_u = points_u
    lat_data.points_v = points_v
    lat_data.points_w = points_w
    lat_data.interpolation_type_u = 'KEY_LINEAR'
    lat_data.interpolation_type_v = 'KEY_LINEAR'
    lat_data.interpolation_type_w = 'KEY_LINEAR'

    # Scale via Lattice.transform() so co == co_deform stays true.
    # See module docstring for why this matters.
    sx = target_x / (points_u - 1)
    sy = target_y / (points_v - 1)
    sz = target_z / (points_w - 1)
    scale_matrix = mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
    lat_data.transform(scale_matrix)

    lattice = bpy.data.objects.new(name, lat_data)
    bpy.context.scene.collection.objects.link(lattice)
    lattice.location = (cx, cy, cz)

    # Display: wireframe so it doesn't visually occlude the body, and
    # show_in_front so you can always see + click the control points.
    lattice.display_type = 'WIRE'
    lattice.show_in_front = True

    # === Add Lattice modifier to each target mesh =====================
    for mesh_obj in deformed_meshes:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)

        mod = mesh_obj.modifiers.new(name="ProportionLattice", type='LATTICE')
        mod.object = lattice
        # Move to top of modifier stack so it runs BEFORE Armature.
        # This means proportion edits affect the rest pose, then the rig
        # poses the proportion-adjusted body.
        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=modifier_index)

    return lattice


def reset_lattice(lattice: bpy.types.Object) -> None:
    """
    Snap all `co_deform` back to `co` on a lattice — undoes all deformation
    without removing the lattice itself.

    Equivalent to selecting all points in Edit Mode and pressing Alt+G
    ("clear location"), but works headlessly.
    """
    for p in lattice.data.points:
        p.co_deform = p.co


def apply_lattice_to_meshes(meshes: list[bpy.types.Object]) -> None:
    """
    Apply all Lattice modifiers on the given meshes, baking the deformation
    into geometry. Each modifier is removed after application.

    Call this before glTF export to make sure proportion edits survive the
    export (glTF doesn't preserve Lattice modifiers; only the baked geometry
    transfers).
    """
    for mesh in meshes:
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        for mod in list(mesh.modifiers):
            if mod.type == 'LATTICE':
                bpy.ops.object.modifier_apply(modifier=mod.name)


# === Anatomy helper for the default 9-layer W axis =====================

def w_layer_for_anatomy(region: str, body_z_min: float, body_z_max: float, points_w: int = 9) -> int:
    """
    Map an anatomical region name to a W-layer index, given the body's Z bbox.

    Useful when scripting proportion changes by anatomy rather than by raw
    layer index: `w_layer_for_anatomy('waist', 0, 1.8)` returns the layer
    closest to z=0.9 (mid-body).

    Recognized regions: 'feet', 'ankle', 'knee', 'mid_thigh', 'waist',
    'lower_chest', 'chest', 'shoulders', 'head'.

    With 9 W layers (default), the mapping for a 1.8m body (z=0 to z=1.8):

        W=0: feet           z=0.00
        W=1: ankle          z=0.225
        W=2: knee           z=0.45
        W=3: mid_thigh      z=0.675
        W=4: waist          z=0.90
        W=5: lower_chest    z=1.125
        W=6: chest          z=1.35
        W=7: shoulders      z=1.575
        W=8: head           z=1.80
    """
    canonical_regions = [
        "feet", "ankle", "knee", "mid_thigh",
        "waist", "lower_chest", "chest", "shoulders", "head",
    ]
    if points_w != len(canonical_regions):
        raise ValueError(
            f"This helper assumes points_w={len(canonical_regions)}. "
            f"For other lattice resolutions, map layers yourself."
        )
    try:
        return canonical_regions.index(region)
    except ValueError:
        raise ValueError(
            f"Unknown region '{region}'. Recognized: {canonical_regions}"
        )
