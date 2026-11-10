"""IRONFRAME frame review gallery (skink52 approves every frame by hand before it goes in game).

usage: python -I tools/review_frames.py [--only key,..] [--no-sheets] [--lod N]

Reads out/addon/_gen/models.json (build with frames.py --all), the converted SMDs (skinned, with the clips) and the work state
(C:/source1/ironframe_work/state.json), and writes
  preview/review/<key>.png          4 turntable views (72 u human silhouette for scale, hit spheres red, waist pivot orange) + a strip with each
                                    clip's key pose, posed from the actual animation SMDs (so it checks the files that get compiled)
  preview/review/contact_sheet.png  one 'three' view per frame, with class / status / warning count
  docs/FRAME_REVIEW.md              the table: key, source item, author, class/height, triangles per LOD, textures, clips, warnings, status
Set `status` in data/frames.json to approved / rejected after looking; frames.py writes only approved frames into models.json unless --all.
"""
import glob, json, math, os, re, sys, time
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'out', 'addon')
REV = os.path.join(PROJ, 'preview', 'review')
BG = (40, 44, 52)
VIEWS = {'front': (1, 0, 0.), 'three': (0.87, 0.5, 0.), 'side': (0, 1, 0.), 'back': (-1, 0, 0.)}
LIGHT = np.array([0.4, 0.3, 0.86]); LIGHT /= np.linalg.norm(LIGHT)


def Rzyx(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]); Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return Rz @ Ry @ Rx


# ---------------------------------------------------------------- SMD reading
def read_nodes_frames(lines):
    nodes, i = [], lines.index('nodes') + 1
    while lines[i] != 'end':
        t = lines[i].split(); nodes.append((t[1].strip('"'), int(t[2]))); i += 1
    frames, i = {}, lines.index('skeleton') + 1
    cur = None
    while i < len(lines) and lines[i] != 'end':
        t = lines[i].split()
        if t[0] == 'time': cur = int(t[1]); frames[cur] = np.zeros((len(nodes), 6))
        else: frames[cur][int(t[0])] = [float(v) for v in t[1:7]]
        i += 1
    return nodes, frames


def read_mesh(path):
    L = open(path).read().split('\n')
    nodes, frames = read_nodes_frames(L)
    i = L.index('triangles') + 1
    mats, V, BI, BW = [], [], [], []
    while i < len(L) and L[i] != 'end':
        mats.append(L[i].strip())
        for k in range(3):
            t = L[i + 1 + k].split()
            V.append([float(x) for x in t[1:4]])
            if len(t) > 9:
                n = int(t[9]); bw = [(int(t[10 + 2 * j]), float(t[11 + 2 * j])) for j in range(n)][:3]
            else: bw = [(int(t[0]), 1.0)]
            bw += [(0, 0.0)] * (3 - len(bw)); BI.append([b for b, _ in bw]); BW.append([w for _, w in bw])
        i += 4
    return dict(nodes=nodes, bind=frames[0], V=np.array(V), BI=np.array(BI), BW=np.array(BW), mats=mats)


def world_mats(nodes, fr):
    W = []
    for k, (n, p) in enumerate(nodes):
        M = np.eye(4); M[:3, :3] = Rzyx(*fr[k][3:6]); M[:3, 3] = fr[k][:3]
        W.append(M if p < 0 else W[p] @ M)
    return W


def posed(mesh, fr):
    """vertices in model space (x forward) for animation frame `fr` ((nb,6) local transforms) or None for bind"""
    nodes = mesh['nodes']
    Wb = world_mats(nodes, mesh['bind'])
    Wp = world_mats(nodes, fr if fr is not None else mesh['bind'])
    S = np.array([Wp[k] @ np.linalg.inv(Wb[k]) for k in range(len(nodes))])
    V = mesh['V']; out = np.zeros_like(V)
    for k in range(3):
        M = S[mesh['BI'][:, k]]
        out += mesh['BW'][:, k:k + 1] * (np.einsum('nij,nj->ni', M[:, :3, :3], V) + M[:, :3, 3])
    return np.stack([-out[:, 1], out[:, 0], out[:, 2]], 1)          # undo the (y, -x, z) import turn


def clip_frames(path):
    L = open(path).read().split('\n')
    nodes, fr = read_nodes_frames(L)
    return nodes, fr


# ---------------------------------------------------------------- pairing + hip curve (models.json)
def upper_clip_for(entry, c):
    """the upper clip played with legs clip c: models.json frames.<key>.sway, else the old pairing"""
    return (entry.get('sway') or {}).get(c) or {'walk': 'walk_sway', 'run': 'run_sway', 'land': 'land'}.get(c, 'idle')


