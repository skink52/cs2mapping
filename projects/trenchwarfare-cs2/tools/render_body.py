"""Before / after render of a player body DMX on a red background, so every crack or hole in the skin shows as red specks
(remaster step 14, tw_de_a re-weld). Bind pose, textures from the vmats, fixed sun; front, back, 3/4 and close-ups of the shoulders/collar.

usage: python tools/render_body.py <before_body.dmx> <after_body.dmx> <out.png>
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tw_models as T          # noqa: E402


def sheet(dmx, label, roots):
    from PIL import Image, ImageDraw
    tris = T.dmx_tris(dmx)
    sc = T.Scene(roots); sc.tris = tris
    P = np.array([v[:3] for _, vs in tris for v in vs]); lo, hi = P.min(0), P.max(0)
    c = (lo + hi) / 2; r = float(np.linalg.norm(hi - lo)) / 2
    shots = [(c, r, 0, 8), (c, r, 180, 8), (c, r, 40, 15),
             (np.array([c[0], c[1], hi[2] - 14]), r * 0.32, 25, 20), (np.array([c[0], c[1], hi[2] - 14]), r * 0.32, 205, 20)]
    ims = []
    for cc, rr, az, el in shots:
        a, b = math.radians(az), math.radians(el)
        eye = cc + 2.5 * rr * np.array([math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b)])
        ims.append(sc.render(eye=tuple(eye), at=tuple(cc), size=(420, 520), fov=40, bg=(255, 0, 0)))
    W = Image.new('RGB', (420, 520 * len(ims)))
    for i, im in enumerate(ims): W.paste(im, (0, i * 520))
    d = ImageDraw.Draw(W); d.rectangle((0, 0, 420, 18), fill=(20, 20, 20)); d.text((4, 3), '%s  %d tris' % (label, len(tris)), fill=(255, 255, 255))
    return W


def main(a):
    from PIL import Image
    roots = [os.path.join(T.PROJ, 'out', 'step14', 'addon'), T.STAGE, T.CONTENT]
    L = sheet(a[0], 'BEFORE (deployed)', roots); R = sheet(a[1], 'AFTER (re-welded GLB)', roots)
    S = Image.new('RGB', (L.size[0] + R.size[0], L.size[1])); S.paste(L, (0, 0)); S.paste(R, (L.size[0], 0))
    S.save(a[2]); print(a[2])


if __name__ == '__main__':
    main(sys.argv[1:])
