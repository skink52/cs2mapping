"""IRONFRAME weapon review gallery (skink52 approves every weapon by hand before it goes in game).

usage: python -I tools/review_weapons.py [--only key,..] [--no-sheets]

Reads out/addon/_gen/models.json (build with weapon_props.py --all), the converted SMDs + textures, the work state
(C:/source1/ironframe_work/state.json) and data/weapons.json, and writes
  preview/review/weapons/<key>.png     side / top / muzzle-on / three-quarter views, textured, plus a scale panel: the weapon in the
                                       hand (arm kinds) or on the shoulder (shoulder kinds) of a 288 u medium-frame silhouette
  preview/review/weapons_contact.png   one three-quarter thumbnail per weapon with source, triangles and status
  docs/WEAPON_REVIEW.md                the table: key, part name, source, author, triangles, textures, warnings, status
Set `status` in data/weapons.json to approved / rejected after looking; weapon_props.py writes only approved keys into models.json unless --all.
Muzzle is +X, up is +Z, grip / mount at the origin (that is the contract the game script relies on).
"""
import glob, json, math, os, re, sys
import numpy as np
from PIL import Image, ImageDraw

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'out', 'addon'); REV = os.path.join(PROJ, 'preview', 'review')
BG = (40, 44, 52)
LIGHT = np.array([0.35, -0.5, 0.8]); LIGHT /= np.linalg.norm(LIGHT)
_tex = {}


def load_smd(path):
    """-> tris (n,3,3) in model space (+x muzzle), uv (n,3,2), mats [n] (material names)"""
    L = open(path, encoding='utf-8', errors='replace').read().split('\n')
    i = L.index('triangles') + 1
    P, UV, M = [], [], []
    while i < len(L) and L[i].strip() != 'end':
        M.append(L[i].strip())
        for k in range(3):
            t = L[i + 1 + k].split(); fx, fy, fz = float(t[1]), float(t[2]), float(t[3])
            P.append([-fy, fx, fz]); UV.append([float(t[7]), float(t[8])])      # undo the (y, -x, z) import turn
        i += 4
    return np.array(P).reshape(-1, 3, 3), np.array(UV).reshape(-1, 3, 2), M


def find_tex(matdirs, mat):
    stem = re.sub(r'\.vmat$', '', mat)
    for d in matdirs:
        for pat in (stem + '_color.png', stem + '_color*.png', stem + '.png'):
            g = glob.glob(os.path.join(d, pat))
            if g: return g[0]
    return None


def get_tex(matdirs, mat):
    k = (tuple(matdirs), mat)
    if k not in _tex:
        p = find_tex(matdirs, mat)
        _tex[k] = (np.array(Image.open(p).convert('RGB'), np.float32), os.path.basename(p)) if p else (None, None)
    return _tex[k]


def raster(tris, uv, mats, matdirs, H, W, h, d, center, sc, base, bg_img=None):
    """orthographic textured raster; camera looks along d, screen right h, screen up u = h x d"""
    u = np.cross(h, d)
    img = (np.array(bg_img, np.float32) if bg_img is not None else np.full((H, W, 3), BG, np.float32)); zb = np.full((H, W), 1e9)
    X = (tris @ h - center @ h) * sc + W / 2; Y = base - (tris @ u - center @ u) * sc; Z = tris @ d
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    facing = n @ d < 0.02
    shade = 0.42 + 0.58 * np.clip(n @ LIGHT * np.sign(-(n @ d) + 1e-9), 0, 1)
    for t in np.argsort(-Z.mean(1)):
        if not facing[t]: continue
        x, y, z = X[t], Y[t], Z[t]
        x0, x1 = int(max(0, math.floor(x.min()))), int(min(W - 1, math.ceil(x.max()))); y0, y1 = int(max(0, math.floor(y.min()))), int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        dd = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(dd) < 1e-9: continue
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / dd; b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / dd; c = 1 - a - b
        m = (a >= -1e-3) & (b >= -1e-3) & (c >= -1e-3)
        zz = a * z[0] + b * z[1] + c * z[2]; sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz < sub
        if not m.any(): continue
        sub[m] = zz[m]
        tx, _ = get_tex(matdirs, mats[t])
        if tx is None: col = np.array([200, 60, 200], np.float32)[None, :]
        else:
            uu = (a * uv[t, 0, 0] + b * uv[t, 1, 0] + c * uv[t, 2, 0])[m]; vv = (a * uv[t, 0, 1] + b * uv[t, 1, 1] + c * uv[t, 2, 1])[m]
            col = tx[((1 - vv) * tx.shape[0]).astype(int) % tx.shape[0], (uu * tx.shape[1]).astype(int) % tx.shape[1]]
        img[y0:y1 + 1, x0:x1 + 1][m] = col * shade[t]
    return img


def view_dirs():
    return {'side': np.array([0, 1., 0]), 'top': np.array([0, 0, -1.]), 'muzzle': np.array([-1., 0, 0]),
            'three': np.array([-0.55, 0.62, -0.5])}


