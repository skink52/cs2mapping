"""Convert a TTT map's ttt_* entities for cs2mapTTT, add the TTT entities, write the map data for ttt.js.

usage: python3 tools/ttt_convert.py <in.vmap> <out.vmap> <map name> [--cs2mapping ../cs2mapping]

CS2 has no ttt_* classes, so each one becomes a logic_relay (or nothing) and every input aimed at it is re-aimed at
ttt_script RunScriptInput "ttt:<op>:<id>". Its outputs move onto relays "<id>__<event>" that ttt.js fires with the
activator. The per-entity data (texts, roles, button spots, tester boxes, owners, credits) goes to maps/<map>.json,
which tools/build_data.py bakes into ttt.js. Re-runnable: a converted map has no ttt_* left and is only re-patched.
"""
import sys, os, json, argparse

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('map')
ap.add_argument('--cs2mapping', default=os.path.join(os.path.dirname(__file__), '..', '..', 'cs2mapping'))
ap.add_argument('--data', default=os.path.join(os.path.dirname(__file__), '..', 'maps'))
A = ap.parse_args()
sys.path.insert(0, os.path.join(A.cs2mapping, 'create'))
import dmx, vmaplib, vmapgen
from dmx import Element, T_STRING, T_INT, T_FLOAT

SCRIPT = 'ttt_script'
WEAPONS = {'weapon_ttt_knife': 'weapon_knife', 'weapon_ttt_sipistol': 'weapon_usp_silencer', 'weapon_ttt_flaregun': 'weapon_revolver',
           'weapon_ttt_teleport': 'weapon_healthshot', 'weapon_ttt_radio': 'weapon_decoy', 'weapon_ttt_decoy': 'weapon_decoy',
           'weapon_ttt_m16': 'weapon_m4a1', 'weapon_ttt_glock': 'weapon_glock', 'weapon_zm_mac10': 'weapon_mac10',
           'weapon_zm_pistol': 'weapon_fiveseven', 'weapon_zm_revolver': 'weapon_deagle', 'weapon_zm_rifle': 'weapon_ssg08',
           'weapon_zm_shotgun': 'weapon_nova', 'weapon_zm_sledge': 'weapon_negev', 'weapon_ttt_smokegrenade': 'weapon_smokegrenade',
           'weapon_zm_molotov': 'weapon_molotov', 'weapon_ttt_confgrenade': 'weapon_hegrenade'}
ROLE = {'0': 'inn', '1': 'tra', '2': 'det', '3': 'any'}
OUT_EVENT = {'ttt_traitor_button': {'OnPressed': 'pressed'}, 'ttt_traitor_check': {'TraitorsFound': 'found'},
             'ttt_logic_role': {'OnPass': 'pass', 'OnFail': 'fail'}, 'ttt_credit_adjust': {'OnSuccess': 'ok', 'OnFail': 'fail'},
             'ttt_map_settings': {'RoundStart': 'start', 'RoundPreparation': 'prep', 'RoundEnd': 'end', 'MapSettingsSpawned': 'prep'}}

d = vmapgen.open_map(A.src, '')
ents = vmapgen.entities(d)
P = lambda c: c.get('entity_properties')
cls_of = lambda c: P(c).get('classname') or ''
tmpl_conn = None
for c in ents:
    for k in c.get('connectionsData') or []:
        tmpl_conn = k; break
    if tmpl_conn: break


def conn(output, target, inp, param='', delay=0.0, times=-1):
    e = Element('DmeConnectionData', '')
    e.attrs = [['outputName', T_STRING, output], ['targetType', T_INT, 7], ['targetName', T_STRING, target],
               ['inputName', T_STRING, inp], ['overrideParam', T_STRING, param], ['delay', T_FLOAT, float(delay)],
               ['timesToFire', T_INT, int(times)]]
    return e


def set_key(c, k, v):
    P(c).set(k, T_STRING, str(v))


def drop_key(c, k):
    ep = P(c); ep.attrs = [a for a in ep.attrs if a[0] != k]


def make_relay(c, name):
    ep = P(c)
    ep.attrs = [['classname', T_STRING, 'logic_relay'], ['targetname', T_STRING, name], ['spawnflags', T_STRING, '0'],
                ['StartDisabled', T_STRING, '0']]
    c.attr('children')[2] = []


