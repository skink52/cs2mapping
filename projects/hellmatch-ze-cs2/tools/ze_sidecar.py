"""ZE sidecar loader + validator (format: projects/hellmatch-cs2/docs/ZE_DESIGN.md section 3).

usage: ze_sidecar.py <ze/map.json> [...]      validate (exit 1 on any error), print a summary
       import ze_sidecar; ze_sidecar.load(path, wad_path, map)   -> the validated object (raises SystemExit on errors)

Indices are WAD indices (lines, sectors, things). Every tag an action moves must belong to sectors the converter gives a
mover model (doors / ceilings -> ceiling movers, lifts / floors -> floor movers), or the game would have nothing to move.
Extension to the design format: door/lift actions may name `{"sector": i}` or `{"sectors": [..]}` instead of a tag, for
manual (untagged) doors such as key doors; the same mover check applies.
"""
import hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CEIL_ACTIONS = {'open_door', 'close_door'}
FLOOR_ACTIONS = {'lower_lift', 'raise_floor', 'lower_floor'}
OTHER_ACTIONS = {'message', 'spawn_group', 'teleport_zombies', 'unblock', 'music', 'score', 'block'}
START_KINDS = {'line_crossed', 'stage_done', 'use_line', 'zone_entered'}


def monster_names():
    """monster keys the game knows (src/core/00_a_monsters.js, read only)"""
    p = os.path.join(ROOT, 'src/core/00_a_monsters.js')
    try:
        src = open(p, encoding='utf-8').read()
    except OSError:
        return None
    return set(re.findall(r"^\s*([A-Z_]+): \{ kind: 'monster'", src, re.M))


