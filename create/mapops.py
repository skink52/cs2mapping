"""Batch map edits from JSON (cs2-map-mcp's map_edit idea): run a list of operations on a .vmap with the create/ generators and save.

  python mapops.py <job.json>        job: {"in": "<map.vmap>", "out": "<map.vmap>", "group": "gen", "content": "<addon content>",
                                           "backup": true, "dry_run": false, "ops": [ {...}, ... ]}
Prints one JSON line: {"ok", "out", "ops": [per-op result], "entities", "meshes", "backup"}. The whole batch runs on the map in memory and
nothing is written unless every op succeeds; with "out" == "in" and backup on (the default), tools/mapbackup.py saves the old map first.
group: the vis group the generated nodes go in; it is REPLACED on each run (vmapgen.finish), so re-running a batch rebuilds its own
objects and leaves everything else (your Hammer work) alone. Hammer must not have the map open.

Ops (op: fields):
  box / wedge / cylinder / prism / stairs / arch / revolve / sweep / extrude: the primitives.py arguments by name, + material
      (+ materials: {top, bottom, side} per face by normal, e.g. a lit facade with a concrete roof)
  mesh_edit: {shape: <a primitive op>, edits: [{edit: extrude|inset|bevel|subdivide|twist|taper|bend|noise|smooth|move, ...args, faces: {normal: [0,0,1]}}],
              cut: [<primitive ops>], uv: {"fit": [1, 1]} | {"scale": 0.5, "rotate": 15}, paint: "x" | "y" | "z" (blend along an axis)}
  entity: {cls, origin, angles, keys}          connect: {from (targetname), output, target, input, param, delay}
  brush: {cls, shape: <primitive op>, keys}    layout: {plan}       building: {footprint, floors, style, front, windows, roof, ...}
  street_front: {start, end, ...}              district: {area, ...}  street: {path, width, sidewalk, ...}  junction: {centre, ...}
  fence: {path, ...}  bank: {path, ...}       scatter: {area, spacing, models, avoid, z}
  kit: {kit, part, at, normal, facing} | {kit, part, row: [start, end]} | {kit, part, stack: count, at}
  competitive: {kind, anchors, paths}          mode / course: {surf_ramp: {...}} | {bhop: {...}} | {zones: {start, finish, name}}
  fx: {effect | precipitation | weather_tiles | lightning: {...}}
  light: {box, preset, sun_angles, sky, lamps: [{origin, kind, color, brightness, range_, name}]}            (gen_light.py)
  physics: {kind: door | button | lift | rotator | breakable | physics_prop | zone | ladder, shape: <primitive op>, ...}  (gen_physics.py)
  mechanics: {config, name, origin}            (also writes the script + HUD into "content")
Ported from project.py map_edit (atomic batches, dry run, backups) of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT); fresh code.
"""
import json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
sys.path.insert(0, HERE)
sys.path.append(TOOLS)                       # after create/: create/dmx.py must win `import dmx`

import vmapgen, vmaplib, primitives as P, meshedit as M

SHAPES = {'box': P.box, 'wedge': P.wedge, 'cylinder': P.cylinder, 'prism': P.prism, 'stairs': P.stairs, 'arch': P.arch,
          'revolve': P.revolve, 'sweep': P.sweep, 'extrude': P.extrude}


def face_rule(mats):
    """{"top": m, "bottom": m, "side": m} -> P.materials rule by face normal (|nz| > 0.7 counts as top / bottom); keys left out keep the shape's"""
    unknown = set(mats) - {'top', 'bottom', 'side'}
    if unknown: raise ValueError('materials takes top / bottom / side, not %s' % ', '.join(sorted(unknown)))
    return lambda i, n: mats.get('top') if n[2] > 0.7 else mats.get('bottom') if n[2] < -0.7 else mats.get('side')


def shape(spec):
    spec = dict(spec); kind = spec.pop('op', None) or spec.pop('shape')
    if kind not in SHAPES: raise ValueError('unknown shape %s (%s)' % (kind, ', '.join(SHAPES)))
    if 'material' in spec: spec['mat'] = spec.pop('material')
    per_face = spec.pop('materials', None)
    if kind == 'sweep' and isinstance(spec.get('section'), dict):
        sec = spec['section']; spec['section'] = P.rect(*sec['rect']) if 'rect' in sec else P.circle(*sec['circle'])
    s = SHAPES[kind](**spec)
    return P.materials(s, face_rule(per_face)) if per_face else s


