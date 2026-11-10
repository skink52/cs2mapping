"""Entity catalog from CS2's own FGD files: every class with its kind, bases, keys (type, default, choices), inputs and outputs.

  python fgdcat.py describe <classname>            keys, defaults, choices, inputs, outputs (JSON)
  python fgdcat.py search <text>                   classes whose name or description has the text
  python fgdcat.py defaults <classname>            the keyvalues Hammer writes for a freshly placed entity (JSON)
  python fgdcat.py stats                           class / key counts, files read

Library:  cat = fgdcat.load()  (or fgdcat.Catalog.from_texts([...]) for tests);  cat.keys(cls), cat.io(cls), cat.defaults(cls),
cat.describe(cls), cat.search(text), cat.is_entity(cls), cat.excluded, cat.similar(name).

Files: <CS2>/game/core/*.fgd then <CS2>/game/csgo/*.fgd, in that order, as Hammer loads them (env CS2_ROOT overrides the install path).
Rules followed: a later @...Class of the same name replaces the earlier one, @OverrideClass merges into it, @exclude removes a class until
something defines it again (csgo.fgd excludes core's env_sky and defines its own), and a key of type remove_key deletes an inherited key.

The idea of an FGD-driven catalog (entity_info, defaults for new entities, key checks) comes from cs2-map-mcp by Rmgs123
(github.com/Rmgs123/cs2-map-mcp, MIT). This is a fresh implementation for skink52's cs2mapping tools; tools/mapcheck.py has the older,
class / I/O-only parser and is unchanged.
"""
import difflib, glob, json, os, re, sys

CS2_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
NODE_KEYS = {'origin', 'angles', 'scales'}          # Hammer keeps these on the node, not in entity_properties

_TOKENS = re.compile(r'''
    (?P<sp>\s+)
  | (?P<cm>//[^\n]*)
  | (?P<st>"(?:[^"\\]|\\.)*")
  | (?P<pu>[@()\[\]{}:=,+])
  | (?P<wd>[^\s@()\[\]{}:=,+"]+)
''', re.X)


def cs2_root():
    return os.environ.get('CS2_ROOT') or CS2_DEFAULT


def fgd_paths(root=None):
    game = os.path.join(root or cs2_root(), 'game')
    return sorted(glob.glob(os.path.join(game, 'core', '*.fgd'))) + sorted(glob.glob(os.path.join(game, 'csgo', '*.fgd')))


class Key:
    __slots__ = ('name', 'type', 'label', 'default', 'help', 'choices', 'readonly')

    def __init__(s, name, typ):
        s.name, s.type = name, typ
        s.label = s.default = s.help = ''
        s.choices = []          # [(value, label)]; for flags the value is the bit
        s.readonly = False

    def as_dict(s):
        d = {'key': s.name, 'type': s.type, 'default': s.default}
        if s.label: d['label'] = s.label
        if s.help: d['help'] = s.help
        if s.choices: d['choices'] = {v: l for v, l in s.choices}
        return d


class EntClass:
    def __init__(s, name, kind):
        s.name, s.kind = name, kind
        s.desc = ''
        s.bases = []
        s.keys = {}             # lower name -> Key (spelling kept in Key.name)
        s.inputs = {}           # lower name -> (name, type, help)
        s.outputs = {}
        s.helper_keys = set()   # keys a Hammer helper edits (box_mins ...), stored on the entity

    def merge(s, other):
        for b in other.bases:
            if b not in s.bases: s.bases.append(b)
        s.keys.update(other.keys); s.inputs.update(other.inputs); s.outputs.update(other.outputs)
        s.helper_keys |= other.helper_keys
        s.desc = other.desc or s.desc


class _Stream:
    def __init__(s, text):
        s.t = []
        for m in _TOKENS.finditer(text):
            k = m.lastgroup
            if k in ('sp', 'cm'): continue
            v = m.group(k)
            if k == 'st': v = v[1:-1].replace('\\"', '"').replace('\\n', '\n')
            s.t.append((k, v))
        s.i = 0

    def peek(s, k=0):
        j = s.i + k
        return s.t[j] if j < len(s.t) else ('eof', '')

    def take(s):
        tok = s.peek(); s.i += 1; return tok

    def is_(s, v, k=0):
        kind, val = s.peek(k)
        return kind == 'pu' and val == v

    def block(s, open_, close):
        """consume a balanced block that starts at the current token; -> its inner tokens joined by spaces"""
        depth, out = 0, []
        while True:
            kind, v = s.take()
            if kind == 'eof': break
            if kind == 'pu' and v == open_:
                depth += 1
                if depth == 1: continue
            elif kind == 'pu' and v == close:
                depth -= 1
                if depth == 0: break
            out.append(v)
        return ' '.join(out)

    def text(s):
        """a string, with "a" + "b" continuations joined; a bare word is accepted too"""
        kind, v = s.peek()
        if kind not in ('st', 'wd'): return ''
        s.i += 1
        while kind == 'st' and s.is_('+') and s.peek(1)[0] == 'st':
            s.i += 1; v += s.take()[1]
        return v


