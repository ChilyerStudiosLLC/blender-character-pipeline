# Body-Topology Costume Recipe

The 9-step pattern for authoring game-ready costume pieces by duplicating and trimming the body mesh, rather than modeling garments from scratch.

This document is the **deep explanation**. The runnable version is `scripts/body_topo.py` — `build_bodytopo_garment(...)` does all 9 steps in one call. Read this when you want to understand *why* each step exists, modify the script for a new edge case, or debug a garment that came out wrong.

---

## Why duplicate-from-body, not model-from-scratch

The naïve approach to character costumes: model a shirt as primitive geometry (boxes, extrusions, subdivision), UV-unwrap it, manually paint vertex weights to bind to the rig.

This sounds simple. In practice it fails for non-trivial garments because:

- **Topology doesn't match the body.** Around the deltoid/shoulder transition, the body has compound curvature (the shoulder bulges over the armpit). A procedural shirt modeled as "cylinder around the torso, cylinder for the sleeve" doesn't have geometry that follows that curve. The shirt either clips into the body or floats above it. No amount of manual weighting fixes this — it's a topology mismatch.

- **Vertex weights are tedious and easy to get wrong.** A correctly-weighted T-shirt has weight blending across the shoulder/upper-arm seam, the chest/lats transition, the lower torso flex. Painting this by hand on an unfamiliar topology eats an hour per garment and produces bugs you only see during animation.

- **Cross-section assumptions break at the upper body.** "Procedural-polar" sampling (which works for skirts) assumes "at each Z slice, the body is roughly cylindrical with one center point." This is true for legs and skirts. It's *false* at the upper body — shoulders bulge radially, bust isn't convex, the armpit is a concave pocket. Polar sampling produces stair-step seams that betray procedural origin.

