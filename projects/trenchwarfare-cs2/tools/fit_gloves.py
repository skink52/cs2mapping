"""Stock CS2 gloves inside our generated sleeves, without clipping at the cuff.
Gloves: the glove mesh(es) from a stock agent's first-person arms DMX (material path containing 'glove'), left exactly as Valve made
them; the bare forearm piece and its jointList dag are dropped (the sleeve covers that part).
Sleeves: the cuff is eased out over the glove. Around the forearm bone (wrist -> elbow) the glove's outer profile is measured per height
and direction (max radius, spread a little so it covers the glove between samples); every sleeve vertex lower than the glove's top
is pushed out to that profile + MARGIN, the push is smoothed over the sleeve surface and fades out above the glove. Then every glove
edge is tested against the sleeve triangles and the margin grows locally until none cross.
usage: python3 tools/fit_gloves.py <stock arms dmx> <sleeves dmx> <out arms dmx> <out sleeves dmx>"""
import sys
import numpy as np
from scipy.ndimage import maximum_filter, gaussian_filter
import dmx9
from soldiers import joint_world

MARGIN = 0.3           # sleeve stays this far outside the glove
FADE = 2.0             # push fades out over this distance above the glove's top
TB, AB = 0.25, 36      # profile bins: height step (u), directions


def mesh_tris(me):
    vd = me['currentState']; pi = np.array(vd['position$0Indices']); out = []
    for fs in me['faceSets']:
        cur = []
        for i in fs['faces']:
            if i < 0: out += [(pi[cur[0]], pi[cur[k]], pi[cur[k + 1]]) for k in range(1, len(cur) - 1)]; cur = []
            else: cur.append(i)
    return np.array(vd['position$0']), np.array(out)


def ray_hits(O, D, A, B, C):
    """nearest positive hit distance per ray (inf if none). O, D: [n,3]; triangles A, B, C: [m,3]"""
    e1, e2 = B - A, C - A
    out = np.full(len(O), np.inf)
    for s in range(0, len(O), 256):
        o, d = O[s:s + 256, None], D[s:s + 256, None]
        p = np.cross(d, e2[None]); det = (e1[None] * p).sum(-1)
        ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
        tv = o - A[None]; u = (tv * p).sum(-1) * inv
        q = np.cross(tv, e1[None]); v = (d * q).sum(-1) * inv; t = (e2[None] * q).sum(-1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4)
        out[s:s + 256] = np.where(hit, t, np.inf).min(1)
    return out


def crossing_edges(G, GE, S, ST):
    """glove edges that pass through a sleeve triangle"""
    if not len(GE) or not len(ST): return np.zeros(0, int)
    O = G[GE[:, 0]]; d = G[GE[:, 1]] - O; L = np.linalg.norm(d, axis=1); d = d / np.maximum(L, 1e-9)[:, None]
    lo, hi = G[GE].min((0, 1)) - 1, G[GE].max((0, 1)) + 1          # only sleeve triangles near the glove
    c = S[ST].mean(1); ST = ST[((c > lo) & (c < hi)).all(1)]
    h = ray_hits(O, d, S[ST[:, 0]], S[ST[:, 1]], S[ST[:, 2]])
    return np.nonzero(h < L)[0]


class Frame:
    def __init__(self, wrist, elbow):
        self.w = wrist; self.a = (elbow - wrist) / np.linalg.norm(elbow - wrist)
        u = np.cross(self.a, [0, 0, 1.0]); self.u = u / np.linalg.norm(u); self.v = np.cross(self.a, self.u)
    def cyl(self, P):
        q = P - self.w; t = q @ self.a; x, y = q @ self.u, q @ self.v
        return t, np.arctan2(y, x), np.hypot(x, y)
    def radial(self, P):
        q = P - self.w; q = q - np.outer(q @ self.a, self.a); return q / np.maximum(np.linalg.norm(q, axis=1), 1e-9)[:, None]