def basis(d):
    d = d / np.linalg.norm(d); h = np.array([1., 0, 0]) if abs(d[2]) > 0.99 else np.cross(d, [0, 0, 1.]); h /= np.linalg.norm(h)
    if abs(d[2]) > 0.99: h = np.array([1., 0, 0])
    return h, d


def tile(tris, uv, mats, matdirs, vname, W, H, label=None):
    h, d = basis(view_dirs()[vname]); u = np.cross(h, d)
    P = tris.reshape(-1, 3); lo, hi = P.min(0), P.max(0); center = (lo + hi) / 2
    ph, pu = P @ h, P @ u; sc = min((W - 20) / max(1e-6, ph.max() - ph.min()), (H - 40) / max(1e-6, pu.max() - pu.min()))
    cc = np.array([(ph.max() + ph.min()) / 2, (pu.max() + pu.min()) / 2])
    # re-centre by projected midpoint: shift centre along h and u
    c3 = h * cc[0] + u * cc[1] + d * (center @ d)
    img = raster(tris, uv, mats, matdirs, H, W, h, d, c3, sc, H / 2 + 8 + 0 + (0), None)
    # raster maps screen-y = base - (v - c.v)*sc, so base = H/2 centres vertically (offset 8 for the label)
    t = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(t)
    dr.text((6, 4), label or vname, fill=(235, 235, 235))
    ext = (ph.max() - ph.min(), pu.max() - pu.min())
    dr.text((6, H - 14), '%.0f x %.0f u' % ext, fill=(170, 180, 195))
    return t


def mech_bg(W, H, sc, base, x_mid, kind):
    """288 u medium-frame silhouette seen from the side (faces +x), weapon hand at x=40 z=165, shoulder mount at x=-5 z=262"""
    im = Image.new('RGB', (W, H), BG); dr = ImageDraw.Draw(im); g = (74, 82, 96); g2 = (92, 102, 118)
    def R(x0, z0, x1, z1, c=g): dr.rectangle([W / 2 + x0 * sc, base - z1 * sc, W / 2 + x1 * sc, base - z0 * sc], fill=c)
    R(-26, 0, 10, 40); R(-22, 40, 18, 125); R(-34, 116, 34, 140); R(-40, 140, 44, 236, g2); R(-12, 232, 30, 268); R(-30, 236, 30, 262, g)
    R(28, 120, 52, 200, g)                                    # arm
    dr.line([W / 2 - 80 * sc, base, W / 2 + 120 * sc, base], fill=(110, 118, 130)); dr.text((6, base - 288 * sc + 2), '288 u frame', fill=(170, 180, 195))
    return im


def scale_panel(tris, uv, mats, matdirs, kind, W, H):
    sc = (H - 40) / 300.0; base = H - 16
    bg = mech_bg(W, H, sc, base, 0, kind)
    anchor = np.array([40., 0, 165]) if kind == 'arm' else np.array([-8., 0, 268])
    d = np.array([0, 1., 0]); h = np.array([1., 0, 0])
    img = raster(tris + anchor, uv, mats, matdirs, H, W, h, d, np.array([0, 0, 0.]), sc, base, bg)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def review_sheet(smd, matdirs, kind, key, tw=520, th=330):
    tris, uv, mats = load_smd(smd)
    tl = [tile(tris, uv, mats, matdirs, v, tw, th, v) for v in ('side', 'top', 'muzzle', 'three')]
    sp = scale_panel(tris, uv, mats, matdirs, kind, tw, th * 2)
    sheet = Image.new('RGB', (tw * 3, th * 2), BG)
    sheet.paste(tl[0], (0, 0)); sheet.paste(tl[1], (tw, 0)); sheet.paste(tl[2], (0, th)); sheet.paste(tl[3], (tw, th)); sheet.paste(sp, (tw * 2, 0))
    dr = ImageDraw.Draw(sheet); dr.text((tw * 2 + 6, 4), '%s: scale (%s)' % (key, 'hand' if kind == 'arm' else 'shoulder'), fill=(235, 235, 235))
    return sheet, tl[3]


def tex_info(matdirs, mats):
    out, miss = {}, []
    for m in sorted(set(mats)):
        p = find_tex(matdirs, m)
        if p:
            try: out[m] = '%dx%d' % Image.open(p).size
            except Exception: out[m] = '?'
        else: miss.append(m)
    return out, miss


def entry_paths(key, vmdl):
    """smd + material dirs for a models.json entry"""
    base = os.path.join(OUT, os.path.splitext(vmdl)[0].replace('/', os.sep))
    smd = base + '.smd'
    if not os.path.exists(smd): smd = os.path.join(base, os.path.basename(base) + '.smd')
    mdir = os.path.join(OUT, 'materials', 'ifr', 'weapons')
    return smd, [os.path.join(mdir, key), os.path.join(mdir, 'proc')]


