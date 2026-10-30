"""Dropped I/O report: entity outputs in the decompiled .vmf that are not in the .vmap. Report only, nothing is changed.

Method from github.com/Ninja-Chris/cs2-slop-porting (MIT): owners are matched by classname + name, unnamed owners by classname and
brush bounds / origin; every .vmf output with no equal output on the matched vmap owner is listed, with whether its target still exists.

run(m, c, vmfpath) -> number of probable losses. Writes maps/<addon>_dropped_io.txt (grouped by owner entity) and one log line
(+ a TO CHECK line when something looks lost). Our own stage C / D conversions are not reported as losses:
- class changes (trigger_push / trigger_gravity -> trigger_multiple, func_wall_toggle -> func_brush, func_breakable_surf, env_steam ...)
- inputs renamed on converted targets (TurnOn/TurnOff -> Enable/Disable on beams and wall toggles, Start/Stop on steam / tesla,
  Use -> TriggerForActivatedPlayer on equips)
- outputs moved into the io script (RunScriptInput Cmd_ / Score_ / Speed_ / GameUIOn_ / GameUIOff_ / Launch_)
- owners the pipeline replaced or removed (point_servercommand, game_score, player_speedmod, game_ui, env_laser, env_beam,
  point_tesla, env_sun, point_viewcontrol)
- cs2mapTTT conversions on TTT maps (outputs moved into <owner>__<event> relays, ttt_* targets, crouch commands, logic_auto sandbox texts)
Those are listed in a separate section of the report. Run it last (end of stage C, or as a stage D pass) so they're all in place."""
import os, math, fnmatch, collections
import vmf as vmfmod

SPECIAL = ('!activator', '!caller', '!self', '!player', '!picker', '!pvsplayer', '!enemy', '!target')

# .vmf class -> classes it may have in the vmap after the importer / our steps
ALIAS = {'trigger_push': ('trigger_multiple',), 'trigger_gravity': ('trigger_multiple',), 'func_wall_toggle': ('func_brush',),
         'func_illusionary': ('func_brush',), 'prop_hallucination': ('prop_dynamic', 'prop_static'), 'func_breakable_surf': ('func_breakable',),
         'func_physbox_multiplayer': ('func_physbox',), 'env_steam': ('info_particle_system',), 'env_particle_glow': ('info_particle_system',),
         'light': ('light_omni2',), 'light_spot': ('light_barn',)}

# owners our steps replace or remove (only used when the owner isn't in the vmap any more)
REPLACED = {'point_servercommand': 'removed by `cmd`, its Command inputs run from the io script',
            'game_score': 'removed by `score`, ApplyScore runs from the io script',
            'player_speedmod': 'removed by `speed`, ModifySpeed runs from the io script',
            'game_ui': 'removed by `gameui`, its outputs are fired from the io script key poll',
            'env_laser': 'replaced by a func_brush beam (`beams`)', 'env_beam': 'replaced by a func_brush beam (`beams`)',
            'point_tesla': 'replaced by an info_particle_system (`tesla`)', 'env_sun': 'removed by `dead` (not in CS2)',
            'point_viewcontrol': 'removed by `dead` (nothing targeted it)'}
SCRIPT_OWNERS = ('game_ui',)

# target .vmf class -> {input: inputs it became}
RENAMED = {'func_wall_toggle': {'turnon': ('enable',), 'turnoff': ('disable',)},
           'env_laser': {'turnon': ('enable',), 'turnoff': ('disable',), 'toggle': ('toggle',)},
           'env_beam': {'turnon': ('enable',), 'turnoff': ('disable',), 'toggle': ('toggle',), 'strikeonce': ('enable',)},
           'env_steam': {'turnon': ('start',), 'turnoff': ('stop',)},
           'point_tesla': {'turnon': ('start',), 'dospark': ('start',), 'turnoff': ('stop',)},
           'game_player_equip': {'use': ('triggerforactivatedplayer',)}}
# target .vmf class -> {input: io script function prefix}
SCRIPTED = {'point_servercommand': {'command': 'Cmd_'}, 'game_score': {'applyscore': 'Score_'}, 'player_speedmod': {'modifyspeed': 'Speed_'},
            'game_ui': {'activate': 'GameUIOn_', 'deactivate': 'GameUIOff_'}, 'trigger_push': {'enable': 'Launch_', 'disable': 'Launch_'}}