# ---------------------------------------------------------------- pass 1: name and collect the ttt entities
data = {'buttons': [], 'checks': {}, 'roles': {}, 'texts': {}, 'owners': {}, 'credits': {}, 'wins': 0, 'settings': 0, 'ptouch': {}, 'alphas': [], 'duck': 0}
ttt = {}          # targetname -> (class, node)
n_auto = 0
for c in ents:
    k = cls_of(c)
    if k in WEAPONS:
        set_key(c, 'classname', WEAPONS[k]); continue
    if not k.startswith('ttt_'): continue
    nm = P(c).get('targetname') or ''
    if not nm:
        n_auto += 1; nm = 'ttt_auto_%d' % n_auto; set_key(c, 'targetname', nm)
    if k == 'ttt_map_settings': nm = '__settings__%d' % len(ttt)
    ttt.setdefault(P(c).get('targetname'), []).append((k, c, nm))

# ---------------------------------------------------------------- pass 2: re-aim inputs at ttt entities
IN_OP = {('ttt_traitor_check', 'CheckForTraitor'): 'chk', ('ttt_traitor_check', 'Enable'): 'chkon', ('ttt_traitor_check', 'Disable'): 'chkoff',
         ('ttt_logic_role', 'TestActivator'): 'role', ('ttt_game_text', 'Display'): 'txt', ('ttt_game_text', 'Kill'): 'txtoff',
         ('ttt_damageowner', 'SetActivatorAsDamageOwner'): 'own', ('ttt_damageowner', 'ClearDamageOwner'): 'unown',
         ('ttt_credit_adjust', 'TakeCredits'): 'cred', ('ttt_traitor_button', 'Kill'): 'btnoff', ('ttt_traitor_button', 'Lock'): 'btnoff',
         ('ttt_traitor_button', 'Unlock'): 'btnon', ('ttt_traitor_button', 'Toggle'): 'btntog',
         ('ttt_win', 'TraitorWin'): 'win', ('ttt_win', 'InnocentWin'): 'win', ('ttt_win', 'Draw'): 'win'}
WIN = {'TraitorWin': 't', 'InnocentWin': 'i', 'Draw': 'd'}
rerouted, dropped = 0, []
for c in ents:
    for k in c.get('connectionsData') or []:
        t = k.get('targetName')
        if t not in ttt: continue
        cls = ttt[t][0][0]; inp = k.get('inputName')
        op = IN_OP.get((cls, inp))
        if not op:
            dropped.append('%s.%s (from %s)' % (t, inp, P(c).get('targetname') or cls_of(c)))
            k.set('targetName', T_STRING, '__ttt_dropped'); continue
        name = 'ttt:win:' + WIN[inp] if op == 'win' else 'ttt:%s:%s' % (op, t)
        k.set('targetName', T_STRING, SCRIPT); k.set('inputName', T_STRING, 'RunScriptInput'); k.set('overrideParam', T_STRING, name)
        rerouted += 1

# ---------------------------------------------------------------- pass 3: convert each ttt entity
def move_outputs(c, cls, base):
    """outputs of a ttt entity -> {event: [connections renamed OnTrigger]}"""
    ev = {}
    for k in c.get('connectionsData') or []:
        e = OUT_EVENT.get(cls, {}).get(k.get('outputName'))
        if not e: dropped.append('%s output %s' % (base, k.get('outputName'))); continue
        k.set('outputName', T_STRING, 'OnTrigger'); ev.setdefault(e, []).append(k)
    return ev


def mesh_box(c):
    lo = [1e9] * 3; hi = [-1e9] * 3
    for m in c.get('children') or []:
        if m.type != 'CMapMesh': continue
        o = m.get('origin') or (0, 0, 0)
        for s in m.get('meshData').get('vertexData').get('streams'):
            if s.get('semanticName') != 'position': continue
            for v in s.get('data'):
                for i in range(3): lo[i] = min(lo[i], v[i] + o[i]); hi[i] = max(hi[i], v[i] + o[i])
    if lo[0] > hi[0]:
        o = c.get('origin'); lo = [o[0] - 32, o[1] - 32, o[2] - 32]; hi = [o[0] + 32, o[1] + 32, o[2] + 32]
    return [round(x, 1) for x in lo], [round(x, 1) for x in hi]


