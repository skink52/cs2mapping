"""CS:GO behaviour the importer leaves broken, fixed in the vmap's entities and I/O (stage C / stage D passes). Every pass is rerun-safe.

Ideas from Ninja-Chris's cs2-slop-porting 2026-11-24 (MIT, Ninja-Chris and skink52); written fresh here. Each pass logs to c.log / c.todo.

  lightio       lights switched by outputs: TurnOn / TurnOff -> Enable / Disable, SetPattern <S1 pattern> -> SetStyle <CS2 style name>;
                switched lights no longer client-only (Create Client-Only Entity gets no server inputs) and never Static; a light_style
                still holding a Source 1 pattern string (our runs before 25 Nov 2026) -> the CS2 style name
  telekeys      trigger_teleport UseLandmarkAngles / CheckDestIfClearForPlayer -> CS2's use_landmark_angles / check_if_dest_clear_for_player
                (the importer leaves the old names, which CS2 does not read)
  ambientstop   ambient_generic: a StopSound in front of a Kill / KillHierarchy of a looping one, and in front of a Volume 0 to one the map
                never gives a positive Volume (CS:GO's Volume 0 silenced it; CS2 passes it as an unused sound event parameter)
  defaultanim   prop_dynamic DefaultAnim (not a CS2 key: the prop stood still) -> IdleAnim, looping
  clipvphys     func_clip_vphysics faces in toolstrigger -> toolsnodraw (CS2 builds its collision from the face materials, and
                toolstrigger is non-solid there; CS:GO's clip collided with the whole brush)
  cliplayer     a brush entity made only of toolsplayerclip (func_brush / func_wall / func_wall_toggle / unbreakable func_breakable) ->
                func_clip_interaction_layer InteractsAs playerclip, InteractsWith player: on an entity CS2 ignores the clip material and
                blocks everything (mg_yolo_multigames' volleyball net clip; cs2-slop-porting's mg_mario_party cannon, checked in game)

  addoutfix     AddOutput parameters CS2 rejects ("AddOutput fired with bad string") on a named target: "health N" -> SetHealth N,
                "renderamt N" -> Alpha N, "rendercolor R G B" -> Color (SetColor on a light), "rendermode N" -> removed; an added output
                written "OnX target:input:param:delay:times" -> CS2's "OnX>target>input>param>delay>times" (the form the importer itself
                wrote on mg_50arenas). !activator ones are listed: they need the io script (cs2-gotchas)
  physwake      a sleeping func_physbox / prop_physics (Start Asleep) inside a physics-object trigger that outputs switch on: each output
                sending that trigger Enable / Toggle also sends the object Wake (CS2's trigger doesn't see a sleeping body; mg_divine)
  physboxmass   func_physbox gets its CS:GO mass by SetMass from a logic_auto on map spawn and every new round (CS2 computes its own:
                mg_hellz 10.6 kg instead of 445): vbsp's volume (visible sides 0.5 u in, approximated as volume - 0.5 x visible area)
                x the surfaceprop density (CS:GO's surfaceproperties), x massScale, capped at 50000. Template physboxes are listed only
  sharedparent  an entity parented to a name several entities share: CS:GO parented to the first of them in the VMF; that one gets
                <name>__parent, the children point at it, and every output to <name> also reaches it (mg_divine's props 500 u up). Needs the VMF

  debugwatch    (opt-in) tools/debug_watch.js as point_script debug_watch: in-game console tools dw_find / dw_class / dw_watch / dw_rel / dw_io

Usage: stage_d.py <addon> <root> lightio,telekeys,...   (`compat` = all but physboxmass and debugwatch. physboxmass runs by default in stage C,
so new builds get it; don't run it on legacy ports. debugwatch only by name; physboxmass reads CS:GO's
surfaceproperties, sharedparent the VMF)
"""
import collections, fnmatch, os, re
import dmx
from lighting import LIGHT_PATTERN_NAMES, LIGHT_STYLE_NAMES, LIGHT_STYLES