def sha1(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest()


class Checker:
    def __init__(self, sc, m, where):
        self.sc, self.m, self.where = sc, m, where
        self.errors = []
        import convert
        self.floor_mv, self.ceil_mv, _ = convert.classify_movers(m)
        self.tags = {}
        for i, s in enumerate(m['sectors']):
            if s['tag']: self.tags.setdefault(s['tag'], []).append(i)
        xs = [v[0] for v in m['verts']]; ys = [v[1] for v in m['verts']]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.monsters = monster_names()

    def err(self, path, msg):
        self.errors.append('%s: %s: %s' % (self.where, path, msg))

    def line(self, path, i):
        if not isinstance(i, int) or not 0 <= i < len(self.m['lines']):
            self.err(path, 'line %r does not exist (0..%d)' % (i, len(self.m['lines']) - 1))

    def sector(self, path, i):
        if not isinstance(i, int) or not 0 <= i < len(self.m['sectors']):
            self.err(path, 'sector %r does not exist (0..%d)' % (i, len(self.m['sectors']) - 1))
            return False
        return True

    def thing(self, path, i):
        if not isinstance(i, int) or not 0 <= i < len(self.m['things']):
            self.err(path, 'thing %r does not exist (0..%d)' % (i, len(self.m['things']) - 1))

    def point(self, path, p):
        if not (isinstance(p, list) and len(p) >= 2 and all(isinstance(c, (int, float)) for c in p)):
            self.err(path, 'point must be [x, y] or [x, y, angle]'); return
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
            self.err(path, 'point %r is outside the map %r' % (p, self.bbox))

    def zone(self, path, z):
        if not isinstance(z, dict):
            self.err(path, 'zone must be an object'); return
        if 'sector' in z: self.sector(path + '.sector', z['sector'])
        elif 'sectors' in z:
            for k, i in enumerate(z['sectors']): self.sector('%s.sectors[%d]' % (path, k), i)
        elif 'box' in z:
            b = z['box']
            if not (isinstance(b, list) and len(b) == 4) or b[0] >= b[2] or b[1] >= b[3]:
                self.err(path, 'box must be [x1, y1, x2, y2] with x1 < x2, y1 < y2')
            else:
                self.point(path + '.box', b[:2]); self.point(path + '.box', b[2:])
        else:
            self.err(path, 'zone needs sector, sectors or box')

    def movers_for(self, path, kind, a):
        """the sectors an open_door/lower_lift/... action moves; each must have the right mover model"""
        want = self.ceil_mv if kind in CEIL_ACTIONS else self.floor_mv
        plane = 'ceiling' if kind in CEIL_ACTIONS else 'floor'
        secs = []
        if 'tag' in a:
            secs = self.tags.get(a['tag'], [])
            if not secs:
                self.err(path, 'tag %r is on no sector' % a['tag']); return
        elif 'sector' in a or 'sectors' in a:
            secs = [a['sector']] if 'sector' in a else list(a['sectors'])
            for i in secs:
                if not self.sector(path, i): return
        else:
            self.err(path, '%s needs tag, sector or sectors' % kind); return
        bad = [i for i in secs if i not in want]
        if bad:
            self.err(path, '%s: sectors %s have no %s mover (no door/lift special moves them in the WAD)' % (kind, bad, plane))

    def actions(self, path, acts, groups, blocks, stage_ids):
        if acts is None: return
        if not isinstance(acts, list):
            self.err(path, 'actions must be a list'); return
        for k, a in enumerate(acts):
            p = '%s[%d]' % (path, k)
            if not isinstance(a, dict) or len(a) != 1:
                self.err(p, 'an action is an object with exactly one key'); continue
            kind, arg = next(iter(a.items()))
            if kind in CEIL_ACTIONS or kind in FLOOR_ACTIONS:
                if not isinstance(arg, dict): self.err(p, kind + ' takes an object'); continue
                self.movers_for(p, kind, arg)
            elif kind == 'message':
                if not isinstance(arg, str) or not arg: self.err(p, 'message takes a string')
                elif len(arg) > 40: self.err(p, 'message longer than 40 characters (HUD line)')
            elif kind == 'spawn_group':
                g = arg if isinstance(arg, str) else (arg or {}).get('id')
                if g not in groups: self.err(p, 'spawn group %r is not defined' % g)
            elif kind in ('unblock', 'block'):
                b = arg if isinstance(arg, str) else (arg or {}).get('id')
                if b not in blocks: self.err(p, 'block %r is not defined' % b)
            elif kind not in OTHER_ACTIONS:
                self.err(p, 'unknown action %r' % kind)

    def run(self):
        sc, m = self.sc, self.m
        for key in ('map', 'wad', 'wad_sha1', 'stages'):
            if key not in sc: self.err(key, 'missing')
        groups = sc.get('spawn_groups', {}) or {}
        blocks = {b.get('id'): b for b in sc.get('blocks', []) or []}
        stages = sc.get('stages', []) or []
        stage_ids = [s.get('id') for s in stages]
        if len(set(stage_ids)) != len(stage_ids): self.err('stages', 'stage ids repeat')
        z = sc.get('zombies', {}) or {}
        mon = self.monsters
        if mon is not None:
            mm = z.get('map_monsters', {}) or {}
            for a, b in (mm.get('replace', {}) or {}).items():
                for n in (a, b):
                    if n not in mon: self.err('zombies.map_monsters.replace', 'unknown monster %r' % n)
            for n in mm.get('drop', []) or []:
                if n not in mon: self.err('zombies.map_monsters.drop', 'unknown monster %r' % n)
            for n in z.get('player_classes', []) or []:
                if n not in mon: self.err('zombies.player_classes', 'unknown monster %r' % n)
        for gid, g in groups.items():
            p = 'spawn_groups.' + gid
            if 'points' in g:
                for k, pt in enumerate(g['points']): self.point('%s.points[%d]' % (p, k), pt)
            elif 'sector' in g: self.sector(p + '.sector', g['sector'])
            elif 'sectors' in g:
                for i in g['sectors']: self.sector(p + '.sectors', i)
            else: self.err(p, 'needs points, sector or sectors')
            for k in g.get('things', []) or []: self.thing(p + '.things', k)
            for n in (g.get('ai', {}) or {}):
                if mon is not None and n not in mon: self.err(p + '.ai', 'unknown monster %r' % n)
        for bid, b in blocks.items():
            p = 'blocks.' + str(bid)
            if not b.get('lines'): self.err(p, 'needs lines')
            for i in b.get('lines', []): self.line(p + '.lines', i)
            u = b.get('until')
            if u is not None and u != 'never':
                mt = re.match(r'stage:(\d+)$', str(u))
                if not mt or int(mt.group(1)) not in stage_ids: self.err(p + '.until', 'must be "stage:<id of a stage>" or "never"')
        for k, s in enumerate(stages):
            p = 'stages[%d]' % k
            st = s.get('start')
            if st != 'round':
                if not isinstance(st, dict) or len(st) != 1 or next(iter(st)) not in START_KINDS:
                    self.err(p + '.start', 'must be "round" or one of %s' % sorted(START_KINDS))
                else:
                    kind, v = next(iter(st.items()))
                    if kind in ('line_crossed', 'use_line'): self.line(p + '.start', v)
                    elif kind == 'stage_done':
                        if v not in stage_ids or stage_ids.index(v) >= k: self.err(p + '.start', 'stage_done must name an earlier stage')
                    else: self.zone(p + '.start.zone_entered', v)
            if 'hold' in s:
                if not isinstance(s['hold'], (int, float)) or s['hold'] <= 0: self.err(p + '.hold', 'must be seconds > 0')
                if 'zone' not in s: self.err(p, 'a hold needs a zone')
            if 'zone' in s: self.zone(p + '.zone', s['zone'])
            if 'boss' in s:
                b = s['boss']
                if mon is not None and b.get('type') not in mon: self.err(p + '.boss.type', 'unknown monster %r' % b.get('type'))
                self.point(p + '.boss.at', b.get('at'))
            if 'hold' not in s and 'boss' not in s: self.err(p, 'a stage needs a hold or a boss')
            for g in s.get('zombie_spawns', []) or []:
                if g not in groups: self.err(p + '.zombie_spawns', 'spawn group %r is not defined' % g)
            for key in ('on_start', 'on_done'):
                self.actions('%s.%s' % (p, key), s.get(key), groups, blocks, stage_ids)
        if stages and not stages[-1].get('escape'): self.err('stages', 'the last stage must be the escape (escape: true)')
        if stages and stages[0].get('start') != 'round': self.err('stages[0].start', 'the first stage starts with the round')
        return self.errors


def load(path, wad_path=None, m=None):
    """reads and validates ze/<map>.json against its WAD; returns the object to embed as L.ze"""
    try:
        sc = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise SystemExit('ze_sidecar: %s: %s' % (path, e))
    import assets
    from wad import load_map
    if wad_path is None:
        wad_path = os.path.join(assets.FD, sc.get('wad', 'levels/%s.wad' % os.path.splitext(os.path.basename(path))[0]))
    if m is None:
        m = load_map(wad_path)
    errs = []
    got = sha1(wad_path)
    if sc.get('wad_sha1') != got:
        errs.append('%s: wad_sha1 %r does not match %s (%s): the sidecar was written for another WAD'
                    % (path, sc.get('wad_sha1'), wad_path, got))
    base = os.path.splitext(os.path.basename(path))[0].lower()
    if str(sc.get('map', '')).lower() != base:
        errs.append('%s: map %r does not match the file name %r' % (path, sc.get('map'), base))
    errs += Checker(sc, m, os.path.basename(path)).run()
    if errs:
        raise SystemExit('ze_sidecar: %d error(s)\n  ' % len(errs) + '\n  '.join(errs))
    return sc


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in sys.argv[1:]:
        sc = load(p)
        st = sc['stages']
        holds = sum(s.get('hold', 0) for s in st)
        print('%s ok: %d stages (%s), holds %ds, %d spawn groups, %d blocks' % (
            p, len(st), ', '.join(s.get('name', '?') for s in st), holds, len(sc.get('spawn_groups', {})), len(sc.get('blocks', []))))
