"""First-person arms from an unrigged arm pair GLB (see soldiers.py). build(T, glb, side, out, preview_dir)."""
import os
import numpy as np
from PIL import Image
import dmx9
from glbskin import GLB
from soldiers import gl2cs, arc, frame, unit, spread, write_material, write_dmx, joint_world, MODEL_DIR

HAND_LEN = 8.0        # template wrist -> middle fingertip
FOREARM_SHARE = 0.45  # elbow position between wrist and the top of the mesh
CAP = 0.05            # shoulder cap above the shoulder joint (share of the mesh length)
UPPER_STUB = 7.0      # keep this much of the upper arm above the elbow (CS2's own arms stop just past the elbow)
BLEND = 1.2           # half-width of the weight blend at elbow and wrist (units)


def rot_axis(axis, deg):
    a = np.radians(deg); k = unit(np.asarray(axis, float))
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def skin_mask(C):
    C = C.astype(int); r, g, b = C[:, 0], C[:, 1], C[:, 2]
    return (r - g > 22) & (r - g > (g - b) * 1.2) & (r > 90)


def centre_at(P, y, band):
    sel = np.abs(P[:, 1] - y) < band
    return P[sel].mean(0) if sel.any() else None


def tri_template(T):
    """the template's glove mesh (hands) with its weights, for copying finger weights"""
    dm = dmx9.DMX.load(T.arms)
    jl = [j.name for j in dm.root['skeleton']['jointList']]
    me = next(e for e in dm.elements if e.type == 'DmeMesh')
    vd = me['currentState']; jc = vd['jointCount']
    P = np.array(vd['position$0']); pi = np.array(vd['position$0Indices'])
    ids = np.array(vd['blendindices$0']).reshape(-1, jc); w = np.array(vd['blendweights$0']).reshape(-1, jc)
    W = [[(jl[ids[i, k]], w[i, k]) for k in range(jc) if w[i, k] > 1e-4] for i in range(len(P))]
    return P, W


