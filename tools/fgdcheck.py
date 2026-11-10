"""Read-only entity and asset validation of a .vmap against the installed CS2 FGDs (keys, values, I/O, targets, assets).

  python fgdcheck.py <map.vmap> [--json] [--no-assets] [--addon NAME] [--only code,code] [--limit N]

Never writes the map. Exit 0 = no errors, 1 = errors found, 2 = bad arguments / unreadable map.
Report lines are SEVERITY<tab>CODE<tab>text (or one JSON object with --json: {map, counts, findings, summary}).

  error    unknown_class      a class no installed FGD defines (does nothing in game)
  error    excluded_class     a class CS2's FGDs remove with @exclude
  error    bad_output         an output the entity's class doesn't have
  error    bad_input          an input none of the target's classes has
  error    dangling_target    an output aimed at a name nothing in the map has
  error    missing_asset      a model / material / particle / script a key names, found neither in the addon (source or compiled) nor in CS2
  warning  missing_material   a mesh face material that exists nowhere (draws as error checkerboard)
  warning  unknown_key        a key the class doesn't define (typo, or left over from CS:GO; the engine ignores it)
  warning  bad_value          a value that doesn't parse as the key's type (integer, float, boolean, colour, vector)
  warning  bad_choice         a value outside the key's choice list
  warning  key_target         a target / parent / filter key naming nothing in the map
  info     unknown_flags      spawnflags bits the class doesn't define

Differences from tools/mapcheck.py (which fixes things, with an out path): this one never fixes, and it adds the key, value, key-target and
asset checks. Asset lookup: <addon content>/<path> (source; .vjs -> .js, .vsnd -> .wav/.mp3, .vxml -> .xml), <addon game>/<path>_c,
<CS2>/game/csgo/<path>_c and the game/csgo and game/core pak01 VPK directories. The addon is the folder above maps/, or --addon.

Ideas (FGD-driven key checks, missing-asset check) from cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), check_map;
fresh code on skink52's tools (vmapedit, vpk, fgdcat).
"""
import argparse, collections, fnmatch, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, fgdcat, vmapedit as V

# Keys Hammer writes on entities that the FGDs don't declare for every class (measured on skink52's ports and original maps).
COMMON_KEYS = {'classname', 'targetname', 'origin', 'angles', 'scales', 'hammeruniqueid', 'parentname', 'parentattachmentname',
               'uselocaloffset', 'local.origin', 'local.angles', 'local.scales', 'vscripts', 'spawnflags', 'globalname',
               'fademindist', 'fademaxdist', 'nearclipplane', 'mincpulevel', 'maxcpulevel', 'mingpulevel', 'maxgpulevel',
               'disablex360', 'lightgroup', 'object_culling', 'disablereceiveshadows', 'lightmapstatic'}
# game_player_equip takes item names as keys (weapon_ak47 "1")
PREFIX_KEYS = {'game_player_equip': ('weapon_', 'item_', 'ammo_')}
ASSET_EXT = ('.vmdl', '.vmat', '.vpcf', '.vtex', '.vsnd', '.vpost', '.vjs', '.vxml', '.vcss', '.vsmart', '.vdata', '.vsnap', '.vmap', '.vnmskel')
ASSET_TYPES = ('studio', 'model', 'material', 'sprite', 'particlesystem', 'decal')
SOURCE_ALT = {'.vjs': ('.js',), '.vsnd': ('.wav', '.mp3'), '.vxml': ('.xml',), '.vcss': ('.css',)}
TARGET_TYPES = ('target_destination', 'target_name_or_class', 'filterclass')
SPECIAL_TARGETS = {'!activator', '!caller', '!self', '!player', '!pvsplayer', '!picker', '!speechtarget', '!target'}
DYNAMIC_INPUTS = {'runscriptinput', 'runscriptcode', 'callscriptfunction', 'addoutput', 'fireuser1', 'fireuser2', 'fireuser3',
                  'fireuser4', 'kill', 'killhierarchy', 'addcontext', 'removecontext', 'clearcontext', 'setparent', 'clearparent',
                  'setparentattachment', 'setparentattachmentmaintainoffset', 'dispatcheffect', 'dispatchresponse', 'use'}
