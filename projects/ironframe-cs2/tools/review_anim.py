"""Animated review GIFs: every clip of every frame (legs clip + its matching upper clip, mech turning slowly), plus one contact GIF per frame.

usage: python -I tools/review_anim.py [--only key,..] [--lod 3] [--jobs N]
writes preview/review/anim/<key>_<clip>.gif (480x480, 15 fps, <3 MB) and <key>_all.gif (locomotion clips side by side),
then lists them in docs/FRAME_REVIEW.md (section 'Animation GIFs'). Same skinning (review_frames.posed) as the stride strips.
One-shot clips shorter than 1 s play in slow motion (x0.35, said in the label)."""
import glob, json, math, os, sys, time
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_frames as RF

FPS = 15; SZ = 480
ANIM = os.path.join(RF.REV, 'anim')
UP_PAIR = {'walk': 'walk_sway', 'run': 'run_sway', 'land': 'land'}
LOCO = ['walk', 'walk_back', 'strafe_l', 'strafe_r', 'run', 'hover', 'boost', 'land']


upper_clip_for, hip_offset, _curve_at = RF.upper_clip_for, RF.hip_offset, RF._curve_at


def load_parts(key, entry, lod):
    d = os.path.join(RF.OUT, 'models', 'ifr', 'frames', key)
    parts = {}
    for g in ('legs', 'upper'):
        v = entry.get(g)
        if v: parts[g] = RF.read_mesh(RF.lod_file(d, os.path.basename(v)[:-5], lod))
    clips = {}
    for g in parts:
        for c in entry.get('anims', {}).get(g, []):
            clips[(g, c)] = RF.clip_frames(os.path.join(d, 'anims', '%s_%s.smd' % (g, c)))[1]
    return parts, clips


def sample(fr, t, loop):
    ks = sorted(fr); n = len(ks)
    i = int(t * 64 + 1e-6)
    return fr[ks[i % n if loop else min(i, n - 1)]]


def render_clip(key, entry, parts, clips, lens, c, g, box):
    """frames of one clip (g = 'legs' or 'upper'), PIL images"""
    T = lens.get(c, 1.0); loop = (g, c) in clips and len(clips[(g, c)]) > 0 and c not in ('land', 'qb_l', 'qb_r', 'fire_r', 'fire_l', 'fire_s', 'stagger')
    slow = 1.0 if (loop or T >= 1.0) else 0.35
    nfr = max(4, int(math.ceil(T / slow * FPS))) + (0 if loop else 6)       # one-shots hold their last pose for 0.4 s
    other = 'upper' if g == 'legs' else 'legs'
    oc = upper_clip_for(entry, c) if g == 'legs' else 'hover'
    if (other, oc) not in clips: oc = 'idle' if other == 'upper' else 'hover'
    out = []
    for f in range(nfr):
        t = min(f / FPS * slow, T - 1e-4) if not loop else (f / nfr) * T
        meshes = []
        hoff = hip_offset(entry, c, t, T) if g == 'legs' else 0
        for gg, m in parts.items():
            cc = c if gg == g else oc
            fr = None
            if (gg, cc) in clips:
                lp = cc not in ('land', 'qb_l', 'qb_r', 'fire_r', 'fire_l', 'fire_s', 'stagger')
                tt = t if gg == g else (t if oc == c or cc in set((entry.get('sway') or {}).values()) | {'walk_sway', 'run_sway', 'land'} else t % max(0.1, lens.get(cc, 1.0)))
                fr = sample(clips[(gg, cc)], tt, lp)
            meshes.append((m, RF.posed(m, fr) + (hoff if (g == 'legs' or oc != 'hover') else 0)))
        a = math.radians(35 + 70 * f / nfr)                       # slow turn
        RF.VIEWS['anim'] = (math.cos(a), math.sin(a), 0.0)
        lab = '%s  %s/%s%s' % (key, g, c, '  slow-mo x0.35' if slow < 1 else '')
        out.append(RF.render_view(key, meshes, entry, 'anim', SZ, None, extras=False, label=lab, box=box, wfrac=1.0))
    return out


def save_gif(path, frames, fps=FPS, colors=96):
    q = [f.convert('RGB').quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=int(1000 / fps), loop=0, optimize=True, disposal=1)
    return os.path.getsize(path)


