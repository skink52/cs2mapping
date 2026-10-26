"""Stage C of the CS:GO -> CS2 port: prefab merge + post-import fixes, done on the .vmap directly (Hammer closed).

python3 stage_c.py <addon> <local_root>
  <local_root> mirrors the PC:  <local_root>/content/<addon>/...   (content\\csgo_addons\\<addon>)
                                <local_root>/source1/maps/<addon>.vmf
Writes changed files to <local_root>/out/<addon>/... (content), <local_root>/out/<addon>_game/... (game-side files)
and <local_root>/out/<addon>_result.json (log, TO CHECK lines, file list, CS:GO archives still needed).
Step keys, in run order (run_pass.py takes any of them): merge, io, wall, equip, push, cmd, roundcfg, score, speed, gravity,
dead, sounds, doors, overlays, overlayfix, facescale, sky, skyvis, vis, beams, lights, alpha, radar, assets, matflags
(+ overlaydepth when asked). daylight is a stage_d.py pass only.
"""
import os, re, sys, json, math, glob, collections, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmf as vmfmod, vmapedit as V, gen_script, assets, vpk, sky as skymod, beams as beammod, lighting, radar, skyvis, visfit, gravity, texfix

CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'

class Ctx:
    def __init__(s, addon, root):
        s.addon = addon; s.root = root
        s.content = os.path.join(root, 'content', addon)
        s.out = os.path.join(root, 'out', addon)
        s.log = []; s.todo = []; s.files = {}   # rel path (content-relative, / separated) -> bytes
        s.script = addon + '_io_script'
        s.push = {}; s.spawn_equips = []; s.commands = []; s.scores = set(); s.speeds = set(); s.gravities = set(); s.src = None; s.cs2v = None; s.need = set(); s.asset_refs = set(); s.game_files = {}
        lp = os.path.join(root, 'content_files_%s.json' % addon)   # listing of the addon content folder on the PC
        s.pc_files = set(x.lower().replace('\\', '/') for x in json.load(open(lp))) if os.path.exists(lp) else set()
    def exists(s, rel):
        rel = rel.lower().replace('\\', '/')
        return rel in s.pc_files or rel in s.files or os.path.exists(os.path.join(s.content, rel))
    def write(s, rel, data):
        s.files[rel] = data if isinstance(data, bytes) else data.encode('utf-8')

# ------------------------------------------------------------------ prefab merge
def merge_prefabs(m, c):
    merged = []; kept = []
    def prefab_path(n):
        for name, t, v in m.E[n]['attrs']:
            if t == dmx.T_STR and v.lower().endswith(b'.vmap'): return v.decode()
        return None
    rounds = 0
    while True:
        prefabs = [(n, p) for n, p in m.walk() if m.type(n) == b'CMapPrefab' and n not in kept]
        if not prefabs or rounds > 8: break
        rounds += 1
        for n, parent in prefabs:
            rel = prefab_path(n)
            if rel is None: kept.append(n); c.todo.append('prefab node %d has no map path - left as is' % n); continue
            if 'skybox' in rel.lower():
                kept.append(n); c.todo.append('3D skybox prefab %s left as a prefab (it must stay separate)' % rel); continue
            local = os.path.join(c.content, rel.replace('\\', '/'))
            if not os.path.exists(local):
                kept.append(n); c.todo.append('prefab %s not found - left as is' % rel); continue
            pm = V.Map(local)
            for pa in (pm.doc.prefix[0] if pm.doc.prefix else []):
                if pa[0] == b'map_asset_references': c.asset_refs.update(pa[2])
            o = m.g(n, b'origin', [0, 0, 0]); a = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1])
            memo = {}; nid = [m.next_node_id()]
            new = [m.import_subtree(pm, ch, memo, nid) for ch in pm.children(pm.world)]
            if any(abs(x) > 1e-4 for x in list(o) + list(a)) or any(abs(x - 1) > 1e-4 for x in sc):
                for j in new:
                    p = m.g(j, b'origin', [0, 0, 0])
                    dmx.set_(m.E[j], b'origin', dmx.T_V3, V.xform([p[0] * sc[0], p[1] * sc[1], p[2] * sc[2]], o, a))
                    if any(a):
                        ja = m.g(j, b'angles', [0, 0, 0])
                        dmx.set_(m.E[j], b'angles', dmx.T_QANG, [ja[0] + a[0], ja[1] + a[1], ja[2] + a[2]])
                if any(a): c.todo.append('prefab %s was rotated (%s) - check its contents line up' % (rel, a))
            ch = dmx.geta(m.E[parent], b'children')
            k = ch[2].index(n); ch[2][k:k + 1] = new
            ents = sum(1 for j in new for x in [j] + [q for q, _ in m.walk(j)] if m.type(x) == b'CMapEntity')
            merged.append('%s (%d nodes, %d entities)' % (os.path.basename(rel), len(new), ents))
    c.log.append('collapsed %d prefabs into the map, world offsets kept: %s' % (len(merged), ', '.join(merged)))
    # prefix asset list: drop the merged prefab maps, add what their contents referenced
    gone = set(os.path.basename(x.split(' (')[0]).lower() for x in merged)
    targets = [m.doc.prefix[0]] if m.doc.prefix else []
    targets += [e['attrs'] for e in m.E if e['type'] == b'$prefix_element$']
    for attrs in targets:
        for pa in attrs:
            if pa[0] == b'map_asset_references':
                keep = [x for x in pa[2] if os.path.basename(x.decode()).lower() not in gone]
                pa[2] = keep + sorted(x for x in c.asset_refs if x not in keep)

# ------------------------------------------------------------------ VMF helpers
def vmf_entities(path):
    root = vmfmod.parse(open(path, encoding='utf-8', errors='replace').read())
    ents = []
    for e in root.ch:
        if e.name != 'entity': continue
        d = {k.lower(): v for k, v in e.kv}
        conns = []
        for cn in e.ch:
            if cn.name == 'connections':
                for k, v in cn.kv:
                    parts = v.split('\x1b') if '\x1b' in v else v.split(',')
                    if len(parts) >= 5:
                        conns.append((k, parts[0], parts[1], ','.join(parts[2:-2]) if '\x1b' not in v else parts[2], round(float(parts[-2] or 0), 3), int(float(parts[-1] or -1))))
        ents.append((d, conns, any(c.name == 'solid' for c in e.ch)))
    return ents

DROPPED = {'point_spotlight': 'spotlight beams', 'func_dustmotes': 'dust motes', 'func_precipitation': 'rain/snow', 'env_lightglow': 'light glows',
           'fog_volume': 'fog volumes', 'color_correction': 'colour correction', 'env_fog_controller': 'fog'}
def dropped_report(m, c, vmfpath):
    src = vmf_entities(vmfpath)
    cnt = collections.Counter(d.get('classname', '').lower() for d, _, _ in src)
    have = collections.Counter(m.cls(e).lower() for e in m.entities())
    lost = ['%d %s (%s)' % (cnt[k], k, v) for k, v in DROPPED.items() if cnt[k] and not have[k]]
    if lost: c.todo.append("the importer leaves these out (they're on its exclusion list, mostly cosmetic): " + ', '.join(lost))