def build(T, glb_path, side, out, preview=None):
    g = GLB(glb_path); m = g.mesh(); mi = g.material_images()
    tex = np.asarray(g.image(mi['baseColorTexture']).convert('RGB')); h, w = tex.shape[:2]
    uv = m['UV']
    C = tex[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)]
    skin = skin_mask(C)
    P0 = m['P']; F = m['F']; NG = m['N']
    tP, tW = tri_template(T)
    from scipy.spatial import cKDTree
    Vall, Nall, UVall, Wall, Fskin, Fcloth = [], [], [], [], [], []
    base = 0
    report = []
    done = set()
    for half in (1, -1):
        sel = (P0[:, 0] > 0) if half > 0 else (P0[:, 0] <= 0)
        idx = np.nonzero(sel)[0]; remap = -np.ones(len(P0), int); remap[idx] = np.arange(len(idx))
        P = P0[idx]; N = NG[idx]; sk = skin[idx]
        ytop, ybot = P[:, 1].max(), P[:, 1].min(); L = ytop - ybot
        ycuff = np.percentile(P[sk, 1], 97) if sk.any() else ybot + 0.25 * L
        hand_len = ycuff - ybot
        sc = HAND_LEN / hand_len
        yS = ytop - CAP * L; yE = ycuff + FOREARM_SHARE * (yS - ycuff); yW = ycuff - 0.02 * L
        band = 0.02 * L
        S, E, Wr = centre_at(P, yS, band), centre_at(P, yE, band), centre_at(P, yW, band)
        Tip = P[P[:, 1] < ybot + 0.03 * L].mean(0)
        f = lambda x: gl2cs(np.atleast_2d(x)) * sc
        Pc0 = f(P); Nc0 = gl2cs(N); S, E, Wr, Tip = (f(x)[0] for x in (S, E, Wr, Tip))
        hand0 = Pc0[sk & (Pc0[:, 2] < Wr[2])]
        # which hand is it, and how is it rolled about the arm? Try every roll (and both sides) and keep the one whose
        # hand lies closest on the template's glove after the fit.
        axis = unit(S - Tip)
        best = None
        for s in ('L', 'R'):
            if s in done: continue
            J = lambda n, s=s: T.J('%s_%s' % (n, s))
            G = tP[(tP[:, 1] > 0) if s == 'L' else (tP[:, 1] <= 0)]; G = G[G[:, 2] < J('hand')[2] + 0.5]; gt = cKDTree(G)
            for deg in range(0, 360, 10):
                Rr = rot_axis(axis, deg)
                Hp = (hand0 - Wr) @ Rr.T + Wr; Tp = (Tip - Wr) @ Rr.T + Wr
                u = Tp - Wr; ucs = J('finger_middle_2') + (J('finger_middle_2') - J('finger_middle_1')) * 0.9 - J('hand')
                A = arc(unit(u), unit(ucs)); al = np.linalg.norm(ucs) / np.linalg.norm(u)
                d = Hp - Wr; aa = (d @ unit(u))[:, None] * unit(u); d = aa * al + (d - aa)
                H = d @ A.T + J('hand')
                c = gt.query(H)[0].mean() + cKDTree(H).query(G)[0].mean()
                if best is None or c < best[0]: best = (c, s, deg)
        c, s, deg = best; done.add(s)
        J = lambda n: T.J('%s_%s' % (n, s))
        Rr = rot_axis(axis, deg)
        Pc = (Pc0 - Wr) @ Rr.T + Wr; Nc = Nc0 @ Rr.T
        S, E, Tip = ((x - Wr) @ Rr.T + Wr for x in (S, E, Tip))
        segs = []
        for a_, b_, c_, d_ in ((S, E, 'arm_upper', 'arm_lower'), (E, Wr, 'arm_lower', 'hand')):
            u = b_ - a_; ucs = J(d_) - J(c_)
            segs.append((a_, J(c_), arc(unit(u), unit(ucs)), unit(u), float(np.linalg.norm(ucs) / np.linalg.norm(u))))
        u = Tip - Wr; ucs = J('finger_middle_2') + (J('finger_middle_2') - J('finger_middle_1')) * 0.9 - J('hand')
        segs.append((Wr, J('hand'), arc(unit(u), unit(ucs)), unit(u), float(np.linalg.norm(ucs) / np.linalg.norm(u))))
        hgt = (Pc - Tip) @ axis; hE, hW = (E - Tip) @ axis, (Wr - Tip) @ axis
        wU = np.clip((hgt - (hE - BLEND)) / (2 * BLEND), 0, 1)
        wH = np.clip(((hW + BLEND * 0.6) - hgt) / (1.2 * BLEND), 0, 1)
        wF = np.clip(1 - wU - wH, 0, 1); tot = wU + wF + wH; wU, wF, wH = wU / tot, wF / tot, wH / tot
        def mv(X, tr):
            p, q, R, ax, al = tr; d = X - p; a = (d @ ax)[:, None] * ax; d = a * al + (d - a)
            return d @ R.T + q
        V = wU[:, None] * mv(Pc, segs[0]) + wF[:, None] * mv(Pc, segs[1]) + wH[:, None] * mv(Pc, segs[2])
        NN = wU[:, None] * (Nc @ segs[0][2].T) + wF[:, None] * (Nc @ segs[1][2].T) + wH[:, None] * (Nc @ segs[2][2].T)
        NN /= np.linalg.norm(NN, axis=1, keepdims=True) + 1e-12
        sg = 1 if s == 'L' else -1
        report.append('glTF %s arm = %s, roll %d, fit %.2f' % ('+x' if half > 0 else '-x', s, deg, c))
        # weights: arm bones by blend, hand + fingers copied from the template glove (nearest vertices of this side)
        tsel = np.nonzero((tP[:, 1] > 0) if sg > 0 else (tP[:, 1] <= 0))[0]
        Wt = []
        # match the hand's box to the glove's box (per axis) before copying, so finger spread and size don't matter
        hz = J('hand')[2] + 1.0
        mine = V[(wH > 0.5) & (V[:, 2] < hz)]; theirs = tP[tsel][tP[tsel][:, 2] < hz]
        lo1, hi1 = np.percentile(mine, 1, 0), np.percentile(mine, 99, 0); lo2, hi2 = np.percentile(theirs, 1, 0), np.percentile(theirs, 99, 0)
        Vn = (V - lo1) / np.maximum(hi1 - lo1, 1e-6) * (hi2 - lo2) + lo2
        tree = cKDTree(tP[tsel])
        dist, nn = tree.query(Vn, k=3)
        for i in range(len(V)):
            d = {}
            for b, x in spread(T, 'arm_upper_' + s, V[i]): d[b] = d.get(b, 0) + wU[i] * x
            for b, x in spread(T, 'arm_lower_' + s, V[i]): d[b] = d.get(b, 0) + wF[i] * x
            if wH[i] > 0:
                iw = 1 / (dist[i] + 0.02); iw /= iw.sum()
                acc = {}
                for k in range(3):
                    for b, x in tW[tsel[nn[i, k]]]: acc[b] = acc.get(b, 0) + iw[k] * x
                tot = sum(acc.values()) or 1
                for b, x in acc.items(): d[b] = d.get(b, 0) + wH[i] * x / tot
            top = sorted(d.items(), key=lambda x: -x[1])[:4]; t = sum(x for _, x in top) or 1
            Wt.append([(b, x / t) for b, x in top])
        # keep forearm, hand and a stub of the upper arm
        cut = J('arm_lower') @ unit(J('arm_upper') - J('arm_lower'))
        keepv = (V - J('arm_lower')) @ unit(J('arm_upper') - J('arm_lower')) < UPPER_STUB
        Fs = F[np.all(sel[F], 1)]; Fs = remap[Fs]
        Fs = Fs[np.all(keepv[Fs], 1)]
        isskin = sk[Fs].sum(1) >= 2
        Fskin += (Fs[isskin] + base).tolist(); Fcloth += (Fs[~isskin] + base).tolist()
        Vall.append(V); Nall.append(NN); UVall.append(uv[idx]); Wall += Wt; base += len(V)
        report[-1] += ', hand x%.1f, %.1f long' % (sc, L * sc)
    V = np.vstack(Vall); N = np.vstack(Nall); UV = np.vstack(UVall)
    name = 'arms_' + side
    mat = write_material(g, name, out)
    d = os.path.join(out, MODEL_DIR, name); os.makedirs(d, exist_ok=True)
    for tpl, fn, nm, FF in ((T.arms, 'arms.dmx', name, Fskin), (T.sleeves, 'sleeves.dmx', name + '_sleeves', Fcloth)):
        FF = np.array(FF); used = np.unique(FF); rm = -np.ones(len(V), int); rm[used] = np.arange(len(used))
        seq = list(range(len(used)))
        write_dmx(tpl, os.path.join(d, fn), nm, V[used], N[used], seq, seq, UV[used].tolist(), [mat], [rm[FF].tolist()],
                  [Wall[i] for i in used])
    print(name, '; '.join(report), '| faces skin %d cloth %d' % (len(Fskin), len(Fcloth)))
    if preview:
        import preview_soldier as PS
        sheet_arms(T, V, np.array(Fskin + Fcloth), Wall, tP, os.path.join(preview, name + '.png'))
    return V


