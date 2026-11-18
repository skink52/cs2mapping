"""Loading slides drawn from the map itself (the original IRONFRAME style, skink52 preferred it over the poster art):
cinematic views of the current .vmap's arena under the arena's own sky, with distance haze and the title.
usage: python -I tools/map_slides.py <map.vmap> <addon out> <map name> [title] [x0,y0,z0,x1,y1,z1]
       python -I tools/map_slides.py --pixel <addon out> <map name> <title> <low-res render1.png> <render2> [...]   chunky 3D (default)
       python -I tools/map_slides.py --shots <addon out> <map name> <title> <shot1.png|jpg> <shot2> [...]   frames in-game screenshots (best)
Writes panorama/images/map_icons/screenshots/1080p/<map>.png, _1.png ... (via create/loading.py write_slides).
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'create'))
import vmap_preview as VP
import vmapedit as V
import importlib.util
_s = importlib.util.spec_from_file_location('cs2_loading', os.path.join(ROOT, 'create', 'loading.py'))
L = importlib.util.module_from_spec(_s); _s.loader.exec_module(L)

W, H, SS = 1920, 1080, 2          # supersampled 2x for clean edges


def sky_backdrop(addon, yaw):
    """the arena's equirect sky, the slice the camera looks at"""
    p = os.path.join(addon, 'materials', 'ifr', 'sky', 'sky_dunes_color.png')
    if not os.path.exists(p):
        g = Image.new('RGB', (W * SS, H * SS)); d = ImageDraw.Draw(g)
        for y in range(H * SS):
            t = y / (H * SS); d.line((0, y, W * SS, y), fill=(int(40 + 160 * t), int(30 + 70 * t), int(70 + 40 * t)))
        return g
    sky = Image.open(p).convert('RGB'); sw, sh = sky.size
    cx = int(((-yaw / 360.0) % 1.0) * sw); span = sw // 4
    strip = Image.new('RGB', (span, sh // 2))
    for i in range(2):
        strip.paste(sky.crop((0, sh // 4, sw, sh // 4 + sh // 2)), (-(cx - span // 2) + i * sw, 0))
    return strip.resize((W * SS, H * SS), Image.BICUBIC)


def render_view(polys, cam, look, base, haze, fov=62):
    img = base.copy(); d = ImageDraw.Draw(img)
    w, h = img.size
    cam = np.array(cam, float); look = np.array(look, float)
    f = look - cam; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.]); r /= np.linalg.norm(r); u = np.cross(r, f)
    k = (w / 2) / math.tan(math.radians(fov) / 2)
    sun = np.array([0.55, -0.35, 0.45]); sun /= np.linalg.norm(sun)
    items = []
    for loop, col in polys:
        v = loop - cam; z = v @ f
        if (z < 5).any(): continue
        n = np.cross(loop[1] - loop[0], loop[2] - loop[0]); nl = np.linalg.norm(n)
        if nl == 0: continue
        n /= nl
        if (cam - loop[0]) @ n < 0: continue
        P = np.stack([w / 2 + (v @ r) * k / z, h / 2 - (v @ u) * k / z], -1)
        if (P[:, 0].max() < 0) or (P[:, 0].min() > w) or (P[:, 1].max() < 0) or (P[:, 1].min() > h): continue
        lit = 0.32 + 0.68 * max(0.0, n @ sun) + 0.12 * max(0.0, n[2])
        warm = np.array([1.05, 0.93, 0.82])                         # dusk light
        c = np.clip(np.array(col, float) * lit * warm, 0, 255)
        fog = min(0.85, (z.mean() / 16000.0) ** 1.3)                # distance haze toward the horizon colour
        c = c * (1 - fog) + np.array(haze, float) * fog
        items.append((z.mean(), [tuple(p) for p in P], tuple(int(x) for x in c)))
    for _, P, c in sorted(items, key=lambda t: -t[0]):
        d.polygon(P, fill=c)
    return img


def grade(img):
    img = img.resize((W, H), Image.LANCZOS)
    glow = img.filter(ImageFilter.GaussianBlur(18))
    a = np.asarray(img, float); g = np.asarray(glow, float)
    a = a + 0.18 * np.clip(g - 150, 0, None)                         # a little bloom on bright parts
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.38 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.4
    a = a * vig[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def title_on(img, title, sub):
    d = ImageDraw.Draw(img)
    f1, f2 = L.font(64), L.font(26)
    x, y = 96, 128
    d.text((x + 3, y + 3), title, font=f1, fill=(0, 0, 0))
    d.text((x, y), title, font=f1, fill=(235, 240, 255))
    d.line((x, y + 84, x + 520, y + 84), fill=(90, 200, 255), width=3)
    if sub: d.text((x, y + 96), sub, font=f2, fill=(200, 210, 230))
    return img


# 18 Nov 2026 (skink52): "no need for the second line too, just ironframe: dunes": framed shots carry the title only (IF_SLIDE_SUBS=1 for the old lines)
SUBS = ['Hold the canyon', 'Every ridge is cover', 'Boost, dodge, lock on', '64 pilots, one arena', 'Break their stagger', 'Upgrade in the hangar']
def shots(a):
    addon, mapname, title, files = a[0], a[1], a[2], a[3:]
    if len(files) < 2: sys.exit('give at least 2 screenshots')
    out = []
    for i, f in enumerate(files[:10]):
        img = L.cover(Image.open(f).convert('RGB'))
        img = title_on(grade(img.resize((W * SS, H * SS))), title.upper(), SUBS[i % len(SUBS)] if os.environ.get('IF_SLIDE_SUBS') == '1' else '')
        out.append(img)
    L.write_slides(addon, mapname, out)
    print('map_slides: %d framed screenshots for %s' % (len(out), mapname))

# 18 Nov 2026 (skink52: "keep font more consistent with gameplay font ... basic tooltips that don't read like AI"): the HUD's Cinzel
# (create/fonts/Cinzel-Variable.ttf, Bold) with its soft glow, gold key names as on the help card, one keys line per slide
TIPS = [[('SHIFT', 1), (' BOOST     ', 0), ('CTRL', 1), (' QUICK BOOST     ', 0), ('SPACE', 1), (' HOVER', 0)],
        [('MOUSE 1 / 2', 1), (' ARMS     ', 0), ('R / E', 1), (' SHOULDERS     ', 0), ('F', 1), (' NEXT TARGET', 0)],
        [('MISSILES TRACK ONCE THE BRACKET IS RED', 0)],
        [('!GARAGE', 1), (' CHANGE YOUR MECH     ', 0), ('F3', 1), (' CHAT IN THE MECH', 0)]]
TXT, GOLD = (242, 246, 250), (255, 210, 90)


def hud_font(sz):
    from PIL import ImageFont
    f = ImageFont.truetype(os.path.join(ROOT, 'create', 'fonts', 'Cinzel-Variable.ttf'), sz)
    try: f.set_variation_by_name('Bold')
    except Exception: pass
    return f


def glow_text(im, xy, parts, f, glow=6):
    """parts [(text, gold?)] in a row, each with the HUD's dark halo and a faint glow of its own colour"""
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); x, y = xy
    for t, g in parts:
        d.text((x, y), t, font=f, fill=(GOLD if g else TXT) + (255,)); x += d.textlength(t, font=f)
    a = lay.split()[3]
    halo = Image.new('RGBA', im.size, (0, 0, 0, 255)); halo.putalpha(a.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: min(255, v * 2)))
    soft = lay.filter(ImageFilter.GaussianBlur(glow * 1.5)); soft.putalpha(soft.split()[3].point(lambda v: v // 2))
    base = im.convert('RGBA'); base.alpha_composite(halo); base.alpha_composite(soft); base.alpha_composite(lay)
    return base.convert('RGB')


def pixel_shot(low, title, tip=None, colours=40):
    """18 Nov 2026 (skink52: "updated versions of that same style" (the very first screen: chunky 3D), "views like you took in the most
    recent version, but with a pixely type of vibe ... the skybox visible"): a low-res Cycles render (480x270, tools/arenas/sprawl_preview_bl.py,
    so depth and props are right) blown up x4 nearest-neighbour, a reduced palette, the first screen's shade, the title and a keys line"""
    import loading as LL
    im = low.convert('RGB')
    im = im.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
    im = im.resize((W, H), Image.NEAREST)
    im = LL.shade(im, top=0.3, bottom=0.45)
    im = glow_text(im, (80, 52), [(title.upper(), 0)], hud_font(96))
    if tip: im = glow_text(im, (84, H - 110), tip, hud_font(40), glow=4)
    return im


def pixel_shots(a):
    """--pixel <addon> <map> <title> <low1.png> <low2> ...: pixel_shot each, write the slides"""
    addon, mapname, title, files = a[0], a[1], a[2], a[3:]
    n = int(os.environ.get('IF_SLIDE_COLOURS', '128' if 'sprawl' in mapname else '40'))   # neon needs more colours than dusk sand
    out = [pixel_shot(Image.open(f), title, None, n) for f in files[:10]]   # skink52 18 Nov: "remove tooltips" (TIPS kept, unused)
    L.write_slides(addon, mapname, out)
    print('map_slides: %d pixel shots for %s' % (len(out), mapname))


def pixel_views(polys, addon, haze, c, ext, ground):
    """4 low-res (480x270) renders: polygons drawn 2x supersampled then box-filtered down (soft edges quantise cleanly)"""
    global W, H
    sw, sh = W, H; W, H = 960, 540
    shots = [((0.42, -0.46), 0.05, 0.0), ((-0.44, 0.40), 0.07, 0.0), ((0.48, 0.30), 0.04, -0.05), ((-0.30, -0.55), 0.22, -0.12)]
    out = []
    try:
        for (sx, sy), up, dz in shots:
            cam = [c[0] + sx * ext, c[1] + sy * ext, ground + 380 + up * ext]
            look = [c[0] - sx * ext * 0.15, c[1] - sy * ext * 0.15, ground + 300 + dz * ext]
            yaw = math.degrees(math.atan2(look[1] - cam[1], look[0] - cam[0]))
            base = sky_backdrop(addon, yaw)
            img = render_view(polys, cam, look, base, haze).resize((480, 270), Image.BOX)
            a = np.asarray(img, float); yy, xx = np.mgrid[0:270, 0:480]       # light vignette, then a punch of contrast
            vig = 1 - 0.30 * (((xx - 240) / 240.0) ** 2 + ((yy - 135) / 135.0) ** 2) ** 1.3
            a = np.clip((a * vig[..., None] - 110) * 1.12 + 110, 0, 255)
            out.append(Image.fromarray(a.astype(np.uint8)))
    finally:
        W, H = sw, sh
    return out


def main(a):
    if a and a[0] == '--shots': return shots(a[1:])
    if a and a[0] == '--pixel': return pixel_shots(a[1:])
    if len(a) < 3: sys.exit(__doc__)
    src, addon, mapname = a[0], a[1], a[2]
    title = a[3] if len(a) > 3 else 'IRONFRAME: DUNES'
    box = None
    if len(a) > 4:
        b = [float(x) for x in a[4].split(',')]; box = (b[:3], b[3:])
    m = V.Map(src)
    polys = VP.polygons(m, box)
    if not polys: sys.exit('no meshes in the box')
    allp = np.vstack([p for p, _ in polys]); lo, hi = np.percentile(allp, 1, 0), np.percentile(allp, 99, 0)
    c = (lo + hi) / 2; ext = float(max(hi - lo)) or 1.0
    ground = float(np.percentile(allp[:, 2], 30))
    haze = (176, 120, 132)
    # four cinematic cameras: low over the edge looking across the arena, and one high establishing shot
    cams = [((0.42, -0.46), 0.05, 0.0, 'Hold the canyon'), ((-0.44, 0.40), 0.07, 0.0, 'Every ridge is cover'),
             ((0.48, 0.30), 0.04, -0.05, 'Boost, dodge, lock on'), ((-0.30, -0.55), 0.22, -0.12, '64 pilots, one arena')]
    if os.environ.get('IF_SLIDES', 'pixel') == 'pixel':
        import pixel_slides as PS
        arena = title.split(':')[-1].strip().upper() or 'DUNES'
        slides = PS.build(pixel_views(polys, addon, haze, c, ext, ground), arena)
        L.write_slides(addon, mapname, slides)
        PS.workshop_icon().save(os.path.join(HERE, '..', 'preview', 'workshop_icon.png'))
        print('map_slides: %d pixel slides + workshop_icon.png for %s' % (len(slides), mapname)); return
    out = []
    for i, ((sx, sy), up, dz, sub) in enumerate(cams):
        cam = [c[0] + sx * ext, c[1] + sy * ext, ground + 380 + up * ext]
        look = [c[0] - sx * ext * 0.15, c[1] - sy * ext * 0.15, ground + 300 + dz * ext]
        yaw = math.degrees(math.atan2(look[1] - cam[1], look[0] - cam[0]))
        base = sky_backdrop(addon, yaw)
        img = render_view(polys, cam, look, base, haze)
        img = grade(img)
        img = title_on(img, title, sub)
        p = os.path.join(addon, '_gen', 'slide_%d.png' % i); img.save(p); out.append(p)
        print('slide', i, 'from', [int(x) for x in cam])
    L.write_slides(addon, mapname, [Image.open(p) for p in out])
    print('map_slides: %d slides for %s' % (len(out), mapname))


if __name__ == '__main__':
    main(sys.argv[1:])
