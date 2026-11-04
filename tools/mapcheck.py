"""Entity problems the way Hammer's Check for Problems sees them, read from CS2's own entity definitions (game/core and game/csgo .fgd files).

  python mapcheck.py <map.vmap> [<out.vmap>]          report; with an out path also fix what has only one right answer

Reports, one per line as KIND<tab>text:
  excluded    a class CS2's csgo.fgd removes (@exclude), e.g. info_ladder_dismount
  unknown     a class no CS2 .fgd defines, e.g. prop_physics_respawnable left by the importer
  dangling    an output aimed at a name nothing in the map has (ttt_island17's lwglass2 OnBreak -> lwbars2_i / lwbars2_f: in CS:GO too)
  bad_input   an input the target's class doesn't have
  bad_output  an output the entity's class doesn't have
  baked_switch a light the map switches or recolours that is still Static (its baked light would stay when it's off)
  disco       a cluster of switched / dynamic lights in several colours (a disco floor): shadows off; check it doesn't want baked bounce
  overflow    a key whose number does not fit a 32-bit int (mg_mario_party's trigger_push speed 9999999999): CS2 logs "Bad key" and
              wraps the value; fix clamps it to 2147483647
  equip_item  an item_* (armour, defuser) in a game_player_equip weapon slot: the server crashes on map load (null vtable in the equip's
              weapon handling; mg_n64_goldeneye, mg_mario_party). Stage C's equip_items moves it into the io script; reported only here
Fixes (with an out path): dangling outputs are removed, since they reached nothing in CS:GO either; classes in SAFE_REMOVE are deleted, because CS2
does their job by itself or never had it; classes in CONVERT become the CS2 entity that does the same job. Everything else is only reported.
"""
import collections, glob, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V

CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
SAFE_REMOVE = {'info_ladder_dismount': 'CS2 ladders dismount on their own', 'info_landmark': 'level transitions', 'func_detail_blocker': 'a compile hint'}
# classes CS2 lacks that one of its own entities does the job of: (new class, keys to set). Converted with an out path.
CONVERT = {
    # CS:GO's leeches: hurts anyone in the water until they get out. A trigger_hurt in the same place does the same.
    'trigger_waterydeath': ('trigger_hurt', {'damage': '15', 'damagecap': '15', 'damagetype': '0', 'damagemodel': '0', 'spawnflags': '1'}),
    # a solid brush entity with no behaviour of its own
    'func_wall': ('func_brush', {'Solidity': '2', 'solidbsp': '0'}),
}
INPUT_RENAME = {'turnon': 'Enable', 'turnoff': 'Disable'}   # fixed only where the target class has the new input
DYNAMIC_INPUTS = {'runscriptinput', 'runscriptcode', 'callscriptfunction', 'addoutput', 'fireuser1', 'fireuser2', 'fireuser3', 'fireuser4', 'kill', 'killhierarchy'}

def fgd_files():
    return sorted(glob.glob(os.path.join(CS2, 'game', 'core', '*.fgd'))) + sorted(glob.glob(os.path.join(CS2, 'game', 'csgo', '*.fgd')))

def parse_fgd(paths):
    """{class: (bases, inputs, outputs)} and the excluded set. Later files (csgo) override core, as Hammer loads them."""
    classes = {}; excluded = set()
    for p in paths:
        t = open(p, encoding='utf-8', errors='replace').read()
        t = re.sub(r'(?m)^\s*//[^\n]*', '', t)   # whole-line comments only: descriptions hold URLs with //
        excluded |= {x.lower() for x in re.findall(r'@exclude\s+(\w+)', t)}   # a file can exclude core's class and define its own (csgo.fgd's env_sky)
        for m in re.finditer(r'@(\w+)Class\b', t):
            # the header can hold ( ) and { key = value } metadata, so the class name is after the first = outside brackets and quotes
            i = m.end(); depth = 0; q = False
            while i < len(t):
                ch = t[i]
                if ch == '"' and t[i - 1] != '\\': q = not q
                elif not q and ch in '({': depth += 1
                elif not q and ch in ')}': depth -= 1
                elif not q and depth == 0 and ch in '=[': break
                i += 1
            if i >= len(t) or t[i] != '=': continue
            nm = re.match(r'=\s*(\w+)', t[i:])
            if not nm: continue
            header = t[m.end():i]; name = nm.group(1).lower()
            j = t.find('[', i); k = t.find('@', i + 1)
            if j < 0 or (0 <= k < j): continue
            depth = 1; e = j + 1; q = False
            while e < len(t) and depth:
                ch = t[e]
                if ch == '"' and t[e - 1] != '\\': q = not q
                elif not q and ch == '[': depth += 1
                elif not q and ch == ']': depth -= 1
                e += 1
            body = t[j + 1:e]
            bases = [b.strip().lower() for b in re.findall(r'\bbase\(([^)]*)\)', header) for b in b.split(',') if b.strip()]
            ins = {x.lower() for x in re.findall(r'^\s*input\s+(\w+)', body, re.M)}
            outs = {x.lower() for x in re.findall(r'^\s*output\s+(\w+)', body, re.M)}
            old = classes.get(name)
            if old and m.group(1) == 'Override': classes[name] = (old[0] + bases, old[1] | ins, old[2] | outs)
            else: classes[name] = (bases, ins, outs)
            if m.group(1) != 'Base': excluded.discard(name)
    return classes, excluded

