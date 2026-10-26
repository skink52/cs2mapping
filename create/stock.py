"""Stock CS2 tiling materials for the procedural props: which Valve material each chart material maps to and how its UVs are laid out.
Faces on these charts skip the atlas bake and get real-scale tiling UVs (per face corner) instead.

modes: plank  - board parts (part frame x = length, y = width, z = thickness) mapped onto one board strip of a boards texture
       box    - model-space box projection, S units per texture tile
       cyl    - around the part's long axis (posts, trunks), S units per tile
"""
import os
PREFIX = os.environ.get('CS2_MODEL_PREFIX', 'props')   # stock material copies go to materials/models/<PREFIX>/stock
import numpy as np

STOCK = {
    'boards': dict(vmat='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_wet.vmat', mode='plank', strips=4, tex=(1024, 512), box_S=64.0),
    'boards_dark': dict(vmat='materials/models/' + PREFIX + '/stock/boards_dark.vmat', mode='plank', strips=4, tex=(1024, 512), box_S=64.0),
    'boards_warm': dict(vmat='materials/models/' + PREFIX + '/stock/boards_warm.vmat', mode='plank', strips=4, tex=(1024, 512), box_S=64.0),
    'boards_v': dict(vmat='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_wet.vmat', mode='box', S=17.0, swap=True),
    'boards_box': dict(vmat='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_wet.vmat', mode='box', S=40.0),
    'rust': dict(vmat='materials/de_overpass/metal/rusty_metal_1.vmat', mode='box', S=96.0),
    'rust_fine': dict(vmat='materials/de_overpass/metal/rusty_metal_1.vmat', mode='box', S=36.0),
    'mud': dict(vmat='materials/de_ancient/hr_ancient_ground_mud_03_wet.vmat', mode='box', S=160.0),
    'mud_fine': dict(vmat='materials/de_ancient/hr_ancient_ground_mud_03_wet.vmat', mode='box', S=40.0),
    'bark': dict(vmat='materials/models/' + PREFIX + '/stock/bark_maple.vmat', mode='cyl', S=72.0),
    # exported from the game files into materials/models/<PREFIX>/stock (their own vmats are foliage/blend shaders)
    'hessian': dict(vmat='materials/models/' + PREFIX + '/stock/hessian.vmat', mode='chart', S=28.0),
    'hessian_b': dict(vmat='materials/models/' + PREFIX + '/stock/hessian_b.vmat', mode='chart', S=28.0),
    'hessian_c': dict(vmat='materials/models/' + PREFIX + '/stock/hessian_c.vmat', mode='chart', S=28.0),
    'paint_white': dict(vmat='materials/models/' + PREFIX + '/stock/paint_white.vmat', mode='box', S=40.0),
    'canvas': dict(vmat='materials/models/' + PREFIX + '/stock/canvas.vmat', mode='chart', S=64.0),
    'canvas_dark': dict(vmat='materials/models/' + PREFIX + '/stock/canvas_dark.vmat', mode='chart', S=64.0),
    'paint_feld': dict(vmat='materials/models/' + PREFIX + '/stock/paint_feldgrau.vmat', mode='box', S=56.0),
    'paint_khaki': dict(vmat='materials/models/' + PREFIX + '/stock/paint_khaki.vmat', mode='box', S=56.0),
    'paint_dark': dict(vmat='materials/models/' + PREFIX + '/stock/paint_dark.vmat', mode='box', S=56.0),
    'paint_khaki_l': dict(vmat='materials/models/' + PREFIX + '/stock/paint_khaki.vmat', mode='box', S=130.0),
    'brass': dict(vmat='materials/models/' + PREFIX + '/stock/brass.vmat', mode='box', S=24.0),
    'steel': dict(vmat='materials/models/' + PREFIX + '/stock/steel.vmat', mode='box', S=48.0),
    'rope': dict(vmat='materials/models/' + PREFIX + '/stock/rope.vmat', mode='cyl', S=6.0, swap=True),
    'rust_heavy': dict(vmat='materials/shared_base/metal/metal_rust_001.vmat', mode='box', S=64.0),
}