def _curve_at(cv, t, T, loop):
    n = len(cv)
    if loop:                                                    # periodic Catmull-Rom, the reading the generator solves the feet against
        x = (t / T) * n; i = int(math.floor(x)); f = x - i
        p0, p1, p2, p3 = cv[(i - 1) % n], cv[i % n], cv[(i + 1) % n], cv[(i + 2) % n]
        return 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)
    x = min(max(t / T, 0.0), 1.0) * (n - 1); i = min(int(x), n - 2); f = x - i
    return cv[i] * (1 - f) + cv[i + 1] * f


def hip_offset(entry, c, t, T):
    """(0, sway, hip z) the script adds to BOTH props at time t of locomotion clip c (zero when the frame has no curve)"""
    z = (entry.get('hip_curve') or {}).get(c); y = (entry.get('sway_curve') or {}).get(c)
    loop = c not in ('land',)
    return np.array([0.0, _curve_at(y, t, T, loop) if y else 0.0, _curve_at(z, t, T, loop) if z else 0.0])


# ---------------------------------------------------------------- colours / rendering
_col = {}
def mat_color(key, mat):
    k = (key, mat)
    if k not in _col:
        stem = re.sub(r'\.vmat$', '', mat)
        g = glob.glob(os.path.join(OUT, 'materials', 'ifr', 'frames', key, stem + '*color*.png')) or glob.glob(os.path.join(OUT, 'materials', 'ifr', 'frames', key, stem + '*.png'))
        c = (150, 150, 155)
        if g:
            try:
                im = Image.open(g[0]).convert('RGB').resize((16, 16)); c = tuple(int(v) for v in np.array(im).reshape(-1, 3).mean(0))
            except Exception: pass
        _col[k] = c
    return _col[k]


def raster(tris, cols, H, W, hv, dv, center, sc, lo_z):
    """tris (m,3,3) world; returns an RGB float image"""
    img = np.full((H, W, 3), BG, np.float32); zb = np.full((H, W), -1e9)
    X = (tris @ hv - center @ hv) * sc + W / 2; Y = H - 20 - (tris[..., 2] - lo_z) * sc; Z = tris @ dv
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); nl = np.linalg.norm(n, axis=1) + 1e-12; n /= nl[:, None]
    facing = n @ dv > -0.05
    shade = 0.4 + 0.6 * np.clip(np.abs(n) @ LIGHT * 0 + n @ LIGHT, 0, 1)
    order = np.argsort(Z.mean(1))
    for t in order:
        if not facing[t]: continue
        x, y, z = X[t], Y[t], Z[t]
        x0, x1 = int(max(0, math.floor(x.min()))), int(min(W - 1, math.ceil(x.max()))); y0, y1 = int(max(0, math.floor(y.min()))), int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d; b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d; c = 1 - a - b
        m = (a >= -1e-3) & (b >= -1e-3) & (c >= -1e-3)
        zz = a * z[0] + b * z[1] + c * z[2]; sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz > sub
        if not m.any(): continue
        sub[m] = zz[m]; img[y0:y1 + 1, x0:x1 + 1][m] = np.array(cols[t], np.float32) * shade[t]
    return img


def silhouette(dr, cx, base_y, sc):
    """72 u human: head, torso, arms, legs"""
    g = (95, 105, 120)
    def R(x0, z0, x1, z1): dr.rectangle([cx + x0 * sc, base_y - z1 * sc, cx + x1 * sc, base_y - z0 * sc], fill=g)
    R(-6, 0, -1, 34); R(1, 0, 6, 34); R(-8, 34, 8, 58); R(-12, 36, -8, 56); R(8, 36, 12, 56)
    dr.ellipse([cx - 5 * sc, base_y - 72 * sc, cx + 5 * sc, base_y - 62 * sc], fill=g)
    dr.text((cx - 12, base_y + 2), '72 u', fill=(170, 180, 195))


