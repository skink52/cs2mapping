"""Space Racer tracks: the designs in trackdefs.py -> sampled centreline data for the game, road / rail / pad / tube
/ scenery models for the map, pixel minimaps for the HUD and a preview picture.

usage: tracks.py <addon_out_dir> [preview.png]

Each track is centred on (0, 0) in its own box (HALF units each way); vmap.py places the boxes: two layers, each a
2 x 2 grid, so all eight fit inside the CS2 world. Everything is drawn in the retro palette (tools/retro.py) with
chunky dithered pixels.
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import s2, pixfont
from retro import *
import retro
from theme import NEON, DEPTH, defs
TRACKS, THEMES, HALF = defs().TRACKS, defs().THEMES, defs().HALF

OUT = sys.argv[1] if __name__ == '__main__' else None
PREVIEW = sys.argv[2] if len(sys.argv) > 2 and __name__ == '__main__' else None
SPACING = 48.0          # distance between centreline samples
SPAN = 14000            # distance between box centres
LAYER_Z = [-5000, 3600] # box layer heights (layer 0 holds tracks 0-3, layer 1 tracks 4-7)

def box_origin(ti):
    """world position of track ti's box centre (the track's local origin)"""
    k = ti % 4
    return [(k % 2 - 0.5) * SPAN, (k // 2 - 0.5) * SPAN, LAYER_Z[ti // 4]]

RAIL_H = 30
SKIRT = 80
CHECKPOINTS = 8
TUBE_UP = 110           # tube centre above the road
PAD_UP = 2.5            # pads, start line and hazard stripes float this far over the road (less z-fights at a distance)
FLOOR_DROP = 1500       # the grid floor sits this far under the lowest road

# ---------------------------------------------------------------- spline sampling
def catmull(p0, p1, p2, p3, t, alpha=0.5):
    """centripetal Catmull-Rom (no cusps or overshoot on unevenly spaced points); t in 0..1 between p1 and p2"""
    def kn(ti, pa, pb): return ti + max(np.linalg.norm(pb[:2] - pa[:2]), 1e-6) ** alpha
    t0 = 0.0; t1 = kn(t0, p0, p1); t2 = kn(t1, p1, p2); t3 = kn(t2, p2, p3)
    tt = t1 + (t2 - t1) * t
    A1 = (t1 - tt) / (t1 - t0) * p0 + (tt - t0) / (t1 - t0) * p1
    A2 = (t2 - tt) / (t2 - t1) * p1 + (tt - t1) / (t2 - t1) * p2
    A3 = (t3 - tt) / (t3 - t2) * p2 + (tt - t2) / (t3 - t2) * p3
    B1 = (t2 - tt) / (t2 - t0) * A1 + (tt - t0) / (t2 - t0) * A2
    B2 = (t3 - tt) / (t3 - t1) * A2 + (tt - t1) / (t3 - t1) * A3
    return (t2 - tt) / (t2 - t1) * B1 + (tt - t1) / (t2 - t1) * B2

def circ_smooth(a, k):
    """circular box filter of half width k"""
    if k <= 0: return a.copy()
    out = np.zeros_like(a)
    for d in range(-k, k + 1): out += np.roll(a, d)
    return out / (2 * k + 1)

def sample(track):
    P = np.array([(x, y, z) for x, y, z, w in track['pts']], np.float64)
    W = np.array([w for x, y, z, w in track['pts']], np.float64)
    n = len(P)
    dense = []; dw = []
    STEPS = 24
    for i in range(n):
        p0, p1, p2, p3 = P[(i - 1) % n], P[i], P[(i + 1) % n], P[(i + 2) % n]
        w1, w2 = W[i], W[(i + 1) % n]
        for k in range(STEPS):
            t = k / STEPS
            dense.append(catmull(p0, p1, p2, p3, t))
            dw.append(w1 + (w2 - w1) * t)
    dense = np.array(dense); dw = np.array(dw)
    seg = np.linalg.norm(np.diff(np.vstack([dense, dense[:1]])[:, :2], axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1]
    N = int(round(L / SPACING))
    targets = np.arange(N) * (L / N)
    idx = np.searchsorted(cum, targets, side='right') - 1
    idx = np.clip(idx, 0, len(dense) - 1)
    frac = (targets - cum[idx]) / np.maximum(seg[idx], 1e-9)
    nxt = (idx + 1) % len(dense)
    pos = dense[idx] + (dense[nxt] - dense[idx]) * frac[:, None]
    hw = dw[idx] + (dw[nxt] - dw[idx]) * frac
    if track.get('zmod'):
        pos[:, 2] += np.array([track['zmod'](k / N) for k in range(N)])
    # heights a little smoother than the control points give
    pos[:, 2] = circ_smooth(pos[:, 2], 2)
    fwd = np.roll(pos, -1, 0) - np.roll(pos, 1, 0)
    t2 = fwd[:, :2] / np.linalg.norm(fwd[:, :2], axis=1)[:, None]
    return dict(pos=pos, hw=hw, tan=t2, N=N, L=L, step=L / N)

def curvature(S):
    """signed curvature per sample (positive = turning left)"""
    tan, step = S['tan'], S['step']
    a, b = np.roll(tan, 1, 0), np.roll(tan, -1, 0)
    cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    return np.arcsin(np.clip(cross, -1, 1)) / (2 * step)

def validate(track, S):
    pos, hw, tan, N = S['pos'], S['hw'], S['tan'], S['N']
    problems = []
    ang = np.arccos(np.clip((tan * np.roll(tan, -1, 0)).sum(1), -1, 1))
    curv = ang / S['step']
    bad = np.where(hw * curv > 0.95)[0]
    if len(bad): problems.append('tight corners (edge folds) at samples %s' % bad[:10].tolist())
    crossings = []; unders = []
    idx = np.arange(N)
    for i in range(N):
        d = pos[:, :2] - pos[i, :2]
        along = d[:, 0] * tan[i, 0] + d[:, 1] * tan[i, 1]
        across = np.abs(d[:, 0] * tan[i, 1] - d[:, 1] * tan[i, 0])
        far = np.minimum(np.abs(idx - i), N - np.abs(idx - i)) > 12
        near2d = far & (np.abs(along) < S['step'] * 0.75) & (across < hw + hw[i] + 40)
        dz = pos[:, 2] - pos[i, 2]
        for j in np.where(near2d & (np.abs(dz) < 150))[0]:
            if j < i: continue
            cosang = abs(float((tan[i] * tan[j]).sum()))
            # a level crossing can't be drawn: the two decks z-fight and each road's rails run across the other
            # (Crosswire's first test). Put one road over the other, 600+ apart.
            if cosang < 0.5: problems.append('level crossing between samples %d and %d: one road must go over the other' % (i, j))
            else: problems.append('overlap between samples %d and %d (angle cos %.2f)' % (i, j, cosang))
        if (near2d & (dz > 400)).any(): unders.append(i)
        tight = near2d & (np.abs(dz) >= 150) & (np.abs(dz) < 600)
        if tight.any(): problems.append('decks only %.0f apart at sample %d' % (np.abs(dz[tight]).min(), i))
    ext = np.abs(pos[:, :2]).max()
    if ext + hw.max() + 500 > HALF: problems.append('track too big: extent %.0f' % (ext + hw.max()))
    return problems, crossings, unders

def ranges_to_set(ranges, N):
    out = set()
    for a, b in ranges:
        i = a
        for _ in range(N):
            out.add(i % N)
            if i % N == b % N: break
            i += 1
    return out

def set_to_ranges(s, N):
    """contiguous runs of a set of sample indices (on the loop) -> [(a, b)] inclusive"""
    if not s: return []
    if len(s) == N: return [(0, N - 1)]
    runs = []
    start = None
    for i in range(N):
        if i in s and (i - 1) % N not in s: start = i
        if i in s and (i + 1) % N not in s and start is not None: runs.append((start, i))
    # a run wrapping past N-1 -> 0
    if 0 in s and (N - 1) in s:
        first = [r for r in runs if r[0] == 0]; last = [r for r in runs if r[1] == N - 1]
        if first and last and first[0] != last[0]:
            runs.remove(first[0]); runs.remove(last[0]); runs.append((last[0][0], first[0][1]))
    return runs

# ---------------------------------------------------------------- textures (drawn small, quantised to the palette, upscaled)
def solid(color, s=8):
    img = np.zeros((s, s, 3), np.uint8); img[:] = color
    return img

def road_texture(th):
    """64x64 -> 512: u along the track (x), v across (y). Rumble strips at the edges, edge lines, centre dashes,
    panel seams and a dithered sheen across the middle."""
    S = 64
    yy, xx = np.mgrid[0:S, 0:S]
    base = np.array(th['road'], np.float32); alt = np.array(th['road2'], np.float32)
    v = np.abs(yy - (S - 1) / 2) / (S / 2)
    img = base[None, None, :] * np.ones((S, S, 1)) + (alt - base)[None, None, :] * (0.35 * (1 - v) ** 2)[..., None]
    n = retro.noise(S, S, 11, 8)
    img *= (0.95 + 0.1 * n)[..., None]
    seam = (xx % 32 == 0)
    img[seam] = img[seam] * 0.6
    img[(yy % 16 == 8) & (xx % 32 < 2)] = alt * 1.4
    line = np.array(th['line'], np.float32)
    rum = ((xx // 8) % 2 == 0)
    for r0, r1 in ((0, 3), (S - 3, S)):
        band = (yy >= r0) & (yy < r1)
        img[band & rum] = line; img[band & ~rum] = np.array(WHITE if th['line'] != WHITE else RED, np.float32) * 0.9
    img[(yy == 4) | (yy == S - 5)] = line * 0.8
    img[((yy == 31) | (yy == 32)) & (xx % 32 < 14)] = line
    q = quantize(img, 10)
    return up(q, 8)

def chevron_texture(color, bg, S=32, k=8):
    """pad: bright chevrons pointing along +u (the direction of travel)"""
    yy, xx = np.mgrid[0:S, 0:S]
    v = np.abs(yy - (S - 1) / 2) / (S / 2)
    phase = ((xx + v * S * 0.45) / (S / 4)) % 1.0
    img = np.zeros((S, S, 3), np.float32); img[:] = bg
    mask = phase < 0.45
    img[mask] = np.array(color, np.float32)
    img[mask & (phase < 0.12)] = np.array(WHITE, np.float32)
    img[(yy == 0) | (yy == S - 1)] = np.array(color, np.float32) * 0.6
    return up(quantize(img, 10), k)

def grid_texture(color, bg, S=32):
    img = np.zeros((S, S, 3), np.float32); img[:] = bg
    yy, xx = np.mgrid[0:S, 0:S]
    c = np.array(color, np.float32)
    img[(yy % 8 == 0) | (xx % 8 == 0)] = c * 0.7
    img[(yy % 8 < 2) & (xx % 8 < 2)] = c
    r = np.hypot(yy - S / 2, xx - S / 2) / (S / 2)
    img += (c * 0.35)[None, None, :] * np.clip(1 - r, 0, 1)[..., None]
    return up(quantize(img, 26), 8)

def slick_texture(S=32):
    """slick zone: oily wavy bands in purple and pink, so it reads as 'no grip' from far away"""
    yy, xx = np.mgrid[0:S, 0:S]
    w = np.sin((xx + 3 * np.sin(yy / S * 2 * math.pi * 2)) / S * 2 * math.pi * 3)
    img = np.zeros((S, S, 3), np.float32)
    img[:] = np.array(PURPLE, np.float32) * 0.55
    img[w > 0.55] = np.array(MAGENTA, np.float32) * 0.8
    img[w > 0.85] = np.array(PINK, np.float32)
    return up(quantize(img, 6), 8)

def rail_texture(color):
    """32 along x 16 up -> 128x64: glowing top band, dark body with bolts"""
    img = np.zeros((16, 32, 3), np.float32)
    c = np.array(color, np.float32)
    v = np.linspace(1, 0.2, 16)[:, None, None]
    img[:] = np.array(INK, np.float32) * 0.6 + c * 0.35 * v
    img[:3, :] = c; img[0, :] = np.array(WHITE, np.float32) * 0.5 + c * 0.5
    img[:, ::8] *= 0.5
    img[8:10, 3::8] = c * 0.8
    return up(quantize(img, 14), 4)

def skirt_texture(th):
    img = np.zeros((16, 16, 3), np.float32); img[:] = np.array(th['road2'], np.float32) * 0.6
    img[:, ::8] = np.array(th['post'], np.float32)
    img[::8, :] = np.array(INK, np.float32)
    return up(quantize(img, 12), 8)

def post_texture(color):
    img = np.zeros((64, 8, 3), np.float32); img[:] = INK
    img[4:10, :] = color; img[36:38, :] = np.array(color, np.float32) * 0.7
    img[:, 0] = BLACK
    return up(quantize(img, 6), 4)

def start_texture():
    yy, xx = np.mgrid[0:8, 0:8]
    img = np.where((((yy // 2) + (xx // 2)) % 2 == 0)[..., None], np.array(WHITE, np.uint8), np.array(BLACK, np.uint8))
    return up(img.astype(np.uint8), 32)

def gate_texture(color):
    img = np.zeros((16, 16, 3), np.float32); img[:] = color
    img[::4, :] = np.array(color, np.float32) * 0.45
    img[:, :2] = WHITE
    return up(quantize(img, 8), 8)

def ring_texture(color, hi):
    """flight rings: bright bands with white chevrons running round them"""
    img = np.zeros((16, 32, 3), np.float32); img[:] = color
    yy, xx = np.mgrid[0:16, 0:32]
    img[((xx + np.abs(yy - 7.5) * 0.8) % 8) < 2.5] = hi
    return up(quantize(img, 6), 8)

def hazard_texture(a=GOLD, b=BLACK):
    yy, xx = np.mgrid[0:16, 0:16]
    st = ((xx + yy) // 4) % 2 == 0
    img = np.where(st[..., None], np.array(a, np.uint8), np.array(b, np.uint8)).astype(np.uint8)
    return up(img, 8)

def sign_texture():
    """turn sign: three chevrons on black with a border (arrows point along +u)"""
    h, w = 16, 32
    img = np.zeros((h, w, 3), np.float32); img[:] = INK
    yy, xx = np.mgrid[0:h, 0:w]
    v = np.abs(yy - (h - 1) / 2) / (h / 2)
    phase = ((xx + v * h * 0.55) / (w / 3)) % 1.0
    img[(phase < 0.42) & (v < 0.75)] = GOLD
    img[:1] = img[-1:] = GOLD; img[:, :1] = img[:, -1:] = GOLD
    return up(quantize(img, 6), 8)

def beacon_texture(color):
    img = np.zeros((8, 8, 3), np.float32); img[:] = color
    img[2:6, 2:6] = WHITE
    return up(quantize(img, 6), 8)

def tube_texture(th, light):
    """inside of a tube: dark ribbed panels; `light` adds a neon strip down the middle that streams past"""
    S = 32
    yy, xx = np.mgrid[0:S, 0:S]
    img = np.zeros((S, S, 3), np.float32); img[:] = np.array(th['road2'], np.float32) * 0.7
    img[(xx % 16) < 2] = np.array(INK, np.float32)
    img[(yy == 0) | (yy == S - 1)] = np.array(BLACK, np.float32)
    if light:
        strip = (yy >= 13) & (yy <= 18)
        img[strip] = np.array(th['glow'], np.float32)
        img[strip & ((xx % 16) < 6)] = np.array(WHITE, np.float32)
    return up(quantize(img, 16), 8)

def tube_out_texture(th):
    S = 16
    yy, xx = np.mgrid[0:S, 0:S]
    img = np.zeros((S, S, 3), np.float32); img[:] = np.array(th['road2'], np.float32) * 0.5
    img[(xx % 8) == 0] = np.array(th['glow'], np.float32) * 0.6
    img[(yy % 8) == 0] = np.array(INK, np.float32)
    return up(quantize(img, 16), 8)

def floor_texture(th):
    """the synth grid far below: thin neon lines on black with dithered glow next to them"""
    S = 32
    yy, xx = np.mgrid[0:S, 0:S]
    d = np.minimum(np.minimum(yy, S - 1 - yy), np.minimum(xx, S - 1 - xx)).astype(np.float32)
    img = np.zeros((S, S, 3), np.float32); img[:] = BLACK
    c = np.array(th['floor'], np.float32)
    img += c[None, None, :] * np.clip(1 - d / 4.0, 0, 1)[..., None] * 0.5
    img[d < 1] = c
    return up(quantize(img, 30), 8)

def window_texture(th, seed, dark=1.0):
    """tower facade: rows of pixel windows, some lit in the theme colours"""
    rng = np.random.RandomState(seed)
    S = 32
    img = np.zeros((S, S, 3), np.float32); img[:] = np.array(INK, np.float32) * dark
    wins = th['win']
    for wy in range(2, S, 6):
        for wx in range(1, S, 4):
            r = rng.rand()
            if r < 0.45: col = np.array(wins[rng.randint(len(wins))], np.float32)
            elif r < 0.75: col = np.array(PLUM, np.float32)
            else: col = np.array(BLACK, np.float32)
            img[wy:wy + 3, wx:wx + 2] = col * dark
    return up(quantize(img, 6), 8)

def roof_texture(th):
    img = np.zeros((16, 16, 3), np.float32); img[:] = np.array(PLUM, np.float32) * 0.8
    img[:1, :] = img[-1:, :] = img[:, :1] = img[:, -1:] = th['glow']
    img[6:10, 6:10] = INK
    return up(quantize(img, 6), 8)

def rock_texture(base, k, seed):
    S = 32
    n = retro.noise(S, S, seed, 6)
    img = np.zeros((S, S, 3), np.float32)
    img[:] = np.array(base, np.float32) * k
    img *= (0.75 + 0.5 * n)[..., None]
    rng = np.random.RandomState(seed)
    for _ in range(5):
        cx, cy, r = rng.randint(S), rng.randint(S), rng.randint(2, 5)
        yy, xx = np.mgrid[0:S, 0:S]
        dd = np.hypot(((xx - cx + S / 2) % S) - S / 2, ((yy - cy + S / 2) % S) - S / 2)
        img[dd < r] *= 0.65
        img[(dd >= r) & (dd < r + 1)] *= 1.25
    return up(quantize(img, 24), 8)

def cloud_texture(top=True):
    S = 32
    n = retro.noise(S, S, 5 if top else 6, 6)
    c0, c1 = (np.array(WHITE, np.float32), np.array(ICE, np.float32)) if top else (np.array(ICE, np.float32), np.array(SKYBLUE, np.float32))
    img = c0[None, None, :] * n[..., None] + c1[None, None, :] * (1 - n[..., None])
    return up(quantize(img, 50), 8)

def crystal_texture(color, k):
    S = 16
    yy, xx = np.mgrid[0:S, 0:S]
    img = np.zeros((S, S, 3), np.float32); img[:] = np.array(color, np.float32) * k
    img[(xx + yy) % 8 == 0] = np.array(WHITE, np.float32) * min(1, k)
    return up(quantize(img, 20), 8)

def letter_texture(color):
    img = np.zeros((8, 8, 3), np.float32); img[:] = color
    img[0, :] = img[:, 0] = np.array(WHITE, np.float32) * 0.6 + np.array(color, np.float32) * 0.4
    return up(quantize(img, 4), 8)

def billboard_texture(text, th):
    """a pixel-font slogan on a dark board with a border: 256x32 -> 1024x128"""
    W, H = 256, 32
    img = np.zeros((H, W, 3), np.uint8); img[:] = INK
    img[:2, :] = img[-2:, :] = th['glow']; img[:, :2] = img[:, -2:] = th['glow']
    img[3:4, 3:-3] = img[-4:-3, 3:-3] = th['road2']
    t = pixfont.render(text, scale=2, color=th['line'], shadow=BLACK, gap=0)
    th_, tw = t.shape[:2]
    if tw > W - 8:
        t = pixfont.render(text, scale=1, color=th['line'], shadow=BLACK)
        th_, tw = t.shape[:2]
    y0, x0 = (H - th_) // 2, (W - tw) // 2
    a = t[..., 3:4] > 0
    img[y0:y0 + th_, x0:x0 + tw] = np.where(a, t[..., :3], img[y0:y0 + th_, x0:x0 + tw])
    # little blinking-light dots along the frame
    for x in range(8, W - 8, 16): img[1, x] = WHITE; img[-2, x] = WHITE
    return up(img, 4)

if NEON:
    from neonlook import *          # Neon Racer: the same pieces drawn as glowing lines on black, in chunky pixels

# ---------------------------------------------------------------- materials
SHARED = {}
def shared_materials():
    mdir = 'materials/spr/track'
    SHARED['boost'] = s2.write_material(OUT, mdir + '/pad_boost', chevron_texture(GOLD, RUST), comment='boost pad')
    SHARED['charge'] = s2.write_material(OUT, mdir + '/pad_charge', grid_texture(ICE, NAVY), comment='charge platform')
    SHARED['slick'] = s2.write_material(OUT, mdir + '/pad_slick', slick_texture(), comment='slick zone')
    SHARED['start'] = s2.write_material(OUT, mdir + '/startline', start_texture(), comment='start line')
    SHARED['edge'] = s2.write_material(OUT, mdir + '/edge_hazard', hazard_texture(), comment='rail-less edge stripe')
    SHARED['ramp'] = s2.write_material(OUT, mdir + '/ramp', chevron_texture(GOLD, BLACK), comment='jump ramp')
    SHARED['sign'] = s2.write_material(OUT, mdir + '/turn_sign', sign_texture(), comment='turn sign (front only: its back is not drawn)')
    SHARED['back'] = s2.write_material(OUT, mdir + '/board_back', solid(INK), comment='back of boards')
    SHARED['white'] = s2.write_material(OUT, mdir + '/white', solid(WHITE), comment='white light')
    SHARED['cloud'] = s2.write_material(OUT, mdir + '/cloud_top', cloud_texture(True), comment='cloud')
    SHARED['cloud2'] = s2.write_material(OUT, mdir + '/cloud_side', cloud_texture(False), comment='cloud side')
    SHARED['ring'] = s2.write_material(OUT, mdir + '/ring_boost', ring_texture(GOLD, WHITE), comment='flight boost ring')
    SHARED['cring'] = s2.write_material(OUT, mdir + '/ring_charge', ring_texture(SKYBLUE, ICE), comment='flight charge ring')

def build_materials(track):
    th = THEMES[track['theme']]
    tid = track['id']
    m = {}
    md = 'materials/spr/track/' + tid
    W = lambda key, img, c: s2.write_material(OUT, '%s/%s' % (md, key), img, comment='%s %s' % (c, tid))
    m['road'] = W('road', road_texture(th), 'road')
    m['rail'] = W('rail', rail_texture(th['rail']), 'rail')
    m['skirt'] = W('skirt', skirt_texture(th), 'skirt')
    m['post'] = W('post', post_texture(th['post']), 'post')
    m['gate'] = W('gate', gate_texture(th['gate']), 'gate')
    m['beacon'] = W('beacon', beacon_texture(th['rail']), 'beacon')
    m['tube'] = W('tube', tube_texture(th, False), 'tube')
    m['tubelight'] = W('tubelight', tube_texture(th, True), 'tube light')
    m['tubeout'] = W('tubeout', tube_out_texture(th), 'tube outside')
    m['frame'] = W('frame', hazard_texture(th['glow'], BLACK), 'tube frame')
    m['floor'] = W('floor', floor_texture(th), 'grid floor')
    m['letter'] = W('letter', letter_texture(th['line']), 'letters')
    m['letter2'] = W('letter2', letter_texture(shade(th['line'], 0.55)), 'letter sides')
    m['win'] = W('win', window_texture(th, 1), 'tower')
    m['win2'] = W('win2', window_texture(th, 2, 0.7), 'tower shade')
    m['roof'] = W('roof', roof_texture(th), 'roof')
    base = th['planet'][0] if track['scenery'] != 'crystals' else th['glow']
    if DEPTH:
        m['kelp'] = s2.write_material(OUT, '%s/kelp' % md, kelp_texture(th['glow']), blend=0, backfaces=True, comment='kelp ' + tid)
    for k, (name, f) in enumerate((('rock0', 1.0), ('rock1', 0.7), ('rock2', 0.45))):
        if DEPTH: m[name] = W(name, crystal_texture(th['accent'] if track['scenery'] == 'coral' else (70, 90, 110), f * (1.1 if track['scenery'] == 'coral' else 0.8)), 'coral / rock')
        elif track['scenery'] == 'crystals': m[name] = W(name, crystal_texture(th['glow'], f * 1.1), 'crystal')
        else: m[name] = W(name, rock_texture(TAN if track['scenery'] != 'rings' else SAND, f, 40 + k), 'rock')
    for k, text in enumerate(track.get('slogans', [])):
        m['bill%d' % k] = W('bill%d' % k, billboard_texture(text, th), 'billboard')
    return m

# ---------------------------------------------------------------- geometry
def voxel_text(text, center, right, upv, fwd, vox, depth, mat, mat2):
    """pixel-font letters as voxels: the front faces along fwd, read left to right along `right`"""
    m = pixfont.text_voxels(text, gap=1)
    m = m[:, :m.shape[1] - 1] if m.shape[1] > 1 else m
    H, Wd = m.shape
    tris = []
    def P(a, b, k):
        return (center[0] + right[0] * (a - Wd * vox / 2) + upv[0] * (b + H * vox / 2) + fwd[0] * k,
                center[1] + right[1] * (a - Wd * vox / 2) + upv[1] * (b + H * vox / 2) + fwd[1] * k,
                center[2] + right[2] * (a - Wd * vox / 2) + upv[2] * (b + H * vox / 2) + fwd[2] * k)
    h = depth / 2
    neg = lambda v: (-v[0], -v[1], -v[2])
    uv = ((0, 0), (1, 0), (1, 1), (0, 1))
    for r in range(H):
        for c in range(Wd):
            if not m[r, c]: continue
            a0, a1 = c * vox, (c + 1) * vox
            b0, b1 = -(r + 1) * vox, -r * vox
            tris += s2.quad_n(mat, P(a0, b0, h), P(a1, b0, h), P(a1, b1, h), P(a0, b1, h), *uv, fwd)
            tris += s2.quad_n(mat2, P(a0, b0, -h), P(a1, b0, -h), P(a1, b1, -h), P(a0, b1, -h), *uv, neg(fwd))
            if c == 0 or not m[r, c - 1]: tris += s2.quad_n(mat2, P(a0, b0, -h), P(a0, b0, h), P(a0, b1, h), P(a0, b1, -h), *uv, neg(right))
            if c == Wd - 1 or not m[r, c + 1]: tris += s2.quad_n(mat2, P(a1, b0, -h), P(a1, b0, h), P(a1, b1, h), P(a1, b1, -h), *uv, right)
            if r == 0 or not m[r - 1, c]: tris += s2.quad_n(mat2, P(a0, b1, -h), P(a1, b1, -h), P(a1, b1, h), P(a0, b1, h), *uv, upv)
            if r == H - 1 or not m[r + 1, c]: tris += s2.quad_n(mat2, P(a0, b0, -h), P(a1, b0, -h), P(a1, b0, h), P(a0, b0, h), *uv, neg(upv))
    return tris, Wd * vox, H * vox

def icosphere(radius, rng, squash=(1, 1, 1), rough=0.25):
    t = (1 + 5 ** 0.5) / 2
    v = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                  (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], np.float64)
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    v /= np.linalg.norm(v, axis=1)[:, None]
    v *= (1 + rough * (rng.rand(len(v)) - 0.5) * 2)[:, None]
    v *= np.array(squash)[None, :] * radius
    return v, f

LIGHT = np.array([0.45, -0.35, 0.82]); LIGHT /= np.linalg.norm(LIGHT)
def shaded_mesh(v, faces, center, rot, mats):
    """faces coloured by a fixed light direction from three materials (light, mid, dark): flat-shaded pixel look"""
    vv = v @ rot.T + np.array(center)[None, :]
    tris = []
    for a, b, c in faces:
        pa, pb, pc = vv[a], vv[b], vv[c]
        n = np.cross(pb - pa, pc - pa)
        ln = np.linalg.norm(n)
        if ln < 1e-6: continue
        n /= ln
        cen = (pa + pb + pc) / 3 - np.array(center)
        if np.dot(n, cen) < 0: n = -n
        k = float(np.dot(n, LIGHT))
        mat = mats[0] if k > 0.35 else mats[1] if k > -0.2 else mats[2]
        uvs = [((p[0] + p[2]) / 256.0, (p[1] - p[2]) / 256.0) for p in (pa, pb, pc)]
        tris += s2.tri_n(mat, tuple(pa), tuple(pb), tuple(pc), uvs[0], uvs[1], uvs[2], tuple(n))
    return tris

def rot_matrix(rng, tilt=1.0):
    a, b, c = rng.rand(3) * 2 * math.pi * np.array([1, tilt, tilt])
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    Ry = np.array([[math.cos(c), 0, math.sin(c)], [0, 1, 0], [-math.sin(c), 0, math.cos(c)]])
    return Rz @ Rx @ Ry

class Geo:
    """the road surface at sample i: banked edges, ramp lift"""
    def __init__(self, S, lift, tb):
        self.pos, self.hw, self.tan, self.N = S['pos'], S['hw'], S['tan'], S['N']
        self.nrm = np.stack([-self.tan[:, 1], self.tan[:, 0]], 1)
        self.lift, self.tb = lift, tb
    def at(self, i, d, dz=0.0):
        """point at sample i, lateral d (left positive), on the banked road surface (+ dz)"""
        i %= self.N
        p, n = self.pos[i], self.nrm[i]
        return (p[0] + n[0] * d, p[1] + n[1] * d, p[2] + self.lift[i] - d * self.tb[i] + dz)
    def L(self, i, k=1.0): return self.at(i, self.hw[i % self.N] * k)
    def R(self, i, k=1.0): return self.at(i, -self.hw[i % self.N] * k)

def Z(p, dz): return (p[0], p[1], p[2] + dz)

def track_tris(track, S, G, feats, gapset, cps, road, tubes, mats, th):
    pos, hw, tan, N, step = S['pos'], S['hw'], S['tan'], S['N'], S['step']
    nrm = G.nrm
    tris = []
    UL = 640.0
    rampseg = {}
    for f in feats:
        if f['kind'] == 'ramp':
            for k, i in enumerate(range(f['a'], f['a'] + ((f['b'] - f['a']) % N) + 1)): rampseg[i % N] = k
    for i in range(N):
        if not road[i]: continue
        j = i + 1
        u0, u1 = i * step / UL, (i + 1) * step / UL
        l0, r0, l1, r1 = G.L(i), G.R(i), G.L(j), G.R(j)
        if i in rampseg:
            k0 = rampseg[i]
            tris += s2.quad('ramp', r0, r1, l1, l0, (k0 * step / 256.0, 1), ((k0 + 1) * step / 256.0, 1), ((k0 + 1) * step / 256.0, 0), (k0 * step / 256.0, 0), (0, 0, 1))
        else:
            tris += s2.quad('road', r0, r1, l1, l0, (u0, 1), (u1, 1), (u1, 0), (u0, 0), (0, 0, 1))
        bz0, bz1 = -SKIRT - G.lift[i % N], -SKIRT - G.lift[j % N]
        tris += s2.quad('skirt', Z(l0, bz0), Z(l1, bz1), l1, l0, (u0, 1), (u1, 1), (u1, 0), (u0, 0), (nrm[i, 0], nrm[i, 1], 0))
        tris += s2.quad('skirt', r0, r1, Z(r1, bz1), Z(r0, bz0), (u0, 0), (u1, 0), (u1, 1), (u0, 1), (-nrm[i, 0], -nrm[i, 1], 0))
        tris += s2.quad('skirt', Z(l0, bz0), Z(l1, bz1), Z(r1, bz1), Z(r0, bz0), (u0, 0), (u1, 0), (u1, 1), (u0, 1), (0, 0, -1))
        # an open end facing a jump gap: a cliff face with a hazard stripe along the lip
        for end, sgn in ((j, 1), (i, -1)):
            nb = end if sgn > 0 else i - 1
            if road[nb % N]: continue
            tl, tr = (l1, r1) if sgn > 0 else (l0, r0)
            nn = (tan[end % N, 0] * sgn, tan[end % N, 1] * sgn, 0)
            bz = -SKIRT - G.lift[end % N]
            tris += s2.quad_n('edge', Z(tr, bz), Z(tl, bz), tl, tr, (0, 1), (4, 1), (4, 0), (0, 0), nn)
            d = (-tan[end % N, 0] * 30 * sgn, -tan[end % N, 1] * 30 * sgn)
            tris += s2.quad_n('edge', Z(tr, PAD_UP), Z((tr[0] + d[0], tr[1] + d[1], tr[2]), PAD_UP), Z((tl[0] + d[0], tl[1] + d[1], tl[2]), PAD_UP), Z(tl, PAD_UP),
                              (0, 0), (0, 1), (4, 1), (4, 0), (0, 0, 1))
        if i in gapset:
            for side in (1, -1):
                pa, pb = (l0, l1) if side > 0 else (r0, r1)
                ia, ib = (G.L(i, 0.92), G.L(j, 0.92)) if side > 0 else (G.R(i, 0.92), G.R(j, 0.92))
                tris += s2.quad_n('edge', Z(ia, PAD_UP), Z(ib, PAD_UP), Z(pb, PAD_UP), Z(pa, PAD_UP), (u0 * 4, 0), (u1 * 4, 0), (u1 * 4, 1), (u0 * 4, 1), (0, 0, 1))
        else:
            ur0, ur1 = i * step / 256.0, (i + 1) * step / 256.0
            for side in (1, -1):
                e0, e1 = (l0, l1) if side > 0 else (r0, r1)
                o0 = G.at(i, side * (hw[i] + 12)); o1 = G.at(j, side * (hw[j % N] + 12))
                n_in = (-nrm[i, 0] * side, -nrm[i, 1] * side, 0)
                tris += s2.quad_n('rail', e0, e1, Z(e1, RAIL_H), Z(e0, RAIL_H), (ur0, 0), (ur1, 0), (ur1, 1), (ur0, 1), n_in)
                tris += s2.quad_n('rail', Z(e0, RAIL_H), Z(e1, RAIL_H), Z(o1, RAIL_H), Z(o0, RAIL_H), (ur0, 1), (ur1, 1), (ur1, 0.9), (ur0, 0.9), (0, 0, 1))
                tris += s2.quad_n('rail', Z(o0, RAIL_H), Z(o1, RAIL_H), Z(o1, bz1), Z(o0, bz0), (ur0, 1), (ur1, 1), (ur1, 0), (ur0, 0), (-n_in[0], -n_in[1], 0))
    # pads: quads 0.5 above the road between lateral fractions (lat -1 = left edge)
    for ft in feats:
        kind, a, b, l0f, l1f = ft['kind'], ft['a'], ft['b'], ft['l0'], ft['l1']
        if kind in ('ramp', 'ring', 'cring'): continue          # flight rings are drawn as rings (flight_tris), not pads
        i = a; k = 0
        for _ in range(N):
            j = i + 1
            uu = 1.0 if kind == 'boost' else 0.5
            u0, u1 = k * step / 256.0 * uu, (k + 1) * step / 256.0 * uu
            p00, p01 = G.at(i, -hw[i % N] * l1f, PAD_UP), G.at(j, -hw[j % N] * l1f, PAD_UP)
            p11, p10 = G.at(j, -hw[j % N] * l0f, PAD_UP), G.at(i, -hw[i % N] * l0f, PAD_UP)
            tris += s2.quad_n(kind, p00, p01, p11, p10, (u0, 1), (u1, 1), (u1, 0), (u0, 0), (0, 0, 1))
            if i % N == b % N: break
            i += 1; k += 1
    # start line
    tris += s2.quad_n('start', Z(G.R(0), PAD_UP + 1), Z(G.R(1), PAD_UP + 1), Z(G.L(1), PAD_UP + 1), Z(G.L(0), PAD_UP + 1), (0, 1), (1, 1), (1, 0), (0, 0), (0, 0, 1))
    # checkpoint gates (not at the start): two pylons, a crossbar and the sector number in voxel digits
    for k, ci in enumerate(cps[1:]):
        out = 90
        l, r = G.at(ci, hw[ci] + out), G.at(ci, -hw[ci] - out)
        for p in (l, r):
            tris += s2.box_tris('gate', p[0] - 18, p[1] - 18, p[2] - SKIRT, p[0] + 18, p[1] + 18, p[2] + 330)
        dx, dy = r[0] - l[0], r[1] - l[1]; ln = math.hypot(dx, dy); dx /= ln; dy /= ln
        t = (-dy * 16, dx * 16)
        a0 = (l[0] + t[0], l[1] + t[1], l[2] + 300); a1 = (r[0] + t[0], r[1] + t[1], r[2] + 300)
        b0 = (l[0] - t[0], l[1] - t[1], l[2] + 300); b1 = (r[0] - t[0], r[1] - t[1], r[2] + 300)
        for dz, nz in ((0, -1), (30, 1)):
            tris += s2.quad_n('gate', Z(a0, dz), Z(a1, dz), Z(b1, dz), Z(b0, dz), (0, 0), (ln / 64, 0), (ln / 64, 1), (0, 1), (0, 0, nz))
        tris += s2.quad_n('gate', a0, a1, Z(a1, 30), Z(a0, 30), (0, 0), (ln / 64, 0), (ln / 64, 1), (0, 1), (dy, -dx, 0))
        tris += s2.quad_n('gate', b1, b0, Z(b0, 30), Z(b1, 30), (0, 0), (ln / 64, 0), (ln / 64, 1), (0, 1), (-dy, dx, 0))
        c = ((l[0] + r[0]) / 2, (l[1] + r[1]) / 2, max(l[2], r[2]) + 300 + 30 + 60)
        tv, _, _ = voxel_text('%d' % (k + 1), c, (-nrm[ci, 0], -nrm[ci, 1], 0), (0, 0, 1), (-tan[ci, 0], -tan[ci, 1], 0), 12, 14, 'letter', 'letter2')
        tris += tv
    # start gantry: two towers, a beam and the track's name in voxel letters facing the grid
    cols = len(track['title']) * 9 - 1
    vox = max(9, min(18, (2 * hw[0] + 1100) / cols))
    out = max(140, cols * vox / 2 - hw[0] + 90)          # the towers stand clear of the title's letters
    l, r = G.at(0, hw[0] + out), G.at(0, -hw[0] - out)
    top = max(l[2], r[2]) + 470
    for p in (l, r):
        tris += s2.box_faces(dict(top='post', x='gate', y='gate'), p[0] - 40, p[1] - 40, p[2] - SKIRT - 100, p[0] + 40, p[1] + 40, top + 40)
        tris += s2.box_tris('beacon', p[0] - 50, p[1] - 50, top + 40, p[0] + 50, p[1] + 50, top + 100)
    right = (-nrm[0, 0], -nrm[0, 1], 0); fwd = (-tan[0, 0], -tan[0, 1], 0)
    c = ((l[0] + r[0]) / 2, (l[1] + r[1]) / 2, top + 4 * vox + 10)
    tv, tw, thh = voxel_text(track['title'], c, right, (0, 0, 1), fwd, vox, 20, 'letter', 'letter2')
    tris += tv
    # the same name on the far side, reading the right way for anyone coming the other way (the grid flyover)
    c2 = (c[0] + tan[0, 0] * 26, c[1] + tan[0, 1] * 26, c[2])
    tv2, _, _ = voxel_text(track['title'], c2, (-right[0], -right[1], 0), (0, 0, 1), (-fwd[0], -fwd[1], 0), vox, 20, 'letter', 'letter2')
    tris += tv2
    span = max(tw / 2 + 60, math.hypot(r[0] - l[0], r[1] - l[1]) / 2)
    bl = (c[0] - right[0] * span, c[1] - right[1] * span); br = (c[0] + right[0] * span, c[1] + right[1] * span)
    for z0, z1, mat in ((top - 30, top, 'gate'), (top + thh + 20, top + thh + 40, 'gate')):
        tris += box_along(mat, bl, br, z0, z1, 18)
    # beacons: tall pylons with glowing caps on alternating sides, so the line of the course reads from far away
    rng = np.random.RandomState(sum(map(ord, track['id'])))
    pts_all = pos[:, :2]
    for k, i in enumerate(range(5, N, 10)):
        if not road[i] or tubes[i]: continue
        side = 1.0 if k % 2 == 0 else -1.0
        p = G.at(i, side * (hw[i] + 190))
        dd = np.hypot(pts_all[:, 0] - p[0], pts_all[:, 1] - p[1]) - hw
        if ((np.abs(pos[:, 2] - p[2]) < 900) & (dd < 120)).any(): continue
        h = 520 + rng.randint(0, 420)
        tris += s2.box_tris('post', p[0] - 14, p[1] - 14, p[2] - SKIRT - 160, p[0] + 14, p[1] + 14, p[2] + h, uscale=1 / 256.0)
        tris += s2.box_tris('beacon', p[0] - 32, p[1] - 32, p[2] + h, p[0] + 32, p[1] + 32, p[2] + h + 64)
        # tied to the track: an arm under the road's edge and a stepped brace from the pylon's foot up to the road's belly
        e, m = G.at(i, side * hw[i]), G.at(i, side * hw[i] * 0.35)
        zu = min(e[2], m[2]) - SKIRT
        tris += box_along('post', (p[0], p[1]), (m[0], m[1]), zu - 26, zu - 2, 10)
        foot = p[2] - SKIRT - 150
        if zu - 40 > foot:
            steps = 5
            for s_ in range(steps):
                t0, t1 = s_ / steps, (s_ + 1) / steps
                a2 = (p[0] + (m[0] - p[0]) * t0, p[1] + (m[1] - p[1]) * t0)
                b2 = (p[0] + (m[0] - p[0]) * t1, p[1] + (m[1] - p[1]) * t1)
                z0 = foot + (zu - 26 - foot) * t0
                tris += box_along('post', a2, b2, z0, z0 + (zu - 26 - foot) / steps + 6, 8)
    # turn signs on the outside of every real corner, facing the cars coming towards them
    head = np.unwrap(np.arctan2(tan[:, 1], tan[:, 0]))
    total = head[-1] - head[0] + math.atan2(math.sin(head[0] - head[-1]), math.cos(head[0] - head[-1]))
    ext_head = np.concatenate([head, head + total])
    turn = np.array([ext_head[i + 12] - ext_head[i] for i in range(N)])
    last = -99
    for i in range(N):
        if abs(turn[i]) < 0.7 or abs(turn[i - 3]) >= 0.7 or i - last < 20: continue
        si = (i - 6) % N
        if not road[si] or tubes[si]: continue
        last = i
        left = turn[i] > 0
        side = -1.0 if left else 1.0
        c = G.at(si, side * (hw[si] + 90))
        # one-sided: the face looks back at the cars coming (left to right as they see it), the arrows point into the
        # turn; from behind there is nothing (a two-sided sign showed its mirror image to cars that had passed it)
        dirv = (-nrm[si, 0], -nrm[si, 1])
        w, z0, z1 = 360, 60, 240
        p0 = (c[0] - dirv[0] * w / 2, c[1] - dirv[1] * w / 2, c[2] + z0); p1 = (c[0] + dirv[0] * w / 2, c[1] + dirv[1] * w / 2, c[2] + z0)
        ua, ub = (1, 0) if left else (0, 1)
        tris += s2.quad_n('sign', p0, p1, Z(p1, z1 - z0), Z(p0, z1 - z0), (ua, 0), (ub, 0), (ub, 1), (ua, 1), (-tan[si, 0], -tan[si, 1], 0))
        for q in (p0, p1):
            tris += s2.box_tris('post', q[0] - 10, q[1] - 10, q[2] - z0 - SKIRT, q[0] + 10, q[1] + 10, q[2], uscale=1 / 256.0)
    tris += tube_tris(S, G, tubes, road)
    return tris

def box_along(mat, a, b, z0, z1, half):
    """a beam from a to b (2D) between heights z0..z1, half thickness `half`"""
    dx, dy = b[0] - a[0], b[1] - a[1]; ln = math.hypot(dx, dy) or 1; dx /= ln; dy /= ln
    nx, ny = -dy * half, dx * half
    c = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    tris = []
    uv = ((0, 0), (ln / 128, 0), (ln / 128, 1), (0, 1))
    tris += s2.quad_n(mat, (c[0][0], c[0][1], z1), (c[1][0], c[1][1], z1), (c[2][0], c[2][1], z1), (c[3][0], c[3][1], z1), *uv, (0, 0, 1))
    tris += s2.quad_n(mat, (c[0][0], c[0][1], z0), (c[1][0], c[1][1], z0), (c[2][0], c[2][1], z0), (c[3][0], c[3][1], z0), *uv, (0, 0, -1))
    for p, q, n in ((c[0], c[1], (-dy, dx, 0)), (c[2], c[3], (dy, -dx, 0)), (c[1], c[2], (dx, dy, 0)), (c[3], c[0], (-dx, -dy, 0))):
        tris += s2.quad_n(mat, (p[0], p[1], z0), (q[0], q[1], z0), (q[0], q[1], z1), (p[0], p[1], z1), *uv, n)
    return tris

def tube_radius(hw): return hw + 270

def tube_tris(S, G, tubes, road):
    """octagonal tubes over the road where tubes[i]: neon-striped inside, panelled outside, a hazard frame at each mouth"""
    pos, hw, tan, N, step = S['pos'], S['hw'], S['tan'], S['N'], S['step']
    nrm = G.nrm
    tris = []
    K = 8
    def ring(i, R):
        i %= N
        c = np.array([pos[i, 0], pos[i, 1], pos[i, 2] + G.lift[i] + TUBE_UP])
        out = []
        for k in range(K):
            a = (k + 0.5) * 2 * math.pi / K
            out.append(tuple(c + np.array([nrm[i, 0], nrm[i, 1], 0]) * math.cos(a) * R + np.array([0, 0, 1]) * math.sin(a) * R))
        return out, c
    for i in range(N):
        if not tubes[i] or not tubes[(i + 1) % N]: continue
        R0, R1 = tube_radius(hw[i]), tube_radius(hw[(i + 1) % N])
        A, ca = ring(i, R0); B, cb = ring(i + 1, R1)
        Ao, _ = ring(i, R0 + 24); Bo, _ = ring(i + 1, R1 + 24)
        u0, u1 = i * step / 256.0, (i + 1) * step / 256.0
        for k in range(K):
            k2 = (k + 1) % K
            mid = ((A[k][0] + A[k2][0]) / 2 - ca[0], (A[k][1] + A[k2][1]) / 2 - ca[1], (A[k][2] + A[k2][2]) / 2 - ca[2])
            inward = (-mid[0], -mid[1], -mid[2])
            mat = 'tubelight' if k in (0, 3) else 'tube'
            tris += s2.quad_n(mat, A[k], B[k], B[k2], A[k2], (u0, 0), (u1, 0), (u1, 1), (u0, 1), inward)
            tris += s2.quad_n('tubeout', Ao[k], Bo[k], Bo[k2], Ao[k2], (u0, 0), (u1, 0), (u1, 1), (u0, 1), mid)
    # frames at the mouths
    for i in range(N):
        a, b = tubes[(i - 1) % N], tubes[i]
        if a == b: continue
        R = tube_radius(hw[i])
        inner, c = ring(i, R); outer, _ = ring(i, R + 110)
        n = (-tan[i, 0], -tan[i, 1], 0) if b else (tan[i, 0], tan[i, 1], 0)
        for k in range(K):
            k2 = (k + 1) % K
            tris += s2.quad_n('frame', inner[k], inner[k2], outer[k2], outer[k], (0, 0), (1, 0), (1, 1), (0, 1), n)
            tris += s2.quad_n('frame', inner[k], inner[k2], outer[k2], outer[k], (0, 0), (1, 0), (1, 1), (0, 1), (-n[0], -n[1], -n[2]))
    return tris

def billboards(track, S, G, road, tubes, mats, curv):
    """slogan boards on poles beside the straights, angled towards the oncoming cars"""
    pos, hw, tan, N = S['pos'], S['hw'], S['tan'], S['N']
    nrm = G.nrm
    slogans = track.get('slogans', [])
    tris = []
    straight = circ_smooth(np.abs(curv), 8) < 0.00012
    cands = [i for i in range(N) if straight[i] and road[i] and not tubes[i] and 40 < i < N - 20]
    chosen = []
    for k in range(len(slogans)):
        want = int((k + 0.35) * N / len(slogans))
        cs = sorted(cands, key=lambda i: min(abs(i - want), N - abs(i - want)))
        for i in cs:
            if all(min(abs(i - j), N - abs(i - j)) > N // (len(slogans) + 2) for j in chosen):
                chosen.append(i); break
    pts_all = pos[:, :2]
    for k, i in enumerate(chosen):
        for side in (1, -1):
            off = hw[i] + 520
            c = G.at(i, side * off)
            dd = np.hypot(pts_all[:, 0] - c[0], pts_all[:, 1] - c[1]) - hw
            if ((np.abs(pos[:, 2] - c[2]) < 1200) & (dd < 700)).any(): continue
            # board 1600 x 200, facing back down the track, turned 25 degrees towards the road
            face = np.array([-tan[i, 0], -tan[i, 1]])
            toward = np.array([-nrm[i, 0], -nrm[i, 1]]) * side
            f = face * math.cos(math.radians(25)) + toward * math.sin(math.radians(25))
            right = np.array([f[1], -f[0]])        # the reader's right
            W, H, z0 = 1600, 200, 260
            p0 = (c[0] - right[0] * W / 2, c[1] - right[1] * W / 2, c[2] + z0)
            p1 = (c[0] + right[0] * W / 2, c[1] + right[1] * W / 2, c[2] + z0)
            mat = 'bill%d' % k
            fn = (f[0], f[1], 0.0)
            tris += s2.quad_n(mat, p0, p1, Z(p1, H), Z(p0, H), (0, 0), (1, 0), (1, 1), (0, 1), fn)
            back = (p0[0] - f[0] * 8, p0[1] - f[1] * 8, p0[2]); back1 = (p1[0] - f[0] * 8, p1[1] - f[1] * 8, p1[2])
            tris += s2.quad_n('back', back, back1, Z(back1, H), Z(back, H), (0, 0), (1, 0), (1, 1), (0, 1), (-f[0], -f[1], 0))
            for q in (p0, p1):
                qq = (q[0] * 0.8 + c[0] * 0.2, q[1] * 0.8 + c[1] * 0.2)
                tris += s2.box_tris('post', qq[0] - 14, qq[1] - 14, c[2] - SKIRT - 400, qq[0] + 14, qq[1] + 14, c[2] + z0, uscale=1 / 256.0)
            break
    return tris

def scenery(track, S, th, flyR=None):
    """the world around the road: a grid floor plus the theme's things (towers, rocks, crystals, rings, clouds)"""
    pos, hw, N = S['pos'], S['hw'], S['N']
    rng = np.random.RandomState(1000 + sum(map(ord, track['id'])))
    tris = []
    kind = track['scenery']
    zmin, zmax = pos[:, 2].min(), pos[:, 2].max()
    floor = zmin - FLOOR_DROP
    E = HALF - 120
    if kind != 'clouds':
        tris += s2.quad_n('floor', (-E, -E, floor), (E, -E, floor), (E, E, floor), (-E, E, floor),
                          (0, 0), (2 * E / 1024, 0), (2 * E / 1024, 2 * E / 1024), (0, 2 * E / 1024), (0, 0, 1))
    pts2 = pos[:, :2]
    # how far the track reaches sideways from its centreline: the road, or a flight corridor (plus its gate rings)
    reach = hw if flyR is None else np.maximum(hw, flyR + 40)
    def clearance(x, y):
        """distance from (x, y) to the track's edge, and the lowest track height near there (where the track passes
        over itself, or a flight dives, the deck under the point is what a building must stay below)"""
        d = np.hypot(pts2[:, 0] - x, pts2[:, 1] - y) - reach
        k = int(d.argmin())
        near = d < d[k] + 600
        zl = float(pos[near, 2].min())
        if flyR is not None and flyR[near].max() > 0: zl = min(zl, float((pos[near, 2] - flyR[near] - 80).min()))
        return float(d[k]), zl
    def near_track(x, y, z, r_xy, r_z):
        """is (x, y, z) within r_xy sideways and r_z up / down of any part of the track"""
        d = np.hypot(pts2[:, 0] - x, pts2[:, 1] - y) - reach
        return bool(((d < r_xy) & (np.abs(pos[:, 2] - z) < r_z + (0 if flyR is None else flyR))).any())
    count = 0
    if kind in ('city', 'rings', 'ruins'):
        step = 620 if kind in ('city', 'ruins') else 900
        for gx in np.arange(-E + 300, E - 300, step):
            for gy in np.arange(-E + 300, E - 300, step):
                x = gx + rng.uniform(-150, 150); y = gy + rng.uniform(-150, 150)
                w = rng.uniform(160, 420); dpt = rng.uniform(160, 420)
                d, rz = clearance(x, y)
                d -= max(w, dpt) * 0.75
                if d < 60: top_max = rz - 420
                elif d < 500: top_max = rz - 200
                else: top_max = zmax + rng.uniform(300, 1700)
                h_min = floor + 300
                if top_max < h_min: continue
                top = rng.uniform(h_min, top_max) if d > 500 and rng.rand() < 0.6 else rng.uniform(h_min, max(h_min + 1, min(top_max, rz - 150)))
                tris += s2.box_faces(dict(top='roof', x='win', y='win2'), x - w / 2, y - dpt / 2, floor, x + w / 2, y + dpt / 2, top)
                if rng.rand() < 0.25:     # an antenna with a light
                    tris += s2.box_tris('post', x - 8, y - 8, top, x + 8, y + 8, top + 180, uscale=1 / 256.0)
                    tris += s2.box_tris('beacon', x - 22, y - 22, top + 180, x + 22, y + 22, top + 224)
                count += 1
    if kind in ('asteroids', 'rings', 'crystals', 'clouds', 'rocks', 'kelp'):
        n_rocks = {'asteroids': 260, 'rings': 80, 'crystals': 0, 'clouds': 0, 'rocks': 150, 'kelp': 50}[kind]
        tries = 0
        while n_rocks > 0 and tries < 4000:
            tries += 1
            x, y = rng.uniform(-E + 400, E - 400, 2)
            z = rng.uniform(zmin - 1300, zmax + 1600)
            rad = 40 + 600 * rng.rand() ** 3
            if near_track(x, y, z, rad + 350, rad + 700): continue
            v, f = icosphere(rad, rng, squash=(1, rng.uniform(0.6, 1), rng.uniform(0.5, 0.9)))
            tris += shaded_mesh(v, f, (x, y, z), rot_matrix(rng), ('rock0', 'rock1', 'rock2'))
            n_rocks -= 1; count += 1
    if kind in ('crystals', 'coral', 'rocks'):
        tries = 0; n = {'crystals': 160, 'coral': 190, 'rocks': 110}[kind]
        while n > 0 and tries < 4000:
            tries += 1
            x, y = rng.uniform(-E + 300, E - 300, 2)
            d, rz = clearance(x, y)
            h = rng.uniform(400, 2600)
            rad = rng.uniform(90, 320)
            top = floor + h
            if d < rad + 250 and top > rz - 300: continue
            # a six-sided spike: base on the floor, point at the top, slightly tilted
            tilt = rng.uniform(-0.25, 0.25, 2)
            ring = [(x + rad * math.cos(a), y + rad * math.sin(a), floor + h * 0.15) for a in np.arange(6) * math.pi / 3 + rng.rand()]
            tipp = (x + tilt[0] * h, y + tilt[1] * h, top)
            if any(near_track(x + tilt[0] * h * f, y + tilt[1] * h * f, floor + h * f, rad * (1 - f) + 200, 300) for f in (0.4, 0.6, 0.8, 1.0)): continue
            basep = (x, y, floor)
            v = np.array([tipp, basep] + ring) - np.array([x, y, floor])
            faces = [(0, 2 + k, 2 + (k + 1) % 6) for k in range(6)] + [(1, 2 + (k + 1) % 6, 2 + k) for k in range(6)]
            tris += shaded_mesh(v, faces, (x, y, floor), np.eye(3), ('rock0', 'rock1', 'rock2'))
            n -= 1; count += 1
        # floating shards around the track (Space Racer's crystal worlds only)
        for _ in range(90 if kind == 'crystals' else 0):
            x, y = rng.uniform(-E + 400, E - 400, 2)
            z = rng.uniform(zmin, zmax + 1500)
            if near_track(x, y, z, 500, 800): continue
            r_ = rng.uniform(60, 200)
            v = np.array([(0, 0, r_ * 2.2), (0, 0, -r_ * 2.2)] + [(r_ * math.cos(a), r_ * math.sin(a), 0) for a in np.arange(6) * math.pi / 3])
            faces = [(0, 2 + k, 2 + (k + 1) % 6) for k in range(6)] + [(1, 2 + (k + 1) % 6, 2 + k) for k in range(6)]
            tris += shaded_mesh(v, faces, (x, y, z), rot_matrix(rng, 0.3), ('rock0', 'rock1', 'rock2'))
    if kind == 'rings':
        made = 0
        for _ in range(400):
            if made >= 7: break
            R = rng.uniform(900, 2200); thick = rng.uniform(70, 140)
            x, y = rng.uniform(-E + R, E - R, 2)
            z = rng.uniform(zmax + 300, zmax + 2200)
            d, rz = clearance(x, y)
            if d < R + 400: continue
            rot = rot_matrix(rng, 0.25)
            tris += torus_tris(R, thick, rot, (x, y, z))
            made += 1; count += 1
    if kind == 'clouds':
        for _ in range(170):
            x, y = rng.uniform(-E + 500, E - 500, 2)
            z = rng.uniform(zmin - 1500, zmin - 300) if rng.rand() < 0.8 else rng.uniform(zmax + 900, zmax + 2200)
            d, rz = clearance(x, y)
            if d < 700 and abs(z - rz) < 600: continue
            for _k in range(rng.randint(3, 7)):
                cx, cy = x + rng.uniform(-500, 500), y + rng.uniform(-300, 300)
                w, dp, h = rng.uniform(300, 900), rng.uniform(200, 600), rng.uniform(60, 160)
                cz = z + rng.uniform(-40, 80)
                tris += s2.box_faces(dict(top='cloud', bottom='cloud2', x='cloud2', y='cloud2'), cx - w / 2, cy - dp / 2, cz, cx + w / 2, cy + dp / 2, cz + h)
            count += 1
    if kind in ('kelp', 'coral', 'ruins', 'rocks'):
        # Depth Racer: kelp stalks swaying up from the sea floor, thick in a kelp forest
        n = {'kelp': 260, 'coral': 90, 'ruins': 110, 'rocks': 70}[kind]
        tries = 0
        while n > 0 and tries < 6000:
            tries += 1
            x, y = rng.uniform(-E + 200, E - 200, 2)
            h = rng.uniform(900, 2600 if kind == 'kelp' else 1800)
            wdt = rng.uniform(26, 48); segs = 10; ph = rng.rand() * 6.28; amp = rng.uniform(40, 120)
            path = [(x + amp * math.sin(ph + k * 0.6), y + amp * 0.6 * math.cos(ph + k * 0.5), floor + h * k / segs) for k in range(segs + 1)]
            if any(near_track(px, py, pz, wdt + 160, 260) for px, py, pz in path): continue
            for (x0, y0, z0), (x1, y1, z1) in zip(path, path[1:]):
                for ax in ((1, 0), (0, 1)):     # two crossed blades: kelp seen from any side
                    a0 = (x0 - ax[0] * wdt, y0 - ax[1] * wdt, z0); b0 = (x0 + ax[0] * wdt, y0 + ax[1] * wdt, z0)
                    a1 = (x1 - ax[0] * wdt, y1 - ax[1] * wdt, z1); b1 = (x1 + ax[0] * wdt, y1 + ax[1] * wdt, z1)
                    v0, v1 = (z0 - floor) / h * 4, (z1 - floor) / h * 4
                    tris += s2.quad_n('kelp', a0, b0, b1, a1, (0, v0), (1, v0), (1, v1), (0, v1), (-ax[1], ax[0], 0))
            n -= 1; count += 1
    return tris, count, floor

