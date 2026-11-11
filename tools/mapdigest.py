"""A small, readable digest of a .vmap: every entity (class, name, origin, parent, the keys that carry logic) and its outputs as
`output -> target.input` edges, with counts and world bounds. No geometry. For reasoning about a map's logic without loading
megabytes of mesh data. Reads the map; never writes to it.

  python mapdigest.py <map.vmap> [filters] [--graph | --summary] [--out FILE] [--pretty]

  --class PATTERN    only entities whose class matches (shell wildcards, several allowed: --class "trigger_*" --class logic_relay)
  --name PATTERN     only entities whose targetname matches (wildcards)
  --near X,Y,Z,R     only entities within R units of a point
  --touches NAME     only entities that send an output to NAME, or are NAME (follow one piece of wiring; wildcards)
  --graph            just the wiring, one line per output:  sender (class) Output -> target.Input param [delay s] [once]
  --summary          just the counts: entities by class, named entities, dangling targets, meshes, bounds
  --keys a,b         extra entity keys to include (default: the logic-bearing ones in KEYS below, when set)
  --limit N          stop after N entities (the summary still counts all that matched)
  --out FILE         write the JSON there instead of printing it (never over a .vmap)
  --pretty           indent the JSON (default: one entity per line, which is smaller)

JSON: {"map", "bytes", "summary": {entities, by_class, named, meshes, bounds, dangling_targets, class_targets, special_targets,
                                    references: {scripts, models, sounds, particles}, script_inputs},
       "entities": [{"i", "class", "name", "origin", "angles", "parent", "keys": {...}, "out": [[output, target, input, param, delay, times], ...]}]}
"i" is the element index in the file: stable until the map is saved again, and what tools/vmapedit.py uses. Coordinates are rounded to
one decimal. A target that no entity is named (and that is not !activator, !self ...) is listed under dangling_targets: usually a
dropped entity or a typo, but not proof of a fault: a name can be given at run time (a script's SetEntityName, a point_template's
name fix-up, a spawned entity), which a read of the file cannot see. A target that is the class of an entity in the map is listed
under class_targets instead (the engine accepts a class name as a target). references: what the matched entities point at by key
(cs_script, model, sound, particle), each with a use count; materials sit on mesh faces, which this tool leaves out
(scripts/vmap_refs.py lists those). script_inputs: the names sent as RunScriptInput, to compare with a script's OnScriptInput names.
"level": this is a read of the file, not of the running map ("untested", docs/reference/compatibility.md).

Python 3.9+, standard library plus tools/vmapedit.py (which reads keyvalues2 text and binary DMX vmaps).
"""
import argparse, collections, fnmatch, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V

# keys worth showing when an entity has them: they change what the map does (not how it looks)
KEYS = ('parentname', 'cs_script', 'model', 'filtername', 'damagefilter', 'spawnflags', 'StartDisabled', 'start_disabled', 'message',
        'soundName', 'soundevent', 'effect_name', 'layout', 'health', 'damage', 'speed', 'wait', 'delay', 'max', 'min', 'startvalue',
        'Case01', 'Case02', 'Case03', 'Case04', 'target', 'landmark', 'master', 'team', 'TeamNum', 'priority', 'enabled')
SPECIAL = ('!activator', '!self', '!caller', '!player', '!pvsplayer', '!picker')


def _r(v): return [round(float(x), 1) for x in v]


def _match(value, patterns):
    return not patterns or any(fnmatch.fnmatchcase(value.lower(), p.lower()) for p in patterns)


