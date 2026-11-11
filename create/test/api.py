"""Look up Valve's cs_script API in point_script.d.ts instead of remembering it, and check a script's calls against it.

  python create/test/api.py <word> [word ...]     every declaration whose name contains all the words: container, signature, doc
  python create/test/api.py --members <Type>      everything a class / interface / enum declares (e.g. --members CSPlayerPawn)
  python create/test/api.py --list                the containers and how many members each has
  python create/test/api.py <word> --examples 3   the same, with up to 3 lines from this repo's scripts that call it
  python create/test/api.py --check <script.js | glob> [...] [--strict] [--json] [--allow FILE | --no-allow]
        every `Instance.X`, `Entities.X`, `GameRules.X`, `Console.X` the script uses that the typings do not declare (INVALID, exit 1),
        and every one they mark @deprecated (DEPRECATED, with the current spelling where one is known; exit 1 with --strict). Also
        `.Method(` calls on anything, when no class declares a member of that name at all. A quick first check;
        `sh create/test/tscheck.sh <script.js>` (TypeScript) is the complete one. Quoted globs are expanded here (`**` allowed).
  python create/test/api.py --check ... --allow-lines      print allowlist lines for the deprecated calls found (to start a baseline)

The allowlist (create/test/api_allow.txt unless --allow names another) holds deprecated calls kept on purpose, one per line:
`<path glob>  <Instance.Name or *>  <reason>`. An allowed call is counted and shown as ALLOWED, never as a problem, so --strict
fails only on a deprecated call nobody wrote a reason for. It never excuses a call the typings do not have.
A clean check is "simulated" in the words of docs/reference/compatibility.md: the names exist; it says nothing about CS2 at run time.

Why: the typings are 50 KB and change with CS2 updates (calls moved from Instance to Entities / GameRules / Console in Oct-Nov 2026).
Reading two matching lines here costs less than reading the file, and far less than a call written from memory that does not exist.
Reads point_script.d.ts next to this file (--dts FILE for another copy). Python 3.9+, standard library. Writes nothing.
"""
import argparse, fnmatch, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTAINER = re.compile(r'^\s*(?:export\s+|declare\s+)*(?:abstract\s+)?(class|interface|enum|namespace)\s+([A-Za-z_]\w*)')
MEMBER = re.compile(r'^\s*(?:readonly\s+|static\s+)*([A-Za-z_]\w*)\s*(\??\s*[(:=<]|,|$)')
TOP = re.compile(r'^\s*(?:export\s+|declare\s+)*(const|type|function)\s+([A-Za-z_]\w*)\s*(.*)$')
GLOBALS = {'Instance': 'IPointScript', 'Entities': 'IEntities', 'GameRules': 'IGameRules', 'Console': 'IConsole'}
REPO = os.path.dirname(os.path.dirname(HERE))
ALLOW = os.path.join(HERE, 'api_allow.txt')
try:                                                # the replacement table lives with the migrator (tools/jsapi.py), one copy
    sys.path.insert(0, os.path.join(REPO, 'tools')); import jsapi; REPLACEMENT = jsapi.REPLACEMENT
except ImportError:
    REPLACEMENT = {}


def replacement(g, name):
    """The current spelling of a deprecated call, or '' when this repo has not established one."""
    return REPLACEMENT.get(name, '') if g == 'Instance' else ''


def load_allow(path):
    """-> [(path glob, 'Instance.Name' or '*', reason)]; a missing file is an empty list."""
    out = []
    try:
        with open(path, encoding='utf-8') as f:
            for raw in f:
                t = raw.split('#', 1)[0].split(None, 2)
                if len(t) == 3: out.append((t[0].replace('\\', '/'), t[1], t[2].strip()))
                elif t: raise SystemExit('api.py: %s: every line needs <path glob> <call or *> <reason>: %r' % (path, raw.strip()))
    except OSError:
        pass
    return out


def allowed(allow, script, call):
    """The reason this deprecated call is kept in this file, or None."""
    try: rel = os.path.relpath(os.path.abspath(script), REPO).replace('\\', '/')
    except ValueError: rel = script.replace('\\', '/')
    for pat, name, reason in allow:
        if (name == '*' or name == call) and (fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(script.replace('\\', '/'), pat)): return reason
    return None


