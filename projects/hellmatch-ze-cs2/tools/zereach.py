"""ZE route check: which sectors a human can reach during each stage, with that stage's blocks and opened doors.

usage: zereach.py ze/<map>.json [--verbose]      exit 1 when a check fails

Walk model (Doom): a two-sided line is passable when it is not impassable (flag 1) and not blocked by the sidecar, the step
up is at most 24 and the opening at least 56 high. A door / lift sector (convert.classify_movers) counts as open when a stage
action opened it, or when a line that works it (its own manual-door line, or any special line with its tag) is not blocked and
touches a reachable sector; a blocked line has no special (as in the game: 75_ze.js setBlock). Teleport lines (39, 97) lead to
the teleport destination in their tag's sector. Keys are ignored (sidecar keys "remove": key doors open for anyone), so a key
door is shut only by a block.

Checks per stage k (state while stage k runs: blocks lifted by `until: stage:j` with j <= k or by an `unblock` in an earlier
on_done / this on_start; doors opened likewise):
  - its hold zone / boss spot / line_crossed start line is reachable (the start line with the earlier stages' doors open);
  - the next stage's hold zone is NOT reachable while stage k is a hold (a gate really gates), unless the next stage starts
    by line_crossed (then the route to its line must be open: a walk-on stage);
  - no exit line (11, 51, 52, 124, 197, 198) is reachable before the escape stage (blocked exits are fine);
  - every spawn group of the stage has a point in a sector reachable at that stage (zombies spawn behind the humans);
  - every `surge` group (on_start: reachable while the stage runs; on_done: reachable once the next stage runs) likewise.
`resupply` and `give` change no route and are accepted as they are (ze_sidecar.py checks their shape).
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets
import convert
from wad import load_map

EXITS = {11, 51, 52, 124, 197, 198}
TELEPORTS = {39, 97}


class Geo:
    """point -> subsector -> sector, and sector *pieces*: Doom maps reuse one sector number for areas that do not touch
    (MAP06's door 35 sits between two parts of sector 34), so the walk graph runs on connected pieces, not sector ids"""
    def __init__(self, m):
        self.m = m
        self.ss_sector = []
        for cnt, first in m['ssectors']:
            sg = m['segs'][first]
            ln = m['lines'][sg['line']]
            sd = ln['s1'] if sg['side'] == 0 else ln['s2']
            self.ss_sector.append(m['sides'][sd]['sector'])
        polys, _ = convert.subsector_polys(m)
        n = len(self.ss_sector)
        par = list(range(n))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]; i = par[i]
            return i
        by = {}
        for ss in range(n):
            if len(polys.get(ss, [])) >= 3: by.setdefault(self.ss_sector[ss], []).append(ss)
        for sec, sss in by.items():
            if len(sss) < 2: continue
            box = {ss: (min(p[0] for p in polys[ss]), min(p[1] for p in polys[ss]),
                        max(p[0] for p in polys[ss]), max(p[1] for p in polys[ss])) for ss in sss}
            for i, a in enumerate(sss):
                for b in sss[i + 1:]:
                    A, B = box[a], box[b]
                    if A[0] > B[2] + 1 or B[0] > A[2] + 1 or A[1] > B[3] + 1 or B[1] > A[3] + 1: continue
                    if find(a) != find(b) and shares_edge(polys[a], polys[b]): par[find(a)] = find(b)
        roots = {}
        self.ss_piece = [roots.setdefault(find(i), len(roots)) for i in range(n)]
        self.piece_sector = {}
        for ss in range(n): self.piece_sector[self.ss_piece[ss]] = self.ss_sector[ss]
        self.sector_pieces = {}
        for pc, sec in self.piece_sector.items(): self.sector_pieces.setdefault(sec, []).append(pc)

    def ss_at(self, x, y):
        nodes = self.m['nodes']
        n = len(nodes) - 1
        while not n & 0x8000:
            nx, ny, ndx, ndy = nodes[n][0:4]
            front = (y - ny) * ndx < ndy * (x - nx)    # R_PointOnSide: right < left -> side 0
            n = nodes[n][12] if front else nodes[n][13]
        return n & 0x7FFF

    def sector_at(self, x, y): return self.ss_sector[self.ss_at(x, y)]
    def piece_at(self, x, y): return self.ss_piece[self.ss_at(x, y)]

    def line_pieces(self, li):
        """(front piece, back piece) of a line (back None when one-sided)"""
        m = self.m; l = m['lines'][li]; V = m['verts']
        (x1, y1), (x2, y2) = V[l['v1']], V[l['v2']]
        dx, dy = x2 - x1, y2 - y1; ln = math.hypot(dx, dy) or 1
        nx, ny = dy / ln, -dx / ln     # the front side is on the right of v1 -> v2
        out = []
        for sd, sgn in ((l['s1'], 1), (l['s2'], -1)):
            sec = sec_of_side(m, sd); got = None
            if sec is None: out.append(None); continue
            for t in (0.5, 0.25, 0.75, 0.1, 0.9):
                for off in (1.0, 3.0):
                    pc = self.piece_at(x1 + dx * t + nx * off * sgn, y1 + dy * t + ny * off * sgn)
                    if self.piece_sector.get(pc) == sec: got = pc; break
                if got is not None: break
            if got is None: got = (self.sector_pieces.get(sec) or [None])[0]
            out.append(got)
        return out


