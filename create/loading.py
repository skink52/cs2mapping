"""loading.py: CS2 loading-screen slides, radar (overview) file, map icon and Workshop pictures.

Where CS2 looks (content paths; CS2 asks for the compiled names in brackets):
  panorama/images/map_icons/screenshots/1080p/<map>.png, <map>_1.png ... <map>_9.png   slides  (<map>_png, <map>_1_png ...)
  panorama/images/overheadmaps/<map>_radar.psd                                          radar   (<map>_radar_psd)
  panorama/images/map_icons/map_icon_<map>.svg                                          icon    (map_icon_<map>.vsvg)
  resource/overviews/<map>.txt   where the radar sits in the world (this one goes in the GAME addon folder)
None of these needs a .vtex: they compile because the HUD css refers to them (panorama.Hud.preload()).

The slideshow (panorama/scripts/loadingscreen.vts) shows the slides 4 s each from a random one, and shows nothing of
yours when there is only one, so `slides` insists on at least 2. A slide is scaled to cover the screen: a 4:3 screen
loses 240 px each side and 21:9 crops top and bottom (keep content in y 128-952). CS2 draws its own column on the
right (300 px wide, 20 px from the edge, the slide blurred behind it) and the loading bar. `overlay` sketches all that.

usage:
  loading.py slides <addon_out> <map> img1 img2 [...] [--css-check]   slide pictures (any size; cover-scaled to
                      1920x1080). Deletes stale <map>*.png slides first. --css-check: fail if the HUD css doesn't
                      reference every slide (raise the preload count)
  loading.py overlay <slide.png> <out.png>       the slide with CS2's column, loading bar and 4:3 / 21:9 edges drawn on
  loading.py radar <addon_out> <map> <image> <minx> <miny> <maxx> <maxy> [--game <game_out>]
                      the image is the top-down picture of that world box (it is fitted into a 1024 square radar);
                      writes the PSD and resource/overviews/<map>.txt (into --game if given, else addon_out)
  loading.py overview <out_dir> <map> <minx> <miny> <maxx> <maxy> [size_px]   only the overview txt
  loading.py icon <addon_out> <map> [svg path data]   a white 64x64 map icon (default: a simple diamond)
  loading.py workshop <in.png> <out.jpg> [WxH]   a Workshop picture (default 1920x1080; 1080x1080 for the thumbnail),
                      lightly shaded at the top / bottom, saved as a JPEG under 1 MB (.png: PNG, shrunk if needed)

From space-racer-cs2/tools/loading.py and hellmatch-cs2/tools/loading.py + workshop_art.py (MIT), made project-neutral.
"""
import os, re, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
SLIDE_DIR = 'panorama/images/map_icons/screenshots/1080p'
FONT_CANDIDATES = ['/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                   '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf']


def font(sz):
    for p in FONT_CANDIDATES:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    try: return ImageFont.load_default(sz)
    except TypeError: return ImageFont.load_default()


def cover(img, w=W, h=H):
    """scale to cover w x h and crop the middle (what CS2 does with a slide)"""
    img = img.convert('RGB')
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, int(round(img.width * s))), max(h, int(round(img.height * s)))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


# ---------------------------------------------------------------- slides
def write_slides(addon_out, map_name, images, css_check=False):
    """images: PIL images or paths. Deletes every old <map>*.png slide, writes <map>.png, <map>_1.png ...
    Returns the file names."""
    if len(images) < 2: raise SystemExit('CS2 shows none of your slides when there is only one: give at least 2')
    if len(images) > 10: raise SystemExit('CS2 looks for <map>.png and <map>_1 .. _9 only: give at most 10')
    names = [map_name + ('_%d' % n if n else '') + '.png' for n in range(len(images))]
    if css_check:
        css = ''
        cdir = os.path.join(addon_out, 'panorama/styles/custom_game')
        for f in (os.listdir(cdir) if os.path.isdir(cdir) else []):
            if f.endswith('.css'): css += open(os.path.join(cdir, f), encoding='utf-8').read()
        missing = [n for n in names if 'screenshots/1080p/' + n not in css]
        if missing: raise SystemExit('slides the HUD css does not preload (raise the preload slide count): %s' % missing)
    path = os.path.join(addon_out, SLIDE_DIR); os.makedirs(path, exist_ok=True)
    rx = re.compile(r'^%s(_\d+)?\.png$' % re.escape(map_name))
    for f in os.listdir(path):                       # no stale extra slides from an older build
        if rx.match(f): os.remove(os.path.join(path, f))
    for name, im in zip(names, images):
        im = Image.open(im) if isinstance(im, str) else im
        cover(im).save(os.path.join(path, name), optimize=True)
    return names