PASSES = ('lightio', 'telekeys', 'ambientstop', 'defaultanim', 'clipvphys', 'cliplayer', 'addoutfix', 'physwake', 'physboxmass', 'sharedparent', 'debugwatch')
LIGHT_CLASSES = ('light_omni2', 'light_barn', 'light_rect', 'light_capsule', 'light_spot', 'light_omni', 'light_ortho')
NODRAW = b'materials/tools/toolsnodraw.vmat'
TRIGGER = b'materials/tools/toolstrigger.vmat'
PLAYERCLIP = b'materials/tools/toolsplayerclip.vmat'


def _s(c, k): return (dmx.get(c, k) or b'').decode('utf-8', 'replace')


def _setstr(c, k, v): dmx.set_(c, k, dmx.T_STR, v.encode())


class _Names:
    """Output target -> entities, as CS2 matches them: case-insensitive here (CS:GO's matching), a trailing / embedded * as a wildcard."""
    def __init__(s, m):
        s.by = {}
        for e in m.entities():
            n = m.name(e).lower()
            if n: s.by.setdefault(n, []).append(e)
    def find(s, target):
        t = (target or '').lower()
        if not t or t.startswith('!'): return []
        if '*' in t: return [e for n, es in s.by.items() if fnmatch.fnmatchcase(n, t) for e in es]
        return s.by.get(t, [])


def _style_name(v):
    v = (v or '').strip()
    if v in LIGHT_PATTERN_NAMES: return LIGHT_PATTERN_NAMES[v]
    try: return LIGHT_STYLE_NAMES.get(int(float(v)))
    except ValueError: return None


def lightio(m, c):
    names = _Names(m)
    lights = set(m.by_class(*LIGHT_CLASSES))
    switched, n_in, n_style, n_unk = set(), 0, 0, 0
    for e, cc in m.all_conns():
        tg = [x for x in names.find(_s(cc, b'targetName')) if x in lights]
        if not tg: continue
        switched.update(tg)
        i = _s(cc, b'inputName'); il = i.lower()
        if il in ('turnon', 'turnoff'):
            _setstr(cc, b'inputName', 'Enable' if il == 'turnon' else 'Disable'); n_in += 1
        elif il == 'setpattern':
            nm = _style_name(_s(cc, b'overrideParam'))
            if nm:
                _setstr(cc, b'inputName', 'SetStyle'); _setstr(cc, b'overrideParam', nm); n_in += 1
            else: n_unk += 1
    n_cl = n_dyn = 0
    for e in lights:
        ls = (m.P(e, 'light_style', '') or '').strip()
        if ls and ls in LIGHT_PATTERN_NAMES: m.setp(e, 'light_style', LIGHT_PATTERN_NAMES[ls]); n_style += 1
        if e in switched:
            if (m.P(e, 'clientSideEntity', '0') or '0') == '1': m.setp(e, 'clientSideEntity', '0'); n_cl += 1
            if (m.P(e, 'directlight', '1') or '1') == '1': m.setp(e, 'directlight', '2'); n_dyn += 1
    c.log.append('lightio: %d light inputs renamed (TurnOn/TurnOff -> Enable/Disable, SetPattern -> SetStyle); %d switched lights no longer '
                 'client-only, %d Static -> Dynamic; %d light_style patterns -> CS2 style names' % (n_in, n_cl, n_dyn, n_style))
    if n_unk: c.todo.append('lightio: %d SetPattern outputs with a custom pattern (no CS2 style of that shape) left as they are' % n_unk)
    return n_in + n_cl + n_dyn + n_style