def _faces(s, sel):
    if sel is None: return list(range(len(s[1])))
    if isinstance(sel, list): return sel
    return M.select(s, sel.get('normal'), sel.get('min_dot', 0.9), sel.get('box'), sel.get('material'))


def mesh_edit(op):
    s = shape(op['shape'])
    for e in op.get('edits', []):
        e = dict(e); kind = e.pop('edit'); sel = e.pop('faces', None)
        if kind in ('extrude', 'inset', 'move'): s = getattr(M, kind)(s, _faces(s, sel), *([e['distance']] if kind == 'extrude' else [e['amount']] if kind == 'inset' else [tuple(e['offset'])]))
        elif kind in ('bevel', 'subdivide', 'twist', 'taper', 'bend', 'noise', 'smooth', 'mirror'): s = getattr(M, kind)(s, **e)
        else: raise ValueError('unknown edit ' + kind)
    for c in op.get('cut', []): s = M.subtract(s, shape(c))
    if op.get('cut') and not s[1]: raise ValueError('the cuts removed the whole shape (nothing left to write)')
    for c in op.get('union', []): s = M.union(s, shape(c))
    uvs = None
    if op.get('uv'): uvs = {i: M.uv(**op['uv']) for i in range(len(s[1]))}
    paint = None
    if op.get('paint'):
        ax = 'xyz'.index(op['paint']); lo = min(p[ax] for p in s[0]); hi = max(p[ax] for p in s[0])
        paint = lambda p, ax=ax, lo=lo, hi=hi: (p[ax] - lo) / ((hi - lo) or 1.0)
    return s, uvs, paint


