"""IRONFRAME frame auras: a signature visual effect around every player frame that shows its trait (docs/FEATURES.md "Frame auras").

usage: python -I tools/auras.py [--only lisa,ogre] [--no-compile] [--no-preview] [--preview-only] [--jobs N]

Reads data/parts.json#auras (one block per frame part key: style, colours, parts, states, flares; the runtime behaviour is
src/cs2/47_auras.js) and the converted frame meshes (out/addon/models/ifr/frames/<model>, posed idle/hover, low LOD), and writes
  models/ifr/aura/<frame>/<part>_<state>.vmdl + .smd   one small additive model per part state, built in the frame's own model
                                                        frame (origin under the feet, x forward), so the script parents it to the
                                                        frame's upper (or legs) prop with no offset
  materials/ifr/aura/<frame>_<mat>.vmat + _color.png    csgo_unlitgeneric F_BLEND_MODE 4 (additive), backfaces, a 16-cell flipbook
                                                        strip (F_TEXTURE_ANIMATION) painted here: the idle motion costs no script work
  particles/ifr/aura/aura_<frame>.vpcf                  the flare burst (tools/particles.py building blocks)
  out/addon/_gen/auras.json                             {frames: {<frame>: {parts: {<part>: {attach, states: {<state>: vmdl}}}}},
                                                         pools: {aura_<frame>: {count, effect}}}  (build.json AURAS)
  preview/auras/sheet.png, <frame>_idle.gif, <frame>_flare.gif, README.md  offline renders (tools/mech_render.py lighting)
A new frame gets an aura by adding a parts.json#auras entry (copy a block, pick a style and colours) and re-running this.
Styles: streamers static_field blade_wings second_wind nanite_swarm plasma_plumes beam_aegis forge_plating gilded_rings bastion
crimson_hunger hazard_rig phase_echo psycho_frame iron_sigil radar_scope slipstream aegis_pulse siege_anchors.
Geometry rules (checked in the preview): nothing above height + 10 over the head (the IFF diamond floats at height + 70), and the
pilot's own crosshair corridor (from the follow camera, cam_back / cam_up of the class) stays clear in the idle states.
"""
import json, math, os, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create')
sys.path.insert(0, HERE); sys.path.insert(0, CREATE)
os.environ.setdefault('CS2_MODEL_PREFIX', 'ifr')
import modelio                                   # noqa: E402
import mech_render as MR                         # noqa: E402
import review_frames as RF                       # noqa: E402
import particles as PT                           # noqa: E402

OUT = os.path.join(PROJ, 'out', 'addon')
REL_M, REL_T, REL_P = 'models/ifr/aura', 'materials/ifr/aura', 'particles/ifr/aura'
PREV = os.path.join(PROJ, 'preview', 'auras')
NF = 16                                          # flipbook cells per material
PARTS = json.load(open(os.path.join(PROJ, 'data', 'parts.json'), encoding='utf-8'))
FRAMES = {p['key']: p for p in PARTS['parts'] if p.get('kind') == 'frame'}
CLASSES = PARTS['classes']


# =============================================================================================== textures (intensity -> colour)
def cellgrid(w, h):
    return np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)


def wrapd(a):                                     # signed distance on a 0..1 loop
    return (a + 0.5) % 1.0 - 0.5


def seg_glow(acc, pts, core, halo, amp=1.0, wrap_w=0):
    """adds a glowing polyline (pixel coordinates) into acc (h, w): exp core + softer halo"""
    h, w = acc.shape
    shifts = (0, -wrap_w, wrap_w) if wrap_w else (0,)
    R = halo * 3.0
    for dx in shifts:
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            ax2, bx2 = ax + dx, bx + dx
            x0 = int(max(0, min(ax2, bx2) - R)); x1 = int(min(w, max(ax2, bx2) + R + 1)); y0 = int(max(0, min(ay, by) - R)); y1 = int(min(h, max(ay, by) + R + 1))
            if x1 <= x0 or y1 <= y0: continue
            X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            vx, vy = bx2 - ax2, by - ay; L2 = vx * vx + vy * vy + 1e-9
            t = np.clip(((X - ax2) * vx + (Y - ay) * vy) / L2, 0, 1)
            d = np.hypot(X - ax2 - t * vx, Y - ay - t * vy)
            sub = acc[y0:y1, x0:x1]
            np.maximum(sub, amp * (np.exp(-(d / core) ** 2) + 0.35 * np.exp(-(d / halo) ** 2)), out=sub)


def periodic_noise(h, w, scale, rs):
    """tileable smooth noise 0..1 (low-passed white noise in the frequency domain)"""
    n = rs.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * h; fx = np.fft.fftfreq(w)[None, :] * w
    F = np.fft.fft2(n) * np.exp(-(fx ** 2 + fy ** 2) / (2 * scale ** 2))
    r = np.real(np.fft.ifft2(F)); r -= r.min(); return r / (r.max() + 1e-9)


def tex_flow(w, h, rs, pulses=3, width=0.3, edge=0.0, taper=0.8, fil=0.6, base=0.35, speed=1):
    """energy streaming along u (ribbons, tendrils, beams): soft body across v, a hot filament, pulses root -> tip"""
    U, V = cellgrid(w, h); out = []
    nz = periodic_noise(h, w, 3.0, rs)
    for f in range(NF):
        prof = np.exp(-((V - 0.5) / width) ** 2)
        I = base * prof + fil * np.exp(-((V - 0.5) / 0.07) ** 2)
        if edge: I += edge * (np.exp(-((V - 0.05) / 0.04) ** 2) + np.exp(-((V - 0.95) / 0.04) ** 2))
        p = sum(np.exp(-(wrapd(U - (j + speed * f / NF) / pulses) / 0.045) ** 2) for j in range(pulses))
        streak = np.roll(nz, int(f * w / NF) * speed, axis=1)
        I = I * (0.5 + 1.1 * p + 0.35 * streak)
        I *= np.clip(1 - U, 0, 1) ** taper * np.clip(U / 0.05, 0, 1)
        out.append(I)
    return np.concatenate(out, 1)


def tex_blade(w, h, rs):
    """an energy blade: hot rim along both edges, faint chevron body, a light sweep root -> tip, glowing tip"""
    U, V = cellgrid(w, h); out = []
    for f in range(NF):
        rim = np.exp(-((V - 0.03) / 0.045) ** 2) + np.exp(-((V - 0.97) / 0.045) ** 2)
        spine = 0.35 * np.exp(-((V - 0.5) / 0.03) ** 2)
        chev = 0.22 * np.exp(-(wrapd(U * 7 - np.abs(V - 0.5) * 3 - f / NF * 2) / 0.08) ** 2)
        sweep = 1.1 * np.exp(-((U - f / NF * 1.25 + 0.1) / 0.06) ** 2)
        I = (0.12 + rim * 0.9 + spine + chev) * (0.75 + sweep) + 0.5 * np.exp(-((U - 0.97) / 0.05) ** 2)
        I *= np.clip(U / 0.04, 0, 1)
        out.append(I)
    return np.concatenate(out, 1)


def bolt_path(rs, x0, y0, x1, y1, depth=5, rough=0.32):
    pts = [(x0, y0), (x1, y1)]
    for _ in range(depth):
        nxt = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            L = math.hypot(bx - ax, by - ay); nx, ny = -(by - ay) / (L + 1e-9), (bx - ax) / (L + 1e-9)
            o = rs.uniform(-rough, rough) * L
            nxt += [((ax + bx) / 2 + nx * o, (ay + by) / 2 + ny * o), (bx, by)]
        pts = nxt
    return pts


def tex_bolts(w, h, rs, n=4, wrap=True, length=(0.35, 0.8), core=1.1, halo=4.5):
    """lightning crawling over a band: n jagged mostly-vertical bolts with a branch each; a new set every 2 cells"""
    out = []
    for f in range(NF):
        I = np.zeros((h, w))
        if f % 2 == 0: seed_keep = rs.randint(1 << 30)
        r2 = np.random.RandomState(seed_keep)       # the same bolts in both cells of a pair; the second one jitters (crawl)
        for b in range(n):
            x = r2.uniform(0, w); y = r2.uniform(0.05, 0.35) * h; L = r2.uniform(*length) * h
            x1 = x + r2.uniform(-0.25, 0.25) * L
            pts = bolt_path(r2, x, y, x1, min(h - 2, y + L))
            if f % 2: pts = [(px + rs.uniform(-1.5, 1.5), py) for px, py in pts]
            seg_glow(I, pts, core, halo, 1.0, w if wrap else 0)
            k = len(pts) // 2; bx, by = pts[k]
            seg_glow(I, bolt_path(r2, bx, by, bx + r2.uniform(-0.3, 0.3) * L, by + 0.3 * L, 4), core * 0.8, halo * 0.7, 0.6, w if wrap else 0)
        out.append(I * rs.uniform(0.75, 1.1))
    return np.concatenate(out, 1)


def tex_motes(w, h, rs, count=14, size=2.2, trail=7, base=0.06):
    """points orbiting along u (one or two laps per loop, both ways), each with a short fading trail"""
    U, V = cellgrid(w, h); X, Y = U * w, V * h
    ms = [(rs.uniform(0, 1), np.clip(rs.normal(0.5, 0.17), 0.12, 0.88), rs.choice([1, 1, 2, -1]), rs.uniform(0.6, 1.0)) for _ in range(count)]
    out = []
    for f in range(NF):
        I = base * np.exp(-((V - 0.5) / 0.3) ** 2)
        for u0, v0, rev, a in ms:
            for k in range(trail):
                u = (u0 + rev * (f - k * 0.18) / NF) % 1.0
                dx = wrapd((X / w) - u) * w; d2 = dx ** 2 + (Y - v0 * h) ** 2
                s = size * (1 - k / trail * 0.5)
                I = I + a * (1 - k / trail) ** 1.6 * np.exp(-d2 / (s * s))
        out.append(I)
    return np.concatenate(out, 1)


def tex_feathers(w, h, rs, count=6, scale=1.0):
    """light-feathers drifting down the card and swaying, fading in at the top and out at the bottom"""
    U, V = cellgrid(w, h); X, Y = U * w, V * h
    fs = [(rs.uniform(0.15, 0.85), rs.uniform(0, 1), rs.uniform(0.7, 1.0), rs.uniform(0.8, 1.2)) for _ in range(count)]
    out = []
    for f in range(NF):
        I = np.zeros((h, w))
        for u0, p, a, sz in fs:
            v = (p + f / NF) % 1.0
            x = (u0 + 0.06 * math.sin(2 * math.pi * (v * 1.5 + p))) * w; y = v * h
            th = 0.9 + 0.45 * math.sin(2 * math.pi * (v + p))
            c, s = math.cos(th), math.sin(th)
            dx, dy = X - x, Y - y; xr = dx * c + dy * s; yr = -dx * s + dy * c
            A, B = 0.2 * h * sz * scale, 0.075 * h * sz * scale
            r2 = (xr / A) ** 2 + (yr / B) ** 2
            fade = math.sin(math.pi * v) ** 0.8
            barbs = 0.85 + 0.15 * np.cos(xr / A * 14)
            I += a * fade * (np.exp(-r2 * 2.0) * barbs + 0.8 * np.exp(-(yr / 0.9) ** 2) * (np.abs(xr) < A))
        out.append(I)
    return np.concatenate(out, 1)


def tex_ring(w, h, rs, segs=3, rev=1, base=0.3, core_w=0.1, seg_w=0.05, ticks=0, glints=0):
    """a band across v (u runs around the ring): a hot core line, soft falloff, bright segments chasing round"""
    U, V = cellgrid(w, h); out = []
    gl = [(rs.uniform(0, 1), rs.choice([2, 3]), rs.uniform(0.6, 1)) for _ in range(glints)]
    for f in range(NF):
        prof = np.exp(-((V - 0.5) / 0.32) ** 2); core = np.exp(-((V - 0.5) / core_w) ** 2)
        seg = sum(np.exp(-(wrapd(U - (j / segs + rev * f / NF / segs)) / seg_w) ** 2) for j in range(segs))
        I = base * prof + core * (0.45 + 1.1 * seg)
        if ticks: I += 0.35 * core * (np.cos(2 * math.pi * U * ticks) > 0.92)
        for u0, r, a in gl:
            I += a * np.exp(-((wrapd(U - (u0 + r * f / NF)) * w) ** 2 + ((V - 0.5) * h) ** 2) / 6.0) * 1.6
        out.append(I)
    return np.concatenate(out, 1)


