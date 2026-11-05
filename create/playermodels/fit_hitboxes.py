"""Re-fit the hit boxes of converted models in place, without reconverting them.

usage: python3 -I fit_hitboxes.py <catalog.json> [--only slug,slug] [--batch N] [--compile]
       python3 -I fit_hitboxes.py --model <model.mdl> --vmdl <converted .vmdl> --template <dir> [--bodygroup part=i]

The converted models keep the stock agent's hit box set, capsules on CS2's bones. Because a model keeps its own neck length, its head
isn't where a stock agent's is (batch 1: 2.5-3.3 u off), so aiming at the visible head could miss. This moves the head capsule onto the
model's head (measured from its eyeballs; without eyeballs from the head mesh below its top fifth) and the neck capsule half as far,
at most HEAD_HITBOX_MAX (5 u). It always starts from the template's own capsules, so running it again changes nothing.
gmod2cs2.py does the same at conversion; this script is for models converted before that, or after changing the rule.

Prints per model: the shift, how it was measured, and the share of head/chest/stomach/arms/legs mesh points outside every capsule
(see hitboxes.py), and writes them into <work>/reports/<slug>.json. --compile recompiles the changed vmdls.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gmod2cs2 as g
import hitboxes
from srcmdl import SrcModel

RC_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe'


def section(txt, cls):
    """(start, end) of the '{ _class = "<cls>" ... }' node in a ModelDoc vmdl"""
    i = txt.index('_class = "%s"' % cls)
    s = txt.rindex('{', 0, i)
    depth = 0
    for k in range(s, len(txt)):
        if txt[k] == '{': depth += 1
        elif txt[k] == '}':
            depth -= 1
            if depth == 0: return s, k + 1
    raise ValueError('unbalanced ' + cls)


def fit_one(mdl_path, vmdl_path, tpl, choices=None, mode='rigid'):
    m = SrcModel(mdl_path)
    cv = g.Converter(m, tpl, log=lambda s: None); cv.transforms(mode)
    used, remap, V, N, W = cv.convert_mesh(m.default_meshes(choices))
    d, how = g.head_hitbox_shift(cv, tpl, V, W)
    t0 = open(tpl.vmdl, encoding='utf-8').read()
    t1 = g.shift_capsules(g.shift_capsules(t0, tpl, 'head_0', d), tpl, 'neck_0', d * 0.5)
    a, b = section(t1, 'HitboxSetList')
    new_hb = t1[a:b]
    txt = open(vmdl_path, encoding='utf-8').read()
    x, y = section(txt, 'HitboxSetList')
    out = txt[:x] + new_hb + txt[y:]
    changed = out != txt
    if changed: open(vmdl_path, 'w', encoding='utf-8', newline='\n').write(out)
    return {'head_hitbox_shift': [round(float(v), 2) for v in d], 'head_hitbox_from': how,
            'hitbox_fit': hitboxes.fit(tpl, V, W, hitboxes.capsules(new_hb)), 'changed': changed}


def main():
    args = sys.argv[1:]
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    if '--model' in args:
        tpl = g.Template(opt('--template'))
        ch = {k: int(v) for k, v in (b.split('=') for b in [args[i + 1] for i, a in enumerate(args) if a == '--bodygroup'])}
        print(json.dumps(fit_one(opt('--model'), opt('--vmdl'), tpl, ch or None), indent=1))
        return
    import fetch
    cat = json.load(open(args[0]))
    p = fetch.paths(cat)
    out = os.environ.get('PM_OUT', p.get('out')); tpl = g.Template(os.environ.get('PM_TEMPLATE', p.get('template')))
    only = set(opt('--only').split(',')) if opt('--only') else None
    batch = int(opt('--batch')) if opt('--batch') else None
    for it in cat['items']:
        if not it.get('chosen') or (only and it['slug'] not in only) or (batch and it.get('batch') != batch): continue
        slug = it['slug']
        vm = os.path.join(out, 'models', 'player', 'gmod', slug, slug + '.vmdl')
        if not os.path.exists(vm): print('%-22s not converted yet' % slug); continue
        mdl = os.path.join(p['work'], 'extract', str(it['id']), *it['mdl'].split('/'))
        r = fit_one(mdl, vm, tpl, it.get('bodygroups'))
        hf = r['hitbox_fit']
        print('%-22s head moved %s (%s); outside capsules: head %.0f%% chest %.0f%% legs %.0f%%%s' % (
            slug, r['head_hitbox_shift'], r['head_hitbox_from'], 100 * hf.get('head', 0), 100 * hf.get('chest', 0), 100 * hf.get('legs', 0),
            '' if r['changed'] else ' (unchanged)'), flush=True)
        rp = os.path.join(p['work'], 'reports', slug + '.json')
        if os.path.exists(rp):
            rep = json.load(open(rp)); rep.update({k: v for k, v in r.items() if k != 'changed'})
            if '--compile' in args and r['changed']:
                c = subprocess.run([opt('--rc') or RC_DEFAULT, '-i', vm, '-nop4'], capture_output=True, text=True, errors='replace')
                ok = ' 1 compiled, 0 failed' in c.stdout
                rep['compile'] = dict(rep.get('compile', {}), ok=ok)
                print('%-22s compile %s' % ('', 'OK' if ok else 'FAILED'), flush=True)
            json.dump(rep, open(rp, 'w'), indent=1)


if __name__ == '__main__':
    main()