def telekeys(m, c):
    n = 0
    for e in m.by_class('trigger_teleport'):
        for old, new in (('UseLandmarkAngles', 'use_landmark_angles'), ('CheckDestIfClearForPlayer', 'check_if_dest_clear_for_player')):
            v = m.P(e, old)
            if v is None: continue
            v = str(v).strip() or '0'
            if (m.P(e, new, '') or '') != v: m.setp(e, new, v); n += 1
    c.log.append('telekeys: %d trigger_teleport keys copied to CS2 names (use_landmark_angles / check_if_dest_clear_for_player)' % n)
    return n


def ambientstop(m, c):
    amb, looping = set(), set()
    for e in m.by_class('ambient_generic'):
        n = m.name(e).lower()
        if not n: continue
        amb.add(n)
        try: sf = int(float(m.P(e, 'spawnflags', '0') or 0))
        except ValueError: sf = 0
        if not sf & 32: looping.add(n)        # 32 = Is NOT Looped
    if not amb: return 0
    def fnum(v):
        try: return float(v or 0)
        except ValueError: return None
    raised = {_s(cc, b'targetName').lower() for _e, cc in m.all_conns()
              if _s(cc, b'inputName').lower() == 'volume' and (fnum(_s(cc, b'overrideParam')) or 0) > 0}
    added = moved = 0
    for e in m.entities():
        a = dmx.geta(m.E[e], b'connectionsData')
        lst = a[2] if a else None
        if not lst: continue
        G = lambda ci, k: _s(m.E[ci], k)
        key = lambda ci: (G(ci, b'outputName').lower(), G(ci, b'targetName').lower(), round(dmx.get(m.E[ci], b'delay') or 0, 3))
        want = {}
        for ci in lst:
            t, i = G(ci, b'targetName').lower(), G(ci, b'inputName').lower()
            if t not in amb: continue
            if i in ('kill', 'killhierarchy') and t in looping: want.setdefault(key(ci), ci)
            elif i == 'volume' and t not in raised and fnum(G(ci, b'overrideParam')) is not None and fnum(G(ci, b'overrideParam')) <= 0:
                want.setdefault(key(ci), ci)
        if not want: continue
        have = {}
        for ci in lst:
            if G(ci, b'inputName').lower() == 'stopsound': have.setdefault(key(ci), ci)
        for k, first in want.items():
            st = have.get(k)
            if st is None:
                st = m.add_conn(e, G(first, b'outputName'), G(first, b'targetName'), 'StopSound', '', dmx.get(m.E[first], b'delay') or 0.0,
                                dmx.get(m.E[first], b'timesToFire'))
                lst = dmx.geta(m.E[e], b'connectionsData')[2]
                lst.remove(st); added += 1
            elif lst.index(st) < lst.index(first): continue
            else: lst.remove(st); moved += 1
            lst.insert(lst.index(first), st)      # in front: same-time events fire in the order they were queued
    c.log.append('ambientstop: %d StopSound added (%d moved) in front of a Kill of a looping ambient_generic / a Volume 0' % (added, moved))
    return added + moved


def defaultanim(m, c):
    n = 0
    for e in m.by_class('prop_dynamic', 'prop_dynamic_override'):
        da = (m.P(e, 'DefaultAnim', '') or '').strip()
        if da and not (m.P(e, 'IdleAnim', '') or '').strip():
            m.setp(e, 'IdleAnim', da); m.setp(e, 'IdleAnimationLoopMode', 'ANIM_LOOP_MODE_LOOPING'); n += 1
    c.log.append('defaultanim: %d prop_dynamic DefaultAnim -> IdleAnim (looping)' % n)
    if n: c.todo.append('defaultanim: %d props now play their CS:GO default animation as a looping IdleAnim: check a few in game' % n)
    return n


def _meshes(m, e):
    return [ch for ch in m.children(e) if m.type(ch) == b'CMapMesh' and m.g(ch, b'meshData') is not None]