def shares_edge(A, B):
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        ex, ey = q[0] - p[0], q[1] - p[1]; el = math.hypot(ex, ey)
        if el < 1: continue
        for j in range(len(B)):
            r, s = B[j], B[(j + 1) % len(B)]
            if abs(ex * (r[1] - p[1]) - ey * (r[0] - p[0])) / el > 0.5: continue
            if abs(ex * (s[1] - p[1]) - ey * (s[0] - p[0])) / el > 0.5: continue
            t1 = ((r[0] - p[0]) * ex + (r[1] - p[1]) * ey) / el
            t2 = ((s[0] - p[0]) * ex + (s[1] - p[1]) * ey) / el
            if min(max(t1, t2), el) - max(min(t1, t2), 0) > 1: return True
    return False


def sec_of_side(m, sd):
    return m['sides'][sd]['sector'] if sd >= 0 else None


def zone_sectors(z, geo, m):
    if not z: return set()
    if 'sector' in z: return {z['sector']}
    if 'sectors' in z: return set(z['sectors'])
    if 'box' in z:
        x1, y1, x2, y2 = z['box']; out = set()
        for i in range(9):
            for j in range(9):
                out.add(geo.sector_at(x1 + (x2 - x1) * (i + .5) / 9, y1 + (y2 - y1) * (j + .5) / 9))
        return out
    return set()


def group_sectors(g, geo):
    out = set()
    for p in g.get('points', []): out.add(geo.sector_at(p[0], p[1]))
    if 'sector' in g: out.add(g['sector'])
    out.update(g.get('sectors', []))
    return out


def reach(m, geo, starts, blocked, opened, floor_mv, ceil_mv):
    """sectors reachable from `starts` (pieces); `blocked` line ids, `opened` mover sector ids (stage actions)"""
    S = m['sectors']; L = m['lines']
    tags = {}
    for i, s in enumerate(S):
        if s['tag']: tags.setdefault(s['tag'], []).append(i)
    active = set(opened)   # movers that can be opened / lowered
    tele = {}
    for i, t in enumerate(m['things']):
        if t['type'] == 14: tele.setdefault(geo.sector_at(t['x'], t['y']), geo.piece_at(t['x'], t['y']))
    nbf = {}
    for l in L:
        a, b = sec_of_side(m, l['s1']), sec_of_side(m, l['s2'])
        if a is not None and b is not None and a != b:
            nbf[a] = min(nbf.get(a, 1e9), S[b]['floor']); nbf[b] = min(nbf.get(b, 1e9), S[a]['floor'])
    if '_lp' not in m:
        m['_lp'] = {}; m['_by_piece'] = {}
        for li, l in enumerate(L):
            if l['s1'] < 0: continue
            pcs = geo.line_pieces(li)
            m['_lp'][li] = pcs
            for pc in pcs:
                if pc is not None: m['_by_piece'].setdefault(pc, []).append(li)
    LP, BYP, PS = m['_lp'], m['_by_piece'], geo.piece_sector

    def flo(i):
        # a working floor mover can be at its lowest neighbour's floor (lifts; Doom's "raise floor" to a lower ceiling
        # snaps down, as E3M1's stair barrier does)
        return min(S[i]['floor'], nbf.get(i, S[i]['floor'])) if i in floor_mv and i in active else S[i]['floor']

    while True:
        seen = set(starts); q = list(starts)
        while q:
            px = q.pop(); x = PS[px]
            for li in BYP.get(px, []):
                if li in blocked: continue
                l = L[li]
                if l['special'] in TELEPORTS and l['tag']:
                    for ts in tags.get(l['tag'], []):
                        if ts in tele and tele[ts] not in seen: seen.add(tele[ts]); q.append(tele[ts])
                pa, pb = LP[li]
                if pa is None or pb is None or l['flags'] & 1: continue
                py = pb if pa == px else pa
                if py in seen: continue
                y = PS[py]
                fx, fy = flo(x), flo(y)
                cx = S[x]['ceil'] if x not in ceil_mv or x not in active else max(S[x]['ceil'], fx + 128)
                cy = S[y]['ceil'] if y not in ceil_mv or y not in active else max(S[y]['ceil'], fy + 128)
                if x in floor_mv and x in active: fx = max(fx, fy - 24)    # a lift rides up
                if fy - fx > 24: continue
                if min(cx, cy) - max(fx, fy) < 56: continue
                seen.add(py); q.append(py)
        # movers a reachable, unblocked special line works
        new = set()
        for li, l in enumerate(L):
            sp = l['special']
            if not sp or li in blocked or li not in LP: continue
            if not set(LP[li]) & seen: continue
            b = sec_of_side(m, l['s2'])
            if sp in convert.MANUAL_DOORS and b is not None: new.add(b)
            elif l['tag']: new.update(tags.get(l['tag'], []))
        new &= (floor_mv | ceil_mv)
        if new <= active:
            m['_last_pieces'] = seen
            return {PS[p] for p in seen}
        active |= new


