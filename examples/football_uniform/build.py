"""
build.py — Football uniform example, reproducible end-to-end.

Takes the Quaternius Superhero_Male base mesh and produces a game-ready
football player with body-topo costume pieces. Outputs:
  - Lineman_Footballer.blend (Blender source file)
  - Lineman_Footballer.glb   (game-ready glTF, ready to drop into Godot)
  - renders/silhouette_*.png (silhouette gate verification renders)

USAGE
=====

    blender --background --python build.py

The first thing you'll want to do is update SUPERHERO_MALE_GLTF below to
point at your local download of the Quaternius base meshes — see SETUP.md
in the repo root.

WHAT THIS SCRIPT DEMONSTRATES
==============================

1. Phase B Stage 1: Import the Superhero_Male base mesh from glTF, prune
   any extras, save as a fresh .blend
2. Phase B Stage 2: Apply gross proportion edits via a lattice cage
   (taller character, slight V-taper at waist), then apply + remove the
   lattice
3. Phase B Stage 3: Silhouette gate — render front/side/3-quarter in
   pure-black-on-white as a visibility check
4. Phase B Stage 3 (costume): Build a jersey, pants, and socks using the
   body-topo pattern (one piece at a time)
5. Phase B Stage 3 (jersey number): Create a 3D text "7" and shrinkwrap it
   onto the chest as a decal
6. Phase B Stage 5: Export the final character as glTF with
   `export_animation_mode='ACTIVE_ACTIONS'` per the project's CLAUDE.md

The Phase A spec for this character (which would normally live in a
separate SPEC.md) is implicit in the parameters below — a heavyset adult
male football player with a black jersey, gold pants, white socks, number
"7" on the chest, slight Coraline-DNA proportion stretching.

REPRODUCIBILITY
===============

Same input + same script → same output. Vertex counts and final geometry
should match across runs. Render shading varies slightly with Blender
version (5.1 was the test target).

LICENSE
=======

MIT — see LICENSE in the repo root. The Quaternius base meshes you point
this script at are CC0 1.0 (Public Domain Dedication). The output meshes
this script produces are also free to use under MIT.
"""

import math
import os
import sys

# ────────────────────────────────────────────────────────────────────
# 1. Path setup — point this at YOUR local Quaternius pack
# ────────────────────────────────────────────────────────────────────

# EDIT THIS to where you unzipped the Quaternius Universal Base Characters pack.
# Get the pack from https://quaternius.com (CC0 license — see SETUP.md).
SUPERHERO_MALE_GLTF = os.environ.get(
    "SUPERHERO_MALE_GLTF",
    r"C:\path\Blender\Characters\Universal Base Characters[Standard]\Base Characters\Godot - UE\Superhero_Male_FullBody.gltf",
)

# Where to put the build output. Defaults to next to this script.
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
RENDERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders")

# ────────────────────────────────────────────────────────────────────
# 2. Make the repo's `scripts/` package importable
# ────────────────────────────────────────────────────────────────────

# When this script runs via `blender --background --python build.py`, the
# working directory is wherever you launched from. Make sure `scripts/`
# can be imported regardless of cwd.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from scripts.body_topo import build_bodytopo_garment, report  # noqa: E402
from scripts.headless_import import import_gltf_base  # noqa: E402
from scripts.lattice_setup import (  # noqa: E402
    add_proportion_lattice,
    apply_lattice_to_meshes,
)


# ────────────────────────────────────────────────────────────────────
# 3. Build parameters — change these to make a different character
# ────────────────────────────────────────────────────────────────────

CHARACTER_NAME = "Lineman_Footballer"

# Costume colors
JERSEY_BLACK = (0.04, 0.04, 0.04, 1.0)   # not pure 0; reads better in PBR
PANTS_GOLD = (1.00, 0.75, 0.00, 1.0)
SOCKS_WHITE = (0.95, 0.95, 0.95, 1.0)
NUMBER_WHITE = (0.95, 0.95, 0.95, 1.0)

# Proportion edits (applied as a lattice block-shift).
# These are DELIBERATELY MILD for this example — the goal is to demonstrate
# the lattice workflow without producing a wildly stretched character.
# Realistic values for your own characters depend heavily on what base
# mesh you start with: leaner bases (like Quaternius Superhero) tolerate
# only small deltas before they look elongated. Bulkier bases can handle
# larger shifts.
#
# For more dramatic Coraline-style proportions, push these to 0.05-0.08
# and combine with sculpt-mode work to tighten the joints. See
# docs/lattice-proportions.md for the full discussion.
UPPER_BODY_LIFT = 0.015  # +1.5cm: very subtle upper-body raise
LOWER_BODY_DROP = 0.010  # -1cm: very subtle leg lengthening
WAIST_PINCH = 0.020      # 2cm V-taper at waist X-extremes

