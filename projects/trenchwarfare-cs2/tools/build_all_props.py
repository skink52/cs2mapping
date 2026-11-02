"""Builds every prop (or the names given) and records model paths/bounds in out/props.json."""
import os, sys, json, traceback
import build_prop, p_sandbag, p_trench, p_wire, p_trees, p_wreck, p_misc, p_minenwerfer, p_trenchlife

def all_specs():
    sp = {}
    for v in range(3):
        sp['sandbag_wall_%s' % 'abc'[v]] = p_sandbag.spec(v, courses=3)
    sp['sandbag_low'] = p_sandbag.spec(5, courses=2)
    sp['sandbag_low_128'] = p_sandbag.spec(6, courses=2, length=128)
    sp['sandbag_wall_128'] = p_sandbag.spec(7, courses=3, length=128)
    for mod in (p_trench, p_wire, p_trees, p_wreck, p_misc, p_minenwerfer, p_trenchlife):
        sp.update(mod.specs())
    return sp

if __name__ == '__main__':
    names = sys.argv[1:]
    path = os.path.join(build_prop.OUT, '..', 'props.json')
    info = json.load(open(path)) if os.path.exists(path) else {}
    sp = all_specs()
    for n in (names or sorted(sp)):
        if n not in sp: print('no spec', n); continue
        try:
            info[n] = build_prop.build(n, sp[n], preview=True)
        except Exception:
            traceback.print_exc()
        json.dump(info, open(path, 'w'), indent=1)
    print('done', len(info))
