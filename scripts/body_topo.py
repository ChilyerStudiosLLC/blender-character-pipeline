"""
body_topo.py — Duplicate-from-body costume authoring helper.

The "body-topo" pattern: rather than modeling a garment from scratch and then
fighting to weight it to the rig, you duplicate the body's geometry, trim it
down to the region you want (chest+arms for a shirt, hips+legs for pants),
push it slightly outward so it doesn't z-fight with the body, smooth the cut
edges, give it some thickness, and assign a material.

The garment inherits the body's vertex groups (and therefore the rig binding)
for free. It fits the body perfectly because it IS the body's topology. It
animates correctly the moment it exists. And the polycount is naturally lean
because you're only keeping the faces in the garment region.

This module provides one main function — `build_bodytopo_garment` — that
implements the 9-step pattern as a single call. You write a face-predicate
that says which faces to keep, and the helper does the rest.

USAGE
=====

```python
from scripts.body_topo import build_bodytopo_garment

body = bpy.data.objects["SuperHero_Male"]

def jersey_region(cx, cy, cz):
    if not (0.95 <= cz <= 1.55):  # upper hip to neck base
        return False
    if abs(cx) > 0.45:             # short sleeve cutoff
        return False
    return True

result = build_bodytopo_garment(
    body_obj=body,
    name="Jersey",
    keep_face=jersey_region,
    base_color=(0.04, 0.04, 0.04, 1.0),  # near-black
)
print(f"Built jersey: {result['verts']} verts, {result['polys']} polys")
```

THE 9 STEPS
===========

1. Duplicate body (inherits topology, UVs, vertex groups, Armature modifier)
2. Merge by distance — CRITICAL because most rigged base meshes ship with
   unmerged centerline doubles (mirror modifier artifact). Skip this and your
   garment splits down the centerline when posed.
3. Cull faces outside the garment zone via the keep_face predicate
4. Push all verts +N mm along their normals — clears z-fighting with the body
5. Laplacian-smooth boundary verts — kills the stair-step edge that face-center
   culling produces along diagonal cuts
6. Remove small disconnected face islands — sweep up stray triangles that
   survived the cull as "epaulets" or "armhole leftovers"
7. Push boundary verts another small amount — Laplacian shrinks the boundary
   loop slightly, this re-clears the body underneath
8. Add Solidify modifier — gives the garment fabric thickness, positioned
   AFTER any Armature modifier so thickness is on the deformed surface
9. Replace materials with a fresh Principled BSDF

REQUIREMENTS
============

The body mesh should:
- Have an Armature modifier (carried over to the duplicate; required for the
  garment to deform with the rig)
- Have vertex groups corresponding to bones (carried over automatically)
- Be in Object Mode when this function is called

The face predicate operates on FACE CENTER coordinates in the body's local
space (which == world space if the body is at world origin with no rotation,
the standard rest-pose convention).

GOTCHAS DOCUMENTED
==================

- If you skip merge-by-distance, garments split visibly at the centerline.
  Don't disable this step.
- If your predicate produces stair-step cuts (faces alternating in/out along
  a diagonal), Laplacian smoothing fixes it. Boundary smoothing also slightly
  shrinks the loop, which is why we push boundary verts again afterward.
- Solidify modifier MUST come after Armature in the stack, or the thickness
  direction will be on the rest-pose surface instead of the animated one.

LICENSE
=======

MIT — see LICENSE file in the repo root.
"""

from __future__ import annotations

from typing import Callable, Optional

import bpy
import bmesh
from mathutils import Vector