SEVERITY = {'unknown_class': 'error', 'excluded_class': 'error', 'bad_output': 'error', 'bad_input': 'error',
            'dangling_target': 'error', 'missing_asset': 'error', 'missing_material': 'warning', 'unknown_key': 'warning',
            'bad_value': 'warning', 'bad_choice': 'warning', 'key_target': 'warning', 'unknown_flags': 'info'}

_INT = re.compile(r'^\s*[-+]?\d+\s*$')
_NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'


def _floats(v, n):
    parts = v.replace(',', ' ').split()
    if len(parts) != n: return None
    try: return [float(p) for p in parts]
    except ValueError: return None


def value_problem(key, v):
    """-> (code, why) when value v doesn't fit the key's type, else None. Empty values are always fine."""
    t = key.type; s = v.strip()
    if s == '': return None
    if t in ('integer', 'int', 'node_id'):
        try: f = float(s)
        except ValueError: return ('bad_value', 'not a whole number')
        return None if f == int(f) else ('bad_value', 'not a whole number')
    if t == 'float':
        try: float(s); return None
        except ValueError: return ('bad_value', 'not a number')
    if t in ('boolean', 'bool'):
        return None if s.lower() in ('0', '1', 'true', 'false', 'yes', 'no') else ('bad_value', 'not a boolean (0/1)')
    if t in ('color255', 'color255alpha'):
        parts = s.split()
        if len(parts) not in (3, 4): return ('bad_value', 'a colour is "r g b" or "r g b a"')
        try: nums = [float(p) for p in parts]
        except ValueError: return ('bad_value', 'colour parts are not numbers')
        if any(x < 0 or x > 255 for x in nums[:3]): return ('bad_value', 'colour part outside 0-255')
        return None
    if t in ('vector', 'angle', 'local_point', 'world_point', 'vecline', 'localaxis'):
        return None if _floats(s, 3) else ('bad_value', 'not three numbers')
    if t == 'vector2d':
        return None if _floats(s, 2) else ('bad_value', 'not two numbers')
    if t in ('choices', 'intchoices', 'floatchoices') and key.choices:
        vals = [c[0] for c in key.choices]
        if t == 'choices':
            ok = s.lower() in {x.lower() for x in vals}
            # named enums (kRenderNormal, PM_NORMAL) also load from their index, which the importer and older Hammer write
            # (renderfx mixes the two: 15 names, then "15", "16", "23" ...)
            if not ok and _INT.match(s): ok = 0 <= int(s) < sum(not _INT.match(x) for x in vals)
        else:
            try: ok = float(s) in {float(x) for x in vals if re.fullmatch(_NUM, x.strip())}
            except ValueError: ok = False
        return None if ok else ('bad_choice', 'not one of %s' % ', '.join(vals[:12]) + (' ...' if len(vals) > 12 else ''))
    return None


class Assets:
    """does an asset exist anywhere the game would find it? (exact paths only: never a recursive search)"""
    def __init__(s, cs2, addon):
        s.cs2, s.addon = cs2, addon
        s.content = os.path.join(cs2, 'content', 'csgo_addons', addon) if addon else None
        s.game = os.path.join(cs2, 'game', 'csgo_addons', addon) if addon else None
        s.vpks = []
        import vpk
        for sub in ('csgo', 'core'):
            p = os.path.join(cs2, 'game', sub, 'pak01_dir.vpk')
            if os.path.exists(p):
                try: s.vpks.append(vpk.VPK(p))
                except Exception: pass
        s.cache = {}

    def exists(s, rel):
        rel = rel.strip().replace('\\', '/').lstrip('/')
        low = rel.lower()
        if low in s.cache: return s.cache[low]
        base, ext = os.path.splitext(rel)
        cands = []
        if s.content:
            cands.append(os.path.join(s.content, rel))
            cands += [os.path.join(s.content, base + e) for e in SOURCE_ALT.get(ext.lower(), ())]
        if s.game: cands.append(os.path.join(s.game, rel + '_c'))
        cands.append(os.path.join(s.cs2, 'game', 'csgo', rel + '_c'))
        ok = any(os.path.exists(c) for c in cands) or any(v.has(rel + '_c') or v.has(rel) for v in s.vpks)
        s.cache[low] = ok
        return ok