def action_sectors(a, m):
    k, v = next(iter(a.items()))
    if k not in ('open_door', 'lower_lift', 'lower_floor', 'raise_floor'): return set()
    if 'tag' in v: return {i for i, s in enumerate(m['sectors']) if s['tag'] == v['tag']}
    if 'sector' in v: return {v['sector']}
    return set(v.get('sectors', []))


def main():
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    path = sys.argv[1]; verbose = '--verbose' in sys.argv
    sc = json.load(open(path, encoding='utf-8'))
    m = load_map(os.path.join(assets.FD, sc['wad']))
    geo = Geo(m)
    floor_mv, ceil_mv, _ = convert.classify_movers(m)
    starts = {geo.piece_at(t['x'], t['y']) for t in m['things'] if t['type'] in (1, 2, 3, 4)}
    blocks = sc.get('blocks', [])
    stages = sc['stages']; ids = [s['id'] for s in stages]
    groups = sc.get('spawn_groups', {})
    exits = [(li, l) for li, l in enumerate(m['lines']) if l['special'] in EXITS]
    fails = []
    unblocked, opened = set(), set()
    prev = None; prev_done_surges = []
    for k, s in enumerate(stages):
        # state while stage k runs
        for a in s.get('on_start', []) or []:
            if 'unblock' in a: unblocked.add(a['unblock'] if isinstance(a['unblock'], str) else a['unblock'].get('id'))
            opened |= action_sectors(a, m)
        blocked = set()
        for b in blocks:
            u = str(b.get('until', 'never'))
            mt = re.match(r'stage:(\d+)$', u)
            lifted = b['id'] in unblocked or (mt and int(mt.group(1)) in ids and ids.index(int(mt.group(1))) <= k)
            if not lifted: blocked |= set(b['lines'])
        seen = reach(m, geo, starts, blocked, opened, floor_mv, ceil_mv)
        tag = 'stage %d %s' % (s['id'], s.get('name', ''))
        zs = zone_sectors(s.get('zone'), geo, m)
        if zs and not zs & seen: fails.append('%s: hold zone %s not reachable' % (tag, sorted(zs)))
        if 'boss' in s:
            bs = geo.sector_at(*s['boss']['at'][:2])
            if bs not in seen: fails.append('%s: boss spot (sector %d) not reachable' % (tag, bs))
        st = s.get('start')
        if isinstance(st, dict) and 'line_crossed' in st:
            l = m['lines'][st['line_crossed']]
            if not {sec_of_side(m, l['s1']), sec_of_side(m, l['s2'])} & seen:
                fails.append('%s: start line %d not reachable' % (tag, st['line_crossed']))
        if k + 1 < len(stages) and 'hold' in s:
            nx = stages[k + 1]
            nz = zone_sectors(nx.get('zone'), geo, m)
            if nz and nz & seen and not ('line_crossed' in (nx.get('start') or {})):
                fails.append('%s: the next hold zone (stage %d, sectors %s) is already reachable: the gate leaks'
                             % (tag, nx['id'], sorted(nz & seen)))
        if not s.get('escape'):
            for li, l in exits:
                if li in blocked: continue
                if {sec_of_side(m, l['s1']), sec_of_side(m, l['s2'])} & seen:
                    fails.append('%s: exit line %d reachable before the escape' % (tag, li))
        for g in s.get('zombie_spawns', []) or []:
            if g in groups and not group_sectors(groups[g], geo) & seen:
                fails.append('%s: spawn group %s is not in a reachable sector' % (tag, g))
        for a in s.get('on_start', []) or []:
            g = (a.get('surge') or {}).get('group') if isinstance(a.get('surge'), dict) else None
            if g in groups and not group_sectors(groups[g], geo) & seen:
                fails.append('%s: on_start surge group %s is not in a reachable sector' % (tag, g))
        if prev_done_surges:
            for g in prev_done_surges:
                if g in groups and not group_sectors(groups[g], geo) & seen:
                    fails.append('%s: the previous stage on_done surge group %s is not in a reachable sector' % (tag, g))
        newly = seen - (prev or set())
        print('%s: %d sectors reachable (+%d)%s' % (tag, len(seen), len(newly), (': ' + ' '.join(map(str, sorted(newly)))) if verbose else ''))
        prev = seen
        prev_done_surges = [a['surge'].get('group') for a in s.get('on_done', []) or [] if isinstance(a.get('surge'), dict)]
        for a in s.get('on_done', []) or []:
            if 'unblock' in a: unblocked.add(a['unblock'] if isinstance(a['unblock'], str) else a['unblock'].get('id'))
            opened |= action_sectors(a, m)
    total = len(m['sectors'])
    print('route covers %d of %d sectors' % (len(prev), total))
    for f in fails: print('FAIL', f)
    print('%s: %s' % (path, 'ok' if not fails else '%d problem(s)' % len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
