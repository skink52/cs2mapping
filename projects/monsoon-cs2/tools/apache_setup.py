"""Installs the CC-BY AH-64 Apache (US helicopters) into the addon tree and measures it for the script and the map generator.

usage: python apache_setup.py [<addon out dir>] [--src <folder holding models/ and materials/>] [--scale 1.0] [--no-copy]
  copies  <src>/models/vehicles/apache      -> <out>/models/vehicles/apache
          <src>/materials/models/vehicles/apache -> <out>/materials/models/vehicles/apache      (only files that differ)
  writes  <out>/../apache.json  (model, nose_yaw, length, rotor_radius, bounds, anims, seats, gun muzzle, rocket pods, credit)

Source: C:\\source2\\projects\\apache\\cs2_apache (README.txt, CREDITS.txt). On this PC that folder holds only the texts and a
preview; the converted trees were installed into content\\csgo_addons\\mapgames, so that addon is the fallback source.
Credit (CC-BY-4.0, required wherever the map is shared): see CREDITS in apache.json.

Axes: an SMD vertex (sx, sy, sz) lands in Hammer at (-sy, sx, sz) (ModelDoc turns SMD imports 90 deg about Z; docs/creation/models.md).
All positions in apache.json are MODEL SPACE in Hammer units (what an entity-local offset is), after --scale. The nose points along
`nose_dir` (+y for this model): an entity yaw of `heading + nose_yaw` makes the nose point along `heading`. Every position also has a
`*_fwd` twin in the nose frame (x forward, y left, z up) for script maths that works in heading space.
The vmdl's model_archetype is checked: "animated_model" works as prop_dynamic; were it "static_prop_model" a copy apache_dyn.vmdl
with archetype "" is written and named in the json.
"""
import os, sys, re, json, shutil, filecmp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_CANDIDATES = [r'C:\source2\projects\apache\cs2_apache',
                  r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mapgames']
MODEL_REL = 'models/vehicles/apache'
MAT_REL = 'materials/models/vehicles/apache'
CREDIT = ('This work is based on "AH-64E Apache "Guardian"" (https://sketchfab.com/3d-models/ah-64e-apache-guardian-'
          '9eb641f9179d413e87367ebd9b96347a) by Jeyhun1985 (https://sketchfab.com/Jeyhun1985) licensed under CC-BY-4.0 '
          '(http://creativecommons.org/licenses/by/4.0/)')


def find_src(explicit=None):
    for c in ([explicit] if explicit else SRC_CANDIDATES):
        if c and os.path.exists(os.path.join(c, MODEL_REL, 'apache.vmdl')): return c
    raise SystemExit('apache: no source with %s/apache.vmdl in %s' % (MODEL_REL, [explicit] if explicit else SRC_CANDIDATES))


def copy_tree(src, dst):
    n = 0
    for root, _, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            a, b = os.path.join(root, f), os.path.join(dst, rel, f)
            if not os.path.exists(b) or not filecmp.cmp(a, b, shallow=False):
                shutil.copy2(a, b); n += 1
    return n


def read_smd(path):
    """-> bone names, bone rest positions (Hammer), per-vertex bone id, positions (Hammer)"""
    lines = open(path).read().split('\n')
    i = lines.index('nodes') + 1; names = {}
    while lines[i].strip() != 'end':
        m = re.match(r'\s*(\d+)\s+"([^"]*)"', lines[i]); names[int(m.group(1))] = m.group(2); i += 1
    i = lines.index('skeleton') + 2; bpos = {}
    while lines[i].strip() != 'end' and not lines[i].startswith('time'):
        v = lines[i].split(); bpos[int(v[0])] = (-float(v[2]), float(v[1]), float(v[3])); i += 1
    t = lines.index('triangles') + 1
    rows = np.array([l.split()[:4] for l in lines[t:] if l[:1].isdigit() or l[:1] == ' '], float)
    return names, bpos, rows[:, 0].astype(int), np.stack([-rows[:, 2], rows[:, 1], rows[:, 3]], 1)


def measure(model_dir, scale=1.0):
    names, bpos, bone, P = read_smd(os.path.join(model_dir, 'apache_lod0.smd'))
    P = P * scale; bpos = {k: np.array(v) * scale for k, v in bpos.items()}
    bid = {v: k for k, v in names.items()}
    main, tail = bid.get('rotor_main', 1), bid.get('rotor_tail', 2)
    B = P[bone == 0]
    lo = np.percentile(B, 0.05, axis=0); hi = np.percentile(B, 99.95, axis=0)      # a few stray vertices sit far outside the hull
    # long axis and nose: the tail rotor is at the tail end
    ext = hi - lo; la = int(np.argmax(ext[:2])); sa = 1 - la
    nose_sign = 1.0 if bpos[tail][la] < bpos[main][la] else -1.0
    nose_dir = [0.0, 0.0, 0.0]; nose_dir[la] = nose_sign
    nose_yaw = -float(np.degrees(np.arctan2(nose_dir[1], nose_dir[0])))
    f = B[:, la] * nose_sign                       # forward coordinate
    l = B[:, sa] * (-nose_sign if la == 1 else nose_sign)   # left coordinate (forward x left = up)
    z = B[:, 2]
    def to_model(fw, left, up):
        v = [0.0, 0.0, 0.0]; v[la] = fw * nose_sign; v[sa] = left * (-nose_sign if la == 1 else nose_sign); v[2] = up
        return [round(float(x), 1) for x in v]
    def both(d, key, fw, left, up):
        d[key] = to_model(fw, left, up); d[key + '_fwd'] = [round(float(fw), 1), round(float(left), 1), round(float(up), 1)]
    hub = bpos[main]
    rm = P[bone == main]; rotor_r = float(np.percentile(np.linalg.norm((rm - hub)[:, :2], axis=1), 99.9))
    rt = P[bone == tail]; tail_r = float(np.percentile(np.linalg.norm((rt - bpos[tail])[:, [la, 2]], axis=1), 99.9)) if len(rt) else 0.0
    al = np.abs(l)
    # stub wings: the widest part near the mast
    near = np.abs(f - hub[la] * nose_sign) < 120 * scale
    half_span = float(np.percentile(al[near], 99.9))
    tipsel = near & (al > half_span - 8 * scale)
    wing_z = float(np.percentile(z[tipsel], 99)); wing_f = float(np.median(f[tipsel]))
    # stores under the wings: lateral clusters below the wing, outboard of the fuselage
    under = near & (z < wing_z - 8 * scale) & (al > 50 * scale)
    hist, edges = np.histogram(al[under], bins=np.arange(50 * scale, half_span + 6 * scale, 4 * scale))
    stations = []
    k = 0
    while k < len(hist):
        if hist[k] > 0.04 * hist.sum():
            j = k
            while j + 1 < len(hist) and hist[j + 1] > 0.04 * hist.sum(): j += 1
            s = under & (al >= edges[k]) & (al < edges[j + 1])
            stations.append(dict(lat=float(np.median(al[s])), z=float(np.median(z[s])), front=float(np.percentile(f[s], 99.5)), back=float(np.percentile(f[s], 0.5)), n=int(s.sum())))
            k = j + 1
        else:
            k += 1
    stations.sort(key=lambda s: s['lat'])
    # chin gun: the lowest central geometry ahead of the main gear, under the forward fuselage
    fmax = float(np.percentile(f, 99.95))
    chin = (al < 8 * scale) & (z < 0.26 * (hi[2] - lo[2]) + lo[2]) & (f > 0.3 * fmax)
    cf = f[chin]; muzzle_f = float(np.percentile(cf, 99.5))
    tip = chin & (f > muzzle_f - 10 * scale)
    muzzle_z = float(np.median(z[tip])); pivot_f = float(np.median(cf))
    # cockpit: tandem seats under the canopy (the tall narrow part ahead of the mast); floor = fuselage belly + a little
    def cabin(f0, f1):
        s = (f >= f0) & (f < f1) & (al < 30 * scale)
        zz = z[s & (z > muzzle_z + 20 * scale)]
        return float(np.percentile(zz, 2)), float(np.percentile(zz, 99.5))
    out = dict(space='model space, Hammer units, origin on the ground under the mast; *_fwd = nose frame (x forward, y left, z up)')
    g_f, p_f = 0.56 * fmax, 0.30 * fmax              # gunner (front seat), pilot (rear seat, raised)
    g_lo, g_hi = cabin(g_f - 15 * scale, g_f + 15 * scale); p_lo, p_hi = cabin(p_f - 15 * scale, p_f + 15 * scale)
    seats = {}
    both(seats, 'gunner', g_f, 0, g_hi - 62 * scale); both(seats, 'pilot', p_f, 0, p_hi - 62 * scale)       # feet so the head (64 u eye) sits under the canopy top
    rider_lat = (stations[0]['lat'] + stations[-1]['lat']) / 2 if len(stations) >= 2 else half_span * 0.75
    both(seats, 'wing_left', wing_f, rider_lat, wing_z + 1 * scale); both(seats, 'wing_right', wing_f, -rider_lat, wing_z + 1 * scale)
    out['seats'] = seats
    out['seat_notes'] = ('feet positions; gunner = front seat (chin gun, own aim), pilot = rear seat; crew are inside the canopy so hide or crouch them; '
                         'wing riders stand/sit on the stub wing between the pylons facing forward')
    out['canopy_top_z'] = round(max(g_hi, p_hi), 1)
    gun = {}
    both(gun, 'muzzle', muzzle_f, 0, muzzle_z); both(gun, 'pivot', pivot_f, 0, muzzle_z + 6 * scale)
    out['gun'] = gun
    pods = []
    for s in stations:
        for sgn, side in ((1, 'left'), (-1, 'right')):
            d = dict(side=side, station='outer' if s is stations[-1] and len(stations) > 1 else 'inner', length=round(s['front'] - s['back'], 1))
            both(d, 'muzzle', s['front'], sgn * s['lat'], s['z']); pods.append(d)
    out['rocket_pods'] = pods
    out['wing'] = dict(half_span=round(half_span, 1), top_z=round(wing_z, 1))
    res = dict(nose_dir=nose_dir, nose_yaw=round(nose_yaw, 1),
               length=round(float(max(np.percentile(P[:, la] * nose_sign, 99.99), fmax) - np.percentile(P[:, la] * nose_sign, 0.01)), 1),
               body_length=round(float(hi[la] - lo[la]), 1), width=round(float(2 * half_span), 1), height=round(float(hi[2]), 1),
               rotor_radius=round(rotor_r, 1), rotor_hub=[round(float(x), 1) for x in hub], tail_rotor_hub=[round(float(x), 1) for x in bpos[tail]],
               tail_rotor_radius=round(tail_r, 1), bounds=dict(mins=[round(float(x), 1) for x in lo], maxs=[round(float(x), 1) for x in hi]),
               bounds_with_rotor=dict(mins=[round(float(x), 1) for x in np.percentile(P, 0.02, axis=0)], maxs=[round(float(x), 1) for x in np.percentile(P, 99.98, axis=0)]),
               bones=[names[k] for k in sorted(names)], lod0_tris=int(len(P) // 3))
    res.update(out)
    return res


def vmdl_info(path, scale=None):
    txt = open(path).read()
    arch = re.search(r'model_archetype\s*=\s*"([^"]*)"', txt).group(1)
    anims = re.findall(r'_class = "AnimFile"\s*name = "([^"]+)"', txt)
    hulls = re.findall(r'_class = "PhysicsHullFile"\s*name = "([^"]+)"', txt)
    lods = [float(x) for x in re.findall(r'switch_threshold = ([\d.]+)', txt)]
    if scale is not None and abs(scale - 1.0) > 1e-6:
        txt = re.sub(r'import_scale = [\d.]+', 'import_scale = %g' % scale, txt)
        open(path, 'w', newline='\n').write(txt)
    return arch, anims, hulls, lods, txt


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    out = os.path.abspath(args[0] if args else os.environ.get('MV_OUT', os.path.join(HERE, '..', 'out', 'addon')))
    scale = float(opt('--scale', 1.0))
    src = find_src(opt('--src'))
    if '--no-copy' not in argv:
        n1 = copy_tree(os.path.join(src, MODEL_REL), os.path.join(out, MODEL_REL))
        n2 = copy_tree(os.path.join(src, MAT_REL), os.path.join(out, MAT_REL))
        print('apache: copied %d model files, %d material files from %s' % (n1, n2, src))
    mdir = os.path.join(out, MODEL_REL)
    arch, anims, hulls, lods, txt = vmdl_info(os.path.join(mdir, 'apache.vmdl'), scale)
    model = MODEL_REL + '/apache.vmdl'
    if arch == 'static_prop_model':
        dyn = re.sub(r'model_archetype\s*=\s*"[^"]*"', 'model_archetype = ""', txt)
        dyn = re.sub(r'primary_associated_entity\s*=\s*"[^"]*"', 'primary_associated_entity = "prop_dynamic"', dyn)
        open(os.path.join(mdir, 'apache_dyn.vmdl'), 'w', newline='\n').write(dyn)
        model = MODEL_REL + '/apache_dyn.vmdl'
    info = dict(model=model, model_archetype=arch, prop_dynamic_ok=arch != 'static_prop_model' or model.endswith('_dyn.vmdl'), scale=scale,
                anims=anims, default_anim='idle', hulls=hulls, lod_thresholds=lods,
                materials=sorted(f for f in os.listdir(os.path.join(out, MAT_REL)) if f.endswith('.vmat')), source=src, credit=CREDIT)
    info.update(measure(mdir, scale))
    p = os.path.join(os.path.dirname(out), 'apache.json')
    json.dump(info, open(p, 'w'), indent=1)
    print('apache: %s archetype "%s" anims %s  nose %s (nose_yaw %+.0f)  length %.0f  rotor r %.0f  -> %s' %
          (model, arch, anims, info['nose_dir'], info['nose_yaw'], info['length'], info['rotor_radius'], p))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
