"""Top-down preview of a Freedoom level (and its ZE sidecar) as a PNG, for picking maps and authoring sidecars.

usage: zepreview.py <level> [--ze ze/<level>.json] [--size 1800] [--labels] [--crop x0,y0,x1,y1] [--out preview/<name>.png]

Sectors are filled by floor height (dark = low); one-sided lines white, steps grey, door lines yellow, lift/floor lines
cyan, exit lines magenta, key doors in their key colour; tags in yellow. Things: player starts 1-4 green (numbered),
hard-skill monsters red (others dim), keys as coloured squares, the rest small grey dots.
--labels writes sector numbers (white) and special line numbers (yellow); --crop zooms to a Doom-unit box.
--ze overlays the sidecar: hold zones per stage (translucent, labelled), blocks (thick red), spawn groups (orange), boss.
"""
import argparse, json, math, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets
from wad import load_map
import convert

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = {5: (60, 90, 255), 40: (60, 90, 255), 6: (255, 220, 40), 39: (255, 220, 40), 13: (255, 40, 40), 38: (255, 40, 40)}
KEY_DOORS = {26: 5, 32: 5, 99: 5, 133: 5, 134: 13, 135: 13, 28: 13, 33: 13, 27: 6, 34: 6, 136: 6, 137: 6}
EXITS = {11, 51, 52, 124, 197, 198}
MONSTERS = {3004, 9, 65, 3001, 3002, 58, 3006, 3005, 69, 3003, 66, 67, 68, 71, 64, 16, 7, 84}
BOSSY = {3003, 69, 16, 7, 64, 67, 68}
STAGE_COL = [(80, 200, 255), (120, 255, 120), (255, 120, 255), (255, 200, 60), (255, 255, 255)]