def restore_io(m, c, vmfpath):
    """re-add outputs the importer dropped (compares every entity's outputs with the decompiled VMF)"""
    src = vmf_entities(vmfpath)
    def key(cls, name, o): return (cls.lower(), name.lower(), tuple(round(x) for x in o))
    idx = collections.defaultdict(list); byname = collections.defaultdict(list)
    for e in m.entities():
        idx[key(m.cls(e), m.name(e), m.origin(e))].append(e)
        if m.name(e): byname[(m.cls(e).lower(), m.name(e).lower())].append(e)
    added = 0; unmatched = 0; samples = []
    for d, conns, brush in src:
        if not conns: continue
        o = [float(x) for x in d.get('origin', '0 0 0').split()[:3]] if d.get('origin') else [0, 0, 0]
        cands = idx.get(key(d.get('classname', ''), d.get('targetname', ''), o)) or []
        if not cands and d.get('targetname'):
            cands = byname.get((d.get('classname', '').lower(), d['targetname'].lower()), [])
        if len(cands) != 1:
            # brush entities: the importer moves the origin to the mesh centre - fall back to nearest same-class unnamed one
            pool = [e for e in m.entities() if m.cls(e).lower() == d.get('classname', '').lower() and m.name(e).lower() == d.get('targetname', '').lower()]
            if pool and d.get('origin'):
                best = min(pool, key=lambda e: sum((a - b) ** 2 for a, b in zip(m.origin(e), o)))
                if sum((a - b) ** 2 for a, b in zip(m.origin(best), o)) < 64 ** 2: cands = [best]
        if len(cands) != 1: unmatched += 1; continue
        e = cands[0]
        have = collections.Counter(tuple(x.lower() if isinstance(x, str) else x for x in m.conn_tuple(cc)) for cc in m.conns(e))
        for cn in conns:
            k = tuple(x.lower() if isinstance(x, str) else x for x in cn)
            if have[k] > 0: have[k] -= 1; continue
            m.add_conn(e, *cn); added += 1
            if len(samples) < 6: samples.append('%s %s -> %s.%s(%s)' % (d.get('classname'), d.get('targetname', ''), cn[1], cn[2], cn[3]))
    c.log.append('outputs restored that the importer dropped: %d%s' % (added, (' (e.g. ' + '; '.join(samples) + ')') if samples else ''))
    if unmatched: c.todo.append('%d VMF entities with outputs could not be matched 1:1 in the vmap - their outputs were not checked' % unmatched)

# ------------------------------------------------------------------ input retargeting helper
def matches(target, names):
    t = target.lower()
    if t.endswith('*'): return [n for n in names if n.lower().startswith(t[:-1])]
    return [n for n in names if n.lower() == t]

# ------------------------------------------------------------------ entity conversions
FUNC_BRUSH_DEFAULTS = {'renderfx': 'kRenderFxNone', 'rendermode': 'kRenderNormal', 'renderamt': '255', 'rendercolor': '255 255 255',
                       'disablereceiveshadows': '0', 'InputFilter': '0', 'excludednpc': '', 'invert_exclusion': '0', 'solidbsp': '0'}

def wall_toggle(m, c):
    ws = m.by_class('func_wall_toggle')
    if not ws: return
    names = set()
    for e in ws:
        sf = int(m.P(e, 'spawnflags', '0') or 0)
        m.setp(e, 'classname', 'func_brush')
        m.setp(e, 'Solidity', '0'); m.setp(e, 'StartDisabled', '1' if sf & 1 else '0'); m.setp(e, 'spawnflags', '2')
        for k, v in FUNC_BRUSH_DEFAULTS.items():
            if m.P(e, k) is None: m.setp(e, k, v)
        if m.name(e): names.add(m.name(e))
    n = 0
    for e, cc in m.all_conns():
        t = dmx.get(cc, b'targetName').decode(); i = dmx.get(cc, b'inputName').decode()
        if matches(t, names) and i.lower() in ('turnon', 'turnoff'):
            dmx.set_(cc, b'inputName', dmx.T_STR, b'Enable' if i.lower() == 'turnon' else b'Disable'); n += 1
    c.log.append('%d func_wall_toggle -> func_brush (Solidity Toggle, StartDisabled from "Starts Invisible"); %d TurnOn/TurnOff inputs -> Enable/Disable' % (len(ws), n))

WEAPON_RE = re.compile(r'^(weapon_|item_)', re.I)
def player_equip(m, c):
    n = 0
    for e in m.by_class('game_player_equip'):
        pe = m.props(e); old = [a for a in pe['attrs'] if WEAPON_RE.match(a[0].decode())]
        if not old: continue
        slots = [a[0].decode() for a in old]
        pe['attrs'] = [a for a in pe['attrs'] if not WEAPON_RE.match(a[0].decode())]
        free = [k for k in ['weapon%d' % i for i in range(22)] if not m.P(e, k)]
        for w, k in zip(slots, free): m.setp(e, k, w.lower())
        for k in ['weapon%d' % i for i in range(22)]:
            if m.P(e, k) is None: m.setp(e, k, '')
        n += 1; c.log.append('game_player_equip %s: CS:GO keys %s -> CS2 weapon0..weapon21 slots' % (m.name(e) or '(unnamed)', slots))
    # "Use" on an equip -> TriggerForActivatedPlayer (CS2's game_player_equip has no Use input)
    eq = set(m.name(e).lower() for e in m.by_class('game_player_equip') if m.name(e))
    nu = 0
    for e, cc in m.all_conns():
        if dmx.get(cc, b'targetName').decode().lower() in eq and dmx.get(cc, b'inputName').decode().lower() == 'use':
            dmx.set_(cc, b'inputName', dmx.T_STR, b'TriggerForActivatedPlayer'); nu += 1
    if nu: c.log.append('%d Use inputs on game_player_equips -> TriggerForActivatedPlayer' % nu)
    # equips without "Use Only" ran on every spawn in CS:GO; CS2 doesn't run them, so the io script does it (OnPlayerReset)
    for e in m.by_class('game_player_equip'):
        sf = int(m.P(e, 'spawnflags', '0') or 0)
        if sf & 1 or m.name(e) == 'port_knife_equip': continue
        items = [m.P(e, 'weapon%d' % i, '') for i in range(22)]; items = [x for x in items if x]
        if not items and not sf & 2: continue
        c.spawn_equips.append({'strip': bool(sf & 2), 'items': items})
        c.log.append('game_player_equip %s ran on every spawn in CS:GO (no "Use Only"): the io script now %sgives %s on every spawn' %
                     (m.name(e) or '(unnamed)', 'strips, then ' if sf & 2 else '', ', '.join(items) or 'nothing'))