def do_frame(args):
    key, entry, lod = args
    t0 = time.time()
    parts, clips = load_parts(key, entry, lod)
    lens = entry.get('anim_len', {})
    h = entry['height']
    lo = np.array([-0.75 * h, -0.75 * h, -0.07 * h]); hi = np.array([0.75 * h, 0.75 * h, h * 1.04])
    # centre the box on the pivot so turning keeps the mech in view
    px, py = entry.get('pivot', [0, 0]); lo[:2] += [px, py]; hi[:2] += [px, py]
    made = {}
    for g in ('legs', 'upper'):
        for c in entry.get('anims', {}).get(g, []):
            if g == 'upper' and c == 'land': continue                       # shown with the legs/land GIF
            if g == 'legs' and c == 'move': continue                        # legacy alias
            fr = render_clip(key, entry, parts, clips, lens, c, g, (lo, hi))
            p = os.path.join(ANIM, '%s_%s.gif' % (key, c if g == 'legs' else 'up_' + c)) if c in entry['anims'].get('legs', []) and g == 'upper' else os.path.join(ANIM, '%s_%s.gif' % (key, c))
            sz = save_gif(p, fr)
            if sz > 2.9e6: sz = save_gif(p, fr[::2], fps=FPS // 2, colors=64)
            made[(g, c)] = (p, fr, sz)
    # contact GIF: locomotion clips side by side
    loco = [c for c in LOCO if ('legs', c) in made]
    if loco:
        cols = 4; rows = int(math.ceil(len(loco) / cols)); tw = 240
        N = int(2.0 * FPS); sheet = []
        for f in range(N):
            im = Image.new('RGB', (cols * tw, rows * tw), RF.BG)
            for i, c in enumerate(loco):
                fr = made[('legs', c)][1]; T = lens.get(c, 1.0)
                if c == 'land': idx = min(len(fr) - 1, f % (len(fr) + 4))
                else: idx = int(((f / FPS) % T) / T * len(fr)) % len(fr)
                im.paste(fr[idx].resize((tw, tw), Image.LANCZOS), ((i % cols) * tw, (i // cols) * tw))
            sheet.append(im)
        p = os.path.join(ANIM, '%s_all.gif' % key)
        sz = save_gif(p, sheet, colors=32)
        made[('all', 'all')] = (p, [], sz)
    return key, {('%s/%s' % k): (os.path.relpath(v[0], RF.PROJ).replace('\\', '/'), round(v[2] / 1e6, 2)) for k, v in made.items()}, time.time() - t0


def main():
    args = sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    lod = int(args[args.index('--lod') + 1]) if '--lod' in args else 3
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    os.makedirs(ANIM, exist_ok=True)
    fr = json.load(open(os.path.join(RF.OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
    todo = [(k, e, lod) for k, e in fr.items() if (not only or k in only) and e.get('anims', {}).get('legs') or (e.get('anims', {}).get('upper') and (not only or k in only))]
    res = {}
    with Pool(min(jobs, len(todo) or 1)) as pool:
        for key, made, secs in pool.imap_unordered(do_frame, todo):
            res[key] = made; print('%-18s %3d gifs %5.0f s  biggest %.2f MB' % (key, len(made), secs, max(v[1] for v in made.values())), flush=True)
    # merge into the index and FRAME_REVIEW.md
    ip = os.path.join(ANIM, 'index.json')
    idx = json.load(open(ip)) if os.path.exists(ip) else {}
    idx.update(res); json.dump(idx, open(ip, 'w'), indent=1)
    md = os.path.join(RF.PROJ, 'docs', 'FRAME_REVIEW.md')
    txt = open(md, encoding='utf-8').read() if os.path.exists(md) else ''
    mark = '<!-- anim-gifs -->'
    if mark in txt: txt = txt[:txt.index(mark)]
    L = [mark, '', '## Animation GIFs', '',
         'Generated by `tools/review_anim.py` (15 fps, 480x480, mech turning slowly, clip name burned in; one-shot clips under 1 s play x0.35). '
         '`<key>_all.gif` plays the locomotion clips (walk, walk_back, strafe_l, strafe_r, run, hover, boost, land) side by side; '
         'stride strips (8 poses per cycle) are on the review sheets in `preview/review/<key>.png`. '
         'The legs clips never move the pelvis: the GIFs add models.json `hip_curve` / `sway_curve` (16 samples per cycle, linear) to BOTH props, '
         'and play the upper clip named by `sway` (walk_sway, walk_back_sway, strafe_l_sway, strafe_r_sway, run_sway) with each legs clip.', '']
    for k in sorted(idx):
        L.append('- **%s**: [all locomotion](../preview/review/anim/%s_all.gif) | ' % (k, k) + ' | '.join(
            '[%s](../preview/review/anim/%s)' % (n.split('/')[1] if n.split('/')[0] == 'legs' else 'up:' + n.split('/')[1], os.path.basename(v[0]))
            for n, v in sorted(idx[k].items()) if n != 'all/all'))
    open(md, 'w', encoding='utf-8').write(txt.rstrip() + '\n\n' + '\n'.join(L) + '\n')
    print('wrote', md)


if __name__ == '__main__':
    main()