def font(sz):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try: return ImageFont.truetype(f, sz)
        except OSError: pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('level'); ap.add_argument('--ze'); ap.add_argument('--size', type=int, default=1800)
    ap.add_argument('--labels', action='store_true'); ap.add_argument('--crop'); ap.add_argument('--out')
    a = ap.parse_args()
    lv = a.level.lower()
    m = load_map(os.path.join(assets.FD, 'levels', lv + '.wad'))
    V = m['verts']; S = m['sectors']; L = m['lines']
    xs = [v[0] for v in V]; ys = [v[1] for v in V]
    bb = [min(xs) - 64, min(ys) - 64, max(xs) + 64, max(ys) + 64]
    if a.crop: bb = [float(c) for c in a.crop.split(',')]
    sc = a.size / max(bb[2] - bb[0], bb[3] - bb[1])
    W, H = int((bb[2] - bb[0]) * sc) + 1, int((bb[3] - bb[1]) * sc) + 1
    P = lambda x, y: ((x - bb[0]) * sc, (bb[3] - y) * sc)
    img = Image.new('RGB', (W, H), (12, 12, 16)); d = ImageDraw.Draw(img, 'RGBA')
    f_small, f_big = font(max(10, int(a.size / 160))), font(max(14, int(a.size / 70)))
    fmin = min(s['floor'] for s in S); fmax = max(s['floor'] for s in S) or 1
    polys, ss_sector = convert.subsector_polys(m)
    floor_mv, ceil_mv, _ = convert.classify_movers(m)
    cen = {}
    for ss, p in polys.items():
        if len(p) < 3: continue
        sec = ss_sector[ss]; s = S[sec]
        t = (s['floor'] - fmin) / max(1, fmax - fmin)
        c = int(35 + 120 * t)
        col = (c, c, int(c * 1.1))
        if s['special'] in (5, 7, 16, 4, 11): col = (int(c * 1.4), int(c * 0.7), int(c * 0.4))   # damaging floor
        if sec in floor_mv: col = (int(c * 0.6), int(c * 1.2), int(c * 1.3))
        if sec in ceil_mv and s['ceil'] - s['floor'] <= 8: col = (int(c * 1.3), int(c * 1.2), int(c * 0.5))  # closed door
        d.polygon([P(x, y) for x, y in p], fill=col)
        cx = sum(q[0] for q in p) / len(p); cy = sum(q[1] for q in p) / len(p)
        ar = abs(convert.area2(p))
        if sec not in cen or ar > cen[sec][2]: cen[sec] = (cx, cy, ar)
    for i, l in enumerate(L):
        x1, y1 = V[l['v1']]; x2, y2 = V[l['v2']]
        sp = l['special']; w = 1; col = (110, 110, 120)
        if l['s2'] < 0: col = (235, 235, 235); w = 2
        elif S[m['sides'][l['s1']]['sector']]['floor'] != S[m['sides'][l['s2']]['sector']]['floor']: col = (150, 150, 160)
        if sp:
            w = 3
            if sp in EXITS: col = (255, 0, 255)
            elif sp in KEY_DOORS: col = KEYS[KEY_DOORS[sp]]
            elif sp in convert.MANUAL_DOORS or sp in convert.DOOR_TAG or sp in convert.CEIL_TAG: col = (255, 220, 0)
            elif sp in convert.LIFT_TAG or sp in convert.FLOOR_TAG or sp in convert.STAIRS: col = (0, 230, 230)
            elif sp in (39, 97, 125, 126): col = (60, 255, 60)   # teleporters
            else: col = (255, 140, 0)
        d.line([P(x1, y1), P(x2, y2)], fill=col, width=w)
        if sp and (a.labels or l['tag']):
            mx, my = P((x1 + x2) / 2, (y1 + y2) / 2)
            txt = ('L%d' % i if a.labels else '') + (' t%d' % l['tag'] if l['tag'] else '') + (' s%d' % sp if a.labels else '')
            d.text((mx + 3, my + 3), txt.strip(), fill=(255, 255, 0), font=f_small)
    if a.labels:
        for sec, (cx, cy, _) in cen.items():
            x, y = P(cx, cy)
            d.text((x - 6, y - 6), str(sec), fill=(255, 255, 255, 200), font=f_small)
    for ti, t in enumerate(m['things']):
        x, y = P(t['x'], t['y']); ty = t['type']; r = max(2, 10 * sc)
        if 1 <= ty <= 4:
            d.ellipse([x - r * 2, y - r * 2, x + r * 2, y + r * 2], fill=(0, 255, 0))
            d.text((x + r * 2, y - r * 2), str(ty), fill=(0, 255, 0), font=f_big)
            ang = math.radians(t['angle'])
            d.line([x, y, x + math.cos(ang) * r * 5, y - math.sin(ang) * r * 5], fill=(0, 255, 0), width=2)
        elif ty in KEYS:
            d.rectangle([x - r * 2.5, y - r * 2.5, x + r * 2.5, y + r * 2.5], fill=KEYS[ty], outline=(255, 255, 255))
        elif ty in MONSTERS:
            hard = t['flags'] & 4 and not t['flags'] & 16
            rr = r * (2.2 if ty in BOSSY else 1.3)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 40, 40, 255 if hard else 90))
        elif ty in (11, 2, 3):
            pass
        else:
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(150, 150, 150))
        if a.labels and (ty in MONSTERS or ty in KEYS or 1 <= ty <= 4):
            d.text((x + 4, y), 'T%d' % ti, fill=(255, 160, 160), font=f_small)
    if a.ze:
        ze = json.load(open(a.ze, encoding='utf-8'))
        overlay(d, ze, m, polys, ss_sector, P, sc, f_big)
    out = a.out or os.path.join(ROOT, 'preview', lv + ('_ze' if a.ze else '') + ('_labels' if a.labels else '') + '.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print(out, W, H)


def zone_polys(z, polys, ss_sector):
    secs = [z['sector']] if 'sector' in z else z.get('sectors', [])
    if secs:
        return [p for ss, p in polys.items() if len(p) >= 3 and ss_sector[ss] in secs]
    if 'box' in z:
        x1, y1, x2, y2 = z['box']; return [[(x1, y1), (x2, y1), (x2, y2), (x1, y2)]]
    return []


def overlay(d, ze, m, polys, ss_sector, P, sc, fb):
    V = m['verts']
    for b in ze.get('blocks', []):
        for i in b['lines']:
            l = m['lines'][i]
            (x1, y1), (x2, y2) = V[l['v1']], V[l['v2']]
            d.line([P(x1, y1), P(x2, y2)], fill=(255, 0, 0), width=7)
        l = m['lines'][b['lines'][0]]
        x, y = P(*V[l['v1']]); d.text((x + 6, y - 22), 'X ' + b['id'] + ' (' + str(b.get('until', '')) + ')', fill=(255, 80, 80), font=fb)
    for k, s in enumerate(ze.get('stages', [])):
        col = STAGE_COL[k % len(STAGE_COL)]
        for z in [s.get('zone')] if s.get('zone') else []:
            ps = zone_polys(z, polys, ss_sector)
            for p in ps: d.polygon([P(x, y) for x, y in p], fill=col + (110,), outline=col + (255,))
            if ps:
                allp = [q for p in ps for q in p]
                cx = sum(q[0] for q in allp) / len(allp); cy = sum(q[1] for q in allp) / len(allp)
                x, y = P(cx, cy)
                d.text((x - 40, y - 10), '%d %s %ss' % (s['id'], s.get('name', ''), s.get('hold', '')), fill=col, font=fb, stroke_width=2, stroke_fill=(0, 0, 0))
        st = s.get('start')
        if isinstance(st, dict) and 'line_crossed' in st:
            l = m['lines'][st['line_crossed']]; (x1, y1), (x2, y2) = V[l['v1']], V[l['v2']]
            d.line([P(x1, y1), P(x2, y2)], fill=col, width=6)
            x, y = P(x1, y1); d.text((x, y + 6), 'start %d' % s['id'], fill=col, font=fb, stroke_width=2, stroke_fill=(0, 0, 0))
        if 'boss' in s:
            bx, by = s['boss']['at'][:2]; x, y = P(bx, by); r = 40 * sc + 6
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 255), width=4)
            d.text((x + r, y - r), 'BOSS ' + s['boss'].get('type', ''), fill=(255, 0, 255), font=fb, stroke_width=2, stroke_fill=(0, 0, 0))
    for gid, g in ze.get('spawn_groups', {}).items():
        pts = [tuple(p[:2]) for p in g.get('points', [])]
        secs = [g['sector']] if 'sector' in g else g.get('sectors', [])
        for p in [p for ss, p in polys.items() if len(p) >= 3 and ss_sector[ss] in secs]:
            d.polygon([P(x, y) for x, y in p], fill=(255, 140, 0, 70))
            pts.append((sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p)))
        for x0, y0 in pts:
            x, y = P(x0, y0); r = (g.get('radius', 64)) * sc + 3
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 140, 0), width=3)
        if pts:
            x, y = P(*pts[0]); d.text((x + 8, y + 8), 'Z ' + gid, fill=(255, 160, 40), font=fb, stroke_width=2, stroke_fill=(0, 0, 0))


if __name__ == '__main__':
    main()