def clipvphys(m, c):
    n_ent = n_slot = 0
    for e in m.by_class('func_clip_vphysics'):
        hit = False
        for ms in _meshes(m, e):
            md = m.E[m.g(ms, b'meshData')]
            a = dmx.geta(md, b'materials')
            if not a or not a[2]: continue
            for k, x in enumerate(a[2]):
                if x.lower().replace(b'\\', b'/') == TRIGGER: a[2][k] = NODRAW; n_slot += 1; hit = True
        n_ent += hit
    c.log.append('clipvphys: %d func_clip_vphysics with toolstrigger faces -> toolsnodraw (%d material slots)' % (n_ent, n_slot))
    if n_ent: c.todo.append('clipvphys: %d func_clip_vphysics now solid on every face: check physics props stay in and players are not blocked' % n_ent)
    return n_ent


_LAYER_INPUTS = {'enable', 'disable', 'kill', 'killhierarchy', 'setparent', 'clearparent', 'setparentattachment',
                 'setparentattachmentmaintainoffset', 'setparentmaintainoffset', 'setparentwithoffset', 'addoutput',
                 'fireuser1', 'fireuser2', 'fireuser3', 'fireuser4'}


def cliplayer(m, c):
    names = _Names(m)
    ins = {}
    for _e, cc in m.all_conns():
        for t in names.find(_s(cc, b'targetName')): ins.setdefault(t, set()).add(_s(cc, b'inputName').lower())
    done, left = 0, []
    for e in m.entities():
        cls = m.cls(e)
        if cls not in ('func_brush', 'func_wall', 'func_wall_toggle', 'func_breakable', 'func_detail_illusionary'): continue
        ms = _meshes(m, e)
        if not ms: continue
        mats = [[x.lower().replace(b'\\', b'/') for x in (m.g(m.g(x, b'meshData'), b'materials') or [])] for x in ms]
        if not all(mm and all(x == PLAYERCLIP for x in mm) for mm in mats): continue
        def num(k):
            try: return float(m.P(e, k, '0') or 0)
            except ValueError: return 0.0
        who = '%s %s' % (cls, m.name(e) or '(unnamed)')
        why = None
        if cls == 'func_breakable' and num('health') > 0: why = 'breakable'
        elif cls == 'func_brush' and (m.P(e, 'Solidity', '0') or '0').strip() == '1': why = 'never solid'
        elif cls == 'func_wall_toggle' and int(num('spawnflags')) & 1: why = 'starts hidden'
        elif ins.get(e, set()) - _LAYER_INPUTS: why = 'sent ' + ', '.join(sorted(ins[e] - _LAYER_INPUTS))
        if why: left.append('%s (%s)' % (who, why)); continue
        m.setp(e, 'csgo_classname', cls)
        m.setp(e, 'classname', 'func_clip_interaction_layer')
        m.setp(e, 'InteractsAs', 'playerclip'); m.setp(e, 'InteractsWith', 'player')
        if m.P(e, 'StartDisabled') is None: m.setp(e, 'StartDisabled', '0')
        done += 1
    c.log.append('cliplayer: %d player-clip brush entities -> func_clip_interaction_layer (stops players only)' % done)
    if left: c.todo.append('cliplayer: %d player-clip entities left as they are, still blocking physics objects and bullets: %s'
                           % (len(left), '; '.join(left[:12]) + (' ...' if len(left) > 12 else '')))
    return done


# ------------------------------------------------------------------ batch 2 (25 Nov 2026)
_ADDED_OUTPUT = re.compile(r'^(On\w+)\s+([^:>]+):([^:]*):([^:]*)(?::([^:]*))?(?::([^:]*))?$')