def trigger_push(m, c):
    ps = m.by_class('trigger_push')
    if not ps: return
    for e in ps:
        b = m.bounds(e)
        if b is None: c.todo.append('trigger_push %s has no mesh - skipped' % m.name(e)); continue
        pd = [float(x) for x in (m.P(e, 'pushdir', '0 0 0') or '0 0 0').split()[:3]]
        ea = m.g(e, b'angles', [0, 0, 0])
        d = V.angle_fwd([pd[0] + ea[0], pd[1] + ea[1], pd[2] + ea[2]])
        pid = str(len(c.push) + 1)
        c.push[pid] = dict(dir=[round(x, 4) + 0.0 for x in d], speed=float(m.P(e, 'speed', '0') or 0), mins=[float(x) for x in b[0]], maxs=[float(x) for x in b[1]])
        m.setp(e, 'classname', 'trigger_multiple')
        for k in ('pushdir', 'speed', 'triggeronstarttouch', 'alternateticksfix', 'FallingSpeedThreshold'): m.delp(e, k)
        m.setp(e, 'spawnflags', '4097'); m.setp(e, 'wait', '0')
        m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'PushIn_' + pid)
        m.add_conn(e, 'OnEndTouch', c.script, 'RunScriptInput', 'PushOut_' + pid)
    sp = sorted(set(v['speed'] for v in c.push.values()))
    c.log.append('%d trigger_push (speeds %s; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept' % (len(ps), sp))

def servercommand(m, c):
    sc = m.by_class('point_servercommand')
    if not sc: return
    names = set(m.name(e) for e in sc if m.name(e))
    n = 0
    for e, cc in list(m.all_conns()):
        t = dmx.get(cc, b'targetName').decode()
        if matches(t, names) and dmx.get(cc, b'inputName').decode().lower() == 'command':
            cmd = dmx.get(cc, b'overrideParam').decode()
            idx = len(c.commands); c.commands.append(cmd)
            dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
            dmx.set_(cc, b'overrideParam', dmx.T_STR, ('Cmd_%d' % idx).encode()); n += 1
            if re.match(r'\s*say\b.*\bport', cmd, re.I) and 'cs2' not in cmd.lower():
                j = len(c.commands); c.commands.append('say *** Ported to CS2 by skink52 ***')
                m.add_conn(e, dmx.get(cc, b'outputName').decode(), c.script, 'RunScriptInput', 'Cmd_%d' % j, dmx.get(cc, b'delay') + 0.1, dmx.get(cc, b'timesToFire'))
    for e in sc: m.remove_node(e)
    c.log.append('removed %d point_servercommand; %d Command outputs -> script Cmd_n (CS2 servers block point_servercommand)' % (len(sc), n))
    if any(x.lower().startswith('say') for x in c.commands): c.todo.append('chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show')

def round_setup(m, c):
    """House rule: a point_servercommand driven by a logic_auto sets mp_freezetime 0 / mp_roundtime 600 on map spawn.
    Maps with only one spawn type (only CT or only T spawns) also get a game_player_equip handing out a knife, fired OnMapSpawn.
    Runs after the 'cmd' pass so this point_servercommand is kept as a real entity."""
    if any(m.name(e) == 'port_servercommand' for e in m.by_class('point_servercommand')): return
    ct = m.by_class('info_player_counterterrorist'); t = m.by_class('info_player_terrorist')
    sp = (ct + t + m.entities())[0]; o = m.origin(sp); o = [o[0], o[1], o[2] + 96]
    m.new_entity('point_servercommand', o, {'targetname': 'port_servercommand'})
    la = m.new_entity('logic_auto', [o[0] + 32, o[1], o[2]], {'targetname': 'port_logic_auto', 'spawnflags': '1'})
    m.add_conn(la, 'OnMapSpawn', 'port_servercommand', 'Command', 'mp_freezetime 0', 0.0, -1)
    m.add_conn(la, 'OnMapSpawn', 'port_servercommand', 'Command', 'mp_roundtime 600', 0.0, -1)
    msg = 'added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600'
    have = [e for e in m.by_class('game_player_equip') if not int(m.P(e, 'spawnflags', '0') or 0) & 1 and m.name(e) != 'port_knife_equip'
            and any(m.P(e, 'weapon%d' % i, '') == 'weapon_knife' or m.P(e, 'weapon_knife') is not None for i in range(22))]
    if bool(ct) != bool(t) and have:
        msg += '; only %s spawns, but the map already has a game_player_equip giving weapon_knife on spawn (%s), so no extra knife equip' % ('CT' if ct else 'T', m.name(have[0]) or 'unnamed')
    elif bool(ct) != bool(t):
        props = {'targetname': 'port_knife_equip', 'spawnflags': '0', 'weapon0': 'weapon_knife'}
        for i in range(1, 22): props['weapon%d' % i] = ''
        m.new_entity('game_player_equip', [o[0] + 64, o[1], o[2]], props)
        m.add_conn(la, 'OnMapSpawn', 'port_knife_equip', 'TriggerForAllPlayers', '', 0.1, -1)
        msg += '; only %s spawns (%d), so game_player_equip port_knife_equip gives weapon_knife on spawn and OnMapSpawn (TriggerForAllPlayers)' % ('CT' if ct else 'T', len(ct or t))
    c.log.append(msg)

def game_score(m, c):
    gs = m.by_class('game_score')
    if not gs: return
    pts = {m.name(e): int(m.P(e, 'points', '1') or 1) for e in gs}
    n = 0
    for e, cc in m.all_conns():
        t = dmx.get(cc, b'targetName').decode()
        hit = matches(t, pts.keys())
        if hit and dmx.get(cc, b'inputName').decode().lower() == 'applyscore':
            p = pts[hit[0]]; c.scores.add(p)
            dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
            dmx.set_(cc, b'overrideParam', dmx.T_STR, ('Score_%d' % p).encode()); n += 1
    for e in gs: m.remove_node(e)
    c.log.append('removed %d game_score (not in CS2); %d ApplyScore -> script Score_n' % (len(gs), n))

def speedmod(m, c):
    sm = m.by_class('player_speedmod')
    if not sm: return
    names = set(m.name(e) for e in sm if m.name(e))
    n = 0
    for e, cc in m.all_conns():
        t = dmx.get(cc, b'targetName').decode()
        if matches(t, names) and dmx.get(cc, b'inputName').decode().lower() == 'modifyspeed':
            try: v = float(dmx.get(cc, b'overrideParam').decode() or 1)
            except ValueError: v = 1.0
            c.speeds.add(v)
            dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
            dmx.set_(cc, b'overrideParam', dmx.T_STR, ('Speed_%g' % v).encode()); n += 1
    for e in sm: m.remove_node(e)
    c.log.append('removed %d player_speedmod (dead in CS2); %d ModifySpeed outputs -> script Speed_n (speeds %s)' % (len(sm), n, sorted(c.speeds)))

