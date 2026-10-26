"""Builds every procedural prop from spec modules and records model path, triangle counts and bounds per prop in props.json
(placer.py and clean_stale.py read it). Each spec module provides specs() -> {name: spec} (a spec is what build_prop.build takes);
a module with only spec() gives one prop named after the module (p_sandbag -> sandbag).

usage: build_all_props.py <module>[,<module>...] [prop names...] [--no-preview]
       build_all_props.py props.list.json [prop names...]      JSON: {"modules": ["p_sandbag", "p_crates"]}
Prop names limit the build to those props; props.json keeps entries from earlier runs. Spec modules are imported from this
folder or from the current directory. Output: $CS2_ADDON_OUT (models/<CS2_MODEL_PREFIX>/<name>/...), props.json next to it.

From trenchwarfare-cs2/tools/build_all_props.py (MIT), made project-neutral.
"""
import os, sys, json, importlib, traceback
sys.path.insert(0, os.getcwd())
import build_prop

PROPS_JSON = os.path.join(os.path.dirname(os.path.abspath(build_prop.OUT)), 'props.json')


def all_specs(modules):
    sp = {}
    for name in modules:
        mod = importlib.import_module(name)
        if hasattr(mod, 'specs'): sp.update(mod.specs())
        elif hasattr(mod, 'spec'): sp[name[2:] if name.startswith('p_') else name] = mod.spec()
        else: print('%s: no specs() or spec()' % name)
    return sp


def main(argv):
    preview = '--no-preview' not in argv
    argv = [a for a in argv if a != '--no-preview']
    if not argv:
        print(__doc__); return 2
    first, names = argv[0], argv[1:]
    modules = json.load(open(first))['modules'] if first.endswith('.json') else [m for m in first.split(',') if m]
    info = json.load(open(PROPS_JSON)) if os.path.exists(PROPS_JSON) else {}
    sp = all_specs(modules)
    bad = 0
    for n in (names or sorted(sp)):
        if n not in sp: print('no spec', n); bad += 1; continue
        try:
            info[n] = build_prop.build(n, sp[n], preview=preview)
        except Exception:
            traceback.print_exc(); bad += 1
        os.makedirs(os.path.dirname(PROPS_JSON), exist_ok=True)
        json.dump(info, open(PROPS_JSON, 'w'), indent=1)
    print('done: %d props in %s, %d failed' % (len(info), PROPS_JSON, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