def tex_flame(w, h, rs, diamonds=4):
    """a plasma plume along u (nozzle at u 0): white-hot core, shock diamonds, turbulent edges, fading tail"""
    U, V = cellgrid(w, h); out = []
    nz = periodic_noise(h, w, 4.0, rs)
    for f in range(NF):
        wd = 0.36 * (1 - U) ** 0.5 + 0.06
        dv = np.abs(V - 0.5)
        turb = np.roll(nz, int(f * w / NF) * 2, axis=1)
        body = np.exp(-(dv / (wd * (0.8 + 0.4 * turb))) ** 2)
        core = np.exp(-(dv / (wd * 0.28)) ** 2)
        diam = 0.5 + 0.5 * np.cos(2 * math.pi * (U * diamonds - 0.15 * math.sin(2 * math.pi * f / NF)))
        flick = 0.85 + 0.25 * rs.uniform()
        I = (0.55 * body * (0.7 + 0.6 * turb) + 1.25 * core * (0.55 + 0.45 * diam)) * (1 - U) ** 1.1 * flick
        I *= np.clip(U / 0.03, 0.3, 1)
        out.append(I)
    return np.concatenate(out, 1)


def hex_edges(X, Y, s):
    """distance to the nearest hex edge (pointy-top hexes of radius s) at pixel coordinates"""
    q = (math.sqrt(3) / 3 * X - Y / 3) / s; r = (2 / 3 * Y) / s
    x, z = q, r; y = -x - z
    rx, ry, rz = np.round(x), np.round(y), np.round(z)
    dx, dy, dz = np.abs(rx - x), np.abs(ry - y), np.abs(rz - z)
    m1 = (dx > dy) & (dx > dz); rx = np.where(m1, -ry - rz, rx)
    m2 = ~m1 & (dy > dz); ry = np.where(m2, -rx - rz, ry)
    rz = np.where(~m1 & ~m2, -rx - ry, rz)
    cx = s * math.sqrt(3) * (rx + rz / 2); cy = s * 1.5 * rz
    px, py = X - cx, Y - cy
    m = np.maximum(np.abs(px), np.abs(px * 0.5 + py * math.sqrt(3) / 2)); m = np.maximum(m, np.abs(px * 0.5 - py * math.sqrt(3) / 2))
    return s * math.sqrt(3) / 2 - m, (rx * 7 + rz * 13) % 97


def tex_hex(w, h, rs, cells=7, lw=1.2, scan=True, fill=0.25):
    """hex lattice lines, a scan band climbing the cell, random hexes lighting up"""
    U, V = cellgrid(w, h); X, Y = U * w, V * h
    s = w / cells / math.sqrt(3)
    e, cid = hex_edges(X, Y, s)
    lines = np.exp(-(e / lw) ** 2) + 0.3 * np.exp(-(e / (lw * 4)) ** 2)
    out = []
    for f in range(NF):
        band = np.exp(-(wrapd(V - (1 - f / NF)) / 0.09) ** 2) if scan else 0
        lit = ((cid * 31 + f * 7 + rs.randint(97)) % 97 < 7) * fill * np.clip(e / (s * 0.4), 0, 1)
        I = lines * (0.45 + 1.3 * band) + lit + 0.08
        out.append(I)
    return np.concatenate(out, 1)


def tex_seams(w, h, rs, depth=4, fill=0.0):
    """psycho-frame seams: panel lines from a recursive split of the cell, glowing nodes, a pulse climbing through them"""
    U, V = cellgrid(w, h); X, Y = U * w, V * h
    lines = np.zeros((h, w)); nodes = []
    def split(x0, y0, x1, y1, d):
        if d == 0 or (x1 - x0) < 14 or (y1 - y0) < 14: return
        if (x1 - x0) > (y1 - y0) * rs.uniform(0.7, 1.4):
            x = rs.uniform(x0 + 0.3 * (x1 - x0), x0 + 0.7 * (x1 - x0)); seg_glow(lines, [(x, y0), (x, y1)], 1.6, 5.0)
            nodes.append((x, y0)); nodes.append((x, y1)); split(x0, y0, x, y1, d - 1); split(x, y0, x1, y1, d - 1)
        else:
            y = rs.uniform(y0 + 0.3 * (y1 - y0), y0 + 0.7 * (y1 - y0)); seg_glow(lines, [(x0, y), (x1, y)], 1.6, 5.0)
            nodes.append((x0, y)); nodes.append((x1, y)); split(x0, y0, x1, y, d - 1); split(x0, y, x1, y1, d - 1)
    split(0, 0, w, h, depth + 2)
    nd = np.zeros((h, w))
    for x, y in nodes: nd = np.maximum(nd, np.exp(-((X - x) ** 2 + (Y - y) ** 2) / 5.0))
    out = []
    for f in range(NF):
        band = np.exp(-(wrapd(V - (1 - f / NF)) / 0.12) ** 2)
        breathe = 0.8 + 0.2 * math.cos(2 * math.pi * f / NF)
        out.append((lines * (0.6 + 1.1 * band) + nd * 1.0 + fill) * breathe)
    return np.concatenate(out, 1)


def tex_heat(w, h, rs):
    """molten plate: glowing crack veins over a warm body, flowing up, ember speckles"""
    n1 = periodic_noise(h, w, 3.0, rs); n2 = periodic_noise(h, w, 7.0, rs)
    veins = (1 - np.abs(n1 - 0.5) * 2) ** 18 * 1.4 + (1 - np.abs(n2 - 0.5) * 2) ** 24 * 0.8
    out = []
    for f in range(NF):
        sh = int(round(f * h / NF))
        vv = np.roll(veins, -sh, axis=0); nn = np.roll(n2, -sh, axis=0)
        emb = (rs.uniform(size=(h, w)) > 0.997) * rs.uniform(0.6, 1.2)
        out.append(0.03 + 0.06 * nn ** 3 + vv * 1.3 + emb)
    return np.concatenate(out, 1)