def relays_for(c, base, ev, keep_node=True):
    first = True
    for e, conns in ev.items():
        name = '%s__%s' % (base, e)
        if first and keep_node:
            make_relay(c, name); c.attr('connectionsData')[2] = conns; first = False
        else:
            r = vmaplib.ent('logic_relay', c.get('origin'), group='ttt', targetname=name, spawnflags='0', StartDisabled='0')
            r.attr('connectionsData')[2] = conns
    if first and keep_node:
        make_relay(c, base + '__unused'); c.attr('connectionsData')[2] = []


settings_ev = {}
for t, lst in ttt.items():
    for cls, c, nm in lst:
        p = {a[0]: a[2] for a in P(c).attrs}
        ev = move_outputs(c, cls, nm)
        if cls == 'ttt_traitor_button':
            o = c.get('origin')
            data['buttons'].append({'id': nm, 'pos': [round(x, 1) for x in o], 'desc': p.get('description', '')[:90],
                                    'once': p.get('RemoveOnPress', '0') == '1', 'wait': float(p.get('wait', '0') or 0),
                                    'range': float(p.get('usable_range', '1024') or 1024), 'off': (int(p.get('spawnflags', '0') or 0) & 2048) != 0})
            relays_for(c, nm, ev)
        elif cls == 'ttt_traitor_check':
            lo, hi = mesh_box(c)
            data['checks'][nm] = {'mins': lo, 'maxs': hi, 'on': p.get('StartDisabled', '0') != '1'}
            relays_for(c, nm, ev)
        elif cls == 'ttt_logic_role':
            data['roles'][nm] = ROLE.get(p.get('Role', '3'), 'any'); relays_for(c, nm, ev)
        elif cls == 'ttt_game_text':
            data['texts'][nm] = {'msg': p.get('message', '')[:120], 'rcv': int(p.get('receive', '0') or 0)}; relays_for(c, nm, ev)
        elif cls == 'ttt_damageowner':
            data['owners'][nm] = {'damager': p.get('damager', ''), 'name': p.get('killname', '')[:40]}; relays_for(c, nm, ev)
        elif cls == 'ttt_credit_adjust':
            data['credits'][nm] = int(p.get('credits', '1') or 1); relays_for(c, nm, ev)
        elif cls == 'ttt_win':
            data['wins'] = 1; relays_for(c, nm, ev)
        elif cls == 'ttt_map_settings':
            data['settings'] = 1
            for e, conns in ev.items(): settings_ev.setdefault(e, []).extend(conns)
            make_relay(c, 'ttt_ms__unused'); c.attr('connectionsData')[2] = []
        else:
            dropped.append('entity %s (%s)' % (nm, cls)); relays_for(c, nm, ev)
for e, conns in settings_ev.items():
    r = vmaplib.ent('logic_relay', (0, 0, 0), group='ttt', targetname='ttt_ms__' + e, spawnflags='0', StartDisabled='0')
    r.attr('connectionsData')[2] = conns

# ---------------------------------------------------------------- map logic CS2 can't run as written (re-runnable on converted maps)
ents = vmapgen.entities(d)
by_name = {}
for c in ents:
    if P(c).get('targetname'): by_name.setdefault(P(c).get('targetname'), []).append(c)
PHYS_CLS = ('prop_physics', 'prop_physics_multiplayer', 'prop_physics_override', 'func_physbox', 'prop_physics_respawnable')
extra = {'ptouch': {}, 'alphas': [], 'duck': 0}
# 1. texts the TTT prep kills (sandbox-mode warnings): never display them from logic_auto
prep_kills = set()
for r in by_name.get('ttt_ms__prep', []):
    for k in r.get('connectionsData') or []:
        if k.get('inputName') == 'Kill': prep_kills.add(k.get('targetName'))
n_err = 0
for c in ents:
    if cls_of(c) != 'logic_auto': continue
    a = c.attr('connectionsData'); keep_c = [k for k in a[2] if not (k.get('targetName') in prep_kills and k.get('inputName') in ('Display', 'ShowMessage'))]
    n_err += len(a[2]) - len(keep_c); a[2] = keep_c