def io(classes, name, seen=None):
    seen = seen or set()
    if name in seen or name not in classes: return set(), set()
    seen.add(name); bases, ins, outs = classes[name]; ins, outs = set(ins), set(outs)
    for b in bases:
        bi, bo = io(classes, b, seen); ins |= bi; outs |= bo
    return ins, outs

def check(m, fix=False):
    classes, excluded = parse_fgd(fgd_files())
    found = []; removed = 0; dropped = 0
    ents = m.entities()
    by_name = {}
    for e in ents: by_name.setdefault(m.name(e).lower(), []).append(e)
    clsnames = {m.cls(e).lower() for e in ents}
    converted = 0
    for e in list(ents):
        c = m.cls(e).lower()
        if fix and c in CONVERT and (c in excluded or c not in classes):
            new, keys = CONVERT[c]; m.setp(e, 'classname', new)
            for k, v in keys.items(): m.setp(e, k, v)
            converted += 1; found.append(('converted', '%s %s -> %s' % (c, m.name(e) or '(unnamed)', new))); continue
        if c in excluded:
            if fix and c in SAFE_REMOVE:
                m.remove_node(e); removed += 1; continue
            found.append(('excluded', '%s %s at %s: CS2 removes this class%s' % (c, m.name(e) or '(unnamed)', ' '.join('%g' % x for x in m.origin(e)), '' if c not in SAFE_REMOVE else ' (fix removes it: %s)' % SAFE_REMOVE[c])))
        elif c not in classes:
            found.append(('unknown', '%s %s at %s: no CS2 .fgd defines this class, so it does nothing in game' % (c, m.name(e) or '(unnamed)', ' '.join('%g' % x for x in m.origin(e)))))
    ents = m.entities()
    by_name = {}
    for e in ents: by_name.setdefault(m.name(e).lower(), []).append(e)
    for e in ents:
        c = m.cls(e).lower(); conns = dmx.geta(m.E[e], b'connectionsData')
        if not conns: continue
        _, outs = io(classes, c)
        for ci in list(conns[2]):
            out, tgt, inp = [str(x) for x in m.conn_tuple(m.E[ci])[:3]]
            if c in classes and outs and out.lower() not in outs:
                found.append(('bad_output', '%s %s: output %s does not exist on %s' % (c, m.name(e) or '(unnamed)', out, c)))
            t = tgt.lower()
            if not t or t.startswith('!'): continue
            hits = [x for n, xs in by_name.items() for x in xs if n == t or (t.endswith('*') and n.startswith(t[:-1]))] or [x for x in ents if m.cls(x).lower() == t]
            if not hits:
                if fix:
                    conns[2].remove(ci); dropped += 1
                found.append(('dangling', '%s %s: %s -> %s.%s, but nothing is called %s%s' % (c, m.name(e) or '(unnamed)', out, tgt, inp, tgt, ' (removed)' if fix else '')))
                continue
            if inp.lower() in DYNAMIC_INPUTS: continue
            tclasses = {m.cls(x).lower() for x in hits}
            if all(tc in classes for tc in tclasses) and not any(inp.lower() in io(classes, tc)[0] for tc in tclasses):
                new = INPUT_RENAME.get(inp.lower())   # CS:GO light inputs on CS2's lights2 classes (mg_galaxy_course's spawn lights never switched)
                if fix and new and all(new.lower() in io(classes, tc)[0] for tc in tclasses):
                    dmx.set_(m.E[ci], b'inputName', dmx.T_STR, new.encode()); converted += 1
                    found.append(('converted', '%s %s: %s -> %s.%s became %s' % (c, m.name(e) or '(unnamed)', out, tgt, inp, new))); continue
                found.append(('bad_input', '%s %s: %s -> %s.%s, but %s has no input %s' % (c, m.name(e) or '(unnamed)', out, tgt, inp, '/'.join(sorted(tclasses)), inp)))
    n, msgs = switched_lights(m, by_name, fix); converted += n; found += msgs
    n, msgs = overflow(m, ents, fix); converted += n; found += msgs
    found += equip_items(m, ents)
    return found, removed + converted, dropped

