"""existing_ports.txt helpers and addon-name cleaning.

  python3 ports.py check <existing_ports.txt> <bsp or map name> [...]   # possible duplicates + cleaned names
  python3 ports.py add <existing_ports.txt> <name> [status] [mapper]    # default: [in progress] [skink]
"""
import re, sys, difflib

BLOAT = r'(?:v\d+[a-z]*(?:[._]\d+[a-z]*)*|b\d+[a-z]?|rc\d*|beta\d*|alpha\d*|final\d*|fix(?:ed)?\d*|hotfix\d*|update[ds]?\d*|patch\d*|csgo|cs2|hdr|ldr|ws|wip)'

def clean_name(base):
    """bsp file name -> addon name: lower case, only a-z0-9_, version/bloat suffixes stripped (mg_x_v2_final -> mg_x)."""
    n = re.sub(r'[^a-z0-9_]+', '_', base.lower()).strip('_')
    n = re.sub(r'_+', '_', n)
    prev = None
    while prev != n:
        prev = n
        n = re.sub(r'_' + BLOAT + r'$', '', n)
    return n or base.lower()

PREFIX = r'^(?:mg|de|cs|jb|ba_jail|ba|dr|deathrun|surf|bhop|kz|aim|awp|ka|fy|gg|zm|ze|ttt|hns|minigame|course)_'

def core(name):
    """comparison key: no prefix, version, _cs2, separators"""
    n = clean_name(re.split(r'\s+-\s+|\s*\[|:', name.strip())[0].strip().replace(' ', '_'))
    for _ in range(2): n = re.sub(PREFIX, '', n)
    return re.sub(r'[_\s]+', '', n)

def entries(text):
    out = []
    for ln in text.splitlines():
        if not ln.strip(): continue
        out.append((ln, core(ln)))
    return out

def check(text, names):
    res = {}
    ents = entries(text)
    for nm in names:
        k = core(nm); hits = []
        for ln, ek in ents:
            if not ek: continue
            r = difflib.SequenceMatcher(None, k, ek).ratio()
            if k == ek or (min(len(k), len(ek)) >= 5 and (k in ek or ek in k)) or r >= 0.9:
                hits.append((round(r, 2), ln.strip()))
        res[nm] = (clean_name(nm), sorted(hits, reverse=True))
    return res

def add(text, name, status='[in progress]', mapper='[skink]'):
    """add or update a line; keeps CRLF. Never touches [ported] / [*original*] / [ext. port] lines."""
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)
    pat = re.compile(r'^\s*' + re.escape(name) + r'(?=\s|\[|:|$)', re.I)
    for i, ln in enumerate(lines):
        if pat.match(ln):
            if re.search(r'\[(ported|\*original\*|ext\. port)\]', ln): return text
            if re.search(r'\[in progress[^\]]*\]', ln): ln = re.sub(r'\[in progress[^\]]*\]', status, ln)
            else: ln = ln.rstrip() + ' ' + status
            if mapper and mapper not in ln: ln += ' ' + mapper
            lines[i] = ln
            return nl.join(lines)
    while lines and not lines[-1].strip(): lines.pop()
    lines.append('%s %s %s' % (name, status, mapper) if mapper else '%s %s' % (name, status))
    return nl.join(lines)

if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]
    text = open(path, encoding='utf-8', errors='replace', newline='').read()
    if cmd == 'check':
        for nm, (cl, hits) in check(text, sys.argv[3:]).items():
            print('%s -> addon name %s' % (nm, cl))
            for r, ln in hits: print('   POSSIBLE EXISTING PORT (%.2f): %s' % (r, ln))
    elif cmd == 'add':
        a = sys.argv[3:]
        t = add(text, a[0], *(a[1:]))
        open(path, 'w', encoding='utf-8', newline='').write(t)
