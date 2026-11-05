"""Close-up check of a converted model's hands and wrists, where a conversion breaks first: both hands in the template's
preview pose (CS2 curls the fingers) and both wrists bent back 60 degrees (a palm under a rifle barrel), in one picture.

usage: python3 -I handcheck.py <model.mdl> <template dir> <out.png> [--fit]
       (pipeline.py writes <work>/preview/<slug>_hands.png for every model)

What to look for: fingers wrung or thrown across the palm (pivots off the fingers), the back of the hand through the
sleeve cuff, a wrist folding flat. The crops only keep triangles inside a 16 u box, so long low-poly forearm triangles can
show as slivers at the edge.
"""
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gmod2cs2 as g
from srcmdl import SrcModel
from preview import render


def check(mdl_path, template, out_png, label='', mode='rigid', choices=None):
    m = SrcModel(mdl_path)
    t = g.Template(template) if isinstance(template, str) else template
    cv = g.Converter(m, t, log=lambda s: None); cv.transforms(mode)
    meshes = m.default_meshes(choices)
    used, remap, V, N, W = cv.convert_mesh(meshes)
    UV = m.UV[used]
    faces = np.vstack([remap[me['tris']] for me in meshes if len(me['tris'])])
    tex = np.full((4, 4, 3), 200, np.uint8)
    base = os.path.splitext(out_png)[0]
    pics = []
    def crop(P, centre, r=8):
        return [(faces[np.all(np.abs(P[faces] - centre).max(2) < r, axis=1)], tex)]
    Wp = t.preview_pose()
    Q = np.zeros_like(V)
    for i, w in enumerate(W):
        tot = sum(x for _, x in w) or 1
        for j, x in w:
            Rb, tb = t.W[j]; Rp, tp = Wp[j]
            Q[i] += x / tot * (Rp @ (Rb.T @ (V[i] - tb)) + tp)
    for s in 'LR':
        hp = Wp['hand_' + s][1]
        p = '%s_p%s.png' % (base, s); pics.append(p)
        render(Q, UV, crop(Q, hp), p, views=('front', 'three'), H=360, box=(hp - 8, hp + 8), label='%s hand_%s, CS2 preview pose' % (label, s))
    for s in 'LR':
        h = t.J('hand_' + s); u = g.unit(h - t.J('arm_lower_' + s))
        lat = t.J('finger_index_0_' + s) - t.J('finger_pinky_0_' + s)
        Rb = g.rot_axis(g.unit(np.cross(u, lat)) * (1 if s == 'L' else -1), np.radians(-60))
        sub = {n for n in t.joints if n.startswith('hand_' + s) or ('finger' in n and n.endswith('_' + s))}
        B = np.array([sum(x / (sum(y for _, y in w) or 1) * ((Rb @ (V[i] - h) + h) if j in sub else V[i]) for j, x in w) for i, w in enumerate(W)])
        p = '%s_w%s.png' % (base, s); pics.append(p)
        render(B, UV, crop(B, h), p, views=('front', 'side'), H=360, box=(h - 8, h + 8), label='%s wrist_%s bent back 60' % (label, s))
    ims = [Image.open(p) for p in pics]
    sheet = Image.new('RGB', (ims[0].width + ims[2].width, 720), (46, 50, 58))
    for k, (x, y) in enumerate(((0, 0), (0, 360), (ims[0].width, 0), (ims[0].width, 360))): sheet.paste(ims[k], (x, y))
    sheet.save(out_png)
    for p in pics: os.remove(p)
    return getattr(cv, 'hand_scale', None)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    print(check(a[0], a[1], a[2], os.path.basename(a[0]), 'fit' if '--fit' in sys.argv else 'rigid'))
