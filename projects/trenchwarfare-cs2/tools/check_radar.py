"""Radar alignment check: does the shipped overview put a player's dot where the radar picture draws the place he stands, and does the
script's !pos square name the square printed on the radar?

usage: check_radar.py [--digest out/digest.json] [--addon out/addon] [--game out/game]       (from the project folder)
  needs tools/make_radar.py's outputs (out/radar_clean.png, out/radar_region.json, the radar png, the overview txt) and a map digest
  (named points: trench_<tg>_N, heal_<tg>_N, mortarpit_<tg>_K). Exit 1 on any failure. Writes out/step8/radar_alignment.png (the shipped
  radar with every named point drawn through the overview math) and out/step8/radar_alignment.json.

Checks
  1 constants: out/radar_region.json = the overview's pos_x / pos_y / scale x 1024 = CONFIG.RADAR in 00_config.js = make_radar.py's X0 / Y0 / SCALE
  2 the script: radarSquare() is taken from the built src/mg_trenchwarfare.js and run in node on every named point; its square must be
    the one the radar's printed grid (16 x 16 over the 1024 px picture) puts the point's pixel in
  3 the picture: CS2's dot for a point is at ((x - pos_x) / scale, (pos_y - y) / scale) px of the 1024 radar. At that pixel (on the
    4096 px master, unlabelled) every infantry post must be on a drawn trench floor, every mortar pit on its drawn tube, every dressing
    station within 40 u of its drawn red cross. Errors in world units and in radar pixels.
What it cannot check: that CS2 really reads pos_x / pos_y as the top-left corner and scale per pixel of a 1024 picture (the cs2port
convention; in game: stand somewhere, `!pos`, compare the dot)."""
import os, sys, re, json, subprocess, argparse
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
ap = argparse.ArgumentParser()
ap.add_argument('--digest', default=os.path.join(ROOT, 'out', 'digest.json'))
ap.add_argument('--addon', default=os.path.join(ROOT, 'out', 'addon'))
ap.add_argument('--game', default=os.path.join(ROOT, 'out', 'game'))
a = ap.parse_args()
prob = []; rep = {}

# ---- 1 constants
rg = json.load(open(os.path.join(ROOT, 'out', 'radar_region.json')))
ov = open(os.path.join(a.game, 'resource', 'overviews', 'mg_trenchwarfare.txt')).read()
pos_x = float(re.search(r'"pos_x"\s+"(-?[\d.]+)"', ov).group(1)); pos_y = float(re.search(r'"pos_y"\s+"(-?[\d.]+)"', ov).group(1))
scale = float(re.search(r'"scale"\s+"([\d.]+)"', ov).group(1))
cfg = open(os.path.join(ROOT, 'src', 'modules', '00_config.js'), encoding='utf-8').read()
m = re.search(r'RADAR:\s*\{\s*x0:\s*(-?[\d.]+),\s*y0:\s*(-?[\d.]+),\s*span:\s*([\d.]+)', cfg)
cr = dict(x0=float(m.group(1)), y0=float(m.group(2)), span=float(m.group(3)))
mr = open(os.path.join(HERE, 'make_radar.py'), encoding='utf-8').read()
mx0, my0 = (float(v) for v in re.search(r'X0, Y0 = (-?[\d.]+), (-?[\d.]+)', mr).groups())
msc = float(re.search(r'SCALE = ([\d.]+)', mr).group(1))
consts = dict(region=rg, overview=dict(pos_x=pos_x, pos_y=pos_y, scale=scale, span=scale * 1024), config=cr, make_radar=dict(x0=mx0, y0=my0, span=msc * 1024))
rep['constants'] = consts
for nm, (x0, y0, sp) in (('overview', (pos_x, pos_y, scale * 1024)), ('CONFIG.RADAR', (cr['x0'], cr['y0'], cr['span'])), ('make_radar', (mx0, my0, msc * 1024))):
    if abs(x0 - rg['x0']) > 0.01 or abs(y0 - rg['y0']) > 0.01 or abs(sp - rg['span']) > 0.01:
        prob.append('constants: %s (%.1f, %.1f, span %.1f) disagrees with out/radar_region.json (%.1f, %.1f, %.1f)' % (nm, x0, y0, sp, rg['x0'], rg['y0'], rg['span']))

# ---- named points
D = json.load(open(a.digest))
pts = []
for e in D['entities']:
    n = e.get('name') or ''
    mm = re.match(r'^(trench|heal|mortarpit)_(t|ct)_(\d+)$', n)
    if mm: pts.append((mm.group(1), n, e['origin'][0], e['origin'][1]))
if not pts: prob.append('no named points in %s' % a.digest)
rep['points'] = len(pts)