def cs2_overlay(img):
    """the slide as CS2 shows it at 16:9 (its column and loading bar sketched in), plus where 4:3 and 21:9 cut"""
    im = cover(img) if isinstance(img, Image.Image) else cover(Image.open(img))
    d = ImageDraw.Draw(im, 'RGBA')
    def text(xy, s, sz, fill, anchor='la'):
        d.text(xy, s, font=font(sz), fill=fill, anchor=anchor, stroke_width=3, stroke_fill=(0, 0, 0))
    d.rectangle([1600, 50, 1899, 1059], fill=(0, 0, 0, 150), outline=(255, 255, 255, 120))
    text((1750, 120), 'CS2: MAP NAME', 22, (230, 230, 230), 'mm')
    text((1750, 150), 'ICON, MODE', 18, (200, 200, 200), 'mm')
    d.rectangle([1620, 1020, 1879, 1027], fill=(30, 150, 210, 230))
    text((1622, 996), 'LOADING...', 18, (200, 200, 200))
    for x in (240, 1680):
        d.line([(x, 0), (x, 1079)], fill=(255, 80, 80, 220), width=3)
    text((246, 1048), '4:3 edge', 20, (255, 120, 120))
    d.line([(1360, 0), (1360, 1079)], fill=(255, 160, 60, 160), width=2)
    text((1366, 1048), "4:3: CS2's column from here", 18, (255, 170, 80))
    for y in (128, 952):
        d.line([(0, y), (1919, y)], fill=(80, 200, 255, 200), width=3)
    text((8, 132), '21:9 edge', 20, (120, 210, 255))
    return im


# ---------------------------------------------------------------- radar
def write_psd(path, img):
    """flat 8-bit RGB Photoshop file (3 channels, planar raw data, no layers): what CS2's compiler reads for *_radar_psd"""
    arr = np.array(img.convert('RGB')); h, w = arr.shape[:2]
    with open(path, 'wb') as f:
        f.write(b'8BPS' + struct.pack('>H6xHIIHH', 1, 3, h, w, 8, 3))
        f.write(struct.pack('>I', 0))     # colour mode data
        f.write(struct.pack('>I', 0))     # image resources
        f.write(struct.pack('>I', 0))     # layer and mask info
        f.write(struct.pack('>H', 0))     # raw image data, planar
        for c in range(3): f.write(arr[..., c].tobytes())


def radar_frame(minx, miny, maxx, maxy, size_px=1024):
    """square radar frame round a world box: (pos_x, pos_y, scale) = top-left world corner and units per pixel"""
    size = max(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return cx - size / 2, cy + size / 2, size / size_px


def write_overview(out_dir, map_name, pos_x, pos_y, scale, material=None):
    """resource/overviews/<map>.txt. `material` defaults to overviews/<map> as Space Racer and Hellmatch write it
    (the porting side's tools/radar.py writes overviews/<map>_radar; which one CS2 needs is not confirmed)"""
    ov = os.path.join(out_dir, 'resource/overviews'); os.makedirs(ov, exist_ok=True)
    p = os.path.join(ov, map_name + '.txt')
    open(p, 'w', newline='\n').write(
        '"%s"\n{\n\t"material"\t"%s"\n\t"pos_x"\t"%d"\n\t"pos_y"\t"%d"\n\t"scale"\t"%.3f"\n\t"rotate"\t"0"\n\t"zoom"\t"1.0"\n}\n'
        % (map_name, material or 'overviews/' + map_name, round(pos_x), round(pos_y), scale))
    return p


def write_radar(addon_out, map_name, img, box, game_out=None, size_px=1024):
    """img: a top-down picture of the world box (minx, miny, maxx, maxy), north up; it is fitted into a square
    size_px radar (black border) so pos/scale match. Writes the PSD and the overview txt."""
    minx, miny, maxx, maxy = box
    pos_x, pos_y, scale = radar_frame(minx, miny, maxx, maxy, size_px)
    img = Image.open(img) if isinstance(img, str) else img
    canvas = Image.new('RGB', (size_px, size_px), (0, 0, 0))
    pw, ph = int(round((maxx - minx) / scale)), int(round((maxy - miny) / scale))
    canvas.paste(img.convert('RGB').resize((max(1, pw), max(1, ph)), Image.LANCZOS),
                 (int(round((minx - pos_x) / scale)), int(round((pos_y - maxy) / scale))))
    path = os.path.join(addon_out, 'panorama/images/overheadmaps'); os.makedirs(path, exist_ok=True)
    write_psd(os.path.join(path, map_name + '_radar.psd'), canvas)
    write_overview(game_out or addon_out, map_name, pos_x, pos_y, scale)
    return pos_x, pos_y, scale


# ---------------------------------------------------------------- map icon
DIAMOND = 'M32 4 L60 32 L32 60 L4 32 Z M32 16 L48 32 L32 48 L16 32 Z'


def write_icon(addon_out, map_name, path_data=DIAMOND):
    """white 64x64 SVG icon like the stock map icons (fill-rule evenodd, so inner shapes cut holes)"""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
           '<path fill="#ffffff" fill-rule="evenodd" d="%s"/></svg>\n' % path_data)
    d = os.path.join(addon_out, 'panorama/images/map_icons'); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, 'map_icon_%s.svg' % map_name)
    open(p, 'w', newline='\n').write(svg)
    return p