def dead_entities(m, c):
    for e in m.by_class('sky_camera'):
        c.todo.append('the map had a CS:GO 3D skybox (sky_camera at %s, scale %s): its geometry is now ordinary geometry in the map and CS2 ignores sky_camera - move it to a separate skybox map + skybox_reference, or delete it' % (' '.join('%g' % x for x in m.origin(e)), m.P(e, 'scale', '16')))
    targeted = set(dmx.get(cc, b'targetName').decode().lower() for _, cc in m.all_conns())
    for e in m.by_class('env_sun'):
        m.remove_node(e); c.log.append("removed env_sun '%s' (not in CS2; light_environment draws the sun)" % m.name(e))
    targeted = set(dmx.get(cc, b'targetName').decode().lower() for _, cc in m.all_conns())
    for e in m.by_class('point_viewcontrol'):
        if not m.name(e): m.remove_node(e); c.log.append('removed unnamed point_viewcontrol (nothing could turn it on)')
        elif not any(matches(t, [m.name(e)]) for t in targeted): m.remove_node(e); c.log.append('removed point_viewcontrol %s (no output targets it)' % m.name(e))
        else: c.todo.append('point_viewcontrol %s - check it still works in CS2' % m.name(e))
    hal = m.by_class('prop_hallucination')
    if hal:
        dyn = 0
        for e in hal:
            if m.name(e) and m.name(e).lower() in targeted: m.setp(e, 'classname', 'prop_dynamic'); dyn += 1
            else: m.setp(e, 'classname', 'prop_static')
        c.log.append('%d prop_hallucination (does not spawn in CS2) -> %d prop_dynamic (targeted by I/O) + %d prop_static' % (len(hal), dyn, len(hal) - dyn))
    bs = m.by_class('func_breakable_surf')
    for e in bs:
        m.setp(e, 'classname', 'func_breakable'); m.setp(e, 'material', '0'); m.setp(e, 'health', m.P(e, 'health', '1') or '1')
    if bs: c.log.append('%d func_breakable_surf (gone in CS2) -> func_breakable, material Glass' % len(bs))
    for cl in ('env_screenoverlay', 'point_clientcommand', 'game_ui', 'logic_script', 'env_entity_igniter', 'func_precipitation', 'env_fog_controller'):
        es = m.by_class(cl)
        if es: c.todo.append('%d %s (%s) - not converted automatically, needs a look' % (len(es), cl, ', '.join(sorted(set(m.name(e) or '-' for e in es)))[:200]))
    vs = [e for e in m.entities() if m.P(e, 'vscripts')]
    if vs: c.todo.append('%d entities use VScript (vscripts key) - CS2 has no VScript, port the logic to cs_script: %s' % (len(vs), ', '.join(sorted(set(m.P(e, 'vscripts') for e in vs)))[:300]))
    inputs = collections.Counter(dmx.get(cc, b'inputName').decode() for _, cc in m.all_conns() if dmx.get(cc, b'inputName').decode().lower() in ('runscriptcode', 'runscriptfile', 'callscriptfunction'))
    if inputs: c.todo.append('VScript inputs in I/O: %s - need porting to cs_script' % dict(inputs))

