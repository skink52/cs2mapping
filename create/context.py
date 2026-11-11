"""One compact snapshot of a project (or a port) to read before opening its long documents.

  python create/context.py <project or path> [--lines 40] [--max-bytes 12000] [--json]
  python create/context.py --list

<project> is a folder under projects/ or ports/ (name or path). The snapshot holds, in this order:
  where it stands   the sections of its status / notes file whose heading says so (Resume here, To do, Next steps, Open questions,
                    Status), each cut to --lines lines, with the line number to read on from
  what to read      the heading outline of its docs, with sizes, so the right section can be opened instead of the whole file
  git               branch, uncommitted files in the folder (someone may be working there), the last commits that touched it
  scripts           its cs_script sources, the API calls they make most, calls the current typings mark deprecated or do not have,
                    and the input names they answer to
  overrides         weapons.vdata (weapon ids it changes) and other game-file overrides in its addon
  tests             the test files and the commands its README gives for them

A project can steer it with an optional `context.json` in its folder: {"status": "docs/STATUS.md", "sections": ["Resume here"],
"scripts": ["src/cs2/*.js"], "notes": "one line shown at the top"}. Without one, the usual file names are tried.

It reads files and asks git; it writes nothing (so it cannot go stale in the repo: run it when you need it). It is a map of where to
look, not a replacement for the documents: read the section it points at before changing anything. Python 3.9+, standard library.
"""
import argparse, glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'test'))
STATUS_NAMES = ('docs/STATUS.md', 'STATUS.md', 'NOTES.md', 'docs/NOTES.md', 'CLAUDE.md', 'README.md')
WANT = re.compile(r'resume|to[ -]?do|next step|open question|^status|where (it|things) stand|still open|left to do|open issue', re.I)
HEAD = re.compile(r'^(#{1,4})\s+(.*?)\s*$')


def find_project(arg):
    for cand in (arg, os.path.join(REPO, arg), os.path.join(REPO, 'projects', arg), os.path.join(REPO, 'ports', arg)):
        if os.path.isdir(cand): return os.path.abspath(cand)
    hits = [d for d in glob.glob(os.path.join(REPO, 'projects', '*')) + glob.glob(os.path.join(REPO, 'ports', '*'))
            if os.path.isdir(d) and arg.lower() in os.path.basename(d).lower()]
    if len(hits) == 1: return hits[0]
    raise SystemExit('context.py: %s' % ('no project matches %r (try --list)' % arg if not hits else '%r matches several: %s' % (arg, ', '.join(os.path.basename(h) for h in hits[:8]))))


def read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f: return f.read()
    except OSError:
        return ''


def sections(text):
    """[(level, title, first line number, [lines])] outside code fences"""
    out, cur, fence = [], None, False
    for no, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith('```'): fence = not fence
        m = None if fence else HEAD.match(line)
        if m:
            cur = [len(m.group(1)), m.group(2), no, []]; out.append(cur)
        elif cur is not None:
            cur[3].append(line)
    return out


def git(args, cwd):
    try:
        r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True, errors='replace', timeout=30)
        return r.stdout.strip().splitlines() if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        return []


def script_facts(files):
    try: import api
    except ImportError: return {}
    try: decls = api.parse(os.path.join(HERE, 'test', 'point_script.d.ts'))
    except OSError: return {}
    calls, inputs, unknown, deprecated = {}, set(), set(), set()
    for f in files:
        src = read(f)
        for g, n in re.findall(r'\b(Instance|Entities|GameRules|Console)\s*\.\s*([A-Za-z_]\w*)', src): calls[g + '.' + n] = calls.get(g + '.' + n, 0) + 1
        inputs |= set(re.findall(r'OnScriptInput\(\s*["\']([^"\']+)["\']', src))
        try: u, d = api.check(decls, f)
        except OSError: continue
        unknown |= {t.split(' is not')[0] for _, t in u if t.startswith(('Instance', 'Entities', 'GameRules', 'Console'))}
        deprecated |= {t.split(' is deprecated')[0] for _, t in d}
    return {'calls': sorted(calls.items(), key=lambda kv: -kv[1])[:14], 'inputs': sorted(inputs), 'unknown': sorted(unknown), 'deprecated': sorted(deprecated)}