INT_MAX = 2147483647
def overflow(m, ents, fix):
    """keys holding a whole number outside the 32-bit int range: CS2 logs "Bad key ... Invalid parsed value" and wraps the number
    (9999999999 -> 1410065407). Clamped with fix."""
    found = []; n = 0
    for e in ents:
        for k, t, v in list(m.props(e)['attrs']):
            if t != dmx.T_STR: continue
            sv = v.decode('utf-8', 'replace').strip()
            if not re.fullmatch('-?[0-9]+', sv) or abs(int(sv)) <= INT_MAX: continue
            new = str(max(-INT_MAX - 1, min(INT_MAX, int(sv))))
            if fix: m.setp(e, k, new); n += 1
            found.append(('overflow', '%s %s: %s = %s does not fit a 32-bit int (CS2 wraps it to %d)%s' % (
                m.cls(e), m.name(e) or '(unnamed)', k.decode(), sv, int(sv) & 0xffffffff, ' (clamped to %s)' % new if fix else '')))
    return n, found

def equip_items(m, ents):
    """item_* in a game_player_equip weapon slot: the CS2 server crashes while the map loads (server.dll null vtable call, the dump's
    stack holds the item name). stage_c.equip_items moves them into the io script; here they are only reported."""
    found = []
    for e in ents:
        if m.cls(e).lower() != 'game_player_equip': continue
        items = [m.P(e, 'weapon%d' % i, '') for i in range(22)]
        items = [v for v in items if v.lower().startswith('item_')]
        if items: found.append(('equip_item', 'game_player_equip %s: %s in a weapon slot crashes CS2 on map load; give it from the io script (stage_c equip_items)' % (m.name(e) or '(unnamed)', ', '.join(items))))
    return found

LIGHTS2 = ('light_omni2', 'light_spot', 'light_rect', 'light_capsule', 'light_ortho', 'light_barn')
SWITCH_INPUTS = {'enable', 'disable', 'toggle', 'turnon', 'turnoff', 'setbrightnessscale', 'setcolor', 'setlightcolor'}

MAX_STATIONARY = 4   # shadowed stationary lights one spot may be inside (lighting.py's MAX_OVERLAP)

def _range(m, x):
    try: return float(m.P(x, 'range', '0') or 0) or 512.0
    except ValueError: return 512.0

DISCO_RADIUS, DISCO_MIN, DISCO_COLOURS = 384.0, 4, 4   # skink52: 4 different colours

def _colour(m, x):
    """'white' for white and near-white (warm room lights), else a hue in 12 steps"""
    import colorsys
    c = (m.P(x, 'color', '') or m.P(x, '_light', '') or '255 255 255').split()[:3]
    try: r, g, b = (float(v) / 255 for v in c)
    except ValueError: return 'white'
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    return 'white' if min(r, g, b) >= 0.75 * max(r, g, b, 1e-6) else 'hue%d' % (round(h * 12) % 12)

def discos(m, hit):
    """Clusters of >= DISCO_MIN switched or Dynamic lights within DISCO_RADIUS of each other in at least DISCO_COLOURS colours (white counts as one),
    that the map switches both on and off (Toggle, or Enable and Disable): a disco floor (ba_jail_skylight, seaside, jb_sides_cs2). Lights that only
    ever go off (ba_jail_lightsout's power cut) aren't one. Their shadows go off: changing colours look better unshadowed (skink52, 3 Nov 2026).
    Reported, since a few discos want baked bounce."""
    pool = [x for x in hit] + [x for c in LIGHTS2 for x in m.by_class(c) if x not in hit and str(m.P(x, 'directlight', '3')) == '2']
    names = collections.defaultdict(set)
    for x in pool: names[(m.name(x) or '').lower()].add(x)
    inputs = collections.defaultdict(set)
    for e, k in m.all_conns():
        u = m.conn_tuple(k)
        for y in names.get(u[1].lower(), ()): inputs[y].add(u[2].lower())
    onoff = lambda y: 'toggle' in inputs[y] or (inputs[y] & {'enable', 'turnon'} and inputs[y] & {'disable', 'turnoff'})
    pos = {x: m.origin(x) for x in pool}; seen = set(); out = []
    for x in pool:
        if x in seen: continue
        grp, todo = set(), [x]
        while todo:
            y = todo.pop()
            if y in grp: continue
            grp.add(y); todo += [z for z in pool if z not in grp and math.dist(pos[y], pos[z]) <= DISCO_RADIUS]
        seen |= grp
        if len(grp) >= DISCO_MIN and len({_colour(m, y) for y in grp}) >= DISCO_COLOURS and any(onoff(y) for y in grp): out.append(sorted(grp))
    return out

