"""Cap the small holes left in a skinned body DMX (remaster step 6: tw_de_a's open edges after tools/weld_cracks.py).
tw_de_a (Tripo GLB, donor weights) kept ~170 open edges in ~47 boundary loops after weld_cracks (NOTES tw31): small holes at the collar,
neck and shoulder straps (2-20 vertices, a few units across) where the welding could not close a gap without fusing layered surfaces.
Seen in game as specks you can look through. This closes each small, simple boundary loop with a fan of triangles wound against the
neighbouring faces; every new corner reuses an existing corner's position / normal / UV / tangent / weights entry (no new vertex data),
so skinning is unchanged. Loops that are not simple cycles, have more than --max-verts vertices or are larger than --max-size units
across are left open and listed (a strap's own outline would be one of those).

usage: python tools/fill_holes.py <body.dmx> <out.dmx> [--max-verts 24] [--max-size 12]
Reads the input (never writes it). Level: unit-checked (open edge count before / after, no new non-manifold edges); not compiled.
"""
import argparse, os, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dmx9                # noqa: E402  (the project copy = create/dmx9.py, libsync)


def corners(me):
    """[(face set index, [face-vertex index a, b, c])] triangulated"""
    out = []
    for si, fs in enumerate(me['faceSets']):
        cur = []
        for i in fs['faces']:
            if i < 0:
                out += [(si, [cur[0], cur[k], cur[k + 1]]) for k in range(1, len(cur) - 1)]; cur = []
            else: cur.append(i)
    return out


def edge_counts(T):
    E = Counter()
    for t in T:
        for i, j in ((0, 1), (1, 2), (2, 0)): E[(min(t[i], t[j]), max(t[i], t[j]))] += 1
    return E


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--max-verts', type=int, default=24); ap.add_argument('--max-size', type=float, default=12.0); ap.add_argument('--close', type=float, default=1.0)
    a = ap.parse_args(argv)
    if os.path.normcase(os.path.abspath(a.src)) == os.path.normcase(os.path.abspath(a.out)): sys.exit('fill_holes: out must differ from the input')
    dm = dmx9.DMX.load(a.src)
    for me in [e for e in dm.elements if e.type == 'DmeMesh']:
        vd = me['currentState']
        pidx = np.array(vd['position$0Indices']); P = np.array(vd['position$0'])
        _, first, canon_of_data = np.unique(np.round(P, 4), axis=0, return_index=True, return_inverse=True)
        canon_of_data = canon_of_data.ravel(); Pc = P[first]
        C = corners(me)
        T = np.array([[canon_of_data[pidx[i]] for i in fv] for _, fv in C])
        E0 = edge_counts(T)
        open0 = sum(1 for c in E0.values() if c == 1); nm0 = sum(1 for c in E0.values() if c > 2)
        # directed boundary edges (u -> v as wound in their triangle), with the face-vertex index of each end and the face set
        out_e = defaultdict(list); fv_of = {}
        for (si, fv), t in zip(C, T):
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if E0[(min(t[i], t[j]), max(t[i], t[j]))] == 1:
                    out_e[t[i]].append((t[j], si)); fv_of.setdefault(t[i], fv[i]); fv_of.setdefault(t[j], fv[j])
        # walk loops; the cap runs the other way round (v -> u), so it faces the same side as its neighbours
        used = set(); capped, skipped, new_tris = 0, [], []
        for start in list(out_e):
            if start in used or len(out_e[start]) != 1: continue
            loop, sets, v, ok = [start], [], start, True
            while True:
                if len(out_e[v]) != 1: ok = False; break
                nxt, si = out_e[v][0]; sets.append(si)
                if nxt == start: break
                if nxt in loop or len(loop) > a.max_verts: ok = False; break
                loop.append(nxt); v = nxt
            if not ok: continue                             # not a closed cycle: the chain pass below looks at it
            for x in loop: used.add(x)
            size = float(np.linalg.norm(Pc[loop].max(0) - Pc[loop].min(0)))
            if not ok or len(loop) < 3 or len(loop) > a.max_verts or size > a.max_size:
                skipped.append((len(loop), round(size, 1), Pc[loop].mean(0).round(1).tolist(), 'not simple' if not ok else 'too big' if len(loop) >= 3 else 'degenerate'))
                continue
            si = Counter(sets).most_common(1)[0][0]
            r = loop[::-1]                                  # reversed winding
            for k in range(1, len(r) - 1):
                new_tris.append((si, [fv_of[r[0]], fv_of[r[k]], fv_of[r[k + 1]]]))
            capped += 1
        # open chains (a hole whose rim also runs along a non-manifold edge, so the boundary edges alone never close): a chain whose
        # two ends are joined by an existing mesh edge (or lie within --close units) is capped the same way
        inc = Counter(w for v in out_e for w, _ in out_e[v])
        all_e = set(E0)
        chains = 0
        for start in list(out_e):
            if start in used or inc[start] != 0 or len(out_e[start]) != 1: continue
            loop, sets, v, ok = [start], [], start, True
            while v in out_e:
                if len(out_e[v]) != 1 or inc[v] > 1: ok = False; break
                nxt, si = out_e[v][0]; sets.append(si)
                if nxt in loop or len(loop) > a.max_verts: ok = False; break
                loop.append(nxt); v = nxt
            for x in loop: used.add(x)
            if not ok or len(loop) < 3:
                skipped.append((len(loop), 0.0, Pc[loop].mean(0).round(1).tolist(), 'chain branches')); continue
            e, b = loop[0], loop[-1]
            joined = (min(e, b), max(e, b)) in all_e or float(np.linalg.norm(Pc[e] - Pc[b])) <= a.close
            size = float(np.linalg.norm(Pc[loop].max(0) - Pc[loop].min(0)))
            if not joined or size > a.max_size:
                skipped.append((len(loop), round(size, 1), Pc[loop].mean(0).round(1).tolist(), 'chain ends apart' if not joined else 'too big')); continue
            si = Counter(sets).most_common(1)[0][0]; r = loop[::-1]
            for k in range(1, len(r) - 1):
                new_tris.append((si, [fv_of[r[0]], fv_of[r[k]], fv_of[r[k + 1]]]))
            chains += 1
        print('  open chains capped: %d' % chains)
        # append the cap corners: one new face-vertex per corner, pointing at the existing attribute entries of the reused corner
        keys = [k for k in vd.attrs if k.endswith('Indices')]
        n = len(vd[keys[0]])
        lists = {k: list(vd[k]) for k in keys}
        faces = {si: list(fs['faces']) for si, fs in enumerate(me['faceSets'])}
        for si, fv in new_tris:
            ids = []
            for f in fv:
                for k in keys: lists[k].append(lists[k][f])
                ids.append(n); n += 1
            faces[si] += ids + [-1]
        for k in keys: vd[k] = lists[k]
        for si, fs in enumerate(me['faceSets']): fs['faces'] = faces[si]
        T2 = np.array([[canon_of_data[pidx[i]] if i < len(pidx) else canon_of_data[lists['position$0Indices'][i]] for i in fv] for _, fv in corners(me)])
        E1 = edge_counts(T2)
        open1 = sum(1 for c in E1.values() if c == 1); nm1 = sum(1 for c in E1.values() if c > 2)
        print('%s: %d holes capped with %d triangles; open edges %d -> %d; non-manifold edges %d -> %d; %d loops left open'
              % (me.name, capped, len(new_tris), open0, open1, nm0, nm1, len(skipped)))
        for s in skipped[:30]: print('   left open: %d verts, %.1f u across, at %s (%s)' % s)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    dm.save(a.out)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
