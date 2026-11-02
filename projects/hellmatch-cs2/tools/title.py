"""Our own title art for the loading screens and the Workshop images: the game's name (names.TITLE) drawn in the
in-game HUD font (Freedoom's STCFN, the font the HUD messages use) with a fire gradient, outline, shadow and glow,
and the level renders in ref/art (made with preview/view.html) with Freedoom's sky behind them.
Freedoom's own logos are not used anywhere."""
import os
import numpy as np
from PIL import Image, ImageFilter
import assets, names

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ref/art')
FIRE = ((255, 244, 170), (255, 170, 40), (215, 60, 12), (120, 12, 5))

def glyph_row(text):
    """The text in the HUD font at 1:1, RGBA, 8 pixels tall (glyphs placed like the HUD places them)."""
    gl = [assets.graphic('STCFN%03d' % ord(c)) if 33 <= ord(c) <= 95 else None for c in text.upper()]
    W = sum(4 if g is None else g[0].shape[1] for g in gl)
    img = np.zeros((8, max(1, W), 4), np.uint8)
    x = 0
    for g in gl:
        if g is None: x += 4; continue
        a, (lo, to) = g
        h, w = a.shape[:2]
        img[max(0, -to):max(0, -to) + h, x:x + w] = a[:8]
        x += w
    return img

def hud_text(text, scale, tint=(235, 235, 235), shadow=True):
    """Plain text in the HUD font, tinted, scaled with crisp pixels (same look as the loading-screen text)."""
    g = glyph_row(text).astype(np.float32)
    lum = g[..., :3].max(2, keepdims=True) / 255.0
    g[..., :3] = lum * np.array(tint, np.float32)
    im = Image.fromarray(g.clip(0, 255).astype(np.uint8), 'RGBA').resize((g.shape[1] * scale, 8 * scale), Image.NEAREST)
    if not shadow: return im
    out = Image.new('RGBA', (im.width + scale, im.height + scale), (0, 0, 0, 0))
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); sh.putalpha(im.getchannel('A'))
    out.alpha_composite(sh, (scale, scale)); out.alpha_composite(im)
    return out

def logo(width):
    """The game's name in the HUD font with a fire gradient, dark outline, shadow and glow, about `width` wide."""
    g = glyph_row(names.TITLE)
    lit = (g[..., 3] > 0) & (g[..., :3].max(2) >= 100)          # the font's bright strokes (not its dark rim)
    m = np.pad(lit, 2)
    edge = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            edge |= np.roll(np.roll(m, dy, 0), dx, 1)
    H, W = m.shape
    ys = np.where(m.any(1))[0]; y0, y1 = ys[0], ys[-1]
    stops = np.array(FIRE, np.float32)
    rows = np.zeros((H, 3), np.float32)
    for y in range(H):
        t = np.clip((y - y0) / max(1, y1 - y0), 0, 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2); f = t - i
        rows[y] = stops[i] * (1 - f) + stops[i + 1] * f
    rgba = np.zeros((H, W, 4), np.float32)
    rgba[..., :3] = np.where(m[..., None], rows[:, None, :], np.array((14, 4, 2), np.float32))
    rgba[..., 3] = edge * 255
    S = max(2, round(width / W))
    big = Image.fromarray(rgba.astype(np.uint8), 'RGBA').resize((W * S, H * S), Image.NEAREST)
    pad = 6 * S
    canvas = Image.new('RGBA', (big.width + pad * 2, big.height + pad * 2), (0, 0, 0, 0))
    a = Image.new('L', canvas.size, 0); a.paste(big.getchannel('A'), (pad, pad))
    glow = a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(S * 2.2))
    gl = Image.new('RGBA', canvas.size, (255, 80, 10, 0)); gl.putalpha(glow.point(lambda v: min(255, int(v * 0.9))))
    canvas.alpha_composite(gl)
    sh = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); sh.putalpha(a.point(lambda v: int(v * 0.7)))
    canvas.alpha_composite(sh, (S, S))
    canvas.alpha_composite(big, (pad, pad))
    return canvas.crop(canvas.getbbox())

def scene(name, sky_path):
    """A level render (ref/art/render_<name>.png, sky drawn as magenta) with Freedoom's sky put in."""
    r = np.array(Image.open(os.path.join(ART, 'render_%s.png' % name)).convert('RGB')).astype(np.int32)
    H, W = r.shape[:2]
    sky = Image.open(sky_path).convert('RGB')
    band = sky.crop((0, int(sky.height * 0.22), sky.width // 2, sky.height // 2)).resize((W, H // 2 + 1), Image.LANCZOS)
    band = np.array(band)
    mask = (r[..., 0] > 200) & (r[..., 1] < 60) & (r[..., 2] > 200)
    out = r.copy()
    yy, xx = np.nonzero(mask)
    out[yy, xx] = band[np.minimum(yy, band.shape[0] - 1), xx]
    return Image.fromarray(out.astype(np.uint8))