def digest(path, classes=(), names=(), near=None, touches=(), extra_keys=(), limit=None):
    m = V.Map(path)
    ents = m.entities()
    all_names = collections.Counter(n for n in (m.name(e) for e in ents) if n)
    out, by_class, dangling, special = [], collections.Counter(), collections.Counter(), collections.Counter()
    all_classes = {m.cls(e) for e in ents}
    by_cls_target, script_inputs = collections.Counter(), collections.Counter()
    refs = {'scripts': collections.Counter(), 'models': collections.Counter(), 'sounds': collections.Counter(), 'particles': collections.Counter()}
    REF_KEYS = (('cs_script', 'scripts'), ('model', 'models'), ('soundName', 'sounds'), ('soundevent', 'sounds'), ('effect_name', 'particles'))
    matched = 0
    for e in ents:
        cls, name = m.cls(e), m.name(e)
        conns = [list(m.conn_tuple(c)) for c in m.conns(e)]
        if not _match(cls, classes) or not _match(name, names):
            continue
        o = m.origin(e)
        if near and sum((o[k] - near[k]) ** 2 for k in range(3)) > near[3] ** 2:
            continue
        if touches and not (_match(name, touches) or any(_match(c[1], touches) for c in conns)):
            continue
        matched += 1; by_class[cls] += 1
        for c in conns:
            t = c[1]
            if t.lower() in SPECIAL or t.startswith('!'): special[t] += 1
            elif t and not any(fnmatch.fnmatchcase(n, t) for n in all_names) and t not in all_names:
                if t in all_classes: by_cls_target[t] += 1
                else: dangling[t] += 1
            if str(c[2]).lower() == 'runscriptinput' and c[3]: script_inputs[str(c[3])] += 1
        for k, kind in REF_KEYS:
            v = m.P(e, k)
            if v not in (None, '', '0'): refs[kind][str(v)] += 1
        if limit is not None and len(out) >= limit:
            continue
        rec = {'i': e, 'class': cls}
        if name: rec['name'] = name
        rec['origin'] = _r(o)
        ang = m.g(e, b'angles')
        if ang is not None and any(abs(float(a)) > 0.05 for a in ang): rec['angles'] = _r(ang)
        keys = {}
        for k in tuple(KEYS) + tuple(extra_keys):
            v = m.P(e, k)
            if v not in (None, '', '0') or (k in extra_keys and v is not None): keys[k] = v
        if 'parentname' in keys: rec['parent'] = keys.pop('parentname')
        if keys: rec['keys'] = keys
        if conns: rec['out'] = [[c[0], c[1], c[2], c[3], c[4], c[5]] for c in conns]
        out.append(rec)
    meshes = [n for n, _ in m.walk() if m.type(n) == b'CMapMesh']
    b = m.bounds(m.world)
    summary = {'entities': matched, 'entities_in_map': len(ents), 'by_class': dict(by_class.most_common()),
               'named': sum(1 for e in out if 'name' in e) if limit is None else None,
               'duplicate_names': {n: c for n, c in all_names.items() if c > 1} if not (classes or names or near or touches) else None,
               'meshes': len(meshes), 'bounds': [_r(b[0]), _r(b[1])] if b else None,
               'dangling_targets': dict(dangling.most_common()), 'class_targets': dict(by_cls_target.most_common()),
               'special_targets': dict(special.most_common()),
               'references': {k: dict(v.most_common(60)) for k, v in refs.items() if v},
               'reference_counts': {k: len(v) for k, v in refs.items() if v},
               'script_inputs': dict(sorted(script_inputs.items())),
               'truncated': bool(limit is not None and matched > len(out))}
    return {'map': os.path.basename(path), 'bytes': os.path.getsize(path), 'level': 'untested', 'manual_check_required': True,
            'summary': {k: v for k, v in summary.items() if v is not None}, 'entities': out}


def graph_lines(d):
    for e in d['entities']:
        who = '%s (%s)' % (e.get('name') or '#%d' % e['i'], e['class'])
        for o, t, i, p, delay, times in e.get('out', []):
            yield '%s %s -> %s.%s%s%s%s' % (who, o, t or '?', i, (' ' + p) if p else '', (' [%gs]' % delay) if delay else '',
                                            ' [once]' if times == 1 else '')


def dumps(d, pretty=False):
    if pretty: return json.dumps(d, indent=1)
    head = {k: v for k, v in d.items() if k != 'entities'}
    return ('{' + json.dumps(head, separators=(',', ':'))[1:-1] + ',"entities":[\n'
            + ',\n'.join(json.dumps(e, separators=(',', ':')) for e in d['entities']) + '\n]}')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Entity and wiring digest of a .vmap (read-only)')
    ap.add_argument('vmap'); ap.add_argument('--class', dest='classes', action='append', default=[]); ap.add_argument('--name', dest='names', action='append', default=[])
    ap.add_argument('--near'); ap.add_argument('--touches', action='append', default=[]); ap.add_argument('--keys', default='')
    ap.add_argument('--limit', type=int); ap.add_argument('--graph', action='store_true'); ap.add_argument('--summary', action='store_true')
    ap.add_argument('--out'); ap.add_argument('--pretty', action='store_true')
    a = ap.parse_args(argv)
    try:
        near = [float(x) for x in a.near.split(',')] if a.near else None
        if near is not None and len(near) != 4: raise ValueError('--near takes X,Y,Z,R')
        if a.out and (a.out.lower().endswith(('.vmap', '.vmap_c', '.vpk')) or os.path.abspath(a.out) == os.path.abspath(a.vmap)):
            raise ValueError('--out must not be a map file')
        d = digest(a.vmap, a.classes, a.names, near, a.touches, [k for k in a.keys.split(',') if k], a.limit)
    except (OSError, ValueError, StopIteration, KeyError, AssertionError) as ex:
        print('mapdigest: cannot read %s: %s' % (a.vmap, ex), file=sys.stderr); return 2
    if a.summary: text = json.dumps({k: v for k, v in d.items() if k != 'entities'}, indent=1)
    elif a.graph: text = '\n'.join(graph_lines(d))
    else: text = dumps(d, a.pretty)
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f: f.write(text + '\n')
        print('%s: %d entities, %d bytes (map %d bytes)' % (a.out, len(d['entities']), len(text), d['bytes']))
    else:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