def tex_glyph(w, h, rs, glyphs=20, rev=1):
    """a rune band: two border lines and stroked glyphs between them; rolls round (rotation) one glyph per loop"""
    base = np.zeros((h, w))
    seg_glow(base, [(0, 0.16 * h), (w, 0.16 * h)], 0.8, 3.0, 0.9); seg_glow(base, [(0, 0.84 * h), (w, 0.84 * h)], 0.8, 3.0, 0.9)
    gw = w / glyphs
    for g in range(glyphs):
        x0 = g * gw + gw * 0.2; x1 = x0 + gw * 0.6; y0, y1 = 0.3 * h, 0.7 * h
        pts = [(rs.uniform(x0, x1), rs.uniform(y0, y1)) for _ in range(4)]
        seg_glow(base, pts, 0.8, 2.5, 0.85)
        if rs.uniform() < 0.5: seg_glow(base, [(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], 0.7, 2.0, 0.6)
    out = []
    for f in range(NF):
        out.append(np.roll(base, int(round(rev * f * gw / NF)), axis=1) + 0.1)
    return np.concatenate(out, 1)


def tex_sigil(w, h, rs, points=6):
    """a planar disc: concentric circles and a star that turns 1/points of a turn per loop (seamless)"""
    U, V = cellgrid(w, h); X, Y = (U - 0.5) * 2, (V - 0.5) * 2
    R = np.hypot(X, Y); A = np.arctan2(Y, X)
    out = []
    for f in range(NF):
        a = A - 2 * math.pi / points * f / NF
        I = np.exp(-((R - 0.96) / 0.02) ** 2) + 0.7 * np.exp(-((R - 0.82) / 0.015) ** 2) + 0.5 * np.exp(-((R - 0.3) / 0.02) ** 2)
        # star: the polygon edge distance of two interleaved triangles
        for k in range(2):
            ak = a + k * math.pi / 3 * (6 / points)
            sec = 2 * math.pi / 3
            rel = (ak + sec / 2) % sec - sec / 2
            edge = R * np.cos(rel) - 0.8 * 0.5
            I += 0.9 * np.exp(-(edge / 0.02) ** 2) * (R < 0.82)
        I += 0.35 * np.exp(-((wrapd(a / (2 * math.pi) * points) * 2 * math.pi * R) ** 2 + (R - 0.89) ** 2) / 0.002)
        I *= (R < 1.0)
        out.append(I)
    return np.concatenate(out, 1)


def tex_scan(w, h, rs):
    """ghost echo: faint body, scanlines, glitch bands that jump and flicker"""
    U, V = cellgrid(w, h); out = []
    for f in range(NF):
        I = 0.18 + 0.22 * (np.cos(2 * math.pi * V * h / 4) > 0.3)
        for _ in range(2):
            v0 = rs.uniform(0, 1); hh = rs.uniform(0.02, 0.07)
            I = I + 0.7 * (np.abs(wrapd(V - v0)) < hh)
        out.append(I * rs.uniform(0.75, 1.1))
    return np.concatenate(out, 1)


def tex_beacon(w, h, rs, strobe=False):
    """a rotating beacon wedge on a planar disc (one turn per loop) around a hot centre"""
    U, V = cellgrid(w, h); X, Y = (U - 0.5) * 2, (V - 0.5) * 2
    R = np.hypot(X, Y); A = np.arctan2(Y, X)
    out = []
    for f in range(NF):
        da = wrapd((A / (2 * math.pi)) - f / NF) * 2 * math.pi
        wedge = np.exp(-(da / 0.32) ** 2) * np.exp(-R * 1.6) * (R < 1)
        wedge2 = np.exp(-(wrapd((A / (2 * math.pi)) - f / NF - 0.5) * 2 * math.pi / 0.32) ** 2) * np.exp(-R * 1.6) * (R < 1)
        core = np.exp(-(R / 0.16) ** 2)
        k = (1.0 if (f % 4) < 2 else 0.35) if strobe else 1.0
        out.append(1.2 * wedge + 0.8 * wedge2 + 1.3 * core * k)
    return np.concatenate(out, 1)


def tex_dust(w, h, rs, puffs=26, chevrons=24):
    """ground ring (u around, v inner -> outer): a hazard chevron track turning, dust puffs and sparks blown outward"""
    U, V = cellgrid(w, h); X, Y = U * w, V * h
    ps = [(rs.uniform(0, 1), rs.uniform(0, 1), rs.uniform(0.5, 1)) for _ in range(puffs)]
    out = []
    for f in range(NF):
        I = 0.1 * np.exp(-((V - 0.25) / 0.2) ** 2)
        chev = (((U * chevrons + np.abs(V - 0.17) * 3 - f / NF) % 1.0) < 0.5) * (np.abs(V - 0.17) < 0.09)
        I = I + chev * 0.9 + np.exp(-((V - 0.05) / 0.025) ** 2) * 0.8
        for u0, p, a in ps:
            v = (p + f / NF) % 1.0
            dx = wrapd(U - u0) * w; d2 = dx ** 2 + ((V - (0.3 + 0.7 * v)) * h) ** 2
            s = 2 + 6 * v
            I = I + a * (1 - v) ** 1.5 * np.exp(-d2 / (s * s)) * 0.8
        out.append(I)
    return np.concatenate(out, 1)


def tex_crown(w, h, rs, streaks=22):
    """rising light (cylinder band, v 0 top -> 1 bottom): bright foot line, streaks climbing and fading upward"""
    U, V = cellgrid(w, h)
    st = [(rs.uniform(0, 1), rs.uniform(0, 1), rs.uniform(0.5, 1), rs.choice([1, 2])) for _ in range(streaks)]
    out = []
    for f in range(NF):
        I = 0.6 * np.exp(-((V - 0.97) / 0.05) ** 2) + 0.25 * V ** 3
        for u0, p, a, sp in st:
            v = 1 - ((p + sp * f / NF) % 1.0)
            I = I + a * np.exp(-((wrapd(U - u0) * w) / 1.4) ** 2) * np.exp(-((V - v) * h / 10) ** 2) * V ** 0.5
        out.append(I)
    return np.concatenate(out, 1)


def tex_bulb(w, h, rs):
    """a strobing lamp: radial glow, 2 cells on / 2 off"""
    U, V = cellgrid(w, h); R = np.hypot(U - 0.5, V - 0.5) * 2
    return np.concatenate([(1.4 * np.exp(-(R / 0.6) ** 2) + 0.2) * (1.0 if f % 4 < 2 else 0.3) for f in range(NF)], 1)


def tex_radar(w, h, rs, rings=3, blips=6):
    """a radar scope on a planar disc: range rings, a sweep line with a fading trail turning once per loop, blips lit as it passes"""
    U, V = cellgrid(w, h); X, Y = (U - 0.5) * 2, (V - 0.5) * 2
    R = np.hypot(X, Y); A = (np.arctan2(Y, X) / (2 * math.pi)) % 1.0
    bl = [(rs.uniform(0, 1), rs.uniform(0.25, 0.9), rs.uniform(0.6, 1.0)) for _ in range(blips)]
    ringI = sum(np.exp(-((R - (k + 1) / rings * 0.97) / 0.018) ** 2) for k in range(rings)) * 0.45
    ticks = 0.5 * (np.cos(2 * math.pi * A * 36) > 0.85) * (np.abs(R - 0.93) < 0.05)
    cross = 0.18 * (np.exp(-(X / 0.012) ** 2) + np.exp(-(Y / 0.012) ** 2))
    out = []
    for f in range(NF):
        s = f / NF
        behind = (s - A) % 1.0                                     # how far the sweep has gone past this angle
        sweep = 1.3 * np.exp(-(behind * 2 * math.pi * R.clip(0.15) / 0.035) ** 2) + 0.75 * np.exp(-behind / 0.12)
        I = (ringI + ticks + cross + 0.1 + sweep * (0.35 + 0.65 * R)) * (R < 1)
        for a0, r0, amp in bl:
            age = (s - a0) % 1.0
            d2 = ((X - r0 * math.cos(2 * math.pi * a0)) ** 2 + (Y - r0 * math.sin(2 * math.pi * a0)) ** 2) / 0.0012
            I = I + amp * 1.4 * math.exp(-age / 0.25) * np.exp(-d2)
        out.append(I)
    return np.concatenate(out, 1)


def tex_pulse(w, h, rs, segs=6):
    """a shockwave ground ring (u around, v inner -> outer): a hot leading edge, a fading wake inside it, bright arcs chasing round"""
    U, V = cellgrid(w, h); out = []
    for f in range(NF):
        edge = np.exp(-((V - 0.8) / 0.07) ** 2)
        wake = np.exp(-np.clip(0.8 - V, 0, None) / 0.22) * (V < 0.8) * 0.55
        arcs = sum(np.exp(-(wrapd(U - (j / segs + f / NF / segs)) / 0.03) ** 2) for j in range(segs))
        hexd = 0.25 * (np.cos(2 * math.pi * (U * segs * 6)) > 0.7) * np.exp(-((V - 0.55) / 0.08) ** 2)
        out.append(edge * (0.9 + 0.8 * arcs) + wake + hexd)
    return np.concatenate(out, 1)


def tex_stake(w, h, rs, n=5):
    """an energy stake (u root -> tip): hot core line, chevrons streaming toward the tip, a bright tip"""
    U, V = cellgrid(w, h); out = []
    for f in range(NF):
        core = np.exp(-((V - 0.5) / 0.08) ** 2); body = np.exp(-((V - 0.5) / 0.3) ** 2)
        chev = ((U * n - np.abs(V - 0.5) * 1.6 - f / NF) % 1.0 < 0.32) * (np.abs(V - 0.5) < 0.4)
        tip = np.exp(-((U - 0.96) / 0.05) ** 2) * body
        out.append(0.25 * body + 0.9 * core + 0.75 * chev + 1.2 * tip)
    return np.concatenate(out, 1)


TEX = dict(flow=tex_flow, blade=tex_blade, bolts=tex_bolts, motes=tex_motes, feathers=tex_feathers, ring=tex_ring, flame=tex_flame, hex=tex_hex,
           seams=tex_seams, heat=tex_heat, glyph=tex_glyph, sigil=tex_sigil, scan=tex_scan, beacon=tex_beacon, dust=tex_dust, crown=tex_crown, bulb=tex_bulb,
           radar=tex_radar, pulse=tex_pulse, stake=tex_stake)


def colorize(I, col, acc, gain=1.0):
    """intensity -> additive colour: saturated body, a hot (accent) core above 0.85"""
    I = np.clip(I * gain, 0, 2.0)[..., None]
    c = np.array(col, float)[None, None] / 255; a = np.array(acc, float)[None, None] / 255
    rgb = c * np.clip(I, 0, 1.3) ** 1.1 + a * np.clip(I - 0.85, 0, 1) * 0.6
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


# =============================================================================================== frame meshes and anchors
def load_mesh(model, part, clip, lod=4):
    e = MODELS[model]; v = e.get(part)
    if not v: return None
    d = os.path.join(OUT, 'models', 'ifr', 'frames', model)
    m = MR.read_mesh_full(RF.lod_file(d, os.path.basename(v)[:-5], lod))
    fr = None; p = os.path.join(d, 'anims', '%s_%s.smd' % (part, clip))
    if os.path.exists(p):
        _, f = RF.clip_frames(p); fr = f[sorted(f)[0]]
    P, N = MR.posed_vn(m, fr)
    return dict(P=P, N=N, UV=m['UV'], mats=m['mats'])


def anchors(fkey):
    fr = FRAMES[fkey]; model = fr['model']; e = MODELS[model]
    h = float(e['height']); cls = CLASSES[fr['class']]
    U = load_mesh(model, 'upper', 'idle'); L = load_mesh(model, 'legs', 'hover')
    pv = e.get('pivot') or [0.0, 0.0]
    P = U['P']
    band = (P[:, 2] > 0.55 * h) & (P[:, 2] < 0.92 * h)
    core = P[band] if band.sum() > 30 else P
    cx, cy, zc = float(np.median(core[:, 0])), float(np.median(core[:, 1])), float(np.median(core[:, 2]))
    ay = np.abs(core[:, 1] - cy)
    W = float(np.percentile(ay, 95)); tw = float(np.percentile(ay, 55))
    mid = core[ay < tw]
    xb = float(np.percentile(mid[:, 0], 3)); xf = float(np.percentile(mid[:, 0], 97))
    sh = {}
    hi = P[P[:, 2] > 0.68 * h]
    for s, nm in ((1, 'l'), (-1, 'r')):
        q = hi[s * (hi[:, 1] - cy) > 0.45 * W]
        if len(q) < 5: q = hi
        sh[nm] = np.array([float(np.median(q[:, 0])), cy + s * float(np.percentile(np.abs(q[:, 1] - cy), 70)), float(np.percentile(q[:, 2], 92))])
    lg = L['P'] if L is not None else P[P[:, 2] < 0.45 * h]
    low = lg[lg[:, 2] < 0.5 * h]
    leg_r = float(np.percentile(np.hypot(low[:, 0] - pv[0], low[:, 1] - pv[1]), 90)) if len(low) else 0.25 * h
    legs_top = float(np.percentile(lg[:, 2], 97)) if len(lg) else 0.45 * h
    la = np.array(e['hardpoints'].get('la', [cx, cy + W, 0.55 * h]), float)
    if la[1] - cy < 0.3 * W: la = np.array([cx + 0.1 * h, cy + W * 0.9, 0.55 * h])
    hip = max(float(e.get('hip_z') or 0), h * 0.45)
    return dict(key=fkey, model=model, h=h, hip=hip, cam_back=cls.get('cam_back', 520), cam_up=cls.get('cam_up', 180), cx=cx, cy=cy, zc=zc, W=W, tw=tw,
                back=np.array([xb, cy, zc]), front_x=xf, sh=sh, top=float(P[:, 2].max()), feet=np.array([pv[0], pv[1], 0.0]), leg_r=leg_r, legs_top=legs_top,
                boosters=[np.array(b, float) for b in (e.get('boosters') or [[xb, cy - 0.3 * W, zc], [xb, cy + 0.3 * W, zc]])], la=la, U=U, L=L)


# =============================================================================================== geometry (triangles: (P 3x3, UV 3x2, mat))
def nrm(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-12)


def quad(p0, p1, p2, p3, uv, mat):
    return [(np.array([p0, p1, p2]), np.array([uv[0], uv[1], uv[2]]), mat), (np.array([p0, p2, p3]), np.array([uv[0], uv[2], uv[3]]), mat)]


def strip(path, sides, widths, mat, flip_uv=False):
    """a ribbon along path (n,3): sides (n,3) unit vectors, widths (n,); u 0 -> 1 along, v 0 -> 1 across"""
    path = np.asarray(path, float); seg = np.linalg.norm(np.diff(path, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)]); u = s / max(s[-1], 1e-6)
    tris = []
    for i in range(len(path) - 1):
        a0 = path[i] - sides[i] * widths[i] / 2; a1 = path[i] + sides[i] * widths[i] / 2
        b0 = path[i + 1] - sides[i + 1] * widths[i + 1] / 2; b1 = path[i + 1] + sides[i + 1] * widths[i + 1] / 2
        tris += quad(a0, b0, b1, a1, [(u[i], 0), (u[i + 1], 0), (u[i + 1], 1), (u[i], 1)], mat)
    return tris


def path_frames(path, up=(0, 0, 1)):
    path = np.asarray(path, float)
    T = np.gradient(path, axis=0); T = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)
    S = np.cross(T, np.array(up, float)); bad = np.linalg.norm(S, axis=1) < 1e-3
    S[bad] = np.cross(T[bad], [1.0, 0, 0]); S = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-9)
    B = np.cross(S, T)
    return T, S, B


def cross_strip(path, widths, mat, roll=0.0):
    """two ribbons crossed at 90 degrees along the same path (never edge-on)"""
    T, S, B = path_frames(path)
    c, s = math.cos(roll), math.sin(roll)
    S1 = S * c + B * s; S2 = -S * s + B * c
    return strip(path, S1, widths, mat) + strip(path, S2, widths, mat)


def basis(axis):
    a = nrm(axis); t = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = nrm(np.cross(a, t)); e2 = np.cross(a, e1)
    return a, e1, e2


def ring_flat(center, axis, r0, r1, mat, n=48):
    """annulus in the plane normal to axis: u around (0..1 once), v inner (0) -> outer (1)"""
    a, e1, e2 = basis(axis); c = np.asarray(center, float); tris = []
    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d0 = e1 * math.cos(t0) + e2 * math.sin(t0); d1 = e1 * math.cos(t1) + e2 * math.sin(t1)
        tris += quad(c + d0 * r0, c + d1 * r0, c + d1 * r1, c + d0 * r1, [(i / n, 0), ((i + 1) / n, 0), ((i + 1) / n, 1), (i / n, 1)], mat)
    return tris


def cyl_band(center, axis, r_top, r_bot, z0, z1, mat, n=40, u_turns=1):
    """open cylinder about axis through center from z0 (bottom) to z1 (top) along the axis: u around, v 0 top -> 1 bottom"""
    a, e1, e2 = basis(axis); c = np.asarray(center, float); tris = []
    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d0 = e1 * math.cos(t0) + e2 * math.sin(t0); d1 = e1 * math.cos(t1) + e2 * math.sin(t1)
        u0, u1 = i / n * u_turns, (i + 1) / n * u_turns
        u0, u1 = u0 % 1.0, (u1 % 1.0) or 1.0
        tris += quad(c + a * z1 + d0 * r_top, c + a * z1 + d1 * r_top, c + a * z0 + d1 * r_bot, c + a * z0 + d0 * r_bot, [(u0, 0), (u1, 0), (u1, 1), (u0, 1)], mat)
    return tris


def disc(center, axis, r, mat, n=32):
    a, e1, e2 = basis(axis); c = np.asarray(center, float); tris = []
    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = c + (e1 * math.cos(t0) + e2 * math.sin(t0)) * r; p1 = c + (e1 * math.cos(t1) + e2 * math.sin(t1)) * r
        uv = lambda t: (0.5 + 0.5 * math.cos(t), 0.5 - 0.5 * math.sin(t))
        tris.append((np.array([c, p0, p1]), np.array([(0.5, 0.5), uv(t0), uv(t1)]), mat))
    return tris