def build_bodytopo_garment(
    body_obj: bpy.types.Object,
    name: str,
    keep_face: Callable[[float, float, float], bool],
    base_color: tuple = (0.5, 0.5, 0.5, 1.0),
    push_distance: float = 0.006,
    smooth_passes: int = 6,
    smooth_lambda: float = 0.5,
    boundary_push: float = 0.002,
    solidify_thickness: float = 0.004,
    min_island_size: int = 50,
    merge_distance: float = 0.0001,
    roughness: float = 0.55,
) -> dict:
    """
    Build a body-topology garment.

    Parameters
    ----------
    body_obj : the base body mesh to duplicate from. Must be in Object Mode.
    name : name for the new garment object and its mesh data
    keep_face : predicate(cx, cy, cz) -> bool — return True to KEEP that face.
                cx, cy, cz are face-center coordinates in the body's local space.
    base_color : RGBA tuple for the Principled BSDF base color
    push_distance : meters to push all verts along their normals (z-fighting clearance)
    smooth_passes : Laplacian smoothing iterations on the boundary
    smooth_lambda : smoothing strength per pass (0..1, where 0.5 is a good default)
    boundary_push : additional meters to push boundary verts after smoothing
    solidify_thickness : meters of thickness from the Solidify modifier
    min_island_size : faces; disconnected islands smaller than this are removed
    merge_distance : meters; threshold for the initial merge-by-distance
    roughness : Principled BSDF roughness (0..1)

    Returns
    -------
    dict with keys:
        'object'         : the created garment Blender object
        'verts'          : final vertex count
        'polys'          : final polygon count
        'doubles_welded' : how many vertices the merge-by-distance step removed
        'islands'        : sorted-descending list of connected face island sizes
        'small_removed'  : how many faces were removed as small disconnected islands
        'boundary_count' : boundary vertex count after smoothing

    Raises
    ------
    RuntimeError if Blender isn't in Object Mode at call time.

    Example
    -------
    >>> body = bpy.data.objects["SuperHero_Male"]
    >>> result = build_bodytopo_garment(
    ...     body, "Shirt",
    ...     keep_face=lambda cx, cy, cz: 1.0 <= cz <= 1.5 and abs(cx) < 0.4,
    ...     base_color=(0.2, 0.4, 0.8, 1.0),
    ... )
    >>> print(result['verts'])
    """
    # Sanity check: must be in Object Mode for object-level ops
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # === STEP 1: Duplicate the body =====================================
    # Use linked=False so the duplicate gets its own mesh data block — we'll
    # modify it independently. Armature modifier and vertex groups carry over.
    bpy.ops.object.select_all(action='DESELECT')
    body_obj.select_set(True)
    bpy.context.view_layer.objects.active = body_obj
    bpy.ops.object.duplicate(linked=False)
    garment = bpy.context.active_object
    garment.name = name
    garment.data.name = name

    # === STEP 2: Merge by distance ======================================
    # The single most-important step. Most rigged base meshes ship with
    # unmerged centerline doubles (mirror-modifier output that was never
    # welded). On the body the seam is invisible; on a garment derived from
    # the body, the left and right halves would be SEPARATE connected
    # components, which become visibly split when the rig deforms them.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    verts_before = len(garment.data.vertices)
    bpy.ops.mesh.remove_doubles(threshold=merge_distance)
    bpy.ops.object.mode_set(mode='OBJECT')
    doubles_welded = verts_before - len(garment.data.vertices)

    # === STEP 3: Cull faces by predicate =================================
    # Use bmesh for efficient face deletion. Predicate receives face-center
    # coordinates; user-side cut conditions live in their predicate function.
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(garment.data)
    bm.faces.ensure_lookup_table()
    faces_to_delete = [
        f for f in bm.faces
        if not keep_face(*f.calc_center_median())
    ]
    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
    bmesh.update_edit_mesh(garment.data)

    # === STEP 4: Push verts along normals ================================
    # Clears z-fighting between the garment and the underlying body. Applied
    # to all verts (not just boundary) so the whole garment lifts uniformly.
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.shrink_fatten(value=push_distance)

    # === STEP 5: Laplacian-smooth boundary verts =========================
    # Boundary = verts on edges where only 1 face uses the edge (i.e., open
    # edges along the cut). Face-center culling produces stair-step boundaries
    # along diagonal cuts; smoothing makes them flow naturally.
    bm = bmesh.from_edit_mesh(garment.data)
    bm.edges.ensure_lookup_table()

    def find_boundary_verts():
        boundary = set()
        for edge in bm.edges:
            if len(edge.link_faces) == 1:
                boundary.update(edge.verts)
        return boundary

    boundary_verts = find_boundary_verts()

    for _ in range(smooth_passes):
        new_positions = {}
        for v in boundary_verts:
            # Average position of boundary-neighbor verts only (so smoothing
            # follows the boundary curve, not the interior)
            neighbors = [
                edge.other_vert(v).co
                for edge in v.link_edges
                if len(edge.link_faces) == 1
                   and edge.other_vert(v) in boundary_verts
            ]
            if neighbors:
                avg = sum(neighbors, Vector()) / len(neighbors)
                new_positions[v] = v.co.lerp(avg, smooth_lambda)
        for v, new_co in new_positions.items():
            v.co = new_co
    bmesh.update_edit_mesh(garment.data)

    # === STEP 6: Remove small disconnected islands =======================
    # BFS connected components by face adjacency. Drop any island below the
    # threshold — these are usually stray triangles that survived the cull
    # (e.g., an isolated armpit face, an island of "epaulet" near the cuff).
    bm.faces.ensure_lookup_table()
    visited = set()
    islands = []
    for start_face in bm.faces:
        if start_face in visited:
            continue
        island = []
        queue = [start_face]
        while queue:
            f = queue.pop()
            if f in visited:
                continue
            visited.add(f)
            island.append(f)
            for edge in f.edges:
                for nf in edge.link_faces:
                    if nf not in visited:
                        queue.append(nf)
        islands.append(island)

    islands_sizes = sorted([len(i) for i in islands], reverse=True)
    small_faces = [f for island in islands if len(island) < min_island_size for f in island]
    if small_faces:
        bmesh.ops.delete(bm, geom=small_faces, context='FACES')
        bmesh.update_edit_mesh(garment.data)

    # === STEP 7: Push boundary verts again ===============================
    # Laplacian smoothing tends to pull boundary verts slightly inward
    # (toward the average of their neighbors). A second small push along
    # normals re-clears the body underneath.
    bm.edges.ensure_lookup_table()
    boundary_verts_2 = find_boundary_verts()
    for v in boundary_verts_2:
        v.co += v.normal * boundary_push
    bmesh.update_edit_mesh(garment.data)

    bpy.ops.object.mode_set(mode='OBJECT')

    # === STEP 8: Solidify modifier =======================================
    # Gives the garment fabric thickness. Offset=0 makes the thickness
    # symmetric around the surface. Modifier order matters: this must come
    # AFTER any Armature modifier so the thickness direction follows the
    # deformed (animated) surface, not the rest-pose one.
    mod = garment.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = solidify_thickness
    mod.offset = 0.0
    mod.use_rim = True

    # === STEP 9: Material assignment =====================================
    # Clear any inherited materials from the body and add a fresh one with
    # the requested base color. Principled BSDF translates cleanly to glTF
    # PBR and renders correctly in any modern engine.
    garment.data.materials.clear()
    mat = bpy.data.materials.new(name=f"{name}_Material")
    mat.use_nodes = True
    principled = next(
        (n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"),
        None,
    )
    if principled:
        principled.inputs["Base Color"].default_value = base_color
        principled.inputs["Roughness"].default_value = roughness
    garment.data.materials.append(mat)

    return {
        "object": garment,
        "verts": len(garment.data.vertices),
        "polys": len(garment.data.polygons),
        "doubles_welded": doubles_welded,
        "islands": islands_sizes,
        "small_removed": len(small_faces),
        "boundary_count": len(boundary_verts_2),
    }


def report(result: dict) -> str:
    """Format a `build_bodytopo_garment` result as a one-line summary string."""
    obj = result["object"]
    return (
        f"{obj.name}: {result['verts']} verts, {result['polys']} polys, "
        f"merged {result['doubles_welded']} doubles, "
        f"islands={result['islands']}, "
        f"removed {result['small_removed']} small-island faces, "
        f"{result['boundary_count']} boundary verts"
    )