# Cut conditions per garment (face-center predicates)
# These define what "jersey" / "pants" / "socks" each MEAN on this body.
def jersey_keep(cx, cy, cz):
    """Black short-sleeve jersey: upper hip to neck base, mid-bicep sleeve."""
    if not (0.95 <= cz <= 1.55):
        return False
    if abs(cx) > 0.45:
        return False
    return True


def pants_keep(cx, cy, cz):
    """Gold pants: waist down to mid-shin."""
    if not (0.22 <= cz <= 0.95):
        return False
    return True


def socks_keep(cx, cy, cz):
    """White socks: just above ankle to slightly above where pants end."""
    if not (0.05 <= cz <= 0.27):
        return False
    return True


# ────────────────────────────────────────────────────────────────────
# 4. Build phases — each stage is a separate function so you can comment
#    out individual stages while debugging.
# ────────────────────────────────────────────────────────────────────


def stage_1_import_base():
    """Stage 1: Import Superhero_Male, prune extras, return key references."""
    print("\n=== STAGE 1: Import base mesh ===")

    if not os.path.exists(SUPERHERO_MALE_GLTF):
        raise FileNotFoundError(
            f"Quaternius base mesh not found at:\n  {SUPERHERO_MALE_GLTF}\n\n"
            f"Edit the SUPERHERO_MALE_GLTF constant at the top of build.py "
            f"to point at your local Quaternius pack. See SETUP.md."
        )

    result = import_gltf_base(
        gltf_path=SUPERHERO_MALE_GLTF,
        keep_object_names=("SuperHero_Male", "Eyes", "Eyebrows"),
    )
    print(f"  Imported, kept: {result['kept']}")
    print(f"  Removed extras: {result['removed']}")
    if result["bbox"]:
        bb_min, bb_max = result["bbox"]
        print(f"  Body bbox z: {bb_min[2]:.2f} → {bb_max[2]:.2f} ({bb_max[2]-bb_min[2]:.2f}m tall)")

    body = bpy.data.objects["SuperHero_Male"]
    eyes = bpy.data.objects.get("Eyes")
    eyebrows = bpy.data.objects.get("Eyebrows")
    armature = bpy.data.objects.get("Armature")
    return body, eyes, eyebrows, armature


def stage_2_proportions(body, eyes, eyebrows):
    """Stage 2: Apply lattice-based proportion edits (taller, V-taper)."""
    print("\n=== STAGE 2: Proportion editing (lattice) ===")

    # Lattice over body + eyes + eyebrows so they all deform together
    lattice = add_proportion_lattice(
        primary=body,
        deformed_meshes=[body, eyes, eyebrows] if eyes and eyebrows else [body],
        name="ProportionLattice",
    )
    lat_data = lattice.data
    PU, PV, PW = lat_data.points_u, lat_data.points_v, lat_data.points_w

    def pt(u, v, w):
        return lat_data.points[u + v * PU + w * PU * PV]

    # Upper body block-lift (W=4..8)
    for w_layer in [4, 5, 6, 7, 8]:
        for u in range(PU):
            for v in range(PV):
                p = pt(u, v, w_layer)
                p.co_deform.z = p.co.z + UPPER_BODY_LIFT

    # Lower body block-drop (W=0..3)
    for w_layer in [0, 1, 2, 3]:
        for u in range(PU):
            for v in range(PV):
                p = pt(u, v, w_layer)
                p.co_deform.z = p.co.z - LOWER_BODY_DROP

    # Waist X-pinch (W=4 only, U=0 and U=PU-1)
    for v in range(PV):
        p_left = pt(0, v, 4)
        p_left.co_deform.x = p_left.co.x + WAIST_PINCH
        p_right = pt(PU - 1, v, 4)
        p_right.co_deform.x = p_right.co.x - WAIST_PINCH

    print(f"  Upper body lifted +{UPPER_BODY_LIFT}m (W=4..8 block)")
    print(f"  Lower body dropped -{LOWER_BODY_DROP}m (W=0..3 block)")
    print(f"  Waist pinched ±{WAIST_PINCH}m (W=4 X-extremes)")

    bpy.context.view_layer.update()

    # Bake the deformation into geometry and remove the lattice — the
    # proportion edits are now permanent in the meshes.
    apply_lattice_to_meshes([body, eyes, eyebrows] if eyes and eyebrows else [body])
    bpy.data.objects.remove(lattice, do_unlink=True)
    print(f"  Lattice applied + removed")