def card(center, u_dir, v_dir, w, h, mat):
    """a flat quad: u along u_dir (width w), v along -v_dir (image top = +v_dir side)"""
    c = np.asarray(center, float); U = nrm(u_dir) * w / 2; V = nrm(v_dir) * h / 2
    return quad(c - U + V, c + U + V, c + U - V, c - U - V, [(0, 0), (1, 0), (1, 1), (0, 1)], mat)


def patch(center, radius, a0, a1, z0, z1, mat, nu=10, nv=4):
    """a vertical cylinder patch (curved panel) around center from angle a0 to a1 (deg, 0 = +x), z0..z1; planar 0..1 UV"""
    c = np.asarray(center, float); tris = []
    for i in range(nu):
        for j in range(nv):
            def P(ii, jj):
                t = math.radians(a0 + (a1 - a0) * ii / nu); z = z1 + (z0 - z1) * jj / nv
                return np.array([c[0] + radius * math.cos(t), c[1] + radius * math.sin(t), z])
            uv = [(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)]
            tris += quad(P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1), uv, mat)
    return tris


def dome(center, r, mat, n=12):
    c = np.asarray(center, float); tris = []
    rings = [(r * math.cos(t), r * math.sin(t)) for t in np.linspace(0, math.pi / 2, 4)]
    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        for (r0, z0), (r1, z1) in zip(rings[:-1], rings[1:]):
            P = lambda rr, zz, t: c + np.array([rr * math.cos(t), rr * math.sin(t), zz])
            uv = lambda rr, t: (0.5 + 0.5 * rr / r * math.cos(t), 0.5 - 0.5 * rr / r * math.sin(t))
            tris += quad(P(r0, z0, t0), P(r0, z0, t1), P(r1, z1, t1), P(r1, z1, t0), [uv(r0, t0), uv(r0, t1), uv(r1, t1), uv(r1, t0)], mat)
    return tris


def shell(mesh, keep, off, mat, axis_xy, z0, z1, shift=(0, 0, 0)):
    """the frame's own surface (triangle soup) pushed out along its normals; cylindrical UV about axis_xy (seam on the right side)"""
    P = mesh['P'].reshape(-1, 3, 3); N = mesh['N'].reshape(-1, 3, 3)
    C = P.mean(1); k = keep(C, nrm_rows(N.mean(1)))
    P = P[k] + N[k] * off + np.asarray(shift, float); tris = []
    ang = np.arctan2(P[..., 1] - axis_xy[1], P[..., 0] - axis_xy[0])
    u = ((ang + math.pi / 2) / (2 * math.pi)) % 1.0
    v = np.clip((z1 - P[..., 2]) / max(1e-3, z1 - z0), 0, 1)
    for t in range(len(P)):
        uu = u[t].copy()
        if uu.max() - uu.min() > 0.5: uu[uu < 0.5] += 1; uu = np.minimum(uu, 1.0)
        tris.append((P[t], np.stack([uu, v[t]], 1), mat))
    return tris


def nrm_rows(v): return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def dirv(e, a, s):
    """unit direction: e elevation (deg, + up), a = how far round from straight back toward side s (deg)"""
    e, a = math.radians(e), math.radians(a)
    return np.array([-math.cos(e) * math.cos(a), s * math.cos(e) * math.sin(a), math.sin(e)])


# =============================================================================================== styles: anchors + params -> {state: tris}, materials
# a material: (texture kind, kwargs, cell w, cell h, seconds per cell, gain); every style's *_hot material is the flare version
MAXW = 2048 // NF                                 # resourcecompiler clamps textures to 2048 px: a 16-cell strip has 128 px cells at most


def M(kind, w=128, h=128, tpf=0.06, gain=1.0, blend='add', dark=None, **kw):
    if w > MAXW: w, h = MAXW, (MAXW if h == w else max(32, min(h, 64)))
    return dict(kind=kind, w=w, h=h, tpf=tpf, gain=gain, blend=blend, dark=dark, kw=kw)


def st_streamers(A, p):
    h = A['h']; mats = {'flow': M('flow', 256, 64, 0.05, pulses=3, width=0.42, base=0.5, fil=0.7), 'flow_hot': M('flow', 256, 64, 0.035, 1.6, pulses=4, width=0.45, fil=0.9, base=0.6)}
    def ribbon(root, s, e, a, L, sag, wave, w0, mat, n=12):
        t = np.linspace(0, 1, n)[:, None]
        d = dirv(e, a, s); side = nrm(np.cross(d, [0, 0, 1]))
        path = root + L * t * d + sag * L * t ** 2 * np.array([0, 0, -1]) + wave * L * t * np.sin(2.6 * math.pi * t) * side
        return cross_strip(path, w0 * (1 - 0.8 * t[:, 0]) + 0.6, mat)
    cfg = {'slack': (-34, 26, 0.32, 0.06, 0.95, 1.0, 'flow'), 'taut': (-10, 20, 0.05, 0.025, 1.15, 1.0, 'flow'), 'flare': (-6, 24, 0.03, 0.03, 1.32, 1.3, 'flow_hot')}
    out = {}
    for stn, (e, a, sag, wave, Lm, wm, mat) in cfg.items():
        tris = []
        for s, nm in ((1, 'l'), (-1, 'r')):
            root = A['sh'][nm] + np.array([-0.05 * h, 0, -0.04 * h])
            tris += ribbon(root, s, e, a, Lm * h, sag, wave, 0.13 * h * wm, mat)
            tris += ribbon(root + np.array([0.02 * h, 0, -0.07 * h]), s, e - 9, a + 14, Lm * h * 0.78, sag * 1.2, wave * 1.4, 0.075 * h * wm, mat)
        out[stn] = tris
    return out, mats


def st_static_field(A, p):
    h = A['h']; f = A['feet']; r = max(A['leg_r'] * 1.08, 0.2 * h); top = min(A['legs_top'] * 0.92, 0.55 * h)
    mats = {'bolts': M('bolts', 256, 128, 0.05, n=4), 'bolts_b': M('bolts', 256, 128, 0.06, n=3), 'bolts_hot': M('bolts', 256, 128, 0.035, 1.35, n=6, halo=6)}
    out = {'idle': cyl_band(f, (0, 0, 1), r, r * 1.05, 0.03 * h, top, 'bolts') + cyl_band(f, (0, 0, 1), r * 1.18, r * 1.25, 0.02 * h, top * 0.6, 'bolts_b'),
           'crackle': cyl_band(f, (0, 0, 1), r * 1.12, r * 1.2, 0.02 * h, top * 1.05, 'bolts_hot') + cyl_band(f, (0, 0, 1), r * 1.4, r * 1.5, 0.0, top * 0.7, 'bolts_hot')}
    return out, mats


def st_blade_wings(A, p):
    h = A['h']; root = A['back'] + np.array([0.02 * h, 0, 0.06 * h])
    mats = {'blade': M('blade', 256, 64, 0.05), 'blade_hot': M('blade', 256, 64, 0.03, 1.7)}
    lens = [0.72, 0.95, 0.84, 0.58]
    cfg = {'fold': ([-48, -60, -70, -78], 58, 0.78, 0.85, 'blade'), 'half': ([22, 6, -12, -30], 42, 0.9, 1.0, 'blade'),
           'spread': ([52, 33, 13, -7], 24, 1.0, 1.0, 'blade'), 'flare': ([55, 35, 14, -7], 22, 1.16, 1.18, 'blade_hot')}
    out = {}
    for stn, (els, b, lm, wm, mat) in cfg.items():
        tris = []
        for s in (1, -1):
            for k, e in enumerate(els):
                r0 = root + np.array([-0.01 * h * k, s * (0.05 + 0.012 * k) * h, -0.02 * h * k])
                d = dirv(e, 90 - b, s)
                L = lens[k] * h * lm
                nb = np.array([-1.0, 0, 0]) + d * d[0]; wv = nrm(np.cross(nb, d))     # blade face looks backward (the chase camera sees it)
                t = np.linspace(0, 1, 7)[:, None]
                path = r0 + L * t * d + 0.06 * L * np.sin(math.pi * t) * np.array([-1.0, 0, 0])
                wd = 0.11 * h * wm * np.array([0.55, 1.0, 1.0, 0.85, 0.6, 0.32, 0.02])
                tris += strip(path, np.repeat(wv[None], len(t), 0), wd, mat)
        out[stn] = tris
    return out, mats


def st_second_wind(A, p):
    h = A['h']; c = A['back'] + np.array([-0.08 * h, 0, 0.1 * h])
    mats = {'feather': M('feathers', 128, 256, 0.1, count=4), 'feather_hot': M('feathers', 128, 256, 0.06, 1.5, count=7),
            'halo': M('ring', 512, 32, 0.07, segs=3, base=0.25), 'halo_hot': M('ring', 512, 32, 0.04, 1.8, segs=5, base=0.5, glints=6)}
    def cards(sc, mat):
        tris = []
        for s in (1, -1):
            for k, (dy, dz, rot) in enumerate(((0.32, 0.0, 0), (0.5, -0.12, 55))):
                cc = c + np.array([-0.04 * h * k, s * (A['tw'] + dy * h * sc), dz * h])
                ud = np.array([math.sin(math.radians(rot)), s * math.cos(math.radians(rot)), 0])
                tris += card(cc, ud, (0, 0, 1), 0.32 * h * sc, 0.6 * h * sc, mat)
        return tris
    rr = max(A['W'] * 1.05, 0.36 * h); zc = A['zc'] - 0.05 * h; ctr = np.array([A['cx'], A['cy'], zc])
    out = {'feathers': {'idle': cards(1.0, 'feather'), 'gust': cards(1.3, 'feather_hot')},
           'halo': {'on': ring_flat(ctr, (0, 0, 1), rr, rr + 0.06 * h, 'halo', 64), 'burst': ring_flat(ctr, (0, 0, 1), rr * 1.3, rr * 1.3 + 0.1 * h, 'halo_hot', 64)}}
    return out, mats


def st_nanite_swarm(A, p):
    h = A['h']; ctr = np.array([A['cx'], A['cy'], A['zc'] - 0.04 * h]); r = max(A['W'] * 1.05, 0.33 * h)
    mats = {'motes': M('motes', 512, 64, 0.09, count=16, size=3.0), 'motes_hot': M('motes', 512, 64, 0.05, 1.5, count=30, size=3.4), 'hex': M('hex', 256, 256, 0.06, cells=9)}
    def bands(rm, mat):
        t = []
        for tilt in (18, -14):
            ax = (0, math.sin(math.radians(tilt)), math.cos(math.radians(tilt)))
            t += cyl_band(ctr, ax, r * rm, r * rm, -0.035 * h, 0.035 * h, mat, 48)
        return t
    U = A['U']; z0, z1 = 0.4 * h, A['top']
    hexs = shell(U, lambda C, Nf: C[:, 2] > z0, 2.5, 'hex', (A['cx'], A['cy']), z0, z1)
    return {'motes': {'idle': bands(1.0, 'motes'), 'surge': bands(1.12, 'motes_hot')}, 'hex': {'on': hexs}}, mats


def st_plasma_plumes(A, p):
    h = A['h']; mats = {'flame': M('flame', 256, 64, 0.045), 'flame_hot': M('flame', 256, 64, 0.03, 1.6)}
    def plumes(Lm, wm, mat):
        t = []
        for b in A['boosters'][:4]:
            d = nrm([-1, 0, -0.18]); pth = b + np.linspace(0, Lm * h, 6)[:, None] * d; _, e1, e2 = basis(d)
            for k in range(3):
                side = e1 * math.cos(k * math.pi / 3) + e2 * math.sin(k * math.pi / 3)
                t += strip(pth, np.repeat(side[None], 6, 0), np.full(6, wm * h), mat)
        return t
    return {'idle': plumes(0.36, 0.14, 'flame'), 'long': plumes(0.85, 0.2, 'flame'), 'flare': plumes(1.05, 0.26, 'flame_hot')}, mats