def sheet_arms(T, V, F, W, tP, path):
    import preview_soldier as PS
    from PIL import ImageDraw
    bones = sorted({b for ws in W for b, _ in ws})
    rng = np.random.default_rng(5); pal = {b: rng.integers(60, 255, 3) for b in bones}
    used = np.unique(F)
    C = np.array([pal[max(ws, key=lambda x: x[1])[0]] for ws in W], np.uint8)
    X, Y, Z = np.eye(3)
    bends = {}
    for side, sg in (('L', 1), ('R', -1)):
        bends['arm_lower_' + side] = ((0, -sg, 0), -60)
        for f in ('index', 'middle', 'ring', 'pinky'):
            for k in (0, 1, 2): bends['finger_%s_%d_%s' % (f, k, side)] = ((0, sg, 0), 60)
        for k in (0, 1, 2): bends['finger_thumb_%d_%s' % (k, side)] = ((1, 0, 0), sg * 30)
    M = PS.pose_matrices(T, bends)
    Vp = PS.skin(V, W, M)
    ims = []
    for P, CC in ((V[used], C[used]), (np.vstack([V[used], tP]), np.vstack([C[used], np.full((len(tP), 3), 255, np.uint8)])), (Vp[used], C[used])):
        for ax, ay, az in ((Y * -1, Z, X * -1), (X, Z, Y)):
            im, lo, sc = PS.splat(P, CC, ax, ay, az, 420, 420)
            ims.append(im)
    out = Image.new('RGB', (420 * 6, 420))
    for i, im in enumerate(ims): out.paste(im, (420 * i, 0))
    out.save(path)
