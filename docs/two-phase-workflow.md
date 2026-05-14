# Two-Phase Workflow

> **The most important rule: don't open Blender on day one.** Every character goes through two distinct sessions before any geometry exists. Skipping Phase A is the single biggest cause of characters that fail review and have to be rebuilt.

This is the meta-workflow. The technique details (body-topo, lattice) are in [body-topo-recipe.md](body-topo-recipe.md) and [lattice-proportions.md](lattice-proportions.md). This doc is the *process* — how you decide what to build before you build it.

---

## The two phases at a glance

| | **Phase A — Spec** | **Phase B — Build** |
|---|---|---|
| **Where** | Plain text / chat / paper | Blender + optional chat |
| **Input** | Vibes, references, design intent | Locked SPEC.md from Phase A |
| **Output** | `SPEC.md` document | Working `.blend` + `.glb` + stage-gate renders |
| **Decisions made** | Style, proportions, costume bill of materials, palette, what to skip | None — execute the spec |
| **Time** | 30–60 min | 2–6 hours (depending on costume complexity) |
| **Skippable?** | **No.** | No, obviously. |

---

## Phase A — Spec session

Six questions. Answer them in writing. Don't proceed until each has a concrete answer.

### Q1 — Style reference (which film/character/shot)

**Bad answer:** "Stylized."
**Good answer:** "Coraline (Laika 2009) for proportion exaggeration; surface finish closer to Arcane than to stop-motion; muted blue/purple palette like the Bobinski sequences."

Specificity here protects you from drift later. If you can't name a film/show/artist whose visual register matches what you want, you don't have a style yet — go gather references for an hour, then come back.

### Q2 — Proportions (head-count, limb thickness, key distortions)

**Bad answer:** "Athletic."
**Good answer:** "7.5 head-counts tall (between realism's 7 and Coraline's 8). Limbs +5% longer than realistic. Narrow waist; hip-to-shoulder ratio pushed toward hourglass. Hands sized for character read, not anatomical accuracy."

Numerical anchors here become editable parameters in your build script. "+5% longer limbs" maps directly to a Z-lattice shift you can dial.

### Q3 — Silhouette intent ("reads as X from far away")

**Bad answer:** "Reads as a person."
**Good answer:** "Reads as a cheerleader from 30m even without color — large bow on head as identity hook, A-line skirt + ponytail give the female-athletic silhouette, pom-poms break the hand-silhouette to make her unique among NPCs."

This question forces you to commit to one identity-defining shape. Every character needs one. Without it your character is interchangeable with every other character at gameplay distance.

### Q4 — Personality (informs pose and gait)

**Bad answer:** "Friendly."
**Good answer:** "12th-grade cheerleader, slightly mean-girl, knowing-smirk default. Hands-on-hips standing pose, hip-led confident walk, head-tilt-with-eye-roll listening pose."

Personality drives the rest pose you author for the bind. It also informs the costume — the "knowing-smirk default" character probably doesn't have generic-cheerful hair; she has a deliberate hairstyle.

### Q5 — Animation intent (gait, mood, weight)

**Bad answer:** "Walks."
**Good answer:** "Confident strut (longer stride than baseline). Stationary idle = hands on hips, weight on one leg, small smirk loop. Combat anim TBD but should keep the hip-led energy of the walk — no heavy lumbering."

If you don't know animation intent, you might build a character whose proportions don't suit any animation you have. Long-limbed characters need different walk cycles than blocky ones.

### Q6 — What to skip for v1

**Bad answer:** "Try to do everything."
**Good answer:** "Skip: face rig (no blendshapes for v1), individual fingers (palm-as-claw is fine), cloth physics, footwear detail (one solid color, no laces), pom-pom dynamic motion. Add: bow, ponytail, pleated skirt, hands-on-hips rest pose."

This question is *the* most-skipped one and *the* most important. Every "I want to do X too" in v1 is a week of work. Cut ruthlessly, ship something playable, iterate from feedback.

---

### What SPEC.md should look like at the end

A flat markdown file in the character's folder. Roughly:

```markdown
# CharacterName — Spec

## Style
[Q1 answer, with specific named references]

## Proportions
- Head-count: X.X
- Limb length: ±X% vs base
- Key distortions: [list]

## Silhouette intent
[Q3 answer — what reads from 30m]

## Personality / pose
[Q4 answer + default standing pose description]

## Animation intent
[Q5 answer + named walk/idle/combat moods]

## Costume bill of materials
1. Body (sculpt from <base mesh name>)
2. Hair (body-topo / hair-card / particle? color?)
3. Top (body-topo, cut conditions: z=A..B, x cutoff, neckline)
4. Bottom (body-topo or procedural-polar, length, color)
5. Footwear (modeled separately, parented to foot bones)
6. ... (one entry per piece)

## Palette
| Role | Hex | Notes |
|---|---|---|
| Costume primary | #XXXXXX | |
| Costume accent | #XXXXXX | |
| Skin | #XXXXXX | |
| Hair | #XXXXXX | |
| Eyes | #XXXXXX | |

## What we're skipping for v1
- [item]
- [item]
```

