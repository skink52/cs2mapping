"""Sky shells out of vis: moondome / tools/skybox meshes that don't seal anything get "Exclude from Vis".

Rebuilt sky brushes (moondome boxes) and their tools/skybox twins are huge surfaces, and the vis compile voxelises every
vis-relevant face at 8 units, so they can be most of the Voxelize / Outside detection time (mg_mario_party: about half of
all vis surface). Most CS:GO rooms are also sealed by their own walls / nodraw hull inside the sky, so the shell only costs time.

For each shell mesh, the world geometry without any sky shells and without pass-through tool faces is voxelised at 16 units
over the shell's box plus a margin, and flood-filled from the margin. If the spawns / teleport destinations inside the box
can't be reached from outside, the room is sealed without its sky, so the shell is excluded from vis (it still renders).
Shells with no play points inside their box (e.g. a sky ceiling slab over an open map) are left alone, so a test that can't
tell is always on the safe side.
"""
import numpy as np
from scipy import ndimage
import dmx
from lighting import mesh_polys, TOOL_PASS

PLAY = ('info_player_counterterrorist', 'info_player_terrorist', 'info_player_start', 'info_teleport_destination')
VS = 16.0
MARGIN = 64.0

def _is_shell(mats):
    return bool(mats) and all('moondome' in x or x == 'materials/tools/toolsskybox.vmat' for x in mats)

def run(m, c):
    par = {n: p for n, p in m.walk()}
    def in_entity(n):
        p = par.get(n)
        while p is not None:
            if m.type(p) == b'CMapEntity': return True
            p = par.get(p)
        return False
    shells, world = [], []
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh' or in_entity(n): continue
        pl = mesh_polys(m, n)
        if _is_shell({x for x, _ in pl}): shells.append(n)
        else: world += [np.array(l, np.float64) for mt, l in pl if not mt.startswith(TOOL_PASS)]
    if not shells: return
    play = [np.array(m.origin(e), np.float64) + [0, 0, 24] for e in m.by_class(*PLAY)]
    wb = [(P.min(0), P.max(0), P) for P in world]
    excluded, kept_leak, kept_empty = [], 0, 0
    cache = {}
    for n in shells:
        b = m.bounds(n)
        if b is None: continue
        key = (tuple(np.round(b[0])), tuple(np.round(b[1])))
        if key not in cache:
            blo, bhi = np.array(b[0]), np.array(b[1])
            inside = [p for p in play if (p > blo).all() and (p < bhi).all()]
            if not inside: cache[key] = 'empty'
            else:
                lo, hi = blo - MARGIN, bhi + MARGIN
                shape = tuple(int(x) for x in np.ceil((hi - lo) / VS))
                if np.prod(shape) > 300_000_000: cache[key] = 'leak'
                else:
                    solid = np.zeros(shape, bool)
                    for pmin, pmax, P in wb:
                        if (pmax < lo).any() or (pmin > hi).any(): continue
                        for i in range(1, len(P) - 1):
                            a, bb, cc = P[0], P[i], P[i + 1]
                            k = int(max(np.linalg.norm(bb - a), np.linalg.norm(cc - a), np.linalg.norm(cc - bb)) / (VS * 0.4)) + 2
                            u, w = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k)); s = (u + w) <= 1
                            q = a + np.outer(u[s], bb - a) + np.outer(w[s], cc - a)
                            idx = np.floor((q - lo) / VS).astype(int)
                            idx = idx[((idx >= 0) & (idx < shape)).all(1)]
                            solid[idx[:, 0], idx[:, 1], idx[:, 2]] = True
                    lab, _ = ndimage.label(~solid)
                    ext = set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(),
                                                        lab[:, :, 0].ravel(), lab[:, :, -1].ravel()]))) - {0}
                    leak = False
                    for p in inside:
                        i = tuple(np.clip(np.floor((p - lo) / VS).astype(int), 0, np.array(shape) - 1))
                        if lab[i] in ext: leak = True; break
                    cache[key] = 'leak' if leak else 'sealed'
        r = cache[key]
        if r == 'sealed':
            a = dmx.geta(m.E[n], b'visexclude')
            if a: a[2] = True
            else: dmx.set_(m.E[n], b'visexclude', dmx.T_BOOL, True)
            excluded.append(n)
        elif r == 'leak': kept_leak += 1
        else: kept_empty += 1
    c.log.append('sky shells: %d moondome / tools/skybox meshes set to Exclude from Vis (their rooms are sealed by other geometry, '
                 'checked at %g units), %d kept because the room needs them to seal, %d kept with no spawns / teleports inside'
                 % (len(excluded), VS, kept_leak, kept_empty))
    if excluded:
        c.todo.append('sky shells excluded from vis: if anything in a room pops in and out of view, a gap under %g units in its own walls '
                      'was missed - untick "Exclude from Vis" on that room\'s sky meshes' % VS)