**Duplicating the body solves all three problems at once:**
- Topology matches by construction (it *is* the body's topology, with faces removed)
- Vertex weights are inherited from the body's vertex groups — zero manual painting
- No cross-section assumptions because the geometry is the actual body surface, with whatever compound curvature it has

The cost is that the garment shape is constrained to "where the body surface goes." For tight-fitting garments (shirts, leggings, sport tops) this is exactly what you want. For loose flowing garments (capes, robes, dresses), you need a different approach — see [Loose-garment alternatives](#loose-garment-alternatives) at the bottom.

---

## The 9 steps in detail

The face-keep predicate you provide is the only design decision. Everything else is mechanical.

### Step 1 — Duplicate the body

```python
bpy.ops.object.duplicate(linked=False)
```

`linked=False` means the duplicate gets its own mesh data block (otherwise edits would propagate to the body). Object-level attributes like the Armature modifier and the vertex groups carry over automatically.

This is the cheapest step and the most important. The duplicate now has the entire body's topology, UVs, vertex groups, and rig binding — all properties we'll trim down, not build up.

### Step 2 — Merge by distance (CRITICAL)

```python
bpy.ops.mesh.remove_doubles(threshold=0.0001)
```

**Skip this and your garment will visibly split down the centerline.**

Most rigged base meshes (Quaternius, MakeHuman exports, ManuelBastioniLAB) are authored with a Mirror modifier and then exported without the modifier being applied to weld the centerline doubles. On the body, the seam is invisible because both halves share the same surface. On a garment derived from the body, the L-half and R-half become *separate connected components* — they can drift apart during rig deformation, producing a visible vertical stripe down the spine.

On the Quaternius Superhero_Male base specifically, this step welds **996 doubled vertices**. Always present, always needs welding. The cost of running this step is negligible (~50ms) compared to the cost of debugging the split later.

### Step 3 — Cull faces by predicate

```python
faces_to_delete = [f for f in bm.faces if not keep_face(*f.calc_center_median())]
bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
```

This is where your design decisions land. The predicate takes the **face center coordinates** (cx, cy, cz) and returns True (keep) or False (delete).

Common patterns:

```python
# A short-sleeved T-shirt: torso + upper arms
def t_shirt(cx, cy, cz):
    if not (1.00 <= cz <= 1.50):  # waist to upper chest
        return False
    if abs(cx) > 0.45:             # short sleeve ends mid-bicep
        return False
    return True

# A V-neck cut into the front (keep the back closed)
def v_neck(cx, cy, cz):
    # ... base shirt range first ...
    if 1.30 < cz < 1.46 and cy < -0.04:  # front-of-chest region
        v_half_width = 0.025 + (cz - 1.30) * 0.3125
        if abs(cx) < v_half_width:
            return False  # cut the V
    return True

# An armhole cut (sleeveless tank top)
def tank_top(cx, cy, cz):
    if not (1.00 <= cz <= 1.50):
        return False
    if abs(cx) > 0.21:  # no sleeve at all
        return False
    # Cut a tight armhole — same range as cap-sleeve T but no fabric out
    if 1.30 < cz < 1.40 and abs(cx) > 0.115 and -0.05 < cy < 0.07:
        return False
    return True
```

The predicate operates on face *centers*, not vertices. This matters because a face spanning the cut boundary will be either kept or deleted as a unit — there's no partial-face cutting. This is what produces the "stair-step" boundary that step 5 has to smooth.

### Step 4 — Push verts along normals

```python
bpy.ops.transform.shrink_fatten(value=0.006)  # 6mm
```

Without this, the garment sits *exactly* on the body surface. The fragment shader can't reliably decide which one is in front, and you get z-fighting (the flickery alternating-render artifact).

6mm is a reasonable default. It's enough to clear z-fighting on most game-render distances, and small enough that the garment still reads as form-fitting. For looser garments, push 10-20mm. For very tight (sport tops), 3-4mm is fine.

This step is applied to **all** verts, not just boundary. The whole garment lifts uniformly.

### Step 5 — Laplacian smooth boundary verts (6 passes, λ=0.5)

Boundary verts are verts on edges that have only one linked face (i.e., the cut edges, where there's no neighbor face on one side).

```python
boundary_verts = {v for edge in bm.edges if len(edge.link_faces) == 1 for v in edge.verts}
for _ in range(smooth_passes):
    for v in boundary_verts:
        neighbors = [edge.other_vert(v).co for edge in v.link_edges
                     if len(edge.link_faces) == 1
                        and edge.other_vert(v) in boundary_verts]
        if neighbors:
            avg = sum(neighbors, Vector()) / len(neighbors)
            v.co = v.co.lerp(avg, smooth_lambda)
```

Each pass moves each boundary vert halfway toward the average position of its *boundary neighbors*. After 6 passes the stair-step edge from face-center culling becomes a smooth curve.

Why only boundary verts? If you Laplacian-smooth the whole mesh you flatten the geometric details (deltoids, ribs, etc.) you specifically inherited from the body. Smoothing only boundary preserves the interior surface.

Why neighbors-among-boundary-only? Without this restriction, boundary verts would average with their interior neighbors and get pulled inward off the boundary — producing a frayed edge instead of a clean one.

### Step 6 — Remove small disconnected face islands

After culling, you sometimes end up with stray triangles that survived but aren't connected to the main garment — a single face above the armhole, a tiny island near a cuff. These look like floating geometry pieces in the final render.

```python
# BFS each face into its connected component, drop components below threshold
visited = set()
islands = []
for start in bm.faces:
    if start in visited: continue
    island = []
    queue = [start]
    while queue:
        f = queue.pop()
        if f in visited: continue
        visited.add(f)
        island.append(f)
        for edge in f.edges:
            for nf in edge.link_faces:
                if nf not in visited: queue.append(nf)
    islands.append(island)

small = [f for isl in islands if len(isl) < min_island_size for f in isl]
bmesh.ops.delete(bm, geom=small, context='FACES')
```

The threshold (default: 50 faces) is "below this size, it's an artifact, not a costume piece." Adjust if you're building intentionally-small accessories.

**Pro tip:** If step 6 reports >0 small-island removals, your cut conditions left stray triangles. Either tighten the cuts or accept the cleanup. If step 6 reports 0 removals, your cuts are clean — that's the result you want.

### Step 7 — Push boundary verts again

```python
boundary_verts = find_boundary_verts()  # recompute after island removal
for v in boundary_verts:
    v.co += v.normal * 0.002  # 2mm more
```

Laplacian smoothing in step 5 pulls boundary verts slightly *inward* (toward the average of their neighbors). This re-pushes them along their normals so they clear the body again. 2mm is enough; more starts to read as visible "fabric thickness" at the seam.

### Step 8 — Solidify modifier

```python
mod = garment.modifiers.new(name="Solidify", type='SOLIDIFY')
mod.thickness = 0.004  # 4mm
mod.offset = 0.0       # symmetric thickness
```

Gives the garment fabric thickness. Without this it's an infinitely-thin sheet that looks weirdly papery in raking light and produces shadow artifacts.

**Modifier order matters.** Solidify must come AFTER the Armature modifier so the thickness is on the deformed surface, not the rest-pose one. If you put Solidify first, then animate the character, the thickness will be in the wrong place — you'll see fabric pinching at joints.

4mm is heavier than realistic shirt fabric (~1mm) but reads correctly at game distance and avoids shadow-acne on low-poly normals. Adjust per material — leather jackets can be 8mm, swimwear can be 2mm.

### Step 9 — Material assignment

```python
garment.data.materials.clear()  # remove inherited body materials
mat = bpy.data.materials.new(name=f"{name}_Material")
mat.use_nodes = True
principled = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
principled.inputs["Base Color"].default_value = base_color
principled.inputs["Roughness"].default_value = 0.55
garment.data.materials.append(mat)
```

Principled BSDF only. It maps cleanly to glTF PBR (which most game engines speak), and roundtrips through Blender → glTF → engine without surprises. Custom shader graphs almost always produce export warnings or visual differences.

Roughness 0.55 is a "matte fabric" default. Increase toward 1.0 for very matte materials (felt), decrease toward 0.3 for shinier (leather, satin).

---

## Cut-condition design tips

These are the design moves you'll make over and over:

**Bounded z slab** (the default — defines vertical extent):
```python
if not (z_low <= cz <= z_high): return False
```

**Bounded x cutoff** (sleeve length, leg coverage):
```python
if abs(cx) > x_max: return False
```

**Front-only feature** (V-neck, chest emblem, belly cutout):
```python
if cy < y_threshold:  # front of body (assuming -Y is forward)
    # ... front-only cut/keep logic
```

**Tapered cut** (V-neck that widens at the top):
```python
if 1.30 < cz < 1.46 and cy < -0.04:
    v_half_width = 0.025 + (cz - 1.30) * 0.3125  # linear taper
    if abs(cx) < v_half_width: return False
```

**Range cut** (armhole — a bounded region with all four conditions):
```python
if z_low < cz < z_high and abs(cx) > x_inner and y_low < cy < y_high:
    return False  # cut this rectangular volume out
```

**Stripe** (chest number panel, racing stripe):
```python
# Cut out a vertical stripe pattern
if cy < -0.06 and abs(cx) < 0.04 and 1.10 < cz < 1.40:
    return False  # use this with a second material slot for color contrast
```

---

## Loose-garment alternatives

The body-topo pattern works for tight-fitting garments. For loose ones, use:

| Garment type | Method |
|---|---|
| Pleated skirt, A-line | **Procedural-polar sampling** (radially symmetric — the one place polar math works first try) |
| Cape, robe, dress with skirt | **Cloth simulation** (Blender's Cloth physics, baked to mesh) |
| Jacket, hoodie (loose but body-attached) | **Body-topo with larger push distance** (15-25mm instead of 6mm) + Solidify thickness 8-12mm |
| Belt, strap, harness (rigid accessory) | **Shrinkwrap modifier** + small mesh modeled separately, projected onto body surface |

---

## Debugging a bad garment

**Visible vertical seam down the spine** — you skipped merge-by-distance. Re-run with step 2 in place.

**Floating triangle pieces near sleeves/cuffs** — increase `min_island_size` (step 6) or tighten cut conditions to not leave strays.

**Stair-step edge along a diagonal cut** — increase `smooth_passes` (step 5). Default is 6; bump to 10 for sharper diagonals.

**Garment clipping into body during animation** — increase `push_distance` (step 4). 6mm is for tight garments; 10-15mm for medium fit.

**Garment looks "papery" in raking light** — increase `solidify_thickness` (step 8). 4mm is a minimum; bump to 6-8mm for thicker fabric.

**Fabric pinches at joints during animation** — wrong modifier order. Verify Solidify comes AFTER Armature in the stack.

**Whole garment vanishes during animation** — your base mesh's Armature modifier wasn't carried over. Check `garment.modifiers` includes both Armature and Solidify.

**Vertex weights don't match the body** — you probably modified vertex groups manually. Re-duplicate the body and don't touch the vertex groups; let them inherit.
