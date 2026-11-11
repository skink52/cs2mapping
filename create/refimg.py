"""Reference pictures: rectify a facade photo and read floors / windows / colours off it, put a photo beside a game frame, lay an aerial
picture under a plan of the ground. Everything it reports is a suggestion to check by eye, never a verdict.

  python refimg.py facade <photo> <out_dir> [--quad x,y;x,y;x,y;x,y] [--width 512]     corners TL;TR;BR;BL in pixels; width in units
  python refimg.py compare <reference> <game frame> <out.png>
  python refimg.py pairs <out.png> <photo1> <frame1> [<photo2> <frame2> ...]               up to 24 numbered rows
  python refimg.py plan <height.png> <out.png> [--image aerial.jpg] [--marks "A,x,y,yaw;B,x,y"] [--grid 1024]
Library: rectify(), facade(), compare(), pairs(), plan(field, ...), palette().

Ported from reference.py (reference_facade, reference_compare, reference_pairs, reference_plan) and the quad rectification of
textures.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT). Fresh code; numpy + Pillow only. Different from theirs:
plan() draws a terrain_img height Field (hillshade) instead of the map's mesh tops, and nothing is cached or pruned.
"""
import argparse, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAX_PIXELS = 32_000_000


def _open(path):
    if not isinstance(path, str) or not os.path.isfile(path): raise ValueError('not a local image file: %r' % (path,))
    im = Image.open(path)
    if im.width * im.height > MAX_PIXELS: raise ValueError('image exceeds 32 megapixels')
    return im.convert('RGB')


def rectify(im, quad):
    """the part of the photo inside quad (TL, TR, BR, BL pixel corners, convex) pulled square: a facade seen at an angle becomes flat"""
    q = np.asarray(quad, float)
    if q.shape != (4, 2) or not np.isfinite(q).all() or (q < 0).any() or (q[:, 0] > im.width).any() or (q[:, 1] > im.height).any():
        raise ValueError('quad needs four in-image corners: TL, TR, BR, BL')
    e = [q[(i + 1) % 4] - q[i] for i in range(4)]
    if not all(e[i][0] * e[(i + 1) % 4][1] - e[i][1] * e[(i + 1) % 4][0] > 1 for i in range(4)):
        raise ValueError('quad must be convex and ordered TL, TR, BR, BL')
    w = int(round(max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3])))); h = int(round(max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1]))))
    w = max(w, 8); h = max(h, 8)
    dst = [(0, 0), (w, 0), (w, h), (0, h)]
    A = []; b = []
    for (x, y), (u, v) in zip(dst, q):            # PIL wants the map from output (x, y) to source (u, v)
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    coeff = np.linalg.solve(np.array(A, float), np.array(b, float))
    return im.transform((w, h), Image.Transform.PERSPECTIVE, tuple(coeff), Image.Resampling.BICUBIC)


def palette(im, colors=5):
    """[{'color': '#rrggbb', 'share': 0..1}] main colours, biggest first"""
    small = im.convert('RGB').resize((128, 128)).quantize(colors=colors).convert('RGB')
    cols = sorted(small.getcolors(128 * 128), reverse=True)
    return [{'color': '#%02x%02x%02x' % rgb, 'share': round(n / 16384.0, 3)} for n, rgb in cols]


def _runs(profile, threshold, minwidth):
    m = profile > threshold
    d = np.diff(np.r_[False, m, False].astype(int))
    return [(int(a), int(b)) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if b - a >= minwidth]


