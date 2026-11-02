"""Self-lit effect models the script pools: the ninja's dash shards, the lancer bolt, the monk's dome cage, the exit beacon.
Built with create/fx_models (geo meshes + csgo_vertexlitgeneric F_SELF_ILLUM materials); a few hundred triangles each.

usage: fx.py <addon_out>      -> models/nt/fx/<name>/<name>.vmdl, materials/models/nt/fx/fx_<name>.vmat; prints the model list
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE)
os.environ.setdefault('CS2_MODEL_PREFIX', 'nt')
import numpy as np
import geo, fx_models as FX

REL_M = 'models/nt/fx'; REL_T = 'materials/models/nt/fx'


def octahedron(r, h):
    """a crystal shard: an elongated octahedron, closed, flat-shaded"""
    V = np.array([(0, 0, h), (r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0), (0, 0, -h)], float)
    F = np.array([(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)])
    m = geo.Mesh(); m.V = V; m.F = F
    N = np.zeros_like(V)
    for a, b, c in F:
        n = np.cross(V[b] - V[a], V[c] - V[a]); N[[a, b, c]] += n
    m.N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return m


def rotz(mesh, deg):
    R = geo.rot('z', deg); mesh.V = mesh.V @ R.T; mesh.N = mesh.N @ R.T; return mesh


def cage(radius, lat=5, mer=12, t=1.6):
    """a wire sphere: latitude rings and meridians, double-sided flat bands"""
    parts = []
    for k in range(1, lat):
        z = -radius + 2 * radius * k / lat; r = math.sqrt(max(radius * radius - z * z, 1.0))
        parts.append(FX.ring(r - t, r + t, n=36, z=z, axis='z'))
    for k in range(mer):
        parts.append(rotz(FX.ring(radius - t, radius + t, n=36, axis='x'), 180.0 * k / mer))
    return FX.merge(parts)


def build(out):
    made = {}
    cyan = FX.emissive(out, REL_T, 'fx_shard', (60, 230, 255), 14.0, 'Nanite Temple: dash shard (AI-generated)')
    amber = FX.emissive(out, REL_T, 'fx_bolt', (255, 190, 60), 30.0, 'Nanite Temple: lancer bolt (AI-generated)')
    gold = FX.emissive(out, REL_T, 'fx_dome', (255, 180, 40), 10.0, 'Nanite Temple: monk dome (AI-generated)')
    magenta = FX.emissive(out, REL_T, 'fx_beacon', (255, 60, 200), 12.0, 'Nanite Temple: exit beacon (AI-generated)')
    made['shard'] = FX.write(out, REL_M, 'nt_shard', octahedron(4.0, 11.0), cyan)
    bolt = geo.tube([(-36, 0, 0), (0, 0, 0)], [1.2, 3.0], sides=6, mat='m')
    made['bolt'] = FX.write(out, REL_M, 'nt_bolt', bolt, amber)
    made['dome'] = FX.write(out, REL_M, 'nt_dome', cage(128.0), gold)
    # exit beacon: a slim column of three rings that the script spins over the amber plate once a vault is cleared
    beacon = FX.merge([FX.ring(40, 46, n=32, z=z) for z in (8, 40, 72)] + [FX.ring(4, 8, n=12, z=z) for z in (0, 90)])
    made['beacon'] = FX.write(out, REL_M, 'nt_beacon', beacon, magenta)
    # death burst: a flat star of shards
    star = FX.merge([rotz(octahedron(3.0, 10.0), 45 * k) for k in range(0)] or [octahedron(5.0, 5.0)])
    made['spark'] = FX.write(out, REL_M, 'nt_spark', star, cyan)
    for k, v in made.items(): print('%-7s %s' % (k, v))
    return made


if __name__ == '__main__':
    build(sys.argv[1])
