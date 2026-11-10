"""Entity / mesh / triangle cost of a Sprawl .vmap, for before / after tables (the detail pass, docs/SPRAWL_NOTES.md).
usage: python -I tools/arenas/sprawl_cost.py <map.vmap> [<map.vmap> ...]
Counts every node of the map (all arena copies): CMapMesh nodes and their faces / triangles (a face of n corners = n - 2), entities
by class, prop_static LOD0 triangles from tools/arenas/sprawl_kit.json (models not in the kit are listed as unknown).
prop_static, baked lights (directlight 1) and meshes are compiled into the world: they are not entities at run time.
"""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'tools'), os.path.join(REPO, 'create')]
import vmapedit as V

KIT = {v['model']: v['tris'] for v in json.load(open(os.path.join(HERE, 'sprawl_kit.json'))).values()}
KIT['models/generic/shipping_container_01/shipping_container_01_120x288x136_01.vmdl'] = 2824      # LOD0, measured from pak01 (11 Nov 2026)


def cost(path):
    m = V.Map(path); meshes = faces = tris = 0; cls = Counter(); ptris = 0; unknown = Counter(); baked = 0
    for n, _ in m.walk():
        t = m.type(n)
        if t == b'CMapMesh':
            md = m.g(n, b'meshData')
            if md is None or md < 0: continue
            fei = m.g(md, b'faceEdgeIndices') or []; nxt = m.g(md, b'edgeNextIndices')
            meshes += 1; faces += len(fei)
            for he in fei:
                k, h = 0, he
                while True:
                    k += 1; h = nxt[h]
                    if h == he or k > 255: break
                tris += max(0, k - 2)
        elif t == b'CMapEntity':
            c = m.cls(n); cls[c] += 1
            if c == 'prop_static':
                mdl = m.P(n, 'model', '')
                if mdl in KIT: ptris += KIT[mdl]
                else: unknown[mdl] += 1
            elif c == 'light_omni2' and m.P(n, 'directlight', '') == '1': baked += 1
    runtime = sum(v for k, v in cls.items() if k != 'prop_static') - baked
    return dict(map=path, meshes=meshes, mesh_faces=faces, mesh_triangles=tris, entities=sum(cls.values()), prop_static=cls['prop_static'], prop_lod0_triangles=ptris,
                baked_only_lights=baked, entities_at_run_time=runtime, light_omni2=cls['light_omni2'], info_particle_system=cls['info_particle_system'],
                unknown_prop_models=dict(unknown))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    for p in sys.argv[1:]: print(json.dumps(cost(p), indent=1))