def torus_tris(R, r, rot, c, seg=28, side=4):
    tris = []
    def P(a, b):
        p = np.array([(R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)])
        return tuple(rot @ p + np.array(c))
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        for k in range(side):
            b0, b1 = 2 * math.pi * k / side + math.pi / 4, 2 * math.pi * (k + 1) / side + math.pi / 4
            bm, am = (b0 + b1) / 2, (a0 + a1) / 2
            n = rot @ np.array([math.cos(bm) * math.cos(am), math.cos(bm) * math.sin(am), math.sin(bm)])
            mat = 'beacon' if k == 0 and i % 2 == 0 else ('rock0' if n @ LIGHT > 0.3 else 'rock1' if n @ LIGHT > -0.2 else 'rock2')
            tris += s2.quad_n(mat, P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1), (0, 0), (1, 0), (1, 1), (0, 1), tuple(n))
    return tris

def ring_tris(mat, c, tan, R, r, seg=24, side=4):
    """a ring standing across the track (its axis along the track direction tan), centre c"""
    t = np.array([tan[0], tan[1], 0.0]); t /= np.linalg.norm(t)
    a = np.array([-t[1], t[0], 0.0]); b = np.array([0.0, 0.0, 1.0])
    rot = np.stack([a, b, t], 1)                    # torus local x, y in the ring's plane, z along the track
    tris = []
    def P(u, v):
        p = np.array([(R + r * math.cos(v)) * math.cos(u), (R + r * math.cos(v)) * math.sin(u), r * math.sin(v)])
        return tuple(rot @ p + np.array(c))
    for i in range(seg):
        u0, u1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        for k in range(side):
            v0, v1 = 2 * math.pi * k / side + math.pi / 4, 2 * math.pi * (k + 1) / side + math.pi / 4
            um, vm = (u0 + u1) / 2, (v0 + v1) / 2
            n = rot @ np.array([math.cos(vm) * math.cos(um), math.cos(vm) * math.sin(um), math.sin(vm)])
            tris += s2.quad_n(mat, P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1), (i / seg * 4, 0), ((i + 1) / seg * 4, 0), ((i + 1) / seg * 4, 1), (i / seg * 4, 1), tuple(n))
    return tris