def main():
    args = sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    parts = json.load(open(os.path.join(PROJ, 'data', 'parts.json'), encoding='utf-8'))['parts']
    kinds = {p['key']: (p.get('kind'), p.get('name', p['key'])) for p in parts if p.get('kind') in ('arm', 'shoulder')}
    wj = json.load(open(os.path.join(PROJ, 'data', 'weapons.json'), encoding='utf-8')) if os.path.exists(os.path.join(PROJ, 'data', 'weapons.json')) else {}
    cat = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
    work = os.environ.get('IF_WORK', cat['paths']['work'])
    sp = os.path.join(work, 'state.json'); state = json.load(open(sp, encoding='utf-8')).get('weapons', {}) if os.path.exists(sp) else {}
    items = {str(i['id']): i for i in cat['weapon_props'].get('item_info', [])}
    os.makedirs(os.path.join(REV, 'weapons'), exist_ok=True)
    rows, thumbs = [], []
    for key, (kind, name) in kinds.items():
        res = state.get(key, {}); meta = wj.get(key, {})
        row = dict(key=key, name=name, kind=kind, res=res, meta=meta, warn=[], tris='-', tex='-', thumb=None)
        rows.append(row)
        if only and key not in only: continue
        if not res.get('ok'): row['warn'].append('not built (run weapon_props.py --all)'); continue
        smd, mdirs = entry_paths(key, res['vmdl'])
        if not os.path.exists(smd): row['warn'].append('smd missing: ' + smd); continue
        tris, uv, mats = load_smd(smd); row['tris'] = len(tris)
        ti, miss = tex_info(mdirs, mats); row['tex'] = ', '.join('%s %s' % (k.replace('.vmat', ''), v) for k, v in ti.items()) or '-'
        if miss: row['warn'].append('%d material(s) without a texture: %s' % (len(miss), ', '.join(m.replace('.vmat', '') for m in miss)[:80]))
        row['warn'] += list(res.get('warnings', []))
        if res.get('source') == 'procedural box': row['warn'].append('procedural box: needs a real model')
        if res.get('compiled') and not res['compiled'].get('ok'): row['warn'].append('compile failed')
        if '--no-sheets' not in args:
            try:
                sheet, th = review_sheet(smd, mdirs, kind, key)
                sheet.save(os.path.join(REV, 'weapons', key + '.png')); row['thumb'] = th; print('%-14s %d tris' % (key, row['tris']), flush=True)
            except Exception as ex:
                import traceback; traceback.print_exc(); row['warn'].append('review render failed: %s' % ex)
    cells = [r for r in rows if r['thumb'] is not None]
    if cells and not only:
        cw, ch, cols = 400, 252, 4; rws = (len(cells) + cols - 1) // cols
        cs = Image.new('RGB', (cols * cw, rws * (ch + 34)), BG); dr = ImageDraw.Draw(cs)
        for i, r in enumerate(cells):
            x, y = (i % cols) * cw, (i // cols) * (ch + 34)
            cs.paste(r['thumb'].resize((cw, ch)), (x, y))
            dr.text((x + 6, y + ch + 2), '%s  %s  [%s]' % (r['key'], r['name'], r['meta'].get('status', 'review')), fill=(240, 240, 240))
            dr.text((x + 6, y + ch + 16), '%s  %s tris  %s' % ((r['meta'].get('source') or '?')[:34], r['tris'], 'WARN' if r['warn'] else ''), fill=(180, 190, 205))
        cs.save(os.path.join(REV, 'weapons_contact.png'))
    write_md(rows, items)


def write_md(rows, items):
    L = ['# IRONFRAME weapon review', '',
         'Generated by `tools/review_weapons.py` (do not edit the table by hand; set `status` in `data/weapons.json`). Open `preview/review/weapons_contact.png` first, then `preview/review/weapons/<key>.png`:',
         'side / top / muzzle-on / three-quarter views (textured, muzzle = +X, grip or mount at the origin) and a scale panel with the weapon in the hand (arm) or on the shoulder (shoulder) of a 288 u medium frame.', '',
         'Status: `review` (not looked at), `approved`, `rejected`. `tools/weapon_props.py` writes only approved keys into `out/addon/_gen/models.json` unless `--all` is passed; `tools/build_all.sh` passes `--all` until weapons are approved.', '',
         '| key | part | source | author | triangles | textures | warnings | status |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        m, res = r['meta'], r['res']; it = items.get(str(m.get('item', '')), {})
        src = ('[%s](https://steamcommunity.com/sharedfiles/filedetails/?id=%s) %s: %s' % (m['item'], m['item'], (it.get('title') or '').replace('|', '/'), m.get('what', ''))) if m.get('item') else (m.get('source') or 'procedural box (needs a model)')
        w = [x.replace('|', '/').replace('\n', ' ')[:140] for x in r['warn']]
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (r['key'], r['name'], src, it.get('author', '-'), r['tris'], r['tex'], '<br>'.join(w) or '-', m.get('status', 'review')))
    p = os.path.join(PROJ, 'docs', 'WEAPON_REVIEW.md')
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n'); print('wrote', p)


if __name__ == '__main__':
    main()
