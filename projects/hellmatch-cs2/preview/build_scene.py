"""Builds a preview scene for one level from the generated SMD/vmdl/vmat files (as CS2 would load them)."""
import json, os, re, sys, struct
ADDON = sys.argv[1]; LEVEL = sys.argv[2]; OUT = sys.argv[3]
props = [p for p in json.load(open(os.path.join(ADDON, '_gen/props.json'))) if p['level'] == LEVEL]
def vmat(path):
    t = open(os.path.join(ADDON, path)).read()
    col = re.search(r'TextureColor "([^"]+)"', t).group(1)
    tr = re.search(r'TextureTranslucency "([^"]+)"', t)
    tint = [float(x) for x in re.search(r'g_vColorTint "\[([^\]]+)\]"', t).group(1).split()[:3]]
    sc = re.search(r'g_vTexCoordScrollSpeed "\[([^\]]+)\]"', t)
    return dict(color=col, trans=tr.group(1) if tr else None, tint=tint)
groups = {}
for p in props:
    vm = open(os.path.join(ADDON, p['model'])).read()
    remap = dict(re.findall(r'from = "([^"]+)\.vmat"\s*to = "([^"]+)"', vm))
    smd = os.path.join(ADDON, p['model'].replace('.vmdl', '.smd'))
    lines = open(smd).read().split('\n')
    i = lines.index('triangles') + 1
    ox, oy, oz = p['origin']
    while i < len(lines) and lines[i] != 'end':
        mat = lines[i]
        g = groups.setdefault(remap[mat], [])
        for k in range(3):
            f = lines[i + 1 + k].split()
            a, b, c = float(f[1]), float(f[2]), float(f[3])
            x, y = -b, a     # ModelDoc's 90 degree turn
            g += [x + ox, y + oy, c + oz, float(f[7]), 1 - float(f[8])]
        i += 4
THINGS = os.environ.get('THINGS')
if THINGS:
    import math
    T = json.load(open(THINGS))
    off = T['off']
    for t in T['things']:
        mp = os.path.join(ADDON, 'models/fdm/spr/%s.vmdl' % t['k'])
        if not os.path.exists(mp): continue
        vm = open(mp).read()
        remap = dict(re.findall(r'from = "([^"]+)\.vmat"\s*to = "([^"]+)"', vm))
        lines = open(mp.replace('.vmdl', '.smd')).read().split('\n')
        i = lines.index('triangles') + 1
        yaw = math.radians(t['a'] if t['k'][:4] in ('play', 'misl') else 0)
        ca, sa = math.cos(yaw), math.sin(yaw)
        while i < len(lines) and lines[i] != 'end':
            mat = lines[i]
            mpath = remap.get(mat, list(remap.values())[0])
            if t.get('s'): mpath = mpath.replace('pal/pal0.vmat', 'pal/pal%d.vmat' % t['s'])
            g = groups.setdefault(mpath, [])
            for kk in range(3):
                f = lines[i + 1 + kk].split()
                a, b, c = float(f[1]), float(f[2]), float(f[3])
                x, y = -b, a
                xr, yr = x * ca - y * sa, x * sa + y * ca
                g += [off[0] + t['x'] + xr, off[1] + t['y'] + yr, off[2] + t['z'] * 1.2 + c, float(f[7]), 1 - float(f[8])]
            i += 4
mats = []
blob = bytearray()
for path, data in groups.items():
    m = vmat(path); m['offset'] = len(blob) // 4; m['count'] = len(data) // 5
    blob += struct.pack('<%df' % len(data), *data); mats.append(m)
open(os.path.join(OUT, 'scene.bin'), 'wb').write(blob)
json.dump(dict(mats=mats), open(os.path.join(OUT, 'scene.json'), 'w'))
print('groups', len(mats), 'floats', len(blob) // 4)
