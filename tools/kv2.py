"""Parse DMX keyvalues2 text (what Valve's importer writes for the main .vmap) into a dmx.Doc,
so it can be edited and saved as binary 9 like Hammer does."""
import re, uuid
import dmx

TYPES = {'element': 1, 'int': 2, 'float': 3, 'bool': 4, 'string': 5, 'binary': 6, 'time': 7, 'color': 8, 'vector2': 9,
         'vector3': 10, 'vector4': 11, 'qangle': 12, 'quaternion': 13, 'matrix': 14, 'uint64': 15, 'uint8': 16}
_tok = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}\[\],])|//[^\n]*|(\S+)')

def _unesc(s): return s.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')

def _scalar(t, s):
    if t == 2: return int(s)
    if t == 3: return float(s)
    if t == 4: return s.strip() not in ('0', 'false', '')
    if t == 5: return _unesc(s).encode('utf-8')
    if t == 6: return bytes.fromhex(''.join(s.split()))
    if t == 7: return int(round(float(s) * 10000))
    if t == 8: return [int(x) for x in s.split()]
    if t in (9, 10, 11, 12, 13, 14): return [float(x) for x in s.split()]
    if t == 15: return int(s, 16) if s.lower().startswith('0x') else int(s)
    if t == 16: return int(s)
    raise ValueError(t)

def loads(text):
    if isinstance(text, bytes): text = text.decode('utf-8')
    nl = text.index('\n')
    toks = [(m.group(1) is not None, m.group(1) if m.group(1) is not None else (m.group(2) or m.group(3))) for m in _tok.finditer(text, nl + 1)
            if m.group(1) is not None or m.group(2) or m.group(3)]
    pos = [0]
    def nxt(): t = toks[pos[0]]; pos[0] += 1; return t
    def peek(): return toks[pos[0]] if pos[0] < len(toks) else (False, None)
    elements = []; by_id = {}; refs = []   # refs: (element index, attr index, list index or None, guid)
    def parse_element(etype):
        q, b = nxt(); assert b == '{', b
        idx = len(elements); el = {'type': etype.encode(), 'name': b'', 'guid': b'', 'attrs': []}; elements.append(el)
        while True:
            q, name = nxt()
            if not q and name == '}': break
            q2, typ = nxt()
            if typ == 'elementid':
                _, v = nxt(); g = uuid.UUID(v).bytes; el['guid'] = g; by_id[g] = idx; continue
            if typ.endswith('_array'):
                bt = TYPES[typ[:-6]]; nxt()  # [
                vals = []
                while True:
                    qv, v = nxt()
                    if not qv and v == ']': break
                    if not qv and v == ',': continue
                    if bt == 1:
                        if v == 'element':
                            _, g = nxt()
                            if g: refs.append((idx, len(el['attrs']), len(vals), uuid.UUID(g).bytes)); vals.append(-1)
                            else: vals.append(-1)
                        else: vals.append(parse_element(v))
                    else: vals.append(_scalar(bt, v))
                el['attrs'].append([name.encode(), bt + 32, vals]); continue
            if typ in TYPES:
                t = TYPES[typ]; _, v = nxt()
                if t == 1:
                    if v: refs.append((idx, len(el['attrs']), None, uuid.UUID(v).bytes))
                    el['attrs'].append([name.encode(), 1, -1]); continue
                if name == 'name' and t == 5: el['name'] = _unesc(v).encode('utf-8'); continue
                el['attrs'].append([name.encode(), t, _scalar(t, v)]); continue
            # inline element: "attr" "ElementType" { ... }
            el['attrs'].append([name.encode(), 1, parse_element(typ)])
        return idx
    tops = []
    while pos[0] < len(toks):
        q, etype = nxt(); tops.append(parse_element(etype))
    for ei, ai, li, g in refs:
        j = by_id.get(g, -1)
        if li is None: elements[ei]['attrs'][ai][2] = j
        else: elements[ei]['attrs'][ai][2][li] = j
    # binary layout: root element first, $prefix_element$ second
    root = next(i for i in tops if elements[i]['type'] == b'CMapRootElement')
    pre = [i for i in tops if elements[i]['type'] == b'$prefix_element$']
    order = [root] + pre + [i for i in range(len(elements)) if i != root and i not in pre]
    remap = {o: n for n, o in enumerate(order)}
    doc = dmx.Doc(); doc.header = b'<!-- dmx encoding binary 9 format vmap 40 -->\n'
    for o in order:
        e = elements[o]; attrs = []
        for n, t, v in e['attrs']:
            if t == 1: v = remap[v] if v >= 0 else -1
            elif t == 33: v = [remap[x] if x >= 0 else -1 for x in v]
            attrs.append([n, t, v])
        doc.elements.append({**e, 'attrs': attrs})
    doc.prefix = [[list(a) for a in doc.elements[1]['attrs']]] if pre else []
    return doc