# ------------------------------------------------------------------ sounds
SOUND_EVENT = '''	// %(comment)s
	"%(name)s" =
	{
		base = "%(base)s"
		volume = %(vol).2f
		use_time_volume_mapping_curve = false
		vsnd_files_track_01 = "%(vsnd)s"
		distance_volume_mapping_curve =
		[
			[
				0.0, 1.0, 0.0, 0.0,
				2.0, 3.0,
			],
			[
				%(radius).1f, %(far).1f, 0.0, 0.0,
				2.0, 3.0,
			],
		]
	}
'''
def wav_to_pcm16(data):
    """-> (new bytes, note) for a wav that isn't plain 16-bit PCM (8/24/32-bit PCM and float are re-encoded, other chunks such as cue/smpl kept),
    (None, None) when it already is, (None, reason) when it can't be converted here (ADPCM and other codecs)."""
    import struct, numpy as np
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE': return None, None
    chunks = []; i = 12
    while i + 8 <= len(data):
        cid = data[i:i + 4]; sz = struct.unpack('<I', data[i + 4:i + 8])[0]
        chunks.append([cid, data[i + 8:i + 8 + sz]]); i += 8 + sz + (sz & 1)
    fmt = next((c for c in chunks if c[0] == b'fmt '), None); dat = next((c for c in chunks if c[0] == b'data'), None)
    if not fmt or not dat: return None, None
    tag, ch, rate, _, _, bits = struct.unpack('<HHIIHH', fmt[1][:16])
    if tag == 0xFFFE and len(fmt[1]) >= 26: tag = struct.unpack('<H', fmt[1][24:26])[0]
    if tag == 1 and bits == 16: return None, None
    raw = dat[1]
    if tag == 1 and bits == 8: x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif tag == 1 and bits == 24:
        b = np.frombuffer(raw[:len(raw) // 3 * 3], np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8 >> 8).astype(np.float32) / 8388608
    elif tag == 1 and bits == 32: x = np.frombuffer(raw, '<i4').astype(np.float32) / 2147483648
    elif tag == 3 and bits == 32: x = np.frombuffer(raw, '<f4').astype(np.float32)
    elif tag == 3 and bits == 64: x = np.frombuffer(raw, '<f8').astype(np.float32)
    else: return None, 'format tag %d, %d-bit' % (tag, bits)
    dat[1] = (np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()
    fmt[1] = struct.pack('<HHIIHH', 1, ch, rate, rate * ch * 2, ch * 2, 16)
    body = b''.join(c[0] + struct.pack('<I', len(c[1])) + c[1] + (b'\0' if len(c[1]) & 1 else b'') for c in chunks)
    return b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body, '%s %d-bit -> 16-bit PCM' % ('float' if tag == 3 else 'PCM', bits)

def wav_add_cue(data):
    """a looping .wav without a cue chunk -> same wav with one cue point at the sampler loop start (or 0); None if not a RIFF wav"""
    import struct
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE': return None
    i, start = 12, 0
    while i + 8 <= len(data):
        cid = data[i:i + 4]; sz = struct.unpack('<I', data[i + 4:i + 8])[0]
        if cid == b'smpl' and sz >= 60: start = struct.unpack('<I', data[i + 8 + 44:i + 8 + 48])[0]
        i += 8 + sz + (sz & 1)
    cue = b'cue ' + struct.pack('<II', 28, 1) + struct.pack('<II4sIII', 1, start, b'data', 0, 0, start)
    body = data[12:] + cue
    return b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body

def sounds(m, c):
    ren = {}
    rp = os.path.join(c.content, 'maps', c.addon + '_sound_renames.json')
    if os.path.exists(rp):
        for old, new in json.load(open(rp)).items():
            ren['sounds/' + os.path.splitext(old.lower())[0] + '.vsnd'] = new
    have = set()
    sd = os.path.join(c.content, 'sounds')
    for dp, _, fs in os.walk(sd):
        for f in fs: have.add(os.path.relpath(os.path.join(dp, f), c.content).replace(os.sep, '/').lower())
    evp = os.path.join(c.content, 'soundevents', 'soundevents_addon.vsndevts')
    ev = open(evp, encoding='utf-8').read()
    prefix = re.sub(r'^(mg|de|jb|ba|cs|surf|bhop|kz)_', '', c.addon).replace('_', '')
    added = {}; fixed = 0; missing = set(); extracted = set(); looped = set()
    pcm_done = set(); converted = []
    for e in m.by_class('ambient_generic'):
        msg = m.P(e, 'message', '')
        if not msg or not msg.lower().endswith('.vsnd'): continue
        key = msg.lower().replace('\\', '/')
        src = ren.get(key)
        if src is None:
            base = os.path.splitext(key)[0]
            src = next((h for h in have if os.path.splitext(h)[0] == base), None)
        if src is None and c.cs2v and c.cs2v.has(key + '_c'): continue        # stock CS2 sound file
        if src is None and c.src:
            stem = 'sound/' + os.path.splitext(key[len('sounds/'):])[0]
            for ext in ('.wav', '.mp3'):
                if c.src.has(stem + ext):
                    data = c.src.read(stem + ext)
                    if data is None: break                                   # waiting on a VPK chunk
                    src = 'sounds/' + stem[len('sound/'):] + ext
                    c.write(src, data); extracted.add(src); break
        if src is None: missing.add(msg); continue
        if src.endswith('.wav') and src not in pcm_done:
            pcm_done.add(src)
            wd = c.files.get(src)
            if wd is None and os.path.exists(os.path.join(c.content, src)): wd = open(os.path.join(c.content, src), 'rb').read()
            if wd:
                nw, note = wav_to_pcm16(wd)
                if nw: c.write(src, nw); converted.append('%s (%s)' % (os.path.basename(src), note))
                elif note: c.todo.append('%s is %s, which CS2 may not compile: re-encode it as 16-bit PCM wav' % (src, note))
        vsnd = os.path.splitext(src)[0] + '.vsnd'
        evname = '%s.%s' % (prefix, re.sub(r'[^a-z0-9_]', '_', os.path.splitext(os.path.basename(src))[0].lower()).strip('_'))
        sf = int(m.P(e, 'spawnflags', '0') or 0); everywhere = bool(sf & 1)
        radius = float(m.P(e, 'radius', '1250') or 1250)
        if evname not in added:
            added[evname] = SOUND_EVENT % dict(comment='ambient_generic "%s"%s' % (m.name(e), ' (play everywhere)' if everywhere else ''),
                                               name=evname, base='amb.looping.stereo.base' if everywhere else 'amb.base', vol=min(1.0, float(m.P(e, 'health', '10') or 10) / 10),
                                               vsnd=vsnd, radius=100000.0 if everywhere else max(radius, 64), far=1.0 if everywhere else 0.0)
            if not (sf & 32):
                data = c.files.get(src)
                if data is None and os.path.exists(os.path.join(c.content, src)): data = open(os.path.join(c.content, src), 'rb').read()
                if src.endswith('.wav') and data and b'cue ' not in data and wav_add_cue(data):
                    c.write(src, wav_add_cue(data)); looped.add(src)
                elif not (src.endswith('.wav') and data and b'cue ' in data):
                    c.todo.append('ambient_generic %s is set to loop but %s has no loop cue points, so it will play once in CS2' % (m.name(e) or '(unnamed)', src))
        m.setp(e, 'message', evname); fixed += 1
    new = {k: v for k, v in added.items() if '"%s"' % k not in ev}
    if new:
        block = '\n\t///////////////////////////////////////////////////////////\n\t/////////////// MAP SOUNDS - added by the CS2 post-import clean (ambient_generic)\n\n' + '\n'.join(new.values())
        i = ev.rstrip().rfind('}')
        ev = ev[:i] + block + ev[i:]
        c.write('soundevents/soundevents_addon.vsndevts', ev)
    if fixed: c.log.append('%d ambient_generics pointed at %d new soundevents (%s) instead of raw .vsnd paths' % (fixed, len(added), ', '.join(sorted(added))))
    if extracted: c.log.append('stock CS:GO sounds extracted from the CS:GO VPK into the addon: %s' % ', '.join(sorted(extracted)))
    if converted: c.log.append('wavs re-encoded to 16-bit PCM: %s' % ', '.join(converted))
    if looped: c.log.append('looping sounds given a cue point (CS2 only loops wavs with markers; start taken from the smpl loop when there is one): %s' % ', '.join(sorted(looped)))
    if missing: c.todo.append('ambient_generic sounds not in the addon (stock CS:GO sounds or not packed in the BSP): %s' % ', '.join(sorted(missing))[:600])

# ------------------------------------------------------------------ door sounds
DOOR_KEYS = (('noise1', ('OnOpen', 'OnClose')), ('noise2', ('OnFullyOpen', 'OnFullyClosed')))
def vmf_door_sounds(vmfpath):
    """(classname, targetname, [origin or brush centre], {noise1/noise2: sound}) for every CS:GO door with sounds"""
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    out = []
    for e in root.ch:
        if e.name != 'entity' or (e.get('classname') or '').lower() not in ('func_door', 'func_door_rotating', 'func_movelinear'): continue
        snd = {k: e.get(k) for k, _ in DOOR_KEYS if e.get(k) and e.get(k) != '0'}
        if not snd: continue
        pts = [[float(x) for x in p.split()] for s in e.ch if s.name == 'solid' for f in s.ch if f.name == 'side'
               for p in re.findall(r'\(([^)]+)\)', f.get('plane', ''))]
        cen = [sum(p[i] for p in pts) / len(pts) for i in range(3)] if pts else None
        org = [float(x) for x in e.get('origin').split()[:3]] if e.get('origin') else None
        out.append((e.get('classname').lower(), e.get('targetname') or '', [x for x in (org, cen) if x], snd))
    return out

def door_sounds(m, c, vmfpath):
    """func_door / func_door_rotating noise1 (move) and noise2 (stop): the importer drops them (and CS2 plays nothing for .vsnd
    paths there), so each sound becomes a soundevent and each door gets a point_soundevent per sound (source entity = the door),
    started from the door's own outputs: OnOpen/OnClose for noise1, OnFullyOpen/OnFullyClosed for noise2."""
    if not os.path.exists(vmfpath): return
    evp = os.path.join(c.content, 'soundevents', 'soundevents_addon.vsndevts')
    ev = c.files.get('soundevents/soundevents_addon.vsndevts')
    ev = ev.decode('utf-8') if ev else open(evp, encoding='utf-8').read()
    prefix = re.sub(r'^(mg|de|jb|ba|cs|surf|bhop|kz)_', '', c.addon).replace('_', '')
    added = {}; missing = set(); unmatched = 0; k = 0; nse = 0; used = set()
    doors = [e for e in m.by_class('func_door', 'func_door_rotating', 'func_movelinear')]
    def spots(e):
        bb = m.bounds(e)
        return [m.origin(e)] + ([[(a + b) / 2 for a, b in zip(*bb)]] if bb else [])
    for cls, name, where, snd in vmf_door_sounds(vmfpath):
        pool = [e for e in doors if m.cls(e).lower() == cls and m.name(e).lower() == name.lower() and e not in used]
        best = None
        if len(pool) == 1 and name: best = pool[0]
        elif pool and where:
            d2 = lambda e: min(sum((a - b) ** 2 for a, b in zip(p, q)) for p in spots(e) for q in where)
            cand = min(pool, key=d2)
            if d2(cand) < 64 ** 2: best = cand
        if best is None: unmatched += 1; continue
        used.add(best); e = best
        for key, outs in DOOR_KEYS:
            msg = snd.get(key)
            if not msg: continue
            rel = msg.lower().replace('\\', '/'); rel = rel[len('sounds/'):] if rel.startswith('sounds/') else rel
            stem = os.path.splitext(rel)[0]
            src = next(('sounds/' + stem + x for x in ('.wav', '.mp3') if c.exists('sounds/' + stem + x)), None)
            if src is None and c.cs2v and c.cs2v.has('sounds/' + stem + '.vsnd_c'): src = 'sounds/' + stem + '.vsnd'
            if src is None and c.src:
                for x in ('.wav', '.mp3'):
                    if c.src.has('sound/' + stem + x):
                        data = c.src.read('sound/' + stem + x)
                        if data is None: break
                        src = 'sounds/' + stem + x; c.write(src, data); break
            if src is None: missing.add(msg); continue
            evname = '%s.door_%s' % (prefix, re.sub(r'[^a-z0-9_]', '_', os.path.basename(stem)).strip('_'))
            if evname not in added:
                added[evname] = SOUND_EVENT % dict(comment='func_door %s (%s)' % (key, msg), name=evname, base='amb.base', vol=1.0,
                                                   vsnd=os.path.splitext(src)[0] + '.vsnd', radius=1250.0, far=0.0)
            dn = m.name(e)
            if not dn:
                k += 1; dn = 'port_door_%d' % k; m.setp(e, 'targetname', dn)
            sp = spots(e)[-1]
            sn = '%s_%s_snd' % (dn, key)
            if not any(m.name(x) == sn for x in m.by_class('point_soundevent')):
                m.new_entity('point_soundevent', sp, {'targetname': sn, 'soundName': evname, 'sourceEntityName': dn,
                                                      'startOnSpawn': '0', 'toLocalPlayer': '0', 'stopOnNew': '1'})
                nse += 1
            for out in outs: m.add_conn(e, out, sn, 'StartSound')
    new = {kk: v for kk, v in added.items() if '"%s"' % kk not in ev}
    if new:
        block = '\n\t///////////////////////////////////////////////////////////\n\t/////////////// DOOR SOUNDS - added by the CS2 post-import clean (func_door noise1/noise2)\n\n' + '\n'.join(new.values())
        i = ev.rstrip().rfind('}')
        c.write('soundevents/soundevents_addon.vsndevts', ev[:i] + block + ev[i:])
    if added: c.log.append('door sounds: %d point_soundevents (%s), started by the doors\' OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2); %d unnamed doors named port_door_N' % (nse, ', '.join(sorted(added)), k))
    if unmatched: c.todo.append('door sounds: %d CS:GO doors with sounds could not be matched in the vmap' % unmatched)
    if missing: c.todo.append('door sounds not found in the addon, CS2 or CS:GO: %s' % ', '.join(sorted(missing)))

# ------------------------------------------------------------------ static overlays
OVERLAY_VMAT = '''// Static overlay (CS2 post-import clean, alpha taken from the original texture): transparent background via a translucency mask.
// Colour: %(col)s   Mask: %(mask)s

Layer0
{
	shader "csgo_static_overlay.vfx"

	//---- Blend Mode ----
	F_BLEND_MODE 1

	//---- Lighting ----
	F_LIT 1

	//---- Color ----
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "%(col)s"

	//---- Translucent ----
	g_flOpacityScale "1.000"
	TextureTranslucency "%(mask)s"

	//---- Normal Map ----
	TextureNormal "materials\\default\\default_normal.tga"

	//---- Roughness ----
	TextureRoughness "materials\\default\\default_rough.tga"

	//---- Metalness ----
	TextureMetalness "materials\\default\\default_metal.tga"
}
'''
def overlay_materials(m):
    mats = set()
    for n, _ in m.walk():
        if m.type(n) == b'CMapStaticOverlay':
            md = m.g(n, b'meshData')
            for x in m.g(md, b'materials') or []: mats.add(x.decode().lower())
    return sorted(mats)

def overlays(m, c, only=None):
    """only: retry just these materials (used after the assets pass, which can rebuild overlay vmats from CS:GO).
    Reads the vmat / colour texture from this run's output first, then the addon."""
    from PIL import Image
    import io as _io
    mats = only if only is not None else overlay_materials(m); done = []; skipped = []
    for mat in mats:
        vp = os.path.join(c.content, mat)
        if mat in c.files: txt = c.files[mat].decode('utf-8', 'replace')
        elif os.path.exists(vp): txt = open(vp, encoding='utf-8', errors='replace').read()
        else: skipped.append(mat + ' (vmat not in addon)'); continue
        if 'csgo_static_overlay' in txt and 'TextureTranslucency' in txt: continue
        mcol = re.search(r'TextureColor"?\s+"([^"]+)"', txt)
        if not mcol: skipped.append(mat + ' (no TextureColor)'); continue
        col = mcol.group(1); colrel = col.replace('\\', '/'); cp = os.path.join(c.content, colrel)
        if colrel in c.files: cp = _io.BytesIO(c.files[colrel])
        elif not os.path.exists(cp): skipped.append(mat + ' (colour texture %s missing)' % col); continue
        im = Image.open(cp)
        if 'A' not in im.getbands():
            skipped.append(mat + ' (texture has no alpha)'); continue
        a = im.getchannel('A')
        if a.getextrema()[0] == 255: skipped.append(mat + ' (alpha fully opaque)'); continue
        mask_rel = os.path.splitext(col)[0] + '_mask.png'
        b = _io.BytesIO(); a.convert('L').save(b, 'PNG')
        c.write(mask_rel.replace('\\', '/'), b.getvalue())
        c.write(mat, OVERLAY_VMAT % dict(col=col.replace('/', '\\'), mask=mask_rel.replace('/', '\\')))
        done.append(os.path.basename(mat))
    if done: c.log.append('%d static overlay materials -> csgo_static_overlay with translucency masks from the original alpha: %s' % (len(done), ', '.join(done)))
    c.overlay_skipped = skipped
    if skipped: c.todo.append('overlay materials not converted: %s' % '; '.join(skipped)[:800])

# ------------------------------------------------------------------ sky: env_sky material + moondomes for dropped sky brushes
SKY_VMAT = """// CS2 sky rebuilt from the CS:GO %(name)s six-face skybox, stitched into a 2:1 equirectangular panorama
// (same face/orientation convention as the mario_party / yolo / super_tower ports). Used by env_sky.

Layer0
{
    shader "sky.vfx"

    //---- Texture ----
    SkyTexture "materials\\skybox\\%(png)s.png"
}
"""
MOONDOME_VMAT = """// Moondome: mesh material that shows the sky, like legacy CS:GO toolsskybox (csgo_moondome shader:
// unlit, samples the sky cubemap by view direction, casts no shadows). Cube map = the same panorama env_sky uses,
// so it lines up with the real sky. TextureColor is a plain white tile so the cubemap shows through untinted.

Layer0
{
	shader "csgo_moondome.vfx"

	//---- Shadows ----
	F_DO_NOT_CAST_SHADOWS 1

	//---- Color ----
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "materials\\skybox\\%(png)s_moondome_color.png"

	//---- Cube Parallax ----
	g_flCubeParallax "0.000"

	//---- Fog ----
	g_bFogEnabled "0"

	//---- Texture ----
	TextureCubeMap "materials\\skybox\\%(png)s.png"
}
"""
def vmf_sky_brushes(vmfpath):
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    boxes = []; odd = 0
    solids = [s for w in root.ch if w.name == 'world' for s in w.ch if s.name == 'solid']
    solids += [s for e in root.ch if e.name == 'entity' and (e.get('classname') or '').lower() == 'func_detail' for s in e.ch if s.name == 'solid']
    for so in solids:
        sides = [sd for sd in so.ch if sd.name == 'side']
        if not sides or not all((sd.get('material') or '').lower() in ('tools/toolsskybox', 'tools/toolsskybox2d') for sd in sides): continue
        pts = []; axis_ok = True
        for sd in sides:
            p = [[float(x) for x in t.split()] for t in re.findall(r'\(([^)]*)\)', sd.get('plane'))]
            pts += p
            n = [(p[1][(k + 1) % 3] - p[0][(k + 1) % 3]) * (p[2][(k + 2) % 3] - p[0][(k + 2) % 3]) - (p[1][(k + 2) % 3] - p[0][(k + 2) % 3]) * (p[2][(k + 1) % 3] - p[0][(k + 1) % 3]) for k in range(3)]
            if sum(1 for x in n if abs(x) > 1e-6) != 1: axis_ok = False
        if not axis_ok or len(sides) != 6: odd += 1; continue
        boxes.append(([min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]))
    return boxes, odd

def sky_pass(m, c, vmfpath):
    import io as _io
    from PIL import Image
    skies = m.by_class('env_sky')
    skymat = (m.P(skies[0], 'skyname', '') if skies else '').lower().replace('\\', '/')
    png = os.path.splitext(os.path.basename(skymat))[0] if skymat else ''
    have_sky = bool(skymat) and ((c.cs2v and c.cs2v.has(skymat + '_c')) or c.exists(skymat))
    built = False
    if skymat and not have_sky and c.src:
        name = png
        faces, half = skymod.load_faces(c.src, name)
        if faces is None and half == 'need': return            # rerun after staging the VPK chunk
        if faces is None and name.endswith('_hdr'): faces, half = skymod.load_faces(c.src, name[:-4])
        if faces is None:
            c.todo.append('env_sky %s: could not rebuild (%s) - pick a stock CS2 sky' % (skymat, half))
        else:
            pano = skymod.equirect(faces, half, 2048)
            b = _io.BytesIO(); pano.save(b, 'PNG'); c.write('materials/skybox/%s.png' % png, b.getvalue())
            c.write(skymat, SKY_VMAT % dict(name=name, png=png)); built = have_sky = True
            c.log.append('env_sky %s: rebuilt from the six CS:GO faces%s' % (skymat, ' (HDR, tone mapped)' if 'hdr' in name else ''))
    boxes, odd = vmf_sky_brushes(vmfpath) if os.path.exists(vmfpath) else ([], 0)
    if not boxes:
        if odd: c.todo.append('%d non-box sky brushes in the VMF were not rebuilt as moondomes' % odd)
        return
    if not have_sky:
        c.todo.append('%d sky brushes dropped by the importer were not rebuilt - no usable sky material' % len(boxes)); return
    tm = V.Map(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'box_template.vmap'))
    tnode = tm.children(tm.world)[0]
    mdome = 'materials/skybox/%s_moondome.vmat' % png
    if not c.exists(mdome):
        c.write(mdome, MOONDOME_VMAT % dict(png=png))
        b = _io.BytesIO(); Image.new('RGB', (4, 4), (255, 255, 255)).save(b, 'PNG'); c.write('materials/skybox/%s_moondome_color.png' % png, b.getvalue())
    for mn, mx in boxes:
        memo = {}; nid = [m.next_node_id()]
        j = m.import_subtree(tm, tnode, memo, nid)
        md = m.g(j, b'meshData')
        dmx.set_(m.E[md], b'materials', dmx.ARR + dmx.T_STR, [mdome.encode()])
        dmx.set_(m.E[j], b'origin', dmx.T_V3, [0.0, 0.0, 0.0])
        for st in m.g(m.g(md, b'vertexData'), b'streams'):
            if m.E[st]['name'].startswith(b'position'):
                a = dmx.geta(m.E[st], b'data'); pts = a[2]
                ctr = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
                a[2] = [[mx[k] if p[k] > ctr[k] else mn[k] for k in range(3)] for p in pts]
        dmx.geta(m.E[m.world], b'children')[2].append(j)
    c.log.append('restored %d sky brushes (dropped by the importer) as moondome meshes using %s' % (len(boxes), mdome))
    if odd: c.todo.append('%d non-box sky brushes in the VMF were not rebuilt as moondomes' % odd)

# ------------------------------------------------------------------ visibility hints
def vis_hints(m, c, cell=512):   # unused: the old grid hints, replaced by visfit.run (the `vis` step)
    if m.by_class('visibility_hint'): return
    boxes = []
    for n, _ in m.walk():
        if m.type(n) == b'CMapMesh':
            md = m.g(n, b'meshData'); mats = [x.decode() for x in m.g(md, b'materials') or []]
            if mats and all('moondome' in x or x.startswith('materials/tools/') for x in mats): continue
            pts = m.mesh_points(n)
            if pts: boxes.append(([min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)], len(pts)))
    if not boxes: return
    lo = [min(b[0][k] for b in boxes) for k in range(3)]; hi = [max(b[1][k] for b in boxes) for k in range(3)]
    def add(mn, mx, t):
        o = [(a + b) / 2 for a, b in zip(mn, mx)]
        m.new_entity('visibility_hint', o, {'box_mins': ' '.join('%g' % (a - b) for a, b in zip(mn, o)),
                                            'box_maxs': ' '.join('%g' % (a - b) for a, b in zip(mx, o)), 'hintType': str(t)})
    add([x - 256 for x in lo], [x + 256 for x in hi], 9)
    import math as _m
    occ = collections.Counter(); dens = collections.Counter()
    for mn, mx, nv in boxes:
        r = [range(int(_m.floor(mn[k] / cell)), int(_m.floor((mx[k] - 1e-3) / cell)) + 1) for k in range(3)]
        cells = [(i, j, kk) for i in r[0] for j in r[1] for kk in r[2]]
        if len(cells) > 4000: continue                                   # giant shells (big outer walls) don't define play space
        for ce in cells: occ[ce] = 1; dens[ce] += nv / len(cells)
    left = set(occ); n3 = 0
    while left:
        i, j, k = min(left)
        x1 = i
        while (x1 + 1, j, k) in left: x1 += 1
        y1 = j
        while all((x, y1 + 1, k) in left for x in range(i, x1 + 1)): y1 += 1
        z1 = k
        while all((x, y, z1 + 1) in left for x in range(i, x1 + 1) for y in range(j, y1 + 1)): z1 += 1
        for x in range(i, x1 + 1):
            for y in range(j, y1 + 1):
                for z in range(k, z1 + 1): left.discard((x, y, z))
        add([i * cell, j * cell, k * cell], [(x1 + 1) * cell, (y1 + 1) * cell, (z1 + 1) * cell], 3); n3 += 1
    dense = [ce for ce, d in dens.items() if d > 1500]
    for i, j, k in dense: add([i * cell, j * cell, k * cell], [(i + 1) * cell, (j + 1) * cell, (k + 1) * cell], 2)
    c.log.append('visibility hints: lowest 1 (whole map incl. void), low %d (cells with geometry), medium %d (densest cells only)' % (n3, len(dense)))

# ------------------------------------------------------------------ main
def run(addon, root, passes=None):
    c = Ctx(addon, root)
    vp = os.path.join(c.content, 'maps', addon + '.vmap')
    m = V.Map(vp)
    steps = passes or ['merge', 'io', 'wall', 'equip', 'push', 'cmd', 'roundcfg', 'score', 'speed', 'gravity', 'dead', 'sounds', 'doors', 'overlays', 'overlayfix', 'facescale', 'sky', 'skyvis', 'vis', 'beams', 'lights', 'alpha', 'radar', 'assets', 'matflags']
    if 'merge' in steps: merge_prefabs(m, c)
    vmfp = os.path.join(root, 'source1', 'maps', addon + '.vmf')
    if 'io' in steps and os.path.exists(vmfp): restore_io(m, c, vmfp); dropped_report(m, c, vmfp)
    if 'wall' in steps: wall_toggle(m, c)
    if 'equip' in steps: player_equip(m, c)
    if 'push' in steps: trigger_push(m, c)
    if 'cmd' in steps: servercommand(m, c)
    if 'roundcfg' in steps: round_setup(m, c)
    if 'score' in steps: game_score(m, c)
    if 'speed' in steps: speedmod(m, c)
    if 'gravity' in steps: gravity.run(m, c)
    if 'dead' in steps: dead_entities(m, c)
    vd = os.path.join(root, 'vpk')
    if os.path.exists(os.path.join(vd, 'cs2_pak01_dir.vpk')):
        c.cs2v = vpk.VPK(os.path.join(vd, 'cs2_pak01_dir.vpk')); csgov = vpk.VPK(os.path.join(vd, 'csgo_pak01_dir.vpk'))
        arcs = {int(f[11:14]): os.path.join(vd, f) for f in os.listdir(vd) if re.match(r'csgo_pak01_\d{3}\.vpk$', f)}
        c.src = assets.Source(c, csgov, arcs)
    if 'sounds' in steps: sounds(m, c)
    if 'doors' in steps: door_sounds(m, c, vmfp)
    if 'overlays' in steps: overlays(m, c)
    if 'overlayfix' in steps or 'overlaydepth' in steps: texfix.overlay_geometry(m, c, vmfp, depth=8.0 if 'overlaydepth' in steps else None)
    if 'facescale' in steps: texfix.face_scales(m, c, vmfp)
    if 'sky' in steps: sky_pass(m, c, vmfp)
    if 'vis' in steps: visfit.run(m, c)                  # hints fitted to the play space + sky shells out of vis
    elif 'skyvis' in steps: skyvis.run(m, c)
    if 'beams' in steps: beammod.run(m, c)
    if 'lights' in steps: lighting.run(m, c)
    if 'alpha' in steps and c.src: assets.fix_alpha(m, c)
    if 'radar' in steps: radar.run(m, c, tex=radar.textures_for(c))
    if 'assets' in steps and c.src:
        assets.fix_materials(m, c, c.cs2v, c.src.vpk, c.src.arcs)
        assets.check_models(m, c, c.cs2v)
        retry = [x.split(' (')[0] for x in getattr(c, 'overlay_skipped', []) if x.endswith('(vmat not in addon)') and x.split(' (')[0] in c.files]
        if retry and 'overlays' in steps:   # overlay vmats the assets pass just rebuilt from CS:GO
            c.todo = [t for t in c.todo if not t.startswith('overlay materials not converted: ')]
            prev = [x for x in c.overlay_skipped if x.split(' (')[0] not in retry]
            overlays(m, c, retry)
            c.todo = [t for t in c.todo if not t.startswith('overlay materials not converted: ')]
            c.overlay_skipped = prev + c.overlay_skipped
            if c.overlay_skipped: c.todo.append('overlay materials not converted: %s' % '; '.join(c.overlay_skipped)[:800])
    if 'matflags' in steps: texfix.material_flags(m, c)
    if c.push or c.commands or c.scores or c.speeds or c.gravities or c.spawn_equips:
        js = gen_script.build(addon, c.script, c.push, c.commands, c.scores, c.speeds, c.gravities, c.spawn_equips)
        c.write('maps/scripts/%s_io.js' % addon, js)
        if not any(m.name(e) == c.script for e in m.by_class('point_script')):
            spawn = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + m.entities())[0]
            o = m.origin(spawn)
            m.new_entity('point_script', [o[0], o[1], o[2] + 64], {'targetname': c.script, 'cs_script': 'maps/scripts/%s_io.vjs' % addon})
            c.log.append('added point_script %s (maps/scripts/%s_io.js)' % (c.script, addon))
    c.log.append('pruned %d orphaned elements' % m.prune())
    c.write('maps/%s.vmap' % addon, m.dumps())
    import datetime
    c.write('maps/%s_cleanup_log.txt' % addon, 'CS2 post-import clean - %s (%s)\n\n' % (addon, datetime.date.today()) +
            '\n'.join('- ' + l for l in c.log) + '\n' + '\n'.join('- TO CHECK: ' + t for t in c.todo) + '\n')
    return c

if __name__ == '__main__':
    addon, root = sys.argv[1], sys.argv[2]
    c = run(addon, root)
    for rel, data in c.files.items():
        p = os.path.join(c.out, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    for rel, data in c.game_files.items():
        p = os.path.join(root, 'out', addon + '_game', rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    print('\n'.join(['- ' + l for l in c.log] + ['TO CHECK: ' + t for t in c.todo]))
    if c.need: print('NEED CS:GO archives:', sorted(c.need))
    json.dump({'log': c.log, 'todo': c.todo, 'files': sorted(c.files), 'need': sorted(c.need)}, open(os.path.join(root, 'out', addon + '_result.json'), 'w'), indent=1)