def addoutfix(m, c):
    names = _Names(m)
    n = collections.Counter(); left = collections.Counter(); drop = []
    for e, cc in list(m.all_conns()):
        if _s(cc, b'inputName').lower() != 'addoutput': continue
        t = _s(cc, b'targetName'); p = _s(cc, b'overrideParam').strip()
        mo = _ADDED_OUTPUT.match(p)
        if mo:
            f = [x if x is not None else d for x, d in zip(mo.groups(), ('', '', '', '', '0', '-1'))]
            _setstr(cc, b'overrideParam', '>'.join(x.strip() for x in f)); n['added outputs -> ">" form'] += 1; continue
        head, _, rest = p.partition(' ')
        key = head.lower(); rest = rest.strip()
        if key not in ('health', 'renderamt', 'rendercolor', 'rendermode'): continue
        if t.startswith('!'): left['%s %s' % (t, key)] += 1; continue
        if key == 'health': _setstr(cc, b'inputName', 'SetHealth'); _setstr(cc, b'overrideParam', rest); n['health -> SetHealth'] += 1
        elif key == 'renderamt': _setstr(cc, b'inputName', 'Alpha'); _setstr(cc, b'overrideParam', rest); n['renderamt -> Alpha'] += 1
        elif key == 'rendercolor':
            light = any(m.cls(x) in LIGHT_CLASSES for x in names.find(t))
            _setstr(cc, b'inputName', 'SetColor' if light else 'Color'); _setstr(cc, b'overrideParam', rest)
            n['rendercolor -> ' + ('SetColor (light)' if light else 'Color')] += 1
        else: drop.append((e, cc)); n['rendermode removed (CS2 has no input for it)'] += 1
    for e, cc in drop:
        a = dmx.geta(m.E[e], b'connectionsData')
        a[2][:] = [x for x in a[2] if m.E[x] is not cc]
    c.log.append('addoutfix: ' + (', '.join('%d %s' % (v, k) for k, v in sorted(n.items())) or 'nothing to change'))
    if left: c.todo.append('addoutfix: AddOutputs on !activator / !self that CS2 rejects, left for the io script: '
                           + ', '.join('%d %s' % (v, k) for k, v in sorted(left.items())))
    return sum(n.values())


def _sf(m, e):
    try: return int(float(m.P(e, 'spawnflags', '0') or 0))
    except ValueError: return 0


def physwake(m, c):
    names = _Names(m)
    sleepers = [e for e in m.by_class('func_physbox', 'func_physbox_multiplayer') if _sf(m, e) & 4096]
    sleepers += [e for e in m.entities() if m.cls(e).startswith('prop_physics') and _sf(m, e) & 1]
    if not sleepers: return 0
    where = {}
    for e in sleepers:
        b = m.bounds(e)
        where[e] = [(b[0][k] + b[1][k]) / 2 for k in range(3)] if b else m.origin(e)
    trig = {}
    for t in m.entities():
        if not m.cls(t).startswith('trigger_') or not _sf(m, t) & 8 or not m.name(t): continue
        b = m.bounds(t)
        if not b: continue
        inside = [e for e, p in where.items() if all(b[0][k] - 1 <= p[k] <= b[1][k] + 1 for k in range(3))]
        if inside: trig[t] = inside
    added = named = 0
    for e, cc in list(m.all_conns()):
        if _s(cc, b'inputName').lower() not in ('enable', 'toggle'): continue
        for t in names.find(_s(cc, b'targetName')):
            for obj in trig.get(t, []):
                nm = m.name(obj)
                if not nm:
                    named += 1; nm = 'port_sleeper_%d' % named
                    while names.find(nm): named += 1; nm = 'port_sleeper_%d' % named
                    m.setp(obj, 'targetname', nm); names.by.setdefault(nm, []).append(obj)
                o, d, tm = _s(cc, b'outputName'), dmx.get(cc, b'delay') or 0.0, dmx.get(cc, b'timesToFire')
                if any(m.conn_tuple(x)[:3] == (o, nm, 'Wake') for x in m.conns(e)): continue
                m.add_conn(e, o, nm, 'Wake', '', d, tm); added += 1
    c.log.append('physwake: %d Wake outputs added beside Enable / Toggle of physics-object triggers over sleeping objects (%d objects named port_sleeper_N)' % (added, named))
    return added


