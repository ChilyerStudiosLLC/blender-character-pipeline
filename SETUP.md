# Setup

One-time setup to run the examples in this repo. Should take ~15 minutes if you don't already have Blender.

---

## Prerequisites

| What | Version | Notes |
|---|---|---|
| **Blender** | 5.1+ (or 4.2 LTS) | The example scripts use the 5.x Python API. 4.2 likely works for the body-topo pattern but is untested by me. |
| **Python knowledge** | Beginner | You'll read and tweak the build scripts — no need to write Python from scratch. |
| **OS** | Windows, Mac, or Linux | All scripts use forward-slash paths or `os.path.join` so they're platform-portable. The example paths in docs are Windows because that's my dev box. |

**Recommended but optional:**
- A Godot 4 installation, to verify the .glb output round-trips into a real game engine.
- Familiarity with Blender's modifier stack and how Edit Mode / Object Mode differ. The body-topo pattern uses both.

---

## Step 1 — Clone this repo

```bash
git clone https://github.com/ChilyerStudiosLLC/blender-character-pipeline.git
cd blender-character-pipeline
```

---

## Step 2 — Download the Quaternius base meshes

The examples use the **Universal Base Characters [Standard]** pack from Quaternius. Released under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) (Public Domain Dedication) — free, no attribution required. I don't redistribute the files here so you always get the latest version from source; attribution and a Patreon contribution are nice if these assets help you ship:

1. Visit **https://quaternius.com** and look for the **Universal Base Characters** pack
2. Download the **Standard** (free) version. There's also a **Source** version (paid, includes rigged .blends + Unity/Unreal/Godot project setups with custom shaders) — the free Standard pack is sufficient for this repo's examples.
3. Unzip somewhere on your machine
4. Note the path to `Base Characters/Godot - UE/Superhero_Male_FullBody.gltf` (and `Superhero_Female_FullBody.gltf` if you want to use the female base)

If you find this pack useful, consider [supporting Quaternius on Patreon](https://www.patreon.com/quaternius). The free CC0 release is genuinely generous for solo devs and worth giving back to.

Then tell the example scripts where the base mesh is. **Edit `examples/football_uniform/build.py`** and update the constant at the top:

```python
SUPERHERO_MALE_GLTF = r"C:\path\to\Quaternius\Universal Base Characters[Standard]\Base Characters\Godot - UE\Superhero_Male_FullBody.gltf"
```

Use the actual path from where you unzipped. Forward slashes work fine on Windows too.

---

## Step 3 (optional) — MakeHuman, for proportion-reference workflows

This is **only needed if you want to use MakeHuman-generated bodies as 3D proportion references** when sculpting your characters. The body-topo costume pipeline doesn't need it.

If you do want it:

1. Install **MakeHuman desktop application** from http://www.makehumancommunity.org/ — this gives you the asset library (skins/hair/clothes/eyes/teeth/poses).
2. Run MakeHuman once to populate the user data folder (typically `~/Documents/makehuman/v1py3/` on Windows; check `Files → Export → User data location` in the app for your platform's path).
3. Install the **MPFB Blender addon** from https://github.com/makehumancommunity/mpfb2 — this brings MakeHuman content into Blender as live-editable assets.
4. In Blender, open **Edit → Preferences → Add-ons → MPFB Settings** and set `mh_user_data` to the path from step 2.

See `docs/proportion-reference-workflow.md` (TODO) for how to use MPFB output as a Blender reference object — it does **not** enter the game directly; rig and topology are incompatible.

---

## Step 4 — Verify it works

Run the football uniform example from a terminal:

```bash
blender --background --python examples/football_uniform/build.py
```

Replace `blender` with the full path to your Blender executable if it's not on PATH (e.g., `"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"` on Windows).

Expected output:
- `examples/football_uniform/output/Lineman_Footballer.blend` — Blender source file
- `examples/football_uniform/output/Lineman_Footballer.glb` — game-ready glTF
- `examples/football_uniform/renders/silhouette_front.png` and friends — silhouette gate renders
- Console output ending with `BUILD COMPLETE` (or a clear error message)

If it runs end-to-end and produces a .glb you can open in any glTF viewer (e.g., https://gltf-viewer.donmccurdy.com/), you're set up.

---

## Step 5 (optional) — Drop into Godot

If you have Godot 4 installed:

1. Create a new Godot project (or open an existing one)
2. Drag `Lineman_Footballer.glb` into the project's `res://` folder
3. Drag the imported scene into a 3D scene
4. Press F5 to play — character should appear, T-pose, materials applied

Animation rebinding to your project's animation library is its own topic; not covered here.

---

## Troubleshooting

**`blender: command not found`** — Blender isn't on your PATH. Use the full path to the executable, or add Blender's install directory to PATH.

**`Cannot load empty file name` errors during glTF import** — your `SUPERHERO_MALE_GLTF` path is wrong. Check Step 2 carefully.

**`bpy.context.object is None`** — you're running interactive Blender scripts that need a UI context but launched headless without one. The build scripts in this repo handle this; if you adapt them and hit this, look up Blender's `temp_override` API.

**The script produces a `.glb` but the character looks wrong** — most common cause is the base mesh has unmerged centerline doubles. The build script's `body_topo.py` helper handles this with a "merge by distance" step. If you're using a different base mesh, ensure step 2 of the body-topo recipe runs.

**More than one shader node tex image used for a texture warnings during export** — cosmetic, doesn't block import. Comes from the Quaternius base material having multi-image texture setups that the glTF exporter collapses imperfectly. Visual difference in Godot is minor (single-image rendering instead of multi-layer). Fix by manually simplifying the material if it bothers you.

---

## Asking for help

GitHub Issues on the repo. Include:
- Your OS + Blender version
- The exact command you ran
- Full console output (paste, don't paraphrase)
- Whether you got partway through and where it broke

If it's a feature request rather than a bug, frame it that way in the title.