def st_beam_aegis(A, p):
    """a beam shield on the left forearm: an elongated hexagon facing out and forward, hex field + a hot rim"""
    h = A['h']; la = A['la']
    mats = {'hex': M('hex', 256, 256, 0.06, cells=5, lw=1.4), 'hex_hot': M('hex', 256, 256, 0.04, 1.8, cells=5, lw=1.8, fill=0.6),
            'rim': M('ring', 256, 32, 0.05, segs=2, base=0.4), 'rim_hot': M('ring', 256, 32, 0.03, 1.6, segs=3, base=0.6)}
    nv = nrm([0.2, 1.0, 0.0]); up = np.array([0, 0, 1.0]); side = nrm(np.cross(up, nv))

    def plate(sc, hm, rm):
        c = la + nv * 0.06 * h + np.array([0.05 * h, 0, 0.02 * h]); hh, hw = 0.26 * h * sc, 0.15 * h * sc
        poly = [c + up * hh, c + up * hh * 0.55 + side * hw, c - up * hh * 0.55 + side * hw, c - up * hh, c - up * hh * 0.55 - side * hw, c + up * hh * 0.55 - side * hw]
        uvp = lambda q: (0.5 + np.dot(q - c, side) / (2 * hw), 0.5 - np.dot(q - c, up) / (2 * hh))
        t = [(np.array([c, poly[i], poly[(i + 1) % 6]]), np.array([uvp(c), uvp(poly[i]), uvp(poly[(i + 1) % 6])]), hm) for i in range(6)]
        loop = np.array(poly + [poly[0]]); per = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(loop, axis=0), axis=1))]); per /= per[-1]
        for i in range(6):
            a0, a1 = loop[i], loop[i + 1]; o0, o1 = nrm(a0 - c), nrm(a1 - c); wd = 0.025 * h * sc
            t += quad(a0 - o0 * wd, a1 - o1 * wd, a1 + o1 * wd, a0 + o0 * wd, [(per[i], 0), (per[i + 1], 0), (per[i + 1], 1), (per[i], 1)], rm)
        return t
    return {'idle': plate(0.85, 'hex', 'rim'), 'raised': plate(1.0, 'hex', 'rim'), 'flare': plate(1.15, 'hex_hot', 'rim_hot')}, mats


def st_forge_plating(A, p):
    h = A['h']; U = A['U']; z0, z1 = 0.32 * h, A['top']
    mats = {'heat': M('heat', 256, 256, 0.08, 1.1, blend='alpha', dark=(70, 25, 0)), 'heat_hot': M('heat', 256, 256, 0.05, 1.7)}
    keep = lambda C, Nf: (Nf[:, 0] > 0.45) & (C[:, 2] > z0)
    return {'idle': shell(U, keep, 1.6, 'heat', (A['cx'], A['cy']), z0, z1), 'flare': shell(U, keep, 2.6, 'heat_hot', (A['cx'], A['cy']), z0, z1)}, mats


def st_gilded_rings(A, p):
    h = A['h']
    mats = {'ring': M('ring', 512, 32, 0.07, 1.5, blend='alpha', dark=(235, 165, 25), segs=2, base=0.8, glints=4, ticks=24),
            'ring_spin': M('ring', 512, 32, 0.03, 1.7, blend='alpha', dark=(250, 185, 40), segs=2, base=0.85, glints=6, ticks=24),
            'ring_hot': M('ring', 512, 32, 0.03, 1.8, segs=4, base=0.6, glints=8)}
    def rings(sc, mat):
        t = []
        for s, nm in ((1, 'l'), (-1, 'r')):
            c = A['sh'][nm] + np.array([-0.02 * h, s * 0.015 * h, -0.02 * h])
            r = min(0.14 * h, (A['h'] + 8 - c[2]) / 1.1) * sc
            t += ring_flat(c, (math.sin(math.radians(25)), s * 1.0, 0.35), r, r + 0.022 * h, mat, 40)
            t += ring_flat(c, (-math.sin(math.radians(30)), s * 0.6, 1.0), r * 0.78, r * 0.78 + 0.016 * h, mat, 36)
        return t
    return {'idle': rings(1.0, 'ring'), 'spin': rings(1.0, 'ring_spin'), 'flare': rings(1.22, 'ring_hot')}, mats


def st_bastion(A, p):
    h = A['h']; pc = A['back'] + np.array([-0.03 * h, 0, 0.1 * h])
    mats = {'proj': M('ring', 256, 32, 0.06, segs=3, base=0.35), 'proj_hot': M('ring', 256, 32, 0.035, 1.6, segs=3, base=0.5, glints=3),
            'core': M('sigil', 128, 128, 0.08, points=6), 'hex': M('hex', 256, 256, 0.05, cells=8), 'hex_hot': M('hex', 256, 256, 0.03, 1.8, cells=8, fill=0.7)}
    proj = lambda sc, mat: ring_flat(pc, (-1, 0, 0), 0.07 * h * sc, 0.1 * h * sc, mat, 32) + disc(pc + np.array([-1.0, 0, 0]), (-1, 0, 0), 0.065 * h * sc, 'core', 24)
    ctr = (A['cx'] - 0.05 * h, A['cy']); R = max(A['front_x'] - A['cx'], 0.3 * h) + 0.22 * h
    wall = lambda sc, mat: patch(ctr, R * sc, -58, 58, 0.12 * h, min(0.95 * h, A['h'] - 0.02 * h), mat, 14, 6)
    return {'projector': {'idle': proj(1.0, 'proj'), 'on': proj(1.25, 'proj_hot')}, 'wall': {'up': wall(1.0, 'hex'), 'flare': wall(1.06, 'hex_hot')}}, mats


def st_crimson_hunger(A, p):
    h = A['h']; root = A['back'] + np.array([0.02 * h, 0, 0.02 * h])
    mats = {'flow': M('flow', 256, 64, 0.045, 1.2, blend='alpha', dark=(55, 0, 12), pulses=4, width=0.3, fil=0.9, base=0.7, taper=1.0),
            'flow_hot': M('flow', 256, 64, 0.03, 1.3, pulses=5, width=0.3, fil=1.0, base=0.45),
            'beam': M('flow', 256, 64, 0.03, 1.8, pulses=5, taper=0, width=0.25, fil=1.0, base=0.5, speed=2)}
    def tendrils(Lm, de, da, mat):
        t = []
        for s in (1, -1):
            for k, (e, a, L) in enumerate(((12, 38, 0.72), (-14, 56, 0.82), (-38, 74, 0.66))):
                r0 = root + np.array([0, s * (0.08 + 0.06 * k) * h, (0.04 - 0.07 * k) * h])
                n = 14; tt = np.linspace(0, 1, n)[:, None]
                d = dirv(e + de, a + da, s); side = nrm(np.cross(d, [0, 0, 1])); up = np.cross(side, d)
                curl = 0.12 * L * h * tt ** 1.5
                path = r0 + L * Lm * h * tt * d + curl * (np.sin(3.2 * math.pi * tt + k) * side + np.cos(2.4 * math.pi * tt + k) * up)
                t += cross_strip(path, 0.08 * h * (1 - 0.85 * tt[:, 0]) + 0.5, mat, roll=0.4 * k)
        return t
    beam = cross_strip(np.linspace([0, 0, 0], [400, 0, 0], 8), np.full(8, 9.0), 'beam')
    return {'tendrils': {'idle': tendrils(1.0, 0, 0, 'flow'), 'lash': tendrils(1.35, 14, -24, 'flow_hot')}, 'drain': {'on': beam}}, mats


def st_hazard_rig(A, p):
    h = A['h']; f = A['feet']
    mats = {'bulb': M('bulb', 64, 64, 0.08), 'bulb_fast': M('bulb', 64, 64, 0.04, 1.4), 'sweep': M('beacon', 128, 128, 0.06), 'sweep_fast': M('beacon', 128, 128, 0.03, 1.4),
            'dust': M('dust', 512, 128, 0.05), 'dust_hot': M('dust', 512, 128, 0.035, 1.6)}
    def beacons(sc, bm, sm):
        t = []
        for nm in ('l', 'r'):
            top = A['sh'][nm].copy(); top[2] = min(top[2] + 0.01 * h, A['h'] - 0.03 * h)
            t += dome(top, 0.035 * h * sc, bm) + disc(top + np.array([0, 0, 0.015 * h]), (0, 0, 1), 0.17 * h * sc, sm, 24)
        return t
    ring = lambda sc, mat: ring_flat(f + np.array([0, 0, 3.0]), (0, 0, 1), 0.24 * h, 0.75 * h * sc, mat, 56)
    return {'beacons': {'idle': beacons(1.0, 'bulb', 'sweep'), 'alert': beacons(1.2, 'bulb_fast', 'sweep_fast')},
            'ring': {'on': ring(1.0, 'dust'), 'flare': ring(1.25, 'dust_hot')}}, mats


def st_phase_echo(A, p):
    h = A['h']; U, L = A['U'], A['L']
    mats = {'scan': M('scan', 128, 256, 0.07), 'scan_hot': M('scan', 128, 256, 0.04, 1.25)}
    z0, z1 = 0.0, A['top']; ax = (A['cx'], A['cy'])
    allk = lambda C, Nf: np.ones(len(C), bool)
    ghost = shell(U, allk, 1.0, 'scan_hot', ax, z0, z1) + (shell(L, allk, 1.0, 'scan_hot', ax, z0, z1) if L is not None else [])
    return {'echo': {'idle': shell(U, allk, 1.2, 'scan', ax, z0, z1, (-0.07 * h, 0, 0)), 'flare': shell(U, allk, 1.6, 'scan_hot', ax, z0, z1, (-0.14 * h, 0, 0.01 * h))},
            'ghost': {'on': ghost}}, mats


def st_psycho_frame(A, p):
    h = A['h']; U = A['U']; z0, z1 = 0.4 * h, A['top']
    mats = {'seams': M('seams', 256, 256, 0.08), 'seams_full': M('seams', 256, 256, 0.05, 1.4, fill=0.12), 'seams_hot': M('seams', 256, 256, 0.035, 1.8, fill=0.25)}
    keep = lambda C, Nf: (np.abs(C[:, 1] - A['cy']) < A['tw'] * 1.3) & (C[:, 2] > z0)
    sh = lambda off, mat: shell(U, keep, off, mat, (A['cx'], A['cy']), z0, z1)
    return {'idle': sh(1.0, 'seams'), 'full': sh(1.2, 'seams_full'), 'flare': sh(2.2, 'seams_hot')}, mats


def st_iron_sigil(A, p):
    h = A['h']; f = A['feet'] + np.array([0, 0, 2.5])
    mats = {'glyph': M('glyph', 512, 64, 0.2), 'glyph_hot': M('glyph', 512, 64, 0.08, 1.7), 'sigil': M('sigil', 256, 256, 0.15), 'sigil_hot': M('sigil', 256, 256, 0.06, 1.7),
            'crown': M('crown', 256, 128, 0.05)}
    sig = lambda sc, gm, sm: ring_flat(f, (0, 0, 1), 0.3 * h * sc, 0.48 * h * sc, gm, 56) + disc(f + np.array([0, 0, 0.5]), (0, 0, 1), 0.29 * h * sc, sm, 32)
    return {'sigil': {'idle': sig(1.0, 'glyph', 'sigil'), 'blaze': sig(1.15, 'glyph_hot', 'sigil_hot')},
            'crown': {'on': cyl_band(f, (0, 0, 1), 0.47 * h, 0.5 * h, 0.0, 0.3 * h, 'crown', 48)}}, mats


def st_radar_scope(A, p):
    """Sandviper: a radar scope ringing the hips (sweep, range rings, blips); brighter while a Spotter mark lives, pings on a new mark"""
    h = A['h']; c = np.array([A['feet'][0], A['feet'][1], A['hip'] * 0.92]); R = max(A['leg_r'] * 1.55, 0.5 * h)
    mats = {'scope': M('radar', 256, 256, 0.07), 'scope_hot': M('radar', 256, 256, 0.04, 1.5, blips=10),
            'rim': M('ring', 512, 32, 0.08, segs=2, base=0.25, ticks=36), 'rim_hot': M('ring', 512, 32, 0.04, 1.6, segs=4, base=0.45, ticks=36, glints=4)}
    def scope(sc, sm, rm, outer=False):
        t = disc(c, (0, 0, 1), R * sc, sm, 40) + ring_flat(c, (0, 0, 1), R * sc, R * sc + 0.035 * h, rm, 56)
        if outer: t += ring_flat(c, (0, 0, 1), R * sc * 1.3, R * sc * 1.3 + 0.03 * h, rm, 56)
        return t
    return {'idle': scope(1.0, 'scope', 'rim'), 'lock': scope(1.06, 'scope_hot', 'rim'), 'ping': scope(1.3, 'scope_hot', 'rim_hot', True)}, mats