_HELPER_SKIP = {'base', 'iconsprite', 'studio', 'color', 'size', 'tags', 'model', 'sprite', 'line', 'sphere', 'cylinder', 'halfgridsnap',
                'editormodel', 'worldtext', 'sweptplayerhull', 'studioprop', 'lightprop', 'lightcone', 'frustum', 'axis', 'wirebox'}


def _read_class(s, kind):
    c = EntClass('', kind)
    while True:                                   # header: helpers until '='
        k, v = s.peek()
        if k == 'eof' or (k == 'pu' and v in '[@'): return None   # @mapsize(...) and friends
        if k == 'pu' and v == '=':
            s.take(); break
        s.take()
        if k == 'wd' and s.is_('('):
            inner = s.block('(', ')')
            if v.lower() == 'base':
                c.bases += [b for b in re.split(r'[\s,]+', inner) if b]
            elif v.lower() not in _HELPER_SKIP:
                c.helper_keys |= {w.lower() for w in re.findall(r'[A-Za-z_]\w*', inner) if w == w.lower()}
        elif k == 'wd' and s.is_('{'):
            s.block('{', '}')
    k, name = s.take()
    if k != 'wd': return None
    c.name = name
    if s.is_(':'):
        s.take(); c.desc = s.text()
    if not s.is_('['): return c
    s.take()
    while True:
        k, v = s.peek()
        if k == 'eof': break
        if k == 'pu' and v == ']':
            s.take(); break
        if k == 'wd' and v.lower() in ('input', 'output') and s.peek(1)[0] == 'wd' and s.is_('(', 2):
            s.take(); io_name = s.take()[1]; io_type = s.block('(', ')').replace(' ', '')
            hlp = ''
            if s.is_(':'):
                s.take(); hlp = s.text()
            (c.inputs if v.lower() == 'input' else c.outputs)[io_name.lower()] = (io_name, io_type, hlp)
            continue
        if k == 'wd' and s.is_('(', 1):
            _read_key(s, c); continue
        s.take()
    return c


def _read_key(s, c):
    name = s.take()[1]
    key = Key(name, s.block('(', ')').replace(' ', '').lower())
    while True:                                   # flags and [ metadata ] / { metadata } before the first ':'
        k, v = s.peek()
        if k == 'wd' and v.lower() in ('readonly', 'report'):
            key.readonly |= v.lower() == 'readonly'; s.take()
        elif k == 'pu' and v == '[': s.block('[', ']')
        elif k == 'pu' and v == '{': s.block('{', '}')
        else: break
    if s.is_(':'):
        s.take(); key.label = s.text() if s.peek()[0] == 'st' else ''
        if s.is_(':'):
            s.take()
            if s.peek()[0] in ('st', 'wd'): key.default = s.text()
            if s.is_(':'):
                s.take(); key.help = s.text() if s.peek()[0] == 'st' else ''
    if s.is_('=') and s.is_('[', 1):
        s.take(); s.take()
        bits_on = 0
        while True:
            k, v = s.peek()
            if k == 'eof': break
            if k == 'pu' and v == ']':
                s.take(); break
            if k not in ('st', 'wd'):
                s.take(); continue
            value = s.take()[1]; label = ''
            if s.is_(':'):
                s.take(); label = s.text()
                if s.is_(':'):                    # spawnflags: bit : "label" : on-by-default
                    s.take(); on = s.take()[1]
                    if on == '1':
                        try: bits_on += int(value)
                        except ValueError: pass
            key.choices.append((value, label))
        if key.type == 'flags' and bits_on and not key.default: key.default = str(bits_on)
    c.keys[name.lower()] = key


def parse_into(text, classes, excluded):
    s = _Stream(text)
    while True:
        k, v = s.take()
        if k == 'eof': return
        if not (k == 'pu' and v == '@'): continue
        kind = s.take()[1]
        low = kind.lower()
        if low == 'exclude':
            excluded.add(s.take()[1].lower()); continue
        if not low.endswith('class'): continue
        c = _read_class(s, kind)
        if c is None or not c.name: continue
        lname = c.name.lower()
        old = classes.get(lname)
        if old is not None and low == 'overrideclass':
            old.merge(c)
        else:
            if low == 'overrideclass': c.kind = 'PointClass'
            classes[lname] = c
        if low != 'baseclass': excluded.discard(lname)