def examples(name, limit):
    """Up to `limit` lines from this repo's scripts that call .name( : real usage, not documentation."""
    out = []
    for pat in ('ports/*/scripts/*.js', 'create/**/*.js', 'projects/*/src/**/*.js'):
        for f in sorted(glob.glob(os.path.join(REPO, pat), recursive=True)):
            try:
                with open(f, encoding='utf-8', errors='replace') as fh:
                    for no, line in enumerate(fh, 1):
                        if re.search(r'\.\s*%s\s*\(' % re.escape(name), line) and not line.lstrip().startswith(('//', '*')):
                            out.append('%s:%d: %s' % (os.path.relpath(f, REPO).replace('\\', '/'), no, line.strip()[:160])); break
            except OSError:
                continue
            if len(out) >= limit: return out
    return out


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
    if d['deprecated'] and d['container'] == 'IPointScript' and REPLACEMENT.get(d['name']): text += '\n    use instead: ' + REPLACEMENT[d['name']]
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
            r = replacement(g, name)
            deprecated.append((line, '%s.%s is deprecated%s' % (g, name, ('; use ' + r) if r else (': ' + d['doc'][:200]))))
        seen.add(key); seen.add('m:' + name)            # already judged as a call on the global: not again as a bare method
    if imported and script.lower().endswith(('.js', '.mjs', '.ts')):                            # not for JS held inside a .py generator: its own Python calls would match
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
    ap.add_argument('--json', action='store_true'); ap.add_argument('--allow', default=ALLOW); ap.add_argument('--no-allow', action='store_true')
    ap.add_argument('--allow-lines', action='store_true'); ap.add_argument('--examples', type=int, default=0, metavar='N')
    a = ap.parse_args(argv)
    try: decls = parse(a.dts)
    except OSError as ex:
        print('api.py: cannot read %s (%s)' % (a.dts, ex), file=sys.stderr); return 2
    if a.check:
        allow = [] if a.no_allow else load_allow(a.allow)
        files = []
        for s in a.check:
            hits = sorted(glob.glob(s, recursive=True)) if any(ch in s for ch in '*?[') else [s]
            files += [h for h in hits if h not in files]
        bad = 0; rows = []; n_inv = n_dep = n_ok = 0
        for s in files:
            try: unknown, dep = check(decls, s)
            except OSError as ex:
                rows.append({'file': s, 'line': 0, 'kind': 'unreadable', 'call': '', 'text': str(ex)}); bad += 1; continue
            for line, text in unknown: rows.append({'file': s, 'line': line, 'kind': 'invalid', 'call': text.split(' is not')[0], 'text': text}); n_inv += 1
            for line, text in dep:
                call = text.split(' is deprecated')[0]; why = allowed(allow, s, call)
                rows.append({'file': s, 'line': line, 'kind': 'allowed' if why else 'deprecated', 'call': call, 'text': text,
                             'replacement': replacement(*call.split('.', 1)), 'reason': why or ''})
                if why: n_ok += 1
                else: n_dep += 1
        bad += n_inv + (n_dep if a.strict else 0)
        if not files: print('api.py: no script matches %s' % ' '.join(a.check), file=sys.stderr); return 2
        if a.allow_lines:
            for r in rows:
                if r['kind'] == 'deprecated': print('%-58s %-36s %s' % (r['file'].replace('\\', '/'), r['call'], 'baseline: not yet moved to the current API'))
            return 0
        if a.json:
            print(json.dumps({'scripts': len(files), 'invalid': n_inv, 'deprecated': n_dep, 'allowed': n_ok, 'strict': a.strict, 'ok': not bad,
                              'level': 'simulated', 'findings': rows}, indent=1))
            return 1 if bad else 0
        tag = {'invalid': 'INVALID', 'deprecated': 'DEPRECATED', 'allowed': 'ALLOWED', 'unreadable': 'UNREADABLE'}
        for r in rows:
            print('%s:%d: %s %s%s' % (r['file'], r['line'], tag[r['kind']], r['text'], (' [kept: %s]' % r['reason']) if r['kind'] == 'allowed' else ''))
        print('api check: %d script%s, %d problem%s (%d invalid, %d deprecated%s, %d allowed by %s)' % (
            len(files), '' if len(files) == 1 else 's', bad, '' if bad == 1 else 's', n_inv, n_dep, '' if a.strict or not n_dep else ': listed only, --strict fails on them',
            n_ok, os.path.basename(a.allow) if not a.no_allow else 'nothing'))
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
    if a.json:
        print(json.dumps({'query': a.members or a.words, 'declarations': [dict(d, replacement=replacement('Instance', d['name']) if d['deprecated'] and d['container'] == 'IPointScript' else '',
                          examples=examples(d['name'], a.examples) if a.examples else []) for d in hits]}, indent=1))
        return 0 if hits else 1
    for d in hits:
        print(show(d))
        for e in (examples(d['name'], a.examples) if a.examples else []): print('    e.g. ' + e)
    print('%d declaration%s' % (len(hits), '' if len(hits) == 1 else 's'))
    return 0 if hits else 1


if __name__ == '__main__':
    sys.exit(main())
