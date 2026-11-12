"""IRONFRAME Sprawl: the city layer, written with the cs2-map-mcp toolset (create/mapops.py batch + matkit materials).

usage: python -I tools/arenas/sprawl_ops.py <map.vmap> <addon content dir> [--dry-run] [--job out.json]

Reads <content>/_gen/sprawl_plan.json (written by tools/arenas/sprawl.py, IF_SPRAWL_CITY=ops), writes the materials under
<content>/materials/ifr/sprawl/ (matkit: lit window walls, storefronts, neon signs) and runs one mapops batch on the map
(vis group ifr_city, replaced on every run; the map is backed up by tools/mapbackup.py first):
  towers     mesh_edit shafts with per-face materials (lit facade sides, concrete tops), storefront band + canopy at street level,
             corner pilasters, floor ledges every 512 u, setbacks on tall towers, roof slab + parapet + plant + antennas;
             about a third of the tall towers are ruins: a stepped broken top cut in 3 x 3 cells, the upper floors hollow with
             floor slabs left hanging, steel stubs, low rubble on the block slab
  streets    kerbed avenues (gen_world.street) between the crossings, junction squares, street lamp poles at the crossings
  signs      vertical neon blade signs at the plan's neon lamps (katakana / kanji words, emissive), horizontal shop signs on canopies
  weather    a 7 x 7 grid of CS2's rain particle over the play area (fxkit.weather_tiles), dim lightning flashes (fxkit)
Nothing here changes the nav grid: the towers keep the footprints and heights sprawl.py recorded (ruins only get lower, and
are never walkable roofs).
"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import matkit

MDIR = 'materials/ifr/sprawl'
CONCRETE = 'materials/concrete/hr_c/hr_concrete_wall_006.vmat'
CONCRETE2 = 'materials/de_overpass/concrete/concrete_12.vmat'
# A face's texture right-to-left is Hammer's default axis (meshedit._axes: u = +y on x faces, +x on y faces), which reads backwards
# on faces looking -x or +y (12 Nov 2026, a mirrored wall board in the preview). READ_U: the u axis that reads left to right for a
# face whose outward normal is the key.
READ_U = {(0, -1): [1, 0, 0], (0, 1): [-1, 0, 0], (-1, 0): [0, -1, 0], (1, 0): [0, 1, 0]}
def read_uv(nx, ny): return {'axis_u': READ_U[(nx, ny)], 'axis_v': [0, 0, -1], 'fit': [1, 1]}
CONCRETE_DARK = 'materials/concrete/hr_c/hr_concrete_floor_001_dark.vmat'
FLOOR = 'materials/de_overpass/concrete/concrete_floor_4.vmat'
ASPHALT = 'materials/de_overpass/asphalt/asphalt_road_worn_01.vmat'
ROOF = 'materials/de_overpass/buildings/roof_metal_painted_1.vmat'
STEEL = 'materials/de_overpass/metal/rusty_metal_1.vmat'
TRIM = 'materials/de_nuke/hr_nuke/hr_metal_trim_001.vmat'
SIGN_WORDS = ['ラーメン', 'ホテル', 'カラオケ', '薬局', '質屋', 'ゲーム', '酒場', '電器', '居酒屋', 'パチンコ', '寿司', '24時間']
WALL_WORDS = ['QUARANTINE ZONE', 'NO ENTRY', 'FLOOD BARRIER 7']   # Latin only: the horizontal sign fonts have no kanji      # the boards on the quarantine wall (sprawl.py outer_ring)
SHOP_WORDS = ['NOODLE BAR', 'PAWN', 'HOTEL', 'ARCADE', 'PHARMACY', 'KARAOKE', 'REPAIR', 'BAR 24H', 'TELECOM', 'MECH PARTS']
FACADE_UV = 1.2          # world units per texel on a 1024 basis: the 16-floor window tile = 1229 u, a storey = 76.8 u (was 2.0 = 128 u:
                         # CS2 player scale). Human scale on this map is 0.6 (tools/arenas/sprawl_detail.py), so a 300-u mech is 4 storeys
FLOOR_H = FACADE_UV * 1024 / 16
NEON = {'255 60 200': '#ff3cc8', '60 220 255': '#3cdcff', '255 160 60': '#ffa03c', '120 255 120': '#78ff78'}


# ------------------------------------------------------------------------------------------------ materials (matkit)
def window_wall(seed, lit_share, palette, size=2048, floors=16, bays=16):
    """a facade tile: concrete spandrels, mullioned windows; lit windows glow (alpha = self-illum mask). 128 px per floor / bay."""
    r = np.random.RandomState(seed)
    fh, bw = size // floors, size // bays
    base = (matkit.fbm(size, 24, seed) * 26 + 70)[..., None] * np.ones(3)                 # spandrel concrete, grey 70-96
    img = base.copy(); mask = np.zeros((size, size))
    for f in range(floors):
        dark_floor = r.uniform() < 0.25                                                   # whole dark floors read as ruin / vacancy
        for b in range(bays):
            y0, y1 = f * fh + int(fh * 0.28), f * fh + int(fh * 0.92); x0, x1 = b * bw + 8, (b + 1) * bw - 8
            lit = (not dark_floor) and r.uniform() < lit_share
            if lit:
                c = np.array(palette[r.randint(len(palette))], float) * r.uniform(0.55, 1.0)
                grad = np.linspace(1.0, 0.75, y1 - y0)[:, None, None]                       # ceiling light falls off downward
                img[y0:y1, x0:x1] = c * grad
                if r.uniform() < 0.35:                                                    # blinds: dark slats
                    img[y0:y1:6, x0:x1] *= 0.35
                mask[y0:y1, x0:x1] = 255 * r.uniform(0.6, 1.0)
            else:
                g = np.linspace(38, 18, y1 - y0)[:, None]                                 # dark glass with a sky reflection
                img[y0:y1, x0:x1] = np.stack([g * 0.8, g * 0.9, g * 1.15], -1)
            img[y0:y1, (x0 + x1) // 2 - 2:(x0 + x1) // 2 + 2] = 30                         # mullion
            img[y0 - 3:y0, x0:x1] = 105                                                   # lintel line
    img = np.clip(img, 0, 255).astype(np.uint8)
    return np.concatenate([img, mask.astype(np.uint8)[..., None]], -1)


def shopfront(seed, size=1024):
    """street-level band: 4 shop bays of lit glass, roller shutters (some down), dark frames"""
    r = np.random.RandomState(seed)
    img = np.zeros((size, size, 3)); mask = np.zeros((size, size))
    img[:] = (matkit.fbm(size, 16, seed) * 20 + 40)[..., None]
    for b in range(4):
        x0, x1 = b * 256 + 18, (b + 1) * 256 - 18; y0, y1 = 300, 1000
        if r.uniform() < 0.35:                                                            # shutter down
            img[y0:y1, x0:x1] = 95; img[y0:y1:10, x0:x1] = 60
        else:
            c = np.array([(255, 214, 160), (190, 230, 255), (255, 170, 220)][r.randint(3)], float) * r.uniform(0.6, 0.95)
            img[y0:y1, x0:x1] = c; mask[y0:y1, x0:x1] = 220
            img[y0:y1, (x0 + x1) // 2 - 3:(x0 + x1) // 2 + 3] = 25
        img[120:260, x0:x1] = (30, 30, 36)                                                # sign fascia (dark; the signs are boards)
    return np.concatenate([np.clip(img, 0, 255).astype(np.uint8), mask.astype(np.uint8)[..., None]], -1)


def _font(names, px):
    for n in names:
        try: return ImageFont.truetype(n, px)
        except OSError: pass
    return ImageFont.load_default()


def neon_sign(text, hexcol, vertical, w, h):
    """neon tube letters with a glow on a near-black plate; returns RGB (self-illum mask = brightness)"""
    col = tuple(int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    ink = Image.new('L', (w, h), 0); d = ImageDraw.Draw(ink)
    fonts = ['YuGothB.ttc', 'msgothic.ttc', 'msyhbd.ttc', 'arialbd.ttf']
    if vertical:
        n = len(text); px = int(min(w * 0.78, h * 0.86 / max(1, n)))
        f = _font(fonts, px)
        for i, ch in enumerate(text):
            bb = d.textbbox((0, 0), ch, font=f)
            d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], h * 0.07 + i * (h * 0.86 / n) + (h * 0.86 / n - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=f, fill=255)
    else:
        px = int(h * 0.62); f = _font(['bahnschrift.ttf', 'arialbd.ttf'], px)
        while px > 10:
            f = _font(['bahnschrift.ttf', 'arialbd.ttf'], px); bb = d.textbbox((0, 0), text, font=f)
            if bb[2] - bb[0] < w * 0.88: break
            px -= 4
        bb = d.textbbox((0, 0), text, font=f)
        d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], (h - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=255)
    d.rectangle([6, 6, w - 7, h - 7], outline=255, width=max(3, min(w, h) // 40))           # border tube
    core = np.asarray(ink, float) / 255
    glow = np.asarray(ink.filter(ImageFilter.GaussianBlur(min(w, h) / 28)), float) / 255
    plate = np.array([14, 12, 18], float)
    c = np.array(col, float)
    rgb = plate * (1 - np.clip(glow * 1.6, 0, 1))[..., None] + c * np.clip(glow * 1.6, 0, 1)[..., None]
    rgb = rgb * (1 - core[..., None]) + (c * 0.35 + 255 * 0.65) * core[..., None]               # white-hot tube core
    return np.clip(rgb, 0, 255).astype(np.uint8)


def materials(content):
    out = {}
    pals = dict(warm=[(255, 205, 150), (255, 186, 120), (240, 230, 200)], cool=[(170, 210, 255), (200, 225, 255), (150, 255, 230)],
                mixed=[(255, 205, 150), (170, 210, 255), (255, 120, 210), (255, 186, 120)])
    for k, (name, share) in enumerate((('warm', 0.32), ('cool', 0.30), ('mixed', 0.28), ('dark', 0.05))):
        img = window_wall(100 + k, share, pals.get(name, pals['warm']))
        out['win_' + name] = matkit.write_material(content, MDIR, 'win_' + name, img, kind='emissive', roughness=0.35, glow=2.5)
    for k in range(3):
        out['shop_%d' % k] = matkit.write_material(content, MDIR, 'shop_%d' % k, shopfront(200 + k), kind='emissive', roughness=0.3, glow=2.0)
    for k, word in enumerate(SIGN_WORDS):
        hexcol = list(NEON.values())[k % 4]
        out['vsign_%d' % k] = matkit.write_material(content, MDIR, 'vsign_%02d' % k, neon_sign(word, hexcol, True, 256, 1024), kind='emissive', roughness=0.4, glow=6.0)
    for k, word in enumerate(SHOP_WORDS):
        hexcol = list(NEON.values())[(k + 1) % 4]
        out['hsign_%d' % k] = matkit.write_material(content, MDIR, 'hsign_%02d' % k, neon_sign(word, hexcol, False, 1024, 256), kind='emissive', roughness=0.4, glow=5.0)
    for k, word in enumerate(WALL_WORDS):
        out['wsign_%d' % k] = matkit.write_material(content, MDIR, 'wsign_%02d' % k, neon_sign(word, ('#ff3a28', '#ffb030', '#ffb030')[k], False, 1024, 256), kind='emissive', roughness=0.4, glow=4.0)
    red = np.zeros((64, 64, 3), np.uint8); red[:] = (255, 30, 20)
    out['aviation'] = matkit.write_material(content, MDIR, 'aviation_red', red, kind='emissive', roughness=0.5, glow=8.0)
    lamp = np.zeros((64, 64, 3), np.uint8); lamp[:] = (255, 228, 190)
    out['lamp_head'] = matkit.write_material(content, MDIR, 'lamp_head', lamp, kind='emissive', roughness=0.5, glow=6.0)
    import sprawl_detail_mats as DM                      # the street wall tiles and everything the detail pass uses (d_*)
    out.update({'d_' + k: v for k, v in DM.materials(content).items()})
    return out


# ------------------------------------------------------------------------------------------------ ops helpers
def box(lo, hi, mat=None, mats=None):
    op = {'op': 'box', 'mins': [round(v, 1) for v in lo], 'maxs': [round(v, 1) for v in hi]}
    if mat: op['material'] = mat
    if mats: op['materials'] = mats
    return op


def shaped(lo, hi, mat=None, mats=None, uv=None, cut=(), edits=()):
    s = {'shape': 'box', 'mins': [round(v, 1) for v in lo], 'maxs': [round(v, 1) for v in hi]}
    if mat: s['material'] = mat
    if mats: s['materials'] = mats
    op = {'op': 'mesh_edit', 'shape': s}
    if cut: op['cut'] = list(cut)
    if edits: op['edits'] = list(edits)
    if uv: op['uv'] = uv
    return op


def cutter(lo, hi, mat=CONCRETE_DARK):
    return {'shape': 'box', 'mins': [round(v, 1) for v in lo], 'maxs': [round(v, 1) for v in hi], 'material': mat}


# ------------------------------------------------------------------------------------------------ the city
def tower_ops(t, mats, ruin, stats):
    x0, y0, z0, x1, y1, top = t['box']
    rnd = random.Random(t['seed'])
    ops = []
    W, D, h = x1 - x0, y1 - y0, top - z0
    face = mats['win_' + rnd.choice(['warm', 'cool', 'mixed'])] if t['lit'] else mats['win_dark']
    street = z0 <= 210                                     # on the ground or a 200-u base slab: storefronts at street level
    SB = 220.0 if street else 0.0
    if street:
        # the street wall tile of sprawl_detail_mats.storefront (3 storeys in 220 u), its pavement row shifted to this tower's base
        ops.append(shaped((x0 + 24, y0 + 24, z0 - 20), (x1 - 24, y1 - 24, z0 + SB - 4), mats={'side': mats['d_shop_%d' % (rnd.randrange(3) + t['seed'] % 2)], 'top': CONCRETE, 'bottom': CONCRETE},
                          uv={'scale': 0.25, 'shift': [0, z0 * 4.0]}))
        ops.append(box((x0 - 70, y0 - 70, z0 + SB - 2), (x1 + 70, y1 + 70, z0 + SB + 22), TRIM))      # canopy (2 u below the shaft: no coplanar faces)
        stats['storefronts'] += 1
        if rnd.random() < 0.6:                                                                # a shop sign on the canopy
            k = rnd.randrange(len(SHOP_WORDS)); side = rnd.randrange(4)
            sw, sh = min(560.0, (W if side < 2 else D) * 0.6), 140.0
            if side == 0: lo, hi = ((x0 + x1) / 2 - sw / 2, y0 - 74, z0 + SB + 22), ((x0 + x1) / 2 + sw / 2, y0 - 62, z0 + SB + 22 + sh)
            elif side == 1: lo, hi = ((x0 + x1) / 2 - sw / 2, y1 + 62, z0 + SB + 22), ((x0 + x1) / 2 + sw / 2, y1 + 74, z0 + SB + 22 + sh)
            elif side == 2: lo, hi = (x0 - 74, (y0 + y1) / 2 - sw / 2, z0 + SB + 22), (x0 - 62, (y0 + y1) / 2 + sw / 2, z0 + SB + 22 + sh)
            else: lo, hi = (x1 + 62, (y0 + y1) / 2 - sw / 2, z0 + SB + 22), (x1 + 74, (y0 + y1) / 2 + sw / 2, z0 + SB + 22 + sh)
            ops.append(shaped(lo, hi, mats['hsign_%d' % k], uv=read_uv(*((0, -1), (0, 1), (-1, 0), (1, 0))[side]))); stats['shop_signs'] += 1
    zs = z0 + SB
    # ruins: the top broken in 3 x 3 cells at different heights, the upper floors hollow
    cells = []
    if ruin:
        zb = z0 + h * rnd.uniform(0.5, 0.72)
        # rows of 3 cells; each row's x splits are staggered so no four cells meet at one corner (two diagonal cells left
        # standing would touch along an edge only: a non-manifold solid, which meshedit rightly refuses)
        for j in range(3):
            sh = (j - 1) * W * 0.09
            xs = [x0 - 12, x0 + W / 3 + sh, x0 + 2 * W / 3 + sh, x1 + 12]
            for i in range(3):
                cz = zb + rnd.uniform(0, top - zb) * (0.25 if (i, j) == (1, 1) else 1.0)
                cells.append(((xs[i], y0 + D * j / 3 - (12 if j == 0 else 0), cz), (xs[i + 1], y0 + D * (j + 1) / 3 + (12 if j == 2 else 0), top + 40)))
        hollow_z = zb - 260
        cut = [cutter(lo, hi) for lo, hi in cells] + [cutter((x0 + 36, y0 + 36, hollow_z), (x1 - 36, y1 - 36, top + 40))]
        ops.append(shaped((x0, y0, zs), (x1, y1, top), mats={'side': face, 'top': CONCRETE_DARK, 'bottom': CONCRETE}, uv={'scale': FACADE_UV}, cut=cut))
        # floor slabs left hanging inside the shell, clipped by the broken cells
        z = hollow_z + 128
        while z < max(c[0][2] for c in cells) - 40:
            ops.append(shaped((x0 + 36, y0 + 36, z - 18), (x1 - 36, y1 - 36, z), FLOOR, cut=[cutter(lo, hi, FLOOR) for lo, hi in cells]))
            z += 256
        for k in range(rnd.randint(3, 6)):                                                     # bent steel stubs on the wall tops
            i, j = rnd.randrange(3), rnd.randrange(3)
            (cx0, cy0, cz), (cx1, cy1, _) = cells[j * 3 + i]
            sx, sy = rnd.uniform(cx0 + 40, cx1 - 40), rnd.uniform(cy0 + 40, cy1 - 40)
            ops.append(shaped((sx - 9, sy - 9, cz - 30), (sx + 9, sy + 9, cz + rnd.uniform(90, 220)), STEEL,
                              edits=[{'edit': 'bend', 'degrees': rnd.uniform(-35, 35), 'axis': 'z', 'toward': rnd.choice(['x', 'y'])}]))
        if street:                                                                              # rubble round the base (low: mechs walk over it)
            for k in range(rnd.randint(4, 8)):
                side = rnd.randrange(4); along = rnd.uniform(0.1, 0.9)
                px = x0 + W * along if side < 2 else (x0 - 120 if side == 2 else x1 + 120)
                py = (y0 - 120 if side == 0 else y1 + 120) if side < 2 else y0 + D * along
                s = rnd.uniform(60, 120)
                ops.append(shaped((px - s, py - s * 0.7, z0 - 10), (px + s, py + s * 0.7, z0 + rnd.uniform(25, 55)), CONCRETE2,
                                  edits=[{'edit': 'subdivide', 'n': 2}, {'edit': 'noise', 'amplitude': 14, 'size': 48, 'seed': rnd.randrange(999)}]))
        stats['ruins'] += 1
        top_line = zb
    else:
        setback = h > 1500 and rnd.random() < 0.6
        if setback:
            zk = z0 + h * rnd.uniform(0.55, 0.7); i = min(110.0, W * 0.12, D * 0.12)
            ops.append(shaped((x0, y0, zs), (x1, y1, zk), mats={'side': face, 'top': CONCRETE, 'bottom': CONCRETE}, uv={'scale': FACADE_UV}))
            ops.append(shaped((x0 + i, y0 + i, zk), (x1 - i, y1 - i, top), mats={'side': face, 'top': CONCRETE, 'bottom': CONCRETE}, uv={'scale': FACADE_UV}))
            ops.append(box((x0 - 16, y0 - 16, zk - 2), (x1 + 16, y1 + 16, zk + 22), CONCRETE2))
            rx0, ry0, rx1, ry1 = x0 + i, y0 + i, x1 - i, y1 - i; stats['setbacks'] += 1
        else:
            ops.append(shaped((x0, y0, zs), (x1, y1, top), mats={'side': face, 'top': CONCRETE, 'bottom': CONCRETE}, uv={'scale': FACADE_UV}))
            rx0, ry0, rx1, ry1 = x0, y0, x1, y1
        # crown: roof slab, parapet ring (200 tall, as the sketch's), plant, antenna + aviation light on the tall ones
        ops.append(box((rx0, ry0, top), (rx1, ry1, top + 14), CONCRETE_DARK))
        T = top + 14                                                                          # parapets stand on the roof slab
        for lo, hi in (((rx0, ry0, T), (rx1, ry0 + 80, top + 200)), ((rx0, ry1 - 80, T), (rx1, ry1, top + 200)),
                       ((rx0, ry0 + 80, T), (rx0 + 80, ry1 - 80, top + 200)), ((rx1 - 80, ry0 + 80, T), (rx1, ry1 - 80, top + 200))):
            ops.append(box(lo, hi, CONCRETE2))
        if t.get('roof_box'):
            a = t['roof_box']; ops.append(box(a[:2] + [a[2] + 14], a[3:], mats={'top': ROOF, 'side': CONCRETE2, 'bottom': CONCRETE2}))
        if (rx1 - rx0) > 420 and not t.get('walk_roof'):
            for k in range(rnd.randint(1, 3)):
                ux, uy = rnd.uniform(rx0 + 120, rx1 - 260), rnd.uniform(ry0 + 120, ry1 - 220)
                ops.append(box((ux, uy, top + 14), (ux + 140, uy + 100, top + 14 + rnd.uniform(70, 120)), mats={'top': ROOF, 'side': TRIM, 'bottom': TRIM}))
        if h > 1800:
            ax, ay = (rx0 + rx1) / 2 + rnd.uniform(-80, 80), (ry0 + ry1) / 2 + rnd.uniform(-80, 80); ah = rnd.uniform(380, 700)
            ops.append({'op': 'cylinder', 'center': [round(ax, 1), round(ay, 1)], 'radius': 10, 'z0': top + 14, 'z1': round(top + 14 + ah, 1), 'sides': 8, 'material': STEEL})
            ops.append(box((ax - 16, ay - 16, top + 14 + ah), (ax + 16, ay + 16, top + 14 + ah + 28), mats['aviation'])); stats['antennas'] += 1
        top_line = top
    # corner pilasters and ledges every 512 u (the facade's rhythm at mech scale)
    for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        ops.append(box((cx - 28, cy - 28, zs + 4), (cx + 28, cy + 28, top_line - (4 if not ruin else 60)), CONCRETE2))   # ends off the shaft's planes
    z = math.ceil((zs + 200) / FLOOR_H) * FLOOR_H - 6          # ledges on floor lines, every 5 storeys
    while z < top_line - 300:
        ops.append(box((x0 - 14, y0 - 14, z), (x1 + 14, y1 + 14, z + 12), CONCRETE2)); z += FLOOR_H * 5
    # for the detail pass (tools/arenas/sprawl_detail.py): what this tower became
    t['_ruin'] = bool(ruin); t['_street'] = street; t['_zs'] = zs; t['_top_line'] = top_line
    t['_roof'] = None if ruin else [rx0, ry0, rx1, ry1]
    return ops


def street_ops(plan, mats):
    C = plan['centres']; B = plan['block']; P = plan['plaza']; half = plan['half']
    pitch = C[1] - C[0]
    lines = sorted(set(round((C[i] + C[i + 1]) / 2) for i in range(len(C) - 1)) | {C[0] - pitch / 2, C[-1] + pitch / 2})   # avenues incl. the outer ring
    road, side = 560.0, (plan['avenue'] - 560.0) / 2
    mats_st = {'road': ASPHALT, 'sidewalk': FLOOR, 'kerb': CONCRETE2}
    ops = []; nseg = 0
    in_plaza = lambda x, y: abs(x) < P and abs(y) < P
    for axis in ('x', 'y'):
        for c in lines:
            stops = [-half] + [v for v in lines] + [half]
            for a, b in zip(stops, stops[1:]):
                a2 = a + (road / 2 + side if a in lines else 0); b2 = b - (road / 2 + side if b in lines else 0)
                if b2 - a2 < 64: continue
                mid = (a2 + b2) / 2
                if (axis == 'x' and in_plaza(mid, c)) or (axis == 'y' and in_plaza(c, mid)): continue
                path = [[a2, c], [b2, c]] if axis == 'x' else [[c, a2], [c, b2]]
                ops.append({'op': 'street', 'path': path, 'width': road, 'sidewalk': side, 'kerb': 10, 'z': 2, 'depth': 18, 'materials': mats_st}); nseg += 1
    njun = 0
    for x in lines:
        for y in lines:
            if in_plaza(x, y): continue
            ops.append({'op': 'junction', 'centre': [x, y], 'size': road, 'z': 2, 'kerb': 10, 'sidewalk': side, 'depth': 18, 'materials': mats_st}); njun += 1
    # lamp poles at the crossings (the lights themselves are sprawl.py's light_omni2 at z 520 over the crossing)
    for (x, y) in plan['lamps']:
        px, py = x + road / 2 + side / 2, y + road / 2 + side / 2
        ops.append({'op': 'cylinder', 'center': [px, py], 'radius': 16, 'z0': 12, 'z1': 560, 'sides': 10, 'material': TRIM})
        ops.append(box((x + 40, py - 12, 540), (px + 10, py + 12, 562), TRIM))
        ops.append(box((x - 30, py - 30, 520), (x + 60, py + 30, 540), mats['lamp_head']))
    return ops, nseg, njun


def sign_ops(plan, mats):
    ops = []
    B = plan['block']
    placed = []
    hw_lines = plan.get('highways', [])
    for k, n in enumerate(plan['neon']):
        x, y, z = n['pos']; cx, cy = n['block']; s = n['side']
        if any(math.hypot(x - a, y - b) < 260 for a, b in placed): continue          # two plan spots on top of each other
        if any((ax == 'x' and abs(y - at) < plan['hw_w'] / 2 + 160) or (ax == 'y' and abs(x - at) < plan['hw_w'] / 2 + 160) for ax, at in hw_lines):
            continue                                                                 # under / through a highway deck
        placed.append((x, y))
        # a blade sign standing out from a tower's wall (sprawl.py sign_mount: the face it hangs on), readable along the street, on
        # two short arms. It used to be a flat board 120 u off the block edge, often with no wall behind it (skink52, 12 Nov 2026:
        # "signs that float unnaturally"). Out from the wall: the blade from 20 to 160 u, 20 thick, 520 tall.
        face = n.get('face')
        if face is None: continue
        nrm = 1.0 if s in (0, 2) else -1.0
        ht, th = 260.0, 10.0
        o0, o1 = sorted((face + nrm * 20, face + nrm * 160))
        mat = mats['vsign_%d' % (k % len(SIGN_WORDS))]
        for h in (-1, 1):                                                           # two halves back to back: both faces read right
            if s in (0, 1): lo, hi = (o0, y + min(0, h * th), z - ht), (o1, y + max(0, h * th), z + ht); nrm2 = (0, h)
            else: lo, hi = (x + min(0, h * th), o0, z - ht), (x + max(0, h * th), o1, z + ht); nrm2 = (h, 0)
            ops.append(shaped(lo, hi, mats={'side': mat, 'top': TRIM, 'bottom': TRIM}, uv=read_uv(*nrm2)))
        b0, b1 = sorted((face - nrm * 2, face + nrm * 24))
        for zz in (z + ht - 60, z - ht + 40):                                       # the arms, into the wall and into the blade
            if s in (0, 1): ops.append(box((b0, y - 6, zz), (b1, y + 6, zz + 14), TRIM))
            else: ops.append(box((x - 6, b0, zz), (x + 6, b1, zz + 14), TRIM))
    return ops


def wall_ops(plan, mats):
    """a lit board on the quarantine wall at the end of every street that leaves the ring: what closes the view down the street
    (sprawl.py outer_ring), flat on the wall face between two cast-in courses"""
    w = plan.get('wall')
    if not w: return []
    ops, k, F = [], 0, w['inner']
    for c in w['streets']:
        for nx, ny in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            mat = mats['wsign_%d' % (k % len(WALL_WORDS))]; k += 1
            if ny: lo, hi = (c - 520, ny * F - (14 if ny > 0 else -14), 860), (c + 520, ny * F, 1120)
            else: lo, hi = (nx * F - (14 if nx > 0 else -14), c - 520, 860), (nx * F, c + 520, 1120)
            lo, hi = [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]
            ops.append(shaped(lo, hi, mats={'side': mat, 'top': TRIM, 'bottom': TRIM}, uv=read_uv(-nx, -ny)))
    return ops


def weather_ops(plan):
    p = plan['play']
    # func_precipitation (fxkit.precipitation) is @exclude in CS2's FGD: rain is a grid of CS2's rain particle instead (relay ifr_rain:
    # FireUser1 starts, FireUser2 stops). 7 x 7 tiles of 2000 u; the overdraw cost is an in-game check (cs2-gotchas: fog particles).
    return [{'op': 'fx', 'weather_tiles': {'box': [[-p, -p, 0], [p, p, 2400]], 'kind': 'rain', 'name': 'ifr_rain', 'tile': 2000}},
            {'op': 'fx', 'lightning': {'name': 'ifr_lightning', 'origin': [0, 0, 4000], 'interval': 28, 'duration': 0.18, 'alpha': 55}}]


def build_job(vmap, content, plan, mats, dry_run=False):
    stats = dict(towers=0, ruins=0, setbacks=0, storefronts=0, shop_signs=0, antennas=0)
    ops = []
    rnd = random.Random(7)
    for t in plan['towers']:
        h = t['box'][5] - t['box'][2]
        ruin = (not t.get('edge')) and (not t['walk_roof']) and h > 1200 and rnd.random() < 0.38      # the outer ring is never ruined (hollow shells)
        ops += tower_ops(t, mats, ruin, stats); stats['towers'] += 1
    sops, nseg, njun = street_ops(plan, mats); ops += sops
    ops += sign_ops(plan, mats)
    ops += wall_ops(plan, mats)
    ops += weather_ops(plan)
    stats.update(street_segments=nseg, junctions=njun, signs=len(plan['neon']), ops=len(ops))
    job = {'in': vmap, 'out': vmap, 'group': 'ifr_city', 'content': content, 'backup': True, 'dry_run': dry_run, 'ops': ops}
    return job, stats


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    vmap, content = argv[1], argv[2]
    plan = json.load(open(os.path.join(content, '_gen', 'sprawl_plan.json')))
    mats = materials(content)
    job, stats = build_job(vmap, content, plan, mats, dry_run='--dry-run' in argv)
    if '--job' in argv: json.dump(job, open(argv[argv.index('--job') + 1], 'w'), indent=0)
    print('sprawl city: %s' % json.dumps(stats))
    import mapops
    res = mapops.run(job)
    if not res['ok']:
        print(json.dumps({k: res[k] for k in ('failed_op', 'op', 'error', 'trace') if k in res}, indent=1)); print('failed op:', json.dumps(job['ops'][res['failed_op']]))
        return 1
    print('mapops ok: %d ops, %s entities, backup %s -> %s' % (len(res['ops']), res.get('entities'), res.get('backup'), res.get('out', '(dry run)')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