def flight_tris(S, fly, flyR, feats):
    """flight sections: a gate frame every few samples marks the corridor (its edge is the wall), plus the rings"""
    pos, tan, N = S['pos'], S['tan'], S['N']
    tris = []
    k = 0
    for i in range(N):
        if not fly[i]: k = 0; continue
        if k % 7 == 0: tris += ring_tris('gate', pos[i], tan[i], flyR[i], 12, seg=24)
        k += 1
    for f in feats:
        if f['kind'] not in ('ring', 'cring'): continue
        i = f['a']; n = (-tan[i][1], tan[i][0])
        c = (pos[i][0] + n[0] * f['rd'], pos[i][1] + n[1] * f['rd'], pos[i][2] + f['rz'])
        tris += ring_tris(f['kind'], c, tan[i], f['rr'], 12, seg=18)
    return tris

# ---------------------------------------------------------------- banking and tubes
def banking(track, S, curv, zero):
    """bank angle per sample from the smoothed curvature; forced flat where zero[i] (start, crossings, jumps, tubes)"""
    N = S['N']
    k = circ_smooth(curv, 6)
    deg = np.clip(k * 30000, -track['bank'], track['bank'])
    deg[zero] = 0
    deg = circ_smooth(deg, 5)
    deg[zero] *= 0.3
    deg = circ_smooth(deg, 3)
    return np.tan(np.radians(deg)), deg

