# Lattice Proportion Editing

A Lattice cage with coarse control points is the right tool for **gross proportion changes** — taller, narrower-waisted, larger-headed. Sculpt mode is the right tool for **fine details**. Use both, in this order.

This document covers the lattice approach: how to set it up, how to edit it without making the side view weird, and how to commit the changes to geometry.

---

## When to use lattice vs sculpt

| | **Lattice** | **Sculpt** |
|---|---|---|
| Strengths | Predictable, repeatable, fast for large changes, affects many meshes at once via shared modifier | Fine-grained per-vertex control, expressive, no axis-lock discipline needed |
| Weaknesses | Coarse — can't isolate small regions (e.g., "make just the cheekbones higher") | No predictability — every artist's sculpt is different |
| Time per edit | Seconds | Minutes for fine work, hours for large changes |
| Use for | Limb length, waist taper, head scaling, character height | Face details, muscle definition, asymmetry, hands/feet detail |

**Workflow:** lattice first to set the gross proportions, then apply the lattice (bake into geometry), then sculpt for refinement. Don't try to do everything in one or the other.

---

## Setup

`scripts/lattice_setup.py` provides `add_proportion_lattice(...)` — call once with your body + all the meshes you want to deform together:

```python
from scripts.lattice_setup import add_proportion_lattice

body = bpy.data.objects["SuperHero_Male"]
all_meshes = [body, eyes, eyebrows, shirt, pants, socks, decals]

lattice = add_proportion_lattice(
    primary=body,
    deformed_meshes=all_meshes,
    name="ProportionLattice",
)
```

Defaults: 5×5×9 control points, 10% X margin around body width, 20% Y margin around body depth, 5% Z margin around body height. Linear interpolation between control points.

After this call:
- A wireframe lattice cage appears around the body, drawn in front of geometry
- Each deformed mesh has a `ProportionLattice` modifier at the top of its stack (before Armature)
- All meshes deform together when you grab control points

### Why 5×5×9?

The W axis (vertical) has more layers than U/V because a humanoid body is taller than it is wide. With 9 W layers and a 1.8m body:

| W layer | Z height | Body region |
|---|---|---|
| W=0 | 0.00 | Feet |
| W=1 | 0.225 | Ankle |
| W=2 | 0.45 | Knee |
| W=3 | 0.675 | Mid-thigh |
| W=4 | 0.90 | Waist / hip |
| W=5 | 1.125 | Lower chest |
| W=6 | 1.35 | Chest |
| W=7 | 1.575 | Shoulders |
| W=8 | 1.80 | Top of head |

That's about one control row per anatomical region. Lifting "W=8" lifts the top of the head. Lifting "all of W=4..8 as a block" stretches the upper body upward (longer torso). Lifting "W=4 only" pulls just the waist (looks like an unnatural barrel shape — usually you want block shifts, not single-layer lifts).

The `scripts.lattice_setup.w_layer_for_anatomy(...)` helper gives you the layer index for a given anatomical region name, so you can write `lift_layer = w_layer_for_anatomy("shoulders", ...)` instead of memorizing numbers.

### Why scale lattice DATA, not lattice OBJECT?

This is a non-obvious Blender gotcha. The intuitive approach to sizing a lattice is:

```python
lattice = bpy.data.objects.new("Lattice", lat_data)
lattice.scale = (sx, sy, sz)
bpy.ops.object.transform_apply(scale=True)  # bake the scale
```

This is **wrong** for two reasons:
1. `transform_apply` is unreliable in headless `--background` mode
2. It scales `point.co` (rest position) but NOT `point.co_deform` (deformed position) — creating a mismatch the Lattice modifier reads as "this lattice is pre-deformed," producing baseline deformation before you've moved any control point

The correct approach (used by `add_proportion_lattice`):

```python
scale_matrix = mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
lat_data.transform(scale_matrix)  # scales BOTH co and co_deform together
```

Result: `co == co_deform` at startup → zero baseline deformation → the meshes look correct before you've edited anything.

---

## Editing the lattice

This is where most of the time goes. Open Blender, select the lattice object, press `Tab` to enter Edit Mode. The 225 control points (for 5×5×9) appear as small dots.

### Axis-lock discipline (MANDATORY)

When you press `G` to grab control points, **always immediately press an axis key** to constrain the motion:

- `G` then `Z` — vertical motion only (stretch height, lift a layer)
- `G` then `X` — horizontal motion only (pinch waist, widen shoulders)
- `G` then `Y` — front/back motion (rarely useful)

If you press `G` without an axis key, Blender will track free 3D motion. The mouse cursor only moves in 2D, so you're really moving in the camera-plane — which means whichever direction is "into the screen" gets motion you didn't intend.

