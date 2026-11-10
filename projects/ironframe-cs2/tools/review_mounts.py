"""IRONFRAME weapon-mount review sheets: every frame holding arm weapons in both hands plus a shoulder pair, front and side views,
placed exactly as the game places them (models.json#mounts from tools/weapon_fit.py; the props' origin is their grip / mount base).

usage: python -I tools/review_mounts.py [--only frame,..] [--pose idle|walk] [--size 560] [--lod 2] [--mounts models.json] [--report weapon_fit.json] [--out dir]
writes preview/weapons/<frame>.png   three loadouts (rows) x front / side (columns): a rotating standard set (every weapon shows up on
                                     some frame) and the frame's hardest pair of each kind (deepest after the fit; shoulder units: the
                                     highest seat gap), labelled with the measured penetration and, for the shoulder units, the seat gap
                                     (build/weapon_fit.json); green cross = palm, orange ring = weapon grip
       preview/weapons/shoulders_<frame>.png   EVERY shoulder unit on the frame: seven pairs, front and side, each labelled with its seat
                                     gap (how far it hovers over the frame, <= 0 = resting / sunk in) and its overlap with the idle frame
       preview/weapons/contact.png   every frame, front view, first loadout;  shoulders_contact.png  every frame, two shoulder pairs from the side
  --mounts / --report / --out        another mounts source (a models.json), fit report and output folder: before / after comparisons
Weapons are tinted amber-ish so they read against the frame. Same software raster as tools/review_frames.py.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import review_frames as RF, review_weapons as RW, weapon_fit as WF     # noqa: E402

OUTDIR = os.path.join(PROJ, 'preview', 'weapons')
VIEW = {'front': np.array([1., 0, 0]), 'side': np.array([0, -1., 0])}     # side: seen from the right
ARMS = ['rifle', 'laser', 'gatling', 'shield', 'bazooka', 'plasma', 'rail', 'smg', 'shotgun', 'blade', 'sniper', 'handmsl', 'burstrifle',
        'grenade', 'flamer', 'eshotgun', 'pilebunker', 'heavyblade']
SHOULDERS = ['vm12', 'lasercannon', 'dualmsl', 'autocannon', 'multimsl', 'clusterart', 'grenadecannon', 'flak', 'vm6', 'pulseshield',
             'decoy', 'repair', 'minelayer', 'orbitdrones']
_wcol = {}
LOD = 2


def weapon_tris(key, vmdl):
    if key not in _wcol:
        smd, mdirs = RW.entry_paths(key, vmdl); t, uv, mats = RW.load_smd(smd)
        cols, per = [], {}
        for mt in mats:
            if mt not in per:
                tx, _ = RW.get_tex(mdirs, mt)
                c = np.array([150., 150, 155]) if tx is None else tx[::8, ::8].reshape(-1, 3).mean(0)
                per[mt] = tuple(c * 0.55 + np.array([255, 170, 60]) * 0.45)          # amber tint: weapons stand out from the frame
            cols.append(per[mt])
        _wcol[key] = (t, cols)
    return _wcol[key]


def splat(T, cols, H, W, hv, dv, center, sc, lo_z):
    """vectorised point-splat raster (the per-triangle loop of review_frames.raster takes minutes on LOD0 frames + weapons): every
    triangle sampled at ~1 pixel spacing (single-pixel gaps filled), flat Lambert shade (two-sided), nearest point per pixel wins. Same framing as RF.raster."""
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    shade = 0.4 + 0.6 * np.abs(n @ RF.LIGHT)
    e = np.max(np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1), np.linalg.norm(T[:, 0] - T[:, 2], axis=1)]), 0)
    k = np.clip(np.ceil(e * sc / 0.9).astype(int), 1, 160)
    img = np.full((H, W, 3), RF.BG, np.float32); best = np.full(H * W, -np.inf)
    for kk in np.unique(k):
        sel = np.nonzero(k == kk)[0]
        i, j = np.mgrid[0:kk + 1, 0:kk + 1]; m = i + j <= kk; a = (i[m] / kk)[None, :, None]; b = (j[m] / kk)[None, :, None]
        for s0 in range(0, len(sel), max(1, 2000000 // a.shape[1])):
            ss = sel[s0:s0 + max(1, 2000000 // a.shape[1])]; S = T[ss]
            P = (S[:, 0, None] * (1 - a - b) + S[:, 1, None] * a + S[:, 2, None] * b).reshape(-1, 3)
            tri = np.repeat(ss, a.shape[1])
            x = ((P - center) @ hv * sc + W / 2).astype(int); y = (H - 20 - (P[:, 2] - lo_z) * sc).astype(int); z = P @ dv
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H); x, y, z, tri = x[ok], y[ok], z[ok], tri[ok]
            pix = y * W + x
            o = np.lexsort((-z, pix)); pix, z, tri = pix[o], z[o], tri[o]
            first = np.ones(len(pix), bool); first[1:] = pix[1:] != pix[:-1]
            pix, z, tri = pix[first], z[first], tri[first]
            win = z > best[pix]; pix, z, tri = pix[win], z[win], tri[win]
            best[pix] = z; img.reshape(-1, 3)[pix] = cols[tri] * shade[tri, None]
    hole = ~np.isfinite(best.reshape(H, W))                                      # fill single-pixel gaps from the nearest drawn neighbour
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nb = np.roll(np.roll(best.reshape(H, W), dy, 0), dx, 1); src = np.roll(np.roll(img, dy, 0), dx, 1)
        f = hole & np.isfinite(nb); img[f] = src[f]; hole &= ~f
    return img


def render(fr, F_pose, loadout, mounts, M, vname, H, label, marks):
    """fr: weapon_fit.Frame; loadout (ra, la, rs, ls) weapon keys; mounts: models.json#mounts.frames[frame]"""
    Tu, Vu, Tl = F_pose
    tris = [Tu]; cols = [RF.mat_color(fr.key, m) for m in fr.parts['upper']['mats']]
    if len(Tl): tris.append(Tl); cols += [RF.mat_color(fr.key, m) for m in fr.parts['legs']['mats']]
    hp = fr.e.get('hardpoints') or {}
    for slot, wk in enumerate(loadout):
        if not wk or wk not in M['weapons']: continue
        t, c = weapon_tris(wk, M['weapons'][wk])
        o = WF.np.array(WF_mount(mounts, wk, slot, hp), float)
        tris.append(t + o); cols += c
    T = np.concatenate(tris)
    P = T.reshape(-1, 3); lo, hi = P.min(0), P.max(0)
    dv = VIEW[vname]; hv = np.cross(-dv, [0, 0, 1.])
    W = int(H * 0.9); sc = min((H - 40) / max(1e-6, hi[2] - lo[2]), (W - 16) / max(1e-6, (P @ hv).max() - (P @ hv).min()))
    center = (lo + hi) / 2
    img = splat(T, np.array(cols, np.float32), H, W, hv, dv, center, sc, lo[2])
    tile = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(tile, 'RGBA')
    proj = lambda p: ((np.array(p) - center) @ hv * sc + W / 2, H - 20 - (p[2] - lo[2]) * sc)
    for p, kind in marks:
        x, y = proj(p)
        if kind == 'palm': dr.line([x - 6, y, x + 6, y], fill=(80, 255, 120, 255), width=2); dr.line([x, y - 6, x, y + 6], fill=(80, 255, 120, 255), width=2)
        else: dr.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(255, 150, 40, 255), width=2)
    y = 5
    for line in label: dr.text((6, y), line, fill=(235, 235, 235)); y += 14
    return tile