def tube_clear(S, tubes, G):
    """drop tube samples whose roof would hit another part of the track"""
    pos, hw, N = S['pos'], S['hw'], S['N']
    idx = np.arange(N)
    out = tubes.copy()
    for i in np.where(tubes)[0]:
        R = tube_radius(hw[i])
        top = pos[i, 2] + TUBE_UP + R + 40
        d = np.hypot(pos[:, 0] - pos[i, 0], pos[:, 1] - pos[i, 1])
        far = np.minimum(np.abs(idx - i), N - np.abs(idx - i)) > 60
        hit = far & (d < R + hw + 40) & (pos[:, 2] - SKIRT - 40 < top) & (pos[:, 2] + 300 > pos[i, 2] - R)
        if hit.any(): out[i] = False
    return out

# ---------------------------------------------------------------- minimap and preview
def minimap(track, S, path, size=192):
    """pixelated: drawn at a quarter size, upscaled 4x"""
    pos, hw = S['pos'], S['hw']
    ext = max(np.abs(pos[:, :2]).max() + hw.max(), 1)
    small = size // 4
    sc = (small / 2 - 2) / ext
    img = Image.new('RGBA', (small, small), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    th = THEMES[track['theme']]
    pts = [(small / 2 + x * sc, small / 2 - y * sc) for x, y in pos[:, :2]]
    dr.line(pts + pts[:1], fill=tuple(BLACK) + (255,), width=4)
    dr.line(pts + pts[:1], fill=tuple(th['rail']) + (255,), width=2)
    x0, y0 = pts[0]
    dr.rectangle([int(x0) - 1, int(y0) - 1, int(x0) + 1, int(y0) + 1], fill=tuple(WHITE) + (255,))
    a = np.array(img)
    a[..., 3] = np.where(a[..., 3] > 100, 255, 0)
    Image.fromarray(up(a, 4)).save(path)
    return dict(scale=sc * 4, size=size)

def preview_draw(dr, S, feats, gapset, cps, tubes, ox, oy, sc, th, title, road, bankdeg, fly=None):
    pos, hw, tan, N = S['pos'], S['hw'], S['tan'], S['N']
    nrm = np.stack([-tan[:, 1], tan[:, 0]], 1)
    def P(x, y): return (ox + x * sc, oy - y * sc)
    zr = max(1, pos[:, 2].max() - pos[:, 2].min())
    order = np.argsort(pos[:, 2])
    for i in order:
        j = (i + 1) % N
        if not road[i]: continue
        l0 = pos[i, :2] + nrm[i] * hw[i]; r0 = pos[i, :2] - nrm[i] * hw[i]
        l1 = pos[j, :2] + nrm[j] * hw[j]; r1 = pos[j, :2] - nrm[j] * hw[j]
        k = 0.7 + 0.6 * (pos[i, 2] - pos[:, 2].min()) / zr
        col = tuple(min(255, int(c * k + 30)) for c in th['road2'])
        if tubes[i]: col = (90, 90, 110)
        dr.polygon([P(*r0), P(*r1), P(*l1), P(*l0)], fill=col)
        if i not in gapset:
            dr.line([P(*l0), P(*l1)], fill=th['rail'], width=2); dr.line([P(*r0), P(*r1)], fill=th['rail'], width=2)
    colors = {'boost': GOLD, 'charge': ICE, 'slick': PINK, 'ramp': HOT}
    if fly is not None:
        for i in np.where(fly)[0]:
            if i % 2 == 0: dr.ellipse([P(*pos[i, :2])[0] - 2, P(*pos[i, :2])[1] - 2, P(*pos[i, :2])[0] + 2, P(*pos[i, :2])[1] + 2], fill=th['gate'])
    for ft in feats:
        i = ft['a']
        if ft['kind'] in ('ring', 'cring'):
            n = nrm[i]; c = P(*(pos[i, :2] + n * ft['rd'])); r = max(3, ft['rr'] * sc)
            dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=GOLD if ft['kind'] == 'ring' else ICE, width=2)
            continue
        for _ in range(N):
            j = (i + 1) % N
            def lat(k, f): return pos[k % N, :2] - nrm[k % N] * hw[k % N] * f
            dr.polygon([P(*lat(i, ft['l1'])), P(*lat(j, ft['l1'])), P(*lat(j, ft['l0'])), P(*lat(i, ft['l0']))], fill=colors[ft['kind']])
            if i % N == ft['b'] % N: break
            i += 1
    for ci in cps:
        l = pos[ci, :2] + nrm[ci] * hw[ci]; r = pos[ci, :2] - nrm[ci] * hw[ci]
        dr.line([P(*l), P(*r)], fill=(255, 255, 255) if ci == 0 else th['gate'], width=3 if ci == 0 else 2)
    i = 8
    dr.line([P(*pos[i, :2]), P(*(pos[i, :2] + tan[i] * 500))], fill=(255, 255, 255), width=3)
    for f in np.arange(0.1, 1.0, 0.1):
        i = int(f * N)
        dr.text(P(*(pos[i, :2] + nrm[i] * (hw[i] + 250))), '%.1f' % f, fill=(160, 160, 170))
    dr.text((ox - 330, oy - 345), title, fill=(255, 255, 255))