# ---- 2 the script's radarSquare against the printed grid
js = open(os.path.join(ROOT, 'src', 'mg_trenchwarfare.js'), encoding='utf-8').read()
fn = re.search(r'function radarSquare\(x, y\) \{.*?\n\}', js, re.S).group(0)
prog = 'const CONFIG = { RADAR: %s };\n%s\nconst P = %s;\nconsole.log(JSON.stringify(P.map(p => radarSquare(p[0], p[1]))));' % (
    json.dumps(cr), fn, json.dumps([[p[2], p[3]] for p in pts]))
js_sq = json.loads(subprocess.run(['node', '-e', prog], capture_output=True, text=True, check=True).stdout)
px = lambda x, y: ((x - pos_x) / scale, (pos_y - y) / scale)               # CS2's dot, 1024 px radar
bad_sq = 0
for p, s in zip(pts, js_sq):
    u, v = px(p[2], p[3])
    want = chr(65 + int(u // 64)) + str(int(v // 64) + 1) if 0 <= u < 1024 and 0 <= v < 1024 else 'off the map'
    if s != want: bad_sq += 1; prob.append('!pos square: %s at (%.0f, %.0f): script says %s, the printed grid %s' % (p[1], p[2], p[3], s, want))
rep['pos_squares'] = dict(checked=len(pts), wrong=bad_sq)

# ---- 3 the picture under each dot (4096 px unlabelled master)
M = np.asarray(Image.open(os.path.join(ROOT, 'out', 'radar_clean.png')).convert('RGB'), np.int32)
K = M.shape[0] / 1024.0
def near(col, tol):
    return np.all(np.abs(M - np.array(col)) <= tol, axis=-1)
trench = near((58, 49, 40), 14) | near((82, 70, 56), 14) | near((56, 64, 60), 14) | near((112, 92, 66), 14)
tube = near((46, 44, 40), 10)
red = near((178, 34, 30), 30)
dt_trench = ndimage.distance_transform_edt(~trench); dt_tube = ndimage.distance_transform_edt(~tube); dt_red = ndimage.distance_transform_edt(~red)
upp4 = scale / K                                                          # world units per master pixel
rows = []
for kind, n, x, y in pts:
    u, v = px(x, y); i, j = int(round(v * K)), int(round(u * K))
    if not (0 <= i < M.shape[0] and 0 <= j < M.shape[1]): prob.append('%s at (%.0f, %.0f) is off the radar' % (n, x, y)); continue
    dist = {'trench': dt_trench, 'mortarpit': dt_tube, 'heal': dt_red}[kind][i, j] * upp4
    lim = {'trench': 4.0, 'mortarpit': 6.0, 'heal': 40.0}[kind]
    rows.append(dict(name=n, x=x, y=y, radar_px=[round(u, 1), round(v, 1)], off_world=round(float(dist), 1), off_radar_px=round(float(dist) / scale, 2)))
    if dist > lim: prob.append('%s at (%.0f, %.0f): the drawn %s is %.0f u (%.1f radar px) from CS2\'s dot (limit %.0f u)' % (n, x, y, kind, dist, dist / scale, lim))
rep['rows'] = rows
for kind in ('trench', 'mortarpit', 'heal'):
    d = [r['off_world'] for r in rows if r['name'].startswith(kind + '_')]
    if d: rep['max_off_' + kind] = dict(world=max(d), radar_px=round(max(d) / scale, 2), n=len(d))

# ---- picture
R = Image.open(os.path.join(a.addon, 'panorama/images/overheadmaps/mg_trenchwarfare_radar_psd.png')).convert('RGB')
dr = ImageDraw.Draw(R)
for kind, n, x, y in pts:
    u, v = px(x, y); c = {'trench': (255, 0, 255), 'heal': (0, 255, 255), 'mortarpit': (255, 255, 0)}[kind]
    dr.ellipse((u - 4, v - 4, u + 4, v + 4), outline=c, width=2)
s8 = os.path.join(ROOT, 'out', 'step8'); os.makedirs(s8, exist_ok=True)
R.save(os.path.join(s8, 'radar_alignment.png'))
rep['problems'] = prob
json.dump(rep, open(os.path.join(s8, 'radar_alignment.json'), 'w'), indent=1)
print('radar: pos %.0f %.0f scale %.2f (span %.1f) = region = CONFIG.RADAR = make_radar: %s' % (pos_x, pos_y, scale, scale * 1024, 'yes' if not any(p.startswith('constants') for p in prob) else 'NO'))
print('!pos squares: %d of %d agree with the printed grid' % (len(pts) - bad_sq, len(pts)))
for kind in ('trench', 'mortarpit', 'heal'):
    if 'max_off_' + kind in rep:
        r = rep['max_off_' + kind]; print('%-9s %2d points, largest gap dot -> drawn feature %.1f u = %.2f radar px' % (kind, r['n'], r['world'], r['radar_px']))
for p in prob: print('RADAR:', p)
print('RESULT: %s' % ('clean' if not prob else '%d problem(s)' % len(prob)))
sys.exit(1 if prob else 0)