_SURF_CACHE = {}
CSGO_DIR = os.environ.get('CSGO_DIR', r'C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/csgo')


def _csgo_read(c, rel):
    """A CS:GO file: the stage's CS:GO source (c.src / embedded files), else CSGO_DIR loose, else CSGO_DIR's pak01."""
    import texfix
    rel = rel.replace(chr(92), '/').lower()
    raw = None
    try: raw = texfix._read_src(c, rel)
    except Exception: pass
    if raw is None and os.path.exists(os.path.join(CSGO_DIR, rel)): raw = open(os.path.join(CSGO_DIR, rel), 'rb').read()
    if raw is None and os.path.exists(os.path.join(CSGO_DIR, 'pak01_dir.vpk')):
        try:
            if 'vpk' not in _SURF_CACHE:
                import vpk, glob
                _SURF_CACHE['vpk'] = (vpk.VPK(os.path.join(CSGO_DIR, 'pak01_dir.vpk')),
                                      {int(x[-7:-4]): x for x in glob.glob(os.path.join(CSGO_DIR, 'pak01_[0-9][0-9][0-9].vpk'))})
            v, arcs = _SURF_CACHE['vpk']
            if v.has(rel): raw = v.read(rel, arcs)
        except Exception: raw = None
    return raw


def _surface_props(c):
    """CS:GO surfaceproperties: name -> (density kg/m^3, thickness in), inherited through "base". {} when no CS:GO files are reachable."""
    if 'd' in _SURF_CACHE: return _SURF_CACHE['d']
    read = lambda rel: _csgo_read(c, rel)
    man = read('scripts/surfaceproperties_manifest.txt')
    raw = {}
    for f in re.findall(r'"file"\s+"([^"]+)"', man.decode('latin1')) if man else []:
        t = read(f.replace('\\', '/'))
        if not t: continue
        t = re.sub(r'//[^\n]*', '', t.decode('latin1'))
        for name, body in re.findall(r'"?([A-Za-z0-9_\-]+)"?\s*\{([^{}]*)\}', t):
            raw[name.lower()] = {k.lower(): v for k, v in re.findall(r'"?([A-Za-z_]+)"?\s+"([^"]*)"', body)}
    def res(n, key, seen=()):
        kv = raw.get(n)
        if kv is None or n in seen: return None
        if key in kv:
            try: return float(kv[key])
            except ValueError: return None
        return res(kv.get('base', '').lower(), key, seen + (n,))
    d = {n: (res(n, 'density') or 2000.0, res(n, 'thickness') or 0.0) for n in raw}
    _SURF_CACHE['d'] = d
    return d


def _mesh_volume(m, node):
    """(volume in cubic units with the node's scales, visible (non-tool) area, visible area per material) of one mesh"""
    import splitfaces as sf, numpy as np
    polys, mats = sf.mesh_read(m, node)
    S = np.array([float(x) for x in (m.g(node, b'scales', [1, 1, 1]) or [1, 1, 1])])
    vol = vis = 0.0; use = collections.Counter()
    for p in polys:
        P = [k['pos'] * S for k in p['corners']]
        for a in range(1, len(P) - 1): vol += float(np.dot(P[0], np.cross(P[a], P[a + 1]))) / 6.0
        mi = p['attrs'].get('materialindex:0')
        try: mt = mats[int(mi)] if mi is not None else ''
        except (IndexError, ValueError, TypeError): mt = ''
        if mt and '/tools' not in mt.lower():
            nn = np.zeros(3)
            for a in range(len(P)): nn += np.cross(P[a], P[(a + 1) % len(P)])
            ar = float(np.linalg.norm(nn)) / 2.0
            vis += ar; use[mt.lower()] += ar
    return abs(vol), vis, use