def st_slipstream(A, p):
    """Kestrel: rigid vapour trails streaming straight back from the shoulder tips, the elbows and the hips; long and bright on a
    quick boost (the Slipstream window), a hotter flick when it cuts a hit"""
    h = A['h']; cy = A['cy']
    mats = {'trail': M('flow', 256, 32, 0.04, 1.3, pulses=4, width=0.36, base=0.5, fil=1.0, taper=1.1, speed=2),
            'trail_hot': M('flow', 256, 32, 0.025, 1.7, pulses=5, width=0.4, base=0.6, fil=1.1, taper=0.9, speed=2)}
    roots = []
    for s, nm in ((1, 'l'), (-1, 'r')):
        sh = A['sh'][nm]; la = A['la']
        roots.append((s, sh + np.array([-0.02 * h, s * 0.02 * h, -0.02 * h]), 1.0))
        roots.append((s, np.array([la[0] - 0.04 * h, cy + s * abs(la[1] - cy), la[2]]), 0.8))
        roots.append((s, np.array([A['cx'] - 0.05 * h, cy + s * A['tw'] * 1.05, A['hip'] * 1.02]), 0.7))
    def trails(Lm, wm, mat):
        t = []
        for s, r0, k in roots:
            d = nrm([-1.0, s * 0.1, 0.06]); n = 8; tt = np.linspace(0, 1, n)[:, None]
            path = r0 + Lm * k * h * tt * d
            t += cross_strip(path, 0.06 * h * wm * (1 - 0.75 * tt[:, 0]) + 0.6, mat)
        return t
    return {'idle': trails(0.45, 1.0, 'trail'), 'slip': trails(1.15, 1.25, 'trail_hot'), 'flare': trails(1.4, 1.6, 'trail_hot')}, mats


def st_aegis_pulse(A, p):
    """Warden: a ward ring circling the chest; the Aegis pulse sends a shockwave out to its real 900 u range along the ground and
    raises a hex barrier cylinder for as long as the Warden's own barrier holds"""
    h = A['h']; f = A['feet']
    ctr = np.array([A['cx'], A['cy'], A['zc'] - 0.12 * h]); rr = max(A['W'] * 1.2, 0.33 * h)
    Rw = max(A['W'] * 1.3, A['leg_r'] * 1.25, 0.4 * h)
    mats = {'band': M('ring', 512, 32, 0.07, segs=3, base=0.3, ticks=12, glints=3), 'band_hot': M('ring', 512, 32, 0.035, 1.6, segs=5, base=0.5, ticks=12, glints=5),
            'ward': M('hex', 256, 256, 0.06, 0.8, cells=5, lw=1.0, fill=0.04), 'ward_hot': M('hex', 256, 256, 0.03, 1.5, cells=5, lw=1.4, fill=0.3),
            'wave': M('pulse', 512, 64, 0.05, 1.3), 'wave_hot': M('pulse', 512, 64, 0.03, 1.7, segs=9)}
    ring = lambda sc, mat: ring_flat(ctr, (0.18, 0.0, 1.0), rr * sc, rr * sc + 0.06 * h, mat, 56) + ring_flat(ctr + np.array([0, 0, -0.06 * h]), (-0.12, 0.1, 1.0), rr * sc * 0.86, rr * sc * 0.86 + 0.04 * h, mat, 48)
    ward = lambda sc, mat: cyl_band(f, (0, 0, 1), Rw * sc, Rw * sc * 1.04, 0.03 * h, 0.9 * h, mat, 48, u_turns=3)
    g = f + np.array([0, 0, 3.0])
    wave = lambda r0, r1, mat: ring_flat(g, (0, 0, 1), r0 * h, r1 * h, mat, 72)
    return {'ring': {'idle': ring(1.0, 'band'), 'on': ring(1.06, 'band_hot')},
            'ward': {'up': ward(1.0, 'ward'), 'flare': ward(1.03, 'ward_hot')},
            'pulse': {'p1': wave(0.45, 0.75, 'wave_hot'), 'p2': wave(1.1, 1.6, 'wave_hot'), 'p3': wave(2.4, 3.1, 'wave')}}, mats


def st_siege_anchors(A, p):
    """Bastion: capacitor bars on the back charging upward; Siege mode drives four light stakes into the ground round the feet,
    joined by a square frame (the fortress footprint)"""
    h = A['h']; f = A['feet']; cy = A['cy']; bx = A['back'][0] - 0.03 * h
    mats = {'cap': M('stake', 256, 32, 0.06), 'cap_hot': M('stake', 256, 32, 0.03, 1.6, n=7),
            'stake': M('stake', 256, 32, 0.045, 1.2, n=4), 'stake_hot': M('stake', 256, 32, 0.03, 1.7, n=6),
            'frame': M('ring', 512, 32, 0.06, segs=4, base=0.35, ticks=20), 'frame_hot': M('ring', 512, 32, 0.03, 1.7, segs=6, base=0.55, ticks=20)}
    def caps(sc, mat):
        t = []
        for s in (1, -1):
            for k, dy in enumerate((0.16, 0.34)):
                y = cy + s * dy * A['W']; z0 = A['zc'] - 0.3 * h; z1 = z0 + 0.32 * h * sc * (1 - 0.15 * k)
                path = np.linspace([bx - 0.01 * h * k, y, z0], [bx - 0.01 * h * k, y, z1], 6)
                t += strip(path, np.repeat(np.array([[0, 1.0, 0]]), 6, 0), np.full(6, 0.045 * h * sc), mat) + strip(path, np.repeat(np.array([[1.0, 0, 0]]), 6, 0), np.full(6, 0.045 * h * sc), mat)
        return t
    Ra = max(A['leg_r'] * 1.25, 0.36 * h)
    def anchors_(sc, sm, fm):
        t = []; gp = []
        for a in (45, 135, 225, 315):
            d = np.array([math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0])
            top = f + d * Ra * 0.62 + np.array([0, 0, 0.5 * h * sc]); bot = f + d * Ra + np.array([0, 0, -0.04 * h])
            t += cross_strip(np.linspace(top, bot, 7), 0.06 * h * sc * np.linspace(1.0, 0.35, 7), sm)
            gp.append(f + d * Ra * 1.02 + np.array([0, 0, 2.5]))
        for i in range(4):
            a, b = gp[i], gp[(i + 1) % 4]; side = nrm(np.cross(b - a, [0, 0, 1])); path = np.linspace(a, b, 8)
            t += strip(path, np.repeat(side[None], 8, 0), np.full(8, 0.05 * h * sc), fm)
        return t
    return {'vents': {'idle': caps(1.0, 'cap'), 'charged': caps(1.12, 'cap_hot'), 'flare': caps(1.25, 'cap_hot')},
            'anchors': {'on': anchors_(1.0, 'stake', 'frame'), 'flare': anchors_(1.25, 'stake_hot', 'frame_hot')}}, mats


STYLES = dict(streamers=st_streamers, static_field=st_static_field, blade_wings=st_blade_wings, second_wind=st_second_wind, nanite_swarm=st_nanite_swarm,
              plasma_plumes=st_plasma_plumes, beam_aegis=st_beam_aegis, forge_plating=st_forge_plating, gilded_rings=st_gilded_rings, bastion=st_bastion,
              crimson_hunger=st_crimson_hunger, hazard_rig=st_hazard_rig, phase_echo=st_phase_echo, psycho_frame=st_psycho_frame, iron_sigil=st_iron_sigil,
              radar_scope=st_radar_scope, slipstream=st_slipstream, aegis_pulse=st_aegis_pulse, siege_anchors=st_siege_anchors)


def build_style(fkey, spec, A):
    res, mats = STYLES[spec['style']](A, spec.get('params') or {})
    parts = spec['parts']
    if not all(isinstance(v, dict) and all(isinstance(t, list) for t in v.values()) for v in res.values()):   # single-part styles
        res = {list(parts)[0]: res}
    for pid, pd in parts.items():
        for stn in pd['states']:
            if stn not in res.get(pid, {}): raise SystemExit('%s: style %s has no state %s.%s' % (fkey, spec['style'], pid, stn))
    return res, mats