def render_view(key, meshes, entry, vname, H, ents, extras=True, label=None, box=None, wfrac=0.62):
    """meshes: [(mesh, posed verts)]"""
    tris = np.concatenate([P.reshape(-1, 3)[None].reshape(-1, 3, 3) for _, P in meshes]); cols = []
    for m, P in meshes: cols += [mat_color(key, mt) for mt in m['mats']]
    lo, hi = box
    dv = np.array(VIEWS[vname]); hv = np.cross(-dv, [0, 0, 1.])
    W = int(H * wfrac); sc = min((H - 40) / max(1e-6, hi[2] - lo[2]), (W - 12) / max(1e-6, max(hi[0] - lo[0], hi[1] - lo[1])))
    center = (lo + hi) / 2
    img = raster(tris, cols, H, W, hv, dv, center, sc, lo[2])
    tile = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(tile, 'RGBA')
    base_y = H - 20
    if extras:
        silhouette(dr, W * 0.1, base_y, sc)
        proj = lambda p: ((np.array(p) - center) @ hv * sc + W / 2, H - 20 - (p[2] - lo[2]) * sc)
        for s in entry.get('spheres', []):
            x, y = proj(s[:3]); r = s[3] * sc
            dr.ellipse([x - r, y - r, x + r, y + r], outline=(255, 70, 60, 200))
        px, py = entry.get('pivot', [0, 0])
        x0, y0 = proj([px, py, 0]); x1, y1 = proj([px, py, entry['height']])
        dr.line([x0, y0, x1, y1], fill=(255, 160, 30, 230), width=1)
        xh, yh = proj([px, py, entry.get('hip_z', 0)]); dr.ellipse([xh - 4, yh - 4, xh + 4, yh + 4], outline=(255, 160, 30, 255), width=2)
    if label: dr.text((6, 5), label, fill=(235, 235, 235))
    return tile


# ---------------------------------------------------------------- one model
def lod_file(d, mname, lod):
    for k in range(lod, -1, -1):
        p = os.path.join(d, mname + ('_lod%dd' % k if k else '') + '.smd')
        if os.path.exists(p): return p
    return os.path.join(d, mname + '.smd')