PHYSBOX_SHRINK = 0.5      # vbsp (utils/vbsp/ivp.cpp) moves every visible side of a brush entity 0.5 u in before taking the collision volume


def physboxmass(m, c):
    import texfix
    surf = _surface_props(c)
    tmpl = {(m.P(t, 'Template%02d' % k, '') or '').lower() for t in m.by_class('point_template') for k in range(1, 17)} - {''}
    names = _Names(m)
    sets, skipped, n_named, guessed = [], [], 0, 0
    for e in m.by_class('func_physbox'):
        if m.name(e).lower() in tmpl: skipped.append(m.name(e)); continue
        vol = vis = 0.0; use = collections.Counter()
        for ms in _meshes(m, e):
            try: v, a, u = _mesh_volume(m, ms)
            except Exception: continue
            vol += v; vis += a; use.update(u)
        if vol <= 0: continue
        by = collections.Counter()
        for mat, a in use.items():
            vmt = (mat[:-5] if mat.endswith('.vmat') else mat) + '.vmt'
            _sh, kv = texfix.load_vmt(c, vmt)
            if not kv:
                raw = _csgo_read(c, vmt)
                kv = texfix._vmt_kv(raw)[1] if raw else {}
                if kv.get('include') and not kv.get('$surfaceprop'):
                    r2 = _csgo_read(c, kv['include']); kv = {**(texfix._vmt_kv(r2)[1] if r2 else {}), **kv}
            by[((kv or {}).get('$surfaceprop') or 'default').lower()] += a
        sp = by.most_common(1)[0][0] if by else 'default'
        if sp in surf: dens, thick = surf[sp]
        else: dens, thick = surf.get('default', (2000.0, 0.0)); guessed += sp != 'default' or not surf
        mass = vis * thick * 0.0254 ** 3 * dens if thick > 0 else max(vol - PHYSBOX_SHRINK * vis, vol * 0.25) * 0.0254 ** 3 * dens
        try: msc = float(m.P(e, 'massScale', '0') or 0)
        except ValueError: msc = 0.0
        mass = min(mass, 50000.0)
        if msc > 0: mass = min(mass * msc, 50000.0)
        mass = max(mass, 1.0)
        if not m.name(e):
            n_named += 1
            while names.find('port_physbox_%d' % n_named): n_named += 1
            m.setp(e, 'targetname', 'port_physbox_%d' % n_named); names.by.setdefault('port_physbox_%d' % n_named, []).append(e)
        elif len(names.find(m.name(e))) > 1:
            skipped.append(m.name(e) + ' (shared name)'); continue
        sets.append((m.name(e), round(mass, 1), sp))
    if skipped: c.todo.append('physboxmass: %d physboxes left at CS2\'s own mass (template / shared name): %s' % (len(skipped), ', '.join(skipped[:10])))
    if not sets: return 0
    la = [e for e in m.by_class('logic_auto') if m.name(e) == 'port_physbox_mass']
    la = la[0] if la else m.new_entity('logic_auto', [0, 0, 0], {'targetname': 'port_physbox_mass', 'spawnflags': '0'})
    a = dmx.geta(m.E[la], b'connectionsData')
    if a and a[2]: a[2][:] = []                     # a rerun rebuilds the list
    for nm, mass, _sp in sets:
        for out in ('OnMapSpawn', 'OnMultiNewRound'): m.add_conn(la, out, nm, 'SetMass', '%g' % mass, 0.0, -1)
    c.log.append('physboxmass: %d func_physbox get their CS:GO mass by SetMass (logic_auto port_physbox_mass; %d unnamed ones named port_physbox_N)%s: %s'
                 % (len(sets), n_named, '; %d with no known surfaceprop used density 2000' % guessed if guessed else '',
                    ', '.join('%s %g kg (%s)' % x for x in sets[:12]) + (' ...' if len(sets) > 12 else '')))
    c.todo.append('physboxmass: %d physboxes now weigh what CS:GO computed: check they still move / break / float as in CS:GO' % len(sets))
    return len(sets)