def switched_lights(m, by_name, fix):
    """A light the map switches or recolours can't be Static: its light is baked into the world and stays when it's off (skink52, 3 Nov 2026).
    Stationary (directlight 3: direct light at runtime, shadows baked) switches and recolours fine and costs less than Dynamic, so that's the
    default; a light riding a parent stays Dynamic (2), since its baked shadows would be wrong once it moves. Where a shadowed Stationary light
    would put a spot inside more than MAX_STATIONARY of them (CS2's shadow slots), it is Stationary with shadows off instead.
    Bounce light is always baked, so it's off on all of them."""
    hit = {}
    for e, k in m.all_conns():
        u = m.conn_tuple(k)
        if u[2].lower() in SWITCH_INPUTS:
            for x in by_name.get(u[1].lower(), []):
                if m.cls(x).lower() in LIGHTS2: hit[x] = u[2]
    for x in m.by_class('light_omni2') + m.by_class('light_spot') + m.by_class('light_rect') + m.by_class('light_capsule'):
        if str(m.P(x, 'enabled', '1')) in ('0', 'False', 'false') and x not in hit and m.name(x): hit[x] = 'starts off'
    shadowed = lambda x: str(m.P(x, 'castshadows', '1')) not in ('0', 'False', 'false')
    S = [(m.origin(x), _range(m, x)) for c in LIGHTS2 for x in m.by_class(c)
         if x not in hit and str(m.P(x, 'directlight', '3')) == '3' and shadowed(x)]
    def fits(p, r):
        near = [(o, rr) for o, rr in S if math.dist(o, p) < r + rr]
        pts = [p] + [tuple((a + b) / 2 for a, b in zip(o, p)) for o, _ in near] + [o for o, _ in near if math.dist(o, p) < r]
        return all(sum(math.dist(q, o) < rr for o, rr in near) + 1 <= MAX_STATIONARY for q in pts if math.dist(q, p) < r)
    n, out = 0, []
    disco = discos(m, hit)
    for i, grp in enumerate(disco, 1):
        o = [sum(c) / len(grp) for c in zip(*(m.origin(x) for x in grp))]
        out.append(('disco', "disco floor %d at %s: %d switched / dynamic lights in %d colours close together, so shadows off (%s). Check it doesn't need its "
                    "baked bounce light, which switched lights don't get" % (i, ' '.join('%.0f' % v for v in o), len(grp), len({_colour(m, x) for x in grp}),
                    ', '.join(sorted({m.name(x) or '(unnamed)' for x in grp}))[:200])))
    disco = {x for g in disco for x in g}
    for x in sorted(hit, key=lambda x: (m.name(x) or '', x)):
        why = hit[x]
        if x in disco and not m.P(x, 'parentname'):
            want = '2' if str(m.P(x, 'directlight', '3')) == '2' else '3'; cs, how = '0', '%s without shadows (disco floor)' % ('Dynamic' if want == '2' else 'Stationary')
        elif m.P(x, 'parentname'): want, cs, how = '2', None, 'Dynamic (it moves with its parent)'
        elif str(m.P(x, 'directlight', '3')) == '2': want, cs, how = '2', None, 'Dynamic (already set so; kept)'   # someone chose it (de_rats_1337)
        elif fits(m.origin(x), _range(m, x)): want, cs, how = '3', None, 'Stationary'
        else: want, cs, how = '3', '0', 'Stationary without shadows (over %d shadowed stationary lights here)' % MAX_STATIONARY
        if want == '3' and cs is None and shadowed(x) and x not in disco: S.append((m.origin(x), _range(m, x)))
        if str(m.P(x, 'directlight', '3')) == want and str(m.P(x, 'bouncelight', '-1')) == '0' and (cs is None or not shadowed(x)): continue
        if fix:
            m.setp(x, 'directlight', want); m.setp(x, 'bouncelight', '0'); n += 1
            if cs is not None: m.setp(x, 'castshadows', cs)
        out.append(('converted' if fix else 'baked_switch', '%s %s (%s): switched by the map, so %s with no bounce light%s' %
                    (m.cls(x), m.name(x) or '(unnamed)', why, how, '' if fix else ' is needed (fix sets it)')))
    return n, out

if __name__ == '__main__':
    if len(sys.argv) not in (2, 3): sys.exit(__doc__)
    mp = V.Map(sys.argv[1]); fix = len(sys.argv) == 3
    found, removed, dropped = check(mp, fix)
    for k, t in found: print('%s\t%s' % (k, t))
    if fix:
        mp.save(sys.argv[2])
        print('fixed\t%d entities removed or converted, %d dangling outputs removed' % (removed, dropped))
    print('summary\t' + ', '.join('%d %s' % (sum(1 for k, _ in found if k == kind), kind) for kind in ('excluded', 'unknown', 'dangling', 'bad_input', 'bad_output', 'baked_switch', 'disco', 'overflow', 'equip_item', 'converted')))
