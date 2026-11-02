import os
import json, os, re, sys, struct, subprocess, time, math
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); ADDON = ROOT + '/out/addon'
models = sys.argv[1].split(',')
cams = json.loads(sys.argv[2])
outp = sys.argv[3]
def vmat(path):
    t = open(os.path.join(ADDON, path)).read()
    col = re.search(r'TextureColor "([^"]+)"', t).group(1)
    tr = re.search(r'TextureTranslucency "([^"]+)"', t)
    tint = [float(x) for x in re.search(r'g_vColorTint "\[([^\]]+)\]"', t).group(1).split()[:3]]
    return dict(color=col, trans=tr.group(1) if tr else None, tint=tint)
groups = {}
for k, m in enumerate(models):
    vm = open(f'{ADDON}/models/fdm/spr/{m}.vmdl').read()
    remap = dict(re.findall(r'from = "([^"]+)\.vmat"\s*to = "([^"]+)"', vm))
    lines = open(f'{ADDON}/models/fdm/spr/{m}.smd').read().split('\n')
    i = lines.index('triangles') + 1
    ox = (k % 8) * 70; oy = (k // 8) * 90
    while i < len(lines) and lines[i] != 'end':
        mat = lines[i]
        g = groups.setdefault(remap.get(mat, list(remap.values())[0]), [])
        for kk in range(3):
            f = lines[i + 1 + kk].split()
            a, b, c = float(f[1]), float(f[2]), float(f[3])
            g += [-b + oy, a + ox, c, float(f[7]), 1 - float(f[8])]
        i += 4
mats = []; blob = bytearray()
for path, data in groups.items():
    m = vmat(path); m['offset'] = len(blob) // 4; m['count'] = len(data) // 5
    blob += struct.pack('<%df' % len(data), *data); mats.append(m)
open(ROOT + '/preview/scene.bin', 'wb').write(blob)
json.dump(dict(mats=mats), open(ROOT + '/preview/scene.json', 'w'))
from playwright.sync_api import sync_playwright
srv = subprocess.Popen(['python3', '-m', 'http.server', '8765', '-d', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = b.new_page(viewport=dict(width=960, height=600))
        for n, c in enumerate(cams):
            c.setdefault('fov', 60); c['fog'] = 1e9
            pg.goto('http://localhost:8765/preview/view.html?cam=' + json.dumps(c))
            pg.wait_for_function('document.title=="done"', timeout=120000)
            pg.screenshot(path=outp.replace('.png', '_%d.png' % n))
        b.close()
finally:
    srv.terminate()
