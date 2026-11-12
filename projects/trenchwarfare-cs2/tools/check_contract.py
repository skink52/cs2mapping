"""Checks docs/CONTRACT.md's promises: every entity name the script looks up exists in the map with the expected class and count,
every model the script sets (and every model on a script-driven entity) is in the addon, every sound event the script triggers is
defined, every HUD id / class the script sends is in the HUD xml / css, and the script / HUD / point_script files are where the map
says. Fails (exit 1) on any MISSING row that docs/CONTRACT.md does not list under "## Known missing", on a script lookup no row
covers (UNLISTED), and on a row whose name no longer appears in the script (STALE). Reads only.

The script is the shipped build src/mg_trenchwarfare.js (src/modules/NN_*.js joined by create/build_script.mjs, config src/build.json);
a build older than its modules is a failure (STALE build), so the names checked are the modules' names.

usage: python tools/check_contract.py [--digest out/digest.json | --vmap V] [--stage DIR] [--addon A] [--game G] [--script JS] [--markdown]
  --digest   the map digest (tools/restage_out.py writes out/digest.json); default: that file, else a fresh digest of --vmap
  --vmap     check this map instead (a fresh digest), e.g. out/mg_trenchwarfare_patched.vmap (step 5) or out/nav_patched_step5.vmap
  --stage    a staging folder (e.g. out/addon): a model on a map entity that is only there counts as OK, "staged, not compiled yet".
             Never for a model the script SetModels on a pawn: that one must be compiled in the game addon (or be the pawn's own
             stock model), because a pawn set to a model the game cannot load is what gave the giant first-person weapons
  --markdown print the tables for docs/CONTRACT.md instead of the plain report (same rows, same statuses)
Defaults: --addon C:/source1/links/content_addons/mg_trenchwarfare, --game C:/source1/links/game_addons/mg_trenchwarfare,
          out/digest.json (the deployed map as restaged), no stage. Level: a read of the files ("untested" in game).
Every SetModel call in the script is checked: its argument must be a CONFIG.UNIFORMS model (each one compiled in the game addon and
precached by a map prop) or the pawn's own model read back from it (p.stockModel); any other argument fails (UNCHECKED SetModel).
"""
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SCRIPT = os.path.join(PROJ, 'src', 'mg_trenchwarfare.js')
CONTRACT = os.path.join(PROJ, 'docs', 'CONTRACT.md')
MAPDIGEST = os.path.normpath(os.path.join(PROJ, '..', '..', 'tools', 'mapdigest.py'))
BUILD = os.path.normpath(os.path.join(PROJ, '..', '..', 'create', 'build_script.mjs'))
TEAMS = ('t', 'ct')


def load_digest(a):
    p = a.digest or os.path.join(PROJ, 'out', 'digest.json')
    if os.path.exists(p) and not a.vmap:
        return json.load(open(p, encoding='utf-8'))
    vmap = a.vmap or os.path.join(a.addon, 'maps', 'mg_trenchwarfare.vmap')
    r = subprocess.run([sys.executable, MAPDIGEST, vmap], capture_output=True, text=True)
    if r.returncode: raise SystemExit('check_contract: mapdigest failed: ' + r.stderr[-400:])
    return json.loads(r.stdout)


def cfg_num(js, key):
    m = re.search(r'\b%s:\s*([0-9.]+)' % key, js)
    if not m: raise SystemExit('check_contract: CONFIG.%s not found in the script' % key)
    return int(float(m.group(1)))