def stage_5_silhouette_gate(body, costumes, armature):
    """Silhouette gate: render flat-black silhouettes of the dressed
    character for the visibility check, plus a full-color review render.

    Runs AFTER costume + decals so the dressed silhouette reflects what
    will actually appear in-game. (The body-only silhouette earlier is
    a separate validation step you'd do during proportion editing.)
    """
    print("\n=== STAGE 5 (gate): Silhouette + review renders ===")
    os.makedirs(RENDERS_DIR, exist_ok=True)

    scene = bpy.context.scene

    # Hide armature so bones don't render in any of these passes
    if armature:
        armature.hide_render = True

    # Compute current body bbox center for camera aim
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body_eval = body.evaluated_get(depsgraph)
    verts_world = [body_eval.matrix_world @ v.co for v in body_eval.data.vertices]
    cz = (min(v.z for v in verts_world) + max(v.z for v in verts_world)) / 2

    # Camera setup (or reuse existing)
    cam = bpy.data.objects.get("ReviewCam")
    if cam is None:
        bpy.ops.object.camera_add(location=(0, -3.5, cz))
        cam = bpy.context.active_object
        cam.name = "ReviewCam"
    scene.camera = cam

    def aim_at(target_z, cam_loc):
        cam.location = cam_loc
        direction = Vector((0, 0, target_z)) - cam.location
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    # === Silhouette renders (Workbench, flat-black) ====================
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.0, 0.0, 0.0)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (1.0, 1.0, 1.0)

    scene.render.resolution_x = 500
    scene.render.resolution_y = 800

    for view_name, loc in [
        ("silhouette_front", (0, -3.5, cz)),
        ("silhouette_side", (3.5, 0, cz)),
        ("silhouette_3q", (2.0, -2.7, cz)),
    ]:
        aim_at(cz, loc)
        scene.render.filepath = os.path.join(RENDERS_DIR, f"{view_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  Rendered: {view_name}.png")

    # === Full-color review render (EEVEE, lit) =========================
    # Restore visibility on armature won't affect render (already hide_render)
    # but we use a different engine + lights here.
    scene.render.engine = 'BLENDER_EEVEE'

    # Add a sun light for the color render
    if not any(o.type == 'LIGHT' for o in bpy.context.scene.objects):
        bpy.ops.object.light_add(type='SUN', location=(2, -3, 4))
        bpy.context.object.data.energy = 3.0

    # Set world background to a neutral grey
    if not scene.world:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    nt = scene.world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs[0].default_value = (0.65, 0.65, 0.7, 1.0)
    bg.inputs[1].default_value = 1.5
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs[0])

    scene.render.resolution_x = 700
    scene.render.resolution_y = 1100
    aim_at(cz, (0.8, -3.0, cz + 0.15))  # slight 3/4-ish framing for the hero shot
    scene.render.filepath = os.path.join(RENDERS_DIR, "final_review.png")
    bpy.ops.render.render(write_still=True)
    print(f"  Rendered: final_review.png")

    # Restore for export downstream
    if armature:
        armature.hide_render = False


def stage_4_costume(body):
    """Stage 4: Build jersey, pants, socks using the body-topo pipeline."""
    print("\n=== STAGE 4: Costume pieces (body-topo) ===")

    jersey = build_bodytopo_garment(
        body_obj=body,
        name="Jersey",
        keep_face=jersey_keep,
        base_color=JERSEY_BLACK,
    )
    print(f"  {report(jersey)}")

    pants = build_bodytopo_garment(
        body_obj=body,
        name="Pants",
        keep_face=pants_keep,
        base_color=PANTS_GOLD,
    )
    print(f"  {report(pants)}")

    socks = build_bodytopo_garment(
        body_obj=body,
        name="Socks",
        keep_face=socks_keep,
        base_color=SOCKS_WHITE,
        solidify_thickness=0.003,  # socks are thinner than other fabric
    )
    print(f"  {report(socks)}")

    return jersey["object"], pants["object"], socks["object"]