def pick_frame(frames, loop):
    ks = sorted(frames)
    if loop: return frames[ks[len(ks) // 4]]
    base = frames[ks[0]]; best = max(ks, key=lambda k: np.abs(frames[k][:, 3:6] - base[:, 3:6]).sum())
    return frames[best]


def review_one(key, entry, lod):
    d = os.path.join(OUT, 'models', 'ifr', 'frames', key)
    parts = {}
    for g in ('legs', 'upper'):
        v = entry.get(g)
        if v: parts[g] = read_mesh(lod_file(d, os.path.basename(v)[:-5], lod))
    anims = entry.get('anims', {}); lens = entry.get('anim_len', {})
    default = {'legs': 'hover', 'upper': 'idle'}
    clipfr = {}
    for g in parts:
        for c in anims.get(g, []):
            nodes, fr = clip_frames(os.path.join(d, 'anims', '%s_%s.smd' % (g, c)))
            clipfr[(g, c)] = (fr, c in ('hover', 'move', 'boost', 'air', 'idle', 'walk', 'walk_back', 'strafe_l', 'strafe_r', 'run', 'walk_sway', 'run_sway'))
    def pose(over=None):
        meshes = []
        for g, m in parts.items():
            c = (over or {}).get(g, default[g])
            fr = None
            if (g, c) in clipfr:
                f, loop = clipfr[(g, c)]; fr = pick_frame(f, loop) if over and g in over else f[0]
            meshes.append((m, posed(m, fr)))
        return meshes
    base = pose()
    allv = np.concatenate([P for _, P in base])
    H = 520; hmax = max(entry['height'], 72) * 1.04
    lo = np.array([allv[:, 0].min(), allv[:, 1].min(), min(0, allv[:, 2].min())]); hi = np.array([allv[:, 0].max(), allv[:, 1].max(), hmax])
    lo[:2] -= 6; hi[:2] += 6
    # keep the same scale in every tile: widen x/y to the 0.62 aspect only through W, centre from the box
    tiles = [render_view(key, base, entry, v, H, None, label=('%s  %s' % (key, v)) if v == 'front' else v, box=(lo, hi)) for v in ('front', 'three', 'side', 'back')]
    minz = float(allv[:, 2].min())
    warn = []
    if minz < -3: warn.append('default pose dips %.0f u below the floor' % -minz)
    strip = []
    SH = 300
    clips = [(g, c) for g in parts for c in anims.get(g, []) if c != 'idle' or g == 'upper']
    for g, c in clips:
        meshes = pose({g: c})
        vn = 'side' if g == 'legs' else 'three'
        sub = np.concatenate([P for _, P in meshes])
        if sub[:, 2].min() < -6 and g == 'legs' and c in ('hover', 'land', 'move'): warn.append('%s dips %.0f u below the floor' % (c, -sub[:, 2].min()))
        strip.append(render_view(key, meshes, entry, vn, SH, None, extras=False, label='%s/%s %.2fs' % (g, c, lens.get(c, 0)), box=(lo, hi)))
    # stride strips: 8 evenly spaced poses of every locomotion cycle (legs + the matching upper sway), side view, ground line drawn
    rows = []
    RH = 250
    if 'legs' in parts:
        blo = lo.copy(); bhi = hi.copy(); w = 0.4 * entry['height']; cxm = (lo[0] + hi[0]) / 2; blo[0] = cxm - w; bhi[0] = cxm + w; cym = (lo[1] + hi[1]) / 2; blo[1] = cym - w; bhi[1] = cym + w
        for c in ('walk', 'walk_back', 'strafe_l', 'strafe_r', 'run', 'land'):
            if ('legs', c) not in clipfr: continue
            lf = clipfr[('legs', c)][0]; ks = sorted(lf); loop = c != 'land'
            uc = upper_clip_for(entry, c) if c != 'land' else 'land'
            if c in ('strafe_l', 'strafe_r', 'walk_back') and uc == 'idle': uc = None
            uf = clipfr.get(('upper', uc))
            row = []
            for j in range(8):
                kk = ks[min(len(ks) - 1, int(round(j / (8 if loop else 7) * len(ks))))] if loop else ks[min(len(ks) - 1, int(round(j / 7 * (len(ks) - 1))))]
                hoff = hip_offset(entry, c, (j / (8 if loop else 7)) * lens.get(c, 1.0), lens.get(c, 1.0))
                meshes = [(parts['legs'], posed(parts['legs'], lf[kk]) + hoff)]
                if 'upper' in parts:
                    fr = None
                    if uf is not None:
                        uk = sorted(uf[0]); fr = uf[0][uk[min(len(uk) - 1, int(round(j / (8 if loop else 7) * len(uk))))]] if loop else uf[0][uk[min(len(uk) - 1, int(round(j / 7 * (len(uk) - 1))))]]
                    elif ('upper', 'idle') in clipfr: fr = clipfr[('upper', 'idle')][0][0]
                    meshes.append((parts['upper'], posed(parts['upper'], fr) + hoff))
                sub = np.concatenate([P for _, P in meshes])
                if sub[:, 2].min() < -4 and c != 'land': warn.append('%s pose %d dips %.0f u below the floor' % (c, j, -sub[:, 2].min()))
                tl = render_view(key, meshes, entry, 'front' if c.startswith('strafe') else 'side', RH, None, extras=False, label='legs/%s %d/8  %.2fs' % (c, j, lens.get(c, 0)) if j == 0 else '%d/8' % j, box=(blo, bhi), wfrac=1.0)
                dgr = ImageDraw.Draw(tl, 'RGBA'); gy = RH - 20 + (lo[2] - min(0, lo[2])) * 0
                dgr.line([0, RH - 20, tl.width, RH - 20], fill=(255, 200, 60, 150), width=1)
                row.append(tl)
            rows.append(row)
    tw = sum(t.width for t in tiles); sw = sum(t.width for t in strip)
    W = max([tw, sw] + [sum(t.width for t in r) for r in rows])
    sheet = Image.new('RGB', (W, H + (SH if strip else 0) + RH * len(rows)), BG)
    x = 0
    for t in tiles: sheet.paste(t, (x, 0)); x += t.width
    x = 0
    for t in strip:
        sheet.paste(t, (x, H)); x += t.width
    y = H + (SH if strip else 0)
    for r in rows:
        x = 0
        for t in r: sheet.paste(t, (x, y)); x += t.width
        y += RH
    return sheet, tiles[1], warn


# ---------------------------------------------------------------- report
def main():
    args = sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    lod = int(args[args.index('--lod') + 1]) if '--lod' in args else 3
    cat = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
    models = json.load(open(os.path.join(OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
    work = cat['paths']['work']
    state = json.load(open(os.path.join(work, 'state.json'), encoding='utf-8')).get('frames', {})
    os.makedirs(REV, exist_ok=True)
    rows, thumbs = [], []
    for key, fr in cat['frames'].items():
        res = state.get(key, {}); e = models.get(key)
        row = dict(key=key, fr=fr, res=res, entry=e, warn=[])
        if only and key not in only: rows.append(row); continue
        if not e:
            row['warn'].append('not in models.json (run frames.py --all)'); rows.append(row); continue
        if '--no-sheets' not in args:
            t0 = time.time()
            try:
                sheet, th, w = review_one(key, e, lod)
                sheet.save(os.path.join(REV, key + '.png')); row['thumb'] = th; row['warn'] += w
                print('%-18s %.0fs' % (key, time.time() - t0), flush=True)
            except Exception as ex:
                import traceback; traceback.print_exc(); row['warn'].append('review render failed: %s' % ex)
        rows.append(row)
    # contact sheet
    cells = [r for r in rows if r.get('thumb') is not None]
    if cells and not only:
        cw, ch = 330, 560; cols = 5; rws = (len(cells) + cols - 1) // cols
        cs = Image.new('RGB', (cols * cw, rws * (ch + 44)), BG); dr = ImageDraw.Draw(cs)
        for i, r in enumerate(cells):
            th = r['thumb'].resize((cw, int(r['thumb'].height * cw / r['thumb'].width)))
            x, y = (i % cols) * cw, (i // cols) * (ch + 44)
            cs.paste(th, (x, y))
            dr.text((x + 6, y + th.height + 2), '%s   [%s]' % (r['key'], r['fr'].get('status', 'review')), fill=(240, 240, 240))
            dr.text((x + 6, y + th.height + 16), '%s %.0f u  clips %d  warn %d' % (r['fr']['class'], r['entry']['height'], sum(len(v) for v in r['entry']['anims'].values()), len(r['warn']) + len(r['res'].get('report', {}).get('warnings', []))), fill=(180, 190, 205))
        cs.save(os.path.join(REV, 'contact_sheet.png'))
    write_md(rows, only)


def write_md(rows, only):
    L = ['# IRONFRAME frame review', '',
         'Generated by `tools/review_frames.py` (do not edit the table by hand; set `status` in `data/frames.json`). Open `preview/review/contact_sheet.png` first, then `preview/review/<key>.png`',
         'for each frame: top row = front / three-quarter / side / back in the default pose (hover legs + idle arms) with a 72 u human silhouette for scale (left), hit spheres (red circles) and the waist pivot',
         '(orange line, ring at hip height); bottom strip = key pose of every clip, posed from the animation SMDs that get compiled.', '',
         'Status: `review` (not looked at), `approved`, `rejected`. `tools/frames.py` writes only approved frames into `out/addon/_gen/models.json` unless `--all` is passed; `tools/build_all.sh` passes `--all` until frames are approved.', '',
         '| key | source item | author | class / height | tris per LOD (legs / upper) | textures | clips | pivot | warnings | status |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        fr, res, e = r['fr'], r['res'], r['entry']
        item = res.get('source_item') or fr['item']
        src = '[%s](https://steamcommunity.com/sharedfiles/filedetails/?id=%s) %s' % (item, item, fr['title'].replace('|', '/'))
        if fr.get('source') == 'tripo': src = 'Tripo AI GLB `%s` %s' % (os.path.basename(fr.get('glb', '')), fr['title'].replace('|', '/'))
        ms = res.get('models', {})
        tris = ' / '.join(('/'.join(str(t) for t in ms[g]['tris']) if g in ms else '-') for g in ('legs', 'upper'))
        clips = '-'
        if e:
            a = e['anims']; clips = ('legs: ' + ', '.join(a['legs']) if a['legs'] else 'legs: static' if e['legs'] else 'no legs prop') + '<br>' + ('upper: ' + ', '.join(a['upper']) if a['upper'] else 'upper: static')
        w = list(res.get('report', {}).get('warnings', [])) + r['warn']
        if res.get('standin'): w.append('stand-in model: ' + (res.get('note') or ''))
        if res.get('warning_source'): w.append(res['warning_source'])
        if fr.get('permission') in ('none', None): w.append('no author permission: private servers only')
        if e and e['legs'] and not e['anims']['legs']: w.append('legs static (no usable leg chain or skeleton)')
        if e and not e['anims']['upper']: w.append('upper static (no usable arm chain or skeleton)')
        mats = res.get('materials', {})
        flat = [t for t, i in mats.items() if i.get('flat') or i.get('missing')]
        if flat: w.append('%d flat/missing textures' % len(flat))
        w = [x.replace('|', '/').replace('\n', ' ')[:140] for x in w]
        L.append('| %s | %s | %s | %s %s u | %s | %s | %s | %s | %s | %s |' % (
            r['key'], src, fr['author'], fr['class'], '%.0f' % e['height'] if e else '?', tris, res.get('textures', '?'), clips,
            ('%.1f, %.1f' % tuple(e['pivot'])) if e else '-', '<br>'.join(w) if w else '-', fr.get('status', 'review')))
    L += ['', 'Pivot = the pelvis / hip bone x,y in the scaled feet-origin model frame (the game script rotates both props about it); frames without a usable bone use the centre of the legs (or upper) mesh bounds.', '']
    p = os.path.join(PROJ, 'docs', 'FRAME_REVIEW.md')
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(L))
    print('wrote', p)


if __name__ == '__main__':
    main()
