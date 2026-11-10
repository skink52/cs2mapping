"""Close-up stills of one frame in one locomotion clip: legs clip + its paired upper clip (+ hip curve when models.json has it).
usage: python -I tools/review_close.py key clip tfrac[,tfrac..] [--views front,side] [--size 520] [--out file.png] [--lod 1] [--box lowhalf|all|upper]
tfrac = fraction of the cycle. One row per tfrac, one column per view."""
import json, math, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_frames as RF, review_anim as RA


def render(key, clip, tfrac, views, size, lod, box, upper_clip=None):
    fr = json.load(open(os.path.join(RF.OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
    entry = fr[key]
    parts, clips = RA.load_parts(key, entry, lod)
    lens = entry.get('anim_len', {})
    h = entry['height']; px, py = entry.get('pivot', [0, 0])
    if box == 'lowhalf': lo = np.array([-0.45 * h + px, -0.45 * h + py, -0.02 * h]); hi = np.array([0.45 * h + px, 0.45 * h + py, 0.62 * h])
    elif box == 'upper': lo = np.array([-0.5 * h + px, -0.5 * h + py, 0.35 * h]); hi = np.array([0.5 * h + px, 0.5 * h + py, 1.02 * h])
    else: lo = np.array([-0.6 * h + px, -0.6 * h + py, -0.04 * h]); hi = np.array([0.6 * h + px, 0.6 * h + py, 1.04 * h])
    T = lens.get(clip, 1.0)
    uc = upper_clip or RA.upper_clip_for(entry, clip)
    tiles = []
    for tf in tfrac:
        row = []
        t = tf * T
        off = RA.hip_offset(entry, clip, t, T)
        meshes = []
        for g, m in parts.items():
            cc = clip if g == 'legs' else uc
            frm = None
            if (g, cc) in clips:
                tt = t if g == 'legs' else (t % max(0.05, lens.get(cc, T)))
                frm = RA.sample(clips[(g, cc)], tt, True)
            P = RF.posed(m, frm)
            if g != 'x': P = P + off
            meshes.append((m, P))
        for v in views:
            RF.VIEWS['c'] = {'front': (1, 0, 0.), 'three': (0.87, 0.5, 0.), 'side': (0, 1, 0.), 'back': (-1, 0, 0.), 'three2': (0.87, -0.5, 0.)}[v]
            row.append(RF.render_view(key, meshes, entry, 'c', size, None, extras=False, label='%s %s/%s t=%.2f %s' % (key, clip, uc, tf, v), box=(lo, hi), wfrac=1.0))
        tiles.append(row)
    W = sum(i.width for i in tiles[0]); H = sum(r[0].height for r in tiles)
    im = Image.new('RGB', (W, H)); y = 0
    for r in tiles:
        x = 0
        for t in r: im.paste(t, (x, y)); x += t.width
        y += r[0].height
    return im


if __name__ == '__main__':
    a = sys.argv[1:]
    key, clip = a[0], a[1]; tf = [float(x) for x in a[2].split(',')]
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    im = render(key, clip, tf, opt('--views', 'front,side').split(','), int(opt('--size', 520)), int(opt('--lod', 1)), opt('--box', 'lowhalf'), opt('--upper', None))
    out = opt('--out', os.path.join(RF.REV, 'close_%s_%s.png' % (key, clip)))
    if '--bright' in a or True: im = Image.fromarray(np.clip(np.asarray(im).astype(np.float32) * 1.0 + 0, 0, 255).astype(np.uint8))
    im.save(out); print(out, im.size)