**Consequence of skipping axis lock:** You make changes that look correct in front view but produce a stretched skull in side view. This is the single most common lattice mistake. The fix is to view from multiple angles before committing — see [the front+side rule](#the-frontside-rule) below.

### Useful selection patterns

- **`A`** — select all (clears all deformation when combined with `Alt+G`)
- **`Alt+A`** — deselect all
- **`B` then drag a box** — box-select (great for "select all of W=4 layer" via top-orthographic view)
- **`C` then click points** — circle-select (good for selecting a contiguous region)
- **`Shift+click`** — toggle individual point selection

### Common edits

```python
# Lift the upper body as a block (longer torso, lifted head)
# All control points in layers W=4..8, shift Z by +0.06m
for w in [4, 5, 6, 7, 8]:
    for u in range(POINTS_U):
        for v in range(POINTS_V):
            p = lat_data.points[u + v*POINTS_U + w*POINTS_U*POINTS_V]
            p.co_deform.z = p.co.z + 0.06

# Lower the lower body as a block (longer legs)
for w in [0, 1, 2, 3]:
    for u in range(POINTS_U):
        for v in range(POINTS_V):
            p = lat_data.points[u + v*POINTS_U + w*POINTS_U*POINTS_V]
            p.co_deform.z = p.co.z - 0.04

# Pinch waist X-extremes inward (V-taper)
for v in range(POINTS_V):
    # Leftmost column (U=0)
    p = lat_data.points[0 + v*POINTS_U + 4*POINTS_U*POINTS_V]
    p.co_deform.x = p.co.x + 0.04  # toward center
    # Rightmost column (U=POINTS_U-1)
    p = lat_data.points[(POINTS_U-1) + v*POINTS_U + 4*POINTS_U*POINTS_V]
    p.co_deform.x = p.co.x - 0.04  # toward center
```

You can do this in the UI by box-selecting the relevant layer, pressing `G` then the axis, typing a numeric value, pressing Enter.

### The front+side rule

**Always view from two orthographic angles when editing.** Split the Blender viewport (drag from a corner) so you have Front view (`Numpad 1`) on one side and Right view (`Numpad 3`) on the other. Make edits, see both views update live.

Most lattice mistakes look fine from the front and are obviously wrong from the side. The front+side split makes the wrong ones impossible to miss.

### Reset deformation without removing the lattice

```python
from scripts.lattice_setup import reset_lattice
reset_lattice(lattice_obj)  # snaps all co_deform back to co
```

Equivalent to selecting all points in Edit Mode and pressing `Alt+G` (clear location).

---

## Committing the deformation to geometry

Once you're happy with proportions:

```python
from scripts.lattice_setup import apply_lattice_to_meshes

apply_lattice_to_meshes([body, eyes, eyebrows, shirt, pants, ...])
# Now delete the lattice object — it's no longer needed
bpy.data.objects.remove(lattice_obj, do_unlink=True)
```

`apply_lattice_to_meshes` iterates each mesh, finds its Lattice modifier, and applies it (baking the deformation into the mesh data).

**Why apply before glTF export?** glTF doesn't preserve Lattice modifiers as runtime deformers. If you skip the apply step and export, the meshes export at their *rest* position — your proportion edits are silently dropped. Applying before export bakes them into the geometry permanently, so they survive.

**`export_apply=True` does this automatically.** The glTF exporter has an option `export_apply` that applies all non-Armature modifiers (including Lattice) before export. If you set that to True in your export call, you don't strictly need to call `apply_lattice_to_meshes` first — but applying explicitly is cleaner and lets you verify the result before committing to the export.

---

## When NOT to use a lattice

- **Asymmetric edits.** A lattice is inherently symmetric across the centerline if your body bbox is centered. For "this character has a hunched left shoulder," sculpt instead.
- **Localized fine details.** A 5×5 X resolution can't isolate "just the bridge of the nose." Sculpt for that.
- **Single-axis stretches you'd rather do via mesh scale.** If you want the whole character 10% taller without changing proportions, set the object's `scale.z = 1.1` and apply transform. A lattice is overkill.

---

## Debugging lattice-edited meshes

**Side view looks wrong** — you broke axis-lock discipline. Look at which lattice layers have non-zero Y deformation in `co_deform - co` and reset their Y components.

**Garment detached from body** — one mesh didn't get the Lattice modifier added. Check `mesh.modifiers` for each costume piece; they should all have ProportionLattice at index 0.

**Deformation is mirrored / inverted** — you scaled the lattice OBJECT instead of the lattice DATA. Re-build the lattice using `add_proportion_lattice`.

**Lattice has no effect** — modifier is in the wrong stack position (after Armature instead of before), or `lattice.modifier.object` doesn't point to the lattice object.

**Lattice applied but mesh is still deformed at "rest"** — you have `co != co_deform` somewhere. Run `reset_lattice(lat_obj)` then re-apply.
