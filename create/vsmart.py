"""SmartProp (.vsmart) reader and linter: what a SmartProp places, and the mistakes that make it place nothing without a word.

  python create/vsmart.py tree <file.vsmart>          the element tree: class, name, model, selection criteria, modifiers
  python create/vsmart.py lint <file.vsmart | dir>    silent-failure checks (below); a folder is checked recursively
  add --json for machine-readable output. Exit 1 when lint finds something.

A .vsmart is KeyValues3 text. The root is a CSmartPropElement_Group with m_Variables, m_Choices, m_Children and m_Modifiers;
elements (CSmartPropElement_Model / Group / PlaceOnPath / FitOnLine / Layout2DGrid / PlaceInSphere / PickOne / PlaceMultiple) place
things, modifiers (CSmartPropOperation_*) transform what they place, and m_SelectionCriteria (EndCap, PathPosition, LinearLength,
ChoiceWeight, SurfaceAngle, Expression, ...) decide whether a branch runs. Authoring notes: docs/creation/smartprops.md.

Lint checks (Hammer5Tools automation/formats/vsmart_lint.py by dertwist, MIT, rewritten for tools/kv3text.py):
  unguarded-division   a divisor in an expression that can be 0: 0/0 is NaN and one NaN hides the whole instance
  unguarded-trig       atan / asin / acos of an unguarded quotient (same NaN)
  untyped-default      a Float / Int / Vector3D / Angles variable with an empty default (read as 0: counts collapse to nothing)
  empty-expression     an empty m_Expression where a number belongs
  duplicate-element-id two elements with one m_nElementID (Hammer's outliner selects the wrong one)
  endcap-linear-scale  LinearScale() on an EndCap-selected model (end posts must stay at scale 1)
  unknown-variable     an expression naming a variable nobody declares (Hammer reads it as 0, so the condition never fires;
                       names are case-insensitive, as in Hammer)
  missing-model        (with --content DIR) a model path that is neither in the addon's content folder nor compiled in the game
                       folder next to it; stock models can't be checked without the VPK and are reported as "stock?" only with -v
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import kv3text  # noqa: E402

INTRINSICS = {'instanceindex', 'instancecount', 'linearscale', 'randomfloat', 'randomint', 'deg2rad', 'rad2deg', 'sin', 'cos',
              'tan', 'asin', 'acos', 'atan', 'atan2', 'sqrt', 'abs', 'min', 'max', 'floor', 'ceil', 'round', 'pow', 'clamp',
              'lerp', 'pi', 'e', 'true', 'false', 'x', 'y', 'z', 'w', 'r', 'g', 'b', 'a'}
NUMERIC_VARS = {'CSmartPropVariable_Float', 'CSmartPropVariable_Int', 'CSmartPropVariable_Vector3D', 'CSmartPropVariable_Angles'}
EXPR_KEYS = ('m_Expression', 'm_HideExpression', 'm_ReadOnlyExpression')
_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_TRIG = re.compile(r'\b(atan|asin|acos)\s*\(', re.I)


def _val(v):
    return v.value if isinstance(v, kv3text.Flagged) else v


def load(path):
    return kv3text.load(path).root


def walk(node, path=''):
    """every (path, dict) in the document"""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items(): yield from walk(v, '%s.%s' % (path, k) if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node): yield from walk(v, '%s[%d]' % (path, i))


def expressions(root):
    out = []
    for p, n in walk(root):
        for k in EXPR_KEYS:
            v = _val(n.get(k))
            if isinstance(v, str) and v.strip(): out.append(('%s.%s' % (p, k) if p else k, v))
    return out


def _arg(expr, open_i):
    depth = 0
    for i in range(open_i, len(expr)):
        if expr[i] == '(': depth += 1
        elif expr[i] == ')':
            depth -= 1
            if depth == 0: return expr[open_i + 1:i]
    return expr[open_i + 1:]


def divisors(expr):
    out, i = [], 0
    while True:
        i = expr.find('/', i)
        if i < 0: return out
        c = i + 1
        while c < len(expr) and expr[c].isspace(): c += 1
        if c >= len(expr): return out
        if expr[c] == '(': d = '(' + _arg(expr, c) + ')'
        else:
            s = c
            while s < len(expr) and not expr[s].isspace() and expr[s] not in '),': s += 1
            d = expr[c:s]
        out.append(d); i = c + max(1, len(d))


def _safe(d):
    s = d.strip().strip('()').strip()
    try: return float(s) != 0.0
    except ValueError: return s.lower().startswith('max')


def _f(check, msg, where=''):
    return {'check': check, 'message': msg, 'where': where}


def lint_doc(root, content=None):
    found = []
    for where, ex in expressions(root):
        bad = [d for d in divisors(ex) if not _safe(d)]
        if bad:
            found.append(_f('unguarded-division', "divisor '%s' can be 0 (0/0 = NaN hides the instance); wrap it in max(1.0, ...): '%s'"
                            % (bad[0], ex), where))
        for m in _TRIG.finditer(ex):
            a = _arg(ex, m.end() - 1)
            if '/' in a and 'max' not in a.lower():
                found.append(_f('unguarded-trig', "%s() of the unguarded quotient '%s' (NaN reaches the rotation)" % (m.group(1), a.strip()), where))
    variables = [v for v in (root.get('m_Variables') or []) if isinstance(v, dict)] if isinstance(root, dict) else []
    for v in variables:
        if v.get('_class') in NUMERIC_VARS and _val(v.get('m_DefaultValue', '')) in ('', None):
            found.append(_f('untyped-default', "'%s' (%s) has an empty default, read as 0" % (v.get('m_VariableName', '?'), v.get('_class')),
                            'm_Variables[%s]' % v.get('m_VariableName', '')))
    for p, n in walk(root):
        if 'm_Expression' in n and isinstance(_val(n['m_Expression']), str) and not _val(n['m_Expression']).strip():
            found.append(_f('empty-expression', 'an empty m_Expression where a number belongs: write the number', p))
    seen, dup = {}, {}
    for p, n in walk(root):
        info = n.get('editor_info') if isinstance(n.get('editor_info'), dict) else None
        holder = info if info and 'm_nElementID' in info else (n if 'm_nElementID' in n and not p.endswith('editor_info') else None)
        if holder is None: continue
        eid = holder.get('m_nElementID')
        if not isinstance(eid, int): continue
        if eid in seen: dup.setdefault(eid, [seen[eid]]).append(p)
        else: seen[eid] = p
    for eid, ps in sorted(dup.items()):
        found.append(_f('duplicate-element-id', 'element ID %d used %d times' % (eid, len(ps)), ', '.join(ps[:4])))
    for p, n in walk(root):
        crit = n.get('m_SelectionCriteria')
        if isinstance(crit, list) and any(isinstance(c, dict) and 'EndCap' in str(c.get('_class', '')) for c in crit) \
                and 'LinearScale()' in json.dumps(n.get('m_vModelScale', ''), default=str):
            found.append(_f('endcap-linear-scale', 'LinearScale() on an EndCap model: end pieces must stay at scale 1', p))
    declared = {str(v.get('m_VariableName', '')).lower() for v in variables}
    for where, ex in expressions(root):
        unknown = sorted({w for w in _IDENT.findall(ex) if w.lower() not in declared and w.lower() not in INTRINSICS})
        if unknown:
            found.append(_f('unknown-variable', "'%s' names %s, which no variable declares (read as 0)" % (ex.strip(), ', '.join(unknown)), where))
    if content:
        game = re.sub(r'([\\/])content([\\/])', r'\1game\2', content, count=1)
        for p, n in walk(root):
            m = _val(n.get('m_sModelName'))
            if isinstance(m, str) and m:
                rel = m.replace('\\', '/')
                if not (os.path.exists(os.path.join(content, rel)) or os.path.exists(os.path.join(game, rel + '_c'))):
                    found.append(_f('missing-model', '%s is not in this addon (stock models are not checked)' % rel, p))
    return found


def lint(path, content=None):
    if os.path.isdir(path):
        files, counts = [], {}
        for dp, _, fs in os.walk(path):
            for fn in sorted(fs):
                if not fn.lower().endswith('.vsmart'): continue
                fp = os.path.join(dp, fn)
                try: fnd = lint_doc(load(fp), content)
                except (OSError, ValueError, SyntaxError) as ex:
                    files.append({'path': fp, 'error': str(ex)}); continue
                for x in fnd: counts[x['check']] = counts.get(x['check'], 0) + 1
                if fnd: files.append({'path': fp, 'findings': fnd})
        return {'directory': path, 'counts': counts, 'clean': not counts and not any('error' in f for f in files), 'files': files}
    fnd = lint_doc(load(path), content)
    return {'path': path, 'clean': not fnd, 'findings': fnd}


def tree(node, depth=0, out=None):
    """one line per element: class, name, model, criteria, modifiers"""
    out = [] if out is None else out
    if not isinstance(node, dict): return out
    cls = str(node.get('_class', '?')).replace('CSmartPropElement_', '')
    bits = [cls]
    name = _val(node.get('m_sLabel') or node.get('m_sName') or '')
    if name: bits.append('"%s"' % name)
    model = _val(node.get('m_sModelName'))
    if model: bits.append(str(model))
    crit = [str(c.get('_class', '')).replace('CSmartPropSelectionCriteria_', '') for c in node.get('m_SelectionCriteria') or [] if isinstance(c, dict)]
    if crit: bits.append('if ' + '+'.join(crit))
    mods = [str(c.get('_class', '')).replace('CSmartPropOperation_', '') for c in node.get('m_Modifiers') or [] if isinstance(c, dict)]
    if mods: bits.append('mods ' + ','.join(mods))
    out.append('  ' * depth + ' '.join(bits))
    for ch in node.get('m_Children') or []: tree(ch, depth + 1, out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='SmartProp (.vsmart) tree and lint')
    ap.add_argument('cmd', choices=('tree', 'lint')); ap.add_argument('path')
    ap.add_argument('--content', help='addon content folder, to check model paths'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'tree':
        root = load(a.path)
        if a.json: print(json.dumps(tree(root), indent=1))
        else:
            for v in (root.get('m_Variables') or []):
                if isinstance(v, dict): print('var %s %s = %r' % (str(v.get('_class', '')).replace('CSmartPropVariable_', ''),
                                                                 v.get('m_VariableName'), _val(v.get('m_DefaultValue'))))
            print('\n'.join(tree(root)))
        return 0
    res = lint(a.path, a.content)
    if a.json: print(json.dumps(res, indent=1, default=str))
    else:
        items = res.get('findings') or [dict(x, path=f['path']) for f in res.get('files', []) for x in f.get('findings', [])]
        for f in res.get('files', []):
            if 'error' in f: print('error\t%s\t%s' % (f['path'], f['error']))
        for x in items: print('%s\t%s\t%s%s' % (x['check'], x.get('where', ''), x['message'], ('\t' + x['path']) if 'path' in x else ''))
        if res['clean']: print('clean')
    return 0 if res['clean'] else 1


if __name__ == '__main__':
    sys.exit(main())
