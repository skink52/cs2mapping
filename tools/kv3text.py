"""KeyValues3 text (.vmdl, .vpost, .vsndevts, .vpcf, .vdata, anim graphs): parse to Python and write back.

  doc = kv3text.loads(text)          -> KV3(header, root): root is dict / list / str / int / float / bool / None; flagged values
                                        (resource_name:"x", soundevent:"y", panorama:"z") come back as Flagged(flag, value)
  text = kv3text.dumps(doc)          tab-indented, Valve's layout ("key = value", arrays "[ ... ]", strings quoted, multi-line \"\"\" kept)
  python kv3text.py <file> [--json]  parse and print (or re-dump, to check a file round-trips)

Comments (// and /* */) are skipped on reading. Keys may be bare words or quoted. Ported from kv3.py in cs2-map-mcp by Rmgs123
(github.com/Rmgs123/cs2-map-mcp, MIT); fresh code. skink52's writers (create/s2.py, sndevents.py, vpcf66.py) stay as they are; this is
for reading and editing existing KV3 files.
"""
import json, re, sys

HEADER = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->'


class Flagged:
    __slots__ = ('flag', 'value')
    def __init__(s, flag, value): s.flag, s.value = flag, value
    def __eq__(s, o): return isinstance(o, Flagged) and (s.flag, s.value) == (o.flag, o.value)
    def __repr__(s): return '%s:%r' % (s.flag, s.value)


class KV3:
    def __init__(s, header, root): s.header, s.root = header, root


_NUM = re.compile(r'[-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)$')
_WORD = re.compile(r'[A-Za-z0-9_.\-+:$@#&|/\\]+')


class _P:
    def __init__(s, t): s.t, s.i = t, 0

    def ws(s):
        t = s.t
        while s.i < len(t):
            c = t[s.i]
            if c in ' \t\r\n,': s.i += 1
            elif t.startswith('//', s.i): s.i = t.find('\n', s.i) if '\n' in t[s.i:] else len(t)
            elif t.startswith('/*', s.i):
                e = t.find('*/', s.i + 2); s.i = len(t) if e < 0 else e + 2
            else: break

    def err(s, msg): raise ValueError('%s at line %d' % (msg, s.t.count('\n', 0, s.i) + 1))

    def value(s):
        s.ws(); t = s.t
        if s.i >= len(t): s.err('unexpected end')
        c = t[s.i]
        if c == '{': return s.obj()
        if c == '[': return s.arr()
        if t.startswith('"""', s.i):
            e = t.find('"""', s.i + 3)
            if e < 0: s.err('unclosed """')
            v = t[s.i + 3:e]; s.i = e + 3
            return v[1:] if v.startswith('\n') else v
        if c == '"': return s.string()
        m = _WORD.match(t, s.i)
        if not m: s.err('unexpected %r' % c)
        w = m.group(0); s.i = m.end()
        if s.i < len(t) and t[s.i] == '"' and w.endswith(':'):
            return Flagged(w[:-1], s.string())
        if w == 'true': return True
        if w == 'false': return False
        if w == 'null': return None
        if _NUM.match(w): return float(w) if any(ch in w for ch in '.eE') else int(w)
        return w

    def string(s):
        t = s.t; s.i += 1; out = []
        while s.i < len(t) and t[s.i] != '"':
            if t[s.i] == '\\' and s.i + 1 < len(t): out.append({'n': '\n', 't': '\t'}.get(t[s.i + 1], t[s.i + 1])); s.i += 2
            else: out.append(t[s.i]); s.i += 1
        if s.i >= len(t): s.err('unclosed string')
        s.i += 1
        return ''.join(out)

    def key(s):
        s.ws(); t = s.t
        if t[s.i] == '"': return s.string()
        m = _WORD.match(t, s.i)
        if not m: s.err('bad key')
        s.i = m.end(); return m.group(0)

    def obj(s):
        s.i += 1; out = {}
        while True:
            s.ws()
            if s.i >= len(s.t): s.err('unclosed {')
            if s.t[s.i] == '}': s.i += 1; return out
            k = s.key(); s.ws()
            if s.i >= len(s.t) or s.t[s.i] != '=': s.err('expected = after %s' % k)
            s.i += 1
            out[k] = s.value()

    def arr(s):
        s.i += 1; out = []
        while True:
            s.ws()
            if s.i >= len(s.t): s.err('unclosed [')
            if s.t[s.i] == ']': s.i += 1; return out
            out.append(s.value())


def loads(text):
    text = text.lstrip('﻿')
    header = ''
    m = re.match(r'\s*(<!--.*?-->)', text, re.S)
    if m: header = m.group(1); text = text[m.end():]
    p = _P(text)
    root = p.value(); p.ws()
    if p.i < len(text): p.err('text after the root value')
    return KV3(header or HEADER, root)


def load(path):
    with open(path, encoding='utf-8') as f: return loads(f.read())


def _scalar(v):
    if v is True: return 'true'
    if v is False: return 'false'
    if v is None: return 'null'
    if isinstance(v, Flagged): return '%s:%s' % (v.flag, _scalar(v.value))
    if isinstance(v, int): return str(v)
    if isinstance(v, float): return repr(v) if v != int(v) or abs(v) >= 1e15 else '%.1f' % v
    if '\n' in v: return '"""\n%s"""' % v
    return '"%s"' % v.replace('\\', '\\\\').replace('"', '\\"')


def _dump(v, ind):
    pad = '\t' * ind
    if isinstance(v, dict):
        if not v: return '{}'
        lines = ['{']
        for k, x in v.items():
            key = k if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', k) else '"%s"' % k
            lines.append('%s\t%s = %s' % (pad, key, _dump(x, ind + 1)))
        return '\n'.join(lines + [pad + '}'])
    if isinstance(v, list):
        if not v: return '[  ]'
        if all(not isinstance(x, (dict, list)) for x in v) and len(v) <= 16:
            return '[ ' + ', '.join(_scalar(x) for x in v) + ' ]'
        return '\n'.join(['['] + ['%s\t%s,' % (pad, _dump(x, ind + 1)) for x in v] + [pad + ']'])
    return _scalar(v)


def dumps(doc):
    root = doc.root if isinstance(doc, KV3) else doc
    header = doc.header if isinstance(doc, KV3) else HEADER
    return header + '\n' + _dump(root, 0) + '\n'


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    doc = load(argv[1])
    if '--json' in argv: print(json.dumps(doc.root, indent=1, default=repr))
    else: sys.stdout.write(dumps(doc))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