# 2. triggers filtered to one physics object (gold block into the tester): touches go through ttt.js, which also polls the object
for c in ents:
    if not cls_of(c).startswith('trigger_'): continue
    f = by_name.get(P(c).get('filtername') or '', [None])[0]
    if f is None or cls_of(f) != 'filter_activator_name' or (P(f).get('Negated') or '0') not in ('0', 'Allow entities that match criteria'): continue
    obj = P(f).get('filtername') or ''
    if not any(cls_of(o) in PHYS_CLS for o in by_name.get(obj, [])): continue
    tn = P(c).get('targetname')
    if not tn:
        k3 = 1
        while 'ttt_pt_%d' % k3 in by_name: k3 += 1
        tn = 'ttt_pt_%d' % k3; set_key(c, 'targetname', tn); by_name[tn] = [c]
    lo, hi = mesh_box(c)
    o = next(o for o in by_name[obj] if cls_of(o) in PHYS_CLS)
    olo, ohi = mesh_box(o) if any(m.type == 'CMapMesh' for m in o.get('children') or []) else (None, None)
    oc = o.get('origin')
    half = [round(max(4.0, (ohi[i] - olo[i]) / 2), 1) for i in range(3)] if olo else [16.0, 16.0, 16.0]
    off = [round((ohi[i] + olo[i]) / 2 - oc[i], 1) for i in range(3)] if olo else [0.0, 0.0, 0.0]
    extra['ptouch'][tn] = {'ent': obj, 'mins': lo, 'maxs': hi, 'half': half, 'off': off}
    a = c.attr('connectionsData')
    moved = [k for k in a[2] if k.get('outputName') == 'OnStartTouch' and k.get('overrideParam') != 'ttt:ptouch:' + tn]
    if not moved: continue
    for k in moved: k.set('outputName', T_STRING, 'OnTrigger')
    a[2] = [k for k in a[2] if k not in moved] + [conn('OnStartTouch', SCRIPT, 'RunScriptInput', 'ttt:ptouch:' + tn)]
    rel = by_name.get(tn + '__touch')
    if rel: rel[0].attr('connectionsData')[2].extend(moved)
    else:
        r = vmaplib.ent('logic_relay', c.get('origin'), group='ttt', targetname=tn + '__touch', spawnflags='0', StartDisabled='0')
        r.attr('connectionsData')[2] = moved
# 3. point_clientcommand +duck / -duck (CS2 blocks client commands) -> a crouch prompt; 4. !activator Alpha / rendermode -> ttt.js
cc = {P(c).get('targetname') for c in ents if cls_of(c) == 'point_clientcommand' and P(c).get('targetname')}
n_duck = n_alpha = 0
for c in ents:
    a = c.attr('connectionsData'); out = []
    for k in a[2] or []:
        t, inp, prm = k.get('targetName'), k.get('inputName'), (k.get('overrideParam') or '').strip()
        if t in cc and inp == 'Command' and prm in ('+duck', '-duck'):
            k.set('targetName', T_STRING, SCRIPT); k.set('inputName', T_STRING, 'RunScriptInput')
            k.set('overrideParam', T_STRING, 'ttt:duck:' + ('on' if prm == '+duck' else 'off')); n_duck += 1; extra['duck'] = 1
        elif t == '!activator' and inp == 'Alpha':
            v = max(0, min(255, int(float(prm or '255'))))
            k.set('targetName', T_STRING, SCRIPT); k.set('inputName', T_STRING, 'RunScriptInput'); k.set('overrideParam', T_STRING, 'ttt:alpha:%d' % v)
            if v not in extra['alphas']: extra['alphas'].append(v)
            n_alpha += 1
        elif t == '!activator' and inp == 'AddOutput' and prm.lower().startswith('rendermode'):
            n_alpha += 1; continue
        out.append(k)
    a[2] = out
for k2 in ('ptouch', 'alphas', 'duck'):
    if k2 == 'ptouch': data[k2] = extra[k2]
    else: data[k2] = sorted(extra[k2]) if isinstance(extra[k2], list) else extra[k2]