def WF_mount(mounts, wk, slot, hp):
    mt = mounts.get(wk)
    if mt and len(mt) >= 6: return mt[0:3] if slot in (0, 2) else mt[3:6]
    return hp.get(['ra', 'la', 'rs', 'ls'][slot], [0, 0, 0])


def main():
    a = sys.argv[1:]
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    H = int(a[a.index('--size') + 1]) if '--size' in a else 560
    pose_name = a[a.index('--pose') + 1] if '--pose' in a else 'idle'
    global LOD; LOD = int(a[a.index('--lod') + 1]) if '--lod' in a else 2
    M = WF.jload(WF.MODELS_JSON); cat = WF.jload(WF.FRAMES_JSON)
    mounts_all = ((WF.jload(a[a.index('--mounts') + 1]) if '--mounts' in a else M).get('mounts') or {}).get('frames', {})
    rp = a[a.index('--report') + 1] if '--report' in a else WF.REPORT
    rep = WF.jload(rp) if os.path.exists(rp) else {}
    global OUTDIR
    if '--out' in a: OUTDIR = a[a.index('--out') + 1]
    os.makedirs(OUTDIR, exist_ok=True)
    thumbs, sthumbs = [], []
    keys = list(M['frames'])
    for n, key in enumerate(keys):
        if only and key not in only: continue
        e = M['frames'][key]
        fr = WF.Frame(key, e, (cat['frames'].get(key, {}).get('mount') or {}), lod=LOD)   # the palms move < 1 u between LODs
        pose = [p for p in fr.poses() if p[0].startswith(pose_name)][0]
        posed = fr.posed(pose)
        palms = [fr.palm(s, posed[1], pose[1]) for s in 'rl']
        mounts = mounts_all.get(key, {}); r = rep.get(key, {}).get('pairs', {})
        pen = lambda wk: max((d['pen'] for d in r.get(wk, {}).values()), default=float('nan'))
        old = lambda wk: max((d['old'] for d in r.get(wk, {}).values()), default=float('nan'))
        seat = lambda wk: max((d.get('seat', float('nan')) for d in r.get(wk, {}).values()), default=float('nan'))
        idle = lambda wk: max((d.get('pen_idle', d['pen']) for d in r.get(wk, {}).values()), default=float('nan'))
        A, S = ARMS[n % len(ARMS)], SHOULDERS[n % len(SHOULDERS)]
        A2, S2 = ARMS[(n + 7) % len(ARMS)], SHOULDERS[(n + 5) % len(SHOULDERS)]
        hardA = max(ARMS, key=lambda k: pen(k) if r.get(k) else -1); hardS = max(SHOULDERS, key=lambda k: (seat(k) if seat(k) == seat(k) else pen(k)) if r.get(k) else -1e9)
        loadouts = [('standard', (A, A, S, S)), ('mixed', (A2, 'shield' if A2 != 'shield' else 'rifle', S2, S)), ('hardest after fit', (hardA, hardA, hardS, hardS))]
        rows = []
        for name, lo in loadouts:
            marks = [(p, 'palm') for p in palms if p is not None]
            for slot in (0, 1):
                wk = lo[slot]
                if wk in M['weapons']:
                    g = WF_mount(mounts, wk, slot, e.get('hardpoints') or {})          # the prop origin = its grip
                    marks.append((np.array(g, float), 'grip'))
            lab = ['%s (%s, %s pose) %s' % (key, e.get('height'), pose_name, name),
                   'R %s %.1f u  L %s %.1f u   (old %.0f / %.0f)' % (lo[0], pen(lo[0]), lo[1], pen(lo[1]), old(lo[0]), old(lo[1])),
                   'shoulders %s seat %+.1f in %.1f u / %s seat %+.1f in %.1f u' % (lo[2], seat(lo[2]), idle(lo[2]), lo[3], seat(lo[3]), idle(lo[3]))]
            rows.append([render(fr, posed, lo, mounts, M, v, H, lab if v == 'front' else ['side (from the right)'], marks) for v in ('front', 'side')])
        W = sum(t.width for t in rows[0]); sheet = Image.new('RGB', (W, H * len(rows)), RF.BG)
        for i, row in enumerate(rows):
            x = 0
            for t in row: sheet.paste(t, (x, i * H)); x += t.width
        p = os.path.join(OUTDIR, key + '.png'); sheet.save(p); print(p, flush=True)
        thumbs.append((key, rows[0][0]))
        # every shoulder unit: pairs (right, left) so each unit is seen on one side, front over side
        Hs = max(300, int(H * 0.62)); tiles = []
        for i in range(0, len(SHOULDERS), 2):
            rs, ls = SHOULDERS[i], SHOULDERS[(i + 1) % len(SHOULDERS)]
            sd = lambda wk, sd_: (r.get(wk, {}).get(sd_, {}) or {})
            lab = ['%s  R %s  L %s' % (key, rs, ls), 'seat %+.1f / %+.1f u  in idle %.1f / %.1f u' % (
                sd(rs, 'r').get('seat', float('nan')), sd(ls, 'l').get('seat', float('nan')), sd(rs, 'r').get('pen_idle', float('nan')), sd(ls, 'l').get('pen_idle', float('nan')))]
            tiles.append([render(fr, posed, (None, None, rs, ls), mounts, M, v, Hs, lab if v == 'front' else ['side (from the right)'], []) for v in ('front', 'side')])
        tw = tiles[0][0].width
        ss = Image.new('RGB', (tw * len(tiles), Hs * 2), RF.BG)
        for i, (f_, s_) in enumerate(tiles): ss.paste(f_, (i * tw, 0)); ss.paste(s_, (i * tw, Hs))
        p = os.path.join(OUTDIR, 'shoulders_%s.png' % key); ss.save(p); print(p, flush=True)
        sthumbs.append((key, tiles[n % len(tiles)][0], tiles[(n + 3) % len(tiles)][1]))
    if thumbs and not only:
        cw, ch, cols = 300, 330, 6
        cs = Image.new('RGB', (cols * cw, ((len(thumbs) + cols - 1) // cols) * ch), RF.BG)
        for i, (k, t) in enumerate(thumbs):
            cs.paste(t.resize((cw, ch)), ((i % cols) * cw, (i // cols) * ch))
        cs.save(os.path.join(OUTDIR, 'contact.png')); print(os.path.join(OUTDIR, 'contact.png'))
        cw, ch, cols = 440, 250, 4                                                  # per frame: one pair from the front, another from the side
        cs = Image.new('RGB', (cols * cw, ((len(sthumbs) + cols - 1) // cols) * ch), RF.BG)
        for i, (k, f_, s_) in enumerate(sthumbs):
            cs.paste(f_.resize((cw // 2, ch)), ((i % cols) * cw, (i // cols) * ch)); cs.paste(s_.resize((cw // 2, ch)), ((i % cols) * cw + cw // 2, (i // cols) * ch))
        cs.save(os.path.join(OUTDIR, 'shoulders_contact.png')); print(os.path.join(OUTDIR, 'shoulders_contact.png'))


if __name__ == '__main__':
    main()