def run(job):
    group = job.get('group', 'gen'); content = job.get('content') or os.path.dirname(os.path.dirname(os.path.abspath(job['out'])))
    d = vmapgen.open_map(job['in'], content)
    results = []
    import gen_layout, gen_buildings, gen_world, gen_kits, gen_gameplay, fxkit, mechkit
    by_name = {}
    def ent_named(n):
        if n in by_name: return by_name[n]
        for e in vmaplib.new_children:
            ep = e.get('entity_properties')
            if ep is not None and ep.get('targetname') == n: return e
        raise KeyError('no entity named %s made in this batch (connect works on entities this batch adds)' % n)
    for i, op in enumerate(job['ops']):
        kind = op.get('op')
        try:
            if kind in SHAPES: P.add(shape(op), group); res = 'mesh'
            elif kind == 'mesh_edit':
                s, uvs, paint = mesh_edit(op); M.write(s, uvs, paint, group=group); res = '%d faces' % len(s[1])
            elif kind == 'entity':
                e = P.entity(op['cls'], op.get('origin', (0, 0, 0)), op.get('angles', (0, 0, 0)), group=group, strict=op.get('strict', True), **op.get('keys', {}))
                if op.get('keys', {}).get('targetname'): by_name[op['keys']['targetname']] = e
                res = op['cls']
            elif kind == 'connect':
                P.connect(ent_named(op['from']), op['output'], op['target'], op['input'], op.get('param', ''), op.get('delay', 0), op.get('times', -1)); res = 'io'
            elif kind == 'brush':
                e = P.brush_entity(op['cls'], shape(op['shape']), group=group, **op.get('keys', {}))
                if op.get('keys', {}).get('targetname'): by_name[op['keys']['targetname']] = e
                res = op['cls']
            elif kind == 'layout': out = gen_layout.build(op['plan']); gen_layout.write(out, group); res = {'rooms': out['rooms'], 'doors': out['doors']}
            elif kind == 'building':
                args = {k: v for k, v in op.items() if k not in ('op', 'footprint')}
                b = gen_buildings.building(op['footprint'], **args); gen_buildings.write(b, group); res = {'door': b['door'], 'top': b['top']}
            elif kind == 'street_front':
                args = {k: v for k, v in op.items() if k not in ('op', 'start', 'end')}
                row = gen_buildings.street_front(op['start'], op['end'], **args); gen_buildings.write(row, group); res = '%d houses' % len(row)
            elif kind == 'district':
                args = {k: v for k, v in op.items() if k not in ('op', 'area')}
                gen_buildings.write([{'shapes': gen_buildings.district(op['area'], **args)}], group); res = 'district'
            elif kind in ('street', 'junction', 'fence', 'bank'):
                first = {'street': 'path', 'junction': 'centre', 'fence': 'path', 'bank': 'path'}[kind]
                args = {k: v for k, v in op.items() if k not in ('op', first)}
                gen_world.write(getattr(gen_world, kind)(op[first], **args), group); res = kind
            elif kind == 'scatter':
                args = {k: v for k, v in op.items() if k not in ('op', 'area', 'cls')}
                items = gen_world.scatter(op['area'], **args); gen_world.place(items, op.get('cls', 'prop_static'), group); res = '%d props' % len(items)
            elif kind == 'kit':
                kit = gen_kits.load(op['kit']); part = gen_kits.part(kit, op['part'])
                if 'row' in op: items = gen_kits.row(part, op['row'][0], op['row'][1], op.get('gap', 8), op.get('normal', (0, 0, 1)), op.get('facing', (1, 0, 0)))
                elif 'stack' in op: items = gen_kits.stack(part, op['at'], op['stack'], op.get('facing', (1, 0, 0)))
                else: items = [gen_kits.place(part, op['at'], op.get('normal', (0, 0, 1)), op.get('facing', (1, 0, 0)))]
                gen_kits.props(items, group); res = '%d props' % len(items)
            elif kind == 'competitive':
                plan = gen_gameplay.competitive(op['kind'], op['anchors'], op.get('paths'), op.get('per_team'))
                gen_gameplay.place_competitive(plan, group); res = {'timings': plan['timings'], 'balance': plan['balance']}
            elif kind == 'course':
                if 'surf_ramp' in op: P.add(gen_gameplay.surf_ramp(**op['surf_ramp']), group)
                if 'bhop' in op:
                    for _, s in gen_gameplay.bhop_platforms(**op['bhop']): P.add(s, group)
                if 'zones' in op: z = op['zones']; gen_gameplay.course_zones(z['start'], z['finish'], z.get('name', 'kz'), z.get('script', 'mech'), group)
                res = 'course'
            elif kind == 'fx':
                for k in ('effect', 'precipitation', 'weather_tiles', 'lightning'):
                    if k in op: getattr(fxkit, k)(**dict(op[k], group=group))
                res = 'fx'
            elif kind == 'light':
                import gen_light
                if 'box' in op: gen_light.light(op['box'], op.get('preset', 'noon'), group, op.get('sun_angles'), op.get('sky'))
                for lp in op.get('lamps', []): gen_light.lamp(group=group, **lp)
                res = 'light'
            elif kind == 'physics':
                import gen_physics
                what = op['kind']; args = {k: v for k, v in op.items() if k not in ('op', 'kind', 'shape')}
                if 'shape' in op: args['shape'] = shape(op['shape'])
                if what == 'button' and 'targets' in args: args['targets'] = [tuple(x) for x in args['targets']]
                getattr(gen_physics, what)(group=group, **args); res = what
            elif kind == 'mechanics':
                name = op.get('name', 'mech')
                files = mechkit.build(op['config'], content, name, write=not job.get('dry_run')); mechkit.place(op['config'], name, op.get('origin', (0, 0, 0)), group)
                res = {'files': files}
            else:
                raise ValueError('unknown op %r' % kind)
            results.append({'op': kind, 'ok': True, 'result': res})
        except Exception as ex:
            return {'ok': False, 'failed_op': i, 'op': kind, 'error': '%s: %s' % (type(ex).__name__, ex), 'trace': traceback.format_exc()[-1500:], 'ops': results}
    if job.get('dry_run'):
        return {'ok': True, 'dry_run': True, 'ops': results}
    backup = None
    if os.path.abspath(job['out']) == os.path.abspath(job['in']) and job.get('backup', True):
        import mapbackup
        e = mapbackup.Store(job.get('backup_store')).save(job['in'], kind='before-mapops')
        backup = e['stamp'] if e else 'unchanged since the newest backup'
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        counts = vmapgen.finish(d, job['out'], group=group, first_run_cleanup=job.get('first_run_cleanup', False))
    return {'ok': True, 'out': job['out'], 'ops': results, 'entities': sum(counts.values()) if isinstance(counts, dict) else None, 'backup': backup}


def main(argv):
    with open(argv[1], encoding='utf-8') as f: job = json.load(f)
    res = run(job)
    print(json.dumps(res, default=str))
    return 0 if res['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
