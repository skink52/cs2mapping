import os
import re, json, sys, subprocess, time
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
css = open(ROOT + '/out/addon/panorama/styles/custom_game/freedm.css').read()
xml = open(ROOT + '/out/addon/panorama/layout/custom_game/freedm.xml').read()
state = json.loads(sys.argv[1]); bg = sys.argv[2]; outp = sys.argv[3]
css = css.replace('file://{images}/', '../out/addon/panorama/images/')
css = re.sub(r'flow-children: right;', 'display: flex; flex-direction: row; position: absolute;', css)
css = css.replace('visibility: collapse;', 'display: none;').replace('visibility: visible;', 'display: block;')
css = re.sub(r'translatex\(', 'translateX(', css); css = re.sub(r'translatey\(', 'translateY(', css)
base = """
div { position: absolute; left: 0; top: 0; box-sizing: border-box; }
.Line > div { position: relative; flex: none; }
.Screen { left: calc(50% - 720px) !important; top: auto; bottom: 0; }
.CtrLine { left: 50%; transform: translateX(-50%); }
.SpecLine { left: 50%; transform: translateX(-50%); }
.InfLine1, .InfLine2 { left: auto; right: 0; }
"""
html = xml
html = re.sub(r'<root>.*?</styles>', '', html, flags=re.S).replace('</root>', '')
html = re.sub(r'<Panel ([^>]*?)\s*/>', r'<div \1></div>', html)
html = html.replace('<Panel ', '<div ').replace('</Panel>', '</div>')
page = f"""<!doctype html><html><head><style>body{{margin:0;width:1920px;height:1080px;overflow:hidden;background:url('{bg}') center/cover}} {base} {css}</style></head>
<body>{html}<script>
const st = {json.dumps(state)};
for (const [id, cls] of Object.entries(st)) {{ const e = document.getElementById(id); if (e) e.classList.add(...cls.split(' ')); }}
document.title='done';
</script></body></html>"""
open(ROOT + '/preview/hud.html', 'w').write(page)
from playwright.sync_api import sync_playwright
srv = subprocess.Popen(['python3', '-m', 'http.server', '8765', '-d', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport=dict(width=1920, height=1080))
        pg.goto('http://localhost:8765/preview/hud.html')
        pg.wait_for_function('document.title=="done"')
        time.sleep(0.5)
        pg.screenshot(path=outp)
        b.close()
finally:
    srv.terminate()