# custom vmats built from the game's textures (their own vmats use foliage/blend/trim shaders or are untinted):
# name -> colour vtex, normal vtex, paint colour (applied to the unrusted/neutral part of the texture, or as a plain tint), metalness, roughness
_HULL = 'materials/metal/metalhull003a_color_psd_80d5ae03'
_MB_N = 'materials/de_mirage/metal/metal_basic_1_normal_tga_f2f13580'
CUSTOM = {
    'hessian': dict(c='materials/pbr_defaults/default_cloth001_color_psd_e8be67f8', n='materials/pbr_defaults/default_cloth001_normal_psd_a04b35dd', tint=(0.80, 0.72, 0.58), rough=0.97),
    'hessian_b': dict(c='materials/pbr_defaults/default_cloth001_color_psd_e8be67f8', n='materials/pbr_defaults/default_cloth001_normal_psd_a04b35dd', tint=(0.66, 0.60, 0.50), rough=0.98),
    'hessian_c': dict(c='materials/pbr_defaults/default_cloth001_color_psd_e8be67f8', n='materials/pbr_defaults/default_cloth001_normal_psd_a04b35dd', tint=(0.54, 0.50, 0.43), rough=0.98),
    'boards_dark': dict(c='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_color_psd_54447bbd', n='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_normal_psd_651e3e65', tint=(0.60, 0.58, 0.54), rough=0.72),
    'boards_warm': dict(c='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_color_psd_54447bbd', n='materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_normal_psd_651e3e65', tint=(0.95, 0.84, 0.70), rough=0.8),
    'paint_white': dict(c=_HULL, n=_MB_N, paint=(0.66, 0.65, 0.60), rough=0.5, chip=True),
    'canvas': dict(c='materials/pbr_defaults/default_cloth001_color_psd_e8be67f8', n='materials/pbr_defaults/default_cloth001_normal_psd_a04b35dd', tint=(0.78, 0.76, 0.64), rough=0.93),
    'canvas_dark': dict(c='materials/pbr_defaults/default_cloth001_color_psd_e8be67f8', n='materials/pbr_defaults/default_cloth001_normal_psd_a04b35dd', tint=(0.52, 0.51, 0.43), rough=0.93),
    'paint_feldgrau': dict(c=_HULL, n=_MB_N, paint=(0.27, 0.29, 0.25), rough=0.62, chip=True),
    'paint_khaki': dict(c=_HULL, n=_MB_N, paint=(0.31, 0.28, 0.20), rough=0.62, chip=True),
    'paint_dark': dict(c=_HULL, n=_MB_N, paint=(0.16, 0.17, 0.16), rough=0.55, chip=True),
    'brass': dict(c='materials/de_mirage/metal/metal_basic_1_color_tga_c231a254', n=_MB_N, tint=(0.80, 0.60, 0.33), metal=1.0, rough=0.38),
    'steel': dict(c='materials/de_mirage/metal/metal_basic_1_color_tga_c231a254', n=_MB_N, tint=(0.42, 0.42, 0.42), metal=1.0, rough=0.45),
    'rope': dict(c='materials/de_overpass/construction/rope/rope_braid_1_color_tga_6f3139a7', n='materials/de_overpass/construction/rope/rope_braid_1_normal_tga_5d3a0f88', tint=(0.52, 0.46, 0.37), rough=0.95),
}


def _vtex(key, maxsize):
    import vtexread as V
    from PIL import Image
    im = V.decode_vtex(V.vpk_read(key + '.vtex_c'), 0)
    if max(im.size) > maxsize:
        f = maxsize / max(im.size); im = im.resize((max(1, int(im.size[0] * f)), max(1, int(im.size[1] * f))), Image.LANCZOS)
    return im