def main():
    ap = argparse.ArgumentParser(description='mg_trenchwarfare contract check (read-only)')
    ap.add_argument('--digest'); ap.add_argument('--vmap')
    ap.add_argument('--addon', default='C:/source1/links/content_addons/mg_trenchwarfare')
    ap.add_argument('--game', default='C:/source1/links/game_addons/mg_trenchwarfare')
    ap.add_argument('--stage', help='staging folder searched for map-entity models not yet deployed (never for SetModel models)')
    ap.add_argument('--markdown', action='store_true')
    ap.add_argument('--script', default=SCRIPT, help='the script to check (default src/mg_trenchwarfare.js)')
    a = ap.parse_args()
    js = open(a.script, encoding='utf-8').read()
    d = load_digest(a)
    ents = d['entities']
    by_name = {}
    for e in ents:
        if e.get('name'): by_name.setdefault(e['name'], []).append(e)
    CREWS, POOL, STEPS = cfg_num(js, 'CREWS'), cfg_num(js, 'POOL'), cfg_num(js, 'TARGET_STEPS')
    rows = {'entity': [], 'model': [], 'sound': [], 'hud': [], 'file': [], 'console': []}
    problems = []

    def row(kind, key, status, cls='', count='', who='', note=''):
        rows[kind].append(dict(key=key, status=status, cls=cls, count=count, who=who, note=note))

    # ---------------------------------------------------------------- entities
    def fam(prefix_re, lo=1, hi=None):           # open-ended numbered family per team: <prefix><tg>_N
        out = {}
        for tg in TEAMS:
            rx = re.compile(prefix_re.replace('<tg>', tg) + r'(\d+)$')
            out[tg] = sorted((n for n in by_name if rx.match(n)), key=lambda n: int(rx.match(n).group(1)))
        return out

    def ent_row(key, tokens, cls, names, who, note='', expect=None):
        """names: the exact names expected (list), or {tg: [found names]} for an open family with expect=(lo, hi) per team"""
        for t in tokens:
            if t not in js: problems.append('STALE row %s: %r is not in the script' % (key, t))
        if isinstance(names, dict):
            got = {tg: [n for n in names[tg] if any(e['class'] == cls for e in by_name[n])] for tg in TEAMS}
            lo, hi = expect
            ok = all(lo <= len(got[tg]) <= hi for tg in TEAMS) and all(len(got[tg]) == len(names[tg]) for tg in TEAMS)
            count = ' / '.join('%d' % len(got[tg]) for tg in TEAMS) + ' (t / ct; script reads 1..%d)' % hi
        else:
            have = [n for n in names if n in by_name and any(e['class'] == cls for e in by_name[n])]
            wrong = [n for n in names if n in by_name and n not in have]
            dup = sum(len(by_name[n]) for n in have)
            ok = len(have) == len(names)
            count = '%d of %d' % (len(have), len(names)) + (' (%d entities)' % dup if dup != len(have) else '')
            if wrong: note = (note + '; ' if note else '') + 'wrong class: ' + ', '.join('%s=%s' % (n, by_name[n][0]['class']) for n in wrong[:3])
        row('entity', key, 'OK' if ok else 'MISSING', cls, count, who, note)

    per_team = lambda f: [f(tg) for tg in TEAMS]
    flat = lambda xs: [y for x in xs for y in x]
    crew = lambda fmt: flat(per_team(lambda tg: [fmt % (tg, k) for k in range(1, CREWS + 1)]))
    pool = lambda p: ['%s%d' % (p, i) for i in range(1, POOL + 1)]
    planes = fam(r'tw_plane_<tg>_')
    tags = flat([[n[len('tw_plane_'):] for n in planes[tg]] for tg in TEAMS])
    per_plane = lambda fmt: [fmt % t for t in tags]

    ent_row('trench_<tg>_N', ['"trench_"'], 'info_teleport_destination', fam(r'trench_<tg>_'), 'make_map.py',
            'infantry posts (deploy, and the bot leash: a post 400+ u from a closed blocker)', expect=(1, 64))
    ent_row('heal_<tg>_N', ['"heal_"'], 'info_target', fam(r'heal_<tg>_'), 'make_map.py', 'dressing stations', expect=(1, 16))
    ent_row('plane_<tg>_N', ['"plane_"'], 'info_teleport_destination', fam(r'plane_<tg>_'), 'make_map.py', 'air-spawn points', expect=(1, 16))
    ent_row('tw_plane_<tg>_N', ['"tw_plane_"'], 'prop_dynamic', planes, 'make_map.py', 'the aircraft (CT SPAD VII, T Dr.I)', expect=(1, 16))
    ent_row('tw_prop_<tg>_N', ['"tw_prop_"'], 'prop_dynamic', per_plane('tw_prop_%s'), 'patch_vmap.py (make_map.py since)', 'propeller, one per aircraft')
    ent_row('tw_bomb_<tg>_N_1..2', ['"tw_bomb_"'], 'prop_dynamic', flat([per_plane('tw_bomb_%%s_%d' % k) for k in (1, 2)]), 'make_map.py', '2 per aircraft')
    ent_row('tw_tracer_<tg>_N_1..6', ['"tw_tracer_"'], 'prop_dynamic', flat([per_plane('tw_tracer_%%s_%d' % k) for k in range(1, 7)]), 'make_map.py', '6 per aircraft')
    ent_row('tw_bombsight_<tg>_N', ['"tw_bombsight_"'], 'prop_dynamic', per_plane('tw_bombsight_%s'), 'make_map.py', '')
    ent_row('tw_gunsight_<tg>_N', ['"tw_gunsight_"'], 'prop_dynamic', per_plane('tw_gunsight_%s'), 'make_map.py', '')
    for k in ('eng', 'gun', 'gun2', 'gun3'):
        ent_row('tw_plane_%s_<tg>_N' % k, ['"%s"' % k, '"tw_plane_"'], 'point_soundevent', per_plane('tw_plane_' + k + '_%s'), 'make_map.py',
                'SetSourceEntity to the aircraft; ' + ('StartSound/StopSound (engine loop)' if k == 'eng' else 'StartSound per burst'))
    ent_row('tw_plane_smoke_<tg>_N', ['"tw_plane_smoke_"'], 'info_particle_system', per_plane('tw_plane_smoke_%s'), 'make_map.py', 'damage smoke Start/Stop')
    ent_row('mortarpit_<tg>_K', ['"mortarpit_"'], 'info_target', crew('mortarpit_%s_%d'), 'make_map.py', 'tube position, K = 1..CREWS (%d)' % CREWS)
    ent_row('mortarcrew_<tg>_K_a', ['"mortarcrew_"'], 'info_teleport_destination', crew('mortarcrew_%s_%d_a'), 'make_map.py', 'seat a: plotting table')
    ent_row('mortarcrew_<tg>_K_b', ['"mortarcrew_"'], 'info_teleport_destination', crew('mortarcrew_%s_%d_b'), 'make_map.py', 'seat b: ammunition box')
    ent_row('tw_launch_snd_<tg>_K', ['"tw_launch_snd_"'], 'point_soundevent', crew('tw_launch_snd_%s_%d'), 'make_map.py', 'StartSound on firing')
    ent_row('tw_launch_fx_<tg>_K', ['"tw_launch_fx_"'], 'info_particle_system', crew('tw_launch_fx_%s_%d'), 'make_map.py', 'Stop/Start on firing')
    ent_row('mortar_<tg>_K', ['"mortar_"'], 'prop_dynamic', crew('mortar_%s_%d'), 'patch_world_1.py (step 5; prop_static in the deployed map)',
            'looked up per round; SetAnimation fire by ent.FireInput when present (fireMortar), and the fallback for a missing mortarpit_')
    for p, cls, inp in (('tw_boom_fx_', 'info_particle_system', 'Stop/Start'), ('tw_dirt_fx_', 'info_particle_system', 'Stop/Start'),
                        ('tw_boom_snd_', 'point_soundevent', 'StartSound'), ('tw_whistle_snd_', 'point_soundevent', 'StartSound'),
                        ('tw_shake_', 'env_shake', 'StartShake')):
        ent_row(p + '1..%d' % POOL, ['"%s"' % p], cls, pool(p), 'make_map.py', 'effect pool (POOL %d), Teleport + %s' % (POOL, inp))
    ent_row('tw_hud', ['"tw_hud"'], 'custom_hud_layout', ['tw_hud'], 'make_map.py', 'CONFIG.HUD')
    for u in ('woodsopen', 'undergroundopen'):
        ent_row(u, ['"%s"' % u], 'prop_dynamic', [u], 'the user (blockers), made prop_dynamic by patch_unlocks.py',
                'Entities.FindByName (both); Remove + effects when the area opens (CONFIG.UNLOCKS); positions: the bot leash and the bots\' sap-head / ladder posts')
    ent_row('tw_script', [], 'point_script', ['tw_script'], 'make_map.py', 'runs the script (not looked up by it)')
    nu = len(set(re.findall(r'"(models/tw/players/[^"]+\.vmdl)"', js)))
    ent_row('tw_uniform_1..%d' % nu, [], 'prop_dynamic', ['tw_uniform_%d' % i for i in range(1, nu + 1)], 'patch_uniforms.py',
            'hidden precache props for the uniform models (not looked up by the script)')
    lob = {c: d['summary']['by_class'].get(c, 0) for c in ('info_player_terrorist', 'info_player_counterterrorist')}
    row('entity', 'info_player_terrorist / _counterterrorist', 'OK' if all(lob.values()) else 'MISSING', 'spawns',
        '%d / %d' % tuple(lob.values()), 'make_map.py', 'lobby spawns (the script teleports from there; not looked up)')

    # every literal a lookup starts with must be some row's token
    tokens = set()
    known_tok = set(re.findall(r'"([A-Za-z_0-9]+)"', ' '.join(
        ['"trench_" "heal_" "plane_" "tw_plane_" "tw_prop_" "tw_bomb_" "tw_tracer_" "tw_bombsight_" "tw_gunsight_" "tw_plane_eng_"',
         '"tw_plane_smoke_" "mortarpit_" "mortar_" "mortarcrew_" "tw_launch_snd_" "tw_launch_fx_" "tw_boom_fx_" "tw_dirt_fx_"',
         '"tw_boom_snd_" "tw_whistle_snd_" "tw_shake_" "tw_hud"'])))
    for m in re.finditer(r'(?:FindEntityByName|FindEntitiesByName|FindByName|\bbyName|findList|\bent|\bfire)\(\s*"([^"]+)"', js):
        tokens.add(m.group(1))
    for t in sorted(tokens - known_tok):
        problems.append('UNLISTED script lookup "%s..." (add a row for it)' % t)
    if 'byName(nm + i)' in js or 'FindEntityByName(nm + i)' in js:
        arr = re.search(r'for \(const nm of \[([^\]]+)\]\)', js)
        for t in re.findall(r'"([^"]+)"', arr.group(1) if arr else ''):
            if t not in known_tok: problems.append('UNLISTED pool lookup "%s"' % t)

    # ---------------------------------------------------------------- models
    def mdl_status(m):
        c = os.path.exists(os.path.join(a.addon, m)); g = os.path.exists(os.path.join(a.game, m + '_c'))
        return c, g
    def staged(m): return bool(a.stage) and os.path.exists(os.path.join(a.stage, m))
    # SetModel on a pawn: every call's argument must be a CONFIG.UNIFORMS model or the pawn's own model read back (p.stockModel)
    uni = re.search(r'UNIFORMS:\s*\{(.*?)\n\s*\},', js, re.S)
    uni_models = set(re.findall(r'"(models/[^"]+\.vmdl)"', uni.group(1) if uni else ''))
    if not uni_models: problems.append('STALE: CONFIG.UNIFORMS not found / no models in it')
    for arg in re.findall(r'\.SetModel\(([^)]*)\)', js):
        if arg.strip() not in ('m', 'p.stockModel'): problems.append('UNCHECKED SetModel(%s): only CONFIG.UNIFORMS models (via m) or p.stockModel are verified' % arg.strip())
    if 'const m = list[p.slot % list.length]' not in js: problems.append('STALE: uniform() no longer picks m from CONFIG.UNIFORMS')
    for m in sorted(set(re.findall(r'"(models/[^"]+\.vmdl)"', js))):
        c, g = mdl_status(m)
        pre = [e.get('name', '#%d' % e['i']) for e in ents if (e.get('keys') or {}).get('model') == m]
        stale = c and g and os.path.getmtime(os.path.join(a.addon, m)) > os.path.getmtime(os.path.join(a.game, m + '_c'))
        ok = c and g and pre
        row('model', m, 'OK' if ok else 'MISSING', 'SetModel (CONFIG.UNIFORMS)' if m in uni_models else 'script literal', '', 'tools/soldiers.py (+ arms tools)',
            'content %s, game vmdl_c %s%s, precache %s' % ('yes' if c else 'NO', 'yes' if g else 'NO', ' (older than the .vmdl: recompile)' if stale else '',
                                                         ', '.join(pre) or 'NONE'))
    driven = {}
    rx = re.compile(r'^(tw_plane_(t|ct)_\d+|tw_prop_.*|tw_bomb_.*|tw_tracer_.*|tw_bombsight_.*|tw_gunsight_.*|woodsopen|undergroundopen|mortar_(t|ct)_\d+)$')
    for e in ents:
        m = (e.get('keys') or {}).get('model')
        if m and e.get('name') and rx.match(e['name']): driven.setdefault(m, set()).add(re.sub(r'_(t|ct)_\d+(_\d+)?$', '_<tg>_N', e['name']))
    for m in sorted(driven):
        c, g = mdl_status(m)
        st = not (c and g) and staged(m)
        row('model', m, 'OK' if (c and g) or st else 'MISSING', 'on ' + ', '.join(sorted(driven[m])), '', 'map (prop_dynamic model key)',
            ('staged in %s, not compiled yet' % a.stage) if st else 'content %s, game vmdl_c %s' % ('yes' if c else 'NO', 'yes' if g else 'NO'))

    # ---------------------------------------------------------------- sounds
    vs = os.path.join(a.addon, 'soundevents', 'soundevents_addon.vsndevts')
    vtext = open(vs, encoding='utf-8', errors='replace').read() if os.path.exists(vs) else ''
    snd_ents = {}
    srx = re.compile(r'^(tw_plane_(eng|gun|gun2|gun3)_(t|ct)_\d+|tw_launch_snd_.*|tw_boom_snd_\d+|tw_whistle_snd_\d+)$')
    for e in ents:
        sn = (e.get('keys') or {}).get('soundName')
        if sn and e.get('name') and srx.match(e['name']): snd_ents.setdefault(sn, set()).add(re.sub(r'_(t|ct)_\d+$|_\d+$', '_N', e['name']))
    for sn in sorted(snd_ents):
        m = re.search(r'^\s*"?%s"?\s*=\s*\n?\s*\{(.*?)\n\t\}' % re.escape(sn), vtext, re.S | re.M)
        if not m:
            row('sound', sn, 'MISSING', '', '', 'tools/sounds.py', 'not defined in soundevents_addon.vsndevts; on ' + ', '.join(sorted(snd_ents[sn])))
            continue
        files = re.findall(r'"(sounds/[^"]+\.vsnd)"', m.group(1))
        own = [f for f in files if f.startswith('sounds/tw/')]
        lost = [f for f in own if not any(os.path.exists(os.path.join(a.addon, f[:-5] + x)) for x in ('.wav', '.mp3'))
                or not os.path.exists(os.path.join(a.game, f + '_c'))]
        stock = [f for f in files if f not in own]
        row('sound', sn, 'MISSING' if lost else 'OK', '', '', 'tools/sounds.py', 'on %s; own files %s%s%s' % (
            ', '.join(sorted(snd_ents[sn])), ', '.join(os.path.basename(f) for f in own) or 'none',
            ('; MISSING ' + ', '.join(lost)) if lost else '', ('; %d stock vsnd (not checked offline)' % len(stock)) if stock else ''))
    g_vs = os.path.exists(os.path.join(a.game, 'soundevents', 'soundevents_addon.vsndevts_c'))
    row('file', 'soundevents/soundevents_addon.vsndevts', 'OK' if vtext and g_vs else 'MISSING', '', '', 'tools/sounds.py',
        'content %s, game vsndevts_c %s' % ('yes' if vtext else 'NO', 'yes' if g_vs else 'NO'))

    # ---------------------------------------------------------------- HUD
    xmlp = os.path.join(a.addon, 'panorama', 'layout', 'custom_game', 'mg_trenchwarfare.xml')
    cssp = os.path.join(a.addon, 'panorama', 'styles', 'custom_game', 'mg_trenchwarfare.css')
    xml = open(xmlp, encoding='utf-8').read() if os.path.exists(xmlp) else ''
    css = open(cssp, encoding='utf-8').read() if os.path.exists(cssp) else ''
    xids = set(re.findall(r'\bid="([^"]+)"', xml))
    ids = set()
    for m in re.finditer(r'\b(hText|hClass|hSwap|placeMarker)\(p, ("[^"]+")(\s*\+\s*[^,]+)?,', js):
        base = m.group(2).strip('"')
        if not m.group(3): names = [base]
        elif base == 'tw_info_l': names = ['tw_info_l%d' % k for k in range(1, 6)]
        elif base == 'tw_imp': names = ['tw_imp%d' % k for k in range(3)]
        else: problems.append('UNLISTED dynamic HUD id %s%s' % (m.group(2), m.group(3))); continue
        if m.group(1) == 'placeMarker': names = names + [n + 'y' for n in names]
        ids.update(names)
    if 'hSwap(p, id + "y"' not in js: problems.append('STALE: placeMarker no longer adds the "<id>y" panel')
    if 'placeMarker(p, "tw_imp" + i' in js and 'for (let i = 0; i < 3; i++)' not in js: problems.append('STALE: tw_imp0..2 range changed')
    miss = sorted(ids - xids)
    row('hud', 'panel ids the script sends (%d)' % len(ids), 'MISSING' if miss else 'OK', '', '%d of %d in the xml' % (len(ids) - len(miss), len(ids)),
        'tools/tw_hud.py + tw_cockpit.py', ('missing: ' + ', '.join(miss)) if miss else ', '.join(sorted(ids)))
    has_cls = lambda c: re.search(r'\.%s(?![\w-])' % re.escape(c), css) is not None
    classes = set(re.findall(r'hClass\(p, [^,]+, "([^"]+)"', js)) | set(re.findall(r'"(mc?t)"', js))   # literal classes + the sight map picture
    fams = []
    if '"a" + (((Math.round(deg / 5) % 72)' in js: fams.append(('a', 72, 'NEEDLE: dial rotation in 5-degree steps'))
    else: problems.append('STALE: NEEDLE class family changed')
    for ax in ('x', 'y'):
        if '"%s" + stepOf(' % ax in js: fams.append((ax, STEPS, 'marker %s position (TARGET_STEPS)' % ax))
        else: problems.append('STALE: marker %s class family changed' % ax)
    for c in sorted(classes):
        row('hud', 'class .%s' % c, 'OK' if has_cls(c) else 'MISSING', '', '', 'tools/tw_hud.py', 'in the css' if has_cls(c) else 'not in the css')
    for p, n, what in fams:
        lack = [p + str(i) for i in range(n) if not has_cls(p + str(i))]
        row('hud', 'classes .%s0 .. .%s%d' % (p, p, n - 1), 'MISSING' if lack else 'OK', '', '%d of %d' % (n - len(lack), n), 'tools/tw_hud.py',
            what + (('; missing ' + ', '.join(lack[:6])) if lack else ''))
    hudents = by_name.get('tw_hud', [])
    lay = (hudents[0].get('keys') or {}).get('layout', '') if hudents else ''
    want = 'panorama/layout/custom_game/mg_trenchwarfare.vxml'
    g_x = os.path.exists(os.path.join(a.game, want + '_c')); g_c = os.path.exists(os.path.join(a.game, 'panorama/styles/custom_game/mg_trenchwarfare.vcss_c'))
    row('file', want, 'OK' if lay == want and xml and css and g_x and g_c else 'MISSING', '', '', 'tools/tw_hud.py',
        'tw_hud layout key %s; content xml %s, css %s; game vxml_c %s, vcss_c %s' % (lay or 'NONE', 'yes' if xml else 'NO', 'yes' if css else 'NO',
                                                                               'yes' if g_x else 'NO', 'yes' if g_c else 'NO'))
    sc = by_name.get('tw_script', [])
    cs = (sc[0].get('keys') or {}).get('cs_script', '') if sc else ''
    src_ok = cs.endswith('.vjs') and os.path.exists(os.path.join(a.addon, cs[:-4] + '.js'))
    same = src_ok and open(os.path.join(a.addon, cs[:-4] + '.js'), encoding='utf-8').read().replace('\r\n', '\n') == js.replace('\r\n', '\n')
    g_s = cs and os.path.exists(os.path.join(a.game, cs + '_c'))
    row('file', cs or 'maps/scripts/mg_trenchwarfare.vjs', 'OK' if src_ok and g_s else 'MISSING', '', '', 'src/mg_trenchwarfare.js (build of src/modules)',
        'tw_script cs_script key; content .js %s (%s src/), game vjs_c %s' % ('yes' if src_ok else 'NO', 'same as' if same else 'DIFFERS from', 'yes' if g_s else 'NO'))

    # ---------------------------------------------------------------- console
    cv = re.search(r'CVARS:\s*\[(.*?)\]', js, re.S)
    for c in re.findall(r'"([^"]+)"', cv.group(1) if cv else ''):
        row('console', c, 'OK', '', '', 'script OnActivate', 'CONFIG.CVARS')
    if '"bot_quota_mode fill"' in js and '"bot_quota " + 2 * CONFIG.BOTS.FILL_PER_SIDE' in js:
        row('console', 'bot_quota_mode fill', 'OK', '', '', 'script OnActivate', 'when CONFIG.BOTS_ON (default true): bots fill the server, leave as humans join')
        row('console', 'bot_quota <2 x FILL_PER_SIDE>', 'OK', '', '', 'script OnActivate', 'when CONFIG.BOTS_ON: %d (FILL_PER_SIDE %d)' % (2 * cfg_num(js, 'FILL_PER_SIDE'), cfg_num(js, 'FILL_PER_SIDE')))
    else: problems.append('STALE: the bot quota commands (bot_quota_mode fill / bot_quota) changed in the script')
    for c in ('bot_quota 0', 'bot_kick'):
        if '"%s"' % c in js: row('console', c, 'OK', '', '', 'script OnActivate', 'only when CONFIG.BOTS_ON is false')
    if '"say "' in js: row('console', 'say <text>', 'OK', '', '', 'script say()', 'chat announcements (unlocks, roles)')

    # ---------------------------------------------------------------- the build must be current (only for the default script)
    if os.path.abspath(a.script) == os.path.abspath(SCRIPT):
        try:
            r = subprocess.run(['node', BUILD, os.path.join(PROJ, 'src', 'build.json'), '--check'], capture_output=True, text=True)
            if r.returncode: problems.append('STALE build: %s' % (r.stdout.strip() or r.stderr.strip())[:200])
        except OSError as e:
            print('note: node not found, build freshness not checked (%s)' % e)

    # ---------------------------------------------------------------- verdict
    known = set()
    if os.path.exists(CONTRACT):
        t = open(CONTRACT, encoding='utf-8').read()
        sec = re.search(r'^## Known missing\n(.*?)(?=^## |\Z)', t, re.S | re.M)
        if sec: known = set(re.findall(r'^- `([^`]+)`', sec.group(1), re.M))
    allrows = [(k, r) for k in rows for r in rows[k]]
    for k, r in allrows:
        if r['status'] == 'MISSING' and r['key'] not in known: problems.append('MISSING %s %s (%s)' % (k, r['key'], r['note'] or r['count']))
        if r['status'] == 'MISSING' and r['key'] in known: r['status'] = 'MISSING (known)'
    for kk in sorted(known - {r['key'] for _, r in allrows if r['status'].startswith('MISSING')}):
        print('note: %s is listed under Known missing but is not missing (or no longer a row): drop it from CONTRACT.md' % kk)
    n_ok = sum(1 for _, r in allrows if r['status'] == 'OK'); n_miss = len(allrows) - n_ok

    if a.markdown:
        heads = {'entity': ('Name', 'Class', 'Count in the vmap', 'Made by', 'Status', 'Notes'),
                 'model': ('Model', 'Use', 'Made by', 'Status', 'Notes'), 'sound': ('Sound event', 'Made by', 'Status', 'Notes'),
                 'hud': ('HUD item', 'Count', 'Made by', 'Status', 'Notes'), 'file': ('File', 'Made by', 'Status', 'Notes'),
                 'console': ('Command', 'Sent by', 'Status', 'Notes')}
        cols = {'entity': ('key', 'cls', 'count', 'who', 'status', 'note'), 'model': ('key', 'cls', 'who', 'status', 'note'),
                'sound': ('key', 'who', 'status', 'note'), 'hud': ('key', 'count', 'who', 'status', 'note'), 'file': ('key', 'who', 'status', 'note'),
                'console': ('key', 'who', 'status', 'note')}
        for k in rows:
            print('### %s\n' % k)
            print('| ' + ' | '.join(heads[k]) + ' |'); print('|' + '---|' * len(heads[k]))
            for r in rows[k]:
                print('| ' + ' | '.join(('`%s`' % r[c]) if c == 'key' else str(r[c]).replace('|', '/') for c in cols[k]) + ' |')
            print()
    else:
        for k in rows:
            for r in rows[k]:
                print('%-16s %-8s %-46s %s %s' % (r['status'], k, r['key'], r['count'], r['note'][:150]))
    print('contract: %d rows, %d OK, %d MISSING (%d known)' % (len(allrows), n_ok, n_miss, sum(1 for _, r in allrows if r['status'] == 'MISSING (known)')))
    for p in problems: print('FAIL ' + p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