# ---------------------------------------------------------------- main
def build_track(ti, track):
    """samples + derived arrays for one track (no files written)"""
    S = sample(track)
    problems, crossings, unders = validate(track, S)
    N = S['N']
    def frac_idx(f): return int(round(f * N)) % N
    feats = [dict(kind=k, a=frac_idx(a), b=frac_idx(b), l0=l0, l1=l1) for k, a, b, l0, l1 in track['feats']]
    gaps_idx = [(frac_idx(a), frac_idx(b)) for a, b in track['gaps']]
    road = np.ones(N, np.int8)
    lift = np.zeros(N)
    zero = np.zeros(N, bool)
    for lip, rn, vn, rh in track.get('jumps', []):
        e = frac_idx(lip)                       # lip at sample e; ramp segments e-rn .. e-1; open e .. e+vn-1
        feats.append(dict(kind='ramp', a=(e - rn) % N, b=(e - 1) % N, l0=-1.0, l1=1.0, h=rh))
        for k in range(rn + 1): lift[(e - rn + k) % N] = rh * k / rn
        for k in range(vn): road[(e + k) % N] = 0
        for k in range(-rn - 10, vn + 10): zero[(e + k) % N] = True
    for k in range(-36, 8): zero[k % N] = True               # the grid and the start line
    for i, j in crossings:
        for k in range(-10, 11): zero[(i + k) % N] = True; zero[(j + k) % N] = True
    tubes = np.zeros(N, bool)
    for a, b in track.get('tunnels', []):
        for i in ranges_to_set([(frac_idx(a), frac_idx(b))], N): tubes[i] = True
    if track.get('undertube'):
        for i in unders:
            for k in range(-8, 9): tubes[(i + k) % N] = True
    for i in np.where(tubes)[0]:
        for k in range(-6, 7): zero[(i + k) % N] = True
    # flight sections: no road, a round corridor (radius tapering to the road at the end, so cars come down onto it)
    fly = np.zeros(N, np.int8); flyR = np.zeros(N)
    for a, b, R in track.get('flights', []):
        ia, ib = frac_idx(a), frac_idx(b)
        run = []; i = ia
        while True:
            run.append(i % N)
            if i % N == ib: break
            i += 1
        for k, i in enumerate(run):
            fly[i] = 1; road[i] = 0
            t = min(1.0, (len(run) - 1 - k) / 14.0)
            flyR[i] = 110 + (R - 110) * (t * t * (3 - 2 * t))
        for k in range(-12, len(run) + 12): zero[(ia + k) % N] = True
    creatures = []
    for kind, frac, h, period, phase, speed, span in track.get('creatures', []):
        creatures.append(dict(kind=kind, i=frac_idx(frac), h=float(h), period=float(period), phase=float(phase), speed=float(speed), span=float(span)))
    for frac, lat, dz, rr, kind in track.get('rings', []):
        i = frac_idx(frac)
        assert fly[i], 'ring outside a flight section: %s %.3f' % (track['id'], frac)
        feats.append(dict(kind=kind, a=i, b=(i + 1) % N, l0=-1.0, l1=1.0, rd=round(-lat * float(flyR[i]), 1), rz=float(dz), rr=float(rr)))
    curv = curvature(S)
    tb, bankdeg = banking(track, S, curv, zero)
    tb[fly == 1] = 0; bankdeg[fly == 1] = 0
    G = Geo(S, lift, tb)
    tubes = tube_clear(S, tubes, G)
    gapset = ranges_to_set(gaps_idx, N)
    cps = []
    for k in range(CHECKPOINTS):
        c = int(round(k * N / CHECKPOINTS)) % N
        c0 = c
        while not road[c] or not road[(c - 1) % N] or (k and tubes[c]): c = (c + 1) % N
        if k and (c - c0) % N > 40:                          # pushed past a long flight: the last road before it instead
            c = c0
            while not road[c] or not road[(c - 1) % N] or tubes[c]: c = (c - 1) % N
        if k and (c <= cps[-1] + 20 or c >= N - 20): continue  # nothing left between: one checkpoint fewer
        cps.append(c)
    rail = np.ones(N, np.int8)
    for i in gapset: rail[i] = 0
    rail[road == 0] = 0
    return dict(S=S, problems=problems, crossings=crossings, feats=feats, gaps_idx=gaps_idx, gapset=gapset, road=road, lift=lift,
                tubes=tubes, tb=tb, bankdeg=bankdeg, curv=curv, G=G, cps=cps, rail=rail, fly=fly, flyR=flyR, creatures=creatures)