class Catalog:
    def __init__(s, classes, excluded, files=()):
        s.classes, s.excluded, s.files = classes, excluded, list(files)
        s._kcache, s._iocache = {}, {}

    @classmethod
    def from_texts(cls, texts, files=()):
        classes, excluded = {}, set()
        for t in texts: parse_into(t, classes, excluded)
        return cls(classes, excluded, files)

    @classmethod
    def from_files(cls, paths):
        texts = []
        for p in paths:
            with open(p, encoding='utf-8', errors='replace') as f: texts.append(f.read())
        return cls.from_texts(texts, paths)

    # ------------------------------------------------------------ lookups
    def chain(s, name, seen=None):
        """the class and its bases, bases first (Hammer's inheritance order)"""
        seen = set() if seen is None else seen
        c = s.classes.get(name.lower())
        if c is None or c.name.lower() in seen: return []
        seen.add(c.name.lower())
        out = []
        for b in c.bases: out += s.chain(b, seen)
        return out + [c]

    def is_entity(s, name):
        c = s.classes.get(name.lower())
        return c is not None and c.kind.lower() != 'baseclass' and name.lower() not in s.excluded

    def kind(s, name):
        c = s.classes.get(name.lower())
        return c.kind if c else None

    def keys(s, name):
        """{lower key: Key} with inheritance applied (remove_key deletes)"""
        n = name.lower()
        if n not in s._kcache:
            out = {}
            for c in s.chain(n):
                for k, key in c.keys.items():
                    if key.type == 'remove_key': out.pop(k, None)
                    else: out[k] = key
            s._kcache[n] = out
        return s._kcache[n]

    def helper_keys(s, name):
        return set().union(*[c.helper_keys for c in s.chain(name)]) if s.chain(name) else set()

    def io(s, name):
        """({lower input: (name, type, help)}, {lower output: ...})"""
        n = name.lower()
        if n not in s._iocache:
            ins, outs = {}, {}
            for c in s.chain(n):
                ins.update(c.inputs); outs.update(c.outputs)
            s._iocache[n] = (ins, outs)
        return s._iocache[n]

    def defaults(s, name):
        """keyvalues Hammer writes for a freshly placed entity of this class (no node keys)"""
        return {k.name: k.default for lk, k in s.keys(name).items() if lk not in NODE_KEYS}

    def similar(s, name, n=6):
        ents = [c.name for c in s.classes.values() if s.is_entity(c.name)]
        close = difflib.get_close_matches(name, ents, n=n, cutoff=0.6)
        sub = [x for x in ents if name.lower() in x.lower() and x not in close]
        return (close + sorted(sub))[:n]

    def search(s, text, limit=40):
        t = text.lower()
        hits = [(c.name, c.kind, c.desc) for c in s.classes.values()
                if c.kind.lower() != 'baseclass' and (t in c.name.lower() or t in c.desc.lower())]
        hits.sort(key=lambda h: (not h[0].lower().startswith(t), t not in h[0].lower(), h[0]))
        return hits[:limit]

    def describe(s, name):
        if not s.is_entity(name):
            why = 'excluded by the FGDs' if name.lower() in s.excluded else 'not an entity class in the installed FGDs'
            return {'classname': name, 'error': why, 'similar': s.similar(name)}
        c = s.classes[name.lower()]
        ins, outs = s.io(name)
        return {'classname': c.name, 'kind': c.kind, 'brush_entity': c.kind.lower() == 'solidclass', 'description': c.desc,
                'bases': [b.name for b in s.chain(name)[:-1]],
                'keyvalues': [k.as_dict() for lk, k in s.keys(name).items() if lk not in NODE_KEYS],
                'inputs': sorted(v[0] for v in ins.values()), 'outputs': sorted(v[0] for v in outs.values())}

    def stats(s):
        ents = [c for c in s.classes.values() if c.kind.lower() != 'baseclass']
        return {'files': len(s.files), 'classes': len(s.classes), 'entity_classes': len(ents),
                'brush_classes': sum(c.kind.lower() == 'solidclass' for c in ents), 'excluded': sorted(s.excluded)}


_LOADED = {}


def load(root=None):
    """the catalog of the installed game (cached per install path)"""
    root = root or cs2_root()
    if root not in _LOADED:
        paths = fgd_paths(root)
        if not paths: raise FileNotFoundError('no .fgd files under %s' % os.path.join(root, 'game'))
        _LOADED[root] = Catalog.from_files(paths)
    return _LOADED[root]


def main(argv):
    if len(argv) < 2 or argv[1] not in ('describe', 'search', 'defaults', 'stats'):
        print(__doc__); return 2
    cat = load()
    if argv[1] == 'stats': out = cat.stats()
    elif argv[1] == 'search': out = [{'classname': n, 'kind': k, 'description': d[:160]} for n, k, d in cat.search(' '.join(argv[2:]))]
    elif argv[1] == 'defaults': out = cat.defaults(argv[2]) if cat.is_entity(argv[2]) else cat.describe(argv[2])
    else: out = cat.describe(argv[2])
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