def _smooth(v):
    k = max(3, len(v) // 80)
    return np.convolve(v, np.ones(k) / k, mode='same')


def facade(image, out_dir, quad=None, real_width=None):
    """Rectified facade + a clean wall crop (for matkit.from_image) + guesses: floors and window columns from the dark bands, palette,
    height from real_width. Shadows, plants and arches fool the guesses: 'needs_visual_review' is always True."""
    im = _open(image)
    if real_width is not None and not 32 <= float(real_width) <= 8192: raise ValueError('real_width must be 32..8192 units')
    if quad is not None: im = rectify(im, quad)
    im.thumbnail((1600, 1600))
    os.makedirs(out_dir, exist_ok=True)
    rect_path = os.path.join(out_dir, 'facade_rectified.png'); im.save(rect_path)
    g = np.asarray(im, float).mean(axis=2); hh, ww = g.shape
    dx = np.abs(np.diff(g, axis=1, prepend=g[:, :1])); dy = np.abs(np.diff(g, axis=0, prepend=g[:1]))
    dark = g < np.percentile(g, 28)                     # windows are the dark, busy parts
    rows = dark.mean(axis=1); cols = dark.mean(axis=0)
    rr = [(a, b) for a, b in _runs(_smooth(rows), max(0.15, rows.mean() + 0.035), max(5, hh // 50)) if a > hh * 0.04 and b < hh * 0.96 and b - a < hh * 0.35]
    cr = [(a, b) for a, b in _runs(_smooth(cols), max(0.15, cols.mean() + 0.035), max(5, ww // 80)) if a > ww * 0.03 and b < ww * 0.97 and b - a < ww * 0.4]
    pw, ph = max(8, ww // 8), max(8, hh // 8); best = None      # the calmest bright patch = bare wall
    for y in range(0, max(1, hh - ph + 1), max(1, ph // 2)):
        for x in range(0, max(1, ww - pw + 1), max(1, pw // 2)):
            score = float((dx[y:y + ph, x:x + pw] + dy[y:y + ph, x:x + pw]).mean() + dark[y:y + ph, x:x + pw].mean() * 50)
            if best is None or score < best[0]: best = (score, [x, y, x + pw, y + ph])
    crop_path = os.path.join(out_dir, 'facade_wall_crop.png'); im.crop(tuple(best[1])).save(crop_path)
    out = {'rectified': rect_path, 'size': list(im.size), 'wall_crop': crop_path, 'wall_region': best[1], 'palette': palette(im),
           'estimated_floors': min(6, len(rr)) or None, 'estimated_columns': min(8, len(cr)) or None,
           'window_positions': [round((a + b) / (2.0 * ww), 3) for a, b in cr[:8]],
           'rows': [list(r) for r in rr], 'columns': [list(c) for c in cr],
           'real_width': real_width, 'estimated_height': round(real_width * hh / ww, 1) if real_width else None,
           'needs_visual_review': True}
    with open(os.path.join(out_dir, 'facade.json'), 'w') as f: json.dump(out, f, indent=1)
    return out


def _fit(im, h): return im.resize((max(1, round(im.width * h / im.height)), h), Image.Resampling.LANCZOS)


def compare(reference, shot, out_png):
    """REFERENCE | OUR SHOT side by side at one height: open it and name the differences"""
    ims = [_open(reference), _open(shot)]
    h = min(1000, max(im.height for im in ims)); ims = [_fit(im, h) for im in ims]
    out = Image.new('RGB', (ims[0].width + ims[1].width + 8, h + 32), '#202020')
    d = ImageDraw.Draw(out); d.text((8, 8), 'REFERENCE', fill='white'); d.text((ims[0].width + 16, 8), 'OUR SHOT', fill='white')
    out.paste(ims[0], (0, 32)); out.paste(ims[1], (ims[0].width + 8, 32)); out.save(out_png)
    return {'comparison': out_png, 'size': list(out.size), 'needs_visual_review': True}


def pairs(items, out_png, row_height=360):
    """numbered rows of photo | game frame for a set of photos of one place"""
    if not 1 <= len(items) <= 24: raise ValueError('1..24 [photo, frame] pairs')
    rows = []
    for i, (photo, frame) in enumerate(items, 1):
        a, b = _fit(_open(photo), row_height), _fit(_open(frame), row_height)
        row = Image.new('RGB', (a.width + b.width + 48, row_height + 8), '#202020')
        ImageDraw.Draw(row).text((8, 8), str(i), fill='white'); row.paste(a, (40, 4)); row.paste(b, (48 + a.width, 4)); rows.append(row)
    out = Image.new('RGB', (max(r.width for r in rows), sum(r.height for r in rows) + 28), '#202020')
    d = ImageDraw.Draw(out); d.text((40, 8), 'PHOTO', fill='white'); d.text((48 + rows[0].width // 2, 8), 'GAME', fill='white')
    y = 28
    for r in rows: out.paste(r, (0, y)); y += r.height
    out.save(out_png)
    return {'comparison': out_png, 'size': list(out.size), 'pairs': len(rows), 'needs_visual_review': True}


def plan(field, out_png, image=None, marks=(), points=(), grid=None, size=1600, blend=0.55):
    """The ground from above, north up: the Field's hillshade, an aerial picture or sketch blended under it (stretched to the Field's
    bounds), a grid in units, points [(x, y)] as dots and marks [(label, x, y[, yaw])] with view arrows (yaw 0 = +x, 90 = +y)."""
    import terrain_img as TI
    x0, y0, x1, y1 = field.bounds
    k = size / max(x1 - x0, y1 - y0); w, h = max(1, round((x1 - x0) * k)), max(1, round((y1 - y0) * k))
    px = lambda x, y: ((x - x0) * k, h - (y - y0) * k)
    out = Image.fromarray(TI.hillshade(field.Z, field.cell, tint=image is None)).resize((w, h), Image.Resampling.BICUBIC)
    if image: out = Image.blend(out, _open(image).resize((w, h), Image.Resampling.LANCZOS), blend)
    d = ImageDraw.Draw(out)
    grid = float(grid or 10 ** math.floor(math.log10(max(x1 - x0, y1 - y0) / 4)))
    gx = math.ceil(x0 / grid) * grid
    while gx <= x1:
        d.line([px(gx, y0), px(gx, y1)], fill=(70, 120, 170), width=1); d.text((px(gx, y0)[0] + 2, h - 12), '%.0f' % gx, fill=(160, 200, 240)); gx += grid
    gy = math.ceil(y0 / grid) * grid
    while gy <= y1:
        d.line([px(x0, gy), px(x1, gy)], fill=(70, 120, 170), width=1); d.text((2, px(x0, gy)[1] - 12), '%.0f' % gy, fill=(160, 200, 240)); gy += grid
    for p in points:
        cx, cy = px(p[0], p[1]); d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(230, 200, 60))
    if len(marks) > 64: raise ValueError('up to 64 marks')
    for m in marks:
        cx, cy = px(float(m[1]), float(m[2]))
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], outline=(255, 70, 60), width=3)
        if len(m) > 3:
            a = math.radians(float(m[3])); d.line([cx, cy, cx + math.cos(a) * 40, cy - math.sin(a) * 40], fill=(255, 70, 60), width=3)
        d.text((cx + 9, cy - 16), str(m[0])[:24], fill='white')
    out.save(out_png)
    return {'plan': out_png, 'size': [w, h], 'units_per_px': round(1 / k, 3), 'grid': grid, 'needs_visual_review': True}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('facade'); f.add_argument('photo'); f.add_argument('out_dir'); f.add_argument('--quad'); f.add_argument('--width', type=float)
    c = sub.add_parser('compare'); c.add_argument('reference'); c.add_argument('shot'); c.add_argument('out')
    p = sub.add_parser('pairs'); p.add_argument('out'); p.add_argument('images', nargs='+')
    l = sub.add_parser('plan'); l.add_argument('height'); l.add_argument('out'); l.add_argument('--image'); l.add_argument('--marks'); l.add_argument('--grid', type=float)
    a = ap.parse_args(argv)
    if a.cmd == 'facade':
        quad = [[float(v) for v in c.split(',')] for c in a.quad.split(';')] if a.quad else None
        res = facade(a.photo, a.out_dir, quad, a.width)
    elif a.cmd == 'compare': res = compare(a.reference, a.shot, a.out)
    elif a.cmd == 'pairs':
        if len(a.images) % 2: ap.error('pairs needs photo / frame pairs')
        res = pairs(list(zip(a.images[0::2], a.images[1::2])), a.out)
    else:
        import terrain_img as TI
        marks = [m.split(',') for m in a.marks.split(';')] if a.marks else []
        res = plan(TI.Field.load(a.height), a.out, a.image, marks, grid=a.grid)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