def addon_of(path):
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    low = [p.lower() for p in parts]
    if 'csgo_addons' in low:
        i = len(low) - 1 - low[::-1].index('csgo_addons')
        if i + 1 < len(parts): return parts[i + 1]
    if len(parts) > 2 and low[-2] == 'maps': return parts[-3]     # <addon>/maps/<map>.vmap reached through a junction
    return None


def _mesh_materials(m):
    """{material: number of mesh nodes using it}"""
    out = collections.Counter()
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None: continue
        for x in m.g(md, b'materials') or []:
            out[x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else str(x)] += 1
    return out


def _all_props(m, e):
    out = {}
    for a in m.props(e)['attrs']:
        k = a[0].decode('utf-8', 'replace') if isinstance(a[0], (bytes, bytearray)) else str(a[0])
        v = a[2]
        if isinstance(v, (bytes, bytearray)): v = v.decode('utf-8', 'replace')
        elif isinstance(v, (list, tuple)): v = ' '.join('%g' % x if isinstance(x, float) else str(x) for x in v)
        else: v = str(v)
        out[k] = v
    return out


def _matches(target, names):
    t = target.lower()
    if t.endswith('*'): return any(n.startswith(t[:-1]) for n in names)
    if any(ch in t for ch in '*?['): return any(fnmatch.fnmatchcase(n, t) for n in names)
    return t in names


def check(m, cat, assets=None):
    """-> list of findings {severity, code, node, cls, name, at, text}"""
    found = []
    ents = m.entities()
    info = []
    for e in ents:
        p = _all_props(m, e)
        info.append((e, p, (p.get('classname') or '').lower(), (p.get('targetname') or '').lower()))
    names = {n for _, _, _, n in info if n}
    classes_present = {c for _, _, c, _ in info}
    by_name = collections.defaultdict(set)
    for _, _, c, n in info:
        if n: by_name[n].add(c)

    def add(code, e, cls, name, text, key=None):
        f = {'severity': SEVERITY[code], 'code': code, 'node': m.g(e, b'nodeID') if e is not None else None, 'cls': cls,
             'name': name, 'text': text}
        if e is not None: f['at'] = [round(x, 1) for x in m.origin(e)]
        if key: f['key'] = key
        found.append(f)

    def target_classes(t):
        tl = t.lower()
        if tl.endswith('*') or any(ch in tl for ch in '?['):
            return set().union(*[cs for n, cs in by_name.items() if _matches(tl, {n})] or [set()])
        if tl in by_name: return by_name[tl]
        return {tl} if tl in classes_present else set()

    for e, p, cls, name in info:
        nm = p.get('targetname') or '(unnamed)'
        if not cat.is_entity(cls):
            if cls in cat.excluded:
                add('excluded_class', e, cls, nm, '%s %s: CS2 removes this class (@exclude)' % (cls, nm))
            else:
                sim = cat.similar(cls, 3)
                add('unknown_class', e, cls, nm, '%s %s: no installed FGD defines this class%s' % (cls, nm, ('; similar: ' + ', '.join(sim)) if sim else ''))
            continue
        keys = cat.keys(cls); helpers = cat.helper_keys(cls)
        prefixes = PREFIX_KEYS.get(cls, ())
        for k, v in p.items():
            lk = k.lower()
            key = keys.get(lk)
            if key is None:
                if lk in COMMON_KEYS or lk in helpers or (prefixes and lk.startswith(prefixes)): continue
                add('unknown_key', e, cls, nm, '%s %s: key %s = "%s" is not in the FGD for %s' % (cls, nm, k, v[:60], cls), k); continue
            prob = value_problem(key, v)
            if prob:
                add(prob[0], e, cls, nm, '%s %s: %s = "%s" (%s): %s' % (cls, nm, k, v[:60], key.type, prob[1]), k)
            if key.type == 'flags' and key.choices and v.strip():
                try:
                    bits = int(float(v)); known = 0
                    for val, _ in key.choices:
                        try: known |= int(val)
                        except ValueError: pass
                    if bits & ~known and bits > 0:
                        add('unknown_flags', e, cls, nm, '%s %s: %s = %d sets bits %d the FGD does not define' % (cls, nm, k, bits, bits & ~known), k)
                except ValueError:
                    pass
            vs = v.strip()
            if vs and key.type in TARGET_TYPES and lk != 'targetname':
                t = vs.split(',')[0].strip().lower() if lk == 'parentname' else vs.lower()
                if t and not t.startswith('!') and not _matches(t, names) and not (key.type != 'target_destination' and t in classes_present):
                    add('key_target', e, cls, nm, '%s %s: %s = "%s" names nothing in the map' % (cls, nm, k, vs[:60]), k)
            if assets is not None and vs and (key.type.startswith('resource:') or key.type in ASSET_TYPES or vs.lower().endswith(ASSET_EXT)):
                if vs.lower().endswith(ASSET_EXT) and not assets.exists(vs):
                    add('missing_asset', e, cls, nm, '%s %s: %s = "%s" exists neither in the addon nor in CS2' % (cls, nm, k, vs), k)
        # outputs
        ins_outs = cat.io(cls)
        for c in m.conns(e):
            out, tgt, inp = [str(x) for x in m.conn_tuple(c)[:3]]
            if ins_outs[1] and out.lower() not in ins_outs[1]:
                add('bad_output', e, cls, nm, '%s %s: output %s does not exist on %s' % (cls, nm, out, cls))
            t = tgt.strip()
            if not t or t.lower() in SPECIAL_TARGETS or t.startswith('!'): continue
            tcls = target_classes(t)
            if not tcls:
                add('dangling_target', e, cls, nm, '%s %s: %s -> %s.%s, but nothing is called %s' % (cls, nm, out, t, inp, t)); continue
            if inp.lower() in DYNAMIC_INPUTS: continue
            known = [tc for tc in tcls if cat.is_entity(tc)]
            if known and len(known) == len(tcls) and not any(inp.lower() in cat.io(tc)[0] for tc in known):
                add('bad_input', e, cls, nm, '%s %s: %s -> %s.%s, but %s has no input %s' % (cls, nm, out, t, inp, '/'.join(sorted(known)), inp))
    if assets is not None:
        for mat, n in sorted(_mesh_materials(m).items()):
            if mat and not assets.exists(mat):
                add('missing_material', None, '', '', 'mesh material %s (used by %d mesh%s) exists neither in the addon nor in CS2' % (mat, n, 'es' if n != 1 else ''))
    return found


