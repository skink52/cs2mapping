import os
import json, sys, os, subprocess, time, math
from playwright.sync_api import sync_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
levels = {L['id']: L for L in json.load(open(ROOT + '/out/addon/_gen/levels.json'))}
def sector_at(L, x, y):
    n = len(L['n']) - 1
    child = n
    while True:
        nx, ny, dx, dy, c0, c1 = L['n'][child]
        side = 0 if (y - ny) * dx < dy * (x - nx) else 1   # 0 = front/right
        # Doom R_PointOnSide: left=dy*(x-nx), right=(y-ny)*dx; right<left -> front(0)
        child = c0 if side == 0 else c1
        if child & 0x8000:
            return L['ss'][child & 0x7fff]
def cam_for(lid, thing_index=None, tx=None, ty=None, ang=None, pitch=0, dz=41):
    L = levels[lid]
    if tx is None:
        starts = [t for t in L['t'] if t[3] == 11]
        t = starts[thing_index or 0]; tx, ty, ang = t[0], t[1], t[2]
    sec = sector_at(L, tx, ty)
    fl = L['s'][sec][0]
    o = L['off']
    return dict(x=o[0] + tx, y=o[1] + ty, z=o[2] + (fl + dz) * 1.2, yaw=ang, pitch=pitch, fov=90)
if __name__ == '__main__':
    lid = sys.argv[1]; outp = sys.argv[2]
    shots = json.loads(sys.argv[3]) if len(sys.argv) > 3 else [dict(i=0)]
    subprocess.run(['python3', '-I', ROOT + '/preview/build_scene.py', ROOT + '/out/addon', lid, ROOT + '/preview'], check=True)
    srv = subprocess.Popen(['python3', '-m', 'http.server', '8765', '-d', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            pg = b.new_page(viewport=dict(width=960, height=600))
            for k, s in enumerate(shots):
                c = cam_for(lid, s.get('i'), s.get('x'), s.get('y'), s.get('a'), s.get('p', 0), s.get('dz', 41))
                pg.goto('http://localhost:8765/preview/view.html?cam=' + json.dumps(c))
                pg.wait_for_function('document.title=="done"', timeout=120000)
                pg.screenshot(path=outp.replace('.png', '_%d.png' % k))
            b.close()
    finally:
        srv.terminate()