def fit_side(G, GE, S, ST, sadj, F, side):
    gv = np.unique(GE.ravel())
    tg, ag, rg = F.cyl(G[gv])
    top = np.percentile(tg, 99.5)
    t0 = tg.min() - 1
    nt = int(np.ceil((top + FADE + 1 - t0) / TB)) + 1
    prof = np.zeros((nt, AB))
    ti = np.clip(((tg - t0) / TB).astype(int), 0, nt - 1); ai = ((ag + np.pi) / (2 * np.pi) * AB).astype(int) % AB
    np.maximum.at(prof, (ti, ai), rg)
    prof = maximum_filter(prof, size=(5, 3), mode=('nearest', 'wrap'))      # cover the glove between samples (+-0.5 u, +-10 deg)
    prof = np.maximum(prof, gaussian_filter(prof, (1.0, 1.0), mode=('nearest', 'wrap')))
    ts, as_, rs = F.cyl(S)
    sti = np.clip(((ts - t0) / TB).astype(int), 0, nt - 1); sai = ((as_ + np.pi) / (2 * np.pi) * AB).astype(int) % AB
    fade = np.clip((top + FADE - ts) / FADE, 0, 1)
    extra = np.zeros(len(S))
    rad = F.radial(S)
    for it in range(10):
        need = prof[sti, sai] + MARGIN + extra
        push = np.where((ts > tg.min() - 0.5) & (ts <= top), np.maximum(need - rs, 0), 0)
        for _ in range(4):                                       # smooth the push over the sleeve surface, never below what's needed
            pm = np.array([push[n].mean() if len(n) else push[i] for i, n in enumerate(sadj)])
            push = np.maximum(push, 0.6 * pm)
        for _ in range(int(FADE / 0.4) + 2):                     # carry it up past the glove's top, fading out
            up = np.array([push[n].max() if len(n) else 0 for n in sadj])
            push = np.where(ts > top, np.maximum(push, up * fade), push)
        S2 = S + rad * push[:, None]
        bad = crossing_edges(G, GE, S2, ST)
        print('  %s pass %d: %d sleeve vertices moved (max %.2f u), %d glove edges cross' % (side, it, int((push > 1e-3).sum()), push.max(), len(bad)))
        if not len(bad): break
        P = (G[GE[bad, 0]] + G[GE[bad, 1]]) / 2                  # grow the margin around the crossings
        tb, ab, _ = F.cyl(P)
        for t_, a_ in zip(tb, ab):
            da = np.abs((as_ - a_ + np.pi) % (2 * np.pi) - np.pi)
            extra[(np.abs(ts - t_) < 1.0) & (da < 0.5)] += 0.15
    return S2 - S


def main(arms_path, sleeves_path, out_arms, out_sleeves):
    dm = dmx9.DMX.load(arms_path); model = dm.root['model']
    gloves = []
    for c in list(model['children']):
        sh = c.get('shape') if c.type == 'DmeDag' else None
        if sh is None: continue
        if any('glove' in fs['material']['mtlName'] for fs in sh['faceSets']): gloves.append(sh)
        else:
            model['children'].remove(c)
            jl = model['jointList']
            if any(j is c for j in jl): jl[:] = [j for j in jl if j is not c]
    assert gloves, 'no glove mesh in ' + arms_path
    W = joint_world(dm)
    G, GT = [], []
    for me in gloves:
        p, t = mesh_tris(me); GT.append(t + sum(len(x) for x in G)); G.append(p)
    G = np.concatenate(G); GT = np.concatenate(GT)
    GE = set()
    for a, b, c in GT: GE |= {tuple(sorted(x)) for x in ((a, b), (b, c), (a, c))}
    GE = np.array(sorted(GE))
    sd = dmx9.DMX.load(sleeves_path)
    total_bad = 0
    for me in [e for e in sd.elements if e.type == 'DmeMesh']:
        S0, ST0 = mesh_tris(me)
        # weld coincident positions (UV seams split them) so both sides of a seam move together - no cracks
        _, first, inv = np.unique(np.round(S0, 4), axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel(); S = S0[first]; ST = inv[ST0]
        adj = [set() for _ in range(len(S))]
        for a, b, c in ST: adj[a] |= {b, c}; adj[b] |= {a, c}; adj[c] |= {a, b}
        D = np.zeros_like(S)
        for sgn, sfx in ((1, 'L'), (-1, 'R')):
            sm = S[:, 1] * sgn > 0; ge = GE[G[GE[:, 0], 1] * sgn > 0]
            if not sm.any() or not len(ge): continue
            idx = np.nonzero(sm)[0]; remap = -np.ones(len(S), int); remap[idx] = np.arange(len(idx))
            st = remap[ST[sm[ST].all(1)]]
            sub_adj = [remap[np.array(sorted(adj[i]), int)] for i in idx]
            sub_adj = [n[n >= 0] for n in sub_adj]
            F = Frame(W['hand_' + sfx][1], W['arm_lower_' + sfx][1])
            D[idx] = fit_side(G, ge, S[idx], st, sub_adj, F, sfx)
        S2 = (S + D)[inv]
        total_bad += len(crossing_edges(G, GE, S2, ST0))
        me['currentState']['position$0'] = [tuple(map(float, p)) for p in S2]
        if me.get('bindState') is not None and 'position$0' in me['bindState'].attrs:
            me['bindState']['position$0'] = [tuple(map(float, p)) for p in S2]
    dm.save(out_arms); sd.save(out_sleeves)
    print('wrote %s + %s; glove edges crossing the sleeve: %d' % (out_arms, out_sleeves, total_bad))


if __name__ == '__main__':
    main(*sys.argv[1:5])