def sharedparent(m, c, vmfpath=None):
    vmfpath = vmfpath or os.path.join(c.root, 'source1', 'maps', c.addon + '.vmf')
    if not os.path.exists(vmfpath): c.log.append('sharedparent: no VMF (%s)' % vmfpath); return 0
    import vmf as vmfmod
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    first = {}
    for ve in root.ch:
        if ve.name != 'entity': continue
        nm = (ve.get('targetname') or '').lower()
        if nm and nm not in first:
            try: first[nm] = ((ve.get('classname') or '').lower(), [float(x) for x in (ve.get('origin') or '0 0 0').split()])
            except ValueError: first[nm] = None
    names = _Names(m)
    children = collections.defaultdict(list)
    for e in m.entities():
        pn = (m.P(e, 'parentname', '') or '').split(',')[0]
        if pn and '*' not in pn and len(names.find(pn)) > 1: children[pn.lower()].append(e)
    done, left = 0, []
    for pn, kids in children.items():
        f = first.get(pn)
        cand = [x for x in names.find(pn) if f and m.cls(x).lower() == f[0] and sum((a - b) ** 2 for a, b in zip(m.origin(x), f[1])) < 4.0]
        if len(cand) != 1: left.append(pn); continue
        par = cand[0]; old = m.name(par); new = old + '__parent'
        m.setp(par, 'targetname', new)
        for k in kids:
            parts = (m.P(k, 'parentname', '') or '').split(',', 1)
            m.setp(k, 'parentname', ','.join([new] + parts[1:]))
        for e, cc in list(m.all_conns()):
            if _s(cc, b'targetName').lower() == pn:
                o, t, i, p, d, tm = m.conn_tuple(cc)
                if not any(m.conn_tuple(x)[:4] == (o, new, i, p) for x in m.conns(e)): m.add_conn(e, o, new, i, p, d, tm)
        done += 1
        c.log.append('sharedparent: the %s %s CS:GO parented %d entities to -> %s (outputs to %s copied to it)' % (m.cls(par), old, len(kids), new, old))
    if left: c.todo.append('sharedparent: parent names shared by several entities with no single first-in-VMF match (left): %s' % ', '.join(left[:12]))
    return done


def debugwatch(m, c):
    """Opt-in: tools/debug_watch.js (dw_find / dw_class / dw_watch / dw_rel / dw_io console tools, sv_cheats 1) into the map as point_script
    debug_watch. For checking a port in game; delete the entity before publishing."""
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_watch.js'), encoding='utf-8').read()
    c.write('maps/scripts/debug_watch.js', js)
    if not m.by_class('point_script') or not any(m.name(e) == 'debug_watch' for e in m.by_class('point_script')):
        sp = (m.by_class('info_player_counterterrorist') + m.by_class('info_player_terrorist') + list(m.entities()))[0]
        o = m.origin(sp)
        m.new_entity('point_script', [o[0], o[1], o[2] + 80], {'targetname': 'debug_watch', 'cs_script': 'maps/scripts/debug_watch.vjs'})
    c.todo.append('debugwatch: point_script debug_watch added (console dw_find / dw_watch / dw_rel / dw_io with sv_cheats 1): delete it before publishing')
    return 1


OPT_IN = ('physboxmass', 'debugwatch')     # not in `compat`: physboxmass is in stage C's default list (new builds only; skink52 25 Nov 2026: never on
                                           # legacy ports through stage D), debugwatch is a test tool


def run(m, c, passes):
    if 'compat' in passes: passes = set(passes) | (set(PASSES) - set(OPT_IN))
    n = 0
    for p in PASSES:
        if p in passes:
            try: n += globals()[p](m, c)
            except Exception as ex: c.todo.append('%s failed: %s: %s' % (p, type(ex).__name__, ex))
    return n
