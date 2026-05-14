# Blender Character Pipeline

A reproducible workflow for authoring game-ready stylized 3D characters in Blender, with AI assistance for the procedural parts and human-in-the-loop for the art parts. Built around a **shared base mesh + body-topology costume pipeline + stop-and-validate stage gates**.

This is a **skill-showcase repo by [Chilyer Studios LLC](https://github.com/ChilyerStudiosLLC)** — built while developing a solo-dev Godot 4 game. The patterns here solved real problems on that game; the code here is what survived after the false starts. Documenting it so other indie devs can skip the false-start cost, and so technical-artist hiring managers can see how I think.

> ⚠️ **This repo is a workflow demonstration, not an asset pack.** You get scripts, docs, and a working example that produces a game-ready character. You bring your own base mesh and (optionally) MakeHuman asset library — see [SETUP.md](SETUP.md). I won't redistribute base meshes or community art here for licensing-cleanliness reasons.

![Example output character](examples/football_uniform/renders/final_review.png)

*The included example: Quaternius Superhero_Male base + body-topo jersey/pants/socks + lattice-tuned proportions + glTF export. One Python script, ~5 seconds, end to end. See [examples/football_uniform/](examples/football_uniform/).*

---

## What's novel about this

Most "make a 3D character" tutorials are 8-hour video click-alongs. The actual pipeline used by indie studios is more like this:

1. **Lock the spec before opening Blender.** 6 design questions answered in writing first — style ref, proportions, silhouette intent, personality, animation intent, what to skip for v1. No spec = bad character.
2. **Costume topology is inherited from body topology**, not authored from scratch. Duplicate the body mesh, cull faces by predicate, smooth the boundary, solidify for thickness. Vertex weights inherited automatically. The garment fits and animates correctly the moment it exists.
3. **Stop and validate at every stage.** Silhouette gate (does the black-on-white shape read as the character?) before texture work. Texture validation before rig binding. Rig validation against one real animation before declaring the character done.
4. **AI handles the procedural parts**, the human handles the art. Cut conditions, lattice math, modifier stacks, glTF export — all scripted. Sculpting, palette choices, costume-detail decisions — human in Blender directly.

The combination of these — shared base, body-topo costumes, stage gates, AI-assisted procedural authoring — is what I haven't seen documented as a single workflow anywhere public.

---

## Example: from base mesh to game-ready in one build script

`examples/football_uniform/build.py` is a reproducible script that takes the Quaternius Superhero_Male base mesh and produces a game-ready football player: black jersey with white "7", gold pants, white socks, all body-topo costume meshes parented to the 65-bone UE Mannequin rig, exported as a `.glb` ready to drop into any Godot 4 project.

| File | What |
|---|---|
| `examples/football_uniform/build.py` | The whole pipeline as one runnable Python script |
| `examples/football_uniform/renders/` | Front + side + 3/4 + silhouette renders of the output |
| `examples/football_uniform/output/Lineman_Footballer.glb` | The game-ready character |

Run it via `blender --background --python build.py` (after SETUP.md). The script is heavily commented as a walkthrough.

---

## The pipeline at a glance

```
Phase A — Spec session            (no Blender)
   │  6 questions answered in writing → SPEC.md
   ▼
Phase B — Build session            (Blender)
   ├─ 1. Import shared base mesh    (Quaternius Superhero, 65-bone UE rig)
   ├─ 2. Proportion editing          (lattice cage for gross, sculpt for fine)
   ├─ 3. Silhouette gate ⚠          (render flat-black; abort if it doesn't read)
   ├─ 4. Costume — one piece at a time, body-topo pipeline:
   │     a. duplicate body
   │     b. merge by distance        (CRITICAL — base ships with unmerged centerline)
   │     c. cull faces by predicate
   │     d. push along normals +6mm
   │     e. Laplacian smooth boundary 6×
   │     f. remove small islands
   │     g. push boundary +2mm
   │     h. solidify modifier
   │     i. material
   ├─ 5. Rig verify ⚠               (load one real animation, watch it deform)
   └─ 6. glTF export with ACTIVE_ACTIONS mode
```

Full recipe with the math: [docs/body-topo-recipe.md](docs/body-topo-recipe.md).

---

## Repo layout

```
.
├── README.md                       (this file)
├── SETUP.md                        (one-time setup — Blender + base mesh download)
├── LICENSE                         (MIT)
├── docs/
│   ├── two-phase-workflow.md       (Phase A spec session + Phase B build session)
│   ├── body-topo-recipe.md         (the 9-step pattern, with math + gotchas)
│   ├── lattice-proportions.md      (lattice cage setup + axis-lock discipline)
│   └── ai-assisted-howto.md        (using LLM coding assistants productively for this)
├── scripts/
│   ├── body_topo.py                (build_bodytopo_garment helper)
│   ├── lattice_setup.py            (add_proportion_lattice helper)
│   └── headless_import.py          (glTF base import via Blender CLI)
└── examples/
    └── football_uniform/
        ├── README.md               (this example, walkthrough)
        ├── build.py                (full pipeline as one script)
        ├── renders/                (output renders)
        └── output/                 (the .blend + .glb the build produces)
```

---

## Who this is for

- **Indie game devs** (especially Godot users) who hit the wall trying to build characters from joined primitives and want a way out
- **Solo devs** who want to ship a playable prototype with placeholder characters before investing in art quality
- **Technical artists** evaluating my work — the engineering decisions, gotchas-documented-with-receipts, and pipeline thinking are what to look at
- **Anyone using AI coding assistants for 3D work** — the patterns for stop-and-validate gates and human/AI division of labor transfer beyond Blender

---

## Who this is NOT for

- **Character artists looking for polish.** The example characters are pipeline-validation quality, not portfolio quality. The point is the workflow, not the model. This is a work in progress project and may evolve over time.
- **One-click solutions.** You'll need to think and make decisions. The AI handles the procedural work; the design judgment is yours.

---

## Status & roadmap

**Current (v0.1):** Body-topo costume pipeline + lattice proportion editing + one full worked example, validated end-to-end Blender → Godot.

**Maybe later, if the repo gets traction:**
- More worked examples (female base mesh, different costume genres)
- Hair card authoring pattern (currently the biggest gap in the pipeline)
- Cloth-simulation hybrid (for dynamic capes/skirts)
- Animation retargeting from Mixamo / library sources
- Variant overlay system (alive/zombie meshes sharing one rig)

I'm not committing to a roadmap — this is a workflow I built for my own game, published as a side-effect of writing it down. PRs welcome, but my time goes to my game first.

---

## License

MIT. See [LICENSE](LICENSE). External assets referenced in SETUP.md (Quaternius base meshes, MakeHuman content) have their own licenses — comply with those when you use them.

---

## Acknowledgments

- [Quaternius](https://quaternius.com/) — for the Universal Base Characters under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) (Public Domain Dedication), which made the shared-base-mesh approach realistic for solo devs. Consider [supporting on Patreon](https://www.patreon.com/quaternius) if these assets help you ship.
- [MakeHuman](http://www.makehumancommunity.org/) — for the realistic-human asset library used as a proportion-reference tool
- [MPFB (MakeHuman Plugin for Blender)](https://github.com/makehumancommunity/mpfb2) — for bringing MakeHuman content into Blender as live-editable assets
- Anthropic's Claude Code — for being a coding assistant that handles the procedural-script tedium well enough that the human can focus on the design decisions

---

## Contact

[GitHub: ChilyerStudiosLLC](https://github.com/ChilyerStudiosLLC) · Built as part of an active solo-dev Godot game project. Reach out if you're working on similar problems.