# ---------------------------------------------------------------- Workshop pictures
def shade(img, top=0.5, top_h=0.4, bottom=0.5, bottom_h=0.25, vignette=0.35):
    """darken the top and bottom bands and the corners (room for a title / text over a busy picture)"""
    a = np.array(img.convert('RGB')).astype(np.float32)
    h, w = a.shape[:2]
    y = np.arange(h)[:, None]
    k = np.ones((h, 1), np.float32)
    k -= top * np.clip(1 - y / (h * top_h), 0, 1)
    k -= bottom * np.clip((y - h * (1 - bottom_h)) / (h * bottom_h), 0, 1)
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - vignette * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    a *= np.clip(k, 0, 1)[..., None] * v[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def save_under_1mb(img, path, limit=1000000):
    """Workshop pictures must be under 1 MB: JPEG at falling quality, or PNG (palette-reduced, then shrunk) by extension"""
    img = img.convert('RGB')
    if path.lower().endswith('.png'):
        im = img
        for step in range(8):
            im.save(path, optimize=True)
            if os.path.getsize(path) < limit: break
            im = img.quantize(256 >> min(step, 3)) if step < 4 else im.resize((im.width * 7 // 8, im.height * 7 // 8), Image.LANCZOS)
    else:
        for q in (92, 88, 84, 80, 75, 70, 60, 50):
            img.save(path, 'JPEG', quality=q, optimize=True)
            if os.path.getsize(path) < limit: break
    size = os.path.getsize(path)
    if size >= limit: raise SystemExit('%s is still %d bytes' % (path, size))
    return size


def main(a):
    if not a: sys.exit(__doc__)
    cmd = a[0]
    if cmd == 'slides' and len(a) >= 4:
        imgs = [x for x in a[3:] if not x.startswith('--')]
        names = write_slides(a[1], a[2], imgs, '--css-check' in a)
        print('loading screen: %d slides (%s)' % (len(names), ' '.join(names)))
    elif cmd == 'overlay' and len(a) == 3:
        cs2_overlay(a[1]).save(a[2]); print('overlay ->', a[2])
    elif cmd == 'radar' and len(a) >= 8:
        game = a[a.index('--game') + 1] if '--game' in a else None
        p = write_radar(a[1], a[2], a[3], [float(v) for v in a[4:8]], game)
        print('radar: pos %.0f, %.0f, scale %.3f' % p)
    elif cmd == 'overview' and len(a) >= 7:
        px_ = int(a[7]) if len(a) > 7 else 1024
        f = radar_frame(*[float(v) for v in a[3:7]], size_px=px_)
        print('overview ->', write_overview(a[1], a[2], *f))
    elif cmd == 'icon' and len(a) >= 3:
        print('icon ->', write_icon(a[1], a[2], a[3] if len(a) > 3 else DIAMOND))
    elif cmd == 'workshop' and len(a) >= 3:
        w, h = (int(v) for v in (a[3] if len(a) > 3 else '1920x1080').split('x'))
        n = save_under_1mb(shade(cover(Image.open(a[1]), w, h)), a[2])
        print('workshop picture %dx%d -> %s (%d KB)' % (w, h, a[2], n // 1024))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
