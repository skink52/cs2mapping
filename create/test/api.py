"""Look up Valve's cs_script API in point_script.d.ts instead of remembering it, and check a script's calls against it.

  python create/test/api.py <word> [word ...]     every declaration whose name contains all the words: container, signature, doc
  python create/test/api.py --members <Type>      everything a class / interface / enum declares (e.g. --members CSPlayerPawn)
  python create/test/api.py --list                the containers and how many members each has
  python create/test/api.py --check <script.js> [...]
        every `Instance.X`, `Entities.X`, `GameRules.X`, `Console.X` the script uses that the typings do not declare (exit 1), and every
        one they mark @deprecated (listed; exit 1 with --strict). Also `.Method(` calls on anything, when no class declares a member of
        that name at all. A quick first check; `sh create/test/tscheck.sh <script.js>` (TypeScript) is the complete one.

Why: the typings are 50 KB and change with CS2 updates (calls moved from Instance to Entities / GameRules / Console in Oct-Nov 2026).
Reading two matching lines here costs less than reading the file, and far less than a call written from memory that does not exist.
Reads point_script.d.ts next to this file (--dts FILE for another copy). Python 3.9+, standard library. Writes nothing.
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTAINER = re.compile(r'^\s*(?:export\s+|declare\s+)*(?:abstract\s+)?(class|interface|enum|namespace)\s+([A-Za-z_]\w*)')
MEMBER = re.compile(r'^\s*(?:readonly\s+|static\s+)*([A-Za-z_]\w*)\s*(\??\s*[(:=<]|,|$)')
TOP = re.compile(r'^\s*(?:export\s+|declare\s+)*(const|type|function)\s+([A-Za-z_]\w*)\s*(.*)$')
GLOBALS = {'Instance': 'IPointScript', 'Entities': 'IEntities', 'GameRules': 'IGameRules', 'Console': 'IConsole'}


def parse(path):
    """-> [{'container', 'kind', 'name', 'sig', 'doc', 'deprecated', 'line'}]"""
    out, stack, doc, in_doc = [], [], [], False
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    pending = None                                   # a container declared on a line whose "{" comes on the next
    for no, raw in enumerate(lines, 1):
        s = raw.strip()
        if in_doc:
            doc.append(s.lstrip('*').strip()); in_doc = '*/' not in s
            if not in_doc: doc[-1] = doc[-1].replace('*/', '').rstrip('/').strip()
            continue
        if s.startswith('/**'):
            doc = [s[3:].replace('*/', '').strip()]; in_doc = '*/' not in s
            continue
        if not s or s.startswith('//'):
            continue
        m = CONTAINER.match(raw)
        if m:
            pending = (m.group(1), m.group(2))
            out.append({'container': stack[-1][1] if stack and stack[-1][0] != 'namespace' else '', 'kind': m.group(1), 'name': m.group(2),
                        'sig': s.rstrip('{').strip(), 'doc': ' '.join(d for d in doc if d), 'deprecated': any('@deprecated' in d for d in doc), 'line': no})
            doc = []
        elif stack and stack[-1][0] in ('class', 'interface', 'enum'):
            mm = MEMBER.match(raw)
            if mm and not s.startswith('}'):
                sig = s.rstrip(';,').strip()
                out.append({'container': stack[-1][1], 'kind': 'member', 'name': mm.group(1), 'sig': sig,
                            'doc': ' '.join(d for d in doc if d), 'deprecated': any('@deprecated' in d for d in doc), 'line': no})
            doc = []
        else:
            t = TOP.match(raw)
            if t:
                out.append({'container': '', 'kind': t.group(1), 'name': t.group(2), 'sig': s.rstrip(';'), 'doc': ' '.join(d for d in doc if d),
                            'deprecated': any('@deprecated' in d for d in doc), 'line': no})
            doc = []
        for ch in raw:
            if ch == '{':
                stack.append(pending or ('block', '')); pending = None
            elif ch == '}' and stack:
                stack.pop()
    return out


def show(d):
    where = (d['container'] + '.') if d['container'] else ''
    text = '%s%s   [%s, line %d]%s\n    %s' % (where, d['name'], d['kind'], d['line'], '  DEPRECATED' if d['deprecated'] else '', d['sig'])
    if d['doc']: text += '\n    // ' + d['doc'][:400]
    return text


def check(decls, script):
    """-> (unknown [(line, text)], deprecated [(line, text)])"""
    members = {}
    for d in decls:
        if d['kind'] != 'member': continue
        old = members.setdefault(d['container'], {}).get(d['name'])
        # overloads: a name counts as deprecated only when every overload is (several calls kept an old signature beside the new one)
        if old is None or (old['deprecated'] and not d['deprecated']): members[d['container']][d['name']] = d
    anywhere = {d['name'] for d in decls if d['kind'] == 'member'}
    with open(script, encoding='utf-8', errors='replace') as f:
        src = f.read()
    src_nc = re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), src)                       # keep line numbers, drop line comments
    src_nc = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), src_nc, flags=re.S)
    imported = set(re.findall(r'\b(Instance|Entities|GameRules|Console)\b', ' '.join(re.findall(r'import\s*\{([^}]*)\}\s*from\s*["\']cs_script/point_script["\']', src))))
    unknown, deprecated, seen = [], [], set()
    for m in re.finditer(r'\b(Instance|Entities|GameRules|Console)\s*\.\s*([A-Za-z_]\w*)', src_nc):
        g, name = m.group(1), m.group(2)
        if g not in imported: continue                                                          # a local variable that happens to share the name
        line = src_nc.count('\n', 0, m.start()) + 1
        d = members.get(GLOBALS[g], {}).get(name)
        key = (g, name)
        if d is None:
            if key not in seen:
                hint = sorted(c for c, mm in members.items() if name in mm)
                unknown.append((line, '%s.%s is not in the typings%s' % (g, name, (' (declared on: %s)' % ', '.join(hint)) if hint else '')))
        elif d['deprecated'] and key not in seen:
            deprecated.append((line, '%s.%s is deprecated: %s' % (g, name, d['doc'][:200])))
        seen.add(key); seen.add('m:' + name)            # already judged as a call on the global: not again as a bare method
    if imported:                                                                                # only for scripts that use the API at all
        own = set(re.findall(r'\b(?:function\s+|(?:const|let|var)\s+)([A-Za-z_]\w*)', src_nc)) | set(re.findall(r'\b([A-Za-z_]\w*)\s*[:=]\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>)', src_nc)) | set(re.findall(r'^\s*(?:async\s+|static\s+)*([A-Za-z_]\w*)\s*\([^)]*\)\s*\{', src_nc, flags=re.M))
        for m in re.finditer(r'\.\s*((?:Get|Set|Is|Find|Fire|Trace|Give|Remove|Destroy|Teleport|Take|Join|Kill|Connect|Debug|Client|Server|Emit|Stop|Enter|Play)[A-Z]\w*)\s*\(', src_nc):
            name = m.group(1)
            if name in anywhere or name in own or ('m:' + name) in seen: continue
            seen.add('m:' + name)
            unknown.append((src_nc.count('\n', 0, m.start()) + 1, '.%s() is not a member of any class in the typings (a method of your own, or a call that does not exist)' % name))
    return unknown, deprecated


def main(argv=None):
    ap = argparse.ArgumentParser(description='Look up the cs_script API in point_script.d.ts')
    ap.add_argument('words', nargs='*'); ap.add_argument('--members'); ap.add_argument('--list', action='store_true')
    ap.add_argument('--check', nargs='+', metavar='SCRIPT'); ap.add_argument('--strict', action='store_true'); ap.add_argument('--dts', default=os.path.join(HERE, 'point_script.d.ts'))
    a = ap.parse_args(argv)
    try: decls = parse(a.dts)
    except OSError as ex:
        print('api.py: cannot read %s (%s)' % (a.dts, ex), file=sys.stderr); return 2
    if a.check:
        bad = 0
        for s in a.check:
            try: unknown, dep = check(decls, s)
            except OSError as ex:
                print('%s: cannot read (%s)' % (s, ex)); bad += 1; continue
            for line, text in unknown: print('%s:%d: %s' % (s, line, text))
            for line, text in dep: print('%s:%d: %s' % (s, line, text))
            bad += len(unknown) + (len(dep) if a.strict else 0)
        print('api check: %d script%s, %d problem%s' % (len(a.check), '' if len(a.check) == 1 else 's', bad, '' if bad == 1 else 's'))
        return 1 if bad else 0
    if a.list:
        for d in decls:
            if d['kind'] in ('class', 'interface', 'enum'):
                print('%-10s %-28s %3d members  (line %d)' % (d['kind'], d['name'], sum(1 for x in decls if x['container'] == d['name'] and x['kind'] == 'member'), d['line']))
        for g, t in GLOBALS.items(): print('global     %-28s is %s' % (g, t))
        return 0
    if a.members:
        t = GLOBALS.get(a.members, a.members)
        hits = [d for d in decls if d['container'].lower() == t.lower() and d['kind'] == 'member']
    elif a.words:
        ws = [w.lower() for w in a.words]
        hits = [d for d in decls if all(w in (d['container'] + '.' + d['name']).lower() for w in ws)]
    else:
        ap.print_help(); return 2
    for d in hits: print(show(d))
    print('%d declaration%s' % (len(hits), '' if len(hits) == 1 else 's'))
    return 0 if hits else 1


if __name__ == '__main__':
    sys.exit(main())