IMPORTER_DROPS = ('point_spotlight', 'func_dustmotes', 'func_precipitation', 'env_lightglow', 'fog_volume', 'color_correction', 'env_fog_controller')


def _vec(s):
    try: return tuple(float(x) for x in str(s).split()[:3])
    except ValueError: return None

def vmf_entities(path):
    root = vmfmod.parse(open(path, encoding='utf-8', errors='replace').read())
    nodes = []
    for n in root.ch:
        if n.name == 'entity': nodes.append(n)
        elif n.name == 'hidden': nodes += [x for x in n.ch if x.name == 'entity']
    out = []
    for e in nodes:
        conns, pts = [], []
        for ch in e.ch:
            if ch.name == 'connections':
                for k, v in ch.kv:
                    esc = '\x1b' in v
                    f = v.split('\x1b') if esc else v.split(',')
                    if len(f) < 5: continue
                    try: conns.append((k, f[0], f[1], f[2] if esc else ','.join(f[2:-2]), round(float(f[-2] or 0), 3), int(float(f[-1] or -1))))
                    except ValueError: pass
            elif ch.name == 'solid':
                for sd in ch.ch:
                    if sd.name != 'side': continue
                    for t in (sd.get('plane') or '').replace('(', ' ').split(')'):
                        p = _vec(t)
                        if p and len(p) == 3: pts.append(p)
        bbox = (tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3))) if pts else None
        out.append({'cls': (e.get('classname') or '').lower(), 'name': e.get('targetname') or '', 'origin': _vec(e.get('origin')) if e.get('origin') else None,
                    'bbox': bbox, 'conns': conns})
    return out

def _low(t): return (t[0].lower(), t[1].lower(), t[2].lower(), t[3], round(t[4], 3), int(t[5]))

def _center(b): return [(b[0][i] + b[1][i]) / 2 for i in range(3)]

def _who(v):
    p = v['origin'] or (_center(v['bbox']) if v['bbox'] else None)
    at = ' '.join('%g' % round(x) for x in p) if p else '?'
    return "%s '%s' (%s)" % (v['cls'], v['name'], at) if v['name'] else '%s (unnamed, %s)' % (v['cls'], at)

def _fmt(t): return '%s -> %s.%s(%s) delay %g times %d' % (t[0], t[1], t[2], t[3], t[4], t[5])