---

## Phase B — Build session

With the spec locked, building is execution. The stages are:

### Stage 1 — Import base mesh

Headless import per [SETUP.md](../SETUP.md). Confirm the body + eyes + eyebrows + armature are all in the scene, bbox is correct (height ~1.8m), 65 bones on the armature.

**Stop and validate:** Open the resulting .blend in Blender, eyeball the base, save to your `CharacterName/CharacterName.blend`.

### Stage 2 — Proportion editing (lattice + sculpt)

Apply your spec's proportions:
- **Lattice** for gross changes — see [lattice-proportions.md](lattice-proportions.md).
- **Sculpt Mode (Grab brush)** for fine cleanup after.

When you're happy, apply the Lattice modifier (bakes the deformation into geometry permanently), delete the lattice object, save.

**Stop and validate at the Silhouette Gate:** render front + side + 3/4 in pure-black-on-white. If the character's identity-defining silhouette (Q3 from spec) reads — proceed. If it doesn't — adjust proportions, don't keep going.

### Stage 3 — Costume blockout (one piece at a time)

For each costume piece in your spec's bill of materials, use the body-topo pipeline ([body-topo-recipe.md](../docs/body-topo-recipe.md)). Build, render, evaluate, adjust cut conditions, re-build. Repeat per piece.

**Don't try to do the whole outfit in one build script.** Each piece is a discrete operation with its own design choices. Sequential building lets you catch problems while they're small.

### Stage 4 — Rig verification

Load *one* real animation from your animation library (e.g., a walk cycle .glb) onto the armature. Scrub the timeline. Check that:
- The body deforms correctly
- Costume pieces follow without clipping
- No "jelly arm" or "exploding shoulder" artifacts

If anything's broken, fix it now before adding more animations.

### Stage 5 — glTF export

Always: `export_animation_mode='ACTIVE_ACTIONS'` (the default `ACTIONS` mode exports every action in `bpy.data.actions` including orphans, which produces duplicate animations in the .glb).

Output goes to `Exports/CharacterName/CharacterName.glb` or wherever your project convention has it.

### Stage 6 — Engine import & verify

Drop the .glb into your game engine. Confirm it imports cleanly, materials look right, animations bind. Walk the character around for 30 seconds in-game. Note anything that catches your eye.

If something's wrong, it's much easier to fix it in Blender now (when you remember what you did) than three weeks from now (when you don't).

---

## Anti-patterns

These all SOUND like they save time but make characters that don't survive review:

| Anti-pattern | What goes wrong |
|---|---|
| Skipping Phase A ("I'll figure it out in Blender") | You make choices in geometry that conflict with your eventual gameplay needs. By the time you notice, you've sunk hours into a character that needs to be rebuilt. |
| One-shotting the whole outfit in one build script | When something looks wrong, you don't know which piece is the problem. Stage-gated piece-by-piece building lets you bisect issues immediately. |
| Skipping the silhouette gate | You polish a character whose identity doesn't read at gameplay distance. They become an interchangeable NPC. |
| Skipping rig verification | You ship a character that breaks under animation. Players don't read your nice base pose; they see her arm dislocate during the run cycle. |
| "I'll add the spec doc later" | You won't. Spec docs only get written when they unblock the next stage. After a character is done, nobody writes its retroactive spec. |
| Refining a placeholder | A test character whose role might shift in playtest doesn't deserve polish hours. Ship the placeholder, ship the gameplay, then decide what's worth polishing. |

---

## When you come back for the next character

The faster onramp is:

1. **Phase A first** — even if you think it'll be quick. 30 minutes here saves 4 hours later.
2. **Use the previous character's SPEC.md as a template** — copy its structure, change the answers, lock the new spec.
3. **Re-use your previous build scripts** — character N+1's `build.py` should be character N's `build.py` with new cut conditions and new colors. Cut conditions ARE the differentiator between characters.
4. **Run the silhouette gate religiously** — it's the cheapest way to catch "this character looks like every other character" before you've sunk time into details.

The pipeline only gets faster with reps. Your tenth character will be ~1 hour of build time once Phase A is done.