def snapshot(root, lines=40):
    conf = {}
    try:
        with open(os.path.join(root, 'context.json'), encoding='utf-8') as f: conf = json.load(f)
    except (OSError, ValueError):
        pass
    try: rel = os.path.relpath(root, REPO).replace('\\', '/')
    except ValueError: rel = root.replace('\\', '/')            # a project folder on another drive than the repo
    snap = {'project': os.path.basename(root), 'path': rel, 'notes': conf.get('notes', '')}

    status = next((s for s in ([conf['status']] if conf.get('status') else []) + list(STATUS_NAMES) if os.path.isfile(os.path.join(root, s))), None)
    snap['status_file'] = status; snap['where'] = []
    if status:
        text = read(os.path.join(root, status)); secs = sections(text)
        want = conf.get('sections')
        for lvl, title, no, body in secs:
            if (title in want) if want else WANT.search(title):
                body = [b for b in body if b.strip()]
                snap['where'].append({'title': title, 'line': no, 'text': body[:lines], 'more': max(0, len(body) - lines)})
        snap['status_bytes'] = len(text.encode('utf-8'))

    docs = []
    for p in sorted(glob.glob(os.path.join(root, '*.md')) + glob.glob(os.path.join(root, 'docs', '*.md'))):
        t = read(p)
        docs.append({'file': os.path.relpath(p, root).replace('\\', '/'), 'bytes': len(t.encode('utf-8')),
                     'headings': ['%s%s (line %d)' % ('  ' * (l - 1), ti, no) for l, ti, no, _ in sections(t) if l <= 2][:14]})
    snap['docs'] = docs

    snap['git'] = {'branch': (git(['rev-parse', '--abbrev-ref', 'HEAD'], root) or ['?'])[0],
                   'uncommitted': git(['status', '--short', '--', '.'], root)[:20],
                   'recent': git(['log', '-6', '--format=%h %ad %s', '--date=short', '--', '.'], root)}

    pats = conf.get('scripts') or ['src/**/*.js', 'src/*.js', 'scripts/*.js', 'addon/maps/scripts/*.js', 'out/addon/maps/scripts/*.js']
    files = []
    for pat in pats:
        for f in sorted(glob.glob(os.path.join(root, pat), recursive=True)):
            if f not in files and os.path.isfile(f): files.append(f)
    if any('src' in os.path.relpath(f, root).split(os.sep)[:1] for f in files):          # sources win over built copies of the same script
        files = [f for f in files if not os.path.relpath(f, root).replace('\\', '/').startswith('out/')]
    snap['scripts'] = [{'file': os.path.relpath(f, root).replace('\\', '/'), 'bytes': os.path.getsize(f)} for f in files][:40]
    snap['script_facts'] = script_facts(files) if files else {}

    over = []
    for f in glob.glob(os.path.join(root, '**', 'weapons.vdata'), recursive=True)[:3]:
        ids = sorted(set(re.findall(r'^\s*"?(weapon_[a-z0-9_]+)"?\s*=?\s*$', read(f), flags=re.M)))
        over.append({'file': os.path.relpath(f, root).replace('\\', '/'), 'weapons': ids[:40]})
    snap['overrides'] = over

    tests = sorted(os.path.relpath(f, root).replace('\\', '/') for f in glob.glob(os.path.join(root, 'test', '*')) if os.path.isfile(f))
    cmds = []
    for name in ('README.md', 'TESTING.md', 'docs/TESTING.md', 'CLAUDE.md'):
        for c in re.findall(r'`((?:node|sh|python3?|python -I|tsc|cd test)[^`\n]{3,140})`', read(os.path.join(root, name))):
            if re.search(r'test|mock|tsc|build', c) and c not in cmds: cmds.append(c)
    snap['tests'] = {'files': tests[:40], 'more': max(0, len(tests) - 40), 'commands': cmds[:12]}
    return snap


