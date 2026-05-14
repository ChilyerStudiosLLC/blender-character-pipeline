"""
headless_import.py — Import a glTF base mesh in headless Blender.

The Blender Python API's `bpy.ops.import_scene.gltf` requires a UI context
(window + active object) that doesn't exist when Blender runs with
`--background`. The workaround is to construct the context override
manually, OR — much simpler — to launch a fresh headless Blender process
specifically for the import, save the result as a .blend, then open that
.blend from whatever environment you actually want to work in.

This module provides the simpler form: a function that imports a glTF
inside the current Blender process. Use this when you're already running
inside a `blender --background --python ...` invocation (e.g., from the
example build scripts in this repo).

USAGE
=====

From a script run with `blender --background --python yourscript.py`:

```python
from scripts.headless_import import import_gltf_base

result = import_gltf_base(
    gltf_path="/path/to/Superhero_Male_FullBody.gltf",
    keep_object_names=("SuperHero_Male", "Eyes", "Eyebrows", "Armature"),
)
print(f"Imported {result['kept']}, removed {result['removed']} extras")
```

The `keep_object_names` argument is a safety net — the Quaternius Universal
Base Characters pack sometimes ships with a stray Icosphere or environment
object that you don't want in your scene. Anything not in the keep-list is
deleted after import.

LICENSE
=======

MIT — see LICENSE file in the repo root.
"""

from __future__ import annotations

import bpy


def import_gltf_base(
    gltf_path: str,
    keep_object_names: tuple[str, ...] = ("Armature",),
    clear_scene_first: bool = True,
) -> dict:
    """
    Import a glTF file and prune the scene to only the named objects (plus
    armatures, which we always keep so the rig is preserved).

    Parameters
    ----------
    gltf_path : absolute path to the .gltf or .glb file
    keep_object_names : object names to keep after import. Anything not in
                        this list gets deleted. The character mesh + eyes/
                        eyebrows are typical entries.
    clear_scene_first : if True, deletes all existing scene objects before
                        importing. Set False to add the character to an
                        existing scene.

    Returns
    -------
    dict with keys:
        'kept'    : list of object names kept after pruning
        'removed' : list of object names removed (stray extras)
        'bbox'    : bbox of the primary mesh (min, max corners) in world space,
                    suitable for setting up cameras and lattices
    """
    if clear_scene_first:
        # Use this pattern in headless mode (read_homefile is unreliable in
        # --background contexts; deleting + purging is more robust).
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False, confirm=False)
        try:
            bpy.ops.outliner.orphans_purge(do_recursive=True)
        except RuntimeError:
            # No outliner context in some headless invocations; skip the purge
            pass

    # Import. Will succeed in headless mode as long as the script is invoked
    # with --background --python (which provides minimum required context).
    bpy.ops.import_scene.gltf(filepath=gltf_path)

    # Prune: delete anything not in keep_object_names. Always keep armatures
    # so we don't lose the rig accidentally.
    kept, removed = [], []
    keep_set = set(keep_object_names)
    for obj in list(bpy.data.objects):
        if obj.type == 'ARMATURE' or obj.name in keep_set:
            kept.append(obj.name)
        else:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    # Compute bbox of the largest remaining mesh (likely the body)
    largest_mesh = max(
        (o for o in bpy.data.objects if o.type == 'MESH'),
        key=lambda o: len(o.data.vertices),
        default=None,
    )
    bbox = None
    if largest_mesh is not None:
        verts_world = [largest_mesh.matrix_world @ v.co for v in largest_mesh.data.vertices]
        bbox = (
            (min(v.x for v in verts_world), min(v.y for v in verts_world), min(v.z for v in verts_world)),
            (max(v.x for v in verts_world), max(v.y for v in verts_world), max(v.z for v in verts_world)),
        )

    return {
        "kept": kept,
        "removed": removed,
        "bbox": bbox,
    }