def export_custom(outdir, maxsize=1024):
    """decode the game textures named in CUSTOM and write csgo_complex vmats (+ derived colour/roughness PNGs) into materials/models/<PREFIX>/stock"""
    from PIL import Image
    rel = 'materials/models/%s/stock' % PREFIX
    d = os.path.join(outdir, rel); os.makedirs(d, exist_ok=True)
    nrm_done = {}
    for name, c in CUSTOM.items():
        col = np.asarray(_vtex(c['c'], maxsize).convert('RGB'), np.float32) / 255.0
        rough = None
        if c.get('chip'):
            # paint over the neutral grey of the hull plate, keep the chipped rust/bare patches as they are
            sat = col.max(-1) - col.min(-1)
            rust = np.clip((sat - 0.06) / 0.10, 0, 1) ** 0.8
            lum = col.mean(-1, keepdims=True)
            painted = np.array(c['paint']) * (0.7 + 0.3 * lum / max(lum.mean(), 1e-3))
            col = painted * (1 - rust[..., None]) + col * 0.85 * rust[..., None]
            rough = c['rough'] + (0.92 - c['rough']) * rust
        # untouched colour textures are shared between the tinted variants
        cfile = '%s/%s.png' % (rel, (name + '_color') if c.get('chip') else c['c'].split('/')[-1].split('_tga_')[0].split('_psd_')[0])
        Image.fromarray((col.clip(0, 1) * 255).astype(np.uint8)).save(os.path.join(outdir, cfile))
        lines = ['// %s: CS2 game texture (Valve) re-used for mg_trenchwarfare props' % name, '', 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1',
                 '\tTextureColor "%s"' % cfile, '\tg_vColorTint "[%.3f %.3f %.3f 0.000000]"' % tuple(c.get('tint', (1, 1, 1))), '\tg_flMetalness "%.3f"' % c.get('metal', 0.0)]
        if rough is not None:
            rfile = '%s/%s_rough.png' % (rel, name)
            Image.fromarray((rough.clip(0, 1) * 255).astype(np.uint8)).save(os.path.join(outdir, rfile))
            lines.append('\tTextureRoughness "%s"' % rfile)
        else:
            lines.append('\tTextureRoughness "[%.3f %.3f %.3f 0.000000]"' % ((c['rough'],) * 3))
        if c.get('n'):
            nfile = '%s/%s.png' % (rel, c['n'].split('/')[-1].split('_tga_')[0].split('_psd_')[0])
            if nfile not in nrm_done:
                a = np.asarray(_vtex(c['n'], maxsize).convert('RGBA'), np.float32) / 255.0
                x, y = a[..., 0] * 2 - 1, a[..., 1] * 2 - 1
                z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
                Image.fromarray((np.stack([x, y, z], -1) * 127.5 + 127.5).clip(0, 255).astype(np.uint8)).save(os.path.join(outdir, nfile)); nrm_done[nfile] = 1
            lines.append('\tTextureNormal "%s"' % nfile)
        lines.append('}')
        open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return sorted(CUSTOM)