# ---------------------------------------------------------------- the TTT entities themselves (only those missing)
have = {(cls_of(c), P(c).get('targetname') or '') for c in vmapgen.entities(d)}
classes = {k for k, _ in have}
BODY_T, BODY_CT = 'agents/models/tm_phoenix/tm_phoenix.vmdl', 'agents/models/ctm_sas/ctm_sas.vmdl'   # real agents; characters/models/* are one-bone placeholders
add = [('point_script', 'ttt_script', dict(cs_script='maps/scripts/ttt.vjs')),
       ('custom_hud_layout', 'ttt_hud', dict(layout='panorama/layout/custom_game/ttt_hud.vxml', observable='1')),
       ('point_template', 'ttt_body_tpl', dict(Template01='ttt_body_src', spawnflags='0', asynchronous='0', timeoutInterval='0',
                                               spawnGroupType='INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP',
                                               clientOnlyEntityBehavior='CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY')),
       ('prop_ragdoll', 'ttt_body_src', dict(model=BODY_CT, solid='6')),
       ('point_template', 'ttt_body_tpl_t', dict(Template01='ttt_body_src_t', spawnflags='0', asynchronous='0', timeoutInterval='0',
                                                 spawnGroupType='INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP',
                                                 clientOnlyEntityBehavior='CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY')),
       ('prop_ragdoll', 'ttt_body_src_t', dict(model=BODY_T, solid='6'))]
for c in vmapgen.entities(d):          # older conversions used the one-bone placeholder agent (shows as a box)
    if cls_of(c) == 'prop_ragdoll' and P(c).get('targetname') in ('ttt_body_src', 'ttt_body_src_t'):
        want = BODY_T if P(c).get('targetname') == 'ttt_body_src_t' else BODY_CT
        if P(c).get('model') != want: set_key(c, 'model', want)
if 'info_map_parameters' not in classes:
    add.append(('info_map_parameters', 'ttt_params', dict(buying='3')))
spawn = next((c.get('origin') for c in ents if cls_of(c) == 'info_player_terrorist'), (0, 0, 0))
for i, (k, nm, keys) in enumerate(add):
    if (k, nm) in have: continue
    vmaplib.ent(k, (spawn[0], spawn[1], spawn[2] + 16 + 16 * i), group='ttt', targetname=nm, **keys)

# ---------------------------------------------------------------- tidy and save
reach = set(); stack = [d.elements[0]]
while stack:
    e = stack.pop()
    if id(e) in reach: continue
    reach.add(id(e))
    for a in e.attrs:
        vals = a[2] if a[1] == dmx.T_ELEMENT + dmx.ARRAY else ([a[2]] if a[1] == dmx.T_ELEMENT else [])
        stack.extend(x for x in vals if x is not None)
keep = lambda e: id(e) in reach or e.type == '$prefix_element$'
orph = [e for e in d.elements if not keep(e)]
d.elements = [e for e in d.elements if keep(e)]
vmapgen.finish(d, A.out, group=None, first_run_cleanup=False, strip_refs=())
os.makedirs(A.data, exist_ok=True)
jf = os.path.join(A.data, A.map + '.json')
if os.path.exists(jf) and not ttt:          # a re-run on a converted map: keep what the first run learnt from the ttt_* entities
    old = json.load(open(jf))
    for k in ('buttons', 'checks', 'roles', 'texts', 'owners', 'credits', 'wins', 'settings'): data[k] = old.get(k, data[k])
    for k in ('ptouch', 'alphas', 'duck'):           # rules whose source outputs the first run already rewrote
        if not data.get(k): data[k] = old.get(k, data[k])
if any(data[k] for k in data):
    json.dump(data, open(jf, 'w'), indent=1)
left = [cls_of(c) for c in vmapgen.entities(dmx.DMX.load(A.out)) if cls_of(c).startswith('ttt_') or cls_of(c).startswith('weapon_ttt')]
print('%s: %d ttt entities converted, %d inputs re-aimed at %s, %d orphan elements removed; buttons %d, testers %d, role tests %d, '
      'texts %d, owners %d, credits %d, win %d, settings %d' % (A.map, sum(len(v) for v in ttt.values()), rerouted, SCRIPT, len(orph),
      len(data['buttons']), len(data['checks']), len(data['roles']), len(data['texts']), len(data['owners']), len(data['credits']),
      data['wins'], data['settings']))
print('  sandbox texts no longer shown by logic_auto: %d, physics-object triggers polled: %d, crouch prompts: %d, alpha outputs: %d'
      % (n_err, len(data['ptouch']), n_duck, n_alpha))
for x in dropped: print('  dropped:', x)
assert not left, 'ttt classes left: %s' % left