def render(s, max_bytes=None):
    L = ['# %s  (%s)' % (s['project'], s['path'])]
    if s['notes']: L.append(s['notes'])
    L.append('\n## Where it stands' + (' (from %s, %d KB: read on from the line given)' % (s['status_file'], s.get('status_bytes', 0) // 1024) if s['status_file'] else ''))
    if not s['where']: L.append('No "Resume here" / "To do" / "Next steps" section found%s. Read the outline below.' % ((' in ' + s['status_file']) if s['status_file'] else ''))
    for w in s['where']:
        L.append('### %s  [%s line %d]' % (w['title'], s['status_file'], w['line'])); L += w['text']
        if w['more']: L.append('... %d more lines in this section' % w['more'])
    g = s['git']
    L.append('\n## Git'); L.append('branch %s' % g['branch'])
    if g['uncommitted']: L.append('UNCOMMITTED in this folder (someone may be working here; do not overwrite or commit these without asking):'); L += ['  ' + u for u in g['uncommitted']]
    L += ['recent: ' + r for r in g['recent']]
    if s['scripts']:
        L.append('\n## Scripts'); L += ['%s  %d KB' % (x['file'], x['bytes'] // 1024) for x in s['scripts'][:16]]
        if len(s['scripts']) > 16: L.append('... and %d more' % (len(s['scripts']) - 16))
        f = s['script_facts']
        if f.get('calls'): L.append('most used API: ' + ', '.join('%s x%d' % kv for kv in f['calls']))
        if f.get('inputs'): L.append('script inputs answered: ' + ', '.join(f['inputs'][:40]))
        if f.get('unknown'): L.append('NOT IN THE TYPINGS: ' + ', '.join(f['unknown']))
        if f.get('deprecated'): L.append('deprecated in the typings: ' + ', '.join(f['deprecated']))
        L.append('look up a signature before using it: python create/test/api.py <word>')
    for o in s['overrides']: L.append('\n## Override  %s: %s' % (o['file'], ', '.join(o['weapons']) or 'no weapon ids found'))
    t = s['tests']
    if t['files'] or t['commands']:
        L.append('\n## Tests'); L += ['run: ' + c for c in t['commands']]
        if t['files']: L.append('files: ' + ', '.join(os.path.basename(x) for x in t['files']) + (' ... +%d' % t['more'] if t['more'] else ''))
    L.append('\n## What to read (open the section, not the file)')
    for d in s['docs']:
        L.append('%s  %d KB' % (d['file'], d['bytes'] // 1024)); L += ['  ' + h for h in d['headings']]
    text = '\n'.join(L) + '\n'
    if max_bytes and len(text.encode('utf-8')) > max_bytes:
        text = text.encode('utf-8')[:max_bytes].decode('utf-8', 'ignore').rsplit('\n', 1)[0] + '\n... cut at %d bytes (--max-bytes)\n' % max_bytes
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description='A compact snapshot of a project to read before its long documents (read-only)')
    ap.add_argument('project', nargs='?'); ap.add_argument('--list', action='store_true'); ap.add_argument('--lines', type=int, default=40)
    ap.add_argument('--max-bytes', type=int, default=12000); ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if a.list or not a.project:
        for d in sorted(glob.glob(os.path.join(REPO, 'projects', '*'))):
            if os.path.isdir(d): print('projects/' + os.path.basename(d))
        print('ports/<addon>: %d folders' % len([d for d in glob.glob(os.path.join(REPO, 'ports', '*')) if os.path.isdir(d)]))
        return 0
    s = snapshot(find_project(a.project), a.lines)
    print(json.dumps(s, indent=1) if a.json else render(s, a.max_bytes), end='' if not a.json else '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