# chart material -> stock key, per prop (prefix match on the prop name)
HES = ['hessian', 'hessian', 'hessian_b', 'hessian_c']
ASSIGN = [
    ('revet_', {'wood': ['boards', 'boards', 'boards', 'boards_dark', 'boards_dark', 'boards_warm'], 'bark': 'bark', 'earth': 'mud', 'galv': 'rust'}),
    ('firestep', {'wood': ['boards', 'boards', 'boards_dark'], 'bark': 'bark'}),
    ('duckboard', {'wood': ['boards', 'boards_dark', 'boards_dark']}),
    ('ladder', {'wood': 'boards'}),
    ('shelter', {'wood': 'boards', 'earth': 'mud', 'galv': 'rust', 'burlap': HES}),
    ('sandbag', {'burlap': HES}),
    ('tree_shattered', {'bark': 'bark', 'splinter': 'boards_v'}),
    ('stump_', {'bark': 'bark', 'splinter': 'boards_v'}),
    ('log_fallen', {'bark': 'bark', 'earth': 'mud', 'splinter': 'boards_v'}),
    ('cheval', {'bark': 'bark', 'wire': 'rust_fine', 'iron': 'rust_fine'}),
    ('wire_', {'wire': 'rust_fine', 'iron': 'rust_fine', 'bark': 'bark'}),
    ('tl_bagpile', {'burlap': HES}),
    ('tl_barrel', {'wood': 'boards', 'iron': 'rust_fine', 'tin': 'rust_fine'}),
    ('tl_bench', {'wood': 'boards'}),
    ('tl_brazier', {'iron': 'rust_heavy'}),
    ('tl_bucket', {'wood': 'boards', 'iron': 'rust_fine', 'rope': 'rope'}),
    ('tl_gong', {'bark': 'bark', 'brass': 'brass', 'wood': 'boards', 'iron': 'rust_fine', 'rope': 'rope'}),
    ('tl_lantern', {'tin': 'paint_dark'}),
    ('tl_periscope', {'wood': 'boards', 'tin': 'paint_khaki'}),
    ('tl_planks', {'wood': 'boards'}),
    ('tl_tins', {'tin': 'steel'}),
    ('tl_tools', {'wood': 'boards', 'iron': 'rust_fine'}),
    ('tl_wirereel', {'wood': 'boards', 'wire': 'rust_fine'}),
    ('wreck_fieldgun', {'gun': 'paint_feld', 'gunsteel': 'paint_dark', 'wood': 'boards'}),
    ('wreck_wheel', {'wood': 'boards', 'gunsteel': 'paint_dark'}),
    ('wreck_tank', {'tank': 'paint_khaki_l', 'track': 'rust_heavy', 'bark': 'bark', 'rust': 'rust', 'gunsteel': 'paint_dark'}),
    ('minenwerfer', {'gun': 'paint_feld', 'gunsteel': 'paint_dark', 'brass': 'brass', 'wood': 'boards'}),
    ('hangar', {'wood': 'boards', 'canvas': 'canvas', 'canvas_in': 'canvas_dark'}),
    ('plotting_table', {'wood': 'boards', 'gunsteel': 'paint_dark'}),
]


def assign(name):
    for pre, m in ASSIGN:
        if name.startswith(pre): return m
    return {}


def _face_data(mesh, fsel):
    F = mesh.F[fsel]; P = mesh.V[F]                      # (n,3,3)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    return F, P, n


def _rng_off(k, salt):
    r = np.random.RandomState((k * 7919 + salt) % (2 ** 31))
    return r.rand(), r.rand(), r.randint(1 << 16)


def uv_for(mesh, fsel, key):
    """per-corner uv (n,3,2) in image convention (v from the top) for the selected faces"""
    cfg = STOCK[key]
    idx = np.nonzero(fsel)[0]
    out = np.zeros((len(idx), 3, 2))
    F, P, N = _face_data(mesh, fsel)
    parts = mesh.FP[fsel]
    for p in np.unique(parts):
        sel = parts == p
        part = mesh.parts[p]
        R = np.asarray(part['R'], float); o = np.asarray(part['o'], float)
        ou, ov, ri = _rng_off(int(p), len(mesh.V))
        if cfg['mode'] == 'plank' and 'grain' in part:
            L = (P[sel] - o) @ R                           # local coords per corner
            nl = N[sel] @ R
            ext = L.reshape(-1, 3); lo, hi = ext.min(0), ext.max(0)
            w = max(hi[1] - lo[1], 1e-3); th = max(hi[2] - lo[2], 1e-3)
            k = ri % cfg['strips']; s0 = (k + 0.04) / cfg['strips']; s1 = (k + 0.96) / cfg['strips']
            ppu = (s1 - s0) * cfg['tex'][1] / w            # texture px per unit across the board
            us = ppu / cfg['tex'][0]
            u = L[..., 0] * us + ou
            ax = np.abs(nl).argmax(1)
            v = np.where(ax[:, None] == 2, s0 + (L[..., 1] - lo[1]) / w * (s1 - s0),
                         np.where(ax[:, None] == 1, s0 + (L[..., 2] - lo[2]) / w * (s1 - s0),
                                  s0 + (L[..., 1] - lo[1]) / w * (s1 - s0)))
            u = np.where(ax[:, None] == 0, (L[..., 2] - lo[2]) * us + ou, u)
            out[sel] = np.stack([u, v], -1)
        elif cfg['mode'] == 'cyl':
            Q = P[sel].reshape(-1, 3)
            c = Q.mean(0); _, _, vt = np.linalg.svd(Q - c, full_matrices=False); a = vt[0]
            b1 = np.cross(a, [0, 0, 1.0] if abs(a[2]) < 0.9 else [1.0, 0, 0]); b1 /= np.linalg.norm(b1); b2 = np.cross(a, b1)
            D = P[sel] - c
            h = D @ a; ang = np.arctan2(D @ b2, D @ b1)
            r = np.sqrt((D @ b1) ** 2 + (D @ b2) ** 2).mean()
            # unwrap per face so no face straddles the seam
            ang = np.where(ang - ang[:, :1] > np.pi, ang - 2 * np.pi, np.where(ang - ang[:, :1] < -np.pi, ang + 2 * np.pi, ang))
            S = cfg['S']
            uvc = np.stack([ang * max(r, 2.0) / S + ou, h / S + ov], -1)
            out[sel] = uvc[..., ::-1] if cfg.get('swap') else uvc
        elif cfg['mode'] == 'chart':
            # the chart's own unwrap (0..1 over w x h units) at real scale
            S = cfg['S']
            fc = mesh.FC[fsel][sel]
            wh = np.array([[mesh.charts[c]['w'], mesh.charts[c]['h']] for c in fc])
            T = mesh.T[F[sel]]
            out[sel] = np.stack([T[..., 0] * wh[:, None, 0] / S + ou, T[..., 1] * wh[:, None, 1] / S + ov], -1)
        else:
            S = cfg.get('S', cfg.get('box_S', 64.0))
            ax = np.abs(N[sel]).argmax(1)
            Q = P[sel]
            uu = np.where(ax[:, None] == 0, Q[..., 1], Q[..., 0])
            vv = np.where(ax[:, None] == 2, Q[..., 1], -Q[..., 2])
            out[sel] = np.stack([vv / S + ov, uu / S + ou], -1) if cfg.get('swap') else np.stack([uu / S + ou, vv / S + ov], -1)
    return out


