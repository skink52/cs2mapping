"""Renders camera shots of the converted map with view.html in headless Chromium.

usage: python3 preview/shot.py <out_prefix> '<json list of {x,y,z,yaw,pitch,fov}>' [width height]
Run preview/scene.py first (it writes preview/build/scene.*).
"""
import os, sys, json, time, subprocess
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
prefix = sys.argv[1]; shots = json.loads(sys.argv[2])
W, H = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (960, 600)
srv = subprocess.Popen(['python3', '-m', 'http.server', '8771', '-d', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = b.new_page(viewport=dict(width=W, height=H))
        for k, c in enumerate(shots):
            pg.goto('http://localhost:8771/preview/view.html?scene=build/&cam=' + json.dumps(c))
            pg.wait_for_function('document.title=="done"', timeout=300000)
            pg.screenshot(path='%s_%d.png' % (prefix, k))
        b.close()
finally:
    srv.terminate()