def summarize(found):
    c = collections.Counter((f['severity'], f['code']) for f in found)
    return {'%s/%s' % k: v for k, v in sorted(c.items())}


def run(path, addon=None, use_assets=True, cs2=None, cat=None):
    """check one map; -> {map, addon, counts, findings}"""
    cs2 = cs2 or fgdcat.cs2_root()
    cat = cat or fgdcat.load(cs2)
    m = V.Map(path)
    addon = addon or addon_of(path)
    assets = Assets(cs2, addon) if use_assets else None
    found = check(m, cat, assets)
    ents = m.entities()
    return {'map': os.path.basename(path), 'addon': addon, 'entities': len(ents),
            'errors': sum(f['severity'] == 'error' for f in found), 'warnings': sum(f['severity'] == 'warning' for f in found),
            'counts': summarize(found), 'findings': found}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only FGD / asset validation of a .vmap')
    ap.add_argument('vmap'); ap.add_argument('--json', action='store_true'); ap.add_argument('--no-assets', action='store_true')
    ap.add_argument('--addon'); ap.add_argument('--only', help='comma-separated codes'); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    try:
        res = run(a.vmap, a.addon, not a.no_assets)
    except (OSError, ValueError, AssertionError, StopIteration) as ex:
        print('cannot read %s: %s' % (a.vmap, ex), file=sys.stderr); return 2
    if a.only:
        keep = set(a.only.split(','))
        res['findings'] = [f for f in res['findings'] if f['code'] in keep]
    if a.limit: res['findings'] = res['findings'][:a.limit]
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        for f in res['findings']: print('%s\t%s\t%s' % (f['severity'], f['code'], f['text']))
        print('# %s: %d entities, %d errors, %d warnings; %s' % (res['map'], res['entities'], res['errors'], res['warnings'],
                                                              ', '.join('%s %d' % kv for kv in res['counts'].items()) or 'clean'))
    return 1 if res['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