def run(m, c, vmfpath):
    rel = 'maps/%s_dropped_io.txt' % c.addon
    if not vmfpath or not os.path.exists(vmfpath):
        c.log.append('dropped I/O report: no .vmf, skipped'); return 0
    script = getattr(c, 'script', c.addon + '_io_script').lower()
    vents = vmf_entities(vmfpath)
    vcls = collections.defaultdict(set)
    for v in vents:
        if v['name']: vcls[v['name'].lower()].add(v['cls'])
    owners = [v for v in vents if v['conns']]

    ments = []
    for e in m.entities():
        ments.append({'e': e, 'cls': m.cls(e).lower(), 'name': m.name(e), 'origin': tuple(m.origin(e)), 'bbox': False, 'used': False,
                      'conns': [_low(m.conn_tuple(cn)) for cn in m.conns(e)]})
    names = {x['name'].lower() for x in ments if x['name']}
    classes = {x['cls'] for x in ments}
    by_cls = collections.defaultdict(list)
    for x in ments: by_cls[x['cls']].append(x)

    def bbox(x):
        if x['bbox'] is False: x['bbox'] = m.bounds(x['e'])
        return x['bbox']

    def dist(v, x):
        if v['bbox'] and bbox(x):
            sz = max(abs((v['bbox'][1][i] - v['bbox'][0][i]) - (x['bbox'][1][i] - x['bbox'][0][i])) for i in range(3))
            dc = math.dist(_center(v['bbox']), _center(x['bbox']))
            if sz <= 4.0 and dc <= 3.0: return dc
        if v['origin']: return math.dist(v['origin'], x['origin']) + (0.0 if not v['bbox'] else 1000.0)
        if v['bbox']: return math.dist(_center(v['bbox']), x['origin']) + 1000.0
        return 1e9

    def target_classes(t):
        tl = t.lower()
        if '*' in tl or '?' in tl: return set().union(*[s for n, s in vcls.items() if fnmatch.fnmatchcase(n, tl)] or [set()])
        return vcls.get(tl, {tl} if tl in {v['cls'] for v in vents} else set())

    def target_status(t):
        tl = t.lower()
        if tl in SPECIAL: return 'SPECIAL'
        if tl in names or tl in classes: return 'EXISTS'
        if ('*' in tl or '?' in tl) and any(fnmatch.fnmatchcase(n, tl) for n in names | classes): return 'EXISTS'
        return 'GONE'

    def is_script(x): return x == script or x.endswith('_io_script')

    # cs2mapTTT (tools/ttt_convert.py) moves outputs into logic_relays named <owner>__<event> and re-aims ttt_* targets at its script
    relays = collections.defaultdict(list)
    for x in ments:
        if x['cls'] == 'logic_relay' and '__' in x['name']:
            relays[x['name'].lower().rsplit('__', 1)[0]] += [(t[1], t[2], t[3], round(t[4], 2)) for t in x['conns']]
    ttt_map = any(x['name'].lower() == 'ttt_script' for x in ments)

    lost = collections.OrderedDict()      # owner -> [(status, conn, note)]
    handled = []                          # (owner, conn, note)
    notfound = []
    nmatched = 0
    for v in owners:
        pool = [x for k in (v['cls'],) + ALIAS.get(v['cls'], ()) for x in by_cls.get(k, []) if not x['used']]
        if v['name']:
            nl = v['name'].lower()
            cand = [x for x in pool if x['name'].lower() == nl]
            if not cand: cand = [x for x in pool if x['name'].lower().startswith(nl + '_')]     # doorsolid renames the 2nd of a shared-name pair
        else:
            cand = [x for x in pool if not x['name'] or x['name'].startswith(('port_', 'ttt_pt_'))]   # doorsolid's port_door_<k>, cs2mapTTT's ttt_pt_<k>
        best = min(cand, key=lambda x: dist(v, x), default=None)
        if best is not None and not v['name']:
            d = dist(v, best)
            if d > (3.0 if v['bbox'] else 1.0) and not (v['bbox'] and d < 1064.0): best = None   # brush: bounds within 3 u, else origin within 64 u
        if best is None:
            if ttt_map and v['cls'].startswith('ttt_'):
                for t in v['conns']: handled.append((v, t, 'TTT: %s replaced by cs2mapTTT (logic_relays fired from ttt.js)' % v['cls']))
            elif v['cls'] in REPLACED:
                for t in v['conns']: handled.append((v, t, ('SCRIPT: ' if v['cls'] in SCRIPT_OWNERS else 'OWNER REPLACED: ') + REPLACED[v['cls']]))
            else: notfound.append(v)
            continue
        best['used'] = True; nmatched += 1
        have = collections.Counter(best['conns'])
        miss = []
        for t in v['conns']:
            k = _low(t)
            if have[k] > 0: have[k] -= 1
            else: miss.append((k, t))
        extra = list(have.elements())
        for k, orig in miss:
            o, tg, inp, p, d, n = k
            tcls = target_classes(tg)
            note = None
            for tc in tcls:
                alt = RENAMED.get(tc, {}).get(inp)
                if alt:
                    hit = next((x for x in extra if x[0] == o and x[1] == tg and x[2] in alt and abs(x[4] - d) < 0.06), None)
                    if hit: extra.remove(hit); note = 'CONVERTED: %s input %s -> %s (target was %s)' % (tg, inp, hit[2], tc); break
                pre = SCRIPTED.get(tc, {}).get(inp)
                if pre:
                    hit = next((x for x in extra if x[0] == o and is_script(x[1]) and x[2] == 'runscriptinput' and x[3].startswith(pre) and abs(x[4] - d) < 0.06), None)
                    if hit: extra.remove(hit); note = 'SCRIPT: -> io script %s (target was %s)' % (hit[3], tc); break
                    if tc == 'trigger_push' and inp == 'disable' and any(x[0] == o and is_script(x[1]) and x[3].startswith('Launch_') for x in best['conns']):
                        note = 'SCRIPT: Disable dropped, the launcher is fired from the io script (Launch_)'; break
            if not note and ttt_map:
                if any(tc.startswith('ttt_') for tc in tcls):
                    note = 'TTT: target was %s, handled by cs2mapTTT (ttt.js)' % '/'.join(sorted(tcls))
                elif best['name'] and any((tg, i2, p, round(d, 2)) in relays.get(best['name'].lower(), [])
                                          for i2 in (inp,) + tuple(a for tc in tcls for a in RENAMED.get(tc, {}).get(inp, ()))):
                    note = 'TTT: moved into cs2mapTTT relay %s__*' % best['name']
                elif 'point_clientcommand' in tcls and any(x[2] == 'runscriptinput' and x[3].startswith('ttt:duck') for x in best['conns']):
                    note = 'TTT: crouch command -> cs2mapTTT ttt:duck prompt'
                elif v['cls'] == 'logic_auto' and 'game_text' in tcls and inp == 'display':
                    note = 'TTT: cs2mapTTT drops the map\'s logic_auto texts (sandbox-mode warnings)'
            if note: handled.append((v, orig, note)); continue
            st = target_status(tg)
            tn = ''
            if st == 'GONE' and tcls:
                tn = 'target was %s' % '/'.join(sorted(tcls))
                if tcls & set(IMPORTER_DROPS): tn += ', a class the importer leaves out'
                elif tcls & set(REPLACED): tn += ', ' + REPLACED[next(iter(tcls & set(REPLACED)))]
            elif st == 'EXISTS' and tcls & (set(RENAMED) | set(SCRIPTED)):
                tn = 'target was %s, converted by the pipeline but no matching converted output found' % '/'.join(sorted(tcls))
            lost.setdefault(id(v), (v, []))[1].append((st, orig, tn))

    rows = [r for _, (v, rs) in lost.items() for r in rs]
    cnt = collections.Counter(r[0] for r in rows)
    nout = sum(len(v['conns']) for v in owners)
    summ = ('dropped I/O report (%s): %d .vmf owners with %d outputs, %d matched; %d outputs missing with the target still there (probable losses), '
            '%d with the target gone, %d to !special targets; %d handled by our own steps (script / converted); %d owners not found (%d outputs not compared)'
            % (rel, len(owners), nout, nmatched, cnt['EXISTS'], cnt['GONE'], cnt['SPECIAL'], len(handled), len(notfound), sum(len(v['conns']) for v in notfound)))
    L = ['Outputs (I/O) in the .vmf that are not in the .vmap - %s. Report only, nothing was changed.' % c.addon,
         'Method from github.com/Ninja-Chris/cs2-slop-porting (MIT).',
         'LOSS    = target still exists in the vmap: probably a real loss, re-add it (Hammer) or check why it went.',
         'SPECIAL = target is !activator / !self / ...: resolved at run time, treat like LOSS.',
         'GONE    = nothing in the vmap has the target name: the logic was removed / replaced (an edited map), or the target was lost too.',
         'Our own conversions (io script, renamed inputs, replaced entities) are listed at the end and are not losses.', '',
         '# ' + summ, '']
    order = {'EXISTS': 0, 'SPECIAL': 1, 'GONE': 2}
    tag = {'EXISTS': 'LOSS   ', 'SPECIAL': 'SPECIAL', 'GONE': 'GONE   '}
    for v, rs in sorted(lost.values(), key=lambda a: (min(order[r[0]] for r in a[1]), a[0]['cls'], a[0]['name'].lower())):
        L.append('== ' + _who(v))
        for st, k, tn in sorted(rs, key=lambda r: (order[r[0]], r[1][0])):
            L.append('  %s %s%s' % (tag[st], _fmt(k), ('   [%s]' % tn) if tn else ''))
        L.append('')
    if notfound:
        L.append('== owners not found in the vmap (outputs not compared)')
        for v in notfound:
            n = ' (the importer leaves this class out)' if v['cls'] in IMPORTER_DROPS else ''
            L.append('  %s%s: %d output(s): %s' % (_who(v), n, len(v['conns']), '; '.join(sorted({'%s->%s.%s' % (o, t, i) for o, t, i, _p, _d, _n in v['conns']}))[:300]))
        L.append('')
    if handled:
        L.append('== handled by the pipeline (not losses)')
        for v, k, note in handled: L.append('  %s  %s   [%s]' % (_who(v), _fmt(k), note))
        L.append('')
    c.write(rel, '\n'.join(L) + '\n')
    c.log.append(summ)
    if cnt['EXISTS'] or cnt['SPECIAL']:
        by = collections.Counter('%s->%s' % (k[0], k[2]) for r in rows if r[0] != 'GONE' for k in [r[1]])
        c.todo.append('%d outputs from the .vmf are missing in the vmap while their target is still there (%s): see %s'
                      % (cnt['EXISTS'] + cnt['SPECIAL'], ', '.join('%s x%d' % a for a in by.most_common(6)), rel))
    return cnt['EXISTS'] + cnt['SPECIAL']
