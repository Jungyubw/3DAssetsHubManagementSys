"""GLB stats for the description: triangles, meshes, animations."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TRIANGLES = 4  # glTF primitive mode


@dataclass(frozen=True)
class GlbStats:
    triangles: int
    meshes: int
    animations: int


def read_stats(path: Path) -> GlbStats:
    from pygltflib import GLTF2

    gltf = GLTF2().load(str(path))
    triangles = 0
    for mesh in gltf.meshes:
        for prim in mesh.primitives:
            if (prim.mode if prim.mode is not None else TRIANGLES) != TRIANGLES:
                continue
            accessor = prim.indices if prim.indices is not None else prim.attributes.POSITION
            if accessor is not None:
                triangles += gltf.accessors[accessor].count // 3
    return GlbStats(triangles=triangles, meshes=len(gltf.meshes), animations=len(gltf.animations))