def export_bark(outdir):
    """writes materials/models/tw/stock/bark_maple.vmat + textures decoded from the game's maple bark (csgo_complex, no wind)"""
    import vtexread as V
    from PIL import Image
    rel = 'materials/models/%s/stock' % PREFIX
    d = os.path.join(outdir, rel); os.makedirs(d, exist_ok=True)
    base = 'models/foliage/trees/maple/maple_01/'
    refs = V.refs(V.vpk_read(base + 'maple_tree_bark_1.vmat_c'))
    got = {}
    for r in refs:
        for k in ('color', 'normal', 'ao'):
            if '_%s_' % k in r: got[k] = r
    col = V.decode_vtex(V.vpk_read(got['color'] + '_c')).convert('RGB')
    col.save(os.path.join(d, 'bark_maple_color.png'))
    nrm = np.asarray(V.decode_vtex(V.vpk_read(got['normal'] + '_c')).convert('RGBA'), np.float32) / 255.0
    x, y = nrm[..., 0] * 2 - 1, nrm[..., 1] * 2 - 1
    z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
    Image.fromarray((np.stack([x, y, z], -1) * 127.5 + 127.5).clip(0, 255).astype(np.uint8)).save(os.path.join(d, 'bark_maple_normal.png'))
    if 'ao' in got: V.decode_vtex(V.vpk_read(got['ao'] + '_c')).convert('L').save(os.path.join(d, 'bark_maple_ao.png'))
    lines = ['// maple bark from the CS2 game files (Valve), re-used without wind animation for mg_trenchwarfare posts and trunks', '',
             'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1',
             '\tTextureColor "%s/bark_maple_color.png"' % rel, '\tTextureNormal "%s/bark_maple_normal.png"' % rel,
             '\tTextureRoughness "[0.900000 0.900000 0.900000 0.000000]"', '\tg_flMetalness "0.000"']
    if 'ao' in got: lines += ['\tTextureAmbientOcclusion "%s/bark_maple_ao.png"' % rel]
    lines += ['\tg_vColorTint "[0.820000 0.800000 0.760000 0.000000]"', '}']
    open(os.path.join(d, 'bark_maple.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