# =============================================================================================== writing models and materials
def write_material(fkey, name, m, spec):
    d = os.path.join(OUT, REL_T); os.makedirs(d, exist_ok=True)
    rs = np.random.RandomState((sum(map(ord, fkey + name)) * 7919) % (1 << 30))
    I = TEX[m['kind']](m['w'], m['h'], rs, **m['kw'])
    hot = name.endswith('_hot') or name.endswith('_fast') or name.endswith('_spin') or name.endswith('_full')
    stem = '%s_%s' % (fkey, name)
    alpha = m.get('blend') == 'alpha'
    if alpha:     # dark smoky body (dark colour) with a glowing core (colour); the alpha follows the intensity
        J = np.clip(I * m['gain'], 0, 2.0)[..., None]; dk = np.array(m['dark'] or (60, 0, 10), float)[None, None] / 255; c = np.array(spec['color'], float)[None, None] / 255
        img = (np.clip(dk + c * np.clip(J - 0.55, 0, 1) * 1.6, 0, 1) * 255).astype(np.uint8)
        Image.fromarray((np.clip(J[..., 0] * 0.95, 0, 0.92) * 255).astype(np.uint8)).save(os.path.join(d, stem + '_trans.png'))
    else:
        img = colorize(I, spec['color'], spec.get('accent', (255, 255, 255)), m['gain'])
    Image.fromarray(img).save(os.path.join(d, stem + '_color.png'))
    T = '\t'
    lines = ['// IRONFRAME aura material (tools/auras.py, generated): additive, %d-cell flipbook %s' % (NF, m['kind']), 'Layer0', '{',
             T + 'shader "csgo_unlitgeneric.vfx"', T + 'F_BLEND_MODE %d' % (1 if alpha else 4), T + 'F_RENDER_BACKFACES 1', T + 'TextureColor "%s/%s_color.png"' % (REL_T, stem)]
    if alpha: lines.append(T + 'TextureTranslucency "%s/%s_trans.png"' % (REL_T, stem))
    lines += [
             T + 'F_TEXTURE_ANIMATION 1', T + 'g_nNumAnimationCells "%d"' % NF, T + 'g_vAnimationGrid "[%d.000000 1.000000]"' % NF,
             T + 'g_flAnimationTimePerFrame "%.3f"' % m['tpf'], T + 'g_vColorTint "[%.6f %.6f %.6f 0.000000]"' % (((1.0 if alpha else 1.6 if hot else 1.25),) * 3),
             T + 'g_flModelTintAmount "1.000"', '}']
    open(os.path.join(d, stem + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/%s.vmat' % (REL_T, stem), img


def write_smd(path, tris):
    L = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f"
    for P, UV, mat in tris:
        n = nrm(np.cross(P[1] - P[0], P[2] - P[0]))
        L.append(mat + '.vmat')
        for (x, y, z), (u, v) in zip(P, UV):
            L.append(fmt % (y, -x, z, n[1], -n[0], n[2], u, 1 - v))
    L.append("end")
    open(path, 'w', newline='\n').write('\n'.join(L) + '\n')


def write_model(fkey, pid, stn, tris, matpaths):
    rel = '%s/%s' % (REL_M, fkey); d = os.path.join(OUT, rel.replace('/', os.sep)); os.makedirs(d, exist_ok=True)
    name = '%s_%s' % (pid, stn)
    write_smd(os.path.join(d, name + '.smd'), tris)
    used = sorted({t[2] for t in tris})
    txt = modelio.vmdl_text(name, rel, [name], [(u + '.vmat', matpaths[u]) for u in used], [], surface='default', archetype='', entity='prop_dynamic', single_lod=True)
    vp = '%s/%s.vmdl' % (rel, name)
    open(os.path.join(OUT, vp.replace('/', os.sep)), 'w', newline='\n').write(txt)
    return vp


# =============================================================================================== particles (tools/particles.py blocks)
def aura_particle(fkey, spec):
    c = tuple(spec['color']); a = tuple(spec.get('accent', (255, 255, 255))); st = spec['style']
    soft = st in ('second_wind', 'nanite_swarm', 'crimson_hunger', 'phase_echo', 'psycho_frame')
    tex = PT.FLARE if soft else PT.SPARK
    grav = {'iron_sigil': (0, 0, 400), 'second_wind': (0, 0, -60), 'static_field': (0, 0, -500), 'hazard_rig': (0, 0, -400), 'siege_anchors': (0, 0, -600),
            'aegis_pulse': (0, 0, 120)}.get(st, (0, 0, -150))
    n = 26 if st in ('static_field', 'phase_echo', 'psycho_frame') else 18
    sparks = PT.system(48, [PT.sprites(tex, additive=True, overbright=2.2)],
                       [PT.move(0.04, grav), PT.decay(), PT.grow(end=0.2 if not soft else 1.4), PT.tint(c, start=0.1, end=0.6), PT.fade_out()],
                       [PT.color(a, c), PT.life(0.3, 0.7), PT.sphere(30, speed=(250, 700) if not soft else (80, 260)), PT.radius(4, 9) if not soft else PT.radius(10, 22), PT.alpha(1.0)],
                       [PT.burst(n)], [PT.child('%s/aura_%s_flash.vpcf' % (REL_P, fkey))], draw_dist=6000)
    flash = PT.system(2, [PT.sprites(PT.FLARE, additive=True, overbright=3.0)], [PT.decay(), PT.fade_out(0.06, prop=False), PT.grow(end=1.8)],
                      [PT.sphere(), PT.life(0.12), PT.color(a, c), PT.radius(70), PT.alpha(0.8)], [PT.burst(1)])
    d = os.path.join(OUT, REL_P.replace('/', os.sep)); os.makedirs(d, exist_ok=True)
    name = 'aura_' + fkey
    open(os.path.join(d, name + '_flash.vpcf'), 'w', encoding='utf-8', newline='\n').write(flash)
    open(os.path.join(d, name + '.vpcf'), 'w', encoding='utf-8', newline='\n').write(sparks)
    return '%s/%s.vpcf' % (REL_P, name), ['%s/%s_flash.vpcf' % (REL_P, name)]


# =============================================================================================== offline preview (same lights as mech_render)
BG_TOP, BG_BOT = np.array([0.42, 0.52, 0.62]), np.array([0.55, 0.47, 0.36])      # hazy sky -> sand (in-game light, not a dark studio)


class Cam:
    def __init__(self, pos, look, W, H, fov=40):
        self.pos = np.asarray(pos, float); f = nrm(np.asarray(look, float) - self.pos); r = nrm(np.cross(f, [0, 0, 1])); u = np.cross(r, f)
        self.f, self.r, self.u, self.W, self.H = f, r, u, W, H; self.fl = 0.5 * H / math.tan(math.radians(fov) / 2)

    def project(self, P):
        rel = P - self.pos; zc = rel @ self.f
        return rel @ self.r / zc * self.fl + self.W / 2, self.H / 2 - (rel @ self.u) / zc * self.fl, zc


def raster(cam, P, N, UV, mats, texfn, shade, zb=None, img=None, add=False, ovr=None):
    """triangle-soup rasteriser: opaque lit (shade) or additive textured (add), perspective-correct UV, depth test against zb"""
    W, H = cam.W, cam.H
    if img is None: img = np.zeros((H, W, 3), np.float32)
    own = zb is None
    if own: zb = np.full((H, W), np.inf, np.float32)
    al = np.zeros((H, W), np.float32)
    SX, SY, ZC = cam.project(P)
    ntri = len(P) // 3
    for t in range(ntri):
        z = ZC[3 * t:3 * t + 3]
        if (z <= 5).any(): continue
        x = SX[3 * t:3 * t + 3]; y = SY[3 * t:3 * t + 3]
        x0 = int(max(0, math.floor(x.min()))); x1 = int(min(W - 1, math.ceil(x.max()))); y0 = int(max(0, math.floor(y.min()))); y1 = int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d; b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d; c = 1 - a - b
        m = (a >= -1e-3) & (b >= -1e-3) & (c >= -1e-3)
        if not m.any(): continue
        w = 1.0 / z; ip = a * w[0] + b * w[1] + c * w[2]; zz = 1.0 / ip
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz < sub
        if not m.any(): continue
        pa, pb, pc = (a * w[0] / ip)[m], (b * w[1] / ip)[m], (c * w[2] / ip)[m]
        uv = pa[:, None] * UV[3 * t] + pb[:, None] * UV[3 * t + 1] + pc[:, None] * UV[3 * t + 2]
        if add:
            tex = texfn(mats[t]); th, tw = tex.shape[:2]
            col = tex[np.clip((uv[:, 1] * th).astype(int), 0, th - 1), np.clip((uv[:, 0] * tw).astype(int), 0, tw - 1)]
            if col.shape[1] == 4:
                o = ovr[y0:y1 + 1, x0:x1 + 1]; a_ = col[:, 3:4]
                o[m] = np.concatenate([o[m][:, :3] * (1 - a_) + col[:, :3] * a_, (o[m][:, 3:4] * (1 - a_) + a_)], 1)
            else: img[y0:y1 + 1, x0:x1 + 1][m] += col
        else:
            sub[m] = zz[m]
            img[y0:y1 + 1, x0:x1 + 1][m] = shade(t, uv, pa, pb, pc)
            al[y0:y1 + 1, x0:x1 + 1][m] = 1
    return img, al, zb


def render_mech(cam, mech):
    P, Nn, UV = mech['P'], mech['N'], mech['UV']
    L = dict(key=(nrm([0.45, -0.75, 0.5]), np.array([1.0, 0.86, 0.72]) * 1.25), fill=(nrm([0.2, 0.9, 0.15]), np.array([0.45, 0.5, 0.7]) * 0.45),
             rim=(nrm([-0.85, -0.25, 0.35]), np.array([0.8, 0.85, 0.95]) * 0.8))
    texs = {m: MR.texture(mech['key'], m) for m in set(mech['mats'])}
    def shade(t, uv, pa, pb, pc):
        nv = MR.norm_rows(pa[:, None] * Nn[3 * t] + pb[:, None] * Nn[3 * t + 1] + pc[:, None] * Nn[3 * t + 2])
        pp = pa[:, None] * P[3 * t] + pb[:, None] * P[3 * t + 1] + pc[:, None] * P[3 * t + 2]
        tex = texs[mech['mats'][t]]; th, tw = tex.shape[:2]
        alb = tex[((uv[:, 1] % 1) * (th - 1)).astype(int), ((uv[:, 0] % 1) * (tw - 1)).astype(int)] ** 2.2 * 1.5
        vd = MR.norm_rows(cam.pos - pp); nv = np.where(((nv * vd).sum(1) < 0)[:, None], -nv, nv)
        col = alb * 0.22
        for ld, lc in L.values():
            col = col + alb * (np.clip(nv @ ld, 0, 1)[:, None] * lc) + (np.clip((nv * MR.norm_rows(ld[None] + vd)).sum(1), 0, 1) ** 36)[:, None] * lc * 0.2
        return col
    return raster(cam, P, Nn, UV, None, None, shade)


def background(W, H):
    t = np.linspace(0, 1, H)[:, None, None]
    return np.broadcast_to(BG_TOP * (1 - t) + BG_BOT * t, (H, W, 3)).astype(np.float32).copy()


def compose(base_lin, al, aura, bloom=True, ovr=None):
    """mech over the sky/sand backdrop, then the additive aura (plus a soft bloom like the game's) and a filmic-ish tone map"""
    H, W = al.shape
    bg = background(W, H)
    img = bg * (1 - al[..., None]) + base_lin * al[..., None]
    if ovr is not None: img = img * (1 - ovr[..., 3:4]) + ovr[..., :3] ** 2.2 * ovr[..., 3:4]
    img = img + aura
    if bloom:
        a8 = Image.fromarray((np.clip(aura / 2, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(W / 60))
        img = img + np.asarray(a8, np.float32) / 255 * 0.9
    rgb = np.clip(img / (1 + img * 0.25) * 1.2, 0, 1) ** (1 / 2.2)
    return Image.fromarray((rgb * 255).astype(np.uint8))


def flat_tris(tris):
    P = np.concatenate([t[0] for t in tris]) if tris else np.zeros((0, 3))
    UV = np.concatenate([t[1] for t in tris]) if tris else np.zeros((0, 2))
    return P, UV, [t[2] for t in tris]


def mech_soup(A):
    P, N, UV, MAT = [], [], [], []
    for m in (A['L'], A['U']):
        if m is None: continue
        P.append(m['P']); N.append(m['N']); UV.append(m['UV']); MAT += m['mats']
    return dict(P=np.concatenate(P), N=np.concatenate(N), UV=np.concatenate(UV), mats=MAT, key=A['model'])


def views(A, W, H):
    h = A['h']; ctr = np.array([A['cx'] * 0.6 + A['feet'][0] * 0.4, A['cy'], h * 0.55])
    def orbit(yaw, elev, dist):
        y, e = math.radians(yaw), math.radians(elev)
        return Cam(ctr + dist * h * np.array([math.cos(e) * math.cos(y), math.cos(e) * math.sin(y), math.sin(e)]), ctr, W, H, 34)
    pilot = Cam(np.array([-A['cam_back'], 0, A['hip'] + A['cam_up']]), np.array([3000, 0, A['hip'] + A['cam_up']]), W, H, 74)
    return {'front': orbit(35, 8, 2.9), 'rear': orbit(150, 14, 2.9), 'pilot': pilot}


def draw_marks(im, cam, A, pilot):
    d = ImageDraw.Draw(im)
    sx, sy, z = cam.project(np.array([[A['feet'][0], A['feet'][1], A['h'] + 70]]))
    if z[0] > 5:
        x, y = float(sx[0]), float(sy[0]); r = max(3, 16 * cam.fl / z[0])
        d.polygon([(x, y - r * 1.6), (x + r, y), (x, y + r * 1.6), (x - r, y)], fill=(255, 150, 40))
    if pilot:
        cx, cy = cam.W / 2, cam.H / 2
        for dx, dy in ((-14, 0), (14, 0), (0, -14), (0, 14)): d.line([(cx + dx * 0.4, cy + dy * 0.4), (cx + dx, cy + dy)], fill=(255, 255, 255), width=2)


class Preview:
    """renders one frame's aura states over its mech (the mech rendered once per view)"""
    def __init__(self, A, spec, res, texs, W, H):
        self.A, self.spec, self.res, self.texs, self.W, self.H = A, spec, res, texs, W, H
        self.mech = mech_soup(A); self.cams = views(A, W, H); self.base = {}

    def mech_view(self, v):
        if v not in self.base: self.base[v] = render_mech(self.cams[v], self.mech)
        return self.base[v]

    def frame(self, v, states, t, k=None):
        """states: {part: state or None}; t seconds (flipbook cell); k: {part: intensity}"""
        cam = self.cams[v]; img0, al, zb = self.mech_view(v)
        aura = np.zeros((self.H, self.W, 3), np.float32); ovr = np.zeros((self.H, self.W, 4), np.float32)
        for pid, stn in states.items():
            if not stn: continue
            tris = self.res[pid][stn]; P, UV, mats = flat_tris(tris)
            kk = (k or {}).get(pid, 1.0)
            def texfn(mat, _t=t, _k=kk):
                img, tpf, hot = self.texs[mat]; cell = int(_t / tpf) % NF; w = img.shape[1] // NF
                c = img[:, cell * w:(cell + 1) * w].astype(np.float32) / 255
                if c.shape[2] == 4: c[..., 3] *= min(1.0, _k * 1.4); return c
                return c * (1.6 if hot else 1.25) * _k
            raster(cam, P, None, UV, mats, texfn, None, zb=zb, img=aura, add=True, ovr=ovr)
        im = compose(img0, al, aura, ovr=ovr)
        draw_marks(im, cam, self.A, v == 'pilot')
        return im, aura

    def corridor(self, states, k=None):
        """mean aura light in the crosshair box of the pilot view (0 = clear)"""
        _, aura = self.frame('pilot', states, 0.3, k)
        cx, cy = self.W // 2, self.H // 2; r = self.W // 18
        return float(aura[cy - r:cy + r, cx - r:cx + r].mean())


def base_states(spec, held=False):
    out = {}
    for pid, pd in spec['parts'].items():
        if pd.get('attach') == 'none': continue
        out[pid] = pd.get('idle')
    if held:
        for hd in spec.get('holds') or []: out[hd['part']] = hd['state']
    return out


def flare_timeline(spec, fps, seconds):
    """the first flare entry (and any others on the same event) played from t 0: [(t, {part: state}, {part: k})]"""
    if not spec.get('flares'): return []
    ev = spec['flares'][0]['on']; held = ev in ('trait:on',) or any(f['on'] == ev and f.get('if') for f in spec['flares'])
    base = base_states(spec, held=held or ev in ('block', 'assault_on'))
    ents = [f for f in spec['flares'] if f['on'] == ev and f.get('part') in spec['parts'] and spec['parts'][f['part']].get('attach') != 'none']
    out = []
    for i in range(int(fps * seconds)):
        t = i / fps; st = dict(base); kk = {}
        for f in ents:
            cur = None
            for s, t0 in f['seq']:
                if t >= t0: cur = s
            if cur is not None: st[f['part']] = cur if cur else base.get(f['part'])
        for pid, s in st.items(): kk[pid] = state_k(spec, pid, s)
        out.append((t, st, kk))
    return out


def state_k(spec, pid, s):
    pd = spec['parts'][pid]
    if s is None: return 0
    ks = spec.get('k') or {}
    if s in ks: return ks[s]
    return spec.get('idle', 0.55) if s == pd.get('idle') else 1.0


def preview_one(args):
    fkey, W, H = args
    spec = AURAS_SPEC[fkey]; A = anchors(fkey); res, mats = build_style(fkey, spec, A)
    texs = {}
    for name, m in mats.items():
        p = os.path.join(OUT, REL_T, '%s_%s_color.png' % (fkey, name))
        hot = name.endswith(('_hot', '_fast', '_spin', '_full'))
        t = np.asarray(Image.open(p).convert('RGB'))
        if m.get('blend') == 'alpha': t = np.concatenate([t, np.asarray(Image.open(p.replace('_color.png', '_trans.png')).convert('L'))[..., None]], 2)
        texs[name] = (t, m['tpf'], hot)
    pv = Preview(A, spec, res, texs, W, H)
    idle = base_states(spec); kid = {pid: state_k(spec, pid, s) for pid, s in idle.items()}
    os.makedirs(PREV, exist_ok=True)
    # idle loop GIF (rear three-quarter view: the side other pilots see most) and the flare GIF
    fr = [pv.frame('rear', idle, i / 12.0, kid)[0] for i in range(20)]
    fr[0].save(os.path.join(PREV, fkey + '_idle.gif'), save_all=True, append_images=fr[1:], duration=83, loop=0, optimize=True)
    tl = flare_timeline(spec, 15, 2.0)
    ff = [pv.frame('rear', st, t, kk)[0] for t, st, kk in tl] or fr[:1]
    for im, (t, st, kk) in zip(ff, tl): ImageDraw.Draw(im).text((8, H - 18), 't %.2f s  %s' % (t, ' '.join('%s:%s' % (p, s) for p, s in st.items() if s)), fill=(255, 255, 255))
    ff[0].save(os.path.join(PREV, fkey + '_flare.gif'), save_all=True, append_images=ff[1:], duration=67, loop=0, optimize=True)
    # sheet tiles: front idle, rear idle, rear peak flare, pilot camera (peak flare) + the corridor numbers
    peak = max(tl, key=lambda x: sum(1 for s in x[1].values() if s and ('flare' in s or 'spread' in s or 'burst' in s or 'lash' in s or 'blaze' in s or 'crackle' in s)) * 10 + x[0] * 0.01)[1:] if tl else (idle, kid)
    tiles = [pv.frame('front', idle, 0.5, kid)[0], pv.frame('rear', idle, 0.5, kid)[0], pv.frame('rear', peak[0], 0.5, peak[1])[0], pv.frame('pilot', peak[0], 0.5, peak[1])[0]]
    c_idle = pv.corridor(idle, kid); c_flare = pv.corridor(peak[0], peak[1])
    # IFF clearance: highest aura point within 80 u of the head column
    top = -1e9
    for pid, sts in res.items():
        if spec['parts'][pid].get('attach') == 'none': continue
        for tris in sts.values():
            P, _, _ = flat_tris(tris)
            if len(P):
                near = np.hypot(P[:, 0] - A['feet'][0], P[:, 1] - A['feet'][1]) < 80
                if near.any(): top = max(top, float(P[near, 2].max()))
    return fkey, tiles, dict(corridor_idle=round(c_idle, 4), corridor_flare=round(c_flare, 4), top_over_head=round(top - A['h'], 1), height=A['h'])


def make_sheet(rows, W, H):
    lab = 26
    sheet = Image.new('RGB', (W * 4 + 220, (H + lab) * len(rows) + 30), (22, 24, 30)); d = ImageDraw.Draw(sheet)
    d.text((8, 8), 'IRONFRAME frame auras: front idle | rear idle | rear flare | pilot camera at the flare (orange diamond = IFF marker, white = crosshair)', fill=(230, 230, 230))
    for i, (fkey, tiles, info) in enumerate(rows):
        y = 30 + i * (H + lab); spec = AURAS_SPEC[fkey]
        for j, t in enumerate(tiles): sheet.paste(t, (j * W, y + lab))
        d.text((6, y + 6), '%s - %s (%s)' % (FRAMES[fkey]['name'], spec['name'], spec['style']), fill=tuple(spec['color']))
        d.text((W * 4 + 8, y + lab + 8), 'trait: %s\ncrosshair idle %.3f\ncrosshair flare %.3f\nover head: %+.0f u\n(IFF at +70)' % (
            FRAMES[fkey].get('trait_name', ''), info['corridor_idle'], info['corridor_flare'], info['top_over_head']), fill=(210, 210, 210))
    sheet.save(os.path.join(PREV, 'sheet.png'))


def write_models_md(gen):
    p = os.path.join(PROJ, 'docs', 'MODELS.md')
    if not os.path.exists(p): return
    txt = open(p, encoding='utf-8').read()
    B, E = '<!-- auras:begin -->', '<!-- auras:end -->'
    if B in txt: txt = txt[:txt.index(B)].rstrip('\n') + '\n' + txt[txt.index(E) + len(E):].lstrip('\n')
    L = ['', B, '## Frame auras (tools/auras.py)', '',
         'Written by `tools/auras.py` (tools/frames.py rewrites this file: re-run auras.py after it). One small model per aura part state in',
         '`models/ifr/aura/<frame>/<part>_<state>.vmdl`, built in the frame\'s own model frame (origin under the feet, x forward) and parented',
         'to its upper or legs prop with no offset; materials `materials/ifr/aura/<frame>_*.vmat` (additive or alpha-blended unlit, 16-cell',
         'flipbook strips of 128 px cells at most); particles `particles/ifr/aura/aura_<frame>.vpcf`. Behaviour: data/parts.json#auras,',
         'docs/FEATURES.md "Frame auras".', '',
         '| Frame key | Model | Style | Parts: states | Triangles | Materials | Texture px | Preview |', '|---|---|---|---|---|---|---|---|']
    for k, e in gen['frames'].items():
        fr = FRAMES.get(k, {})
        ps = '; '.join('%s (%s): %s' % (pid, pd['attach'], ', '.join(pd['states'])) for pid, pd in e['parts'].items())
        L.append('| `%s` | `%s` | %s | %s | %s | %s | %s | [idle](../preview/auras/%s_idle.gif) [flare](../preview/auras/%s_flare.gif) |' % (
            k, fr.get('model', ''), e.get('style', ''), ps, e.get('tris', ''), e.get('materials', ''), e.get('texture_px', ''), k, k))
    L += ['', 'Review sheet: [preview/auras/sheet.png](../preview/auras/sheet.png).', E, '']
    open(p, 'w', encoding='utf-8', newline='\n').write(txt.rstrip('\n') + '\n' + '\n'.join(L))


# =============================================================================================== main
MODELS = json.load(open(os.path.join(OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
AURAS_SPEC = {k: v for k, v in (PARTS.get('auras') or {}).items() if not k.startswith('_')}


def main():
    a = sys.argv[1:]
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 6
    keys = []
    for k in AURAS_SPEC:
        if only and k not in only: continue
        if k not in FRAMES: sys.exit('auras: %s is not a frame part key' % k)
        if FRAMES[k]['model'] not in MODELS: print('skip %s: model %s not in models.json' % (k, FRAMES[k]['model'])); continue
        keys.append(k)
    gpath = os.path.join(OUT, '_gen', 'auras.json')
    gen = json.load(open(gpath, encoding='utf-8')) if os.path.exists(gpath) else {'frames': {}, 'pools': {}}
    if '--preview-only' not in a:
        vmdls, vpcfs, t0 = [], [], time.time()
        for k in keys:
            spec = AURAS_SPEC[k]; A = anchors(k); res, mats = build_style(k, spec, A)
            mp = {}
            for name, m in mats.items(): mp[name], _ = write_material(k, name, m, spec)
            entry = {'style': spec['style'], 'parts': {}}
            ntri = 0
            for pid, pd in spec['parts'].items():
                entry['parts'][pid] = {'attach': pd.get('attach', 'upper'), 'states': {}}
                for stn in pd['states']:
                    vp = write_model(k, pid, stn, res[pid][stn], mp); entry['parts'][pid]['states'][stn] = vp; vmdls.append(vp); ntri += len(res[pid][stn])
            eff, kids = aura_particle(k, spec); vpcfs += [eff] + kids
            entry['tris'] = ntri; entry['materials'] = len(mats); entry['texture_px'] = sum(m['w'] * m['h'] * NF for m in mats.values())
            gen['frames'][k] = entry; gen['pools']['aura_' + k] = {'count': 4, 'effect': eff}
            print('%-10s %-15s %d parts, %d states, %d tris, %d materials' % (k, spec['style'], len(spec['parts']), sum(len(p['states']) for p in spec['parts'].values()), ntri, len(mats)))
        write_models_md(gen)
        gen['version'] = 1; gen['note'] = 'tools/auras.py: aura models per frame part key, the aura particle pools (map entities ifr_pfx_aura_<frame>_00..03)'
        if '--no-compile' not in a:
            import frames as FR
            log = os.path.join(json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work'], 'logs', 'rc_auras.log')
            cres = FR.compile_models(OUT, [REL_M, REL_T, REL_P], vmdls + vpcfs, log)
            bad = [v for v, (ok, s, pr) in cres.items() if not ok]
            print('compiled %d/%d in %.0f s%s' % (len(cres) - len(bad), len(cres), time.time() - t0, ('; FAILED: ' + ', '.join(bad[:8])) if bad else ''))
            for v in bad[:5]: print('  ', v, cres[v][2][:3])
            gen['compiled'] = not bad
        json.dump(gen, open(gpath, 'w', encoding='utf-8'), indent=1)
        print('wrote', os.path.relpath(gpath, PROJ))
    if '--no-preview' not in a:
        W, H = 300, 340; t0 = time.time()
        from multiprocessing import Pool
        with Pool(min(jobs, len(keys))) as pool: rows = pool.map(preview_one, [(k, W, H) for k in keys])
        order = [k for k in AURAS_SPEC if k in keys]; rows.sort(key=lambda r: order.index(r[0]))
        if not only: make_sheet(rows, W, H)
        rep = {r[0]: r[2] for r in rows}
        rp = os.path.join(PREV, 'report.json'); old = json.load(open(rp)) if os.path.exists(rp) else {}
        old.update(rep); json.dump(old, open(rp, 'w'), indent=1)
        for k, info in rep.items(): print('%-10s crosshair idle %.3f flare %.3f, over head %s' % (k, info['corridor_idle'], info['corridor_flare'], ('%+.0f u' % info['top_over_head']) if info['top_over_head'] > -1e6 else 'clear'))
        print('previews in %.0f s -> %s' % (time.time() - t0, os.path.relpath(PREV, PROJ)))


if __name__ == '__main__':
    main()