def main():
    os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
    mmdir = os.path.join(OUT, 'panorama/images/custom_game/spr'); os.makedirs(mmdir, exist_ok=True)
    shared_materials()
    runtime = []
    props = []
    prev = Image.new('RGB', (4 * 700, 2 * 700), (12, 12, 18)) if PREVIEW else None
    dr = ImageDraw.Draw(prev) if prev else None
    ok = True
    for ti, track in enumerate(TRACKS):
        B = build_track(ti, track)
        S, N, L = B['S'], B['S']['N'], B['S']['L']
        for p in B['problems']: print('  %s: %s' % (track['id'], p)); ok = False
        th = THEMES[track['theme']]
        mats = build_materials(track)
        tris = track_tris(track, S, B['G'], B['feats'], B['gapset'], B['cps'], B['road'], B['tubes'], mats, th)
        if B['fly'].any(): tris += flight_tris(S, B['fly'], B['flyR'], B['feats'])
        ntrack = len(tris)
        tris += billboards(track, S, B['G'], B['road'], B['tubes'], mats, B['curv'])
        st, nscen, floor = scenery(track, S, th, B['flyR'])
        tris += st
        allmats = dict(mats); allmats.update(SHARED)
        used = set(t[0] for t in tris)
        model = s2.write_model(OUT, 'models/spr/track', track['id'], tris, {k: v for k, v in allmats.items() if k in used})
        mm = minimap(track, S, os.path.join(mmdir, 'mm_%s.png' % track['id']))
        pos, hw, tan = S['pos'], S['hw'], S['tan']
        runtime.append(dict(
            id=track['id'], title=track['title'], laps=track['laps'], theme=track['theme'], index=ti,
            n=N, length=round(L, 1), step=round(S['step'], 4),
            x=[round(float(v), 1) for v in pos[:, 0]], y=[round(float(v), 1) for v in pos[:, 1]], z=[round(float(v), 1) for v in pos[:, 2]],
            tx=[round(float(v), 4) for v in tan[:, 0]], ty=[round(float(v), 4) for v in tan[:, 1]],
            hw=[round(float(v), 1) for v in hw], rail=[int(v) for v in B['rail']], road=[int(v) for v in B['road']],
            bk=[round(float(v), 4) for v in B['tb']], tube=[int(v) for v in B['tubes']],
            **(dict(fly=[int(v) for v in B['fly']], flyR=[round(float(v), 1) for v in B['flyR']]) if B['fly'].any() else {}),
            **(dict(creatures=B['creatures']) if B['creatures'] else {}),
            cp=B['cps'], feats=B['feats'], crossing=bool(track.get('crossing')),
            mm=dict(scale=round(mm['scale'], 5), size=mm['size']),
            ext=round(float(np.abs(pos[:, :2]).max() + hw.max()), 1),
            zmin=round(float(pos[:, 2].min()), 1), zmax=round(float(pos[:, 2].max()), 1),
            off=box_origin(ti),
        ))
        props.append(dict(id=track['id'], model=model, index=ti, off=box_origin(ti), ext=runtime[-1]['ext'], zmin=runtime[-1]['zmin'],
                          zmax=runtime[-1]['zmax'], title=track['title'], theme=track['theme'], half=HALF, floor=round(float(floor), 1)))
        print('%-10s %4d samples, lap %6.0f x%d, hw %3.0f-%3.0f, z %5.0f-%5.0f, bank max %4.1f, tube %3d, feats %2d, crossings %d, scenery %3d, tris %6d (track %d)' % (
            track['id'], N, L, track['laps'], hw.min(), hw.max(), pos[:, 2].min(), pos[:, 2].max(), np.abs(B['bankdeg']).max(), B['tubes'].sum(),
            len(B['feats']), len(B['crossings']), nscen, len(tris), ntrack))
        if dr:
            ox = 350 + (ti % 4) * 700; oy = 350 + (ti // 4) * 700
            preview_draw(dr, S, B['feats'], B['gapset'], B['cps'], B['tubes'], ox, oy, 330 / HALF, th, track['title'] + '  lap %.0f' % L, B['road'], B['bankdeg'], B['fly'])
    json.dump(runtime, open(os.path.join(OUT, '_gen/tracks.json'), 'w'), separators=(',', ':'))
    json.dump(props, open(os.path.join(OUT, '_gen/track_props.json'), 'w'))
    if prev: prev.save(PREVIEW)
    if not ok: sys.exit('track problems found')

if __name__ == '__main__':
    main()
