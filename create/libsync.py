"""libsync.py: keeps the shared tool files identical across skink52's CS2 repos, and flags project tools that changed after
their project-neutral copy in create/ was made.

The repos are expected side by side (../hellmatch-cs2, ../space-racer-cs2, ... next to cs2mapping); a missing one is skipped.
The list lives in libsync.json next to this file:
  copies: canonical file in cs2mapping -> {repo: path}. Must be byte-identical everywhere. cs2mapping holds the master.
  forks:  neutral file in create/ -> {origin: "repo:path", seen: git blob of the origin when it was last reviewed}.
          A changed origin means a fix or feature there may belong in the neutral copy too.

usage:
  libsync.py check                      report drift (exit 1 if any)
  libsync.py push [repo ...]            copy every canonical file out to the repos (all repos if none named)
  libsync.py pull <canonical> <repo>    a repo's copy has the newer fix: take it as the master (then push)
  libsync.py ack <neutral|all>          a fork's origin changes were reviewed / ported: record the origin as seen
  libsync.py add <canonical> <repo> <path>   track another copy
  --root DIR   folder holding the repo checkouts (default: the folder above cs2mapping)
"""
import json, os, subprocess, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CFG = os.path.join(HERE, 'libsync.json')
args = sys.argv[1:]
ROOT = os.path.dirname(REPO)
if '--root' in args:
    i = args.index('--root'); ROOT = args[i + 1]; del args[i:i + 2]


def load(): return json.load(open(CFG))


def save(c): open(CFG, 'w', newline='\n').write(json.dumps(c, indent=1, sort_keys=True) + '\n')


def rpath(repo, path): return os.path.join(REPO if repo == 'cs2mapping' else os.path.join(ROOT, repo), path)


def have(repo): return os.path.isdir(rpath(repo, '.git'))


def blob(p): return subprocess.run(['git', 'hash-object', p], capture_output=True, text=True).stdout.strip() if os.path.exists(p) else None


def last_change(repo, path):
    r = subprocess.run(['git', '-C', rpath(repo, ''), 'log', '-1', '--format=%cI', '--', path], capture_output=True, text=True)
    return r.stdout.strip() or 'uncommitted'


def check():
    c = load(); bad = 0; skipped = set()
    for canon, outs in sorted(c['copies'].items()):
        cb = blob(rpath('cs2mapping', canon))
        for repo, path in sorted(outs.items()):
            if not have(repo): skipped.add(repo); continue
            b = blob(rpath(repo, path))
            if b == cb: continue
            bad += 1
            if b is None: print('MISSING  %s:%s  (push)' % (repo, path)); continue
            mine, theirs = last_change('cs2mapping', canon), last_change(repo, path)
            hint = 'pull %s %s' % (canon, repo) if theirs > mine else 'push %s' % repo
            print('DIFFERS  %s:%s  master %s, copy %s  -> diff them, then %s' % (repo, path, mine[:16], theirs[:16], hint))
    for neutral, f in sorted(c['forks'].items()):
        repo, path = f['origin'].split(':', 1)
        if not have(repo): skipped.add(repo); continue
        if blob(rpath(repo, path)) == f['seen']: continue
        bad += 1
        log = subprocess.run(['git', '-C', rpath(repo, ''), 'log', '--format=  %h %cs %s', '--', path], capture_output=True, text=True).stdout.split('\n')
        new = []
        for line in log:
            if not line: continue
            h = line.split()[0]
            if subprocess.run(['git', '-C', rpath(repo, ''), 'rev-parse', '%s:%s' % (h, path)], capture_output=True, text=True).stdout.strip() == f['seen']: break
            new.append(line)
        print('ORIGIN CHANGED  %s <- %s  (port what is generic into %s, then: ack %s)' % (neutral, f['origin'], neutral, neutral))
        print('\n'.join(new[:8]) if new else '  (uncommitted changes)')
    for r in sorted(skipped): print('skipped %s (no checkout under %s)' % (r, ROOT))
    print('libsync: %s' % ('%d problem(s)' % bad if bad else 'all in step'))
    return bad


def push(repos):
    c = load(); n = 0
    for canon, outs in sorted(c['copies'].items()):
        src = rpath('cs2mapping', canon)
        for repo, path in sorted(outs.items()):
            if repos and repo not in repos or not have(repo): continue
            dst = rpath(repo, path)
            if blob(dst) == blob(src): continue
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); n += 1
            print('pushed %s -> %s:%s' % (canon, repo, path))
    print('%d file(s) pushed; commit them in each repo' % n)


def main():
    if not args: sys.exit(__doc__)
    cmd = args[0]
    if cmd == 'check': sys.exit(1 if check() else 0)
    elif cmd == 'push': push(args[1:])
    elif cmd == 'pull':
        c = load(); canon, repo = args[1], args[2]
        shutil.copyfile(rpath(repo, c['copies'][canon][repo]), rpath('cs2mapping', canon)); print('master %s <- %s' % (canon, repo))
    elif cmd == 'ack':
        c = load()
        for k in (c['forks'] if args[1] == 'all' else [args[1]]):
            repo, path = c['forks'][k]['origin'].split(':', 1)
            if have(repo): c['forks'][k]['seen'] = blob(rpath(repo, path))
        save(c)
    elif cmd == 'add':
        c = load(); c['copies'].setdefault(args[1], {})[args[2]] = args[3]; save(c)
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main()