def stage_5_jersey_number(jersey_obj, armature):
    """Stage 5: Add a "7" text decal shrinkwrapped onto the jersey chest."""
    print("\n=== STAGE 5: Jersey number 7 (text + shrinkwrap + rig) ===")

    # Create 3D text in front of the chest
    bpy.ops.object.text_add(location=(0, -0.30, 1.25))
    num = bpy.context.active_object
    num.name = "Jersey_Number_7"
    num.data.body = "7"
    num.data.size = 0.22
    num.data.extrude = 0.003
    num.data.align_x = 'CENTER'
    num.data.align_y = 'CENTER'
    num.data.fill_mode = 'BOTH'

    # Rotate to face -Y (forward, where the camera is)
    num.rotation_euler = (math.radians(90), 0, 0)

    # Convert text → mesh
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Shrinkwrap onto jersey surface
    sw = num.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
    sw.target = jersey_obj
    sw.wrap_method = 'PROJECT'
    sw.use_project_y = True
    sw.use_positive_direction = True
    sw.use_negative_direction = True
    sw.offset = 0.004  # 4mm above jersey surface
    bpy.ops.object.modifier_apply(modifier=sw.name)

    # White material
    num.data.materials.clear()
    mat = bpy.data.materials.new(name="Number_Material")
    mat.use_nodes = True
    p = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = NUMBER_WHITE
    p.inputs["Roughness"].default_value = 0.45
    num.data.materials.append(mat)

    # Rig: parent to armature, weight all verts to spine_03 (chest bone)
    if armature is not None:
        num.parent = armature
        num.matrix_parent_inverse = armature.matrix_world.inverted()
        arm_mod = num.modifiers.new(name="Armature", type='ARMATURE')
        arm_mod.object = armature

        # Single-bone weight: try spine_03, fall back to last spine bone
        bone_name = "spine_03"
        if bone_name not in [b.name for b in armature.data.bones]:
            spines = [b.name for b in armature.data.bones if "spine" in b.name.lower()]
            bone_name = spines[-1] if spines else "spine_01"

        vg = num.vertex_groups.new(name=bone_name)
        vg.add(list(range(len(num.data.vertices))), 1.0, 'REPLACE')
        print(f"  Number weighted to bone '{bone_name}'")

    print(f"  Number 7: {len(num.data.vertices)} verts, {len(num.data.polygons)} polys")
    return num


def stage_6_export(body, costumes, armature):
    """Stage 6: Save .blend + export game-ready .glb."""
    print("\n=== STAGE 6: Save + export ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    blend_path = os.path.join(OUTPUT_DIR, f"{CHARACTER_NAME}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"  Saved: {blend_path} ({os.path.getsize(blend_path)/1024/1024:.1f} MB)")

    # Select rig + all costume meshes for export
    bpy.ops.object.select_all(action='DESELECT')
    if armature:
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
    body.select_set(True)
    for o in costumes:
        if o:
            o.select_set(True)

    glb_path = os.path.join(OUTPUT_DIR, f"{CHARACTER_NAME}.glb")

    # IMPORTANT: export_animation_mode='ACTIVE_ACTIONS' — see CLAUDE.md
    # in any consumer project. Default 'ACTIONS' exports every orphan in
    # bpy.data.actions which produces duplicate animations in the .glb.
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_selection=True,
        export_apply=True,                      # bake remaining modifiers (Solidify)
        export_yup=True,                        # glTF + Godot convention
        export_animations=False,                # bind pose only, no animations
        export_animation_mode='ACTIVE_ACTIONS',
        export_skins=True,
        export_morph=False,
        export_materials='EXPORT',
        export_image_format='AUTO',
        export_normals=True,
        export_tangents=True,
    )
    print(f"  Exported: {glb_path} ({os.path.getsize(glb_path)/1024/1024:.1f} MB)")


# ────────────────────────────────────────────────────────────────────
# 5. Orchestration — run all stages in sequence
# ────────────────────────────────────────────────────────────────────


def main():
    print(f"BUILD START — {CHARACTER_NAME}")
    print(f"  Base mesh: {SUPERHERO_MALE_GLTF}")
    print(f"  Output dir: {OUTPUT_DIR}")

    body, eyes, eyebrows, armature = stage_1_import_base()
    stage_2_proportions(body, eyes, eyebrows)
    jersey, pants, socks = stage_4_costume(body)
    number = stage_5_jersey_number(jersey, armature)
    stage_5_silhouette_gate(body, [jersey, pants, socks, number], armature)
    stage_6_export(body, [jersey, pants, socks, number, eyes, eyebrows], armature)

    print("\nBUILD COMPLETE")
    print(f"  → {os.path.join(OUTPUT_DIR, CHARACTER_NAME + '.blend')}")
    print(f"  → {os.path.join(OUTPUT_DIR, CHARACTER_NAME + '.glb')}")
    print(f"  → silhouette renders in {RENDERS_DIR}")


if __name__ == "__main__":
    main()
